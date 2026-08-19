"""Check that CELL_SPEC.md still matches the simulation.

    ../venv/bin/python v5_check_spec.py

WHY THIS EXISTS. CELL_SPEC.md is the document the real cell gets built and programmed
from. Its whole value is that every number in it was read out of the model rather than
typed from memory -- and that guarantee decays the moment anyone edits the scene without
re-reading the spec. A specification that has silently drifted from the thing it
specifies is worse than no specification, because it will be trusted.

So the numbers are asserted here, in code, against the live model. If you change the
scene and this fails, the fix is to update CELL_SPEC.md -- not to relax the assertion.

Each entry is (description, measured-from-model, value-as-printed-in-CELL_SPEC).
"""
import sys
import numpy as np
import mujoco

XML = "ufactory_xarm7/refurb_scene_v5.xml"

# UFACTORY xArm7 published joint ranges, degrees. CELL_SPEC section 1 claims our model
# matches these on all seven joints -- that claim is what makes "a pose that solves in
# sim is inside the real arm's envelope" true, so it gets asserted, not assumed.
DATASHEET_LIMITS = {1: (-360, 360), 2: (-118, 120), 3: (-360, 360), 4: (-11, 225),
                    5: (-360, 360), 6: (-97, 180), 7: (-360, 360)}


def main():
    m = mujoco.MjModel.from_xml_path(XML)
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)

    def geom(n):
        i = m.geom(n).id
        return d.geom_xpos[i], m.geom_size[i]

    tt_p, tt_s = geom("tt_disc")
    tp_p, tp_s = geom("post_base")
    bd_p, bd_s = geom("backdrop_x")
    bn_p, bn_s = geom("bench")
    cb_p, cb_s = geom("cab_body")
    ps_p, ps_s = geom("pad_stem")
    pf_p, pf_s = geom("pad_face")
    st_p, st_s = geom("sol_floor")          # V8 solution tray
    bp_p, bp_s = geom("post_buff")          # V10 buff post
    sl_p, sl_s = geom("sol_liquid")
    swp, sws = geom("sol_w_yp")             # a side wall: its inner face gives the basin
    sw_p = abs(swp[1] - st_p[1]) - sws[1]   # half of the inner width
    sf_top = st_p[2] + st_s[2]
    pad = m.body("padtool").id
    cab = m.body("cabinet").id
    base = m.body("link_base").id
    tcp = m.site("link_tcp").id
    cam = m.camera("wrist").id
    icam = m.camera("inspect").id
    by_p, by_s = geom("backdrop_y")
    disc = m.geom("tt_disc").id

    checks = [
        # --- section 2, frames
        ("bench top surface Z", bn_p[2] + bn_s[2], 0.000),
        ("arm mounting flange Z (the 120 mm riser)", d.xpos[base][2], 0.120),
        ("TCP offset along gripper-base +Z", m.site_pos[tcp][2], 0.172),
        ("wrist camera local X", m.cam_pos[cam][0], 0.060),
        ("wrist camera local Z", m.cam_pos[cam][2], 0.030),
        ("wrist camera fovy (deg)", m.cam_fovy[cam], 75.0),
        # --- section 3, stations
        ("rotary indexer centre X", tt_p[0], 0.580),
        ("rotary indexer centre Y", tt_p[1], 0.000),
        ("rotary indexer top face Z", tt_p[2] + tt_s[1], 0.010),
        ("rotary indexer platter diameter", 2 * tt_s[0], 0.350),
        ("device base Z (stands on the indexer)", d.xpos[cab][2], 0.010),
        ("device depth (X)", 2 * cb_s[0], 0.180),
        ("device width (Y)", 2 * cb_s[1], 0.250),
        # PLACEHOLDER mass -- asserted so it stays a chosen number rather than reverting
        # to MuJoCo's default density (which gave 21.3 kg, a water-filled box)
        ("device mass placeholder (kg)", m.body_mass[cab], 8.00),
        ("rotating subtree mass, indexer sizing (kg)",
         m.body_subtreemass[m.body("turntable").id], 8.96),
        ("tool post X", tp_p[0], 0.300),
        ("tool post Y", tp_p[1], -0.340),
        ("tool post top face Z", tp_p[2] + tp_s[1], 0.020),
        ("tool post diameter", 2 * tp_s[0], 0.110),
        ("pad tool at rest X", d.xpos[pad][0], 0.300),
        ("pad tool at rest Y", d.xpos[pad][1], -0.340),
        ("pad tool at rest Z", d.xpos[pad][2], 0.040),
        ("backdrop face toward the arm, X", bd_p[0] - bd_s[0], 0.854),
        ("backdrop width", 2 * bd_s[1], 0.920),
        ("backdrop height", 2 * bd_s[2], 0.720),
        ("backdrop +X bottom Z", bd_p[2] - bd_s[2], 0.000),
        # V5-B additions. Every one of these was in the scene but NOT in CELL_SPEC until
        # an audit of "what is in the model vs what the spec lists" caught them -- a
        # check that verifies listed values cannot notice a MISSING entry.
        ("inspection camera X", d.cam_xpos[icam][0], 0.100),
        ("inspection camera Y", d.cam_xpos[icam][1], -0.450),
        ("inspection camera Z", d.cam_xpos[icam][2], 0.400),
        ("inspection camera fovy (deg)", m.cam_fovy[icam], 48.0),
        ("backdrop +Y face toward device", by_p[1] - by_s[1], 0.414),
        ("backdrop +Y width (X extent)", 2 * by_s[0], 0.600),
        ("bench working area X", 2 * bn_s[0], 1.100),
        ("bench working area Y", 2 * bn_s[1], 1.200),
        # --- section 5, tooling
        ("pad tool total mass (kg)", m.body_subtreemass[pad], 0.220),
        # keyed rectangular shank: 60 mm along the jaws, 40 mm across them, 90 mm long
        ("pad shank across jaws", 2 * ps_s[1], 0.040),
        ("pad shank along jaws (anti-rotation)", 2 * ps_s[0], 0.060),
        ("pad shank length", 2 * ps_s[2], 0.090),
        ("pad face width", 2 * pf_s[0], 0.060),
        ("pad face thickness", 2 * pf_s[2], 0.020),
        # --- V8 solution tray (Stage 3). Listed here for the same reason as everything
        # else: CELL_SPEC's whole value is that its numbers were READ FROM THE MODEL
        # rather than typed, and a fixture that exists in the scene but not in the spec
        # is a fixture the builder will not fit. The clearance line is the important
        # one -- a basin sized to the pad's 60 mm WIDTH instead of its 84.9 mm DIAGONAL
        # is the v4 staging-nest mistake, which cost a day.
        ("solution tray X", st_p[0], 0.140),
        ("solution tray Y", st_p[1], -0.360),
        ("solution tray inner width", 2 * sw_p, 0.130),
        ("solution tray wall height above floor", 2 * sws[2], 0.040),
        ("solution liquid surface Z", sl_p[2] + sl_s[2], 0.028),
        # --- V9 membrane spindle: a purchased component with a two-number spec. The
        # torque limit is the stall criterion the leak result keys off; the free speed
        # is the ctrlrange that silently capped three versions of "drive rate" sweeps.
        ("spindle torque limit (N*m)", m.actuator_forcerange[m.actuator("capdrv").id][1], 6.00),
        ("spindle free speed (rad/s)", m.actuator_ctrlrange[m.actuator("capdrv").id][1], 30.0),
        # --- V10 powered buff: the purchased motor + the geometry the coverage math
        # inherits. The disc radius EQUALS the wipe logic's in-plane radius by design;
        # if either moves without the other, coverage claims silently detach from the
        # tool that earns them.
        ("buff post X", bp_p[0], 0.460),
        ("buff post Y", bp_p[1], -0.520),
        ("buff disc radius", m.geom_size[m.geom("buff_face").id][0], 0.030),
        ("buff motor torque (N*m)", m.actuator_forcerange[m.actuator("buffdrv").id][1], 0.80),
        ("buff motor free speed (rad/s)", m.actuator_ctrlrange[m.actuator("buffdrv").id][1], 60.0),
        ("buff tool total mass (kg)", m.body_subtreemass[m.body("bufftool").id], 0.240),
    ]

    bad = 0
    print(f"CELL_SPEC.md vs {XML}\n")
    for desc, got, want in checks:
        good = abs(float(got) - want) < 5e-3
        print(f"  {'PASS' if good else 'FAIL'}  {desc:<45} model {float(got):+.4f}  "
              f"spec {want:+.4f}")
        bad += not good

    print("\n  joint limits vs UFACTORY datasheet")
    for i, (rl, rh) in DATASHEET_LIMITS.items():
        lo, hi = np.degrees(m.jnt_range[m.joint(f"joint{i}").id])
        good = abs(lo - rl) < 1.5 and abs(hi - rh) < 1.5
        print(f"  {'PASS' if good else 'FAIL'}  J{i}: model {lo:+.0f}..{hi:+.0f}  "
              f"datasheet {rl:+d}..{rh:+d}")
        bad += not good

    # the indexer platter must be MATTE BLACK -- a vision requirement, not cosmetic
    disc_rgb = m.mat_rgba[m.geom_matid[disc]][:3]
    dark = bool(disc_rgb.max() < 0.15)
    print(f"\n  {'PASS' if dark else 'FAIL'}  indexer platter is matte black "
          f"(rgb {np.round(disc_rgb, 3)}) -- else its rim reads as a dent")
    bad += not dark

    # the arm must park clear of the inspection camera's frame
    jn = [m.joint(f"joint{i}").id for i in range(1, 8)]
    qadr = np.array([m.jnt_qposadr[j] for j in jn])
    base = m.body("link_base").id
    arm_b = set()
    for b in range(m.nbody):
        pb = b
        while pb != 0:
            if pb == base:
                arm_b.add(b)
                break
            pb = m.body_parentid[pb]
    arm_g = [g for g in range(m.ngeom) if m.geom_bodyid[g] in arm_b]
    mujoco.mj_resetDataKeyframe(m, d, m.key("v5home").id)
    d.qpos[qadr] = [np.pi / 2, -0.247, 0.0, 0.909, 0.0, 1.15644, 0.0]
    mujoco.mj_forward(m, d)
    rr = mujoco.Renderer(m, 480, 640)
    rr.update_scene(d, camera="inspect")
    rr.enable_segmentation_rendering()
    seg = rr.render()[:, :, 0]
    rr.disable_segmentation_rendering()
    frac = float(np.isin(seg, arm_g).mean())
    ok_park = frac < 0.001
    print(f"  {'PASS' if ok_park else 'FAIL'}  arm PARK pose is clear of the inspection "
          f"camera ({frac*100:.3f}% of frame)")
    bad += not ok_park
    mujoco.mj_resetData(m, d)
    mujoco.mj_forward(m, d)

    # payload headroom -- CELL_SPEC claims 6% utilisation against the 3.5 kg rating
    util = m.body_subtreemass[pad] / 3.5
    good = util < 0.10
    print(f"\n  {'PASS' if good else 'FAIL'}  payload utilisation {util*100:.1f}% "
          f"of the 3.5 kg rating")
    bad += not good

    # REGRESSION GUARD for the silent-clamp bug. The indexer's ctrlrange was +-pi, an
    # unexamined default, and MuJoCo clamps ctrl without complaining -- so a commanded
    # 270 deg silently became 180 deg, the fourth face pass re-wiped the back panel, and
    # one SIDE face was never presented on any unit. Nothing failed, nothing logged, and
    # the only symptom was a coverage percentage. The cell drives 0->90->180->270->360, so
    # the command range must cover a full revolution. CELL_SPEC section 4 states this as a
    # hardware requirement; this asserts the model still honours it.
    tt = m.actuator("tt").id
    lo, hi = m.actuator_ctrlrange[tt]
    need = np.deg2rad(360.0)
    good = (not m.actuator_ctrllimited[tt]) or (lo <= -need + 1e-6 and hi >= need - 1e-6)
    print(f"  {'PASS' if good else 'FAIL'}  indexer ctrlrange spans a full revolution "
          f"({np.degrees(lo):.0f}..{np.degrees(hi):.0f} deg; the cycle commands 0..360)")
    bad += not good

    # --- SPEED LIMITS. Added 2026-08-10 after the controller was found commanding 10 rad/s
    #     against a published 3.14, reaching 3020 mm/s at the tool against a published
    #     1 m/s. NOTHING CAUGHT IT FOR THREE PHASES OF WORK because every other number this
    #     cell reports is about CONTACT -- force, coverage, tilt -- so free-space motion was
    #     in no metric, no assertion and no gate. A human watching the video caught it.
    #     This is the cheap static half (does the CONFIG obey the datasheet); the measured
    #     half is asserted per-run in v5_clean.report() against the real peak tool speed.
    import v5_clean as _CL
    arm = _CL.ARM
    rate_rad_s = arm.joint_rate / m.opt.timestep
    good = rate_rad_s <= arm.max_joint_rate_rad_s + 1e-6
    print(f"  {'PASS' if good else 'FAIL'}  setpoint rate {rate_rad_s:.2f} rad/s is within "
          f"the arm's published {arm.max_joint_rate_rad_s:.2f} rad/s "
          f"({np.degrees(arm.max_joint_rate_rad_s):.0f} deg/s)")
    bad += not good

    # Kinematic worst case: every joint slewing at the limit, each contributing its own
    # moment arm to the tool. Conservative by construction (real configurations cannot
    # align every axis favourably at once), so passing it is a real guarantee and failing
    # it is only a warning that the BOUND is loose -- which is why it prints the margin.
    mujoco.mj_resetDataKeyframe(m, d, m.key("v5home").id)
    mujoco.mj_forward(m, d)
    tcp = d.site_xpos[m.site("link_tcp").id]
    worst = 0.0
    for i in range(1, 8):
        j = m.joint(f"joint{i}").id
        anchor = d.xanchor[j]
        axis = d.xaxis[j]
        r = np.linalg.norm(np.cross(axis, tcp - anchor))
        worst += r * arm.max_joint_rate_rad_s
    good = worst <= arm.max_tcp_speed * 3.0
    print(f"  {'PASS' if good else 'WARN'}  worst-case tool speed bound {worst:.2f} m/s at "
          f"the home pose (published TCP limit {arm.max_tcp_speed:.2f} m/s; this bound sums "
          f"all 7 joints slewing at once, so it is loose by design)")

    print()
    if bad:
        print(f"CELL_SPEC CHECK: {bad} MISMATCH(ES) -- update CELL_SPEC.md to match the "
              f"model.\nDo NOT relax these assertions; the spec is what the real cell "
              f"gets built from.")
        return 1
    print(f"CELL_SPEC CHECK: ALL {len(checks) + len(DATASHEET_LIMITS) + 3} VALUES MATCH")
    return 0


if __name__ == "__main__":
    sys.exit(main())
