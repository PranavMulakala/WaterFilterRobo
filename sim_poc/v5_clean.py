"""V5-C -- Stage-2/3 cleaning: wipe the device's faces with a compliant pad.

    ../venv/bin/python v5_clean.py --run 3          one unit, verbose
    ../venv/bin/python v5_clean.py --eval 8          held-out; --seed0 defaults to 900

    ../venv/bin/python v5_clean.py --sabotage 8      V5-D falsification test

`--render` is still NOT implemented (that is V5-G): no v5 station writes video. The
`frames` dict is threaded through every motion method, so a renderer is wiring rather than
construction -- sim_poc4.py has a working template.

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
import v5_reach as RE
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
    # A WIPE IS DONE WHEN THE PAD HAS SWEPT THE POINT, not when the wrist hits a
    # positional tolerance it cannot hold while loaded. Waiting on 4 mm of TCP error was
    # unreachable under contact -- 0.8 deg of joint lag is 14 mm at that extension -- so
    # every top-face point and 60% of front-face points ran the full 2.5 s timeout
    # pressing at full command. Measured cost of that stall: peak 326 N and only 74.8%
    # of samples in band, beyond where the pad model is validated. Terminating on contact
    # is both the physical completion criterion for a wipe and the thing that bounds the
    # press duration. The COVERAGE criterion is untouched: a patch still only counts when
    # real contact force passes over it.
    # First attempt at this was "break once contact has lasted 0.1 s", which fired on the
    # first graze while the wrist was still 20-90 mm out: coverage fell 100% -> 88.9%.
    # A position-controlled arm pressing into a surface converges to a STEADY-STATE
    # error; the useful signal is that it has stopped closing, not that it has touched.
    # --- V5-D verification. The check re-inspects the unit we just cleaned through the
    #     SAME observation path the triage station uses -- same fixed camera, same index
    #     angles, same per-face regions, same feature extractor. That is not tidiness: v4's
    #     first sabotage test wrongly PASSED 2 of 5 dirty parts precisely because
    #     verification looked through one camera view while the inspection it was checking
    #     used two. A verifier that sees less than the process it verifies cannot fail.
    verify_soil_max: int = 0        # residual soil components tolerated, per unit
    wipe_stall_s: float = 0.20      # window over which progress is judged
    wipe_stall_m: float = 0.0005    # less closing than this, while in contact, is a stall
    # ...and 'in contact' has to mean SEATED, not grazing. contact_min_n is 0.5 N, which
    # the pad reaches on the way in while the wrist is still tens of mm out; stalling on
    # that ended points before the pad had swept them and cost 11 points of coverage.
    wipe_seat_n: float = 5.0        # N the pad must carry before a stall counts as done

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


# --- the tilt cone. THIS IS NOT A RELAXATION WE INVENTED TO PASS. v5_reach's gate has
#     always reported coverage inside a 30-degree cone alongside the exact-normal
#     "strict" figure, because a 20 mm compliant pad genuinely conforms over about that
#     much. What went wrong is that the gate allowed the cone and the CLEANER did not
#     use it: tool_mat_face() returned one fixed exact-normal frame for every point, so
#     the station was living in the strict column -- front 83%, sides 27%, top 63% --
#     while a green gate reported the 100% one. Worse, re-running the placement sweep
#     with the tool's real 105 mm wrist-to-pad length shows NO placement presses
#     exact-normal on all five faces. The cone is load-bearing, not optional.
#
#     THE CONE IS IMPORTED FROM THE GATE, not restated here. That is fix 5, and it is the
#     one that stops this recurring: a gate is only a gate for the quantity it measures,
#     and a consumer that quietly uses a DIFFERENT quantity turns a green light into
#     decoration. v5_reach reports strict and relaxed side by side precisely so the
#     relaxation stays visible; the cleaner now spends that same allowance, from the same
#     constant, and reports the tilt it actually used against the limit.
TILT_TOL_DEG = RE.TILT_TOL_DEG
TILT_DIRS = RE.TILT_DIRS
COLD = np.array([0.0, -0.3, 0.0, 0.9, 0.0, 1.1, 0.0])
POS_TOL, ROT_TOL = 0.004, np.deg2rad(4)
PLAN_ITERS = 220


def tilted_mats(base):
    """(matrix, tilt_deg) pressing into the same face, smallest deviation first.

    Same construction as v5_reach.tilted_mats, but about a base frame handed in rather
    than rebuilt from a normal -- the tool changer cares about the in-plane orientation
    and re-deriving it here would quietly rotate the jaws.
    """
    for tilt in TILT_TOL_DEG:
        if tilt == 0.0:
            yield base, 0.0
            continue
        t = np.deg2rad(tilt)
        for k in range(TILT_DIRS):
            a = 2 * np.pi * k / TILT_DIRS
            axis = np.cos(a) * base[:, 0] + np.sin(a) * base[:, 1]
            quat, Rm = np.zeros(4), np.zeros(9)
            mujoco.mju_axisAngle2Quat(quat, axis, t)
            mujoco.mju_quat2Mat(Rm, quat)
            yield Rm.reshape(3, 3) @ base, tilt


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
        # the device's own COLLIDABLE geoms -- what surface_x rays against. Condition
        # patches are excluded by contype: they are 1 mm decals lying ON the surface, and
        # letting the probe hit one would put the raster plane a patch-thickness proud of
        # the face at exactly the points that matter most.
        self.cab_geoms = [g for g in range(m.ngeom)
                          if m.geom_bodyid[g] == self.cab_bodyid and m.geom_contype[g]]
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
        # a THIRD MjData, for planning only. mj_forward has to run to get contacts, and
        # running it on the live data would teleport the arm mid-cycle.
        self.plan = mujoco.MjData(m)
        base = m.body("link_base").id
        arm_bodies = set()
        for b in range(m.nbody):
            p = b
            while p != 0:
                if p == base:
                    arm_bodies.add(b)
                    break
                p = m.body_parentid[p]
        self.arm_geoms = {g for g in range(m.ngeom) if m.geom_bodyid[g] in arm_bodies}
        tool_bodies = {m.body("padtool").id, m.body("padhead").id}
        self.tool_geoms = {g for g in range(m.ngeom) if m.geom_bodyid[g] in tool_bodies}
        self.pad_jq = m.jnt_qposadr[m.body_jntadr[m.body("padtool").id]]
        self.tool_rel = None
        self.rend = None            # built lazily; rendering is the expensive part
        self.rend_top = None        # V5-D: the top face needs its own camera
        # V5-D: when True the pad still moves, still presses and still logs contact --
        # it simply stops REMOVING soil. Sabotaging the outcome rather than the motion is
        # what makes the falsification test about the verifier instead of about the arm.
        self.sabotage = False

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
        # keep the weld transform so the PLANNER can put the tool where the arm will
        # actually carry it. Without this the planner is blind to its own tool.
        self.tool_rel = (relpos.copy(), q.copy())
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
        self.raster_planned = self.raster_skipped = self.raster_infeasible = 0
        self.tilts = []
        self.q_warm = None
        self.face_unreachable = {}
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

    # ------------------------------------------------------- V5-D verification
    def _sync_triage_globals(self):
        """Point v5_triage's face-projection globals at THIS model.

        face_regions() reads module-level constants that load_scene() normally fills in.
        v5_clean builds its own model and never calls load_scene, so those constants would
        silently describe whatever was loaded last -- and being right by default is not the
        same as being right on purpose.
        """
        m, d = self.m, self.d
        g = m.geom("cab_body").id
        TR.CFG_CAB_XY = (float(d.geom_xpos[g][0]), float(d.geom_xpos[g][1]))
        TR.CAB_HALF_XY = (float(m.geom_size[g][0]), float(m.geom_size[g][1]))
        zs = [(d.geom_xpos[i][2] - m.geom_size[i][2], d.geom_xpos[i][2] + m.geom_size[i][2])
              for i in range(m.ngeom)
              if m.geom_bodyid[i] == self.cab_bodyid and m.geom_contype[i]]
        TR.CAB_BASE = float(min(a for a, _ in zs))
        TR.CAB_TOP = float(max(b for _, b in zs))

    def soil_face(self, g):
        """Which face a soil geom sits on, in the cabinet's own frame."""
        cab = self.cab_bodyid
        p0 = self.d.xpos[cab]
        R0 = self.d.xmat[cab].reshape(3, 3)
        x, y, z = R0.T @ (self.d.geom_xpos[g] - p0)
        hd, hw = self.m.geom_size[self.m.geom("cab_body").id][:2]
        if z > 2 * self.m.geom_size[self.m.geom("cab_body").id][2] - 0.02:
            return "top"
        if x < -hd + 0.02:
            return "front"
        if x > hd + 0.01:
            return "back"
        return "left" if y < 0 else "right"

    def verify(self):
        """Re-inspect the unit THIS cycle just cleaned. Returns residual soil seen.

        Deliberately NOT a fresh spawn: it renders the live model, so the geoms it looks
        for are the same ones the wipe hid. And it reuses v5_triage's own `face_regions`
        and `image_features` rather than a second implementation, so the verifier and the
        grader cannot drift apart.

        WHAT IT CANNOT SEE, AND THIS IS THE V5-D RESULT: the station camera sits at
        z = 0.400 and the device's top face is at z = 0.450, so the camera is BELOW that
        plane -- cos(top normal, view) = +0.076 -- and `face_regions` returns the four
        VERTICAL faces only. The cleaning station wipes five faces and counts all five in
        its coverage number. So soil left on the TOP is structurally invisible here. That
        is reported per unit rather than hidden, and the sabotage test measures it.
        """
        m, d, cfg = self.m, self.d, self.cfg
        self._sync_triage_globals()
        if self.rend is None:
            self.rend = mujoco.Renderer(m, TR.CFG.cam_h, TR.CFG.cam_w)
        tt = m.jnt_qposadr[m.joint("tt_rot").id]
        # park the arm clear of frame -- v5_check_spec asserts this pose is 0.000% of the
        # inspect view, against 4.28% at the home pose
        d.qpos[self.qadr] = TR.PARK
        best = {}
        for deg in TR.CFG.index_deg:
            d.qpos[tt] = np.deg2rad(deg)
            mujoco.mj_forward(m, d)
            self.rend.update_scene(d, camera=TR.CFG.cam)
            rgb = self.rend.render()
            # grade each face ONCE, in the index position where it is most face-on --
            # the same rule triage uses, so a face seen twice is not counted twice
            for fid, cosang, roi in TR.face_regions(m, d, TR.CFG, deg):
                if fid in best and best[fid][0] <= cosang:
                    continue
                f = TR.image_features(rgb, roi, TR.CFG)
                if f is not None:
                    best[fid] = (cosang, f)
        # --- THE TOP FACE, from its own camera. Without this the check is blind exactly
        #     where the cleaning fails: the first falsification run caught 10/10 sabotaged
        #     units and still let 9 of 10 honestly-cleaned-but-dirty units pass, because
        #     100% of the residue sat on the one face `inspect` cannot see.
        top_f = None
        if self.rend_top is None:
            self.rend_top = mujoco.Renderer(m, TR.CFG.cam_h, TR.CFG.cam_w)
        d.qpos[tt] = 0.0
        mujoco.mj_forward(m, d)
        self.rend_top.update_scene(d, camera="verify_top")
        rgb = self.rend_top.render()
        roi = self.top_region()
        if roi is not None:
            top_f = TR.image_features(rgb, roi, TR.CFG)

        seen = sum(f["soil"] for _, f in best.values())
        seen_top = int(top_f["soil"]) if top_f else 0
        seen += seen_top
        left = [g for g in self.revealed_soil if m.geom_rgba[g][3] > 0]
        hidden_top = sum(1 for g in left if self.soil_face(g) == "top")
        return {"soil_seen": int(seen), "soil_seen_top": seen_top,
                "faces_graded": len(best) + (1 if top_f else 0),
                "top_graded": bool(top_f is not None),
                "soil_left_truth": len(left), "soil_left_top": int(hidden_top),
                "verified": bool(seen <= cfg.verify_soil_max)}

    def top_region(self):
        """Search region for the TOP face, projected from the verify_top camera.

        Same projection and same hull-mask format as v5_triage.face_regions, deliberately,
        so image_features can be reused unchanged -- one feature extractor for every face
        of both stations. Built here rather than inside face_regions because V5-B's triage
        result is frozen at 97.5% and must not move: the triage station grades the four
        vertical faces from `inspect`, and this is the CLEANING station's extra eye.
        """
        m, d = self.m, self.d
        cam = m.camera("verify_top").id
        p = d.cam_xpos[cam]
        R = d.cam_xmat[cam].reshape(3, 3)
        f = (TR.CFG.cam_h / 2) / np.tan(np.deg2rad(m.cam_fovy[cam]) / 2)
        cg = m.geom("cab_body").id
        cx, cy = float(d.geom_xpos[cg][0]), float(d.geom_xpos[cg][1])
        hd, hw = float(m.geom_size[cg][0]), float(m.geom_size[cg][1])
        z = TR.CAB_TOP
        ins = TR.CFG.face_inset
        quad = [(cx - hd + ins, cy - hw + ins), (cx + hd - ins, cy - hw + ins),
                (cx + hd - ins, cy + hw - ins), (cx - hd + ins, cy + hw - ins)]
        uv = []
        for X in [np.array([qx, qy, z]) for qx, qy in quad]:
            q = R.T @ (X - p)
            depth = -q[2]
            if depth < 1e-3:
                return None
            uv.append((TR.CFG.cam_w / 2 + f * q[0] / depth,
                       TR.CFG.cam_h / 2 - f * q[1] / depth))
        uv = np.array(uv)
        u0 = max(0, int(uv[:, 0].min()) - 2)
        u1 = min(TR.CFG.cam_w, int(uv[:, 0].max()) + 2)
        v0 = max(0, int(uv[:, 1].min()) - 2)
        v1 = min(TR.CFG.cam_h, int(uv[:, 1].max()) + 2)
        if u1 - u0 < 40 or v1 - v0 < 40:
            return None
        H = TR._hull(uv)
        gy, gx = np.mgrid[v0:v1, u0:u1]
        inside = np.ones(gx.shape, bool)
        for i in range(len(H)):
            a, b = H[i], H[(i + 1) % len(H)]
            inside &= ((b[0] - a[0]) * (gy - a[1])
                       - (b[1] - a[1]) * (gx - a[0])) >= 0
        return (v0, v1, u0, u1, inside)

    def wipe(self):
        """Hide soil geoms the pad's contact patch has passed over.

        Removal requires ACTUAL CONTACT, not proximity: if the pad is not pressing, it
        cleans nothing. That is what makes the coverage number a statement about the
        motion rather than about the trajectory we happened to command.
        """
        f = self.pad_contact_force()
        if f < self.cfg.contact_min_n:
            return 0
        if self.sabotage:
            return 0                # V5-D: contact happened, removal deliberately withheld
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

    # ------------------------------------------------------------- planning
    def plan_pose(self, tgt, base_mat, q_seed=None):
        """Smallest-tilt joint solution that is reachable, limit-clear and NOT colliding.

        WHY THIS EXISTS. The cleaner used to servo straight at a Cartesian target with a
        resolved-rate step and no notion of collision. Measured consequence: link1 jammed
        against link6 at 130-271 N with joint 4 pinned at its 30 Nm limit, and every
        setup waypoint missed by 100-400 mm -- the whole raster then ran from the wrong
        place. A local Jacobian step cannot climb out of a self-collision basin because
        nothing in it knows the basin is there. Solve first, reject the bad branches,
        then drive to a configuration already known to be good.

        Returns (q, mat, tilt_deg) or None.
        """
        for mat, tilt in tilted_mats(base_mat):
            q = self.solve_at(tgt, mat, q_seed)
            if q is not None:
                return q, mat, tilt
        return None

    def plan_pad(self, pad_pt, base_mat, pad_rel, q_seed=None):
        """Same, but for a raster point where PAD_PT is what must be hit, not the TCP.

        The tilt loop has to live out here: the pad hangs 105 mm off the wrist, so
        tilting the tool SWINGS THE TARGET. Solving a fixed TCP target and then tilting
        would land the pad somewhere else on the face -- which is the whole reason the
        tool's length matters to this station in the first place.
        """
        for mat, tilt in tilted_mats(base_mat):
            tgt = pad_pt - mat @ pad_rel
            q = self.solve_at(tgt, mat, q_seed)
            if q is not None:
                return q, mat, tilt, tgt
        return None

    def _carry_tool(self):
        """Put the welded tool where the arm would actually carry it, in the PLAN copy.

        The padtool is a free body held by an equality, so moving arm joints in a copy of
        the state leaves it behind -- its pose there is whatever the live sim last had.
        The first version of the planner therefore EXCLUDED the tool from its collision
        test, which made it blind to the one part of the machine that touches anything:
        it planned bottom-row poses whose 60 mm pad reached below the platter (measured
        pad z down to 1 mm against a platter top of 10 mm, with tt_disc and bench in the
        contact list), and top-face poses the pad could not physically reach. Result:
        0 of 48 top points and only 40% of front-face points ever arrived -- each one
        pressing at full command for the whole 2.5 s timeout, which is where the 326 N
        peak and the 74.8% in-band came from.

        Reconstructing the weld transform is exact and costs one quaternion multiply.
        The flange is set to its FREE extension, which is the conservative end: that is
        the longest the tool can be, so anything that clears here clears in practice.
        """
        if self.tool_rel is None:
            return
        relpos, relq = self.tool_rel
        mujoco.mj_kinematics(self.m, self.plan)
        p1 = self.plan.xpos[self.gb]
        R1 = self.plan.xmat[self.gb].reshape(3, 3)
        q1 = np.zeros(4)
        mujoco.mju_mat2Quat(q1, R1.flatten())
        qt = np.zeros(4)
        mujoco.mju_mulQuat(qt, q1, relq)
        self.plan.qpos[self.pad_jq:self.pad_jq + 3] = p1 + R1 @ relpos
        self.plan.qpos[self.pad_jq + 3:self.pad_jq + 7] = qt
        self.plan.qpos[self.acf_q] = self.m.jnt_range[self.m.joint("acf").id][0]

    def solve_at(self, tgt, mat, q_seed=None):
        """One pose, one orientation: reachable AND limit-clear AND collision-free."""
        m = self.m
        lo, hi = self.rng_j[:, 0], self.rng_j[:, 1]
        seeds = [q_seed, COLD] if q_seed is not None else [COLD]
        for q0 in seeds:
            q = np.array(q0, float)
            for _ in range(PLAN_ITERS):
                self.plan.qpos[:] = self.d.qpos
                self.plan.qpos[self.qadr] = q
                mujoco.mj_kinematics(m, self.plan)
                mujoco.mj_comPos(m, self.plan)
                dq, _ = ik_step(m, self.plan, self.site, tgt, mat, self.dof,
                                damping=0.08, gain=0.55)
                step = np.max(np.abs(dq))
                if step > 0.12:
                    dq = dq * (0.12 / step)
                q = np.clip(q + dq, lo, hi)
                if step < 1e-5:
                    break
            self.plan.qpos[:] = self.d.qpos
            self.plan.qpos[self.qadr] = q
            self._carry_tool()
            mujoco.mj_forward(m, self.plan)
            if np.linalg.norm(tgt - self.plan.site_xpos[self.site]) > POS_TOL:
                continue
            R = self.plan.site_xmat[self.site].reshape(3, 3)
            quat, rv = np.zeros(4), np.zeros(3)
            mujoco.mju_mat2Quat(quat, (mat @ R.T).flatten())
            mujoco.mju_quat2Vel(rv, quat, 1.0)
            if np.linalg.norm(rv) > ROT_TOL:
                continue
            if np.min(np.minimum(q - lo, hi - q)) < np.deg2rad(1.0):
                continue
            # THE ARM may touch nothing. THE PAD may touch the device and nothing else --
            # pad-on-device IS the motion, pad-on-platter is the bug that made the
            # bottom rows stall. Anything else (bench, platter, riser, backdrop, post) is
            # a rejection for either.
            hit = False
            for k in range(self.plan.ncon):
                g1, g2 = self.plan.contact[k].geom1, self.plan.contact[k].geom2
                tool = (g1 in self.tool_geoms) or (g2 in self.tool_geoms)
                arm = (g1 in self.arm_geoms) or (g2 in self.arm_geoms)
                if tool and not arm:
                    other = g2 if g1 in self.tool_geoms else g1
                    if self.m.geom_bodyid[other] == self.cab_bodyid:
                        continue                 # the wipe itself
                    hit = True
                    break
                if arm:
                    hit = True
                    break
            if hit:
                continue
            return q
        return None

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

    def move_planned(self, q_goal, tgt, grip, index_deg=0.0, tol=0.004, t_max=6.0,
                     wipe=False, log=None, frames=None, tag=""):
        """Drive to a PLANNED joint configuration, waiting for the MEASURED TCP.

        The setpoint is the planner's configuration, so the arm is not re-deriving a
        branch every control step and cannot wander into one the planner already
        rejected. Completion is still judged on the measured TCP -- the commanded
        configuration says nothing about whether the arm got there, which is exactly the
        distinction that took four bugs to untangle.
        """
        m, d = self.m, self.d
        t, cleaned, settle = 0.0, 0, 0.0
        stall_t, stall_err = 0.0, np.inf
        while t < t_max:
            dq = q_goal - self.q_des
            mx = np.max(np.abs(dq))
            lim = 0.02 * self.cfg.speed
            if mx > lim:
                dq = dq * (lim / mx)
            self.q_des = np.clip(self.q_des + dq, self.rng_j[:, 0], self.rng_j[:, 1])
            d.ctrl[self.act] = self.q_des
            d.ctrl[self.grip] = grip
            d.ctrl[self.tt_act] = np.deg2rad(index_deg)
            d.qfrc_applied[self.dof] = d.qfrc_bias[self.dof]
            mujoco.mj_step(m, d)
            t += self.dt
            if wipe:
                cleaned += self.wipe()
                f = self.pad_contact_force()
                if log is not None:
                    log.append(f)
                stall_t += self.dt
                if stall_t >= self.cfg.wipe_stall_s:
                    e = float(np.linalg.norm(d.site_xpos[self.site] - tgt))
                    if f >= self.cfg.wipe_seat_n and \
                            stall_err - e < self.cfg.wipe_stall_m:
                        break
                    stall_err, stall_t = e, 0.0
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    int(t / self.dt) % frames["every"] == 0:
                frames["cb"](tag)
            if float(np.linalg.norm(d.site_xpos[self.site] - tgt)) < tol:
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

        RAYS ONLY THE CABINET'S OWN GEOMS, one at a time, and takes the nearest hit.
        The scene-wide `mj_ray` returns the FIRST geom along the beam, and the beam starts
        at x = 0.20 and travels +X -- straight through the space the arm and the pad
        occupy while wiping. Whenever a link was in the way the hit belonged to the arm,
        this returned None, and the raster loop silently `continue`d: no wipe, no force
        sample, no entry in the contact statistics. Measured on seed 800: 154 of 450
        raster points skipped (34.2%), the beam landing on xarm_gripper_base_link x61,
        link7 x33, link4 x26 and the pad itself x14. Because skipped points log nothing,
        the reported "contact during raster" was a fraction of the points that RAN --
        74.4% where the true figure over the planned raster was about 49%.

        Per-geom rays cannot be occluded by anything that is not the device, so the
        answer no longer depends on where the arm happens to be standing.
        """
        pnt = np.array([0.20, y, z])
        vec = np.array([1.0, 0.0, 0.0])
        best = -1.0
        for g in self.cab_geoms:
            d = mujoco.mju_rayGeom(self.d.geom_xpos[g], self.d.geom_xmat[g],
                                   self.m.geom_size[g], pnt, vec,
                                   int(self.m.geom_type[g]))
            if d >= 0 and (best < 0 or d < best):
                best = d
        if best < 0:
            return None
        return float(pnt[0] + best)

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
            pl = self.plan_pose(safe, tool_mat_face(deg), self.q_des)
            if pl is not None:
                self.move_planned(pl[0], safe, cfg.grip_open, index_deg=prev_deg,
                                  tol=0.006, t_max=8.0, tag="SAFE", frames=frames)
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
            pl = self.plan_pose(approach, tm, self.q_des)
            if pl is None:
                self.face_unreachable[deg] = "approach"
                continue
            q_ap, mat_ap, _ = pl
            self.move_planned(q_ap, approach, cfg.grip_open, index_deg=deg,
                              tol=0.006, t_max=10.0, tag="TO FACE", frames=frames)
            self.dwell(0.3, mat_ap, approach, cfg.grip_open, index_deg=deg,
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
                    # COUNT what gets skipped. A `continue` here used to be invisible:
                    # the point contributed no wipe and no force sample, so a raster that
                    # never ran a third of its points still reported healthy contact.
                    # Anything the station declines to attempt has to show up in the
                    # numbers, or the metric is measuring the subset that succeeded.
                    self.raster_planned += 1
                    hit = self.surface_x(cy + u, zc + v)
                    if hit is None:
                        self.raster_skipped += 1
                        continue
                    pad_pt = np.array([hit - cfg.pad_thick_half + cfg.press,
                                       cy + u, zc + v])
                    # PLAN the point before driving at it, and let it TILT. The target
                    # moves with the tilt, because the pad is offset from the wrist: the
                    # pad face has to land on pad_pt whatever angle the tool arrives at.
                    warm = self.q_warm if self.q_warm is not None else self.q_des
                    got = self.plan_pad(pad_pt, tm, pad_rel, warm)
                    if got is None:
                        self.raster_infeasible += 1
                        continue
                    q_pt, mat_pt, tilt_pt, tgt = got
                    self.q_warm = q_pt
                    self.tilts.append(tilt_pt)
                    cleaned += self.move_planned(q_pt, tgt, cfg.grip_open, index_deg=deg,
                                                 tol=cfg.wipe_tol, t_max=2.5, wipe=True,
                                                 log=forces, tag=f"WIPE {deg:.0f}",
                                                 frames=frames)
            retract = np.array([fx - cfg.standoff - 0.05, cy, zc]) - tm @ pad_rel
            pl = self.plan_pose(retract, tm, self.q_des)
            if pl is not None:
                self.move_planned(pl[0], retract, cfg.grip_open, index_deg=deg,
                                  tol=0.006, t_max=8.0, tag="RETRACT", frames=frames)
            if verbose:
                on_face = sum(1 for g in self.revealed_soil
                              if self.m.geom_rgba[g][3] > 0)
                print(f"    face {deg:>5.0f} deg: {rows}x{cols} raster, "
                      f"pad_rel {np.round(pad_rel,4)}, fx={fx:.4f}, "
                      f"cleaned so far {n0 - on_face}/{n0}")

        pl = self.plan_pose(safe, tool_mat_face(0.0), self.q_des)
        if pl is not None:
            self.move_planned(pl[0], safe, cfg.grip_open, index_deg=prev_deg,
                              tol=0.006, t_max=8.0, tag="SAFE", frames=frames)

        # --- the TOP face. Stage 3 names the top cover explicitly, and the vertical
        #     loop above never touches it -- soil there would have been permanently
        #     uncleanable while the coverage number quietly ignored it.
        #
        # INDEX FORWARD TO 360, NOT BACK TO 0. The top raster spans the cabinet's LOCAL
        # half-extents (180 x 250 mm) along world X and Y, so it is only correct with the
        # device square-on. It used to get there by accident: every top-pass move left
        # index_deg at its 0.0 default, so the indexer was commanded to unwind 270 deg
        # WHILE the arm was already travelling over the device -- the exact sequencing
        # error the vertical loop documents above. 360 deg keeps every step of the cycle
        # a +90 deg move in one direction, which is also how a real indexer is driven.
        top_deg = 360.0
        self.dwell(1.4, tool_mat_face(0.0), safe, cfg.grip_open, index_deg=top_deg,
                   frames=frames, tag=f"INDEX {top_deg:.0f}")
        tmt = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]]).T
        cg = self.m.geom("cab_body").id
        cx, cyy = self.d.geom_xpos[cg][0], self.d.geom_xpos[cg][1]
        _, _, _, _, ztop = self.front_face_plane(top_deg)
        appr = np.array([cx, cyy, ztop + 0.10])
        pl = self.plan_pose(appr, tmt, self.q_des)
        if pl is not None:
            self.move_planned(pl[0], appr, cfg.grip_open, index_deg=top_deg,
                              tol=0.006, t_max=10.0, tag="TO TOP", frames=frames)
        self.dwell(0.3, tmt, appr, cfg.grip_open, index_deg=top_deg,
                   frames=frames, tag="SETTLE")
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
                self.raster_planned += 1
                warm = self.q_warm if self.q_warm is not None else self.q_des
                got = self.plan_pad(pad_pt, tmt, prel, warm)
                if got is None:
                    self.raster_infeasible += 1
                    continue
                q_pt, mat_pt, tilt_pt, tgt = got
                self.q_warm = q_pt
                self.tilts.append(tilt_pt)
                cleaned += self.move_planned(q_pt, tgt, cfg.grip_open,
                                             index_deg=top_deg, tol=cfg.wipe_tol,
                                             t_max=2.5, wipe=True, log=forces,
                                             tag="WIPE top", frames=frames)
        clear = np.array([cx, cyy, ztop + 0.12])
        pl = self.plan_pose(clear, tmt, self.q_des)
        if pl is not None:
            self.move_planned(pl[0], clear, cfg.grip_open, index_deg=top_deg,
                              tol=0.006, t_max=8.0, tag="TOP CLEAR", frames=frames)

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
        # HOLD the indexer where the job left it for the tool return. Letting index_deg
        # fall back to its 0.0 default here commands a 360 deg unwind while the arm is
        # crossing the cell to the holder -- same class of sequencing error as the top
        # pass, and free to avoid.
        self.move(want + np.array([0, 0, 0.14]), gm, cfg.grip_open, index_deg=top_deg,
                  t_max=12.0, tag="RETURN", frames=frames)
        self.move(want, gm, cfg.grip_open, index_deg=top_deg, tol=0.004, t_max=8.0,
                  tag="PLACE", frames=frames)
        self.decouple()
        self.dwell(0.3, gm, want, cfg.grip_open, index_deg=top_deg,
                   frames=frames, tag="UNLATCH")
        self.move(want + np.array([0, 0, 0.14]), gm, cfg.grip_open, index_deg=top_deg,
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
                "contact_frac": float((f >= cfg.contact_min_n).mean()),
                "raster_planned": self.raster_planned,
                "raster_skipped": self.raster_skipped,
                "raster_infeasible": self.raster_infeasible,
                "tilt_mean": float(np.mean(self.tilts)) if self.tilts else 0.0,
                "tilt_max": float(np.max(self.tilts)) if self.tilts else 0.0,
                "tilt_zero_frac": float(np.mean([t == 0.0 for t in self.tilts]))
                                  if self.tilts else 0.0}


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
          f"(our pad curve is monotonic to 60 N -- a MODEL-validity limit, not a rating)")
    rp = sum(r.get("raster_planned", 0) for r in ok)
    rs = sum(r.get("raster_skipped", 0) for r in ok)
    # Contact is reported over the PLANNED raster, not the executed subset. Skipped
    # points log no force sample, so averaging only what ran quietly excused every point
    # the station declined to attempt.
    cf_planned = cf.mean() * (1 - rs / max(rp, 1))
    print(f"  in force band   : {ib.mean()*100:.1f}%   contact during raster: "
          f"{cf.mean()*100:.1f}% of points RUN, {cf_planned*100:.1f}% of points PLANNED")
    ri = sum(r.get("raster_infeasible", 0) for r in ok)
    print(f"  raster skipped  : {rs} probe-miss + {ri} no-feasible-pose of {rp} "
          f"planned points ({(rs+ri)/max(rp,1)*100:.1f}%)")
    tz = np.array([r.get("tilt_zero_frac", 0.0) for r in ok]) if ok else np.array([0.0])
    tm_ = np.array([r.get("tilt_mean", 0.0) for r in ok]) if ok else np.array([0.0])
    tx = np.array([r.get("tilt_max", 0.0) for r in ok]) if ok else np.array([0.0])
    print(f"  press angle     : {tz.mean()*100:.1f}% at exact normal, mean tilt "
          f"{tm_.mean():.1f} deg, max {tx.max():.0f} deg (cone limit "
          f"{max(TILT_TOL_DEG):.0f} deg)")
    cd = np.array([r.get("coupling_drift_mm", 0.0) for r in ok]) if ok else np.array([0.0])
    print(f"  coupling drift  : {cd.mean():.2f} mm mean, {cd.max():.2f} mm worst "
          f"(tool changer; the flange stroke is separate and expected)")
    print("\n  Coverage is of ALL FIVE faces -- the back panel carries soil too, since the")
    print("  indexer reaches it. No fluid or chemistry is simulated: what is verified is")
    print("  that the soil the camera could see is gone.")
    print("\n  THE TRAJECTORY IS OPEN-LOOP AND SEED-INDEPENDENT. The raster, the planned")
    print("  poses and the contact are identical for every unit; the seed only moves the")
    print("  soil. So force, tilt and raster figures above have NO seed variance -- they")
    print("  are effectively n = 1 and must not be quoted as an n-unit spread. Only the")
    print("  coverage and missed-spot figures actually vary across units.")
    return {"n": n, "picked": len(ok), "coverage_mean": float(cov.mean()),
            "coverage_worst": float(cov.min()), "missed": int(totm), "soil": int(tot0),
            "f_max": float(fx.max()), "in_band": float(ib.mean()),
            "contact_run": float(cf.mean()), "contact_planned": float(cf_planned),
            "raster_planned": int(rp), "raster_skipped": int(rs),
            "raster_infeasible": int(ri), "tilt_mean_deg": float(tm_.mean()),
            "tilt_max_deg": float(tx.max()),
            "exact_normal_frac": float(tz.mean())}


def falsify(n, seed0):
    """V5-D: the same unit cleaned honestly and cleaned NOT AT ALL, verified both ways.

    PAIRED, deliberately. Each seed is run twice -- once with the wipe working and once
    with removal withheld -- so the two arms differ in exactly one thing. An unpaired test
    can be passed by a verifier that is merely lucky about which units it saw.

    The exit criterion from V5_PLAN is n/n both ways: every honest cleaning verified, every
    sabotaged cleaning caught. Anything less means the check cannot fail, and a check that
    cannot fail is not evidence.
    """
    rows = []
    for k in range(n):
        seed = seed0 + k
        rec = {"seed": seed}
        for sab in (False, True):
            c = Cell()
            c.sabotage = sab
            r = c.run(seed)
            v = c.verify()
            tag = "sab" if sab else "hon"
            rec[f"{tag}_cov"] = r["coverage"]
            rec[f"{tag}_seen"] = v["soil_seen"]
            rec[f"{tag}_left"] = v["soil_left_truth"]
            rec[f"{tag}_top"] = v["soil_left_top"]
            rec[f"{tag}_pass"] = v["verified"]
        rows.append(rec)
        # print the honest side's RESIDUE too. A unit can be verified while still
        # carrying soil -- that is a FALSE VERIFY, and it is the error this station's
        # customer would care about most. Hiding it behind "seen 0" would repeat exactly
        # the mistake v4's sabotage test was built to catch.
        rec["hon_false"] = bool(rec["hon_pass"] and rec["hon_left"] > 0)
        print(f"  seed {seed}: honest cov {rec['hon_cov']*100:5.1f}% "
              f"left {rec['hon_left']:2d} (top {rec['hon_top']:2d}) seen {rec['hon_seen']:2d}"
              f" -> {'VERIFIED' if rec['hon_pass'] else 'failed'}"
              f"{' **FALSE VERIFY**' if rec['hon_false'] else ''}"
              f" | sabotaged left {rec['sab_left']:2d} (top {rec['sab_top']:2d}) "
              f"seen {rec['sab_seen']:2d} -> {'ESCAPED' if rec['sab_pass'] else 'caught'}")

    hon_ok = sum(r["hon_pass"] for r in rows)
    false_verify = sum(r["hon_false"] for r in rows)
    hon_left_tot = sum(r["hon_left"] for r in rows)
    hon_top_tot = sum(r["hon_top"] for r in rows)
    sab_caught = sum(not r["sab_pass"] for r in rows)
    # the sharp question: could a filthy unit pass because all its residue is on the face
    # the camera cannot see?
    blind = [r for r in rows if r["sab_left"] > 0 and r["sab_left"] == r["sab_top"]]
    top_left = sum(r["sab_top"] for r in rows)
    all_left = sum(r["sab_left"] for r in rows)

    print(f"\nV5-D FALSIFICATION: {n} units, each run twice")
    print(f"  honest cleanings VERIFIED   : {hon_ok}/{n}")
    print(f"  FALSE VERIFIES              : {false_verify}/{n}   <- passed while still "
          f"carrying soil ({hon_left_tot} patches left, {hon_top_tot} of them on the "
          f"unseeable top face)")
    print(f"  sabotaged cleanings CAUGHT  : {sab_caught}/{n}   <- the one that matters")
    print(f"  residue on the TOP face     : {top_left} of {all_left} patches "
          f"({top_left/max(all_left,1)*100:.1f}%) -- the face V5-C cleans worst")
    print(f"  units that could ESCAPE      : {len(blind)}/{n} "
          f"(all residue on one face)")
    print("\n  WHY THERE ARE TWO CAMERAS. The triage camera sits at z = 0.400 and the")
    print("  device top face at z = 0.450 -- below the plane of that face, so it can never")
    print("  see the top, and `face_regions` returns the four VERTICAL faces only. V5-C")
    print("  wipes five faces and counts five. Verified through that camera alone, this")
    print("  test scored a perfect 10/10 sabotage-caught while letting 9 of 10 honestly-")
    print("  cleaned-but-still-dirty units PASS, because the face cleaning misses and the")
    print("  face the camera cannot see are the SAME face. `verify_top` was added for that")
    print("  reason and is a hardware requirement, not a rendering convenience.")
    print("\n  A CHECK THAT CANNOT FAIL IS NOT EVIDENCE -- and n/n on the sabotage arm")
    print("  alone would have been exactly that. Read the FALSE VERIFY line first.")
    st = {"n": n, "honest_verified": hon_ok, "false_verify": false_verify,
          "honest_residual": hon_left_tot, "honest_residual_on_top": hon_top_tot,
          "sabotage_caught": sab_caught,
          "residual_total": all_left, "residual_on_top": top_left,
          "would_escape": len(blind), "rows": rows}
    with open("stats_v5_verify.json", "w") as f:
        json.dump(st, f, indent=2)
    print("\nwrote stats_v5_verify.json")
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int)
    ap.add_argument("--eval", type=int)
    ap.add_argument("--sabotage", type=int,
                    help="V5-D paired falsification test: N units, honest and sabotaged")
    # 900, not 800: a bare --eval should reproduce the PUBLISHED number, not a seed range
    # the ledger records as spent on development. 800-807 were used to diagnose against
    # the old 64.7%, so defaulting there quietly reproduced a development figure.
    ap.add_argument("--seed0", type=int, default=900)
    a = ap.parse_args()
    if a.sabotage:
        falsify(a.sabotage, a.seed0)
    elif a.run is not None:
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
