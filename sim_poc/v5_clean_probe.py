"""V5-C probe -- why does the arm not reach its commanded pose while holding the pad?

The diagnostic (v5_clean_diag.py) split the failure two ways: the IK solves the target
exactly (commanded config puts the TCP on it) yet the MEASURED arm sits 130-400 mm away
with up to 2 rad of joint lag. That is a tracking failure, and there are only three
things it can be: something is touching the arm, the actuators are saturating, or the
gravity compensation is wrong about what the arm is carrying.

    ../venv/bin/python v5_clean_probe.py
"""
import numpy as np
import mujoco

import v5_clean as CL


def main():
    c = CL.Cell()
    m, d = c.m, c.d
    c.reset(800)
    gm = CL.grasp_mat()
    want = np.array(c.cfg.couple_tcp)

    tool = [i for i in range(m.nbody)
            if mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, i) in
            ("padtool", "padshank")]
    print("PAD TOOL MASS")
    for b in tool:
        print(f"  {mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, b):<10} "
              f"mass {m.body_mass[b]*1000:7.1f} g")
    print(f"  total {sum(m.body_mass[b] for b in tool)*1000:.1f} g  "
          f"(weight {sum(m.body_mass[b] for b in tool)*9.81:.2f} N)")

    # --- couple exactly as the real cycle does
    c.move(want + np.array([0, 0, 0.12]), gm, c.cfg.grip_open)
    c.move(want, gm, c.cfg.grip_open, tol=0.003, t_max=8.0)
    latched, perr, aerr = c.couple()
    c.move(want + np.array([0, 0, 0.14]), gm, c.cfg.grip_open, t_max=8.0)
    print(f"\nlatched={latched}  perr={perr*1000:.2f} mm  aerr={aerr:.2f} deg")

    # --- now the first move that fails in the real cycle
    safe = np.array([0.26, 0.0, 0.42])
    tm = CL.tool_mat_face(0.0)
    print(f"\nDriving to SAFE {safe} with the tool pointing +X "
          f"(the orientation every face pass uses)")
    hdr = (f"  {'t':>5} {'err mm':>8} {'IK mm':>7} {'lag rad':>8} {'sat':>4} "
           f"{'contacts on arm/tool':>22} {'|constraint N|':>14}")
    print(hdr)
    t = 0.0
    armbodies = set()
    for b in range(m.nbody):
        nm = mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, b) or ""
        if nm.startswith(("link", "xarm", "left_", "right_", "pad")):
            armbodies.add(b)
    while t < 8.0:
        c.step_to(safe, tm, c.cfg.grip_open, 0.0)
        t += c.dt
        if abs(t % 1.0) < c.dt / 2 or t < c.dt * 2:
            c.ik.qpos[:] = d.qpos
            c.ik.qpos[c.qadr] = c.q_des
            mujoco.mj_kinematics(m, c.ik)
            err = np.linalg.norm(d.site_xpos[c.site] - safe) * 1000
            ikerr = np.linalg.norm(c.ik.site_xpos[c.site] - safe) * 1000
            lag = np.max(np.abs(c.q_des - d.qpos[c.qadr]))
            frc = np.abs(d.actuator_force[c.act])
            lim = m.actuator_forcerange[c.act][:, 1]
            sat = int(np.sum(frc > lim * 0.98))
            hits = []
            f6 = np.zeros(6)
            for k in range(d.ncon):
                g1, g2 = d.contact[k].geom1, d.contact[k].geom2
                b1, b2 = m.geom_bodyid[g1], m.geom_bodyid[g2]
                if b1 in armbodies or b2 in armbodies:
                    bn = lambda b: mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, b)
                    mujoco.mj_contactForce(m, d, k, f6)
                    hits.append(f"{bn(b1)}~{bn(b2)}@{abs(f6[0]):.0f}N")
            print(f"  {t:5.1f} {err:8.1f} {ikerr:7.1f} {lag:8.3f} {sat:4d} "
                  f"{len(hits):>4}  {','.join(sorted(set(hits))[:2]):<28} "
                  f"{np.linalg.norm(d.qfrc_constraint[c.dof]):8.2f}")

    print("\nPER-JOINT at the end of the move")
    print(f"  {'joint':>6} {'cmd rad':>9} {'meas rad':>9} {'lag':>8} "
          f"{'torque':>8} {'limit':>7} {'bias':>8}")
    for i in range(7):
        a = c.act[i]
        print(f"  {i+1:>6} {c.q_des[i]:9.3f} {d.qpos[c.qadr[i]]:9.3f} "
              f"{c.q_des[i]-d.qpos[c.qadr[i]]:8.3f} "
              f"{d.actuator_force[a]:8.2f} {m.actuator_forcerange[a][1]:7.1f} "
              f"{d.qfrc_bias[c.dof[i]]:8.2f}")

    # --- does the gravity compensation know about the welded tool?
    print("\nGRAVITY COMPENSATION vs the load actually carried")
    bias = d.qfrc_bias[c.dof].copy()
    con = d.qfrc_constraint[c.dof].copy()
    print(f"  qfrc_bias  (what we compensate) : {np.round(bias, 2)}")
    print(f"  qfrc_constraint (weld + contact): {np.round(con, 2)}")
    print(f"  |bias| {np.linalg.norm(bias):.2f}   |constraint| {np.linalg.norm(con):.2f}")
    print("  The weld carries the tool. If |constraint| is large and un-compensated,")
    print("  the position servo must fight it with proportional error -- i.e. sag.")


if __name__ == "__main__":
    main()
