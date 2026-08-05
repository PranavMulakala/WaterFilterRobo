"""V5-A -- structural checks on the generated scene.

Run after `make_scene_v5.py`. Every check here exists because something went wrong
without it. None of these would have been caught by "does the scene load?" -- the scene
loaded fine through all five bugs listed below.

    ../venv/bin/python v5_check_scene.py

Checks, and the bug each one catches (all 2026-08-04, see PAIN_JOURNAL):

  1. Cabinet stands ON the bench (z = 0), and body + top cover are FLUSH.
     -> a 12 mm cover stacked on a full-height body put the visible top surface 12 mm
        above the plane the raster and the reachability study both call "the top face".
  2. Every condition patch lies ON its face, with its thickness axis along the OUTWARD
     normal, protruding rather than sunk, and entirely inside the face rectangle.
     -> patches whose frame pointed inward still passed a careless abs()-based check.
  3. Every patch carries its MATERIAL'S RGB with alpha 0.
     -> written as rgba="0 0 0 0", revealing a patch made it BLACK regardless of
        material, so brown soil / white scratches / grey dents were indistinguishable.
  4. All FIVE exposed faces carry pools, including the back.
     -> the back was excluded while it was unreachable at every placement; the rotary
        indexer reaches it now, and leaving it clean would flatter every coverage number.
  5. Nothing interpenetrates at spawn, and the pad tool RESTS on its post.
     -> the pad first floated 45 mm above a post whose locating ring was narrower than
        the pad's own diagonal, exactly the v4 staging-nest mistake.
"""
import sys
import numpy as np
import mujoco

XML = "ufactory_xarm7/refurb_scene_v5.xml"
# the device stands ON the rotary indexer, so its top surface is the disc rise plus the
# cabinet height -- see make_scene_v5.TT_RISE / CAB_HEIGHT
TT_RISE = 0.010
CAB_HEIGHT = 0.450
NOMINAL_HEIGHT = TT_RISE + CAB_HEIGHT
POOLS = ("soil", "scr", "dent")
POOL_RGB = {"soil": (0.42, 0.36, 0.28),
            "scr": (0.34, 0.34, 0.35),
            "dent": (0.30, 0.30, 0.32)}

fails = []


def check(cond, msg):
    if cond:
        print(f"  PASS  {msg}")
    else:
        print(f"  FAIL  {msg}")
        fails.append(msg)


def main():
    m = mujoco.MjModel.from_xml_path(XML)
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    gname = lambda i: mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i) or ""

    print(f"V5-A scene check -- {XML}\n")
    print("1. cabinet")
    body = m.geom("cab_body").id
    cover = m.geom("cab_topcover").id
    bp, bs = d.geom_xpos[body], m.geom_size[body]
    cp, cs = d.geom_xpos[cover], m.geom_size[cover]
    disc = m.geom("tt_disc").id
    dtop = d.geom_xpos[disc][2] + m.geom_size[disc][1]
    check(abs(dtop - TT_RISE) < 1e-9,
          f"rotary indexer disc top at {TT_RISE*1000:.0f} mm")
    check(abs((bp[2] - bs[2]) - TT_RISE) < 1e-9, "device stands ON the indexer, no gap")
    check(abs((bp[2] + bs[2]) - (cp[2] - cs[2])) < 1e-9, "body and top cover are flush")
    check(abs((cp[2] + cs[2]) - NOMINAL_HEIGHT) < 1e-9,
          f"top surface == indexer + cabinet height ({NOMINAL_HEIGHT*1000:.0f} mm)")
    # the indexer must actually carry the device and its pools
    tt = m.joint("tt_rot").id
    qadr = m.jnt_qposadr[tt]
    d.qpos[qadr] = np.pi / 2
    mujoco.mj_forward(m, d)
    rot_ok = abs(d.geom_xmat[body].reshape(3, 3)[1, 0] - 1.0) < 1e-6
    soil0 = next(i for i in range(m.ngeom)
                 if (mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i) or "")
                 .startswith("soil"))
    moved = abs(d.geom_xpos[soil0][1]) > 1e-4 or abs(d.geom_xpos[soil0][0] - 0.58) > 1e-4
    d.qpos[qadr] = 0.0
    mujoco.mj_forward(m, d)
    check(rot_ok, "indexing 90 deg rotates the device")
    check(moved, "condition pools are carried by the device when it indexes")
    check(any(mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_ACTUATOR, i) == "tt"
              for i in range(m.nu)), "indexer is a commanded axis, not scenery")

    lo, hi = bp - bs, bp + bs
    # the BACK face is the back PANEL's outer surface, 10 mm proud of the body
    pan = m.geom("cab_backpanel").id
    pan_x = float(d.geom_xpos[pan][0] + m.geom_size[pan][0])
    faces = {"front": (0, lo[0], -1), "back": (0, pan_x, 1),
             "left": (1, lo[1], -1), "right": (1, hi[1], 1),
             "top": (2, NOMINAL_HEIGHT, 1)}

    print("\n2-4. condition pools")
    counts, per_face = {}, {}
    off_plane = wrong_frame = sunk = off_edge = 0
    for i in range(m.ngeom):
        n = gname(i)
        pre = next((p for p in POOLS if n.startswith(p)), None)
        if pre is None:
            continue
        counts[pre] = counts.get(pre, 0) + 1
        p, R, sz = d.geom_xpos[i], d.geom_xmat[i].reshape(3, 3), m.geom_size[i]
        fname, (ax, val, sgn) = min(faces.items(),
                                    key=lambda kv: abs(p[kv[1][0]] - kv[1][1]))
        per_face[fname] = per_face.get(fname, 0) + 1
        if abs(p[ax] - val) > sz[2] + 1e-4:
            off_plane += 1
        want = np.zeros(3)
        want[ax] = sgn
        if float(R[:, 2] @ want) < 0.999:
            wrong_frame += 1
        if (p[ax] - val) * sgn <= 0:
            sunk += 1
        if fname == "back":
            flo = np.array([lo[0], d.geom_xpos[pan][1] - m.geom_size[pan][1],
                            d.geom_xpos[pan][2] - m.geom_size[pan][2]])
            fhi = np.array([hi[0], d.geom_xpos[pan][1] + m.geom_size[pan][1],
                            d.geom_xpos[pan][2] + m.geom_size[pan][2]])
        else:
            flo, fhi = lo, hi
        for su in (-1, 1):
            for sv in (-1, 1):
                c = p + R[:, 0] * sz[0] * su + R[:, 1] * sz[1] * sv
                if any(c[a] < flo[a] - 1e-6 or c[a] > fhi[a] + 1e-6
                       for a in range(3) if a != ax):
                    off_edge += 1
                    break

    total = sum(counts.values())
    print(f"       pools: {counts}  (total {total});  per face: {per_face}")
    check(off_plane == 0, f"all {total} patches lie on their face plane")
    check(wrong_frame == 0, "all patch frames point OUTWARD (thickness axis == normal)")
    check(sunk == 0, "all patches protrude rather than sink below the surface")
    check(off_edge == 0, "no patch overhangs its face edge")
    # FLIPPED. The back was excluded while it was unreachable at every placement; the
    # rotary indexer made it reachable, so leaving it clean would have flattered every
    # cleaning-coverage number V5-C produces.
    check(per_face.get("back", 0) > 0,
          f"back face CARRIES pools ({per_face.get('back', 0)}) -- the indexer reaches it")
    check(len(per_face) == 5, f"all five exposed faces carry pools ({sorted(per_face)})")

    for pre, exp in POOL_RGB.items():
        ids = [i for i in range(m.ngeom) if gname(i).startswith(pre)]
        rgb_ok = all(np.allclose(m.geom_rgba[i][:3], exp, atol=1e-3) for i in ids)
        hidden = all(m.geom_rgba[i][3] == 0 for i in ids)
        novis = all(m.geom_contype[i] == 0 and m.geom_conaffinity[i] == 0 for i in ids)
        check(rgb_ok, f"{pre}: carries material RGB {exp} (not black)")
        check(hidden, f"{pre}: hidden at rest (alpha 0)")
        check(novis, f"{pre}: visual only (non-colliding)")

    print("\n5. keyframe (the v4 trap, recurring)")
    keys = {mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_KEY, i): i for i in range(m.nkey)}
    check("v5home" in keys, "a scene-local `v5home` keyframe exists")
    if "v5home" in keys:
        mujoco.mj_resetDataKeyframe(m, d, keys["v5home"])
        mujoco.mj_forward(m, d)
        pad = d.xpos[m.body("padtool").id]
        check(np.allclose(pad, [0.300, -0.340, 0.040], atol=1e-6),
              f"v5home places the pad tool on its post {np.round(pad, 4)}")
        check(d.ncon == 0, "v5home has no interpenetration")
    # the inherited `home` is KNOWN BAD in this scene -- assert that it still is, so the
    # warning in the XML never quietly becomes stale advice
    if "home" in keys:
        mujoco.mj_resetDataKeyframe(m, d, keys["home"])
        mujoco.mj_forward(m, d)
        bad = d.xpos[m.body("padtool").id]
        check(not np.allclose(bad, [0.300, -0.340, 0.040], atol=1e-3),
              "inherited `home` is still the unsafe one (documented; use v5home)")
    mujoco.mj_resetData(m, d)
    mujoco.mj_forward(m, d)

    print("\n6. compliant pad contact")
    pf = m.geom("pad_face").id
    check(m.geom_priority[pf] > 0,
          "pad_face has contact priority (else MuJoCo averages its solref away)")
    check(m.geom_solimp[pf][2] < m.geom_size[pf][2],
          f"solimp width {m.geom_solimp[pf][2]:.4f} < pad half-thickness "
          f"{m.geom_size[pf][2]:.4f} (else it never reaches full stiffness)")
    # force/penetration must be monotonic and must never approach the pad thickness
    pen, body = [], m.body("padtool").id
    for f in (0, 5, 10, 20, 40, 60):
        if "v5home" in keys:
            mujoco.mj_resetDataKeyframe(m, d, keys["v5home"])
        else:
            mujoco.mj_resetData(m, d)
        for _ in range(3000):
            d.xfrc_applied[body] = [0, 0, -f, 0, 0, 0]
            mujoco.mj_step(m, d)
        pen.append(max([-c.dist for c in d.contact[:d.ncon]] or [0]))
    d.xfrc_applied[body] = np.zeros(6)
    mono = all(pen[i] <= pen[i + 1] + 5e-5 for i in range(len(pen) - 1))
    print("        penetration mm @ 0/5/10/20/40/60 N: "
          + " ".join(f"{p*1000:.2f}" for p in pen))
    check(mono, "force/penetration curve is monotonic (no solver instability)")
    check(max(pen) < m.geom_size[pf][2],
          f"pad never crushes through its own half-thickness "
          f"(max {max(pen)*1000:.2f} mm < {m.geom_size[pf][2]*1000:.0f} mm)")
    # WHERE THE MODEL STOPS BEING A MODEL. Probed, printed, and deliberately NOT asserted
    # monotonic -- the point is to record the ceiling, not to pretend it is higher. At
    # 80 N penetration jumps 2.19 -> 20.25 mm, i.e. twice the pad's half-thickness, and
    # above that it is non-monotonic (111 N -> 11.7, 120 N -> 21.6, 200 N -> 12.2). So
    # 60 N is a MODEL-VALIDITY CEILING, not a component rating, and any station pressing
    # this pad must stay under it BY CONSTRUCTION rather than by luck. v5_clean asserts
    # exactly that on every eval.
    hi = []
    for f in (80, 120, 200):
        mujoco.mj_resetDataKeyframe(m, d, keys["v5home"])
        for _ in range(3000):
            d.xfrc_applied[body] = [0, 0, -f, 0, 0, 0]
            mujoco.mj_step(m, d)
        hi.append(max([-c.dist for c in d.contact[:d.ncon]] or [0]))
    d.xfrc_applied[body] = np.zeros(6)
    print("        BEYOND VALIDITY, penetration mm @ 80/120/200 N: "
          + " ".join(f"{p*1000:.1f}" for p in hi)
          + f"  (half-thickness {m.geom_size[pf][2]*1000:.0f} mm -- the curve breaks")
    print("        between 60 and 80 N; 60 N is the ceiling the cleaning station must "
          "stay under)")
    mujoco.mj_resetData(m, d)
    mujoco.mj_forward(m, d)

    print("\n7. tool post + pad, and spawn state")
    check(d.ncon == 0, f"no interpenetration at spawn (ncon = {d.ncon})")
    pid = m.body("padtool").id
    p0 = d.xpos[pid].copy()
    for _ in range(1500):
        mujoco.mj_step(m, d)
    drift = float(np.linalg.norm(d.xpos[pid] - p0))
    check(drift < 0.005, f"pad tool rests on its post (drift {drift*1000:.1f} mm "
                         f"over 3 s; the pad is deliberately compliant)")
    touching = {gname(d.contact[c].geom1) for c in range(d.ncon)} | \
               {gname(d.contact[c].geom2) for c in range(d.ncon)}
    check("post_base" in touching and "pad_face" in touching,
          "pad is supported by the post, not by anything else")

    print()
    if fails:
        print(f"V5-A SCENE CHECK: FAILED ({len(fails)})")
        for f in fails:
            print(f"    - {f}")
        return 1
    print("V5-A SCENE CHECK: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
