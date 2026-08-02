"""
Sim POC: xArm7 picks up a filter cartridge and inserts it into a socket.
Scripted controller using damped-least-squares inverse kinematics (IK).

Run:  MUJOCO_GL=egl python3 sim_poc.py        (headless, writes cartridge_insertion.mp4)
      python3 sim_poc.py --view               (interactive viewer, if you have a display)

This is Phase 0 of the DrinkPrime POC: prove the motion in simulation for ~$0
before buying hardware. Phase 1 replaces this scripted controller with a
learned policy (teleop demos -> LeRobot format -> fine-tuned pi0.5 / ACT).
"""

import argparse
import numpy as np
import mujoco

XML = "ufactory_xarm7/cartridge_scene.xml"
FPS = 30

# ---------------------------------------------------------------- IK utilities
def ik_step(model, ik_data, site_id, target_pos, target_mat, dof_ids, damping=0.1, gain=0.3):
    """One velocity-level IK step toward a 6D target, computed on the PLANNED
    configuration in ik_data (not the lagging measured state). Returns joint deltas."""
    err = np.zeros(6)
    # position error
    err[:3] = target_pos - ik_data.site_xpos[site_id]
    # orientation error (rotation vector taking current to target)
    site_mat = ik_data.site_xmat[site_id].reshape(3, 3)
    err_rot_mat = target_mat @ site_mat.T
    quat = np.zeros(4)
    mujoco.mju_mat2Quat(quat, err_rot_mat.flatten())
    rotvec = np.zeros(3)
    mujoco.mju_quat2Vel(rotvec, quat, 1.0)
    err[3:] = rotvec

    jacp = np.zeros((3, model.nv))
    jacr = np.zeros((3, model.nv))
    mujoco.mj_jacSite(model, ik_data, jacp, jacr, site_id)
    jac = np.vstack([jacp, jacr])[:, dof_ids]

    # damped least squares
    dq = jac.T @ np.linalg.solve(jac @ jac.T + damping**2 * np.eye(6), gain * err)
    return dq, np.linalg.norm(err[:3]), np.linalg.norm(err[3:])


def down_mat(yaw=0.0):
    """TCP orientation: z-axis pointing straight down, x rotated by yaw."""
    c, s = np.cos(yaw), np.sin(yaw)
    return np.array([[c, -s, 0], [-s, -c, 0], [0, 0, -1.0]]).T


# ---------------------------------------------------------------- main routine
def main(interactive=False):
    model = mujoco.MjModel.from_xml_path(XML)
    data = mujoco.MjData(model)

    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "link_tcp")
    cart_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cartridge")
    arm_joints = [f"joint{i}" for i in range(1, 8)]
    dof_ids = np.array([model.joint(n).dofadr[0] for n in arm_joints])
    qpos_ids = np.array([model.joint(n).qposadr[0] for n in arm_joints])
    act_ids = np.array([model.actuator(f"act{i}").id for i in range(1, 8)])
    grip_id = model.actuator("gripper").id

    # start from the home keyframe (arm only), then place the cartridge —
    # the keyframe predates our free-floating cartridge, so set its pose explicitly
    key = model.key("home").id
    mujoco.mj_resetDataKeyframe(model, data, key)
    free_adr = model.joint("cartridge_free").qposadr[0]
    data.qpos[free_adr:free_adr + 7] = [0.46, -0.26, 0.062, 1, 0, 0, 0]
    mujoco.mj_forward(model, data)

    cart_xy = np.array([0.46, -0.26])
    sock_xy = np.array([0.46, 0.26])

    GRIP_OPEN, GRIP_CLOSED = 0.0, 235.0
    TCP_GRASP_Z = 0.090      # grasp point: fingers wrap the cylinder's upper half
    TCP_TRAVEL_Z = 0.35
    TCP_INSERT_Z = 0.120     # cartridge deep in the socket, fingers clear of walls

    # (label, tcp target, gripper, dwell seconds, position tolerance)
    W = [
        ("hover over cartridge", np.array([*cart_xy, 0.28]), GRIP_OPEN,   0.1, 0.015),
        ("descend to grasp",     np.array([*cart_xy, TCP_GRASP_Z]), GRIP_OPEN, 0.3, 0.008),
        ("close gripper",        np.array([*cart_xy, TCP_GRASP_Z]), GRIP_CLOSED, 1.2, 0.012),
        ("lift",                 np.array([*cart_xy, TCP_TRAVEL_Z]), GRIP_CLOSED, 0.2, 0.020),
        ("carry to socket",      np.array([*sock_xy, TCP_TRAVEL_Z]), GRIP_CLOSED, 0.3, 0.012),
        ("align over socket",    np.array([*sock_xy, 0.26]), GRIP_CLOSED, 0.5, 0.006),
        ("insert",               np.array([*sock_xy, TCP_INSERT_Z]), GRIP_CLOSED, 0.5, 0.006),
        ("release",              np.array([*sock_xy, TCP_INSERT_Z]), GRIP_OPEN, 1.0, 0.012),
        ("retreat",              np.array([*sock_xy, 0.35]), GRIP_OPEN, 0.5, 0.03),
    ]

    target_mat = down_mat(yaw=np.pi / 2)  # fingers straddle the cylinder
    frames, captions = [], []
    renderer = None if interactive else mujoco.Renderer(model, 720, 1280)

    dt = model.opt.timestep
    steps_per_frame = max(1, int(round(1.0 / FPS / dt)))
    sim_time_limit = 40.0

    wp_idx, dwell_left = 0, W[0][3]
    step_count = 0
    success = False

    # kinematic planner: IK runs on a separate MjData holding the COMMANDED
    # configuration, so the plan is smooth and gravity sag is compensated
    # by the position actuators tracking it.
    q_des = data.qpos[qpos_ids].copy()
    jnt_range = np.array([model.joint(n).range for n in arm_joints])
    ik_data = mujoco.MjData(model)

    MAX_STEP = 2.0 * dt  # max joint speed ~2 rad/s

    while data.time < sim_time_limit and wp_idx < len(W):
        label, target, grip, dwell, tol = W[wp_idx]

        # plan on the commanded configuration
        ik_data.qpos[:] = data.qpos
        ik_data.qpos[qpos_ids] = q_des
        mujoco.mj_kinematics(model, ik_data)
        mujoco.mj_comPos(model, ik_data)

        dq, pos_err, rot_err = ik_step(model, ik_data, site_id, target, target_mat, dof_ids)
        dq = np.clip(dq, -MAX_STEP, MAX_STEP)
        q_des = np.clip(q_des + dq, jnt_range[:, 0], jnt_range[:, 1])
        data.ctrl[act_ids] = q_des

        # gravity compensation so the position servos track without sag
        data.qfrc_applied[dof_ids] = data.qfrc_bias[dof_ids]
        data.ctrl[grip_id] = grip

        mujoco.mj_step(model, data)
        step_count += 1

        # gate waypoint advancement on the ACTUAL arm position, not the plan
        actual_err = np.linalg.norm(target - data.site_xpos[site_id])
        if actual_err < tol and rot_err < 0.1:
            dwell_left -= dt
            if dwell_left <= 0:
                wp_idx += 1
                if wp_idx < len(W):
                    dwell_left = W[wp_idx][3]

        if renderer is not None and step_count % steps_per_frame == 0:
            renderer.update_scene(data, camera="main")
            frames.append(renderer.render())
            captions.append(label)

    # --- success check: cartridge inside socket?
    cart_pos = data.xpos[cart_id]
    xy_off = np.linalg.norm(cart_pos[:2] - np.array([0.46, 0.26]))
    upright = data.xmat[cart_id].reshape(3, 3)[2, 2]
    success = xy_off < 0.02 and cart_pos[2] < 0.09 and upright > 0.9
    print(f"RESULT: {'SUCCESS' if success else 'FAIL'} | "
          f"cartridge xy-offset from socket center: {xy_off*1000:.1f} mm | "
          f"height: {cart_pos[2]*1000:.0f} mm | uprightness: {upright:.3f} | "
          f"sim time: {data.time:.1f}s | reached waypoint {wp_idx}/{len(W)}")

    if renderer is not None and frames:
        import imageio
        # hold the last frame for a second
        frames.extend([frames[-1]] * FPS)
        imageio.mimsave("cartridge_insertion.mp4", frames, fps=FPS,
                        codec="libx264", quality=8)
        print(f"wrote cartridge_insertion.mp4 ({len(frames)} frames)")
    return success


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--view", action="store_true")
    args = p.parse_args()
    main(interactive=args.view)
