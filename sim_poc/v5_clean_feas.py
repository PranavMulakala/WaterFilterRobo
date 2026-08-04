"""V5-C feasibility -- does a collision-free pose EXIST where the cleaner fails?

The probe found the arm jammed link1-against-link6 with joint 4 pinned at its 30 Nm
limit. That is a self-collision, and it says nothing yet about whether the waypoint is
bad or the PATH INTO IT is bad. Those need opposite fixes:

  * no solution exists    -> move the waypoint / re-plan the station layout
  * a solution exists     -> the resolved-rate servo walked into the wrong branch and
                             cannot climb out; fix the seeding, not the geometry

So: re-solve the cleaner's own targets with the reachability study's solver, which does
multiple random restarts and REJECTS collisions and joint-limit pinning.

    ../venv/bin/python v5_clean_feas.py
"""
import numpy as np
import mujoco

import v5_clean as CL
import v5_reach as RE

VERBOSE = False


def ids_for(model):
    """Same id bundle v5_reach.solve expects, built against the real v5 scene."""
    ids = {}
    jnt = [model.joint(f"joint{i}").id for i in range(1, 8)]
    ids["jnt"] = jnt
    ids["dof"] = np.array([model.jnt_dofadr[j] for j in jnt])
    ids["qpos"] = np.array([model.jnt_qposadr[j] for j in jnt])
    ids["range"] = model.jnt_range[jnt].copy()
    ids["site_tcp"] = model.site("link_tcp").id
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
    return ids


def best(model, data, ids, pos, mat, rng, tries=24, pairs=None):
    """Solve from many restarts; return the first clean solution, else the best excuse.

    When it fails on collision, record WHICH bodies touched. "collision" on its own sent
    this project hunting a kinematic problem that did not exist once already (v5_reach
    fix #2); the pair is the part that tells you what to move.
    """
    lo, hi = ids["range"][:, 0], ids["range"][:, 1]
    seeds = [np.array([0.0, -0.3, 0.0, 0.9, 0.0, 1.1, 0.0])]
    seeds += [rng.uniform(lo, hi) for _ in range(tries - 1)]
    why_seen = []
    for q0 in seeds:
        ok, q, pe, re, why = RE.solve(model, data, ids, pos, mat, q0)
        if ok:
            return True, q, pe, why
        if why == "collision" and pairs is not None:
            bn = lambda b: mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, b) or "?"
            for k in range(data.ncon):
                g1, g2 = data.contact[k].geom1, data.contact[k].geom2
                if g1 in ids["arm_geoms"] or g2 in ids["arm_geoms"]:
                    key = "~".join(sorted((bn(model.geom_bodyid[g1]),
                                           bn(model.geom_bodyid[g2]))))
                    pairs[key] = pairs.get(key, 0) + 1
        why_seen.append(why)
    order = ["collision", "joint_limit", "orientation", "unreachable"]
    worst = min(why_seen, key=lambda w: order.index(w) if w in order else 9)
    return False, None, None, worst


def main(maps=False):
    global MAPS
    MAPS = maps
    c = CL.Cell()
    model, data = c.m, c.d
    ids = ids_for(model)
    mujoco.mj_resetDataKeyframe(model, data, model.key("v5home").id)
    mujoco.mj_forward(model, data)
    rng = np.random.default_rng(0)
    cfg = c.cfg

    tm = CL.tool_mat_face(0.0)
    gm = CL.grasp_mat()

    print("Does a COLLISION-FREE, limit-clear solution exist for the cleaner's poses?")
    print("(v5_reach solver: 4 mm / 4 deg, joint margin > 1 deg, no arm contact, "
          "24 restarts)\n")

    print("  --- fixed waypoints")
    for name, pos, mat in [
        ("COUPLE (tool changer, tool down)", np.array(cfg.couple_tcp), gm),
        ("SAFE   (0.26, 0, 0.42) tool +X", np.array([0.26, 0.0, 0.42]), tm),
    ]:
        ok, q, pe, why = best(model, data, ids, pos, mat, rng)
        print(f"    {name:<36} {'OK' if ok else 'NO -- ' + why}")

    # How far out does SAFE have to be before a clean solution exists?
    print("\n  --- SAFE waypoint swept along X, tool pointing +X (z = 0.42)")
    for x in np.arange(0.20, 0.56, 0.04):
        ok, q, pe, why = best(model, data, ids, np.array([x, 0.0, 0.42]), tm, rng)
        print(f"    x = {x:.2f}   {'OK' if ok else 'NO -- ' + why}")

    # ---- the raster targets themselves, on the real scene geometry.
    #
    # CONTROLLED against the two things that changed since V5-0 measured 100%/83% on
    # these same faces, because either one alone would explain the gap:
    #   * V5-0 stood the TCP PAD_STANDOFF = 45 mm off the face. The tool that actually
    #     got built is 105 mm from wrist to pad face, which drags the TCP 60 mm CLOSER
    #     to the arm's own base -- the wrong direction.
    #   * V5-0's probe scene has no arm_riser geom. The riser went into the scene during
    #     V5-C as an obstacle, and nothing re-ran the reach study against it.
    ttq = model.jnt_qposadr[model.joint("tt_rot").id]
    riser = model.geom("arm_riser").id

    home = model.key("v5home").id

    def park():
        """Arm back to a known clear pose. The surface ray must be cast with the arm out
        of the way -- RE.solve leaves it in whatever configuration it last tried, and a
        link standing in the beam makes surface_x return None, silently shrinking the
        denominator."""
        q_keep = data.qpos[ttq]
        mujoco.mj_resetDataKeyframe(model, data, home)
        data.qpos[ttq] = q_keep
        mujoco.mj_forward(model, data)

    def raster_scan(stand, tries=12):
        out, pairs = {}, {}
        for deg in (0.0, 90.0, 180.0, 270.0):
            data.qpos[ttq] = np.deg2rad(deg)
            park()
            fx, cy, hw, z0, z1 = c.front_face_plane(deg)
            zc = (z0 + z1) / 2
            ph, u_lim = cfg.pad_half, hw - cfg.pad_half
            v_lo, v_hi = (z0 + ph + cfg.floor_margin) - zc, (z1 - ph) - zc
            # cast EVERY ray first, arm parked, then solve -- see park()
            pts = []
            for r in range(5):
                v = v_lo + (v_hi - v_lo) * r / 4
                for cc in range(5):
                    u = -u_lim + 2 * u_lim * cc / 4
                    # the ray, exactly as the controller does it -- fx is the corner-most
                    # extent of a rotated box, NOT the presented surface, so planning
                    # feasibility off fx would test poses the cleaner never commands
                    hit = c.surface_x(cy + u, zc + v)
                    pts.append((r, cc, None if hit is None else
                                np.array([hit - cfg.pad_thick_half + cfg.press,
                                          cy + u, zc + v])))
            okn = tot = 0
            grid = [["." for _ in range(5)] for _ in range(5)]
            for r, cc, pad_pt in pts:
                if pad_pt is None:
                    grid[r][cc] = "-"                    # ray never found the surface
                    continue
                ok, q, pe, why = best(model, data, ids, pad_pt - tm @ [0, 0, stand],
                                      tm, rng, tries, pairs)
                tot += 1
                okn += ok
                grid[r][cc] = "o" if ok else why[0].upper()
            out[deg] = (okn, tot)
            if VERBOSE:
                print(f"      index {deg:>5.0f}  (top row first; o=ok C=collision "
                      f"U=unreachable J=joint-limit -=no ray)")
                for r in range(4, -1, -1):
                    print("        " + " ".join(grid[r]))
        # top face, tool pointing down
        data.qpos[ttq] = 0.0
        park()
        cg = model.geom("cab_body").id
        cx, cyy = data.geom_xpos[cg][0], data.geom_xpos[cg][1]
        _, _, _, _, ztop = c.front_face_plane(0.0)
        ux, uy = model.geom_size[cg][0] - cfg.pad_half, model.geom_size[cg][1] - cfg.pad_half
        okn = tot = 0
        for r in range(5):
            for cc in range(5):
                pad_pt = np.array([cx - ux + 2 * ux * r / 4, cyy - uy + 2 * uy * cc / 4,
                                   ztop + cfg.pad_thick_half - cfg.press])
                ok, q, pe, why = best(model, data, ids, pad_pt - gm @ [0, 0, stand],
                                      gm, rng, tries, pairs)
                tot += 1
                okn += ok
        out["top"] = (okn, tot)
        return out, pairs

    print("\n  --- raster feasibility, at exact face normal (what the cleaner commands)")
    print(f"    {'config':<34} {'front':>9} {'idx 90':>9} {'idx 180':>9} "
          f"{'idx 270':>9} {'top':>9}")
    global VERBOSE
    for stand, rz, label in [
        (0.045, True, "V5-0 standoff 45 mm, riser on"),
        (0.105, True, "REAL tool 105 mm, riser on"),
        (0.105, False, "REAL tool 105 mm, riser OFF"),
        (0.045, False, "V5-0 standoff 45 mm, riser OFF"),
    ]:
        VERBOSE = MAPS
        model.geom_contype[riser] = 1 if rz else 0
        model.geom_conaffinity[riser] = 1 if rz else 0
        res, pairs = raster_scan(stand)
        cells = "".join(f"{res[k][0]:>4}/{res[k][1]:<4}"
                        for k in (0.0, 90.0, 180.0, 270.0, "top"))
        print(f"    {label:<34} {cells}")
        if pairs:
            top = sorted(pairs.items(), key=lambda kv: -kv[1])[:3]
            print(f"      blocked by: " + ", ".join(f"{k} x{v}" for k, v in top))
    model.geom_contype[riser] = 1
    model.geom_conaffinity[riser] = 1


if __name__ == "__main__":
    import sys
    main("--maps" in sys.argv)
