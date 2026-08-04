"""V5-0 -- reachability and scale study for the unit-scale cell.

THE QUESTION THIS ANSWERS, BEFORE ANY v5 CODE IS WRITTEN:
v4 manipulates a 110 mm cartridge. v5 has to work on a whole device -- orbit a wrist
camera around it for Stage-1 triage, and raster a pad across its faces for the Stage-2/3
cleaning pass. Those are unit-scale motions with a horizontal tool axis, which is a
posture nothing in v2/v3/v4 ever asked the arm for. If the xArm7 cannot do it from this
base position, every other v5 phase is built on sand.

WHY IT IS A SWEEP AND NOT A YES/NO:
We do not have DrinkPrime's cabinet dimensions (open ask -- docs/drinkprime/README.md).
Picking one plausible size and reporting "it works" would be a number with no meaning the
moment the real dimensions arrive. So this sweeps size and placement and reports an
ENVELOPE: which cabinets this cell can serve. That converts an unknown into a spec we can
check the instant the founder answers -- the same move that made the +-2.5 mm domain
randomization result useful in v4.

WHAT IT DOES NOT DO:
Kinematics only. No dynamics, no contact forces, no controller. A pose that is reachable
here can still fail under contact -- that is V5-C's problem, not this one. This is a
necessary condition, not a sufficient one, and the report says so.

CLI:
    python v5_reach.py --nominal          detailed report for one cabinet
    python v5_reach.py --sweep            size + placement envelope  (writes reach_v5.json)
    python v5_reach.py --nominal --w 0.30 --h 0.50 --d 0.20 --x 0.46
"""
import argparse
import json
import sys

import numpy as np
import mujoco

from sim_poc2 import ik_step

XML = "ufactory_xarm7/cabinet_probe_v5.xml"

# --- tolerances. Deliberately tighter than the cell needs, so that "reachable" here
#     leaves headroom for the controller to be imperfect later.
POS_TOL = 0.004          # m   -- 4 mm, well inside the +-2.5 mm cell-calibration envelope
ROT_TOL = np.deg2rad(4)  # rad
IK_ITERS = 220

# --- task geometry
# m, tcp to the face during a cleaning raster (pad sits in between).
# 105, NOT 45. The 45 mm was a GUESS made before the wiping tool existed, and it sized the
# whole cell: V5-C then found the built tool is 105 mm wrist-to-pad, and those 60 mm come
# off the wrist's X -- pushing it toward its own base, the one direction a 7-DoF arm cannot
# go. V5-C fix 5 imported the tilt cone from this module so "gate and consumer cannot
# drift", but left THIS number un-unified, so the gate went on planning a 45 mm tool for a
# 105 mm cell. Correcting it does not change the PASS verdict (every face is still 100%
# inside the 30 deg cone) but it roughly halves every STRICT figure -- front 83.3 -> 47.9%,
# sides 27.1 -> 14.6%, top 62.5 -> 29.2%. Those are the honest exact-normal numbers.
PAD_STANDOFF = 0.105
ORBIT_AZIMUTHS = 12
ORBIT_ELEV_DEG = 18.0    # look slightly down at the device
FRAME_MARGIN = 1.18      # frame the device with 18% slack around it

# A wiping pad does NOT need its axis exactly normal to the surface -- a compliant pad
# conforms over a good 20-30 deg. The first version of this study demanded an exact
# normal press and reported 10% coverage on the front face; that number was measuring an
# over-constrained test, not the cell. We search a small tilt cone and report BOTH the
# strict (exact-normal) and relaxed (within-cone) coverage, so the relaxation is visible
# rather than buried.
TILT_TOL_DEG = (0.0, 10.0, 20.0, 30.0)
TILT_DIRS = 6            # azimuths around the normal, per nonzero tilt ring

FACES = {
    #  name  : (outward normal, "is this face reachable at all by design")
    "front": np.array([-1.0, 0.0, 0.0]),   # faces the arm base
    "top":   np.array([0.0, 0.0, 1.0]),
    "left":  np.array([0.0, -1.0, 0.0]),
    "right": np.array([0.0, 1.0, 0.0]),
    "back":  np.array([1.0, 0.0, 0.0]),    # expected worst case: arm must reach over
}


# ============================================================ model plumbing
def load(xml=XML):
    model = mujoco.MjModel.from_xml_path(xml)
    data = mujoco.MjData(model)
    ids = {}
    ids["site_tcp"] = model.site("link_tcp").id
    ids["cam_wrist"] = model.camera("wrist").id
    # the probe scene calls it "cab"; the real v5 scene calls it "cab_body"
    for gn in ("cab", "cab_body"):
        try:
            ids["cab_geom"] = model.geom(gn).id
            break
        except KeyError:
            continue
    ids["cab_body"] = model.body("cabinet").id

    # the 7 arm joints, in order
    jnt = [model.joint(f"joint{i}").id for i in range(1, 8)]
    ids["jnt"] = jnt
    ids["dof"] = np.array([model.jnt_dofadr[j] for j in jnt])
    ids["qpos"] = np.array([model.jnt_qposadr[j] for j in jnt])
    ids["range"] = model.jnt_range[jnt].copy()

    # every geom belonging to the arm chain, for collision filtering
    base = model.body("link_base").id
    arm_bodies = set()
    for b in range(model.nbody):
        p = b
        while p != 0:
            if p == base:
                arm_bodies.add(b)
                break
            p = model.body_parentid[p]
    ids["arm_geoms"] = {g for g in range(model.ngeom)
                        if model.geom_bodyid[g] in arm_bodies}
    return model, data, ids


def _set_cabinet(model, ids, width, depth, height, x, y=0.0):
    """Resize/reposition the cabinet. Keeps the box standing ON the bench (z=0).

    AXIS CONVENTION -- fixed explicitly because getting it wrong is not visible in the
    numbers. The first version of this file set geom_size to (width/2, depth/2, ...),
    i.e. width along X, while raster_test placed the front face at +/- depth/2 along X.
    With 250 x 180 mm that put every front/back raster target 35 mm INSIDE the box and
    every left/right target 35 mm outside it, so five of six face-coverage numbers were
    measuring nothing real. Only `top` was correct.

        depth  -> X extent  (front-to-back; the front face -X points at the arm base)
        width  -> Y extent  (side to side)
        height -> Z extent  (standing on the bench at z = 0)
    """
    g = ids["cab_geom"]
    model.geom_size[g] = [depth / 2, width / 2, height / 2]
    model.geom_pos[g] = [0, 0, height / 2]
    model.body_pos[ids["cab_body"]] = [x, y, 0]
    # facia strip sits on the FRONT (-X) face so renders match the raster convention
    fg = model.geom("cab_facia").id
    model.geom_size[fg] = [0.004, width / 2, min(0.03, height / 6)]
    model.geom_pos[fg] = [-(depth / 2 + 0.004), 0, min(0.06, height / 5)]
    return np.array([x, y, height / 2])        # cabinet centre, world


def cam_to_tcp_transform(model, data, ids):
    """Measure the RIGID camera->tcp offset from the model instead of deriving it from
    the XML by hand. Both are fixed to link7, so one forward pass at any pose gives the
    exact relationship -- ask MuJoCo, do not theorise (see PAIN_JOURNAL)."""
    mujoco.mj_resetData(model, data)
    data.qpos[ids["qpos"]] = [0.0, -0.3, 0.0, 0.9, 0.0, 1.1, 0.0]
    mujoco.mj_forward(model, data)
    p_cam = data.cam_xpos[ids["cam_wrist"]].copy()
    R_cam = data.cam_xmat[ids["cam_wrist"]].reshape(3, 3).copy()
    p_tcp = data.site_xpos[ids["site_tcp"]].copy()
    R_tcp = data.site_xmat[ids["site_tcp"]].reshape(3, 3).copy()
    R_rel = R_cam.T @ R_tcp
    t_rel = R_cam.T @ (p_tcp - p_cam)
    return R_rel, t_rel


def look_at(eye, target, up_hint=np.array([0.0, 0.0, 1.0])):
    """Rotation whose -Z points from eye at target (MuJoCo camera convention)."""
    f = target - eye
    n = np.linalg.norm(f)
    if n < 1e-9:
        return np.eye(3)
    f = f / n
    z = -f
    x = np.cross(up_hint, z)
    if np.linalg.norm(x) < 1e-6:                 # up parallel to view axis
        x = np.cross(np.array([1.0, 0.0, 0.0]), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.column_stack([x, y, z])


def tool_mat(normal, up_hint=np.array([0.0, 0.0, 1.0])):
    """Tool frame with -Z pressing INTO a face of the given outward normal."""
    z = -np.asarray(normal, float)
    z = z / np.linalg.norm(z)
    x = np.cross(up_hint, z)
    if np.linalg.norm(x) < 1e-6:
        x = np.cross(np.array([1.0, 0.0, 0.0]), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.column_stack([x, y, z])


# ============================================================ feasibility test
def solve(model, data, ids, tgt_pos, tgt_mat, q_seed):
    """IK to a full 6-DoF pose. Returns (ok, q, pos_err, rot_err, why)."""
    q = np.array(q_seed, float)
    lo, hi = ids["range"][:, 0], ids["range"][:, 1]
    for _ in range(IK_ITERS):
        data.qpos[ids["qpos"]] = q
        mujoco.mj_kinematics(model, data)
        mujoco.mj_comPos(model, data)
        dq, _ = ik_step(model, data, ids["site_tcp"], tgt_pos, tgt_mat, ids["dof"],
                        damping=0.08, gain=0.55)
        step = np.max(np.abs(dq))
        if step > 0.12:
            dq = dq * (0.12 / step)
        q = np.clip(q + dq, lo, hi)
        if step < 1e-5:
            break

    data.qpos[ids["qpos"]] = q
    mujoco.mj_forward(model, data)
    p = data.site_xpos[ids["site_tcp"]]
    R = data.site_xmat[ids["site_tcp"]].reshape(3, 3)
    pos_err = float(np.linalg.norm(tgt_pos - p))
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, (tgt_mat @ R.T).flatten())
    rv = np.zeros(3)
    mujoco.mju_quat2Vel(rv, quat, 1.0)
    rot_err = float(np.linalg.norm(rv))

    if pos_err > POS_TOL:
        return False, q, pos_err, rot_err, "unreachable"
    if rot_err > ROT_TOL:
        return False, q, pos_err, rot_err, "orientation"
    # joints pinned hard against a limit are a red flag even when the pose converged
    margin = np.minimum(q - lo, hi - q)
    if np.min(margin) < np.deg2rad(1.0):
        return False, q, pos_err, rot_err, "joint_limit"
    for c in range(data.ncon):
        g1, g2 = data.contact[c].geom1, data.contact[c].geom2
        if (g1 in ids["arm_geoms"]) or (g2 in ids["arm_geoms"]):
            return False, q, pos_err, rot_err, "collision"
    return True, q, pos_err, rot_err, "ok"


def in_view(model, data, ids, corners, margin=0.94):
    """Are all cabinet corners inside the wrist camera's frustum, at the solved pose?"""
    p = data.cam_xpos[ids["cam_wrist"]]
    R = data.cam_xmat[ids["cam_wrist"]].reshape(3, 3)
    fovy = np.deg2rad(model.cam_fovy[ids["cam_wrist"]])
    aspect = 640 / 480
    ty = np.tan(fovy / 2) * margin
    tx = ty * aspect
    for X in corners:
        v = R.T @ (X - p)
        depth = -v[2]                       # camera looks along -Z
        if depth < 0.05:
            return False
        if abs(v[1]) / depth > ty or abs(v[0]) / depth > tx:
            return False
    return True


def corners_of(center, width, depth, height):
    cx, cy, _ = center
    return [np.array([cx + ex * depth / 2, cy + ey * width / 2, ez])
            for ex in (-1, 1) for ey in (-1, 1) for ez in (0.001, height - 0.001)]


def fit_standoff(model, ids, width, depth, height):
    """Distance at which the whole device fits in the wrist camera's frame.

    The first version of this study hardcoded 0.42 m + half the device. For a 450 mm box
    at fovy 75 the camera only needs 0.29 m, so that pushed the far side of the orbit to
    x = 1.05 against a measured max planar reach of 0.88 -- the arm was being asked to
    stand back twice as far as the optics require, and 'unreachable' was the answer to
    the wrong question. Derive it instead.
    """
    fovy = np.deg2rad(model.cam_fovy[ids["cam_wrist"]])
    aspect = 640 / 480
    ty, tx = np.tan(fovy / 2), np.tan(fovy / 2) * aspect
    diag_h = np.hypot(width, depth)              # worst-case horizontal extent, any azimuth
    return FRAME_MARGIN * max((height / 2) / ty, (diag_h / 2) / tx) + diag_h / 2


def tilted_mats(normal, up_hint):
    """Tool orientations pressing into a face: exact normal first, then widening cones.

    Yields (matrix, tilt_deg) in increasing order of tilt so the caller can stop at the
    smallest deviation that works and report it.
    """
    base = tool_mat(normal, up_hint)
    for tilt in TILT_TOL_DEG:
        if tilt == 0.0:
            yield base, 0.0
            continue
        t = np.deg2rad(tilt)
        for k in range(TILT_DIRS):
            a = 2 * np.pi * k / TILT_DIRS
            # rotate the tool axis off-normal by `tilt` about an in-plane direction
            axis = np.cos(a) * base[:, 0] + np.sin(a) * base[:, 1]
            quat = np.zeros(4)
            mujoco.mju_axisAngle2Quat(quat, axis, t)
            Rm = np.zeros(9)
            mujoco.mju_quat2Mat(Rm, quat)
            yield Rm.reshape(3, 3) @ base, tilt


# ============================================================ the two tasks
def orbit_test(model, data, ids, center, w, d, h, R_rel, t_rel, n_az=ORBIT_AZIMUTHS):
    """Stage-1 triage: can the wrist camera orbit the device and actually SEE it?

    Note the design decision being tested here -- the arm moves the CAMERA, not the
    part. A cabinet is far too big to present to a fixed camera, and every grip finding
    in this repo came from trying to hold something up to one. No grasp is involved.
    """
    corners = corners_of(center, w, d, h)
    standoff = fit_standoff(model, ids, w, d, h)
    elev = np.deg2rad(ORBIT_ELEV_DEG)
    q = np.array([0.0, -0.3, 0.0, 0.9, 0.0, 1.1, 0.0])
    out = []
    for k in range(n_az):
        th = 2 * np.pi * k / n_az
        eye = center + standoff * np.array([np.cos(th) * np.cos(elev),
                                            np.sin(th) * np.cos(elev),
                                            np.sin(elev)])
        R_cam = look_at(eye, center)
        tgt_pos = eye + R_cam @ t_rel
        tgt_mat = R_cam @ R_rel
        ok, q_sol, pe, re, why = solve(model, data, ids, tgt_pos, tgt_mat, q)
        seen = bool(ok and in_view(model, data, ids, corners))
        if ok:
            q = q_sol
        out.append({"az_deg": round(np.degrees(th), 1), "reach": ok,
                    "in_view": seen, "why": why if not ok else ("framing" if not seen else "ok"),
                    "pos_err_mm": round(pe * 1000, 2)})
    return out, standoff


def view_separation(orbit):
    """Largest angular gap between two framed views.

    This -- not '360 degrees of orbit' -- is what the inspection architecture actually
    needs. v4's classifier gained 6 points from a SECOND view 180 deg opposite the first,
    but it got that for free by spinning the wrist on a part it was holding. A device
    standing on a bench cannot be spun, so the arm can only see the hemisphere it can
    reach round to. The useful question is therefore how far apart the two best views are.
    """
    az = [o["az_deg"] for o in orbit if o["in_view"]]
    if len(az) < 2:
        return 0.0, len(az)
    best = 0.0
    for i in range(len(az)):
        for j in range(i + 1, len(az)):
            sep = abs(az[i] - az[j]) % 360
            best = max(best, min(sep, 360 - sep))
    return round(best, 1), len(az)


COLD = np.array([0.0, -0.3, 0.0, 0.9, 0.0, 1.1, 0.0])   # neutral IK seed
HOPELESS = 0.15          # m -- beyond this the tilt cone cannot rescue a point


def _try_point(model, data, ids, tgt, n, up, q_warm):
    """Try to place the tool on one raster point. Returns ((tilt, q), None) or (None, why).

    TWO CORRECTNESS FIXES over the first version, both found by a real discrepancy --
    the right face read 89.6% on the bare probe scene and 0.0% on the real one:

    1. ORDER-INDEPENDENCE. The old loop warm-started each point from the previous
       success and never fell back. If the FIRST point of a face failed, the warm seed
       never advanced, every later point cold-started into a bad basin, and the WHOLE
       FACE collapsed to 0% -- a result driven by iteration order, not by the robot.
       Now every point tries the warm seed and then the cold seed before giving up.

    2. HONEST FAILURE REASONS. The old loop reported the reason from whichever tilt was
       tried LAST, which was near-meaningless. On the very point that started this, an
       orientation reached the target with 0.0 mm position error and was rejected for
       COLLISION -- but the reported reason was "unreachable", which sent us hunting a
       kinematic problem that did not exist. Now: if any orientation actually reached
       the point, the binding constraint (collision / joint_limit) is what gets
       reported. "unreachable" now means genuinely out of reach.
    """
    seeds = [q_warm] if np.allclose(q_warm, COLD) else [q_warm, COLD]
    reached = None          # a reason where position WAS achieved -- the real blocker
    best_err = np.inf
    for seed in seeds:
        for tgt_mat, tilt in tilted_mats(n, up):
            ok, q_sol, pe, re, why = solve(model, data, ids, tgt, tgt_mat, seed)
            best_err = min(best_err, pe)
            if ok:
                return (tilt, q_sol), None
            if why in ("collision", "joint_limit", "orientation"):
                reached = why
            if tilt == 0.0 and pe > HOPELESS and seed is seeds[-1]:
                return None, "unreachable"     # tilt cone cannot close a 150 mm gap
    return None, (reached or "unreachable")


def raster_test(model, data, ids, center, w, d, h, cols=6, rows=4):
    """Stage-2/3 cleaning: can a pad raster each face?

    Their own acceptance criterion is coverage -- "ensuring all surfaces are covered"
    (Stage 2) and "check for any missed spots" (Stage 3) -- so the metric here is the
    fraction of raster points the arm can actually put the tool on.
    """
    cx, cy, _ = center
    width, depth, height = w, d, h     # depth -> X, width -> Y, height -> Z (see _set_cabinet)
    res = {}
    for name, n in FACES.items():
        # face plane centre + the two in-plane axes spanning it
        if name in ("front", "back"):          # normal along X
            fc = np.array([cx + n[0] * depth / 2, cy, height / 2])
            u, v, su, sv = np.array([0, 1.0, 0]), np.array([0, 0, 1.0]), width, height
        elif name in ("left", "right"):        # normal along Y
            fc = np.array([cx, cy + n[1] * width / 2, height / 2])
            u, v, su, sv = np.array([1.0, 0, 0]), np.array([0, 0, 1.0]), depth, height
        else:                                  # top, normal along Z
            fc = np.array([cx, cy, height])
            u, v, su, sv = np.array([1.0, 0, 0]), np.array([0, 1.0, 0]), depth, width

        up = np.array([0.0, 0.0, 1.0]) if name != "top" else np.array([1.0, 0.0, 0.0])
        q = COLD.copy()
        pts = strict = relaxed = 0
        reasons, tilts = {}, []
        # inset 12% so we test the face, not its edges
        for i in range(rows):
            fv = (-0.38 + 0.76 * i / max(rows - 1, 1)) * sv
            order = range(cols) if i % 2 == 0 else reversed(range(cols))
            for j in order:
                fu = (-0.38 + 0.76 * j / max(cols - 1, 1)) * su
                tgt = fc + u * fu + v * fv + n * PAD_STANDOFF
                pts += 1
                got, why = _try_point(model, data, ids, tgt, n, up, q)
                if got is None:
                    reasons[why] = reasons.get(why, 0) + 1
                else:
                    tilt, q = got
                    relaxed += 1
                    tilts.append(tilt)
                    if tilt == 0.0:
                        strict += 1
        res[name] = {"coverage": round(relaxed / pts, 3),
                     "strict": round(strict / pts, 3),
                     "pts": pts, "hit": relaxed,
                     "max_tilt_deg": max(tilts) if tilts else 0.0,
                     "mean_tilt_deg": round(float(np.mean(tilts)), 1) if tilts else 0.0,
                     "fail_reasons": reasons}
    return res


# ============================================================ reporting
def run_config(model, data, ids, w, d, h, x, R_rel, t_rel, cols=6, rows=4, n_az=12):
    center = _set_cabinet(model, ids, w, d, h, x)
    orb, standoff = orbit_test(model, data, ids, center, w, d, h, R_rel, t_rel, n_az)
    ras = raster_test(model, data, ids, center, w, d, h, cols, rows)
    orbit_ok = sum(1 for o in orb if o["in_view"]) / len(orb)
    sep, n_views = view_separation(orb)
    return {
        "w": w, "d": d, "h": h, "x": x,
        "standoff_m": round(standoff, 3),
        "orbit_in_view": round(orbit_ok, 3),
        "orbit_reach": round(sum(1 for o in orb if o["reach"]) / len(orb), 3),
        "view_sep_deg": sep, "n_framed_views": n_views,
        "faces": {k: v["coverage"] for k, v in ras.items()},
        "faces_strict": {k: v["strict"] for k, v in ras.items()},
        "front_top": round((ras["front"]["coverage"] + ras["top"]["coverage"]) / 2, 3),
        "_orbit": orb, "_raster": ras,
    }


def nominal(args):
    model, data, ids = load()
    R_rel, t_rel = cam_to_tcp_transform(model, data, ids)
    print(f"V5-0 reachability -- cabinet {args.w*1000:.0f} x {args.d*1000:.0f} x "
          f"{args.h*1000:.0f} mm at x={args.x:.2f}\n"
          f"  tolerances: pos < {POS_TOL*1000:.0f} mm, rot < {np.degrees(ROT_TOL):.0f} deg, "
          f"joint-limit margin > 1 deg, no arm contact\n")
    r = run_config(model, data, ids, args.w, args.d, args.h, args.x, R_rel, t_rel,
                   cols=8, rows=6, n_az=16)

    print(f"TRIAGE -- wrist-camera orbit (arm moves the camera, not the part)")
    print(f"  standoff derived from fovy + device size: {r['standoff_m']:.3f} m")
    for o in r["_orbit"]:
        mark = "ok " if o["in_view"] else ("reachable, device not fully framed"
                                           if o["reach"] else o["why"])
        print(f"    az {o['az_deg']:>6.1f} deg  {mark}")
    print(f"  reachable {r['orbit_reach']*100:.0f}%   whole device framed "
          f"{r['orbit_in_view']*100:.0f}%   framed views {r['n_framed_views']}   "
          f"best view separation {r['view_sep_deg']:.0f} deg\n")

    print("CLEAN -- pad raster coverage per face   (strict = exact-normal press)")
    for name in FACES:
        f = r["_raster"][name]
        why = ", ".join(f"{k} x{v}" for k, v in sorted(f["fail_reasons"].items())) or "-"
        print(f"    {name:<6} {f['coverage']*100:>5.1f}%  strict {f['strict']*100:>5.1f}%  "
              f"({f['hit']}/{f['pts']})  tilt used mean {f['mean_tilt_deg']:.0f} / "
              f"max {f['max_tilt_deg']:.0f} deg   {why}")
    print()

    front, top = r["_raster"]["front"], r["_raster"]["top"]
    verdict = (front["coverage"] >= 0.95 and top["coverage"] >= 0.95
               and r["n_framed_views"] >= 2 and r["view_sep_deg"] >= 45)
    print(f"V5-0 GATE: {'PASS' if verdict else 'FAIL'}")
    print("  criteria: front and top raster >=95% within a 30 deg tilt cone; at least 2")
    print("            framed camera views at least 45 deg apart")
    print("\nKinematics only -- no contact, no dynamics. A pose reachable here can still "
          "fail\nunder contact; that is V5-C's problem. This is necessary, not sufficient.")
    return r


def sweep(args):
    model, data, ids = load()
    R_rel, t_rel = cam_to_tcp_transform(model, data, ids)
    rows = []

    print("=== size envelope (depth 180 mm, x = 0.50) ===")
    print(f"{'':>8}" + "".join(f"{int(h*1000):>8}" for h in
                               (0.30, 0.35, 0.40, 0.45, 0.50, 0.55)) + "   <- height mm")
    for w in (0.20, 0.25, 0.30, 0.35):
        line = f"{int(w*1000):>5}mm "
        for h in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55):
            r = run_config(model, data, ids, w, 0.18, h, 0.50, R_rel, t_rel,
                           cols=5, rows=3, n_az=8)
            rows.append(r)
            line += f"{r['front_top']*100:>7.0f}%"
        print(line)
    print("  cell = mean coverage of FRONT and TOP faces (the two Stage-2/3 surfaces)\n")

    print("=== placement sweep (250 x 180 x 450 mm) ===")
    place = []
    for x in (0.34, 0.38, 0.42, 0.46, 0.50, 0.54, 0.58, 0.62):
        r = run_config(model, data, ids, 0.25, 0.18, 0.45, x, R_rel, t_rel,
                       cols=5, rows=3, n_az=8)
        place.append(r)
        rows.append(r)
        fc = r["faces"]
        print(f"  x={x:.2f}  front {fc['front']*100:>5.0f}%  top {fc['top']*100:>5.0f}%  "
              f"left {fc['left']*100:>5.0f}%  right {fc['right']*100:>5.0f}%  "
              f"back {fc['back']*100:>5.0f}%   views {r['n_framed_views']:>2} "
              f"sep {r['view_sep_deg']:>3.0f}deg")

    best = max(place, key=lambda r: r["front_top"])
    print(f"\n  coarse-scan best: x = {best['x']:.2f} "
          f"(front+top {best['front_top']*100:.0f}%)")
    print("  NOTE: this sweep rasters 15 points per face for speed. The placement "
          "DECISION\n  was made at full resolution (48 points/face, 16 azimuths) with "
          "`--nominal --x`;\n  do not quote these cells against those numbers. And with "
          "the rotary indexer in\n  the real scene, placement no longer trades off "
          "against face coverage at all --\n  see `--indexed`.")

    out = {"pos_tol_m": POS_TOL, "rot_tol_deg": float(np.degrees(ROT_TOL)),
           "pad_standoff_m": PAD_STANDOFF,
           "tilt_cone_deg": list(TILT_TOL_DEG), "frame_margin": FRAME_MARGIN,
           "note": "kinematics only; no contact or dynamics. Camera standoff is derived "
                   "per-config from fovy and device size -- see fit_standoff().",
           "configs": [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]}
    with open("reach_v5.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nwrote reach_v5.json")
    return out


def indexed_test(args):
    """Does the rotary indexer actually make every face workable?

    The claim is: present each vertical face at the FRONT position, where V5-0 measured
    100% coverage, and work it there. That is a claim, so it gets measured. For each
    index angle the turntable is commanded, the scene is re-solved, and whichever face
    now points at the arm (-X) is rastered in place.

    Index -> presented face, for a box on a Z turntable:
        0 deg -> front (-X local)      180 deg -> back  (+X local)
       90 deg -> right (+Y local)      270 deg -> left  (-Y local)
    """
    xml = args.indexed
    model, data, ids = load(xml)
    R_rel, t_rel = cam_to_tcp_transform(model, data, ids)
    tt = model.joint("tt_rot").id
    qadr = model.jnt_qposadr[tt]
    g = ids["cab_geom"]
    presented = {0: "front", 90: "right", 180: "back", 270: "left"}

    print(f"V5-A indexed reachability -- {xml}")
    print("  Each vertical face is rotated into the front working position and rastered "
          "there.\n  Without the indexer, V5-0 measured: front 100%, sides 90%, "
          "BACK 0% at every placement.\n")
    rows = []
    for deg in (0, 90, 180, 270):
        data.qpos[qadr] = np.deg2rad(deg)
        mujoco.mj_forward(model, data)
        # world-aligned half-extents of the rotated box
        R = data.geom_xmat[g].reshape(3, 3)
        sz = model.geom_size[g]
        ext = np.abs(R) @ sz
        cx, cy = data.geom_xpos[g][0], data.geom_xpos[g][1]
        # true top of the device (body + flush cover), and its base
        zs = [(data.geom_xpos[i][2] - model.geom_size[i][2],
               data.geom_xpos[i][2] + model.geom_size[i][2])
              for i in range(model.ngeom)
              if model.geom_bodyid[i] == ids["cab_body"] and model.geom_contype[i]]
        z0, z1 = min(a for a, _ in zs), max(b for _, b in zs)
        center = np.array([cx, cy, (z0 + z1) / 2])
        # raster the face now pointing -X: plane at cx - ext[0], spanning world Y and Z
        n = np.array([-1.0, 0.0, 0.0])
        fc = np.array([cx - ext[0], cy, (z0 + z1) / 2])
        u, v = np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])
        su, sv = 2 * ext[1], (z1 - z0)
        up = np.array([0.0, 0.0, 1.0])
        tgt_mat_base = tool_mat(n, up)
        q = COLD.copy()
        pts = strict = relaxed = 0
        reasons, tilts = {}, []
        for i in range(6):
            fv = (-0.38 + 0.76 * i / 5) * sv
            order = range(8) if i % 2 == 0 else reversed(range(8))
            for j in order:
                fu = (-0.38 + 0.76 * j / 7) * su
                tgt = fc + u * fu + v * fv + n * PAD_STANDOFF
                pts += 1
                got, why = _try_point(model, data, ids, tgt, n, up, q)
                if got is None:
                    reasons[why] = reasons.get(why, 0) + 1
                else:
                    tilt, q = got
                    relaxed += 1
                    tilts.append(tilt)
                    if tilt == 0.0:
                        strict += 1
        cov, st = relaxed / pts, strict / pts
        rows.append((deg, presented[deg], cov, st, reasons))
        why = ", ".join(f"{k} x{v}" for k, v in sorted(reasons.items())) or "-"
        print(f"  index {deg:>3} deg -> {presented[deg]:<6} face   "
              f"{cov*100:>5.1f}%  strict {st*100:>5.1f}%  ({relaxed}/{pts})   {why}")

    # the top face needs no indexing, but confirm it is still reachable with the riser
    data.qpos[qadr] = 0.0
    mujoco.mj_forward(model, data)
    zs = [(data.geom_xpos[i][2] - model.geom_size[i][2],
           data.geom_xpos[i][2] + model.geom_size[i][2])
          for i in range(model.ngeom)
          if model.geom_bodyid[i] == ids["cab_body"] and model.geom_contype[i]]
    z1 = max(b for _, b in zs)
    ras = raster_test(model, data, ids,
                      np.array([data.geom_xpos[g][0], data.geom_xpos[g][1], z1 / 2]),
                      2 * model.geom_size[g][1], 2 * model.geom_size[g][0], z1, 8, 6)
    t = ras["top"]
    print(f"  (no index)     -> top    face   {t['coverage']*100:>5.1f}%  "
          f"strict {t['strict']*100:>5.1f}%  ({t['hit']}/{t['pts']})")

    worst = min(r[2] for r in rows)
    ok = worst >= 0.95 and t["coverage"] >= 0.95
    print(f"\n  worst vertical face with the indexer: {worst*100:.1f}%")
    print(f"INDEXED GATE: {'PASS' if ok else 'FAIL'}  "
          f"(every vertical face and the top >= 95% in a 30 deg tilt cone)")
    return ok


def riser_sweep(args):
    """How much reach does the arm's own pedestal cost?

    The 120 mm offset from bench top to arm flange is inherited from the stock arm model
    and was never modelled as a solid -- so every reachability number before this was
    quoted for a cell with nothing holding the arm up. This resizes the riser and
    re-measures, so the cost is a measurement rather than an assumption.
    """
    xml = args.riser
    print(f"V5-A riser sensitivity -- {xml}")
    print("  Every number in V5_PLAN/CELL_SPEC was measured with NO riser modelled.\n")
    print(f"{'riser dia':>10} {'front':>8} {'top':>8} {'left':>8} {'right':>8}   "
          f"{'front strict':>12} {'sides strict':>12}")
    for dia in (0.0, 0.120, 0.150, 0.200, 0.250):
        model, data, ids = load(xml)
        g = model.geom("arm_riser").id
        if dia == 0.0:
            model.geom_contype[g] = 0
            model.geom_conaffinity[g] = 0
        else:
            model.geom_size[g][0] = dia / 2
        mujoco.mj_forward(model, data)
        cg = ids["cab_geom"]
        sz, bx = model.geom_size[cg], data.geom_xpos[cg]
        zs = [(data.geom_xpos[i][2] - model.geom_size[i][2],
               data.geom_xpos[i][2] + model.geom_size[i][2])
              for i in range(model.ngeom)
              if model.geom_bodyid[i] == ids["cab_body"] and model.geom_contype[i]]
        z1 = max(b for _, b in zs)
        centre = np.array([bx[0], bx[1], z1 / 2])
        ras = raster_test(model, data, ids, centre, 2 * sz[1], 2 * sz[0], z1, 8, 6)
        lab = "none" if dia == 0 else f"{dia*1000:.0f} mm"
        print(f"{lab:>10} {ras['front']['coverage']*100:>7.1f}% "
              f"{ras['top']['coverage']*100:>7.1f}% {ras['left']['coverage']*100:>7.1f}% "
              f"{ras['right']['coverage']*100:>7.1f}%   "
              f"{ras['front']['strict']*100:>11.1f}% "
              f"{(ras['left']['strict']+ras['right']['strict'])/2*100:>11.1f}%")
    print("\n  'strict' = exact-normal press. The 30-degree tilt cone hides most of the")
    print("  cost, which is exactly why both columns are reported.")
    return True


def scene_check(args):
    """Re-run the V5-0 tests against the REAL generated scene, not the bare probe.

    The probe has only the arm, the bench and a bare box. The real scene adds a matte
    backdrop, a tool post, a pad tool, a back panel and a top cover -- any of which can
    steal reachability that the probe said was available. A gate passed on a simplified
    scene is not a gate passed.
    """
    xml = args.scene
    model, data, ids = load(xml)
    R_rel, t_rel = cam_to_tcp_transform(model, data, ids)
    g = ids["cab_geom"]
    mujoco.mj_forward(model, data)
    sz = model.geom_size[g].copy()
    bx = data.geom_xpos[g].copy()
    depth, width = 2 * sz[0], 2 * sz[1]
    # the cabinet is body + flush cover; take the true top from the whole body's geoms
    top = max(data.geom_xpos[i][2] + model.geom_size[i][2]
              for i in range(model.ngeom)
              if model.geom_bodyid[i] == ids["cab_body"] and model.geom_contype[i])
    height = float(top)
    x = float(bx[0])
    print(f"V5-A scene check -- {xml}")
    print(f"  cabinet as built: depth(X) {depth*1000:.0f}  width(Y) {width*1000:.0f}  "
          f"height(Z) {height*1000:.0f} mm  at x={x:.3f}\n")

    center = np.array([x, float(bx[1]), height / 2])
    orb, standoff = orbit_test(model, data, ids, center, width, depth, height,
                               R_rel, t_rel, 16)
    sep, nviews = view_separation(orb)
    print(f"TRIAGE orbit: standoff {standoff:.3f} m | framed views {nviews} | "
          f"best separation {sep:.0f} deg")
    for o in orb:
        if o["in_view"]:
            print(f"    az {o['az_deg']:>6.1f} deg  framed")
    ras = raster_test(model, data, ids, center, width, depth, height, 8, 6)
    print("\nCLEAN raster (strict = exact-normal press)")
    for name in FACES:
        f = ras[name]
        why = ", ".join(f"{k} x{v}" for k, v in sorted(f["fail_reasons"].items())) or "-"
        print(f"    {name:<6} {f['coverage']*100:>5.1f}%  strict {f['strict']*100:>5.1f}%  "
              f"({f['hit']}/{f['pts']})  tilt mean {f['mean_tilt_deg']:.0f}/"
              f"max {f['max_tilt_deg']:.0f} deg   {why}")
    ok = (ras["front"]["coverage"] >= 0.95 and ras["top"]["coverage"] >= 0.95
          and nviews >= 2 and sep >= 45)
    print(f"\nV5-A GATE: {'PASS' if ok else 'FAIL'}  "
          f"(front & top >=95% in a 30 deg cone; >=2 framed views >=45 deg apart)")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nominal", action="store_true")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--scene", nargs="?", const="ufactory_xarm7/refurb_scene_v5.xml",
                    default=None, help="validate the real generated scene")
    ap.add_argument("--indexed", nargs="?", const="ufactory_xarm7/refurb_scene_v5.xml",
                    default=None, help="test every face via the rotary indexer")
    ap.add_argument("--riser", nargs="?", const="ufactory_xarm7/refurb_scene_v5.xml",
                    default=None, help="sweep arm-riser diameter vs reach")
    ap.add_argument("--w", type=float, default=0.25)
    ap.add_argument("--d", type=float, default=0.18)
    ap.add_argument("--h", type=float, default=0.45)
    ap.add_argument("--x", type=float, default=0.50)
    a = ap.parse_args()
    if a.riser:
        sys.exit(0 if riser_sweep(a) else 1)
    elif a.indexed:
        sys.exit(0 if indexed_test(a) else 1)
    elif a.scene:
        sys.exit(0 if scene_check(a) else 1)
    elif a.sweep:
        sweep(a)
    elif a.nominal:
        nominal(a)
    else:
        ap.print_help()
        sys.exit(1)
