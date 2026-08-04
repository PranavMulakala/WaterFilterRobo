"""V5-C placement -- re-run V5-0's placement question with the tool that got BUILT.

V5-0 chose x = 0.58 using PAD_STANDOFF = 45 mm: a guess at how far the wrist would sit
from the surface, made before the wiping tool existed. The tool that exists is 105 mm
from wrist to pad face. Those 60 mm come off the wrist's X coordinate, i.e. they push the
wrist TOWARD its own base -- the one direction a 7-DoF arm cannot go, because it folds
onto itself.

This asks the placement question through v5_clean's OWN planner (`Cell.plan_pad`), so it
measures what the cleaning station can actually do rather than a proxy: same tilt cone,
same collision and joint-limit rejection, same pad offset, same per-point surface ray.

    ../venv/bin/python v5_clean_place.py            # with the tilt cone (what ships)
    ../venv/bin/python v5_clean_place.py --strict   # exact normal only, for comparison
"""
import argparse

import numpy as np
import mujoco

import v5_clean as CL


def scan(c, strict=False):
    """Feasibility of the real raster, per indexed face, at the current placement."""
    m, d, cfg = c.m, c.d, c.cfg
    tm = CL.tool_mat_face(0.0)
    gm = CL.grasp_mat()
    ttq = m.jnt_qposadr[m.joint("tt_rot").id]
    home = m.key("v5home").id
    pad_rel = np.array([0.0, 0.0, 0.105])          # measured on the coupled tool
    cone = CL.TILT_TOL_DEG
    if strict:
        CL.TILT_TOL_DEG = (0.0,)
    out, tilts = {}, []
    try:
        for deg in (0.0, 90.0, 180.0, 270.0):
            mujoco.mj_resetDataKeyframe(m, d, home)
            d.qpos[ttq] = np.deg2rad(deg)
            mujoco.mj_forward(m, d)
            fx, cy, hw, z0, z1 = c.front_face_plane(deg)
            zc = (z0 + z1) / 2
            ph, u_lim = cfg.pad_half, hw - cfg.pad_half
            v_lo, v_hi = (z0 + ph + cfg.floor_margin) - zc, (z1 - ph) - zc
            # every ray FIRST, arm parked: plan_pad leaves the planning copy wherever it
            # last tried, and surface_x reads the live state
            pts = []
            for r in range(5):
                v = v_lo + (v_hi - v_lo) * r / 4
                for cc in range(5):
                    u = -u_lim + 2 * u_lim * cc / 4
                    hit = c.surface_x(cy + u, zc + v)
                    if hit is not None:
                        pts.append(np.array([hit - cfg.pad_thick_half + cfg.press,
                                             cy + u, zc + v]))
            okn, warm = 0, None
            for p in pts:
                got = c.plan_pad(p, tm, pad_rel, warm)
                if got is not None:
                    okn += 1
                    warm = got[0]
                    tilts.append(got[2])
            out[deg] = (okn, len(pts))
        # top face, tool pointing down
        mujoco.mj_resetDataKeyframe(m, d, home)
        mujoco.mj_forward(m, d)
        cg = m.geom("cab_body").id
        cx, cyy = d.geom_xpos[cg][0], d.geom_xpos[cg][1]
        _, _, _, _, ztop = c.front_face_plane(0.0)
        ux, uy = m.geom_size[cg][0] - cfg.pad_half, m.geom_size[cg][1] - cfg.pad_half
        okn, warm = 0, None
        for r in range(5):
            for cc in range(5):
                p = np.array([cx - ux + 2 * ux * r / 4, cyy - uy + 2 * uy * cc / 4,
                              ztop + cfg.pad_thick_half - cfg.press])
                got = c.plan_pad(p, gm, pad_rel, warm)
                if got is not None:
                    okn += 1
                    warm = got[0]
                    tilts.append(got[2])
        out["top"] = (okn, 25)
    finally:
        CL.TILT_TOL_DEG = cone
    return out, tilts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true",
                    help="exact normal only -- what the cleaner used to command")
    a = ap.parse_args()

    c = CL.Cell()
    tt = c.m.body("turntable").id
    x0 = float(c.m.body_pos[tt][0])
    mode = "EXACT NORMAL ONLY" if a.strict else \
        f"within the {max(CL.TILT_TOL_DEG):.0f} deg tilt cone"
    print(f"Raster feasibility vs device placement, {mode}.")
    print(f"Measured through v5_clean's own planner. Working position is x = {x0:.2f}.\n")
    print(f"  {'x':>5} {'front':>9} {'idx 90':>9} {'idx 180':>9} {'idx 270':>9} "
          f"{'top':>9}   {'mean':>6}  {'mean tilt':>9}")
    for x in (0.54, 0.58, 0.62, 0.66, 0.70):
        c.m.body_pos[tt][0] = x
        res, tilts = scan(c, a.strict)
        cells = "".join(f"{res[k][0]:>4}/{res[k][1]:<5}"
                        for k in (0.0, 90.0, 180.0, 270.0, "top"))
        mean = np.mean([res[k][0] / max(res[k][1], 1)
                        for k in (0.0, 90.0, 180.0, 270.0, "top")])
        print(f"  {x:5.2f} {cells}   {mean*100:5.1f}%  {np.mean(tilts):8.1f} deg")
    c.m.body_pos[tt][0] = x0
    print("\nKinematics only -- a necessary condition, not a sufficient one. Contact,")
    print("force and the flange's 30 mm stroke are not modelled here.")


if __name__ == "__main__":
    main()
