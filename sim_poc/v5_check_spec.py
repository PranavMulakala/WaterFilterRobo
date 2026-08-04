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
        ("backdrop bottom Z", bd_p[2] - bd_s[2], 0.000),
        ("bench working area X", 2 * bn_s[0], 1.100),
        ("bench working area Y", 2 * bn_s[1], 1.200),
        # --- section 5, tooling
        ("pad tool total mass (kg)", m.body_subtreemass[pad], 0.220),
        ("pad stem diameter", 2 * ps_s[0], 0.040),
        ("pad stem length", 2 * ps_s[1], 0.090),
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

    # payload headroom -- CELL_SPEC claims 6% utilisation against the 3.5 kg rating
    util = m.body_subtreemass[pad] / 3.5
    good = util < 0.10
    print(f"\n  {'PASS' if good else 'FAIL'}  payload utilisation {util*100:.1f}% "
          f"of the 3.5 kg rating")
    bad += not good

    print()
    if bad:
        print(f"CELL_SPEC CHECK: {bad} MISMATCH(ES) -- update CELL_SPEC.md to match the "
              f"model.\nDo NOT relax these assertions; the spec is what the real cell "
              f"gets built from.")
        return 1
    print(f"CELL_SPEC CHECK: ALL {len(checks) + len(DATASHEET_LIMITS) + 1} VALUES MATCH")
    return 0


if __name__ == "__main__":
    sys.exit(main())
