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

DE-SCOPED ON PURPOSE (PITCH_NOTES): Teflon tape and the elbows (pre-fitted by a human).
V6-ARM UPDATE: the cap is now PICKED AND PLACED BY THE ARM onto the bowl mouth; arriving
inside a 4 mm / 4 deg THREAD-START CAPTURE ENVELOPE exchanges it for the threaded cap on
its first thread (capture modelled, arm pose real -- the tool-changer pattern). The arm
then HOLDS THE DRIVER: the spindle only advances while the wrist holds station over the
cap, enforced every step. Thread-STARTING physics and spindle reaction torque remain
declared de-scopes.

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
    drive_rate: float = 12.0          # rad/s commanded. V6: was 4.0. Swept 4/8/12/16
                                      # with the sabotage gate: 5/5 honest, 0/5 false
                                      # pass, loaded-turns median unchanged (9.33) at
                                      # every rate. 12 keeps 2.6x margin to a real
                                      # nutrunner's ~31 rad/s. Torque criterion untouched.
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
    # MINIMUM settle before the velocity check is believed, seconds. Was a hard-coded 0.4
    # inside _hold; there are 16 _hold calls per unit so it was a 6.4 s floor. 0.20 is
    # still a VELOCITY criterion -- if the part is genuinely still moving the hold
    # continues -- it just stops assuming nothing can have settled in under 0.4 s.
    # Measured over 6 seeds: 46.3 -> 43.8 s with insert 6/6, cap 6/6, stall 6/6.
    hold_floor_s: float = 0.20

    # --- MEMBRANE INSERT (2026-08-05). A REAL MOTION, where there was none.
    #     The bowl is OPEN while the element goes in -- see present_cap().
    grip_below_top: float = 0.012     # pads this far below the element top. Grip HIGH: the
                                      # fingers are wider than the bore and cannot follow
                                      # the element in, so this sets the release depth.
    # 0.20 (V7.2, 2026-08-11). V6 chose 0.10 and that sweep is STALE -- it predates the
    # 2026-08-10 arm-speed clamp, which changed the tracking this depends on, exactly as
    # it did for the cleaning feed rate. Re-swept on 6 seeds (1890-95) with the accuracy
    # gates: insert 6/6, cap placed 6/6, stall 6/6 at every value, and the MARGINS get
    # BETTER not worse -- worst placement error 1.74 -> 1.90 mm inside a 4 mm capture, and
    # worst pre-insert alignment 1.74 -> 0.97 mm. Membrane station 46.3 -> 39.1 s with the
    # hold floor below. Original V6 note, still true, kept below.
    carry_speed: float = 0.20         # m/s setpoint limit. At 0.10 the
                                      # worst settled seat is 1.48 mm vs 1.47 at 0.05
                                      # (bound 1.8), insert 26.1 -> 22.2 s. 0.15 passed
                                      # too (worst 1.57) and was NOT taken -- the margin
                                      # thins for 2 s. The pads are flat and close
                                      # along Y, so in X the element rides on FRICTION
                                      # ALONE; an unlimited carry slid it 19 mm in the jaws.
    align_speed: float = 0.020        # V6: was 0.010; swept with carry_speed above
    align_tol_m: float = 0.0010       # against 1.5 mm radial clearance
    align_tries: int = 5
    rim_clear_m: float = 0.004
    transit_z: float = 0.36           # go OVER the station, never through it: the direct
                                      # path from home swept the arm into the bowl and
                                      # shoved it 53.7 mm off its post.
    # SEATING CRITERION, DERIVED FROM GEOMETRY rather than picked. Bore inner radius is
    # 22.5 mm and the element is 21.0 mm, so a part resting anywhere in the bore is up to
    # RADIAL_CLEARANCE = 1.5 mm off-axis -- that is the part sitting where gravity and
    # clearance put it, not an error. The bound is therefore clearance + a small settling
    # allowance, and NOT the 6.0 mm it used to be.
    #
    # Why that mattered: at 6.0 mm the worst observed settled offset (1.537 mm) passed by
    # a 4x margin while being quoted next to a "1.5 mm clearance" headline -- scoring the
    # release against the clearance and the outcome against four times it. An audit called
    # that flattering and was right.
    seat_tol_m: float = 0.0018        # = 1.5 mm clearance + 0.3 mm settling allowance
    seat_z_max: float = 0.004         # base within 4 mm of the bowl floor (was 12 mm)
    seat_tilt_min: float = 0.999      # cos: <= 2.6 deg. The bore is 1.5 mm on the radius
                                      # over a 72 mm part -- it PHYSICALLY cannot tilt more
                                      # than ~2.4 deg while seated, so the old 0.95
                                      # (18.2 deg) could not have failed anything.

    # --- sabotage: stop early so the seal is never preloaded
    sabotage_turns: float = 4.0

    # --- the dip
    dip_hold_s: float = 1.2

    # --- leak grading, on rendered pixels
    bubble_px_max: int = 40           # frozen on calibration seeds 9000+, see --calib
    cam: str = "verify_dip"           # NOT verify_top: that one looks at the device


MCFG = MemConfig()

# the thread, as the scene defines it: cap_z = -(pitch/2pi) * cap_rot, pitch 2 mm/turn.
PITCH_PER_RAD = 0.00031831

# Gripper geometry, MEASURED from the model rather than inherited. The two finger-pad rows
# sit +20.9 mm and +38.9 mm ABOVE link_tcp. PAD_MID is their midpoint (line this up with
# the intended grip height); PAD_LO is the lower row (this is what must clear the rim).
PAD_MID, PAD_LO = 0.0299, 0.0209
ELEM_HALF_H = 0.036


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
        self.blank_b = m.body("cap_blank").id
        self.blank_q = m.jnt_qposadr[m.body_jntadr[self.blank_b]]
        self.blank_geoms = [g for g in range(m.ngeom)
                            if m.geom_bodyid[g] == self.blank_b]
        self._blank_spawn = None     # captured on first reset
        # the cap's own geoms, so it can be absent while the element goes in
        self.cap_geoms = [g for g in range(m.ngeom)
                          if m.geom_bodyid[g] == m.body("mem_cap").id]
        self._cap_alpha = {g: float(m.geom_rgba[g][3]) for g in self.cap_geoms}
        self._cap_on = True
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
        self.d.qpos[self.cap_z_q] = -PITCH_PER_RAD * self.d.qpos[self.cap_rot_q]
        # THE BOWL ARRIVES OPEN. The cap cannot be fitted while the element still has to
        # go in -- it overhangs the bore -- so it is absent here and presented afterwards
        # by cap_present(True). See the note above insert_element for why no cap position
        # works, and note that presenting it is a FIXTURE action, not a robot motion.
        self.cap_present(False)
        # the ARM will place the cap: restore the blank to its nest (a previous cycle
        # parked it after the thread-start capture)
        # THE KEYFRAME TRAP, third appearance: v5home predates this free joint, so
        # mj_resetDataKeyframe zeroes it and the blank spawns at the ORIGIN, inside the
        # arm riser. qpos0 carries the XML pose; set it explicitly, as the gotcha list
        # has said since v2.
        if self._blank_spawn is None:
            self._blank_spawn = self.m.qpos0[self.blank_q:self.blank_q + 7].copy()
        self.d.qpos[self.blank_q:self.blank_q + 7] = self._blank_spawn
        for g in self.blank_geoms:
            self.m.geom_contype[g] = 1
            self.m.geom_conaffinity[g] = 1
            self.m.geom_rgba[g][3] = 1.0
        for g in self.bubbles:
            self.m.geom_rgba[g][3] = 0.0
        self._rot0 = float(self.d.qpos[self.cap_rot_q])
        mujoco.mj_forward(self.m, self.d)
        self.q_des = self.d.qpos[self.qadr].copy()
        self.q_warm = None
        return rng

    # ------------------------------------------------- 3.4 element into the bowl
    #
    # THE BOWL IS OPEN WHILE THIS HAPPENS, and that is not a convenience -- it is the only
    # physically possible order, and it matches a de-scope this module already declared.
    #
    # The cap overhangs the whole bore (r=34 mm) 20 mm above a 155 mm rim, so a 72 x 42 mm
    # element has no path in while it is fitted. Retracting the cap up its own thread does
    # not help: the gripper assembly spans tcp+0.005..tcp+0.185 at radii to 99 mm and must
    # occupy exactly the space above the bore to lower the element, so every legal cap
    # position sits inside the gripper envelope. Measured, not argued.
    #
    # So the cap is ABSENT during insertion and is then PRESENTED ENGAGED ON THE FIRST
    # THREAD -- which is verbatim the de-scope in this module's own docstring
    # ("the cap is presented engaged on the first thread -- thread-starting is its own
    # research problem"). Presenting it is a fixture action, NOT a robot motion, and it is
    # reported as such. What the robot really does here is pick, align and place the
    # element, and that is measured on the element.
    def cap_present(self, present):
        """Fit or remove the cap as a fixture action. Not a robot motion; labelled so."""
        for g in self.cap_geoms:
            self.m.geom_contype[g] = 1 if present else 0
            self.m.geom_conaffinity[g] = 1 if present else 0
            self.m.geom_rgba[g][3] = self._cap_alpha[g] if present else 0.0
        self._cap_on = bool(present)

    def elem_pose(self):
        """Element position and uprightness. Judged on the PART, never the wrist."""
        p = self.d.xpos[self.elem_b].copy()
        R = self.d.xmat[self.elem_b].reshape(3, 3)
        return p, float(R[:, 2] @ np.array([0.0, 0.0, 1.0]))

    def elem_speed(self):
        a = self.m.jnt_dofadr[self.m.body_jntadr[self.elem_b]]
        return float(np.linalg.norm(self.d.qvel[a:a + 6]))

    def bowl_axis_xy(self):
        return self.d.xpos[self.bowl_b][:2].copy()

    def bowl_floor_z(self):
        g = self.m.geom("mem_bowl_base").id
        return float(self.d.geom_xpos[g][2] + self.m.geom_size[g][1])

    def bowl_rim_z(self):
        zs = [self.d.geom_xpos[self.m.geom(f"mem_wall{i}").id][2]
              + self.m.geom_size[self.m.geom(f"mem_wall{i}").id][2] for i in range(8)]
        return float(max(zs))

    def _glide(self, tgt, grip, speed, frames=None, tag=""):
        """Velocity-limited setpoint -- bounds the acceleration a friction grip must survive."""
        p = self.d.site_xpos[self.site].copy()
        n = max(1, int(float(np.linalg.norm(tgt - p)) / (speed * self.dt)))
        for i in range(1, n + 1):
            self.step_to(p + (tgt - p) * i / n, CL.grasp_mat(), grip, 0.0, frames, tag)
            # KEEP FILMING -- this is the membrane station's MAIN travel primitive (every
            # carry, lift, descend and align goes through it) and it emitted nothing, so
            # most of the membrane phase was simulated time with no frames. See
            # v5_clean.dwell for why that shows up as judder in the CLEAN phase too:
            # make_realtime stretches uniformly, so a gap anywhere is duplicated frames
            # everywhere.
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    i % frames["every"] == 0:
                frames["cb"](tag)

    def _hold(self, tgt, grip, s=2.5, frames=None, tag=""):
        """Hold until the carried element stops swinging."""
        t = 0.0
        while t < s:
            self.step_to(tgt, CL.grasp_mat(), grip, 0.0, frames, tag)
            t += self.dt
            # KEEP FILMING. Same defect as v5_clean.dwell: step_to takes `frames` and
            # never uses it, so every settle hold was simulated time with no frames --
            # and make_realtime's uniform stretch turns those gaps into duplicated
            # frames spread over the whole clip, i.e. judder during the MOVING parts.
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    int(t / self.dt) % frames["every"] == 0:
                frames["cb"](tag)
            if t > self.mcfg.hold_floor_s and self.elem_speed() < 0.01:
                break

    def insert_element(self, verbose=False, frames=None):
        """Pick the membrane element off its nest and place it in the open bowl."""
        mc, gm = self.mcfg, CL.grasp_mat()
        p0, _ = self.elem_pose()
        tcp_grasp = p0[2] + ELEM_HALF_H - mc.grip_below_top - PAD_MID
        tcp_rel = self.bowl_rim_z() + mc.rim_clear_m - PAD_LO
        carry_z = max(tcp_grasp + 0.12, tcp_rel + 0.052)
        out = {"picked": False, "inserted": False, "align_mm": None, "align_iters": 0,
               "seat_xy_mm": None, "seat_dz_mm": None, "upright": None}

        # TRANSIT OVER THE STATION, never through it.
        here = self.d.site_xpos[self.site].copy()
        self.move(np.array([here[0], here[1], mc.transit_z]), gm, self.cfg.grip_open,
                  tol=0.006, t_max=6.0, frames=frames, tag="ELEM_UP")
        self.move(np.array([p0[0], p0[1], mc.transit_z]), gm, self.cfg.grip_open,
                  tol=0.005, t_max=8.0, frames=frames, tag="ELEM_OVER")
        self.move(np.array([p0[0], p0[1], tcp_grasp]), gm, self.cfg.grip_open,
                  tol=0.003, t_max=8.0, frames=frames, tag="ELEM_DESCEND")
        self._hold(np.array([p0[0], p0[1], tcp_grasp]), self.cfg.grip_closed, 1.2,
                   frames, "ELEM_GRIP")
        self._glide(np.array([p0[0], p0[1], carry_z]), self.cfg.grip_closed,
                    mc.carry_speed, frames, "ELEM_LIFT")
        self._hold(np.array([p0[0], p0[1], carry_z]), self.cfg.grip_closed, 2.0,
                   frames, "ELEM_LIFT")
        p, _ = self.elem_pose()
        out["picked"] = bool(p[2] - p0[2] > 0.05)
        if not out["picked"]:
            if verbose:
                print("    INSERT: grip slipped off the nest")
            return out

        bxy = self.bowl_axis_xy()
        self._glide(np.array([bxy[0], bxy[1], carry_z]), self.cfg.grip_closed,
                    mc.carry_speed, frames, "ELEM_CARRY")
        self._hold(np.array([bxy[0], bxy[1], carry_z]), self.cfg.grip_closed, 3.0,
                   frames, "ELEM_CARRY")

        # ALIGN ON THE PART: 1.5 mm radial clearance, and whatever the element slid to in
        # the jaws is the error that matters. The wrist cannot report it.
        for k in range(mc.align_tries):
            p, _ = self.elem_pose()
            err = self.bowl_axis_xy() - p[:2]
            out["align_iters"] = k
            if float(np.linalg.norm(err)) < mc.align_tol_m:
                break
            tcp = self.d.site_xpos[self.site].copy()
            goal = np.array([tcp[0] + err[0], tcp[1] + err[1], carry_z])
            self._glide(goal, self.cfg.grip_closed, mc.align_speed, frames, "ELEM_ALIGN")
            self._hold(goal, self.cfg.grip_closed, 2.5, frames, "ELEM_ALIGN")
        p, _ = self.elem_pose()
        out["align_mm"] = float(np.linalg.norm(self.bowl_axis_xy() - p[:2]) * 1000)

        tcp = self.d.site_xpos[self.site].copy()
        self._glide(np.array([tcp[0], tcp[1], tcp_rel]), self.cfg.grip_closed, 0.015,
                    frames, "ELEM_INSERT")
        self._hold(np.array([tcp[0], tcp[1], tcp_rel]), self.cfg.grip_closed, 2.0,
                   frames, "ELEM_INSERT")
        self._hold(np.array([tcp[0], tcp[1], tcp_rel]), self.cfg.grip_open, 2.5,
                   frames, "ELEM_RELEASE")
        self._glide(np.array([tcp[0], tcp[1], mc.transit_z]), self.cfg.grip_open, 0.10,
                    frames, "ELEM_RETRACT")
        self._hold(np.array([tcp[0], tcp[1], mc.transit_z]), self.cfg.grip_open, 3.0,
                   frames, "ELEM_SETTLE")

        p, up = self.elem_pose()
        dz = (p[2] - ELEM_HALF_H) - self.bowl_floor_z()
        xy = float(np.linalg.norm(p[:2] - self.bowl_axis_xy()))
        out.update(seat_xy_mm=xy * 1000, seat_dz_mm=dz * 1000, upright=up)
        out["inserted"] = bool(xy < mc.seat_tol_m and abs(dz) < mc.seat_z_max
                               and up > mc.seat_tilt_min)
        if verbose:
            print(f"    INSERT: aligned to {out['align_mm']:.2f} mm in "
                  f"{out['align_iters']} corrections -> seated xy {xy*1000:.2f} mm, "
                  f"base {dz*1000:+.2f} mm off the floor, upright {up:.3f} -> "
                  f"{'IN' if out['inserted'] else 'NOT SEATED'}")
        return out

    def cap_place(self, verbose=False, frames=None):
        """3.5a -- the ARM places the cap on the bowl mouth. A REAL MOTION.

        The arm picks the cap blank off its nest by the spanner flat, carries it, aligns
        on the MEASURED blank (never the wrist), and lowers it onto the bowl mouth. If
        the blank arrives inside a THREAD-START CAPTURE ENVELOPE -- 4 mm / 4 deg, the
        same figures as the tool changer -- the blank is exchanged for the threaded cap
        engaged on its first thread. The capture is the modelled part and says so;
        thread-STARTING physics (cross-threading and all) stays a declared de-scope.
        The ARM ACHIEVING THE POSE is real and is what this measures.
        """
        mc, gm = self.mcfg, CL.grasp_mat()
        d = self.d
        bp = d.xpos[self.blank_b].copy()
        # grip the CYLINDER BODY with both pad rows (the flat is unreachable: the
        # cylinder blocks jaw travel at 68 mm before it, and a one-row edge pinch
        # slipped). Grip 5 mm ABOVE the centre: a cylinder in flat jaws is a PIVOT, and
        # the spanner flat puts the CoM 2.5 mm above the centreline -- gripping at the
        # centre made an INVERTED pendulum that rolled loose and sagged out of the jaws
        # during the hold. With the grip line above the CoM it hangs stable. Same
        # physics as the v2 grasp-height lesson, on a new part.
        # grip the PICK STEM (see the scene comment): both pad rows on the stem, CoM
        # far below the grip line -- a stable pendulum, the v2 grasp-height lesson.
        tcp_grasp = bp[2] + 0.035 - PAD_MID
        out = {"placed": False, "picked": False, "place_err_mm": None,
               "place_tilt_deg": None}
        here = d.site_xpos[self.site].copy()
        self.move(np.array([here[0], here[1], mc.transit_z]), gm, self.cfg.grip_open,
                  tol=0.006, t_max=6.0, frames=frames, tag="CAP_UP")
        self.move(np.array([bp[0], bp[1], mc.transit_z]), gm, self.cfg.grip_open,
                  tol=0.005, t_max=8.0, frames=frames, tag="CAP_OVER")
        self.move(np.array([bp[0], bp[1], tcp_grasp]), gm, self.cfg.grip_open,
                  tol=0.003, t_max=8.0, frames=frames, tag="CAP_DESCEND")
        self._hold(np.array([bp[0], bp[1], tcp_grasp]), self.cfg.grip_closed, 1.0,
                   frames, "CAP_GRIP")
        carry_z = self.bowl_rim_z() + 0.060
        self._glide(np.array([bp[0], bp[1], carry_z]), self.cfg.grip_closed,
                    mc.carry_speed, frames, "CAP_LIFT")
        b = d.xpos[self.blank_b]
        out["picked"] = bool(b[2] > bp[2] + 0.03)
        if not out["picked"]:
            if verbose:
                print("    CAP: grip slipped off the nest")
            return out
        bxy = self.bowl_axis_xy()
        self._glide(np.array([bxy[0], bxy[1], carry_z]), self.cfg.grip_closed,
                    mc.carry_speed, frames, "CAP_CARRY")
        self._hold(np.array([bxy[0], bxy[1], carry_z]), self.cfg.grip_closed, 2.0,
                   frames, "CAP_CARRY")
        for k in range(mc.align_tries):
            b = d.xpos[self.blank_b]
            err = self.bowl_axis_xy() - b[:2]
            if float(np.linalg.norm(err)) < 0.0012:
                break
            tcp = d.site_xpos[self.site].copy()
            goal = np.array([tcp[0] + err[0], tcp[1] + err[1], carry_z])
            self._glide(goal, self.cfg.grip_closed, mc.align_speed, frames, "CAP_ALIGN")
            self._hold(goal, self.cfg.grip_closed, 2.0, frames, "CAP_ALIGN")
        # lower until the blank's underside sits just above the rim (first-thread height)
        b = d.xpos[self.blank_b]
        drop = (b[2] - 0.010) - (self.bowl_rim_z() + 0.003)
        tcp = d.site_xpos[self.site].copy()
        self._glide(np.array([tcp[0], tcp[1], tcp[2] - drop]), self.cfg.grip_closed,
                    0.015, frames, "CAP_LOWER")
        self._hold(np.array([tcp[0], tcp[1], tcp[2] - drop]), self.cfg.grip_closed, 1.5,
                   frames, "CAP_LOWER")
        b = d.xpos[self.blank_b].copy()
        Rb = d.xmat[self.blank_b].reshape(3, 3)
        err_mm = float(np.linalg.norm(b[:2] - self.bowl_axis_xy()) * 1000)
        tilt = float(np.degrees(np.arccos(np.clip(Rb[2, 2], -1, 1))))
        out["place_err_mm"], out["place_tilt_deg"] = err_mm, tilt
        # RELEASE AND RETRACT BEFORE THE CAPTURE SWAP. Swapping while the jaws were
        # still closed at the spot materialised the threaded cap INSIDE the gripper --
        # at some random cap phases its spanner flat intersected a finger body and the
        # contact explosion launched the whole bowl metres off the bench (seed 1882).
        # Order now: set the blank down on the mouth, open, withdraw, THEN the capture
        # exchanges it -- which is also the physically sensible sequence.
        self._hold(np.array([b[0], b[1], d.site_xpos[self.site][2]]),
                   self.cfg.grip_open, 1.0, frames, "CAP_RELEASE")
        tcp = d.site_xpos[self.site].copy()
        self._glide(np.array([tcp[0], tcp[1], mc.transit_z]), self.cfg.grip_open,
                    0.10, frames, "CAP_RETRACT")
        if err_mm <= 4.0 and tilt <= 4.0:
            # THREAD-START CAPTURE (modelled, labelled): blank out, threaded cap in at
            # the first thread. The random phase reset_mem chose is kept.
            self.d.qpos[self.blank_q:self.blank_q + 3] = (0.05, 0.55, 0.011)
            for g in self.blank_geoms:
                self.m.geom_contype[g] = 0
                self.m.geom_conaffinity[g] = 0
                self.m.geom_rgba[g][3] = 0.0
            self.cap_present(True)
            mujoco.mj_forward(self.m, self.d)
            out["placed"] = True
        if verbose:
            print(f"    CAP PLACE: err {err_mm:.2f} mm tilt {tilt:.2f} deg -> "
                  f"{'CAPTURED on first thread' if out['placed'] else 'MISSED envelope'}")
        return out

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
    def tighten(self, stop_turns=None, verbose=False, frames=None):
        """Drive the cap until the driver STALLS on torque. Returns the workpiece state.

        Stall, not a turn count: torque at the limit AND rotation collapsed, held for a
        dwell. A nutrunner terminates exactly this way, and it is why the reported number
        is achieved turns rather than commanded angle. `stop_turns` is the sabotage arm --
        it cuts out early so the seal is never preloaded.
        """
        mc = self.mcfg
        # V6-ARM: the ARM holds the driver. Dock the TCP over the cap first; the spindle
        # only advances while the wrist HOLDS STATION inside a 8 mm envelope -- enforced
        # every step, so "the arm does it" is a gate, not a caption. The spindle motor
        # and its reaction torque are the tool's (not modelled on the arm) -- same
        # honesty class as the wiping pad's compliance unit.
        gm = CL.grasp_mat()
        cap_site = self.m.site("cap_top").id
        cap_top = self.d.site_xpos[cap_site].copy()
        dock = np.array([cap_top[0], cap_top[1], cap_top[2] + 0.045])
        self.move(dock + np.array([0, 0, 0.06]), gm, self.cfg.grip_closed,
                  tol=0.006, t_max=6.0, tag="DRV_APPROACH")
        self.move(dock, gm, self.cfg.grip_closed, tol=0.004, t_max=6.0, tag="DRV_DOCK")
        t, held = 0.0, 0.0
        peak_tq, peak_seal = 0.0, 0.0
        win = max(int(0.1 / self.dt), 1)
        hist = []
        while t < mc.drive_t_max:
            # ON-STATION = the cap is INSIDE THE SOCKET'S THROW. The cap screws itself
            # ~17 mm downward while driving; the arm holds still and the fastener
            # descends within the socket, exactly like a real nutrunner sleeve. (Two
            # rejected versions, for the record: a FIXED 8 mm ball -- the cap descended
            # out of it, cutting the spindle mid-drive; and an in-loop IK servo
            # following the cap -- planned on unsynced state, the v2 oscillation lesson
            # in new clothes, and it destroyed every run.) Gate: within 8 mm in XY and
            # the cap top between 0 and 25 mm below the socket mouth.
            tcp_now = self.d.site_xpos[self.site]
            cap_now = self.d.site_xpos[cap_site]
            dxy = float(np.hypot(tcp_now[0] - cap_now[0], tcp_now[1] - cap_now[1]))
            depth = float((tcp_now[2] - 0.045) - cap_now[2])   # 0 at dock, grows as cap sinks
            on_station = (dxy < 0.008) and (-0.004 <= depth <= 0.025)
            self.d.ctrl[self.capdrv] = mc.drive_rate if on_station else 0.0
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    int(t / self.dt) % frames["every"] == 0:
                frames["cb"]("DRV_SPIN")
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
        # 3.4 -- the element goes into the OPEN bowl. A real motion, measured on the part.
        ins = self.insert_element(verbose=verbose)
        # 3.5a -- THE ARM places the cap (thread-start capture, modelled engagement)
        cp = self.cap_place(verbose=verbose)
        if not cp["placed"]:
            # no cap, no tightening, no seal -- the cycle fails honestly
            return {"seed": seed, "sabotage": bool(sabotage),
                    "elem_inserted": bool(ins["inserted"]), "elem_picked": True,
                    "elem_align_mm": ins["align_mm"], "elem_seat_xy_mm": ins["seat_xy_mm"],
                    "elem_seat_dz_mm": ins["seat_dz_mm"], "elem_upright": ins["upright"],
                "cap_placed": True, "cap_place_err_mm": cp["place_err_mm"],
                    "cap_placed": False, "cap_place_err_mm": cp["place_err_mm"],
                    "turns": 0.0, "torque_nm": 0.0, "peak_torque_nm": 0.0,
                    "seal_n": 0.0, "peak_seal_n": 0.0, "cap_z_mm": 0.0, "stalled": False,
                    "charge_psi": 0.0, "bubble_px": 99999, "tight_ok": False,
                    "leak_pass": False, "truth_seal": False,
                    "false_pass": False, "false_fail": False}
        # 3.5b -- the ARM holds the driver that tightens it (gated in tighten())
        tg = self.tighten(stop_turns=mc.sabotage_turns if sabotage else None,
                          verbose=verbose)
        chg = self.pressurise(tg["torque_nm"])
        self.emit_bubbles(chg["seal_holds"])
        px, _ = self.dip_and_grade(verbose=verbose)

        # --- SUCCESS IS JUDGED ON THE WORKPIECE, never on a commanded value
        # The element must actually BE in the bowl for the assembly to mean anything.
        tight_ok = (tg["torque_nm"] >= mc.torque_pass_nm
                    and mc.turns_min <= tg["turns"] <= mc.turns_max
                    and tg["stalled"] and ins["inserted"])
        leak_pass = px <= mc.bubble_px_max          # what the CAMERA says
        truth_seal = chg["seal_holds"]              # what the workpiece actually did
        return {"seed": seed, "sabotage": bool(sabotage),
                "elem_inserted": bool(ins["inserted"]), "elem_picked": bool(ins["picked"]),
                "elem_align_mm": ins["align_mm"], "elem_seat_xy_mm": ins["seat_xy_mm"],
                "elem_seat_dz_mm": ins["seat_dz_mm"], "elem_upright": ins["upright"],
                "cap_placed": True, "cap_place_err_mm": cp["place_err_mm"],
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
        ins = [r for r in hon if r.get("elem_align_mm") is not None]
        if ins:
            al = np.array([r["elem_align_mm"] for r in ins])
            sx = np.array([r["elem_seat_xy_mm"] for r in ins])
            dz = np.array([r["elem_seat_dz_mm"] for r in ins])
            print(f"  MEMBRANE INSERT (3.4) -- a REAL motion, measured on the ELEMENT:")
            print(f"    inserted         : {sum(r['elem_inserted'] for r in hon)}/{len(hon)}")
            print(f"    align before drop: median {np.median(al):.2f} mm  worst {al.max():.2f} mm"
                  f"   (radial clearance is 1.5 mm)")
            print(f"    seated off-axis  : median {np.median(sx):.2f} mm  worst {sx.max():.2f} mm")
            print(f"    base vs floor    : median {np.median(dz):+.2f} mm  worst {dz.max():+.2f} mm")
            cp_ = [r for r in hon if r.get("cap_place_err_mm") is not None]
            if cp_:
                ce = np.array([r["cap_place_err_mm"] for r in cp_])
                print(f"    cap placed BY THE ARM: {sum(r.get('cap_placed', False) for r in hon)}"
                      f"/{len(hon)}, landing median {np.median(ce):.2f} mm worst {ce.max():.2f}"
                      f" (capture envelope 4 mm / 4 deg)")
            print(f"    NOTE: the bowl is OPEN for the insert. Thread-start ENGAGEMENT is")
            print(f"    modelled (capture envelope); the arm's aim is real. The DRIVER is")
            print(f"    HELD BY THE ARM -- the spindle advances only while the wrist holds")
            print(f"    station over the cap, enforced every step.")
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
          "elem_inserted": int(sum(r["elem_inserted"] for r in hon)),
          "elem_align_mm_med": float(np.median([r["elem_align_mm"] for r in hon
                                                if r["elem_align_mm"] is not None]))
                               if any(r["elem_align_mm"] is not None for r in hon) else None,
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
    # 1800 reproduces the PUBLISHED result. 1400-1409 are the paired diagnostic range and
    # are permanently labelled development seeds -- a bare run must reproduce, not replace.
    ap.add_argument("--seed0", type=int, default=1800)
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
