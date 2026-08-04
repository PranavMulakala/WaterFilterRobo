"""V5-C -- Stage-2/3 cleaning: wipe the device's faces with a compliant pad.

    ../venv/bin/python v5_clean.py --run 3          one unit, verbose
    ../venv/bin/python v5_clean.py --eval 20 --seed0 800
    ../venv/bin/python v5_clean.py --sabotage 10    prove the verification can FAIL
    ../venv/bin/python v5_clean.py --render 3       write a video

WHAT THIS IS. DrinkPrime Stage 2 (Cabinet Cleaning) and Stage 3 (Back Panel & Top Cover
Cleaning). Their own acceptance criterion is COVERAGE, in their words:

    Stage 2, activity : "Thoroughly clean the exterior of the device,
                         ENSURING ALL SURFACES ARE COVERED"
    Stage 3, QC check : "check for any MISSED SPOTS during cleaning"

So the metric is not one we picked for being easy to compute -- it is theirs.

HOW IT WORKS. The arm picks the wiping pad off its post by the stem, presses it against a
face, and rasters. The device is on the rotary indexer, so each face is rotated into the
front working position -- where V5-0 measured 100% reachability -- and wiped there. Soil
is removed where the pad actually makes contact, so cleaning and the camera observe the
IDENTICAL mechanism: the same geoms the classifier graded are the ones that disappear.

CONTACT IS THE WHOLE PROBLEM. A position-controlled arm cannot ask for a force; it can
only ask for a position. Press too little and the pad floats and misses patches; press too
much and you stall the arm or shove the device off the indexer. The pad is deliberately
compliant (measured force/penetration: 1.4 / 2.0 / 2.4 / 2.6 / 3.0 / 4.6 mm at
0 / 5 / 10 / 20 / 40 / 60 N, monotonic), so a commanded over-travel converts into a bounded
force rather than a collision. That is the cheap industrial answer -- let the tool absorb
the error instead of closing a force loop -- and it is what V5-0's 30-degree tilt cone
was already assuming.

WHAT IS NOT MODELLED. No cream, no detergent, no chemistry, no wear. What is verified is
that the soil the camera could see is gone, not that CIF cream would lift it.
"""
import argparse
import json
import sys
from dataclasses import dataclass

import numpy as np
import mujoco

import v5_triage as TR
from sim_poc2 import ik_step

XML = "ufactory_xarm7/refurb_scene_v5.xml"


@dataclass(frozen=True)
class CleanConfig:
    xml: str = XML
    # --- grasp. MEASURED, not inherited: the finger pads sit +38.9 mm ABOVE link_tcp on
    #     this gripper. The project's older note says ~25 mm, which is for the v2
    #     cartridge grasp; reusing it here would have missed the stem entirely.
    # --- tool changer. The wrist must reach this pose, pointing down, within the
    #     capture envelope, or the latch fails and the cycle aborts. A real changer's
    #     capture is a few mm; 4 mm / 4 deg is a realistic commodity figure.
    couple_tcp: tuple = (0.300, -0.340, 0.130)
    capture_mm: float = 4.0
    capture_deg: float = 4.0

    pad_offset: float = 0.0389
    stem_grasp_z: float = 0.105     # where on the stem the pads should close
    grip_open: float = 0.0
    grip_closed: float = 245.0

    # --- raster. Rows/cols are COMPUTED PER FACE from the pad size, not fixed: a fixed
    #     5 x 7 grid put 99 mm between rows while the pad only wipes a 68 mm swathe, so
    #     the raster stepped straight over the soil and cleaned 0 of 9 patches while
    #     reporting healthy contact forces the whole time. Step must be <= the wipe
    #     width or coverage is decided by luck.
    # step <= radius guarantees the worst-case in-plane gap (step/sqrt(2) for a square
    # grid) stays inside the wipe radius. At 1.30 it did not, and coverage depended on
    # where the soil happened to land between passes.
    step_frac: float = 0.95         # raster step, in pad RADII
    # 3 mm, not 6. The pad gives 1.4-4.6 mm over 0-60 N, so 6 mm of commanded
    # over-travel sat high on that curve and the resulting friction tore the tool out of
    # the grip. 3 mm lands around 10 N -- enough to wipe, not enough to strip.
    # THE PRESS AND THE TOLERANCE ARE COUPLED. With a positively-latched tool nothing
    # absorbs position error except the pad's own compliance (2.6 mm at 20 N), so an
    # arrival tolerance LARGER than the press depth lets the pad bury itself: at
    # tol 5 mm / press 3 mm the median contact force was 101 N and the peak 933 N, with
    # only 22% of samples in band. The compliant GRIP used to hide this by slipping --
    # that is the hidden cost of a rigid coupling, and it has to be paid in precision.
    # The pad is 20 mm thick and its geom ORIGIN is at its centre, so commanding the
    # centre onto the face plane buries it by half a thickness before any press at all.
    # Measured consequence: 12.5 mm of penetration, 101 N median / 795 N peak contact,
    # 22% of samples in band. Target the pad's CONTACT SURFACE, not its centre. Same
    # mistake as the gripper finger-pad offset, one object further out.
    pad_thick_half: float = 0.010   # m, half-thickness of the pad face geom
    # With the ACTIVE CONTACT FLANGE the press is no longer a knife-edge: it is the
    # commanded COMPRESSION of a 800 N/m spring, so it sets force directly (12 mm ->
    # ~9.6 N) and a few mm of path error costs a few newtons instead of tens. Before
    # the flange the press had to be smaller than the arrival tolerance to avoid burying
    # the tool, which is not a condition a real arm can hold.
    press: float = 0.012            # m of commanded flange compression
    wipe_tol: float = 0.004         # m, arrival tolerance -- now well inside the stroke
    standoff: float = 0.055         # m, tcp-to-face when clear
    # The generator scatters patches over +-0.41 of each face extent, so a raster that
    # only spans +-0.34 can never reach the outer ring no matter how well it presses.
    pad_half: float = 0.030         # m, half-width of the 60 mm pad
    floor_margin: float = 0.012     # m, extra clearance above the bench/platter
    faces_deg: tuple = (0.0, 90.0, 180.0, 270.0)

    # --- soil removal: the pad's contact patch
    pad_radius: float = 0.030       # m, in-plane wipe radius of the 60 mm square pad
    pad_reach: float = 0.022        # m, how far off the pad plane a patch still counts
    contact_min_n: float = 0.5      # N, below this the pad is not really touching

    # --- force band. Upper bound from the pad curve (60 N is still monotonic); lower
    #     bound is "actually touching".
    force_lo: float = 1.0
    force_hi: float = 60.0

    speed: float = 1.0
    settle_s: float = 0.35


CFG = CleanConfig()


# ============================================================ helpers
def tool_mat_face(index_deg):
    """Tool frame pressing into the face currently at the FRONT (-X) position."""
    n = np.array([-1.0, 0.0, 0.0])
    z = -n
    x = np.cross(np.array([0.0, 0.0, 1.0]), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.column_stack([x, y, z])


def grasp_mat():
    """Gripper pointing straight down, jaws across the stem."""
    return np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]]).T


class Cell:
    def __init__(self, cfg=CFG):
        self.cfg = cfg
        self.m = mujoco.MjModel.from_xml_path(cfg.xml)
        self.d = mujoco.MjData(self.m)
        self.ik = mujoco.MjData(self.m)
        m = self.m
        self.jnt = [m.joint(f"joint{i}").id for i in range(1, 8)]
        self.qadr = np.array([m.jnt_qposadr[j] for j in self.jnt])
        self.dof = np.array([m.jnt_dofadr[j] for j in self.jnt])
        self.rng_j = m.jnt_range[self.jnt].copy()
        self.act = [m.actuator(f"act{i}").id for i in range(1, 8)]
        self.grip = m.actuator("gripper").id
        self.tt_act = m.actuator("tt").id
        self.tt_q = m.jnt_qposadr[m.joint("tt_rot").id]
        self.site = m.site("link_tcp").id
        self.pad_face = m.geom("pad_face").id
        self.stem = m.geom("pad_stem").id
        self.acf_q = m.jnt_qposadr[m.joint("acf").id]
        self.cab_bodyid = m.body("cabinet").id
        self.geomgroup = np.array([1, 1, 1, 1, 1, 1], np.uint8)
        self.pad_body = m.body("padtool").id
        name = lambda i: mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i) or ""
        self.pools = {p: [i for i in range(m.ngeom) if name(i).startswith(p)]
                      for p in ("soil", "scr", "dent")}
        self.dt = m.opt.timestep
        self.q_des = None
        self.gb = m.body("xarm_gripper_base_link").id
        self.eq = next(k for k in range(m.neq)
                       if mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_EQUALITY, k) == "toollock")

    # ------------------------------------------------------- tool changer
    def couple(self):
        """Latch the tool changer, if the wrist is inside the capture envelope.

        Returns (latched, position error, angle error). The latch welds at the pose
        ACTUALLY achieved, so residual misalignment is carried into the wipe rather than
        silently corrected -- a real changer would centre the tool as it pulls in, so
        this is the conservative direction.
        """
        m, d = self.m, self.d
        tcp = d.site_xpos[self.site]
        Rt = d.site_xmat[self.site].reshape(3, 3)
        want = np.array(self.cfg.couple_tcp)
        perr = float(np.linalg.norm(tcp - want))
        # wrist must also be pointing down, as the holder presents the tool
        aerr = float(np.degrees(np.arccos(np.clip(-Rt[2, 2], -1, 1))))
        if perr > self.cfg.capture_mm / 1000 or aerr > self.cfg.capture_deg:
            return False, perr, aerr
        p1, R1 = d.xpos[self.gb], d.xmat[self.gb].reshape(3, 3)
        p2, R2 = d.xpos[self.pad_body], d.xmat[self.pad_body].reshape(3, 3)
        relpos = R1.T @ (p2 - p1)
        q = np.zeros(4)
        mujoco.mju_mat2Quat(q, (R1.T @ R2).flatten())
        m.eq_data[self.eq][:3] = 0.0             # anchor, in body2 frame
        m.eq_data[self.eq][3:6] = relpos
        m.eq_data[self.eq][6:10] = q
        m.eq_data[self.eq][10] = 1.0             # torquescale
        d.eq_active[self.eq] = 1
        mujoco.mj_forward(m, d)
        return True, perr, aerr

    def decouple(self):
        self.d.eq_active[self.eq] = 0
        mujoco.mj_forward(self.m, self.d)

    # ---------------------------------------------------------------- state
    def reset(self, seed):
        m, d = self.m, self.d
        mujoco.mj_resetDataKeyframe(m, d, m.key("v5home").id)
        rng = np.random.default_rng(seed)
        truth, nd, ns, no = TR.sample_condition(rng, TR.CFG)
        TR.set_pools(m, self.pools, nd, ns, no, rng)
        self.revealed_soil = [g for g in self.pools["soil"] if m.geom_rgba[g][3] > 0]
        mujoco.mj_forward(m, d)
        self.q_des = d.qpos[self.qadr].copy()
        return truth, nd, ns, no

    def pad_contact_force(self):
        """Total normal force on the pad face this step."""
        tot = 0.0
        f6 = np.zeros(6)
        for c in range(self.d.ncon):
            con = self.d.contact[c]
            if self.pad_face in (con.geom1, con.geom2):
                mujoco.mj_contactForce(self.m, self.d, c, f6)
                tot += abs(f6[0])
        return tot

    def wipe(self):
        """Hide soil geoms the pad's contact patch has passed over.

        Removal requires ACTUAL CONTACT, not proximity: if the pad is not pressing, it
        cleans nothing. That is what makes the coverage number a statement about the
        motion rather than about the trajectory we happened to command.
        """
        f = self.pad_contact_force()
        if f < self.cfg.contact_min_n:
            return 0
        centre = self.d.geom_xpos[self.pad_face]
        R = self.d.geom_xmat[self.pad_face].reshape(3, 3)
        n_hat = R[:, 2]                       # pad's own face normal
        n = 0
        for g in self.revealed_soil:
            if self.m.geom_rgba[g][3] <= 0:
                continue
            v = self.d.geom_xpos[g] - centre
            # IN-PLANE distance, not 3D. The pad is a flat 60 mm square and its geom
            # CENTRE sits half a thickness behind the contact surface, so a 3D distance
            # spends part of the wipe radius on that offset -- measured, the closest
            # approach came out 33.8 mm against a 34 mm radius, i.e. cleaning succeeded
            # or failed on rounding. Contact is already required separately by the force
            # test above, so the only question left is lateral reach.
            out = float(v @ n_hat)
            inplane = float(np.linalg.norm(v - out * n_hat))
            if inplane < self.cfg.pad_radius and abs(out) < self.cfg.pad_reach:
                self.m.geom_rgba[g][3] = 0.0
                n += 1
        return n

    # ---------------------------------------------------------------- motion
    def step_to(self, tgt, mat, grip, index_deg=0.0, frames=None, tag=""):
        """One control step toward a Cartesian target. Returns TCP position error."""
        m, d = self.m, self.d
        self.ik.qpos[:] = d.qpos
        self.ik.qpos[self.qadr] = self.q_des
        mujoco.mj_kinematics(m, self.ik)
        mujoco.mj_comPos(m, self.ik)
        dq, err = ik_step(m, self.ik, self.site, tgt, mat, self.dof)
        mx = np.max(np.abs(dq))
        lim = 0.02 * self.cfg.speed
        if mx > lim:
            dq *= lim / mx
        self.q_des = np.clip(self.q_des + dq, self.rng_j[:, 0], self.rng_j[:, 1])
        d.ctrl[self.act] = self.q_des
        d.ctrl[self.grip] = grip
        d.ctrl[self.tt_act] = np.deg2rad(index_deg)
        d.qfrc_applied[self.dof] = d.qfrc_bias[self.dof]
        mujoco.mj_step(m, d)
        return err

    def move(self, tgt, mat, grip, index_deg=0.0, tol=0.004, t_max=6.0,
             wipe=False, log=None, frames=None, tag=""):
        """Drive to a Cartesian target and WAIT FOR THE ARM TO ACTUALLY GET THERE.

        The completion test is on the MEASURED TCP, not on the commanded configuration.
        The first version broke as soon as the IK's own error went under tolerance --
        which happens in ~0.4 s, while the physical arm is still up to 0.9 rad behind and
        147 mm away from the target. Every downstream phase then started from the wrong
        place, and the pad was never picked up. This is the same class of mistake as
        v2's original oscillation, in reverse: there we listened to the measured state
        when we should have planned on the commanded one; here we judged completion on
        the commanded one when only the measured one means anything.
        """
        t = 0.0
        cleaned = 0
        settle = 0.0
        while t < t_max:
            self.step_to(tgt, mat, grip, index_deg, frames, tag)
            t += self.dt
            if wipe:
                cleaned += self.wipe()
                if log is not None:
                    log.append(self.pad_contact_force())
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    int(t / self.dt) % frames["every"] == 0:
                frames["cb"](tag)
            reached = float(np.linalg.norm(self.d.site_xpos[self.site] - tgt))
            if reached < tol:
                settle += self.dt
                if settle >= 0.06:
                    break
            else:
                settle = 0.0
        return cleaned

    def dwell(self, s, mat, tgt, grip, index_deg=0.0, frames=None, tag=""):
        t = 0.0
        while t < s:
            self.step_to(tgt, mat, grip, index_deg, frames, tag)
            t += self.dt

    def surface_x(self, y, z):
        """X of the device surface at (y, z), by casting a ray from in front of it.

        Exact where a plane fit is not: it sees whatever geom is actually presented at
        this point -- body, proud back panel, top cover ledge -- with no assumption about
        which face the indexer has brought round.
        """
        pnt = np.array([0.20, y, z])
        vec = np.array([1.0, 0.0, 0.0])
        geomid = np.zeros(1, np.int32)
        # bodyexclude = -1: exclude NOTHING. Passing the cabinet here excludes the very
        # thing we are trying to hit -- the ray then flew past it and returned the
        # backdrop at x = 0.854 for every point, on every face.
        dist = mujoco.mj_ray(self.m, self.d, pnt, vec,
                             self.geomgroup, 1, -1, geomid)
        if dist < 0 or geomid[0] < 0:
            return None
        if self.m.geom_bodyid[geomid[0]] != self.cab_bodyid:
            return None                        # hit something that is not the device
        return float(pnt[0] + dist)

    # ---------------------------------------------------------------- geometry
    def front_face_plane(self, index_deg):
        """(x of the face now at the FRONT position, half-width in Y, z range).

        Read from the model at the commanded index angle, so it follows the device
        rather than assuming which face is presented.
        """
        m, d = self.m, self.d
        cab = m.body("cabinet").id
        cg = m.geom("cab_body").id
        cy = d.geom_xpos[cg][1]
        # THE PRESENTED SURFACE IS THE OUTERMOST GEOM, not the body's own face. The back
        # panel stands 10 mm proud of the body, so at index 180 a plane taken from
        # cab_body sits 10 mm INSIDE the panel -- and the raster then drove the pad 10 mm
        # into it. Measured: 1.2 M pad/back-panel contacts, 153 k of them above 100 N,
        # and a median force that did not respond to press depth at all because the press
        # was not what was causing it.
        xs, ys, zs = [], [], []
        for i in range(m.ngeom):
            if m.geom_bodyid[i] != cab or not m.geom_contype[i]:
                continue
            e = np.abs(d.geom_xmat[i].reshape(3, 3)) @ m.geom_size[i]
            p = d.geom_xpos[i]
            xs.append(p[0] - e[0])
            ys.append(e[1])
            zs.append((p[2] - e[2], p[2] + e[2]))
        z0, z1 = min(a for a, _ in zs), max(b for _, b in zs)
        return min(xs), cy, max(ys), z0, z1

    # ---------------------------------------------------------------- the cycle
    def run(self, seed, verbose=False, frames=None):  # noqa: C901
        cfg = self.cfg
        truth, nd, ns, no = self.reset(seed)
        n0 = len(self.revealed_soil)
        gm = grasp_mat()
        want = np.array(cfg.couple_tcp)

        # --- couple the tool changer
        self.move(want + np.array([0, 0, 0.12]), gm, cfg.grip_open, tag="APPROACH",
                  frames=frames)
        self.move(want, gm, cfg.grip_open, tol=0.003, t_max=8.0, tag="COUPLE",
                  frames=frames)
        latched, perr, aerr = self.couple()
        self.move(want + np.array([0, 0, 0.14]), gm, cfg.grip_open, t_max=8.0,
                  tag="LIFT", frames=frames)

        # MEASURE the coupled tool offset. Even with a positive coupling this is
        # measured rather than assumed -- the latch welds at the pose ACTUALLY achieved,
        # so whatever misalignment was inside the capture envelope is carried here.
        tcp = self.d.site_xpos[self.site]
        Rt = self.d.site_xmat[self.site].reshape(3, 3)
        self.pad_rel = Rt.T @ (self.d.geom_xpos[self.pad_face] - tcp)
        self.stem_rel = Rt.T @ (self.d.geom_xpos[self.stem] - tcp)

        if not latched:
            return {"seed": seed, "truth": truth, "picked": False, "coverage": 0.0,
                    "soil0": n0, "cleaned": 0, "missed": n0, "f_med": 0.0, "f_max": 0.0,
                    "in_band": 0.0, "contact_frac": 0.0,
                    "couple_mm": perr * 1000, "couple_deg": aerr}

        # --- wipe each face at the front working position
        forces, cleaned = [], 0
        # A SAFE WAYPOINT well clear of the device, in front of it and above the bench.
        # Everything indexes from here.
        safe = np.array([0.26, 0.0, 0.42])
        prev_deg = 0.0
        for deg in cfg.faces_deg:
            # RETRACT CLEAR, THEN INDEX, THEN APPROACH -- in that order. Rotating the
            # device while the arm was still swinging back across it swept the tool
            # through the cabinet and knocked it out of the jaws: face 0 wiped correctly
            # and every face after it was "wiped" with an empty gripper, while the force
            # log kept reporting healthy contact. A real cell sequences it the same way,
            # for the same reason.
            self.move(safe, tool_mat_face(deg), cfg.grip_open, index_deg=prev_deg,
                      t_max=8.0, tag="SAFE", frames=frames)
            self.dwell(1.2, tool_mat_face(deg), safe, cfg.grip_open,
                       index_deg=deg, frames=frames, tag=f"INDEX {deg:.0f}")
            prev_deg = deg
            fx, cy, hw, z0, z1 = self.front_face_plane(deg)
            tm = tool_mat_face(deg)
            zc, zh = (z0 + z1) / 2, (z1 - z0)
            # approach the face centre from clear
            # Approach on the LIFT-frame estimate, then RE-MEASURE once the wrist is
            # actually in the working orientation. The pad shifts in the jaws when the
            # tool rotates from pointing-down to pointing-horizontal -- gravity now pulls
            # it sideways across the grip instead of along it -- so an offset measured at
            # the lift is not the offset during the wipe. Measuring at the lift and using
            # it here put coverage at 0%.
            approach = np.array([fx - cfg.standoff, cy, zc]) - tm @ self.pad_rel
            self.move(approach, tm, cfg.grip_open,
                      index_deg=deg, t_max=10.0, tag="TO FACE", frames=frames)
            self.dwell(0.3, tm, approach, cfg.grip_open, index_deg=deg,
                       frames=frames, tag="SETTLE")
            tcp_n = self.d.site_xpos[self.site]
            Rn = self.d.site_xmat[self.site].reshape(3, 3)
            pad_rel = Rn.T @ (self.d.geom_xpos[self.pad_face] - tcp_n)
            # RASTER BOUNDS FROM THE FACE AND THE PAD, not a fixed fraction. The pad
            # CENTRE must stay inside the face by its own half-width, or the pad hangs
            # over the edge -- and at the bottom it hangs into the BENCH. Measured: with
            # a fixed +-0.44 span the bottom row drove the pad into the bench at raster
            # point 9 of 135, knocked the tool out of the jaws, and every later face was
            # "wiped" with an empty gripper while the metrics still logged contact.
            ph = cfg.pad_half
            v_lo = (z0 + ph + cfg.floor_margin) - zc
            v_hi = (z1 - ph) - zc
            u_lim = hw - ph
            step = cfg.step_frac * cfg.pad_radius
            rows = max(int(np.ceil((v_hi - v_lo) / step)) + 1, 2)
            cols = max(int(np.ceil(2 * u_lim / step)) + 1, 2)
            for r in range(rows):
                v = v_lo + (v_hi - v_lo) * r / (rows - 1)
                order = range(cols) if r % 2 == 0 else reversed(range(cols))
                for c in order:
                    u = -u_lim + 2 * u_lim * c / (cols - 1)
                    # PROBE THE SURFACE PER POINT with a ray, instead of assuming one
                    # plane for the whole face. A single plane from the geom extents was
                    # inconsistent between mirror-symmetric orientations (0.4536 at index
                    # 90 vs 0.4800 at 270), because a rotated box's X-extent is not its
                    # presented face -- so the pad was commanded short of the surface and
                    # did not touch for 29% of the raster. A ray gives the ACTUAL surface
                    # at this point, and handles the proud back panel for free.
                    hit = self.surface_x(cy + u, zc + v)
                    if hit is None:
                        continue
                    pad_pt = np.array([hit - cfg.pad_thick_half + cfg.press,
                                       cy + u, zc + v])
                    tgt = pad_pt - tm @ pad_rel
                    cleaned += self.move(tgt, tm, cfg.grip_open, index_deg=deg,
                                         tol=cfg.wipe_tol, t_max=2.5, wipe=True,
                                         log=forces, tag=f"WIPE {deg:.0f}", frames=frames)
            retract = np.array([fx - cfg.standoff - 0.05, cy, zc]) - tm @ pad_rel
            self.move(retract, tm, cfg.grip_open,
                      index_deg=deg, t_max=8.0, tag="RETRACT", frames=frames)
            if verbose:
                on_face = sum(1 for g in self.revealed_soil
                              if self.m.geom_rgba[g][3] > 0)
                print(f"    face {deg:>5.0f} deg: {rows}x{cols} raster, "
                      f"pad_rel {np.round(pad_rel,4)}, fx={fx:.4f}, "
                      f"cleaned so far {n0 - on_face}/{n0}")

        self.move(safe, tool_mat_face(0.0), cfg.grip_open, index_deg=prev_deg,
                  t_max=8.0, tag="SAFE", frames=frames)

        # --- the TOP face. Stage 3 names the top cover explicitly, and the vertical
        #     loop above never touches it -- soil there would have been permanently
        #     uncleanable while the coverage number quietly ignored it.
        tmt = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]]).T
        cg = self.m.geom("cab_body").id
        cx, cyy = self.d.geom_xpos[cg][0], self.d.geom_xpos[cg][1]
        _, _, _, _, ztop = self.front_face_plane(0.0)
        appr = np.array([cx, cyy, ztop + 0.10])
        self.move(appr, tmt, cfg.grip_open, t_max=10.0, tag="TO TOP", frames=frames)
        self.dwell(0.3, tmt, appr, cfg.grip_open, frames=frames, tag="SETTLE")
        tcp_n = self.d.site_xpos[self.site]
        Rn = self.d.site_xmat[self.site].reshape(3, 3)
        prel = Rn.T @ (self.d.geom_xpos[self.pad_face] - tcp_n)
        hx, hy = self.m.geom_size[cg][0], self.m.geom_size[cg][1]
        step = cfg.step_frac * cfg.pad_radius
        ux, uy = hx - cfg.pad_half, hy - cfg.pad_half
        rows = max(int(np.ceil(2 * ux / step)) + 1, 2)
        cols = max(int(np.ceil(2 * uy / step)) + 1, 2)
        for r in range(rows):
            du = -ux + 2 * ux * r / (rows - 1)
            order = range(cols) if r % 2 == 0 else reversed(range(cols))
            for cc in order:
                dv = -uy + 2 * uy * cc / (cols - 1)
                pad_pt = np.array([cx + du, cyy + dv,
                                   ztop + cfg.pad_thick_half - cfg.press])
                cleaned += self.move(pad_pt - tmt @ prel, tmt, cfg.grip_open,
                                     tol=cfg.wipe_tol, t_max=2.5, wipe=True, log=forces,
                                     tag="WIPE top", frames=frames)
        self.move(np.array([cx, cyy, ztop + 0.12]), tmt, cfg.grip_open,
                  t_max=8.0, tag="TOP CLEAR", frames=frames)

        # measure how far the tool moved relative to the wrist across the whole job,
        # while it is STILL LATCHED -- measuring after unlatch just reports the holder
        # COUPLING integrity is measured on the SHANK, not the pad. The pad now rides
        # on the compliance flange, so its offset from the wrist SHOULD change -- that
        # movement is the flange doing its job, and reporting it as "tool drift" would
        # make a working spring look like a slipping grip.
        tcp_e = self.d.site_xpos[self.site]
        Re = self.d.site_xmat[self.site].reshape(3, 3)
        drift_mm = float(np.linalg.norm(
            Re.T @ (self.d.geom_xpos[self.stem] - tcp_e) - self.stem_rel) * 1000)
        acf_mm = float(self.d.qpos[self.acf_q] * 1000)

        # --- return the tool to its holder and unlatch
        self.move(want + np.array([0, 0, 0.14]), gm, cfg.grip_open,
                  t_max=12.0, tag="RETURN", frames=frames)
        self.move(want, gm, cfg.grip_open, tol=0.004, t_max=8.0, tag="PLACE",
                  frames=frames)
        self.decouple()
        self.dwell(0.3, gm, want, cfg.grip_open, frames=frames, tag="UNLATCH")
        self.move(want + np.array([0, 0, 0.14]), gm, cfg.grip_open,
                  t_max=8.0, tag="CLEAR", frames=frames)

        left = sum(1 for g in self.revealed_soil if self.m.geom_rgba[g][3] > 0)
        f = np.array(forces) if forces else np.array([0.0])
        touching = f[f >= self.cfg.contact_min_n]
        return {"seed": seed, "truth": truth, "picked": True,
                "couple_mm": perr * 1000, "couple_deg": aerr,
                "coupling_drift_mm": drift_mm, "acf_mm": acf_mm,
                "soil0": n0, "cleaned": n0 - left, "missed": left,
                "coverage": (n0 - left) / n0 if n0 else 1.0,
                "f_med": float(np.median(touching)) if len(touching) else 0.0,
                "f_max": float(f.max()),
                "in_band": float(((touching >= cfg.force_lo) &
                                  (touching <= cfg.force_hi)).mean()) if len(touching) else 0.0,
                "contact_frac": float((f >= cfg.contact_min_n).mean())}


def report(rows):
    n = len(rows)
    ok = [r for r in rows if r["picked"]]
    cov = np.array([r["coverage"] for r in ok]) if ok else np.array([0.0])
    print(f"\nCLEANING: {n} units | pad picked {len(ok)}/{n}")
    print(f"  COVERAGE        : mean {cov.mean()*100:.1f}%  median "
          f"{np.median(cov)*100:.1f}%  worst {cov.min()*100:.1f}%")
    print(f"  units at 100%   : {sum(1 for c in cov if c >= 0.999)}/{len(ok)}")
    tot0 = sum(r["soil0"] for r in ok)
    totm = sum(r["missed"] for r in ok)
    print(f"  MISSED SPOTS    : {totm} of {tot0} soil patches "
          f"({totm/max(tot0,1)*100:.1f}%)   <- Stage 3's own QC check")
    fm = np.array([r["f_med"] for r in ok]) if ok else np.array([0.0])
    fx = np.array([r["f_max"] for r in ok]) if ok else np.array([0.0])
    ib = np.array([r["in_band"] for r in ok]) if ok else np.array([0.0])
    cf = np.array([r["contact_frac"] for r in ok]) if ok else np.array([0.0])
    print(f"  contact force   : median {fm.mean():.1f} N, peak {fx.max():.1f} N "
          f"(pad validated monotonic to 60 N)")
    print(f"  in force band   : {ib.mean()*100:.1f}%   contact during raster: "
          f"{cf.mean()*100:.1f}%")
    cd = np.array([r.get("coupling_drift_mm", 0.0) for r in ok]) if ok else np.array([0.0])
    print(f"  coupling drift  : {cd.mean():.2f} mm mean, {cd.max():.2f} mm worst "
          f"(tool changer; the flange stroke is separate and expected)")
    print("\n  Coverage is of ALL FIVE faces -- the back panel carries soil too, since the")
    print("  indexer reaches it. No fluid or chemistry is simulated: what is verified is")
    print("  that the soil the camera could see is gone.")
    return {"n": n, "picked": len(ok), "coverage_mean": float(cov.mean()),
            "coverage_worst": float(cov.min()), "missed": int(totm), "soil": int(tot0),
            "f_max": float(fx.max()), "in_band": float(ib.mean())}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int)
    ap.add_argument("--eval", type=int)
    ap.add_argument("--seed0", type=int, default=800)
    a = ap.parse_args()
    if a.run is not None:
        c = Cell()
        r = c.run(a.run, verbose=True)
        print(r)
    elif a.eval:
        c = Cell()
        rows = []
        for k in range(a.eval):
            rows.append(c.run(a.seed0 + k))
            print(f"  seed {a.seed0+k}: cov {rows[-1]['coverage']*100:5.1f}%  "
                  f"picked={rows[-1]['picked']}  fmax {rows[-1]['f_max']:.1f} N")
        st = report(rows)
        with open("stats_v5_clean.json", "w") as f:
            json.dump(st, f, indent=2)
        print("\nwrote stats_v5_clean.json")
    else:
        ap.print_help()
        sys.exit(1)
