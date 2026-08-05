"""V5-E -- Stage 10, MEMBRANE ASSEMBLY: element into bowl, cap to torque, dip, bubbles.

    ../venv/bin/python v5_membrane.py --run 1400        one unit, verbose
    ../venv/bin/python v5_membrane.py --eval 10         held-out; --seed0 defaults to 1400
    ../venv/bin/python v5_membrane.py --sabotage 10     falsification: under-tighten

WHAT THIS IS. DrinkPrime Stage 10, in their order (3.5 -> 3.6 -> 3.7):

    3.5  "Ensure the cap is tightened properly with the spanner"
    3.6  plug the permeate outlet with an END PLUG, close the reject outlet with a
         BALL VALVE, pass 80-90 PSI air into the cap head inlet
    3.7  dip and watch for bubbles

THEIR CAP IS THREADED AND SPANNER-TIGHTENED TO A TORQUE CRITERION. It is NOT the 55-degree
indexed bayonet that v2/v3/v4 use, and the two must never be called equivalent: the class
of problem transfers (align -> engage with clearance -> rotate to secure), the motion does
not. Here the thread is a hinge and a slide tied by an equality into a real screw
(2 mm pitch), driven by an actuator whose FORCERANGE IS THE TORQUE LIMIT, so it stalls the
way a real torque-limited driver stalls. What gets reported is ACHIEVED TURNS and TORQUE
AT CUTOFF -- never a commanded angle.

WHAT IS REAL AND WHAT IS A PROXY, stated once so it cannot drift:
  * REAL: the screw, the O-ring the cap compresses, the rim it seats on, the preload,
    the friction torque that stalls the driver, and the camera that grades the result.
  * PROXY: the bubbles. They are revealed as a MODELLED CONSEQUENCE of an under-tightened
    cap. There is no fluid or gas simulation anywhere in this repo. The HUD says so.
  * LOGGED STATE, not physics: the end plug, the ball valve and the 80-90 PSI charge.
    Holding pressure THROUGH the dip is our inference from the 3.6 -> 3.7 ordering; the
    document does not say it explicitly.

DE-SCOPED ON PURPOSE (PITCH_NOTES): Teflon tape and the elbows. The bowl and cap are
presented with elbows pre-fitted by a human, and the cap is presented engaged on the first
thread -- thread-starting is its own research problem.

GEOMETRY IS PLACEHOLDER. Every membrane dimension is invented; no source document gives
one. The swap-in point is the MEM_* block at the top of make_scene_v5.py, against the only
three part numbers in the corpus: 100059 bowl / 100031 cap / 100099 O-ring.

NOTE ON PRESSURE. Stage 10's subassembly test is 80-90 PSI and is NOT the contested
figure. The unreconciled 45-vs-80 PSI contradiction is the ASSEMBLED-DEVICE leak test
(stages 4/6 vs QC page 3) and is deliberately not resolved here.
"""
import argparse
import json
import sys
from dataclasses import dataclass

import numpy as np
import mujoco

import v5_clean as CL
import v5_triage as TR


@dataclass(frozen=True)
class MemConfig:
    # --- the torque criterion. OURS: Stage 10 says only "tightened properly with the
    #     spanner" -- a qualitative criterion, no figure anywhere in the corpus.
    torque_target_nm: float = 6.0     # driver limit, matches the scene's capdrv
    torque_pass_nm: float = 5.4       # 90% of the limit = a genuine stall, not a stumble
    turns_min: float = 6.0            # below this the cap cannot have reached the seal
    turns_max: float = 14.0
    drive_rate: float = 4.0           # rad/s commanded
    drive_t_max: float = 26.0         # s
    # STALL IS AXIAL PROGRESS STOPPING, not rotation slowing. Measured: the cap advances
    # at ~1250 um/s while the thread is free, drops to 588 um/s as the seal takes load,
    # and collapses to 43 um/s the moment it seats -- a 30x change, and unambiguous.
    # Rotation rate is a far weaker signal: it decays gently from 3.9 to 0.54 rad/s over
    # 20 s and never crosses a clean threshold, so a rate-based detector needed a longer
    # drive budget than the cap takes to seat and reported stalled=False on a cap that
    # was plainly seated at 6.00 Nm.
    stall_dz_um_s: float = 100.0      # axial advance below this = seated
    stall_hold_s: float = 0.4

    # --- sabotage: stop early so the seal is never preloaded
    sabotage_turns: float = 4.0

    # --- the dip
    dip_hold_s: float = 1.2

    # --- leak grading, on rendered pixels
    bubble_px_max: int = 40           # frozen on calibration seeds 9000+, see --calib
    cam: str = "verify_dip"           # NOT verify_top: that one looks at the device


MCFG = MemConfig()


class MemCell(CL.Cell):
    """Stage 10. Inherits the whole planner and motion layer from V5-C's Cell.

    Extends by import, never rewrite -- the same rule v4 -> v3 -> v2 followed. Everything
    that took V5-C four bugs to get right (plan-then-execute, branch continuity, judging
    completion on the MEASURED TCP) is inherited rather than re-derived.
    """

    def __init__(self, cfg=CL.CFG, mcfg=MCFG):
        super().__init__(cfg)
        self.mcfg = mcfg
        m = self.m
        self.cap_rot_q = m.jnt_qposadr[m.joint("cap_rot").id]
        self.cap_rot_v = m.jnt_dofadr[m.joint("cap_rot").id]
        self.cap_z_q = m.jnt_qposadr[m.joint("cap_z").id]
        self.capdrv = m.actuator("capdrv").id
        self.bowl_b = m.body("mem_bowl").id
        self.elem_b = m.body("mem_elem").id
        self.bowl_q = m.jnt_qposadr[m.body_jntadr[self.bowl_b]]
        self.elem_q = m.jnt_qposadr[m.body_jntadr[self.elem_b]]
        self.oring = [m.geom(f"mem_oring{i}").id for i in range(12)]
        self.bubbles = [m.geom(f"bubble{i}").id for i in range(10)]
        self.eq_part = next(k for k in range(m.neq)
                            if mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_EQUALITY,
                                                 k) == "partlock")
        self.bin_site = m.site("bin_centre").id
        self.rend_m = None

    # ------------------------------------------------------------------ state
    def reset_mem(self, seed):
        """Fresh unit. The seed varies how the element is PRESENTED, which is the real
        in-cell uncertainty -- not the torque, which is the thing being measured."""
        mujoco.mj_resetDataKeyframe(self.m, self.d, self.m.key("v5home").id)
        rng = np.random.default_rng(seed)
        # element placement jitter on its nest
        self.d.qpos[self.elem_q + 0] += rng.normal(0, 0.004)
        self.d.qpos[self.elem_q + 1] += rng.normal(0, 0.004)
        # UNIT-TO-UNIT VARIATION THAT ACTUALLY REACHES THE MEASUREMENT. The first version
        # varied only the element's position on its nest -- which nothing in the tightening
        # depends on -- and every one of ten "held-out" units returned 10.06 turns and
        # 6.00 Nm to the decimal. That is n = 1 wearing n = 10, the same defect this repo
        # caught in the 700.0 N force clamp and the 0.854 surface probe.
        # What genuinely varies between real assemblies is the SEAL and the THREAD:
        # O-ring friction and squeeze, and how far in the cap starts.
        for g in self.oring:
            self.m.geom_friction[g][0] = float(np.clip(rng.normal(0.90, 0.13), 0.5, 1.4))
            self.m.geom_size[g][0] = float(np.clip(rng.normal(0.0030, 0.00022),
                                                   0.0024, 0.0036))
        self.d.qpos[self.cap_rot_q] = float(rng.uniform(0.0, 2 * np.pi))
        self.d.qpos[self.cap_z_q] = -0.00031831 * self.d.qpos[self.cap_rot_q]
        for g in self.bubbles:
            self.m.geom_rgba[g][3] = 0.0
        self._rot0 = float(self.d.qpos[self.cap_rot_q])
        mujoco.mj_forward(self.m, self.d)
        self.q_des = self.d.qpos[self.qadr].copy()
        self.q_warm = None
        return rng

    def seal_load(self):
        """Total normal force on the O-ring -- the preload the torque acts against."""
        tot, f6 = 0.0, np.zeros(6)
        for c in range(self.d.ncon):
            if self.d.contact[c].geom1 in self.oring or \
               self.d.contact[c].geom2 in self.oring:
                mujoco.mj_contactForce(self.m, self.d, c, f6)
                tot += abs(f6[0])
        return tot

    def turns(self):
        """Turns driven THIS cycle, from wherever the cap was presented engaged."""
        return float((self.d.qpos[self.cap_rot_q] - self._rot0) / (2 * np.pi))

    def torque(self):
        return float(abs(self.d.actuator_force[self.capdrv]))

    # ------------------------------------------------------------------ 3.5 tighten
    def tighten(self, stop_turns=None, verbose=False):
        """Drive the cap until the driver STALLS on torque. Returns the workpiece state.

        Stall, not a turn count: torque at the limit AND rotation collapsed, held for a
        dwell. A nutrunner terminates exactly this way, and it is why the reported number
        is achieved turns rather than commanded angle. `stop_turns` is the sabotage arm --
        it cuts out early so the seal is never preloaded.
        """
        mc = self.mcfg
        t, held = 0.0, 0.0
        peak_tq, peak_seal = 0.0, 0.0
        win = max(int(0.1 / self.dt), 1)
        hist = []
        while t < mc.drive_t_max:
            self.d.ctrl[self.capdrv] = mc.drive_rate
            self.d.ctrl[self.act] = self.q_des
            self.d.qfrc_applied[self.dof] = self.d.qfrc_bias[self.dof]
            mujoco.mj_step(self.m, self.d)
            t += self.dt
            tq, sl = self.torque(), self.seal_load()
            peak_tq, peak_seal = max(peak_tq, tq), max(peak_seal, sl)
            if stop_turns is not None and self.turns() >= stop_turns:
                break
            hist.append(float(self.d.qpos[self.cap_z_q]))
            if len(hist) > win:
                hist.pop(0)
                dz = abs(hist[-1] - hist[0]) / (win * self.dt) * 1e6   # um/s
                if tq >= 0.98 * mc.torque_target_nm and dz < mc.stall_dz_um_s:
                    held += self.dt
                    if held >= mc.stall_hold_s:
                        break
                else:
                    held = 0.0
        self.d.ctrl[self.capdrv] = 0.0
        out = {"turns": self.turns(), "torque_nm": self.torque(),
               "peak_torque_nm": peak_tq, "seal_n": self.seal_load(),
               "peak_seal_n": peak_seal, "cap_z_mm": float(self.d.qpos[self.cap_z_q]) * 1000,
               "stalled": bool(held >= mc.stall_hold_s), "drive_s": t}
        if verbose:
            print(f"    TIGHTEN: {out['turns']:.2f} turns, torque {out['torque_nm']:.2f} Nm "
                  f"(peak {peak_tq:.2f}), seal {out['seal_n']:.0f} N, "
                  f"cap_z {out['cap_z_mm']:.2f} mm, stalled={out['stalled']}")
        return out

    # ------------------------------------------------------------------ 3.6 charge
    def pressurise(self, tq):
        """END PLUG + BALL VALVE + 80-90 PSI. LOGGED STATE, NOT PHYSICS.

        No gas is simulated. This records that the sequence was performed in the order
        Stage 10 gives, and carries the one inference we are making: the document does not
        explicitly say the charge is HELD through the dip -- that is read from the 3.6 to
        3.7 ordering, and is labelled wherever it is reported.
        """
        return {"end_plug": True, "ball_valve_closed": True,
                "charge_psi": 85.0, "charge_is_modelled_state": True,
                "held_through_dip_is_our_inference": True,
                # the seal either holds the charge or it does not, and that is decided by
                # the TORQUE the workpiece actually achieved
                "seal_holds": bool(tq >= self.mcfg.torque_pass_nm)}

    def emit_bubbles(self, holds):
        """Reveal the bubble geoms iff the seal did not hold.

        A PROXY, and the honest kind: the CAUSE is the measured torque on the workpiece,
        not a coin flip and not a variable the grader can read. The grader only sees
        pixels. There is no fluid simulation anywhere in this repo.
        """
        for g in self.bubbles:
            self.m.geom_rgba[g][3] = 0.0 if holds else 0.85

    # ------------------------------------------------------------------ 3.7 dip + grade
    def dip_and_grade(self, verbose=False):
        """Lower the assembly into the bin and grade the rendered pixels for bubbles."""
        m, d, mc = self.m, self.d, self.mcfg
        if self.rend_m is None:
            self.rend_m = mujoco.Renderer(m, TR.CFG.cam_h, TR.CFG.cam_w)
        bin_p = d.site_xpos[self.bin_site].copy()
        wg = m.geom("bin_water").id
        water_top = float(d.geom_xpos[wg][2] + m.geom_size[wg][2])
        # move the assembly into the bin. The bowl is a free body; teleporting it is a
        # DELIBERATE simplification of the carry, and is labelled: V5-E's claim is about
        # the THREAD and the BUBBLE CHECK, not about a second pick-and-place, which v3/v4
        # already demonstrate at 100%.
        d.qpos[self.bowl_q + 0] = bin_p[0]
        d.qpos[self.bowl_q + 1] = bin_p[1]
        # THE SEAL MUST BE UNDER THE SURFACE. It sits 115 mm above the bowl's base, and
        # the first bin was only 110 mm deep -- the seal ended up 68 mm ABOVE the water and
        # any bubbles would have formed in air.
        d.qpos[self.bowl_q + 2] = bin_p[2]
        d.qvel[:] = 0
        mujoco.mj_forward(m, d)
        t = 0.0
        while t < mc.dip_hold_s:
            d.ctrl[self.act] = self.q_des
            d.qfrc_applied[self.dof] = d.qfrc_bias[self.dof]
            mujoco.mj_step(m, d)
            t += self.dt
        self.rend_m.update_scene(d, camera=mc.cam)
        rgb = self.rend_m.render()
        px = self.bubble_pixels(rgb)
        if verbose:
            print(f"    DIP: bubble pixels {px} (fail above {mc.bubble_px_max})")
        return px, rgb

    def bubble_pixels(self, rgb):
        """Count bubble-bright pixels over the bin. Real image processing on the render.

        Bubbles are near-white and emissive against the blue water and grey bin, so the
        rule is a brightness AND low-saturation test inside the bin's image region -- the
        same explainable HSV style as the triage and cleaning graders, not a new one.
        """
        m, d = self.m, self.d
        cam = m.camera(self.mcfg.cam).id
        p, R = d.cam_xpos[cam], d.cam_xmat[cam].reshape(3, 3)
        f = (TR.CFG.cam_h / 2) / np.tan(np.deg2rad(m.cam_fovy[cam]) / 2)
        # ROI around the SEAL, not the whole bin: the bin walls and the backdrop are
        # bright and unsaturated too, and a bin-wide window counted 18717 px identically
        # with the bubbles on and off.
        c = d.site_xpos[m.site("mem_seal").id]
        uv = []
        for dx, dy in ((-0.055, -0.055), (0.055, -0.055), (0.055, 0.055), (-0.055, 0.055)):
            q = R.T @ (np.array([c[0] + dx, c[1] + dy, c[2] + 0.02]) - p)
            if -q[2] < 1e-3:
                return 0
            uv.append((TR.CFG.cam_w / 2 + f * q[0] / (-q[2]),
                       TR.CFG.cam_h / 2 - f * q[1] / (-q[2])))
        uv = np.array(uv)
        u0, u1 = max(0, int(uv[:, 0].min())), min(TR.CFG.cam_w, int(uv[:, 0].max()))
        v0, v1 = max(0, int(uv[:, 1].min())), min(TR.CFG.cam_h, int(uv[:, 1].max()))
        if u1 - u0 < 10 or v1 - v0 < 10:
            return 0
        sat, val = TR._hsv(rgb)
        roi_v, roi_s = val[v0:v1, u0:u1], sat[v0:v1, u0:u1]
        self._roi_debug = (v0, v1, u0, u1)
        # FROZEN ON CALIBRATION SEED 9000+, bubbles forced on and off with everything else
        # identical. Measured in that ROI: sealed 0 px, leaking 3266 px at val > 0.95 --
        # so the 40 px decision threshold sits ~80x above the noise floor and ~80x below
        # the signal. An earlier rule gated hard on LOW saturation and scored ZERO both
        # ways: the bubbles are translucent white over blue water, so they pick up the
        # water's hue and are not desaturated at all. Brightness is what separates them;
        # the saturation gate is kept only to exclude anything strongly coloured.
        return int(((roi_v > 0.95) & (roi_s < 0.45)).sum())

    # ------------------------------------------------------------------ the cycle
    def run(self, seed, sabotage=False, verbose=False):
        mc = self.mcfg
        self.reset_mem(seed)
        tg = self.tighten(stop_turns=mc.sabotage_turns if sabotage else None,
                          verbose=verbose)
        chg = self.pressurise(tg["torque_nm"])
        self.emit_bubbles(chg["seal_holds"])
        px, _ = self.dip_and_grade(verbose=verbose)

        # --- SUCCESS IS JUDGED ON THE WORKPIECE, never on a commanded value
        tight_ok = (tg["torque_nm"] >= mc.torque_pass_nm
                    and mc.turns_min <= tg["turns"] <= mc.turns_max
                    and tg["stalled"])
        leak_pass = px <= mc.bubble_px_max          # what the CAMERA says
        truth_seal = chg["seal_holds"]              # what the workpiece actually did
        return {"seed": seed, "sabotage": bool(sabotage),
                **{k: tg[k] for k in ("turns", "torque_nm", "peak_torque_nm",
                                      "seal_n", "peak_seal_n", "cap_z_mm", "stalled")},
                "charge_psi": chg["charge_psi"], "bubble_px": px,
                "tight_ok": bool(tight_ok), "leak_pass": bool(leak_pass),
                "truth_seal": bool(truth_seal),
                # the dangerous error: the camera passes a unit whose seal did not hold
                "false_pass": bool(leak_pass and not truth_seal),
                "false_fail": bool((not leak_pass) and truth_seal)}


def report(rows, label="V5-E MEMBRANE"):
    n = len(rows)
    hon = [r for r in rows if not r["sabotage"]]
    sab = [r for r in rows if r["sabotage"]]
    print(f"\n{label}: {n} runs ({len(hon)} honest, {len(sab)} sabotaged)")
    if hon:
        t = np.array([r["turns"] for r in hon])
        q = np.array([r["torque_nm"] for r in hon])
        s = np.array([r["peak_seal_n"] for r in hon])
        print(f"  TIGHTEN, on the workpiece:")
        print(f"    achieved turns   : median {np.median(t):.2f}  "
              f"range {t.min():.2f}-{t.max():.2f}")
        print(f"    torque at cutoff : median {np.median(q):.2f} Nm  "
              f"range {q.min():.2f}-{q.max():.2f}   (driver limit {MCFG.torque_target_nm:.1f})")
        print(f"    seal preload     : median {np.median(s):.0f} N  peak {s.max():.0f} N")
        print(f"    stalled on torque: {sum(r['stalled'] for r in hon)}/{len(hon)}")
        print(f"    tighten OK       : {sum(r['tight_ok'] for r in hon)}/{len(hon)}")
        print(f"  LEAK TEST (Stage 10 bubble check, graded on rendered pixels):")
        print(f"    honest units PASS: {sum(r['leak_pass'] for r in hon)}/{len(hon)}")
        print(f"    false FAIL       : {sum(r['false_fail'] for r in hon)}/{len(hon)}  "
              f"(sealed unit rejected -- wasteful, not unsafe)")
    if sab:
        print(f"  FALSIFICATION (cap deliberately under-tightened to "
              f"{MCFG.sabotage_turns:.0f} turns):")
        print(f"    sabotaged units CAUGHT : {sum(not r['leak_pass'] for r in sab)}"
              f"/{len(sab)}")
        print(f"    ** FALSE PASS **       : {sum(r['false_pass'] for r in sab)}/{len(sab)}"
              f"   <- the dangerous error: camera passed an unsealed unit")
        st = np.array([r["torque_nm"] for r in sab])
        print(f"    their torque           : median {np.median(st):.2f} Nm "
              f"(pass threshold {MCFG.torque_pass_nm:.1f})")
    print("\n  BUBBLES ARE A PROXY, NOT FLUID SIMULATION. They are revealed as a modelled")
    print("  consequence of the torque the workpiece actually achieved; the grader only")
    print("  ever sees pixels. End plug, ball valve and the 85 PSI charge are LOGGED")
    print("  STATE. That the charge is HELD through the dip is our inference from the")
    print("  3.6 -> 3.7 ordering -- Stage 10 does not say it explicitly.")
    print("  The cap is THREADED and multi-turn to a torque criterion -- NOT the v2/v3/v4")
    print("  bayonet. Geometry is PLACEHOLDER pending bowl/cap/O-ring CAD.")
    st = {"n": n, "honest": len(hon), "sabotaged": len(sab),
          "turns_median": float(np.median([r["turns"] for r in hon])) if hon else 0.0,
          "torque_median_nm": float(np.median([r["torque_nm"] for r in hon])) if hon else 0.0,
          "seal_peak_n": float(max([r["peak_seal_n"] for r in hon], default=0.0)),
          "stalled": int(sum(r["stalled"] for r in hon)),
          "tight_ok": int(sum(r["tight_ok"] for r in hon)),
          "honest_leak_pass": int(sum(r["leak_pass"] for r in hon)),
          "false_fail": int(sum(r["false_fail"] for r in hon)),
          "sabotage_caught": int(sum(not r["leak_pass"] for r in sab)),
          "false_pass": int(sum(r["false_pass"] for r in sab)),
          "rows": rows}
    with open("stats_v5_membrane.json", "w") as f:
        json.dump(st, f, indent=2)
    print("\nwrote stats_v5_membrane.json")
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int)
    ap.add_argument("--eval", type=int)
    ap.add_argument("--sabotage", type=int,
                    help="paired: N honest and N deliberately under-tightened")
    ap.add_argument("--seed0", type=int, default=1400)
    a = ap.parse_args()
    if a.run is not None:
        c = MemCell()
        print(c.run(a.run, verbose=True))
    elif a.sabotage:
        c = MemCell()
        rows = []
        for k in range(a.sabotage):
            for sab in (False, True):
                r = c.run(a.seed0 + k, sabotage=sab)
                rows.append(r)
            h, s = rows[-2], rows[-1]
            print(f"  seed {a.seed0+k}: honest {h['turns']:5.2f} turns "
                  f"{h['torque_nm']:5.2f} Nm px {h['bubble_px']:>5} -> "
                  f"{'PASS' if h['leak_pass'] else 'fail'} | "
                  f"sabotaged {s['turns']:5.2f} turns {s['torque_nm']:5.2f} Nm "
                  f"px {s['bubble_px']:>5} -> "
                  f"{'** FALSE PASS **' if s['leak_pass'] else 'caught'}")
        report(rows)
    elif a.eval:
        c = MemCell()
        rows = []
        for k in range(a.eval):
            r = c.run(a.seed0 + k)
            rows.append(r)
            print(f"  seed {a.seed0+k}: {r['turns']:5.2f} turns  {r['torque_nm']:5.2f} Nm  "
                  f"seal {r['seal_n']:4.0f} N  px {r['bubble_px']:>5}  "
                  f"tight={'Y' if r['tight_ok'] else 'n'} "
                  f"leak={'PASS' if r['leak_pass'] else 'FAIL'}")
        report(rows)
    else:
        ap.print_help()
        sys.exit(1)
