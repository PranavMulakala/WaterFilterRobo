"""V5-B -- Stage-1 triage: grade an incoming unit Easy / Medium / Hard from pixels.

    ../venv/bin/python v5_triage.py --calibrate 40      fit thresholds (seeds 9000+)
    ../venv/bin/python v5_triage.py --eval 60 --seed0 200      held-out evaluation
    ../venv/bin/python v5_triage.py --views 3           save annotated masks to /tmp

WHAT THIS IS. DrinkPrime's line begins with a human looking at a returned device and
calling it Easy, Medium or Hard (Stage 1 CHECKS; QC flow page 1). That call is the
founder's "image processing" bar. This grades it from rendered pixels.

** THE CLASS NAMES ARE THEIRS. THE BOUNDARIES ARE OURS. ** No document in the 13-document
set defines Easy/Medium/Hard -- the QC flow attaches no annexure to the VISUAL INSPECTION
fan-out at all (see dp_process.MISSING). What IS theirs is the three surface conditions
and their remedies, quoted in make_scene_v5:

    soil     -> wipes off with CIF cream (Stage 2)                  -> EASY
    scratch  -> needs the rubbing-component pass (Stage 2)          -> MEDIUM
    dent     -> no remedy in ANY of the ten stages                  -> HARD

Every number this file prints must carry that caveat.

WHY A FIXED CAMERA AND A ROTATING DEVICE. V5_PLAN originally specified the arm orbiting
its wrist camera -- correct when the device could not move. The rotary indexer changed
that. A fixed station camera plus an indexed device is simpler, is what real rotary vision
cells do, needs no hand-eye calibration (the biggest un-modelled risk in the wrist-camera
plan), and leaves the arm free during inspection. The arm is PARKED clear of frame.

HOW IT DECIDES -- deliberately simple and explainable, because it has to be defensible to
a customer rather than impressive to a reviewer. Measured pixel statistics (below) drove
every choice; none of it was guessed.

  body 0.788 value / 0.047 sat | soil 0.373 / 0.309 | scr 0.378 / 0.051 | dent 0.298 / 0.085

  1. ROI from the CALIBRATED camera and the NOMINAL part pose -- project the device's
     bounding box into the image. Standard machine vision (a search region from CAD +
     calibration). Uses no per-trial information. It also excludes the bench, which is
     0.767 value and would otherwise be indistinguishable from the 0.788 body.
  2. Device mask = bright inside the ROI (the backdrop is 0.085), then eroded to drop
     silhouette edges.
  3. Anomaly = darker than its LOCAL surroundings. Local, not absolute, so the four faces
     being lit differently does not matter. Captures 100% of scratch, 99% of dent and 96%
     of soil pixels against 0.5% of body.
  4. Saturated anomalies are SOIL (0.309 vs 0.05-0.085 -- brown dirt against neutral grey).
  5. The neutral anomalies split by SHAPE, which is what a human grader uses: a dent is
     compact and survives a 3x3 erosion; a scratch is a 1-2 px line and does not. Measured
     discrimination 7.7x. Shape is also why the modelling choice of a dark groove for
     scratches does not decide the answer -- a pale scratch would still be found by the
     two-sided anomaly test and still be thin.
  6. Two frozen thresholds on the summed fractions: dent -> HARD, else scratch -> MEDIUM,
     else EASY.

THE DANGEROUS ERROR IS FALSE-EASY: a unit needing real work sent down the cosmetic path.
It is reported separately and the thresholds are fitted to drive it to zero first,
accuracy second -- the same asymmetry v4 used for false-clean.
"""
import argparse
import json
import sys
from dataclasses import dataclass, field

import numpy as np
import mujoco

XML = "ufactory_xarm7/refurb_scene_v5.xml"
GRADES = ("easy", "medium", "hard")
# arm parked clear of the inspection camera. Measured: 0.000% of the inspect view is arm
# pixels here, against 4.28% at the v5home pose.
PARK = np.array([np.pi / 2, -0.247, 0.0, 0.909, 0.0, 1.15644, 0.0])


@dataclass(frozen=True)
class TriageConfig:
    xml: str = XML
    cam: str = "inspect"
    cam_w: int = 1280
    cam_h: int = 720

    # --- ground truth. CRISP, NON-OVERLAPPING count bands, as in v4. The measurement
    #     difficulty must come from occlusion, lighting and pose -- never from fuzzing
    #     the labels. A classifier that scores well on vague labels has measured nothing.
    #     (dent_lo, dent_hi, scr_lo, scr_hi, soil_lo, soil_hi)
    bands: tuple = (("easy",   0, 1,  0, 2,  12, 34),
                    ("medium", 0, 1,  9, 22,  4, 28),
                    ("hard",   6, 18, 0, 22,  0, 28))
    weights: tuple = (0.34, 0.33, 0.33)

    # --- views: index angles presented to the fixed camera
    index_deg: tuple = (0.0, 90.0, 180.0, 270.0)

    # --- realistic per-trial variation. This is the in-cell equivalent of v4's lesson:
    #     the real uncertainty is HOW THE DEVICE WAS PUT DOWN, plus the indexer's own
    #     repeatability and the lighting.
    place_xy_mm: float = 5.0        # device placement on the platter
    place_yaw_deg: float = 3.0
    index_repeat_deg: float = 0.5   # indexer repeatability, per CELL_SPEC
    light_lo: float = 0.80
    light_hi: float = 1.20

    # --- pixel rules (measured, see module docstring)
    roi_margin_px: int = 6          # small crop pad; the hull does the real work
    # MUST sit below the DARKEST defect (dent, 0.298) and well above the backdrop
    # (0.085). At 0.30 the dents fell BELOW it, so they were cut out of the body mask
    # and became holes -- every "dent" the classifier found was an edge around one.
    v_bg: float = 0.18
    erode_body: int = 4             # px, drop silhouette edges
    local_r: int = 9                # local-mean radius
    t_dark: float = 0.05            # anomaly depth below local mean
    s_soil: float = 0.18            # soil 0.309 vs neutral 0.05-0.085
    s_accent: float = 0.50          # facia is 0.802 -- exclude, it is not a defect
    base_skirt: float = 0.030       # m, lift the search region clear of the bench
    top_skirt: float = 0.015        # m, keep clear of the top-cover seam
    # MEASURED, not guessed: real defect components run median 114 px (p5 = 18);
    # spurious ones from residual edges and anti-aliasing run median 2 px (p95 = 18).
    # A 25 px floor keeps 94% of real defects and removes 96% of spurious ones.
    min_defect_px: int = 25         # ignore specks below this -- render noise
    close_r: int = 2                # px, closing radius to rejoin dashed scratch lines
    elong_scratch: float = 2.6      # principal-axis ratio at/above which a blob is a
                                    # scratch. Rotation-invariant -- see components().
    face_inset: float = 0.012       # m, keep each face quad clear of its own corners

    # --- FROZEN decision thresholds, fitted by `--calibrate 100` on seeds 9000-9099,
    #     disjoint from every eval seed.
    #     These are COUNTS OF DEFECTS, not pixel fractions: "more than 3 dents -> HARD,
    #     else more than 5 scratches -> MEDIUM, else EASY". Directly comparable to the
    #     ground-truth bands, and legible to a customer, which the pixel-fraction
    #     version never was.
    #     History worth keeping: the pixel-fraction version scored 55.0% on 120 held-out
    #     units and NEVER ONCE said "easy", because the easy and medium scratch-fraction
    #     distributions overlapped and no threshold could separate them.
    t_dent: float = 3.0
    t_scratch: float = 6.0


CFG = TriageConfig()


# ============================================================ pure-numpy imaging
def _box_sum(a, r):
    p = np.pad(a, r + 1, mode="constant")
    c = p.cumsum(0).cumsum(1)
    H, W = a.shape
    k = 2 * r + 1
    return (c[k:k + H, k:k + W] - c[:H, k:k + W]
            - c[k:k + H, :W] + c[:H, :W])


def box_mean(a, r, mask=None):
    """Local mean via integral images. Pure numpy -- scipy/cv2 are not dependencies and
    requirements.txt is pinned on purpose.

    MASKED, when a mask is given: the mean is taken over mask pixels only. This matters
    more than it looks. Unmasked, the window near the device's outline mixes in the dark
    backdrop, and near an internal shading step it mixes the two faces -- so ordinary
    structure reads as "much darker than my surroundings", i.e. as a compact dent.
    Measured before the fix: 67.7% of everything in the dent channel was an edge artifact
    on no defect geom at all, against 30% real dents.
    """
    if mask is None:
        return _box_sum(a, r) / ((2 * r + 1) ** 2)
    mf = mask.astype(np.float32)
    num = _box_sum(a * mf, r)
    den = _box_sum(mf, r)
    return np.where(den > 0.5, num / np.maximum(den, 1e-6), a)


def erode(mask, r=1):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out &= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def dilate(mask, r=1):
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def components(mask, min_px=6):
    """Connected components (8-connectivity) of a sparse boolean mask, via union-find
    over the set pixels only. Pure numpy/python -- scipy is not a dependency, and the
    masks are a few thousand pixels, so iterating them directly is cheap.

    Returns a list of (n_px, height, width, fill) per component.
    """
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return []
    idx = {}
    for k, (y, x) in enumerate(zip(ys.tolist(), xs.tolist())):
        idx[(y, x)] = k
    parent = list(range(len(ys)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for (y, x), k in idx.items():
        for dy, dx in ((0, 1), (1, -1), (1, 0), (1, 1)):     # forward half of 8-nbhd
            j = idx.get((y + dy, x + dx))
            if j is not None:
                union(k, j)

    groups = {}
    for (y, x), k in idx.items():
        groups.setdefault(find(k), []).append((y, x))

    out = []
    for pts in groups.values():
        if len(pts) < min_px:
            continue
        a = np.array(pts, float)
        a -= a.mean(0)
        # ROTATION-INVARIANT elongation from second moments, NOT the bounding box.
        # A 40 px scratch at 45 degrees has a ~30x30 bounding box -- aspect 1.0, i.e.
        # perfectly "compact" -- so a bbox test calls every diagonal scratch a dent.
        # Scratches here are placed at uniformly random angles, so most of them defeated
        # it. The principal-axis ratio does not care which way the line points.
        cov = (a.T @ a) / len(a)
        tr = cov[0, 0] + cov[1, 1]
        det = cov[0, 0] * cov[1, 1] - cov[0, 1] ** 2
        disc = max(tr * tr / 4 - det, 0.0)
        l1 = tr / 2 + np.sqrt(disc)
        l2 = max(tr / 2 - np.sqrt(disc), 1e-9)
        out.append((len(pts), float(np.sqrt(l1 / l2))))
    return out


def _hsv(rgb):
    a = rgb.astype(np.float32) / 255.0
    v = a.max(2)
    mn = a.min(2)
    return np.where(v > 1e-6, (v - mn) / np.maximum(v, 1e-6), 0.0), v


# ============================================================ region of interest
def _hull(pts):
    """Convex hull of a handful of 2D points -- monotone chain, 8 points, no scipy."""
    pts = sorted(map(tuple, pts))
    def half(ps):
        out = []
        for p in ps:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    return np.array(half(pts)[:-1] + half(pts[::-1])[:-1], float)


def face_regions(model, data, cfg=CFG, index_deg=0.0):
    """One search region PER VISIBLE FACE, projected from the calibrated camera.

    Returns [(v0, v1, u0, u1, mask), ...] -- one entry per face pointing at the camera.

    WHY PER FACE, AND NOT ONE SILHOUETTE. Four rounds of measurement got here:
      * projected 2D bbox      -> swallowed the turntable rim, bench and base shadow;
                                  3381 of 3398 dent pixels were on no defect geom
      * convex hull, circumscribed box -> still 154 mm half-extent vs a 90 x 125 device,
                                  ~1000 false dent px per view
      * hull at the commanded index angle, lifted clear of the bench -> 62.6% of the
                                  dent channel was STILL structural edge
    The residue is edges ON the device: the step between two faces lit differently, and
    the top-cover seam. Both are long dark lines, both survive as compact after erosion,
    both read as dents. Inside a SINGLE face there is no such step -- shading is smooth
    and the only anomalies are defects. Inspecting each face as its own region is also
    what a real cell does.

    Uses only the camera pose, the nominal part pose and the angle the cell COMMANDED
    the indexer to. No per-trial ground truth.
    """
    cam = model.camera(cfg.cam).id
    p = data.cam_xpos[cam]
    R = data.cam_xmat[cam].reshape(3, 3)
    f = (cfg.cam_h / 2) / np.tan(np.deg2rad(model.cam_fovy[cam]) / 2)
    cx, cy = CFG_CAB_XY
    hd, hw = CAB_HALF_XY
    th = np.deg2rad(index_deg)
    ct, st = np.cos(th), np.sin(th)

    def w(lx, ly, lz):
        return np.array([cx + ct * lx - st * ly, cy + st * lx + ct * ly, lz])

    z0, z1 = CAB_BASE + cfg.base_skirt, CAB_TOP - cfg.top_skirt
    # the four vertical faces, in the device's own frame, inset so the projected quad
    # sits INSIDE the face and never straddles a corner
    ins = cfg.face_inset
    # the BACK face is the back panel's outer surface, 10 mm proud of the body and
    # slightly narrower -- pools live there, so the search region must too
    bx, bhw = hd + 0.010, hw - 0.006
    faces = [
        ((-1, 0), [w(-hd, -hw + ins, z0), w(-hd, hw - ins, z0),
                   w(-hd, hw - ins, z1), w(-hd, -hw + ins, z1)]),
        ((1, 0),  [w(bx, -bhw + ins, z0), w(bx, bhw - ins, z0),
                   w(bx, bhw - ins, z1), w(bx, -bhw + ins, z1)]),
        ((0, -1), [w(-hd + ins, -hw, z0), w(hd - ins, -hw, z0),
                   w(hd - ins, -hw, z1), w(-hd + ins, -hw, z1)]),
        ((0, 1),  [w(-hd + ins, hw, z0), w(hd - ins, hw, z0),
                   w(hd - ins, hw, z1), w(-hd + ins, hw, z1)]),
    ]
    out = []
    for fid, ((nx, ny), quad) in enumerate(faces):
        n_world = np.array([ct * nx - st * ny, st * nx + ct * ny, 0.0])
        centre = np.mean(quad, axis=0)
        view = centre - p
        cosang = float(n_world @ view) / np.linalg.norm(view)
        if cosang > -0.25:
            continue                          # facing away or too oblique to grade
        uv = []
        for X in quad:
            q = R.T @ (X - p)
            depth = -q[2]
            if depth < 1e-3:
                break
            uv.append((cfg.cam_w / 2 + f * q[0] / depth,
                       cfg.cam_h / 2 - f * q[1] / depth))
        if len(uv) != 4:
            continue
        uv = np.array(uv)
        u0 = max(0, int(uv[:, 0].min()) - 2)
        u1 = min(cfg.cam_w, int(uv[:, 0].max()) + 2)
        v0 = max(0, int(uv[:, 1].min()) - 2)
        v1 = min(cfg.cam_h, int(uv[:, 1].max()) + 2)
        if u1 - u0 < 40 or v1 - v0 < 40:
            continue
        H = _hull(uv)
        gy, gx = np.mgrid[v0:v1, u0:u1]
        inside = np.ones(gx.shape, bool)
        for i in range(len(H)):
            a, b = H[i], H[(i + 1) % len(H)]
            inside &= ((b[0] - a[0]) * (gy - a[1])
                       - (b[1] - a[1]) * (gx - a[0])) >= 0
        out.append((fid, cosang, (v0, v1, u0, u1, inside)))
    return out


# filled in by load_scene()
CFG_CAB_XY = (0.58, 0.0)
CAB_HALF_XY = (0.09, 0.125)
CAB_BASE = 0.010
CAB_TOP = 0.46


# ============================================================ feature extraction
def image_features(rgb, roi, cfg=CFG):
    """Count DEFECT INSTANCES on one face. Returns None if the face is not visible.

    COUNTS, NOT PIXEL FRACTIONS. The ground truth is defined by how MANY defects of each
    kind a unit has, so that is what should be measured. The pixel-fraction version could
    not separate easy from medium at all -- the scratch fractions overlapped
    (easy 0.00104-0.00363 vs medium 0.00222-0.00508), so no threshold existed and no
    amount of tuning could have helped. Counting instances matches the label definition.

    A component is a DENT if it is compact, a SCRATCH if it is elongated -- the same
    shape test a human grader uses, now applied per defect rather than to the whole mask.
    """
    v0, v1, u0, u1, hull = roi
    sat, val = _hsv(rgb)
    sat = sat[v0:v1, u0:u1]
    val = val[v0:v1, u0:u1]

    body = (val > cfg.v_bg) & hull
    body = erode(body, cfg.erode_body)
    body &= sat < cfg.s_accent
    n_body = int(body.sum())
    if n_body < 1500:
        return None

    local = box_mean(val, cfg.local_r, body)
    anomaly = body & (val < local - cfg.t_dark)
    soil = anomaly & (sat > cfg.s_soil)
    neutral = anomaly & ~soil
    # MORPHOLOGICAL CLOSING before labelling. A 1-2 px scratch line, anti-aliased and
    # then thresholded, breaks into a dashed row of specks -- and every speck is compact,
    # so every one of them counted as a DENT. Measured before closing: dents over by
    # +4.4 per unit and scratches under by -5.4, the two errors being the same defects
    # counted in the wrong channel. Closing bridges the dashes back into one elongated
    # component.
    if cfg.close_r:
        neutral = erode(dilate(neutral, cfg.close_r), cfg.close_r)

    n_dent = n_scr = 0
    for n_px, elong in components(neutral, cfg.min_defect_px):
        if elong >= cfg.elong_scratch:
            n_scr += 1
        else:
            n_dent += 1
    n_soil = len(components(soil, cfg.min_defect_px))
    return {"n_body": n_body, "dent": n_dent, "scratch": n_scr, "soil": n_soil}


def classify(feats, cfg=CFG):
    """Merge per-face counts, then apply the two frozen thresholds.

    Each face is graded ONCE, in the view where it is most face-on -- see
    grade_unit(). Without that, a face visible in two adjacent index positions would
    have its defects counted twice.
    """
    feats = [f for f in feats if f]
    if not feats:
        return "hard", {}                       # cannot see it -> fail safe to the slow path
    d = sum(f["dent"] for f in feats)
    s = sum(f["scratch"] for f in feats)
    o = sum(f["soil"] for f in feats)
    sc = {"dent": float(d), "scratch": float(s), "soil": float(o)}
    if d > cfg.t_dent:
        return "hard", sc
    if s > cfg.t_scratch:
        return "medium", sc
    return "easy", sc


# ============================================================ scene / trial setup
def load_scene(cfg=CFG):
    global CFG_CAB_XY, CAB_HALF_XY, CAB_TOP, CAB_BASE
    model = mujoco.MjModel.from_xml_path(cfg.xml)
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)
    g = model.geom("cab_body").id
    CFG_CAB_XY = (float(data.geom_xpos[g][0]), float(data.geom_xpos[g][1]))
    CAB_HALF_XY = (float(model.geom_size[g][0]), float(model.geom_size[g][1]))
    zs = [(data.geom_xpos[i][2] - model.geom_size[i][2],
           data.geom_xpos[i][2] + model.geom_size[i][2])
          for i in range(model.ngeom)
          if model.geom_bodyid[i] == model.body("cabinet").id and model.geom_contype[i]]
    CAB_BASE = float(min(a for a, _ in zs))
    CAB_TOP = float(max(b for _, b in zs))
    name = lambda i: mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or ""
    pools = {p: [i for i in range(model.ngeom) if name(i).startswith(p)]
             for p in ("soil", "scr", "dent")}
    return model, data, pools


def sample_condition(rng, cfg=CFG):
    i = rng.choice(len(cfg.bands), p=list(cfg.weights))
    name, dlo, dhi, slo, shi, olo, ohi = cfg.bands[i]
    return (name,
            int(rng.integers(dlo, dhi + 1)),
            int(rng.integers(slo, shi + 1)),
            int(rng.integers(olo, ohi + 1)))


def set_pools(model, pools, n_dent, n_scr, n_soil, rng):
    """Reveal a random subset of each pool. Ground truth is the COUNT; which geoms and
    therefore which faces they land on is random, so occlusion is a real difficulty."""
    for p in pools.values():
        for g in p:
            model.geom_rgba[g][3] = 0.0
    for key, n in (("dent", n_dent), ("scr", n_scr), ("soil", n_soil)):
        if n <= 0:
            continue
        for g in rng.choice(pools[key], size=min(n, len(pools[key])), replace=False):
            model.geom_rgba[g][3] = 1.0


def grade_unit(model, data, pools, renderer, seed, cfg=CFG, save=None):
    """One trial: place a unit with realistic jitter, index it past the camera, grade it."""
    rng = np.random.default_rng(seed)
    truth, nd, ns, no = sample_condition(rng, cfg)
    set_pools(model, pools, nd, ns, no, rng)

    base_light = model.light_diffuse.copy()
    model.light_diffuse[:] = np.clip(base_light * rng.uniform(cfg.light_lo, cfg.light_hi),
                                     0, 1)
    # how the device was PUT DOWN on the platter -- the real in-cell variation
    cab = model.body("cabinet").id
    base_pos = model.body_pos[cab].copy()
    jitter = np.array([rng.normal(0, cfg.place_xy_mm / 1000),
                       rng.normal(0, cfg.place_xy_mm / 1000), 0.0])
    model.body_pos[cab] = base_pos + jitter
    yaw0 = np.deg2rad(rng.normal(0, cfg.place_yaw_deg))

    jn = [model.joint(f"joint{i}").id for i in range(1, 8)]
    qadr = np.array([model.jnt_qposadr[j] for j in jn])
    tt = model.jnt_qposadr[model.joint("tt_rot").id]

    mujoco.mj_resetDataKeyframe(model, data, model.key("v5home").id)
    data.qpos[qadr] = PARK

    # EACH FACE IS GRADED ONCE, in the index position where it is most face-on. Without
    # this a face visible from two adjacent index positions has its defects counted
    # twice, which inflates exactly the counts the decision is made on.
    best = {}                                   # face_id -> (cosang, features)
    shots = []
    for deg in cfg.index_deg:
        idx_err = np.deg2rad(rng.normal(0, cfg.index_repeat_deg))
        data.qpos[tt] = np.deg2rad(deg) + yaw0 + idx_err
        mujoco.mj_forward(model, data)
        renderer.update_scene(data, camera=cfg.cam)
        rgb = renderer.render()
        for fid, cosang, roi in face_regions(model, data, cfg, deg):
            if fid in best and best[fid][0] <= cosang:
                continue                        # a more face-on view already graded it
            f = image_features(rgb, roi, cfg)
            if f is not None:
                best[fid] = (cosang, f)
        if save is not None:
            shots.append((rgb, deg))
    feats = [f for _, f in best.values()]

    model.light_diffuse[:] = base_light
    model.body_pos[cab] = base_pos
    pred, sc = classify(feats, cfg)
    row = {"seed": seed, "truth": truth, "pred": pred,
           "n_dent": nd, "n_scr": ns, "n_soil": no, **sc}
    if save is not None:
        save.append((row, shots))
    return row


# ============================================================ reporting
def confusion(rows):
    M = {t: {p: 0 for p in GRADES} for t in GRADES}
    for r in rows:
        M[r["truth"]][r["pred"]] += 1
    return M


def false_easy_rate(rows):
    """THE number. A unit that genuinely needs work, graded EASY and sent down the
    cosmetic path. The opposite error only wastes effort."""
    risky = [r for r in rows if r["truth"] in ("medium", "hard")]
    if not risky:
        return 0.0
    return sum(r["pred"] == "easy" for r in risky) / len(risky)


def missed_hard_rate(rows):
    """A HARD unit graded anything less. Dents have no remedy in any of the ten stages,
    so this unit goes back to a customer with damage no station will fix."""
    hard = [r for r in rows if r["truth"] == "hard"]
    if not hard:
        return 0.0
    return sum(r["pred"] != "hard" for r in hard) / len(hard)


def report(rows, cfg=CFG):
    n = len(rows)
    M = confusion(rows)
    acc = sum(M[c][c] for c in GRADES) / n
    print(f"\nTRIAGE: {n} units | accuracy {acc*100:.1f}%")
    print(f"  {'truth\\pred':>12} " + " ".join(f"{p:>8}" for p in GRADES) + "      acc")
    for t in GRADES:
        tot = sum(M[t].values())
        a = M[t][t] / tot * 100 if tot else 0.0
        print(f"  {t:>12} " + " ".join(f"{M[t][p]:>8}" for p in GRADES) + f"  {a:>7.1f}%")
    fe = false_easy_rate(rows)
    mh = missed_hard_rate(rows)
    print(f"  FALSE-EASY RATE : {fe*100:.1f}%  <-- the error that matters "
          f"(needs work, graded easy)")
    print(f"  MISSED-HARD RATE: {mh*100:.1f}%  (dents have no remedy in any stage)")
    over = sum(1 for r in rows if r["truth"] == "easy" and r["pred"] != "easy")
    ne = sum(1 for r in rows if r["truth"] == "easy")
    if ne:
        print(f"  over-treatment  : {over/ne*100:.1f}%  (easy unit sent for work -- "
              f"wasteful, not unsafe)")
    print("\n  The class NAMES are DrinkPrime's; the BOUNDARIES are ours -- no document")
    print("  in their set defines Easy/Medium/Hard. See dp_process.MISSING.")
    return {"n": n, "accuracy": acc, "false_easy_rate": fe, "missed_hard_rate": mh,
            "confusion": M, "t_dent": cfg.t_dent, "t_scratch": cfg.t_scratch}


# ============================================================ entry points
def run(n, seed0, cfg=CFG, verbose=True):
    model, data, pools = load_scene(cfg)
    r = mujoco.Renderer(model, cfg.cam_h, cfg.cam_w)
    rows = []
    for k in range(n):
        rows.append(grade_unit(model, data, pools, r, seed0 + k, cfg))
        if verbose and (k + 1) % 10 == 0:
            print(f"    ... {k+1}/{n}")
    return rows


def calibrate(n, cfg=CFG):
    """Fit the two thresholds on CALIBRATION seeds 9000+, disjoint from every eval seed.

    Objective, in order: drive FALSE-EASY to zero, then MISSED-HARD, then maximise
    accuracy. That ordering is the whole point -- an accuracy-optimal threshold that
    sends damaged units down the cosmetic path is worse than a slightly blunter one
    that does not.
    """
    print(f"CALIBRATION on seeds 9000-{9000+n-1} (disjoint from eval seeds)")
    rows = run(n, 9000, cfg)
    D = np.array([r["dent"] for r in rows])
    S = np.array([r["scratch"] for r in rows])
    T = [r["truth"] for r in rows]

    cand_d = np.unique(np.quantile(D, np.linspace(0.02, 0.98, 120)))
    cand_s = np.unique(np.quantile(S, np.linspace(0.02, 0.98, 120)))
    best = None
    for td in cand_d:
        hard_pred = D > td
        for ts in cand_s:
            pred = np.where(hard_pred, "hard", np.where(S > ts, "medium", "easy"))
            fe_d = [(p, t) for p, t in zip(pred, T) if t in ("medium", "hard")]
            fe = sum(p == "easy" for p, _ in fe_d) / max(len(fe_d), 1)
            hd = [(p, t) for p, t in zip(pred, T) if t == "hard"]
            mh = sum(p != "hard" for p, _ in hd) / max(len(hd), 1)
            acc = np.mean([p == t for p, t in zip(pred, T)])
            key = (fe, mh, -acc)
            if best is None or key < best[0]:
                best = (key, td, ts, acc, fe, mh)
    _, td, ts, acc, fe, mh = best
    print(f"  fitted t_dent    = {td:.6f}")
    print(f"  fitted t_scratch = {ts:.6f}")
    print(f"  on the calibration set: accuracy {acc*100:.1f}%, "
          f"false-easy {fe*100:.1f}%, missed-hard {mh*100:.1f}%")
    print("\n  Paste these into TriageConfig.t_dent / t_scratch, then run --eval on")
    print("  held-out seeds. Calibration numbers are NOT a result.")
    return td, ts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", type=int, metavar="N")
    ap.add_argument("--seed0", type=int, default=200)
    ap.add_argument("--calibrate", type=int, metavar="N")
    ap.add_argument("--views", type=int, metavar="SEED",
                    help="render one unit's views + masks to /tmp for inspection")
    a = ap.parse_args()

    if a.calibrate:
        calibrate(a.calibrate)
    elif a.eval:
        if a.seed0 < 200:
            print("refusing: eval seeds must start at 200+ (9000+ is calibration)")
            sys.exit(2)
        print(f"EVAL on held-out seeds {a.seed0}-{a.seed0+a.eval-1}")
        rows = run(a.eval, a.seed0)
        stats = report(rows)
        with open("stats_v5_triage.json", "w") as f:
            json.dump(stats, f, indent=2, default=str)
        print("\nwrote stats_v5_triage.json")
    elif a.views is not None:
        import PIL.Image as I
        model, data, pools = load_scene()
        r = mujoco.Renderer(model, CFG.cam_h, CFG.cam_w)
        save = []
        row = grade_unit(model, data, pools, r, a.views, save=save)
        print(row)
        _, shots = save[0]
        strip = [s[0][s[1][0]:s[1][1], s[1][2]:s[1][3]] for s in shots]
        h = min(s.shape[0] for s in strip)
        I.fromarray(np.concatenate([s[:h] for s in strip], axis=1)).save("/tmp/v5_triage_views.png")
        print("wrote /tmp/v5_triage_views.png")
    else:
        ap.print_help()
        sys.exit(1)
