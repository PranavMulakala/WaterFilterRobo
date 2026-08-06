"""V5-F -- route wiring: the triage grade selects the route, end to end.

    ../venv/bin/python v5_route.py --eval 28        held-out; --seed0 defaults to 1700
    ../venv/bin/python v5_route.py --run 1700       one unit, verbose

WHAT THIS IS. The three v5 stations exist and are measured independently. This wires them
together along `dp_process.V5_ROUTES`.

  A CORRECTION TO HOW THAT USED TO BE PHRASED (2026-08-05). This module and V5_PLAN said
  the routes were "theirs, not invented". Overstated. The three-way EASY/MEDIUM/HARD
  fan-out and the HARD fork are DrinkPrime's, but `dp_process.V5_ROUTES` itself says it
  "describes what OUR CELL does -- a deliberate subset". The step SEQUENCES are ours,
  assembled from their stages. Their vocabulary, our composition.

    easy                 TRIAGE -> CLEAN_CABINET -> VERIFY_CLEAN -> PASS
    medium               ... -> MEMBRANE_INSERT -> CAP_TIGHTEN -> LEAK_DIP -> VERIFY_LEAK
    hard_rectifiable     same line as medium  (their chart rejoins it)
    hard_non_rectifiable TRIAGE -> ROUTE_TO_SCRAP_APPROVAL

AND A SECOND ONE, WHICH MATTERS MORE. Route-plan compliance compares `steps_done` to
`plan`, so any step with no motion behind it PASSES BY BEING NAMED. Two did.
`MEMBRANE_INSERT` was one of them and is now a REAL, MEASURED motion (2026-08-05) -- the
arm picks the element and places it in the open bowl, judged on the element. What remains
UNBACKED is `ROUTE_TO_SCRAP_APPROVAL`: nothing physically delivers a unit anywhere, it is
a software decision. Every run prints which steps are MEASURED, which are a PROXY and
which are UNBACKED. Do not quote compliance -- or end-to-end, which inherits it -- as
"every named action was performed".

THE FORK WE CANNOT DECIDE, AND DO NOT PRETEND TO. Their chart splits HARD into
RECTIFIABLE and NON RECTIFIABLE on whether rectification cost exceeds 80-90% -- of what,
no document in the set says. Our classifier outputs three grades and has no cost model, no
price list and no labour figure, so **it cannot make that call**. A cell that guessed would
be scrapping units on a number it invented.

So HARD routes to **SCRAP_APPROVAL**, which is a HUMAN DECISION GATE, and the cycle stops
there. That is exactly what `V5_ROUTES['hard_non_rectifiable']` says we do -- "We stop at
routing it out of the line" -- and for the rectifiable half it is the honest answer too:
the unit is presented to a person, who decides. Routing a HARD unit CORRECTLY therefore
means "delivered to the approval gate", not "repaired" -- and note "delivered" is a
SOFTWARE DECISION, not motion: nothing physically moves the unit (STEP_EVIDENCE).

WHAT COUNTS AS SUCCESS, and it is judged on the workpiece. THREE DISTINCT METRICS, and
keeping them distinct is the point -- the first two answer different questions and only
the third is the headline:
  * route-plan compliance -- did the cell execute the plan its own PREDICTION selected?
                             This says nothing about whether that prediction was right.
  * right-route accuracy  -- did the predicted grade match the unit's TRUTH? This is the
                             route the unit actually needed, and it is capped by triage.
  * per-step success      -- cleaning verified with zero residue; cap stalled on torque
                             and the leak check passed.
  * end-to-end            -- RIGHT ROUTE **and** every step of it succeeded. It requires
                             all three of the above.
  * the dangerous error is still FALSE-EASY: a unit needing deep work sent down the
    cosmetic path. It is reported separately, as it has been since v4's false-clean.

RETRACTION, 2026-08-05. This module previously computed end-to-end as
`routing_ok and clean_ok and leak_ok`, with `plan` selected from the PREDICTED grade -- so
a misgraded unit that completed its wrong route scored as a full end-to-end success, and
the published "28/28 (right route AND every step of it succeeded)" asserted something the
code never checked. Seed 1517 (truth easy -> graded medium) was such a unit. That figure is
RETRACTED; `grade_correct` is now required for `end_to_end`. Route-plan compliance was and
remains a real, separate measurement -- it is not deleted and it is not merged in.
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

# WHAT ACTUALLY BACKS EACH STEP NAME. A route step is a STRING appended to `steps_done`,
# and route-plan compliance is `steps_done == plan` -- so a step with no motion behind it
# passes by being named. That is not a hypothetical: two of these are exactly that, and
# hiding it inside a 28/28 would be the same class of error as the retracted end-to-end.
#
#   MEASURED   a physical quantity from the sim decides pass/fail (force, torque, pixels)
#   PROXY      the motion is real but the CONSEQUENCE is modelled, not computed
#   UNBACKED   a CLAIMED ACTION with no motion and no measurement -- the string is all of it
#   META       bookkeeping, claims no action at all
STEP_EVIDENCE = {
    "TRIAGE":                 ("MEASURED", "camera grades the unit; 97.5% held out"),
    "CLEAN_CABINET":          ("MEASURED", "pad rasters 5 faces; coverage, force, tilt logged"),
    "VERIFY_CLEAN":           ("MEASURED", "2nd camera re-inspects; residue counted"),
    "MEMBRANE_INSERT":        ("MEASURED", "arm picks the element and places it in the OPEN "
                                           "bowl; seating judged on the element (off-axis "
                                           "mm, base vs floor, upright). Was UNBACKED until "
                                           "2026-08-05 -- the capped bowl had no path in"),
    "CAP_TIGHTEN":            ("MEASURED", "ARM places the cap (thread-start capture 4mm/4deg "
                                           "modelled) and holds the driver; spindle advances "
                                           "only while the wrist holds station; stalls on torque"),
    "LEAK_DIP":               ("PROXY",    "dip motion is real; BUBBLES ARE MODELLED FROM "
                                           "TORQUE, no fluid or gas is simulated"),
    "VERIFY_LEAK":            ("MEASURED", "camera must actually SEE bubbles to fail it"),
    "ROUTE_TO_SCRAP_APPROVAL":("UNBACKED", "a software decision. NO robot or indexer motion "
                                           "delivers the unit anywhere"),
    # META, not UNBACKED: a terminator is not a CLAIMED ACTION, and lumping it in made
    # every EASY/MEDIUM route look as though it contained unbacked work -- diluting
    # attention from the one place that actually does (the HARD handoff).
    "PASS":                   ("META",     "bookkeeping terminator, not a claimed action"),
}


def route_evidence(plan):
    """(measured, proxy, unbacked) step counts for a route plan."""
    kinds = [STEP_EVIDENCE.get(s, ("UNBACKED", "unknown step"))[0] for s in plan]
    return (kinds.count("MEASURED"), kinds.count("PROXY"), kinds.count("UNBACKED"))


def fully_backed(row):
    """True when the route contains no CLAIMED ACTION that nothing implements.

    This is the count to publish next to end-to-end. `end_to_end` is a SOFTWARE verdict:
    for the HARD route `steps_ok` is unconditionally True, so a HARD unit scores an
    end-to-end success on the strength of a correct grade and a matching trace alone.
    """
    return not row["unbacked_steps"]


class RouteCell(MB.MemCell):
    """One cell that can triage, clean, verify and assemble -- the stations already built.

    Inherits MemCell -> CL.Cell, so nothing here re-derives motion, planning or grading.
    """

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        # PIN v5_triage's face-projection globals, and restore them before every grade.
        #
        # CFG_CAB_XY / CAB_HALF_XY / CAB_BASE / CAB_TOP are MODULE-LEVEL state in
        # v5_triage, and v5_clean.verify() writes to them through _sync_triage_globals().
        # Any caller that writes them BEFORE mj_forward has run is reading all-zero
        # geom_xpos, and gets garbage that still looks like plausible geometry:
        #
        #   load_scene()              XY (0.58, 0.0)  BASE  0.010  TOP 0.46   correct
        #   _sync on UNFORWARDED data XY (0.00, 0.0)  BASE -0.220  TOP 0.22   garbage
        #   _sync AFTER mj_forward    XY (0.58, 0.0)  BASE  0.010  TOP 0.46   correct
        #
        # The tell is BASE == -TOP. With every geom_xpos still at the origin each geom
        # spans 0 +/- its own half-extent, so "the cabinet" becomes a box centred on the
        # world origin whose height is just the largest half-size (cab_body, 0.22). The
        # device also lands at x = 0, which is the more damaging half: the projected face
        # quads miss the part entirely and the grader returns HARD for EVERY unit.
        # Measured -- 4 of 7 sampled seeds flip, and seed 1500 goes truth EASY -> HARD,
        # the two-class jump the published confusion matrix says never happens.
        #
        # CORRECTION, 2026-08-05. This comment used to say load_scene() computes
        # CAB_TOP = 0.220 and that the frozen triage thresholds were calibrated against a
        # half-face region. BOTH ARE FALSE and the story was inverted. load_scene() calls
        # mj_forward and returns 0.46; v5_triage's module-level defaults are ALREADY
        # (0.58, 0.0) / (0.09, 0.125) / 0.010 / 0.46; the thresholds are therefore
        # calibrated against the FULL face. There are not two internally-consistent
        # conventions here -- there is one correct value and one uninitialised read.
        #
        # WHAT THIS GUARD IS ACTUALLY WORTH, stated honestly: verify() is the only caller
        # of _sync_triage_globals(), and in the current cycle it always runs after
        # mj_forward, where it writes values IDENTICAL to these at every indexer angle
        # (0/90/180/270/360 all checked). So today the restore is a NO-OP -- insurance
        # against call ordering, not a live fix. The root cause is that Cell.__init__
        # never forwards its MjData; correcting that is a controller change and needs a
        # full re-eval, so it is deliberately not done here.
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
            # MARGINS, not just the rate -- the binding rule. A composed system must not
            # throw away the evidence that made its components credible, so the cleaning
            # station's physical margins travel into the route row.
            out["f_max"] = float(cr["f_max"])
            out["in_band"] = float(cr["in_band"])
            out["tilt_max_deg"] = float(cr["tilt_max"])
            out["raster_skipped"] = int(cr["raster_skipped"])
            out["raster_infeasible"] = int(cr["raster_infeasible"])
            out["coupling_drift_mm"] = float(cr["coupling_drift_mm"])
            if verbose:
                print(f"    CLEAN: coverage {cr['coverage']*100:.1f}%, residue "
                      f"{v['soil_left_truth']}, verified {v['verified']}")
            if route in ("medium", "hard_rectifiable"):
                # --- the Stage-10 subassembly, the V5-E station
                self.reset_mem(seed)
                ins = self.insert_element()
                self.cap_present(True)
                mujoco.mj_forward(self.m, self.d)
                tg = self.tighten()
                steps_done += ["MEMBRANE_INSERT", "CAP_TIGHTEN"]
                chg = self.pressurise(tg["torque_nm"])
                self.emit_bubbles(chg["seal_holds"])
                px, _ = self.dip_and_grade()
                steps_done += ["LEAK_DIP", "VERIFY_LEAK"]
                out["elem_inserted"] = bool(ins["inserted"])
                out["elem_align_mm"] = ins["align_mm"]
                out["elem_seat_xy_mm"] = ins["seat_xy_mm"]
                out["turns"] = tg["turns"]
                out["torque_nm"] = tg["torque_nm"]
                out["bubble_px"] = px
                # membrane margins, same rule
                out["peak_torque_nm"] = float(tg["peak_torque_nm"])
                out["seal_n"] = float(tg["seal_n"])
                out["peak_seal_n"] = float(tg["peak_seal_n"])
                out["stalled"] = bool(tg["stalled"])
                out["cap_z_mm"] = float(tg["cap_z_mm"])
                out["leak_ok"] = bool(px <= self.mcfg.bubble_px_max
                                      and tg["stalled"]
                                      and tg["torque_nm"] >= self.mcfg.torque_pass_nm
                                      and ins["inserted"])
                out["leak_false_pass"] = bool(px <= self.mcfg.bubble_px_max
                                              and not chg["seal_holds"])
                if verbose:
                    print(f"    MEMBRANE: {tg['turns']:.2f} turns, "
                          f"{tg['torque_nm']:.2f} Nm, bubbles {px} px, "
                          f"leak_ok {out['leak_ok']}")
            steps_done.append("PASS")

        # --- route-plan compliance: did we execute the plan the PREDICTION selected?
        # This is a real measurement of the wiring -- "the cell did what it decided to do"
        # -- and it is deliberately NOT the same question as whether the decision was
        # right. `plan` comes from the predicted grade, so a misgraded unit can comply
        # perfectly. Kept separate for exactly that reason.
        out["steps_done"] = steps_done
        out["routing_ok"] = bool(steps_done == list(plan))
        # how much of that compliance is actually backed by physics
        meas, proxy, unb = route_evidence(plan)
        out["steps_measured"], out["steps_proxy"], out["steps_unbacked"] = meas, proxy, unb
        out["unbacked_steps"] = [s for s in plan
                                 if STEP_EVIDENCE.get(s, ("UNBACKED",))[0] == "UNBACKED"]
        # --- right route: did the prediction match the unit's truth? Capped by triage.
        out["grade_correct"] = bool(grade == truth)
        # --- end to end: RIGHT route AND every step of it worked. Without grade_correct
        # this would score a wrong-route unit as a success (seed 1517 did exactly that).
        if route == "hard_non_rectifiable":
            steps_ok = True
        elif route == "easy":
            steps_ok = bool(out["clean_ok"])
        else:
            steps_ok = bool(out["clean_ok"] and out["leak_ok"])
        out["end_to_end"] = bool(out["grade_correct"] and out["routing_ok"] and steps_ok)
        # --- the dangerous error, carried through from triage
        out["false_easy"] = bool(truth != "easy" and grade == "easy")
        out["missed_hard"] = bool(truth == "hard" and grade != "hard")
        return out


def report(rows):
    n = len(rows)
    comply = sum(r["routing_ok"] for r in rows)
    right = sum(r["grade_correct"] for r in rows)
    e2e = sum(r["end_to_end"] for r in rows)
    fe = sum(r["false_easy"] for r in rows)
    mh = sum(r["missed_hard"] for r in rows)
    print(f"\nV5-F ROUTE WIRING: {n} units, held out")
    print(f"  route-plan compliance : {comply}/{n} ({comply/n*100:.1f}%)   "
          f"(cell executed the plan its own PREDICTION selected --")
    print(f"  {'':<22}  says nothing about whether that prediction was right)")
    print(f"  RIGHT ROUTE           : {right}/{n} ({right/n*100:.1f}%)   "
          f"(predicted grade == truth; capped by triage)")
    fb = sum(fully_backed(r) for r in rows)
    fbe = sum(r["end_to_end"] and fully_backed(r) for r in rows)
    print(f"  END-TO-END (software) : {e2e}/{n} ({e2e/n*100:.1f}%)   "
          f"(right route AND every step its route DEFINES succeeded)")
    print(f"  ...FULLY BACKED       : {fbe}/{n} ({fbe/n*100:.1f}%)   <- the honest headline:")
    print(f"  {'':<22}  end-to-end AND no claimed action that nothing implements.")
    print(f"  {'':<22}  {n-fb} of {n} routes here contain one. For HARD, `steps_ok`")
    print(f"  {'':<22}  is UNCONDITIONALLY True -- a correct grade plus a matching")
    print(f"  {'':<22}  trace is the whole of it, with no physical handoff.")
    print(f"  FALSE-EASY            : {fe}/{n} ({fe/n*100:.1f}%)   <- the dangerous error")
    print(f"  missed-hard           : {mh}/{n} ({mh/n*100:.1f}%)")
    wrong = [r for r in rows if not r["grade_correct"]]
    if wrong:
        print(f"\n  misgraded (wrong route, so NOT end-to-end successes even where every")
        print(f"  step of the wrong route completed):")
        for r in wrong:
            print(f"    seed {r['seed']}: truth {r['truth']:<6} -> graded "
                  f"{r['grade']:<6} route {r['route']:<21} "
                  f"plan-compliant={'Y' if r['routing_ok'] else 'N'}")
    print(f"\n  by route:")
    for rt in ("easy", "medium", "hard_non_rectifiable"):
        sel = [r for r in rows if r["route"] == rt]
        if not sel:
            continue
        ok = sum(r["end_to_end"] for r in sel)
        print(f"    {rt:<22} n={len(sel):<3} end-to-end {ok}/{len(sel)}")
    # ---- WHAT THE COMPLIANCE NUMBER IS AND IS NOT MADE OF
    nun = len({s for r in rows for s in r["unbacked_steps"]})
    print(f"\n  ROUTE-PLAN COMPLIANCE COUNTS STEP NAMES, AND {nun} OF THEM HAS NO MOTION")
    print("  BEHIND IT. Per step, what actually decides it:")
    for s, (kind, why) in STEP_EVIDENCE.items():
        used = sum(s in r["plan"] for r in rows)
        if not used:
            continue
        mark = {"MEASURED": "  ", "PROXY": "~ ", "META": ". "}.get(kind, "!!")
        print(f"   {mark}{kind:<9} {s:<24} n={used:<3} {why}")
    unb = sorted({s for r in rows for s in r["unbacked_steps"]} - {"PASS"})
    print(f"\n  => {', '.join(unb)} still pass by BEING NAMED: nothing physically")
    print("     delivers a unit to the scrap gate, it is a software decision. Read")
    print("     compliance as 'the cell ran the sequence it chose', NOT as 'every named")
    print("     action was performed'. END-TO-END INHERITS THIS CAVEAT.")
    print("     (MEMBRANE_INSERT was on this list until 2026-08-05 and is now MEASURED --")
    print("      the arm really picks the element and places it in the open bowl.)")

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
    # ---- MARGINS, not just rates. The rule that caught a systemic defect once already.
    if cl:
        fm = np.array([r["f_max"] for r in cl])
        tl = np.array([r["tilt_max_deg"] for r in cl])
        ib = np.array([r["in_band"] for r in cl])
        sk = sum(r["raster_skipped"] for r in cl)
        inf = sum(r["raster_infeasible"] for r in cl)
        dr = np.array([r["coupling_drift_mm"] for r in cl])
        print(f"\n  MARGINS (cleaning, n={len(cl)}):")
        print(f"    peak force      {fm.max():6.2f} N   vs 45 N model-validity ceiling"
              f"   -> {'OK' if fm.max() <= 45 else 'OVER'}")
        print(f"    in-band frac    {ib.min()*100:6.1f}%  worst unit")
        print(f"    peak tilt       {tl.max():6.2f} deg vs 30 deg cone"
              f"              -> {'OK' if tl.max() <= 30.001 else 'OVER'}")
        print(f"    raster skipped  {sk:6d}     infeasible {inf}")
        print(f"    tool drift      {dr.max():6.3f} mm  worst unit")
    if lk:
        pt = np.array([r["peak_torque_nm"] for r in lk])
        sn = np.array([r["seal_n"] for r in lk])
        sp = np.array([r["peak_seal_n"] for r in lk])
        print(f"  MARGINS (membrane, n={len(lk)}):")
        print(f"    peak torque     {pt.min():6.2f}-{pt.max():.2f} N.m   stalled "
              f"{sum(r['stalled'] for r in lk)}/{len(lk)}")
        # BOTH, deliberately: V5-E publishes the PEAK (341 N). Printing only the settled
        # figure would read as contradicting it. The gap is elastic relaxation after the
        # drive stops, not a disagreement between stations.
        print(f"    seal preload    {sp.min():6.0f}-{sp.max():.0f} N peak, "
              f"{sn.min():.0f}-{sn.max():.0f} N settled after the drive releases")
    print("\n  The cleaning trajectory is OPEN-LOOP and seed-independent: force, tilt and")
    print("  raster figures do not vary with the seed and must not be quoted as a spread.")
    print("\n  THE HARD FORK IS NOT DECIDED BY THIS CELL. DrinkPrime's chart splits HARD")
    print("  into RECTIFIABLE and NON RECTIFIABLE on whether rectification cost exceeds")
    print("  80-90% -- of what, no document in the set says. We have no cost model, so a")
    print("  HARD unit is routed to SCRAP_APPROVAL, a human decision gate, and the cycle")
    print("  stops there. Routing a HARD unit CORRECTLY means 'handed off in software',")
    print("  not 'repaired'. Asking what defines that fork is on the open-ask list.")
    print("  Easy/Medium/Hard class NAMES are DrinkPrime's; the BOUNDARIES are ours.")
    st = {"n": n, "routing_compliance": comply / n, "right_route": right / n,
          "end_to_end": e2e / n, "fully_backed": fbe / n,
          "routing_compliance_n": comply, "right_route_n": right, "end_to_end_n": e2e,
          "fully_backed_n": fbe,
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
    # 1700 is the range that reproduces the PUBLISHED result. A bare --eval must
    # reproduce, never replace: 1500-1539 are spent development seeds.
    ap.add_argument("--seed0", type=int, default=1700)
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
                  f"right={'Y' if r['grade_correct'] else 'N'} "
                  f"e2e={'Y' if r['end_to_end'] else 'N'}")
        report(rows)
    else:
        ap.print_help()
        sys.exit(1)
