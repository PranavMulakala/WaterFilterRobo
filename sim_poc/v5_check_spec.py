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

    print()
    if bad:
        print(f"CELL_SPEC CHECK: {bad} MISMATCH(ES) -- update CELL_SPEC.md to match the "
              f"model.\nDo NOT relax these assertions; the spec is what the real cell "
              f"gets built from.")
        return 1
    print(f"CELL_SPEC CHECK: ALL {len(checks) + len(DATASHEET_LIMITS) + 2} VALUES MATCH")
    return 0


if __name__ == "__main__":
    sys.exit(main())
