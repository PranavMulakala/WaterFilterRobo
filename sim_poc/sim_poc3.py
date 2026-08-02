"""
Sim POC v3 — DrinkPrime REFURBISHMENT cell: the cartridge swap cycle.

v2 answered "can a robot install a cartridge?". v3 answers the question the
DrinkPrime founder actually cares about: "can a robot REFURBISH a returned unit?"
The generic first scene of that is a like-for-like swap:

    EXTRACT  untwist the spent cartridge out of its bayonet lock and lift it clear
    DISCARD  carry it to a bin and drop it
    INSERT   pick the fresh cartridge out of the tray and insert it (the v2 cycle)
    LOCK     twist 55 deg to seat it, and verify

This EXTENDS sim_poc2 rather than replacing it: ik_step, down_mat, the closed-loop
yaw servo, the tip-following compliant descent and every insertion constant are
imported and reused unchanged. The insertion half of the cycle is v2's phase table
verbatim. Only the extraction half is new.

Why extraction is not just insertion backwards:
  * Going IN, the chamfer funnel mechanically centres the part. Going OUT there is
    no funnel -- the lugs must thread back up through 3 mm slot channels with no
    lead-in geometry at all.
  * The untwist is applied through a friction grip on a 22 mm cap: a small contact
    patch transmitting torsion. The wrist can rotate while the cartridge does not.
    The servo is therefore closed-loop on the MEASURED cartridge yaw, with an
    anti-windup clamp so a slipping grip cannot wind the command up without bound
    (the same defect class that caused the v2 insertion wedge).

CLI (same shape as v2):
  python3 sim_poc3.py --eval 25            # headless: swap-cycle stats over N seeds
  python3 sim_poc3.py --render 1 7 1       # render one swap cycle (idx, seed, speed)
  python3 sim_poc3.py --cards              # title + end cards from stats_v3.json
  python3 sim_poc3.py --concat             # stitch refurb_cell_v3.mp4
"""

import argparse, json, os
import numpy as np
import mujoco

# --- everything reusable comes straight from v2; nothing is reimplemented -------
import sim_poc2 as v2
from sim_poc2 import (
    ik_step, down_mat, wrap_pi, _font,
    SOCK, SPAWN_C, CART_HALF, SPAWN_Z, GRASP_OFF, SEAT_Z, TWIST_DEG,
    PERCEPTION_NOISE, ENTRY_TOL, GRIP_ECC_MAX, Z_LAG,
    INSERT_UPRIGHT, INSERT_DEPTH_Z, FPS,
)

XML = "ufactory_xarm7/cartridge_scene_v3.xml"
STATS = "stats_v3.json"

BIN = np.array([0.46, 0.0])      # spent-cartridge bin, matches cartridge_scene_v3.xml
BIN_RIM_Z = 0.055                # top of the bin walls
CAP_TCP = 0.131                  # tcp height to grip a SEATED cartridge's cap (v2 REGRIP)

# The installed cartridge is left locked somewhere in this band. The slot gap spans
# ~72-108 deg and a lug is ~7.6 deg wide, so anything outside [64, 116] deg is
# captive; 25-50 deg is comfortably locked without being a single fixed pose.
LOCK_YAW_RANGE = (np.deg2rad(25.0), np.deg2rad(50.0))

# Anti-windup on the untwist. The cartridge is turned through friction at the cap,
# so if it stalls, a closed-loop-on-the-PART servo would keep commanding more wrist
# rotation forever -- exactly the "integrator winding up against a constraint" that
# caused the v2 wedge. Cap how far the commanded wrist yaw may lead the achieved
# wrist yaw; beyond that, more command produces no more torque, only windup.
YAW_LEAD_MAX = 0.35              # rad (~20 deg)

UNTWIST_TOL = np.deg2rad(4.0)    # lug axis must reach the slot axis within this
LUG_TARGET = np.pi / 2           # slots lie along world y

# Bin acceptance: the part must actually be inside the bin footprint and low enough
# to be resting in it rather than perched on a wall or still in the gripper.
BIN_XY_TOL = 0.075
BIN_Z_MAX = 0.090


def _yaw_of(mat):
    return np.arctan2(mat[1, 0], mat[0, 0])


def lug_err(mat):
    """signed error from the body's lug axis to the slot axis, mod pi (2-fold lugs)"""
    return wrap_pi((LUG_TARGET - _yaw_of(mat) + np.pi / 2) % np.pi - np.pi / 2)


# ----------------------------------------------------------------- trial
def run_trial(seed, frame_cb=None):
    rng = np.random.default_rng(seed)
    model = mujoco.MjModel.from_xml_path(XML)
    data = mujoco.MjData(model)

    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "link_tcp")
    fresh_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cartridge")
    spent_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "spent_cartridge")
    arm_joints = [f"joint{i}" for i in range(1, 8)]
    dof_ids = np.array([model.joint(n).dofadr[0] for n in arm_joints])
    qpos_ids = np.array([model.joint(n).qposadr[0] for n in arm_joints])
    act_ids = np.array([model.actuator(f"act{i}").id for i in range(1, 8)])
    grip_id = model.actuator("gripper").id
    jnt_range = np.array([model.joint(n).range for n in arm_joints])

    mujoco.mj_resetDataKeyframe(model, data, model.key("home").id)

    # --- both free joints must be placed explicitly: the `home` keyframe predates
    # --- them and reset would otherwise teleport both cartridges to the origin.
    spawn = SPAWN_C + rng.uniform(-0.04, 0.04, 2)
    yaw0 = rng.uniform(0, 2 * np.pi)
    a = model.joint("cartridge_free").qposadr[0]
    data.qpos[a:a + 3] = [*spawn, SPAWN_Z + 0.002]
    data.qpos[a + 3:a + 7] = [np.cos(yaw0 / 2), 0, 0, np.sin(yaw0 / 2)]

    lock_yaw = rng.uniform(*LOCK_YAW_RANGE)
    b = model.joint("spent_free").qposadr[0]
    data.qpos[b:b + 3] = [*SOCK, SEAT_Z]
    data.qpos[b + 3:b + 7] = [np.cos(lock_yaw / 2), 0, 0, np.sin(lock_yaw / 2)]
    mujoco.mj_forward(model, data)

    # --- simulated perception (same 1 mm / 1 deg noise model as v2) -------------
    detected = spawn + rng.normal(0, PERCEPTION_NOISE, 2)
    fx = data.xmat[fresh_id].reshape(3, 3)[:, 0]
    detected_yaw = np.arctan2(fx[1], fx[0]) + rng.normal(0, np.deg2rad(1.0))
    detected_lock_yaw = lock_yaw + rng.normal(0, np.deg2rad(1.0))

    GRIP_OPEN, GRIP_CLOSED = 0.0, 240.0
    grasp_z = SPAWN_Z + GRASP_OFF

    # phase table: (name, tcp_xyz, grip, dwell_s, tol_m, speed_scale, servo, max_s, body)
    #   servo: False | "yaw" (v2 lug servo) -- body says WHICH cartridge it tracks
    P = [
        ("PERCEPTION",     None,               GRIP_OPEN,   0.8, None,  1.0, False, 2.0,  None),
        # ---------------- EXTRACT: free the installed cartridge -----------------
        ("APPROACH SPENT", [*SOCK, 0.30],      GRIP_OPEN,   0.1, 0.015, 1.0, False, 6.0,  None),
        ("DESCEND CAP",    [*SOCK, CAP_TCP],   GRIP_OPEN,   0.3, 0.006, 0.4, False, 6.0,  None),
        ("GRIP CAP",       [*SOCK, CAP_TCP],   GRIP_CLOSED, 1.0, 0.012, 0.5, False, 3.0,  "spent"),
        ("UNTWIST",        [*SOCK, CAP_TCP],   GRIP_CLOSED, 0.5, 0.008, 0.5, "yaw", 10.0, "spent"),
        ("EXTRACT",        [*SOCK, 0.30],      GRIP_CLOSED, 0.3, 0.020, 0.18, "yaw", 10.0, "spent"),
        # ---------------- DISCARD: drop it in the bin ---------------------------
        ("CARRY TO BIN",   [*BIN, 0.30],       GRIP_CLOSED, 0.4, 0.015, 0.5, False, 8.0,  "spent"),
        ("DISCARD",        [*BIN, 0.26],       GRIP_OPEN,   1.0, 0.020, 0.6, False, 4.0,  "spent"),
        ("CLEAR BIN",      [*BIN, 0.34],       GRIP_OPEN,   0.2, 0.030, 1.0, False, 4.0,  None),
        # ---------------- INSERT + LOCK: the v2 cycle, unchanged ----------------
        ("APPROACH",       [*detected, 0.28],  GRIP_OPEN,   0.1, 0.015, 1.0, False, 6.0,  "fresh"),
        ("DESCEND",        [*detected, grasp_z], GRIP_OPEN, 0.3, 0.008, 0.6, False, 5.0,  "fresh"),
        ("GRASP",          [*detected, grasp_z], GRIP_CLOSED, 1.2, 0.012, 1.0, False, 3.0, "fresh"),
        ("LIFT",           [*detected, 0.35],  GRIP_CLOSED, 0.2, 0.020, 1.0, False, 4.0,  "fresh"),
        ("TRANSIT",        [*SOCK, 0.35],      GRIP_CLOSED, 0.5, 0.012, 0.5, False, 8.0,  "fresh"),
        ("RECOVER GRIP",   [*SOCK, 0.131],     GRIP_CLOSED, 0.6, 0.012, 0.5, False, 3.0,  "fresh"),
        ("RECOVER LIFT",   [*SOCK, 0.30],      GRIP_CLOSED, 0.3, 0.020, 0.6, False, 6.0,  "fresh"),
        ("ORIENT LUGS",    [*SOCK, 0.24],      GRIP_CLOSED, 1.2, 0.005, 0.6, "yaw", 16.0, "fresh"),
        ("PRE-INSERT",     [*SOCK, 0.19],      GRIP_CLOSED, 0.6, 0.004, 0.25, "yaw", 14.0, "fresh"),
        ("INSERT",         [*SOCK, 0.126],     GRIP_CLOSED, 0.3, 0.005, 0.12, "yaw", 14.0, "fresh"),
        ("DROP-SEAT",      [*SOCK, 0.126],     GRIP_OPEN,   0.8, 0.005, 0.3, False, 4.0,  "fresh"),
        ("REGRIP ALIGN",   [*SOCK, 0.131],     GRIP_OPEN,   0.4, 0.003, 0.3, False, 6.0,  "fresh"),
        ("REGRIP CAP",     [*SOCK, 0.131],     GRIP_CLOSED, 1.0, 0.012, 0.5, False, 3.0,  "fresh"),
        ("TWIST-LOCK",     [*SOCK, 0.131],     GRIP_CLOSED, 1.4, 0.006, 0.5, False, 4.0,  "fresh"),
        ("RELEASE",        [*SOCK, 0.131],     GRIP_OPEN,   0.8, 0.012, 1.0, False, 3.0,  "fresh"),
        ("RETREAT",        [*SOCK, 0.34],      GRIP_OPEN,   0.4, 0.030, 1.0, False, 4.0,  None),
    ]
    FOLLOW = ("DROP-SEAT", "REGRIP ALIGN", "REGRIP CAP", "TWIST-LOCK", "RELEASE",
              "RECOVER GRIP")
    CONTINUOUS_DWELL = ("INSERT",)
    # stage label for the HUD / video
    STAGE = {}
    for nm in ("APPROACH SPENT", "DESCEND CAP", "GRIP CAP", "UNTWIST", "EXTRACT"):
        STAGE[nm] = "EXTRACT"
    for nm in ("CARRY TO BIN", "DISCARD", "CLEAR BIN"):
        STAGE[nm] = "DISCARD"
    for nm in ("APPROACH", "DESCEND", "GRASP", "LIFT", "TRANSIT", "RECOVER GRIP",
               "RECOVER LIFT", "ORIENT LUGS", "PRE-INSERT", "INSERT", "DROP-SEAT"):
        STAGE[nm] = "INSERT"
    for nm in ("REGRIP ALIGN", "REGRIP CAP", "TWIST-LOCK", "RELEASE", "RETREAT"):
        STAGE[nm] = "LOCK"
    STAGE["PERCEPTION"] = "EXTRACT"

    q_des = data.qpos[qpos_ids].copy()
    ik_data = mujoco.MjData(model)
    dt = model.opt.timestep
    base_step = 2.0 * dt

    wp, dwell_left, phase_t = 0, P[0][3], 0.0
    t_limit = 120.0                 # a swap is roughly two v2 cycles
    retries = 0
    untwist_retries = 0
    servo_yaw = 0.0
    twist_from = None
    insert_end_cart_yaw = None
    hold_e = None
    aborted = False
    peak_extract_tilt = 0.0
    untwist_stalled = False

    def body_id(tag):
        return spent_id if tag == "spent" else fresh_id

    while data.time < t_limit and wp < len(P):
        name, tgt, grip, dwell, tol, spd, servo, max_s, btag = P[wp]
        cart_id = body_id(btag) if btag else fresh_id
        cmat = data.xmat[cart_id].reshape(3, 3)

        if name == "PERCEPTION":
            data.ctrl[act_ids] = q_des
            data.ctrl[grip_id] = grip
            data.qfrc_applied[dof_ids] = data.qfrc_bias[dof_ids]
            mujoco.mj_step(model, data)
            dwell_left -= dt
            if dwell_left <= 0:
                wp += 1; dwell_left = P[wp][3]; phase_t = 0.0
            if frame_cb:
                frame_cb(model, data, name, STAGE[name], detected, detected_yaw, seed)
            continue

        # ---- yaw command (v2's servo law, told which body to track) -----------
        if servo == "yaw":
            servo_yaw -= np.clip(lug_err(cmat), -0.0025, 0.0025)
            # ANTI-WINDUP: the untwist is transmitted through friction on a 22 mm
            # cap. If the cap slips, the part stops turning while the servo keeps
            # asking for more -- so bound how far the command may lead the wrist's
            # ACHIEVED yaw. Past that, extra command adds no torque, only windup.
            sm = data.site_xmat[site_id].reshape(3, 3)
            yaw_meas = np.arctan2(-sm[1, 0], sm[0, 0])          # down_mat convention
            yaw_meas += 2 * np.pi * np.round((servo_yaw - yaw_meas) / (2 * np.pi))
            servo_yaw = float(np.clip(servo_yaw, yaw_meas - YAW_LEAD_MAX,
                                      yaw_meas + YAW_LEAD_MAX))
        elif name == "TWIST-LOCK":
            if twist_from is None:
                twist_from = servo_yaw
                insert_end_cart_yaw = _yaw_of(cmat)
            servo_yaw = twist_from + np.deg2rad(TWIST_DEG) * min(1.0, phase_t / 1.2)
        tmat = down_mat(servo_yaw)

        # ---- lateral command --------------------------------------------------
        tgt_arr = np.array(tgt, dtype=float)
        cart_xy = data.xpos[cart_id][:2]
        tcp_xy = data.site_xpos[site_id][:2]
        if name != "INSERT":
            hold_e = None
        if name == "INSERT":
            # v2's tip-following compliant descent, unchanged
            tip = data.xpos[cart_id] + cmat @ np.array([0.0, 0.0, -CART_HALF])
            if hold_e is None:
                hold_e = np.clip(tcp_xy - tip[:2], -GRIP_ECC_MAX, GRIP_ECC_MAX)
            tgt_arr[:2] = tip[:2] + hold_e
            tgt_arr[2] = max(tgt_arr[2], data.site_xpos[site_id][2] - Z_LAG)
        elif name in ("ORIENT LUGS", "PRE-INSERT"):
            tgt_arr[:2] = tcp_xy + (SOCK - cart_xy)
        elif name in ("UNTWIST", "EXTRACT"):
            # Hold the socket axis exactly. There is no funnel on the way out: the
            # lugs have to thread back up 3 mm slot channels with no lead-in, so any
            # commanded lateral motion here is pure risk.
            tgt_arr[:2] = SOCK
        elif name in FOLLOW:
            tgt_arr[:2] = cart_xy

        ik_data.qpos[:] = data.qpos
        ik_data.qpos[qpos_ids] = q_des
        mujoco.mj_kinematics(model, ik_data)
        mujoco.mj_comPos(model, ik_data)
        dq, _ = ik_step(model, ik_data, site_id, tgt_arr, tmat, dof_ids)
        ms = base_step * spd
        mx = np.max(np.abs(dq))
        if mx > ms:
            dq = dq * (ms / mx)          # direction-preserving (v2 fix)
        q_des = np.clip(q_des + dq, jnt_range[:, 0], jnt_range[:, 1])
        data.ctrl[act_ids] = q_des
        data.ctrl[grip_id] = grip
        data.qfrc_applied[dof_ids] = data.qfrc_bias[dof_ids]
        mujoco.mj_step(model, data)
        phase_t += dt

        if name in ("UNTWIST", "EXTRACT"):
            peak_extract_tilt = max(peak_extract_tilt,
                                    np.rad2deg(np.arccos(np.clip(cmat[2, 2], -1, 1))))

        yaw_ok = True
        if servo == "yaw":
            yaw_ok = abs(lug_err(cmat)) < np.deg2rad(4)

        # ---- completion, judged on the PART wherever the part is what matters --
        if name == "UNTWIST":
            # the lug axis must actually reach the slot axis -- judged on the
            # CARTRIDGE, not on the wrist, precisely because the grip can slip.
            done = abs(lug_err(cmat)) < UNTWIST_TOL
        elif name == "EXTRACT":
            # lugs (49 mm below centre) must be clear of the collar top (100 mm)
            done = data.xpos[cart_id][2] > SEAT_Z + 0.085
        elif name == "DISCARD":
            done = (np.linalg.norm(data.xpos[cart_id][:2] - BIN) < BIN_XY_TOL
                    and data.xpos[cart_id][2] < BIN_Z_MAX)
        elif name == "TWIST-LOCK":
            done = phase_t > 1.2
        elif name in ("ORIENT LUGS", "PRE-INSERT"):
            cart_xy_err = np.linalg.norm(data.xpos[cart_id][:2] - SOCK)
            z_err = abs(data.site_xpos[site_id][2] - tgt_arr[2])
            done = (cart_xy_err < ENTRY_TOL and z_err < 0.008 and yaw_ok
                    and cmat[2, 2] > 0.9986)
        elif name == "INSERT":
            done = (data.site_xpos[site_id][2] < 0.129
                    and cmat[2, 2] > INSERT_UPRIGHT
                    and data.xpos[cart_id][2] < INSERT_DEPTH_Z)
        elif name == "DROP-SEAT":
            done = data.xpos[cart_id][2] < SEAT_Z + 0.008
        else:
            done = np.linalg.norm(tgt_arr - data.site_xpos[site_id]) < tol and yaw_ok

        if done:
            dwell_left -= dt
        elif name in CONTINUOUS_DWELL:
            dwell_left = dwell
        if dwell_left <= 0:
            wp += 1; phase_t = 0.0
            while wp < len(P) and P[wp][0].startswith("RECOVER"):
                wp += 1
            if wp < len(P):
                dwell_left = P[wp][3]
                if P[wp][0] == "INSERT":
                    hold_e = None
        elif phase_t > max_s:
            if name in ("INSERT", "DROP-SEAT") and retries < 2:
                retries += 1
                wp = next(i for i, p in enumerate(P) if p[0] == "RECOVER GRIP")
                dwell_left, phase_t = P[wp][3], 0.0
                continue
            if name in ("UNTWIST", "EXTRACT") and untwist_retries < 2:
                # back off, re-seat the grip on the cap, and try the untwist again
                untwist_retries += 1
                untwist_stalled = True
                wp = next(i for i, p in enumerate(P) if p[0] == "DESCEND CAP")
                dwell_left, phase_t = P[wp][3], 0.0
                continue
            aborted = True
            break

        if frame_cb:
            frame_cb(model, data, name, STAGE[name], detected, detected_yaw, seed)

    # ---- verification -----------------------------------------------------
    # NEW cartridge: v2's checks, unchanged and not relaxed.
    npos = data.xpos[fresh_id]
    nmat = data.xmat[fresh_id].reshape(3, 3)
    xy_off = float(np.linalg.norm(npos[:2] - SOCK))
    upright = float(nmat[2, 2])
    if insert_end_cart_yaw is not None:
        rel_twist = abs(np.rad2deg(wrap_pi(_yaw_of(nmat) - insert_end_cart_yaw)))
    else:
        rel_twist = 0.0
    seated = (not aborted) and xy_off < 0.006 and npos[2] < SEAT_Z + 0.008 and upright > 0.95
    locked = seated and rel_twist > 30.0

    # OLD cartridge: must be in the bin, and demonstrably out of the socket.
    spos = data.xpos[spent_id]
    bin_xy = float(np.linalg.norm(spos[:2] - BIN))
    discarded = bool(bin_xy < BIN_XY_TOL and spos[2] < BIN_Z_MAX)
    removed = bool(np.linalg.norm(spos[:2] - SOCK) > 0.05 or spos[2] > SEAT_Z + 0.05)

    swap_ok = bool(locked and discarded and removed)
    return {
        "seed": int(seed), "spawn": spawn.tolist(),
        "spawn_yaw_deg": float(np.rad2deg(yaw0) % 360),
        "lock_yaw_deg": float(np.rad2deg(lock_yaw)),
        "xy_offset_mm": float(xy_off * 1000), "height_mm": float(npos[2] * 1000),
        "upright": upright, "twist_deg": float(rel_twist),
        "seated": bool(seated), "locked": bool(locked),
        "spent_bin_xy_mm": float(bin_xy * 1000), "spent_z_mm": float(spos[2] * 1000),
        "discarded": discarded, "removed": removed, "swap_ok": swap_ok,
        "aborted": bool(aborted), "retries": int(retries),
        "untwist_retries": int(untwist_retries), "untwist_stalled": bool(untwist_stalled),
        "peak_extract_tilt_deg": float(peak_extract_tilt),
        "cycle_s": float(data.time), "phases_done": int(wp),
    }


# ----------------------------------------------------------------- rendering
def make_frame_cb(frames, model):
    """Same wrist-cam PiP + HUD pipeline as v2, extended to show both cartridges
    and the current refurb STAGE."""
    from PIL import Image, ImageDraw
    main_r = mujoco.Renderer(model, 720, 1280)
    wrist_r = mujoco.Renderer(model, 216, 288)
    font = _font("mono", 20)
    font_b = _font("mono_bold", 22)
    font_s = _font("mono", 15)
    state = {"n": 0}
    steps_per_frame = max(1, int(round(1.0 / FPS / model.opt.timestep)))

    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "link_tcp")
    fresh_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cartridge")
    spent_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "spent_cartridge")
    STAGES = ["EXTRACT", "DISCARD", "INSERT", "LOCK"]

    def cb(m, d, phase, stage, detected, det_yaw, seed):
        state["n"] += 1
        if state["n"] % steps_per_frame:
            return
        main_r.update_scene(d, camera="main")
        img = Image.fromarray(main_r.render())
        wrist_r.update_scene(d, camera="wrist")
        wr = Image.fromarray(wrist_r.render())
        draw = ImageDraw.Draw(img, "RGBA")

        px, py = 1280 - 288 - 16, 720 - 216 - 16
        draw.rectangle([px - 3, py - 3, px + 288 + 3, py + 216 + 3], fill=(255, 255, 255, 220))
        img.paste(wr, (px, py))
        draw.text((px + 6, py + 4), "WRIST CAM", font=font_s, fill=(255, 255, 255, 230))

        tcp = d.site_xpos[site_id]
        new, old = d.xpos[fresh_id], d.xpos[spent_id]
        nmat = d.xmat[fresh_id].reshape(3, 3)
        omat = d.xmat[spent_id].reshape(3, 3)
        grip_state = "CLOSED" if d.ctrl[mujoco.mj_name2id(
            m, mujoco.mjtObj.mjOBJ_ACTUATOR, "gripper")] > 100 else "OPEN"
        lines = [
            f"PHASE   {phase}",
            f"t       {d.time:6.2f} s",
            f"TCP     x{tcp[0]*1000:7.1f}  y{tcp[1]*1000:7.1f}  z{tcp[2]*1000:6.1f} mm",
            f"SPENT   z{old[2]*1000:6.1f} mm  lug {np.degrees(np.arctan2(omat[1,0],omat[0,0])):6.1f} deg"
            f"   {'-> BIN' if np.linalg.norm(old[:2]-BIN)<BIN_XY_TOL else 'in socket'}",
            f"FRESH   z{new[2]*1000:6.1f} mm  lug {np.degrees(np.arctan2(nmat[1,0],nmat[0,0])):6.1f} deg"
            f"   err {np.linalg.norm(new[:2]-SOCK)*1000:5.1f} mm",
            f"GRIPPER {grip_state}   clearance 3.0 mm   bayonet +-{TWIST_DEG:.0f} deg",
        ]
        draw.rectangle([12, 12, 700, 12 + 24 + len(lines) * 26], fill=(10, 14, 20, 175))
        draw.text((24, 20), f"REFURBISHMENT CELL - CARTRIDGE SWAP (seed {seed})",
                  font=font_b, fill=(120, 200, 255, 255))
        for i, ln in enumerate(lines):
            draw.text((24, 50 + i * 26), ln, font=font, fill=(235, 240, 245, 255))

        # stage ribbon: EXTRACT > DISCARD > INSERT > LOCK, current one highlighted
        x0, y0 = 24, 12 + 24 + len(lines) * 26 + 14
        for st in STAGES:
            w = int(draw.textlength(st, font=font)) + 26
            on = (st == stage)
            draw.rectangle([x0, y0, x0 + w, y0 + 32],
                           fill=(41, 121, 255, 235) if on else (255, 255, 255, 38))
            draw.text((x0 + 13, y0 + 6), st, font=font,
                      fill=(255, 255, 255, 255) if on else (170, 180, 195, 255))
            x0 += w + 8
        frames.append(np.asarray(img).copy())
    return cb


def render_trial(idx, seed, speed):
    import imageio
    model = mujoco.MjModel.from_xml_path(XML)
    frames = []
    res = run_trial(seed, frame_cb=make_frame_cb(frames, model))
    frames = frames[::speed]
    imageio.mimsave(f"swap_{idx}.mp4", frames, fps=FPS, codec="libx264", quality=8,
                    pixelformat="yuv420p")
    print(f"swap_{idx}.mp4: {len(frames)} frames | {json.dumps(res)}")


def make_cards():
    import imageio
    from PIL import Image, ImageDraw
    stats = json.load(open(STATS))
    fb = lambda s: _font("sans_bold", s)
    fr = lambda s: _font("sans", s)

    def card(lines, fname, secs):
        img = Image.new("RGB", (1280, 720), (13, 17, 23))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 1280, 6], fill=(41, 121, 255))
        y = 140
        for txt, fnt, col in lines:
            d.text(((1280 - d.textlength(txt, font=fnt)) / 2, y), txt, font=fnt, fill=col)
            y += fnt.size + 24
        imageio.mimsave(fname, [np.asarray(img)] * int(FPS * secs), fps=FPS,
                        codec="libx264", quality=8, pixelformat="yuv420p")

    card([
        ("REFURBISHMENT CELL - CARTRIDGE SWAP", fb(50), (235, 240, 245)),
        ("Simulation POC", fr(30), (150, 160, 175)),
        ("", fr(10), (0, 0, 0)),
        ("Spent cartridge arrives twist-locked in the unit. The robot must", fr(24), (150, 160, 175)),
        ("untwist it out of the bayonet, bin it, then install a fresh one", fr(24), (150, 160, 175)),
        ("from a randomized pose - a full refurb swap cycle, unassisted.", fr(24), (150, 160, 175)),
        ("", fr(10), (0, 0, 0)),
        ("EXTRACT  >  DISCARD  >  INSERT  >  LOCK", fr(26), (120, 200, 255)),
        ("", fr(10), (0, 0, 0)),
        ("DrinkPrime automation study - Phase 0 (pre-hardware)", fr(22), (110, 120, 135)),
    ], "card_v3_title.mp4", 4.0)

    n, sr = stats["trials"], stats["swap_rate"] * 100
    card([
        ("SWAP CYCLE RELIABILITY", fb(50), (235, 240, 245)),
        (f"{n} randomized trials - fresh part +-40 mm / 360 deg,", fr(25), (150, 160, 175)),
        ("spent part locked at a random angle, 1 mm vision noise", fr(25), (150, 160, 175)),
        ("", fr(10), (0, 0, 0)),
        (f"FULL SWAP COMPLETED: {sr:.0f}%", fb(60),
         (80, 220, 130) if sr >= 80 else (255, 190, 80)),
        (f"old cartridge binned {stats['discard_rate']*100:.0f}%   |   "
         f"new cartridge locked {stats['locked_rate']*100:.0f}%", fr(25), (150, 160, 175)),
        (f"avg cycle {stats['avg_cycle_s']:.1f} s   |   "
         f"seating {stats['avg_xy_mm']:.1f} mm", fr(25), (150, 160, 175)),
        ("", fr(10), (0, 0, 0)),
        ("Next: real refurb steps from DrinkPrime's process video", fr(25), (120, 200, 255)),
    ], "card_v3_end.mp4", 5.0)
    print("cards written")


def concat():
    import subprocess, imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    parts = ["card_v3_title.mp4", "swap_1.mp4", "swap_2.mp4", "card_v3_end.mp4"]
    with open("concat_v3.txt", "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", "concat_v3.txt",
                    "-c", "copy", "refurb_cell_v3.mp4"], check=True, capture_output=True)
    print("refurb_cell_v3.mp4 written")


# ----------------------------------------------------------------- eval
def evaluate(n):
    results = [run_trial(s) for s in range(n)]
    ok = [r for r in results if r["swap_ok"]]
    stats = {
        "trials": n,
        "swap_rate": sum(r["swap_ok"] for r in results) / n,
        "discard_rate": sum(r["discarded"] for r in results) / n,
        "removed_rate": sum(r["removed"] for r in results) / n,
        "seated_rate": sum(r["seated"] for r in results) / n,
        "locked_rate": sum(r["locked"] for r in results) / n,
        "avg_cycle_s": float(np.mean([r["cycle_s"] for r in ok])) if ok else 0.0,
        "avg_xy_mm": float(np.mean([r["xy_offset_mm"] for r in ok])) if ok else 0.0,
        "avg_twist_deg": float(np.mean([r["twist_deg"] for r in ok])) if ok else 0.0,
        "untwist_stall_rate": sum(r["untwist_stalled"] for r in results) / n,
        "results": results,
    }
    json.dump(stats, open(STATS, "w"), indent=1)
    print(f"EVAL v3 swap: {n} trials | FULL SWAP {stats['swap_rate']*100:.0f}% | "
          f"binned {stats['discard_rate']*100:.0f}% | "
          f"locked {stats['locked_rate']*100:.0f}% | "
          f"avg cycle {stats['avg_cycle_s']:.1f}s")
    for r in results:
        tag = "SWAP-OK" if r["swap_ok"] else ("PART-OK" if r["locked"] or r["discarded"] else "FAIL")
        print(f"  seed {r['seed']:3d}: {tag:7s} bin={'Y' if r['discarded'] else 'n'}"
              f" lock={'Y' if r['locked'] else 'n'}"
              f" lockyaw={r['lock_yaw_deg']:4.0f}deg xy={r['xy_offset_mm']:5.1f}mm"
              f" twist={r['twist_deg']:4.0f}deg exTilt={r['peak_extract_tilt_deg']:5.1f}deg"
              f" t={r['cycle_s']:5.1f}s ph={r['phases_done']:2d}"
              f" utr={r['untwist_retries']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", type=int)
    ap.add_argument("--render", nargs=3, type=int, metavar=("IDX", "SEED", "SPEED"))
    ap.add_argument("--cards", action="store_true")
    ap.add_argument("--concat", action="store_true")
    a = ap.parse_args()
    if a.eval: evaluate(a.eval)
    elif a.render: render_trial(*a.render)
    elif a.cards: make_cards()
    elif a.concat: concat()
