"""
Sim POC v2 — DrinkPrime cartridge cell, hard-mode edition.

What makes this version non-trivial:
  * The cartridge spawns at a RANDOM position (+-4 cm) and RANDOM rotation (360 deg)
    in the parts tray every trial. The controller reads its pose (simulated
    perception, with 1 mm gaussian noise) and re-plans. No replayed motion.
  * The socket is a BAYONET mount: two entry slots, 3.0 mm radial clearance.
    The cartridge's two lugs must be rotated to align with the slots before
    insertion, and after seating the arm TWISTS the cartridge ~55 deg to lock it
    under the walls — contact-rich manipulation, the hard part of the task.
  * Wrist-camera picture-in-picture, live telemetry HUD, and a multi-trial
    evaluation (success rate over N randomized seeds), not one lucky run.

CLI:
  python3 sim_poc2.py --eval 25            # headless: stats over 25 random seeds
  python3 sim_poc2.py --render 1 7 1       # render trial video chunk (idx, seed, speed)
  python3 sim_poc2.py --cards              # title + end cards from stats.json
  python3 sim_poc2.py --concat             # stitch final cartridge_cell_v2.mp4
"""

import argparse, json, os
import numpy as np
import mujoco

XML = "ufactory_xarm7/cartridge_scene_v2.xml"
FPS = 30
SOCK = np.array([0.46, 0.26])
SPAWN_C = np.array([0.46, -0.26])
CART_HALF = 0.055
SPAWN_Z = 0.068          # cartridge center resting on the tray floor
GRASP_OFF = 0.004        # tcp at fingertips; the pads land ~25 mm higher, mid-body
SEAT_Z = 0.100           # cartridge center when seated on the pedestal (45 mm base)
TWIST_DEG = 55.0
PERCEPTION_NOISE = 0.001  # 1 mm
# --- insertion control (see RESULTS.md; every one of these earned its place) ---
# FIX 1 -- the wedge. The old lateral law recomputed the target as
# (current TCP + part error) every step. When the part is jammed in the funnel and
# cannot move the error never shrinks, so the wrist walks sideways indefinitely:
# an integrator winding up against a contact constraint. It torqued the part until
# it jammed. Now the wrist is commanded to hang plumb over the cartridge's BOTTOM
# FACE (the bit actually inside the funnel), not its body centre -- when the part
# tilts its centre swings sideways, so centre-following chases and amplifies the
# tilt, whereas tip-following corrects it.
ENTRY_TOL = 0.0015       # cartridge xy error required before INSERT starts (m).
                         # TIGHTER than the old 0.0025 -- the bayonet slot leaves
                         # only ~3 mm of tangential slack at the lug.
GRIP_ECC_MAX = 0.004     # in-jaw eccentricity (m): the part never hangs perfectly
                         # centred in the pads, so latch that offset once at INSERT
                         # entry and hold it, rather than re-measuring (and chasing)
                         # it every step.
Z_LAG = 0.008            # max commanded-below-actual TCP height during INSERT (m).
                         # The old code commanded a 64 mm absolute z step, which
                         # saturated the per-joint rate clip -- so the whole rate
                         # budget went to the descent and none was left for lateral
                         # or rotational correction, AND the clip distorted the
                         # joint-space direction so the TCP did not travel straight
                         # down. A bounded feed lead keeps the IK residual small.

# FIX 2 -- honest failure detection. INSERT used to complete on TCP height alone,
# but a wedged part still lets the wrist descend, so jams reported SUCCESS and were
# only noticed two phases later at DROP-SEAT (which had no retry path). Measured
# separation at INSERT exit: healthy runs <=0.9 deg tilt and 121-127 mm; wedged runs
# 24-49 deg and 140-151 mm. These thresholds sit in that gap, with margin both sides.
INSERT_UPRIGHT = 0.96    # cos(16.3 deg) -- part must still be near-vertical
INSERT_DEPTH_Z = 0.135   # cartridge centre must genuinely be down in the bore (m)

# ----------------------------------------------------------------- helpers
def down_mat(yaw=0.0):
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([[c, -s, 0], [-s, -c, 0], [0, 0, -1.0]]).T

def ik_step(model, ik_data, site_id, target_pos, target_mat, dof_ids,
            damping=0.1, gain=0.3):
    err = np.zeros(6)
    err[:3] = target_pos - ik_data.site_xpos[site_id]
    site_mat = ik_data.site_xmat[site_id].reshape(3, 3)
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, (target_mat @ site_mat.T).flatten())
    rotvec = np.zeros(3)
    mujoco.mju_quat2Vel(rotvec, quat, 1.0)
    err[3:] = rotvec
    jacp = np.zeros((3, model.nv)); jacr = np.zeros((3, model.nv))
    mujoco.mj_jacSite(model, ik_data, jacp, jacr, site_id)
    jac = np.vstack([jacp, jacr])[:, dof_ids]
    dq = jac.T @ np.linalg.solve(jac @ jac.T + damping**2 * np.eye(6), gain * err)
    return dq, np.linalg.norm(err[:3])

def wrap_pi(a):
    return (a + np.pi) % (2 * np.pi) - np.pi

def nearest_mod_pi(desired, reference):
    """angle congruent to desired (mod pi) closest to reference (lugs are 2-fold symmetric)"""
    best = None
    for k in (-2, -1, 0, 1, 2):
        cand = desired + k * np.pi
        if best is None or abs(wrap_pi(cand - reference)) < abs(wrap_pi(best - reference)):
            best = cand
    return best

# ----------------------------------------------------------------- trial
def run_trial(seed, frame_cb=None):
    rng = np.random.default_rng(seed)
    model = mujoco.MjModel.from_xml_path(XML)
    data = mujoco.MjData(model)

    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "link_tcp")
    cart_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cartridge")
    arm_joints = [f"joint{i}" for i in range(1, 8)]
    dof_ids = np.array([model.joint(n).dofadr[0] for n in arm_joints])
    qpos_ids = np.array([model.joint(n).qposadr[0] for n in arm_joints])
    act_ids = np.array([model.actuator(f"act{i}").id for i in range(1, 8)])
    grip_id = model.actuator("gripper").id
    jnt_range = np.array([model.joint(n).range for n in arm_joints])

    mujoco.mj_resetDataKeyframe(model, data, model.key("home").id)

    # randomized spawn: position +-4 cm, yaw 0..2pi
    spawn = SPAWN_C + rng.uniform(-0.04, 0.04, 2)
    yaw0 = rng.uniform(0, 2 * np.pi)
    q = np.array([np.cos(yaw0 / 2), 0, 0, np.sin(yaw0 / 2)])
    adr = model.joint("cartridge_free").qposadr[0]
    data.qpos[adr:adr + 3] = [*spawn, SPAWN_Z + 0.002]
    data.qpos[adr + 3:adr + 7] = q
    mujoco.mj_forward(model, data)

    # ---- simulated perception (pose from sim + gaussian noise)
    detected = spawn + rng.normal(0, PERCEPTION_NOISE, 2)
    cart_x_world = data.xmat[cart_id].reshape(3, 3)[:, 0]
    detected_yaw = np.arctan2(cart_x_world[1], cart_x_world[0]) \
        + rng.normal(0, np.deg2rad(1.0))

    # yaw plan: grasp at a comfortable wrist angle (cylinder = yaw-agnostic),
    # then CLOSED-LOOP servo the cartridge's lug axis onto the slot axis
    # (world y, i.e. pi/2 mod pi) during transit/align — robust to in-grip slip.
    grasp_yaw = 0.0
    LUG_TARGET = np.pi / 2  # slots are along world y

    GRIP_OPEN, GRIP_CLOSED = 0.0, 240.0
    grasp_z = SPAWN_Z + GRASP_OFF
    seat_tcp = 0.110   # fingertips 10 mm above the collar; part settles on release

    # phase table: (name, tcp_xyz, grip, dwell_s, tol_m, speed_scale, servo, max_s)
    P = [
        ("PERCEPTION",      None,               GRIP_OPEN,   0.8, None,  1.0, False, 2.0),
        ("APPROACH",        [*detected, 0.28],  GRIP_OPEN,   0.1, 0.015, 1.0, False, 6.0),
        ("DESCEND",         [*detected, grasp_z], GRIP_OPEN, 0.3, 0.008, 0.6, False, 5.0),
        ("GRASP",           [*detected, grasp_z], GRIP_CLOSED, 1.2, 0.012, 1.0, False, 3.0),
        ("LIFT",            [*detected, 0.35],  GRIP_CLOSED, 0.2, 0.020, 1.0, False, 4.0),
        ("TRANSIT",         [*SOCK, 0.35],      GRIP_CLOSED, 0.5, 0.012, 0.5, False, 8.0),
        # --- stall recovery (FIX 3). These two are SKIPPED on the normal forward
        # path and are only ever entered by the retry jump below. The old retry set
        # wp straight back to ORIENT LUGS, whose target is z=0.24, so the arm
        # ascended while the part might still be hooked under the collar rim -- and
        # if the retry came from DROP-SEAT the gripper was OPEN, so it went back to
        # "orient" holding nothing. Re-grip first, THEN lift clear, then re-approach.
        ("RECOVER GRIP",    [*SOCK, 0.131],     GRIP_CLOSED, 0.6, 0.012, 0.5, False, 3.0),
        ("RECOVER LIFT",    [*SOCK, 0.30],      GRIP_CLOSED, 0.3, 0.020, 0.6, False, 6.0),
        ("ORIENT LUGS",     [*SOCK, 0.24],      GRIP_CLOSED, 1.2, 0.005, 0.6, True, 16.0),
        ("PRE-INSERT",      [*SOCK, 0.19],      GRIP_CLOSED, 0.6, 0.004, 0.25, True, 14.0),
        ("INSERT",          [*SOCK, 0.126],     GRIP_CLOSED, 0.3, 0.005, 0.12, True, 14.0),
        ("DROP-SEAT",       [*SOCK, 0.126],     GRIP_OPEN,   0.8, 0.005, 0.3, False, 4.0),
        ("REGRIP ALIGN",    [*SOCK, 0.131],     GRIP_OPEN,   0.4, 0.003, 0.3, False, 6.0),
        ("REGRIP CAP",      [*SOCK, 0.131],     GRIP_CLOSED, 1.0, 0.012, 0.5, False, 3.0),
        ("TWIST-LOCK",      [*SOCK, 0.131],     GRIP_CLOSED, 1.4, 0.006, 0.5, False, 4.0),
        ("RELEASE",         [*SOCK, 0.131],     GRIP_OPEN,   0.8, 0.012, 1.0, False, 3.0),
        ("RETREAT",         [*SOCK, 0.34],      GRIP_OPEN,   0.4, 0.030, 1.0, False, 4.0),
    ]
    # phases whose xy target tracks the PART rather than the socket axis. RECOVER
    # GRIP is here because a wedged part sits 20-35 mm off-axis: the jaws have to go
    # to where the part actually is, not where it was supposed to end up.
    FOLLOW = ("DROP-SEAT", "REGRIP ALIGN", "REGRIP CAP", "TWIST-LOCK", "RELEASE",
              "RECOVER GRIP")
    # phases whose dwell timer demands the completion condition hold CONTINUOUSLY
    # rather than cumulatively (see FIX 4 below).
    CONTINUOUS_DWELL = ("INSERT",)

    q_des = data.qpos[qpos_ids].copy()
    ik_data = mujoco.MjData(model)
    dt = model.opt.timestep
    base_step = 2.0 * dt

    wp, dwell_left, phase_t = 0, P[0][3], 0.0
    t_limit = 60.0
    retries = 0
    servo_yaw = grasp_yaw          # commanded gripper yaw (integrates servo corrections)
    twist_from = None
    insert_end_cart_yaw = None
    aborted = False

    def cart_yaw_now():
        cm = data.xmat[cart_id].reshape(3, 3)
        return np.arctan2(cm[1, 0], cm[0, 0])

    def cart_tip():
        cm = data.xmat[cart_id].reshape(3, 3)
        return data.xpos[cart_id] + cm @ np.array([0.0, 0.0, -CART_HALF])

    hold_e = None

    while data.time < t_limit and wp < len(P):
        name, tgt, grip, dwell, tol, spd, servo, max_s = P[wp]

        if name == "PERCEPTION":
            data.ctrl[act_ids] = q_des
            data.ctrl[grip_id] = grip
            data.qfrc_applied[dof_ids] = data.qfrc_bias[dof_ids]
            mujoco.mj_step(model, data)
            dwell_left -= dt
            if dwell_left <= 0:
                wp += 1; dwell_left = P[wp][3]; phase_t = 0.0
            if frame_cb: frame_cb(model, data, name, detected, detected_yaw, seed)
            continue

        # ---- yaw command
        if servo:
            # closed-loop: rotate wrist so the cartridge's lug axis reaches the
            # slot axis, using the MEASURED cartridge yaw (robust to grip slip)
            yaw_err = wrap_pi((LUG_TARGET - cart_yaw_now() + np.pi / 2) % np.pi - np.pi / 2)
            servo_yaw -= np.clip(yaw_err, -0.0025, 0.0025)  # cmd yaw maps to -physical yaw
        elif name == "TWIST-LOCK":
            if twist_from is None:
                twist_from = servo_yaw
                insert_end_cart_yaw = cart_yaw_now()
            frac = min(1.0, phase_t / 1.2)
            servo_yaw = twist_from + np.deg2rad(TWIST_DEG) * frac
        tmat = down_mat(servo_yaw)

        # closed-loop XY centering during align/insert: steer the TCP so the
        # CARTRIDGE (not the wrist) sits over the socket axis — absorbs any
        # off-center grip. This is what a wrist camera gives you on real hardware.
        tgt_arr = np.array(tgt, dtype=float)
        cart_xy = data.xpos[cart_id][:2]
        tcp_xy = data.site_xpos[site_id][:2]
        if name != "INSERT":
            hold_e = None
        if servo:
            if name == "INSERT":
                tip = cart_tip()
                if hold_e is None:
                    hold_e = np.clip(tcp_xy - tip[:2], -GRIP_ECC_MAX, GRIP_ECC_MAX)
                tgt_arr[:2] = tip[:2] + hold_e
                tgt_arr[2] = max(tgt_arr[2], data.site_xpos[site_id][2] - Z_LAG)
            else:
                tgt_arr[:2] = tcp_xy + (SOCK - cart_xy)
        elif name in FOLLOW:
            # stay centered over the (seated) part for drop, regrip, twist
            tgt_arr[:2] = cart_xy

        ik_data.qpos[:] = data.qpos
        ik_data.qpos[qpos_ids] = q_des
        mujoco.mj_kinematics(model, ik_data)
        mujoco.mj_comPos(model, ik_data)
        dq, _ = ik_step(model, ik_data, site_id, tgt_arr, tmat, dof_ids)
        ms = base_step * spd
        mx = np.max(np.abs(dq))
        if mx > ms:
            dq = dq * (ms / mx)
        q_des = np.clip(q_des + dq, jnt_range[:, 0], jnt_range[:, 1])
        data.ctrl[act_ids] = q_des
        data.ctrl[grip_id] = grip
        data.qfrc_applied[dof_ids] = data.qfrc_bias[dof_ids]
        mujoco.mj_step(model, data)
        phase_t += dt

        yaw_ok = True
        if servo:
            yaw_ok = abs(wrap_pi((LUG_TARGET - cart_yaw_now() + np.pi / 2) % np.pi - np.pi / 2)) < np.deg2rad(4)

        # phase completion: judged on the PART where it matters, else on the TCP
        if name == "TWIST-LOCK":
            done = phase_t > 1.2
        elif name in ("ORIENT LUGS", "PRE-INSERT"):
            cart_xy_err = np.linalg.norm(data.xpos[cart_id][:2] - SOCK)
            z_err = abs(data.site_xpos[site_id][2] - tgt_arr[2])
            hanging_straight = data.xmat[cart_id].reshape(3, 3)[2, 2] > 0.9986  # tilt < 3 deg
            done = cart_xy_err < ENTRY_TOL and z_err < 0.008 and yaw_ok and hanging_straight
        elif name == "INSERT":
            # Judge the PART, not just the wrist (FIX 2). The TCP-height term alone
            # cannot tell "inserted" from "jammed with the wrist pushed past it".
            insert_upright = data.xmat[cart_id].reshape(3, 3)[2, 2] > INSERT_UPRIGHT
            insert_deep = data.xpos[cart_id][2] < INSERT_DEPTH_Z
            done = (data.site_xpos[site_id][2] < 0.129   # fingertips past the chamfer
                    and insert_upright and insert_deep)
        elif name == "DROP-SEAT":
            done = data.xpos[cart_id][2] < SEAT_Z + 0.008  # part fell to seat
        else:
            done = np.linalg.norm(tgt_arr - data.site_xpos[site_id]) < tol and yaw_ok
        if done:
            dwell_left -= dt
        elif name in CONTINUOUS_DWELL:
            # FIX 4: require the condition to hold CONTINUOUSLY, for INSERT only.
            # dwell_left is otherwise reset only on a phase change, so it decrements
            # on any step where `done` momentarily holds -- a jammed insert whose TCP
            # oscillated around the 129 mm threshold could burn the whole 0.3 s dwell
            # on transient touches and "complete" without the condition ever being
            # true for a sustained moment.
            #
            # Scoped deliberately. Applying this to every phase drops the success
            # rate to 4%: ORIENT LUGS and PRE-INSERT gate on a part that is still
            # swinging like a pendulum, and for them the cumulative dwell is the
            # CORRECT semantic -- it accumulates evidence that the swing is decaying.
            # Only INSERT was certifying a settled state it had not actually reached.
            dwell_left = dwell
        if dwell_left <= 0:
            wp += 1; phase_t = 0.0
            # RECOVER phases are reachable only via the retry jump below.
            while wp < len(P) and P[wp][0].startswith("RECOVER"):
                wp += 1
            if wp < len(P): dwell_left = P[wp][3]
        elif phase_t > max_s:
            # FIX 3: a wedge is usually detected at DROP-SEAT (the part never falls
            # to the seat), not at INSERT. The old code only retried on an INSERT
            # timeout, so the common failure aborted immediately with its retry
            # budget untouched -- seed 21 died having used 0 of 2.
            if name in ("INSERT", "DROP-SEAT") and retries < 2:
                retries += 1
                wp = next(i for i, p in enumerate(P) if p[0] == "RECOVER GRIP")
                dwell_left, phase_t = P[wp][3], 0.0
                continue
            aborted = True
            break

        if frame_cb: frame_cb(model, data, name, detected, detected_yaw, seed)

    # ---- verification
    cpos = data.xpos[cart_id]
    cmat = data.xmat[cart_id].reshape(3, 3)
    xy_off = np.linalg.norm(cpos[:2] - SOCK)
    upright = cmat[2, 2]
    final_yaw = np.arctan2(cmat[1, 0], cmat[0, 0])
    if insert_end_cart_yaw is not None:
        rel_twist = abs(np.rad2deg(wrap_pi(final_yaw - insert_end_cart_yaw)))
    else:
        rel_twist = 0.0
    seated = (not aborted) and xy_off < 0.006 and cpos[2] < SEAT_Z + 0.008 and upright > 0.95
    locked = seated and rel_twist > 30.0
    return {
        "seed": int(seed), "spawn": spawn.tolist(), "spawn_yaw_deg": float(np.rad2deg(yaw0) % 360),
        "xy_offset_mm": float(xy_off * 1000), "height_mm": float(cpos[2] * 1000),
        "upright": float(upright), "twist_deg": float(rel_twist),
        "seated": bool(seated), "locked": bool(locked), "aborted": bool(aborted),
        "retries": int(retries),
        "cycle_s": float(data.time), "phases_done": int(wp),
    }

# ----------------------------------------------------------------- rendering
# Font resolution used to be three hardcoded Linux DejaVu paths, which meant every
# --render and --cards call died with FileNotFoundError on macOS before drawing a
# single frame. Resolve across platforms instead, and degrade to PIL's built-in
# font rather than crashing.
_FONTS = {
    "mono":      ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                  "/System/Library/Fonts/Menlo.ttc",
                  "/System/Library/Fonts/Supplemental/Courier New.ttf",
                  "C:/Windows/Fonts/consola.ttf"],
    "mono_bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                  "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
                  "/System/Library/Fonts/Menlo.ttc",
                  "C:/Windows/Fonts/consolab.ttf"],
    "sans":      ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                  "/System/Library/Fonts/Supplemental/Arial.ttf",
                  "/System/Library/Fonts/Helvetica.ttc",
                  "C:/Windows/Fonts/arial.ttf"],
    "sans_bold": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                  "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                  "/System/Library/Fonts/Helvetica.ttc",
                  "C:/Windows/Fonts/arialbd.ttf"],
}

def _font(kind, size):
    from PIL import ImageFont
    for path in _FONTS[kind]:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    try:
        return ImageFont.load_default(size)
    except TypeError:            # Pillow < 10 has no size argument
        return ImageFont.load_default()

def make_frame_cb(frames, model):
    from PIL import Image, ImageDraw, ImageFont
    main_r = mujoco.Renderer(model, 720, 1280)
    wrist_r = mujoco.Renderer(model, 216, 288)
    font = _font("mono", 20)
    font_b = _font("mono_bold", 22)
    font_s = _font("mono", 15)
    state = {"n": 0}
    steps_per_frame = max(1, int(round(1.0 / FPS / model.opt.timestep)))

    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "link_tcp")
    cart_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cartridge")

    def cb(m, d, phase, detected, det_yaw, seed):
        state["n"] += 1
        if state["n"] % steps_per_frame: return
        main_r.update_scene(d, camera="main")
        img = Image.fromarray(main_r.render())
        wrist_r.update_scene(d, camera="wrist")
        wr = Image.fromarray(wrist_r.render())
        draw = ImageDraw.Draw(img, "RGBA")

        # wrist cam PiP
        px, py = 1280 - 288 - 16, 720 - 216 - 16
        draw.rectangle([px - 3, py - 3, px + 288 + 3, py + 216 + 3], fill=(255, 255, 255, 220))
        img.paste(wr, (px, py))
        draw.text((px + 6, py + 4), "WRIST CAM", font=font_s, fill=(255, 255, 255, 230))

        # HUD
        tcp = d.site_xpos[site_id]; cart = d.xpos[cart_id]
        err = np.linalg.norm(cart[:2] - SOCK) * 1000
        grip_state = "CLOSED" if d.ctrl[mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_ACTUATOR, "gripper")] > 100 else "OPEN"
        cmat = d.xmat[cart_id].reshape(3, 3)
        cyaw = np.degrees(np.arctan2(cmat[1, 0], cmat[0, 0]))
        lines = [
            f"PHASE  {phase}",
            f"t      {d.time:6.2f} s",
            f"TCP    x{tcp[0]*1000:7.1f}  y{tcp[1]*1000:7.1f}  z{tcp[2]*1000:6.1f} mm",
            f"PART   detected ({detected[0]*1000:.0f}, {detected[1]*1000:.0f}) mm  th {np.degrees(det_yaw):5.1f} deg",
            f"CART->SOCKET  {err:6.1f} mm   yaw {cyaw:6.1f} deg",
            f"GRIPPER {grip_state}   clearance 3.0 mm   lock {TWIST_DEG:.0f} deg",
        ]
        draw.rectangle([12, 12, 640, 12 + 24 + len(lines) * 26], fill=(10, 14, 20, 175))
        draw.text((24, 20), f"CARTRIDGE CELL - SIM TRIAL (seed {seed})", font=font_b, fill=(120, 200, 255, 255))
        for i, ln in enumerate(lines):
            draw.text((24, 50 + i * 26), ln, font=font, fill=(235, 240, 245, 255))
        frames.append(np.asarray(img).copy())
    return cb

def render_trial(idx, seed, speed):
    import imageio
    model = mujoco.MjModel.from_xml_path(XML)
    frames = []
    cb = make_frame_cb(frames, model)
    res = run_trial(seed, frame_cb=cb)
    frames = frames[::speed]
    imageio.mimsave(f"trial_{idx}.mp4", frames, fps=FPS, codec="libx264", quality=8,
                    pixelformat="yuv420p")
    print(f"trial_{idx}.mp4: {len(frames)} frames | {json.dumps(res)}")

def make_cards():
    import imageio
    from PIL import Image, ImageDraw, ImageFont
    stats = json.load(open("stats.json"))
    fb = lambda s: _font("sans_bold", s)
    fr = lambda s: _font("sans", s)

    def card(lines, fname, secs):
        img = Image.new("RGB", (1280, 720), (13, 17, 23))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 1280, 6], fill=(41, 121, 255))
        y = 150
        for txt, fnt, col in lines:
            w = d.textlength(txt, font=fnt)
            d.text(((1280 - w) / 2, y), txt, font=fnt, fill=col)
            y += fnt.size + 26
        fr_ = np.asarray(img)
        imageio.mimsave(fname, [fr_] * int(FPS * secs), fps=FPS, codec="libx264",
                        quality=8, pixelformat="yuv420p")

    card([
        ("CARTRIDGE INSERTION CELL", fb(56), (235, 240, 245)),
        ("Simulation POC v2 - bayonet twist-lock, randomized spawn", fr(28), (150, 160, 175)),
        ("Simulated UFACTORY xArm7  |  MuJoCo physics  |  scripted IK baseline", fr(24), (150, 160, 175)),
        ("", fr(10), (0, 0, 0)),
        ("Task: locate cartridge (random pose, 360 deg) -> grasp -> orient lugs", fr(24), (120, 200, 255)),
        ("-> insert at 3.0 mm clearance -> twist 55 deg to lock -> verify", fr(24), (120, 200, 255)),
        ("", fr(10), (0, 0, 0)),
        ("DrinkPrime automation study - Phase 0 (pre-hardware)", fr(22), (110, 120, 135)),
    ], "card_title.mp4", 3.0)

    n = stats["trials"]; sr = stats["locked_rate"] * 100
    card([
        ("RELIABILITY EVALUATION", fb(52), (235, 240, 245)),
        (f"{n} randomized trials (position +-40 mm, rotation 360 deg, 1 mm vision noise)", fr(26), (150, 160, 175)),
        ("", fr(10), (0, 0, 0)),
        (f"SEATED + LOCKED: {sr:.0f}%", fb(64), (80, 220, 130) if sr >= 80 else (255, 190, 80)),
        (f"avg cycle {stats['avg_cycle_s']:.1f} s   |   avg seating offset {stats['avg_xy_mm']:.1f} mm   |   avg twist {stats['avg_twist_deg']:.0f} deg", fr(26), (150, 160, 175)),
        ("", fr(10), (0, 0, 0)),
        ("Next: replace scripted IK with a learned policy", fr(26), (120, 200, 255)),
        ("(teleop demos -> LeRobot dataset -> pi0.5 fine-tune)", fr(26), (120, 200, 255)),
    ], "card_end.mp4", 4.0)
    print("cards written")

def concat():
    import subprocess, imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    parts = ["card_title.mp4", "trial_1.mp4", "trial_2.mp4", "trial_3.mp4", "card_end.mp4"]
    with open("concat.txt", "w") as f:
        for p in parts: f.write(f"file '{p}'\n")
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
                    "-c", "copy", "cartridge_cell_v2.mp4"], check=True, capture_output=True)
    print("cartridge_cell_v2.mp4 written")

# ----------------------------------------------------------------- eval
def evaluate(n):
    results = [run_trial(s) for s in range(n)]
    locked = [r for r in results if r["locked"]]
    seated = [r for r in results if r["seated"]]
    stats = {
        "trials": n,
        "seated_rate": len(seated) / n,
        "locked_rate": len(locked) / n,
        "avg_cycle_s": float(np.mean([r["cycle_s"] for r in locked])) if locked else 0,
        "avg_xy_mm": float(np.mean([r["xy_offset_mm"] for r in locked])) if locked else 0,
        "avg_twist_deg": float(np.mean([r["twist_deg"] for r in locked])) if locked else 0,
        "results": results,
    }
    json.dump(stats, open("stats.json", "w"), indent=1)
    print(f"EVAL: {n} trials | seated {stats['seated_rate']*100:.0f}% | "
          f"locked {stats['locked_rate']*100:.0f}% | avg cycle {stats['avg_cycle_s']:.1f}s")
    for r in results:
        print(f"  seed {r['seed']:2d}: {'LOCKED' if r['locked'] else 'SEATED' if r['seated'] else 'FAIL':6s}"
              f" xy={r['xy_offset_mm']:5.1f}mm z={r['height_mm']:5.1f}mm twist={r['twist_deg']:5.1f}deg"
              f" t={r['cycle_s']:5.1f}s phases={r['phases_done']:2d} retries={r['retries']}")

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
