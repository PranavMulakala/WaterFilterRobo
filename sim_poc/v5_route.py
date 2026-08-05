"""V5-F -- route wiring: the triage grade selects the route, end to end.

    ../venv/bin/python v5_route.py --eval 12        held-out; --seed0 defaults to 1500
    ../venv/bin/python v5_route.py --run 1500       one unit, verbose

WHAT THIS IS. The three v5 stations exist and are measured independently. This wires them
into DrinkPrime's own routing, taken from `dp_process.V5_ROUTES` rather than invented:

    easy                 TRIAGE -> CLEAN_CABINET -> VERIFY_CLEAN -> PASS
    medium               ... -> MEMBRANE_INSERT -> CAP_TIGHTEN -> LEAK_DIP -> VERIFY_LEAK
    hard_rectifiable     same line as medium  (their chart rejoins it)
    hard_non_rectifiable TRIAGE -> ROUTE_TO_SCRAP_APPROVAL

THE FORK WE CANNOT DECIDE, AND DO NOT PRETEND TO. Their chart splits HARD into
RECTIFIABLE and NON RECTIFIABLE on whether rectification cost exceeds 80-90% -- of what,
no document in the set says. Our classifier outputs three grades and has no cost model, no
price list and no labour figure, so **it cannot make that call**. A cell that guessed would
be scrapping units on a number it invented.

So HARD routes to **SCRAP_APPROVAL**, which is a HUMAN DECISION GATE, and the cycle stops
there. That is exactly what `V5_ROUTES['hard_non_rectifiable']` says we do -- "We stop at
routing it out of the line" -- and for the rectifiable half it is the honest answer too:
the unit is presented to a person, who decides. Routing a HARD unit CORRECTLY therefore
means "delivered to the approval gate", not "repaired".

WHAT COUNTS AS SUCCESS, and it is judged on the workpiece:
  * routing compliance -- did the cell execute the route its own grade selected?
  * per-step success   -- cleaning verified with zero residue; cap stalled on torque and
                          the leak check passed
  * end-to-end         -- right route AND every step of it succeeded
  * the dangerous error is still FALSE-EASY: a unit needing deep work sent down the
    cosmetic path. It is reported separately, as it has been since v4's false-clean.
"""
import argparse
import json
import sys

import numpy as np
import mujoco

import dp_process as DP
import v5_triage as TR
import v5_membrane as MB

GRADE_ROUTE = {"easy": "easy", "medium": "medium", "hard": "hard_non_rectifiable"}


class RouteCell(MB.MemCell):
    """One cell that can triage, clean, verify and assemble -- the stations already built.

    Inherits MemCell -> CL.Cell, so nothing here re-derives motion, planning or grading.
    """

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        # CAPTURE v5_triage's OWN face-projection globals, and restore them before every
        # grade. This is not tidiness -- it is the difference between 97.5% and nonsense.
        #
        # v5_clean._sync_triage_globals() recomputes CAB_TOP from the LIVE model and gets
        # 0.460 (the true top of the device). v5_triage.load_scene() computes 0.220 from a
        # freshly-loaded MjData, and THE TRIAGE THRESHOLDS WERE FROZEN AGAINST THAT -- so
        # its per-face search quads cover roughly the lower half of each face. Grading the
        # full face with thresholds calibrated on the half-face reads far more defect area
        # and grades harder: seed 1500 went truth EASY -> predicted HARD, a two-class jump
        # the published confusion matrix says never happens.
        #
        # The station that must not move is V5-B (97.5%, frozen thresholds), so the
        # cleaning station's sync is the one that gets isolated here. Both are internally
        # consistent; they are simply not interchangeable, and nothing said so until a
        # cell tried to run both in one process.
        _m, _d, _p = TR.load_scene()
        self._tr_globals = (TR.CFG_CAB_XY, TR.CAB_HALF_XY, TR.CAB_BASE, TR.CAB_TOP)

    def _restore_triage_globals(self):
        (TR.CFG_CAB_XY, TR.CAB_HALF_XY, TR.CAB_BASE, TR.CAB_TOP) = self._tr_globals

    def grade(self, seed):
        """Triage this unit through the station camera, exactly as V5-B does."""
        if self.rend is None:
            self.rend = mujoco.Renderer(self.m, TR.CFG.cam_h, TR.CFG.cam_w)
        self._restore_triage_globals()
        row = TR.grade_unit(self.m, self.d, self.pools, self.rend, seed, TR.CFG)
        return row

    def run_route(self, seed, verbose=False):
        steps_done = []
        row = self.grade(seed)
        grade, truth = row["pred"], row["truth"]
        route = GRADE_ROUTE[grade]
        plan = DP.V5_ROUTES[route].steps
        steps_done.append("TRIAGE")
        if verbose:
            print(f"    TRIAGE: truth {truth} -> graded {grade} -> route {route}")
            print(f"      plan: {' -> '.join(plan)}")

        out = {"seed": seed, "truth": truth, "grade": grade, "route": route,
               "plan": list(plan), "clean_ok": None, "leak_ok": None,
               "turns": None, "torque_nm": None, "residue": None}

        if route == "hard_non_rectifiable":
            # the fork we cannot decide -- hand it to a person and stop
            steps_done.append("ROUTE_TO_SCRAP_APPROVAL")
            out["scrap_gate"] = True
            if verbose:
                print("    ROUTE_TO_SCRAP_APPROVAL: handed to the human cost decision, "
                      "cycle stops (we have no cost model)")
        else:
            # --- CLEAN_CABINET + VERIFY_CLEAN, the V5-C/V5-D stations
            cr = super(MB.MemCell, self).run(seed)
            steps_done.append("CLEAN_CABINET")
            v = self.verify()
            steps_done.append("VERIFY_CLEAN")
            out["clean_ok"] = bool(v["verified"] and v["soil_left_truth"] == 0)
            out["residue"] = int(v["soil_left_truth"])
            out["coverage"] = float(cr["coverage"])
            if verbose:
                print(f"    CLEAN: coverage {cr['coverage']*100:.1f}%, residue "
                      f"{v['soil_left_truth']}, verified {v['verified']}")
            if route in ("medium", "hard_rectifiable"):
                # --- the Stage-10 subassembly, the V5-E station
                self.reset_mem(seed)
                tg = self.tighten()
                steps_done += ["MEMBRANE_INSERT", "CAP_TIGHTEN"]
                chg = self.pressurise(tg["torque_nm"])
                self.emit_bubbles(chg["seal_holds"])
                px, _ = self.dip_and_grade()
                steps_done += ["LEAK_DIP", "VERIFY_LEAK"]
                out["turns"] = tg["turns"]
                out["torque_nm"] = tg["torque_nm"]
                out["bubble_px"] = px
                out["leak_ok"] = bool(px <= self.mcfg.bubble_px_max
                                      and tg["stalled"]
                                      and tg["torque_nm"] >= self.mcfg.torque_pass_nm)
                out["leak_false_pass"] = bool(px <= self.mcfg.bubble_px_max
                                              and not chg["seal_holds"])
                if verbose:
                    print(f"    MEMBRANE: {tg['turns']:.2f} turns, "
                          f"{tg['torque_nm']:.2f} Nm, bubbles {px} px, "
                          f"leak_ok {out['leak_ok']}")
            steps_done.append("PASS")

        # --- routing compliance: did we execute the route the grade selected?
        out["steps_done"] = steps_done
        out["routing_ok"] = bool(steps_done == list(plan))
        # --- end to end: right route AND every step of it worked
        if route == "hard_non_rectifiable":
            out["end_to_end"] = out["routing_ok"]
        elif route == "easy":
            out["end_to_end"] = bool(out["routing_ok"] and out["clean_ok"])
        else:
            out["end_to_end"] = bool(out["routing_ok"] and out["clean_ok"]
                                     and out["leak_ok"])
        # --- the dangerous error, carried through from triage
        out["false_easy"] = bool(truth != "easy" and grade == "easy")
        out["missed_hard"] = bool(truth == "hard" and grade != "hard")
        return out


def report(rows):
    n = len(rows)
    comply = sum(r["routing_ok"] for r in rows)
    e2e = sum(r["end_to_end"] for r in rows)
    fe = sum(r["false_easy"] for r in rows)
    mh = sum(r["missed_hard"] for r in rows)
    print(f"\nV5-F ROUTE WIRING: {n} units, held out")
    print(f"  routing compliance : {comply}/{n} ({comply/n*100:.1f}%)   "
          f"(cell executed the route its own grade selected)")
    print(f"  END-TO-END         : {e2e}/{n} ({e2e/n*100:.1f}%)   "
          f"(right route AND every step of it succeeded)")
    print(f"  FALSE-EASY         : {fe}/{n} ({fe/n*100:.1f}%)   <- the dangerous error")
    print(f"  missed-hard        : {mh}/{n} ({mh/n*100:.1f}%)")
    print(f"\n  by route:")
    for rt in ("easy", "medium", "hard_non_rectifiable"):
        sel = [r for r in rows if r["route"] == rt]
        if not sel:
            continue
        ok = sum(r["end_to_end"] for r in sel)
        print(f"    {rt:<22} n={len(sel):<3} end-to-end {ok}/{len(sel)}")
    cl = [r for r in rows if r["clean_ok"] is not None]
    lk = [r for r in rows if r["leak_ok"] is not None]
    if cl:
        print(f"\n  CLEAN_CABINET + VERIFY_CLEAN : {sum(r['clean_ok'] for r in cl)}"
              f"/{len(cl)} verified with zero residue")
    if lk:
        t = np.array([r["turns"] for r in lk])
        print(f"  CAP_TIGHTEN + VERIFY_LEAK    : {sum(r['leak_ok'] for r in lk)}"
              f"/{len(lk)} passed; turns median {np.median(t):.2f}; "
              f"leak false-pass {sum(r.get('leak_false_pass', False) for r in lk)}")
    print("\n  THE HARD FORK IS NOT DECIDED BY THIS CELL. DrinkPrime's chart splits HARD")
    print("  into RECTIFIABLE and NON RECTIFIABLE on whether rectification cost exceeds")
    print("  80-90% -- of what, no document in the set says. We have no cost model, so a")
    print("  HARD unit is routed to SCRAP_APPROVAL, a human decision gate, and the cycle")
    print("  stops there. Routing a HARD unit CORRECTLY means 'delivered to the gate',")
    print("  not 'repaired'. Asking what defines that fork is on the open-ask list.")
    print("  Easy/Medium/Hard class NAMES are DrinkPrime's; the BOUNDARIES are ours.")
    st = {"n": n, "routing_compliance": comply / n, "end_to_end": e2e / n,
          "false_easy": fe / n, "missed_hard": mh / n,
          "clean_verified": int(sum(r["clean_ok"] for r in cl)), "clean_n": len(cl),
          "leak_passed": int(sum(r["leak_ok"] for r in lk)), "leak_n": len(lk),
          "rows": rows}
    with open("stats_v5_route.json", "w") as f:
        json.dump(st, f, indent=2)
    print("\nwrote stats_v5_route.json")
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int)
    ap.add_argument("--eval", type=int)
    ap.add_argument("--seed0", type=int, default=1500)
    a = ap.parse_args()
    if a.run is not None:
        c = RouteCell()
        print(c.run_route(a.run, verbose=True))
    elif a.eval:
        c = RouteCell()
        rows = []
        for k in range(a.eval):
            r = c.run_route(a.seed0 + k)
            rows.append(r)
            print(f"  seed {a.seed0+k}: truth {r['truth']:<6} -> {r['grade']:<6} "
                  f"route {r['route']:<21} comply={'Y' if r['routing_ok'] else 'N'} "
                  f"e2e={'Y' if r['end_to_end'] else 'N'}")
        report(rows)
    else:
        ap.print_help()
        sys.exit(1)
