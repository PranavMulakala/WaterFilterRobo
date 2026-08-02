"""
Sim POC v4 — DrinkPrime refurbishment cell: INSPECT, CLEAN, or REPLACE.

v3 answered "can a robot swap a cartridge?". v4 answers the question the founder
actually set as the funding bar: can the cell *decide* what a returned unit needs,
from an image, and then do it?

    EXTRACT   untwist the installed cartridge out of its bayonet lock, lift it clear
    INSPECT   present it to a fixed station camera; RENDER the frame and run a real
              classifier ON THE PIXELS to grade its condition
    ROUTE     clean -> reinstall straight away
              light -> cleaning station -> re-inspect -> reinstall
              heavy -> bin -> install a fresh cartridge (the v3 path)

Extends v3, which extends v2. ik_step, down_mat, the yaw servo, the tip-following
compliant descent, the bayonet untwist and the whole insertion phase table are
imported and reused. sim_poc2.py and sim_poc3.py are untouched.

WHAT IS AND IS NOT MODELLED
  * The inspection is real image processing. A frame is rendered from the station
    camera and graded on pixel statistics (coverage of chalky deposits over the
    cartridge body, plus intensity texture). Scale is represented as actual geometry
    -- a pool of small deposit geoms, a random subset revealed per trial -- NOT as a
    flat colour swap, so the classifier cannot simply read back a value we wrote.
  * Deposits are VISUAL ONLY (no collision, negligible mass). Real scale would change
    fit and mass; that is not modelled.
  * Cleaning is modelled as dip + dwell + agitate in a solution tank. There is no
    fluid or chemical simulation. Success is not asserted -- it is VERIFIED by
    re-inspecting the part with the same classifier on a fresh render.

CLI:
  python3 sim_poc4.py --eval 25          # full refurb loop over randomized conditions
  python3 sim_poc4.py --inspect-eval 90  # inspection classifier only (fast)
  python3 sim_poc4.py --render idx seed speed
  python3 sim_poc4.py --cards | --concat
"""

import argparse, json, os
from dataclasses import dataclass, field
import numpy as np
import mujoco

import sim_poc2 as v2
import sim_poc3 as v3
from sim_poc2 import (ik_step, down_mat, wrap_pi, _font, CART_HALF, SPAWN_Z,
                      GRASP_OFF, SEAT_Z, TWIST_DEG, PERCEPTION_NOISE, ENTRY_TOL,
                      GRIP_ECC_MAX, Z_LAG, INSERT_UPRIGHT, INSERT_DEPTH_Z, FPS)
from sim_poc3 import lug_err, LUG_TARGET


# ===================================================================== config
@dataclass(frozen=True)
class RefurbConfig:
    """Every swap-in point for real geometry / a real process lives here.

    When DrinkPrime's plant video and tech docs arrive, the intent is that adapting
    the cell means editing THIS object and the PROCESS table below -- not the
    controller. Geometry constants must stay consistent with the scene XML.
    """
    xml: str = "ufactory_xarm7/cartridge_scene_v4.xml"
    stats_path: str = "stats_v4.json"

    # --- part + socket geometry (swap-in point: real cartridge SKU) -------------
    cart_half: float = CART_HALF          # 55 mm half-length
    cart_radius: float = 0.0215
    seat_z: float = SEAT_Z                # seated centre height
    sock: tuple = (0.46, 0.26)
    spawn_c: tuple = (0.46, -0.26)
    spawn_jitter: float = 0.04
    cap_tcp: float = 0.131                # tcp height to grip a seated cartridge's cap
    cap_hang: float = 0.083               # measured: part centre hangs this far below the
                                          # tcp when held by the cap (v3 trace: tcp 0.300 -> cart 0.217)
    lock_yaw_range: tuple = (np.deg2rad(25.0), np.deg2rad(50.0))

    # --- stations (swap-in point: real cell layout) ----------------------------
    bin_xy: tuple = (0.46, 0.0)
    tank_xy: tuple = (0.28, -0.42)
    inspect_xyz: tuple = (0.28, 0.42, 0.30)
    nest_xy: tuple = (0.32, -0.28)        # staging nest (chamfered cup) -- see scene XML
    # release the part with its bottom ~6 mm above the nest chamfer. Measured capture
    # envelope of the nest: seats reliably up to 8 mm lateral offset and 8 deg tilt.
    nest_release_part_z: float = 0.141
    stage_xy: tuple = (0.515, -0.205)     # (unused since the nest replaced flat staging)
    stage_clearance: float = 0.060        # fresh spawn is kept this far from staging

    # --- condition model (swap-in point: real soiling grades) ------------------
    # Ground truth is crisp -- non-overlapping deposit counts. The measurement
    # overlap that makes this non-trivial comes from single-view occlusion,
    # lighting and presentation pose, not from fuzzing the labels.
    cond_counts: tuple = (("clean", 0, 3), ("light", 4, 16), ("heavy", 17, 34))
    cond_weights: tuple = (0.30, 0.40, 0.30)

    # --- inspection (swap-in point: real camera + real grading rule) -----------
    inspect_views: int = 2                # 180 deg apart; see PAIN_JOURNAL
    cam_w: int = 640
    cam_h: int = 480
    # FROZEN on calibration seeds 9000+, disjoint from every eval seed, and fit on
    # IN-CELL presentations -- the arm actually holding and presenting the part -- not
    # on a rig that teleports it into position. Fitting on the rig was worth 37 points
    # of accuracy when deployed (see PAIN_JOURNAL); a vision model is only as valid as
    # the fixture that presents the part.
    # score = coverage + TEX_W * texture
    tex_w: float = 0.70
    t_clean: float = 0.1018
    t_light: float = 0.1576
    v_part: float = 0.13                  # part vs matte backdrop
    v_deposit: float = 0.62               # chalky deposit vs dull body
    s_lug: float = 0.45                   # drops the saturated yellow lugs
    band: tuple = (0.16, 0.82)            # body band: excludes cap and lug row

    # --- cleaning (swap-in point: real process step) ---------------------------
    lost_hang: float = 0.150              # hang beyond this = the part is out of the jaws
    dip_tcp: float = 0.160
    agitate_hz: float = 1.5
    # Agitation is VERTICAL, not rotational. A 2 Hz wrist oscillation was tried first
    # and it shook the part out of the jaws: the cap is a small friction patch (it
    # already loses 16-18% of commanded rotation in the untwist), and asking it to
    # transmit sustained cyclic TORQUE walks the part loose -- measured slipping at
    # ~2.5 mm/s, then a clean drop during the following phase. Bobbing loads the grip
    # along gravity, its strong axis. See PAIN_JOURNAL.
    agitate_amp_z: float = 0.010          # m, vertical bob amplitude
    clean_dwell_s: float = 2.5

    # --- domain randomization (Phase C) ---------------------------------------
    # A single fixed simulation is trivially overfittable: every number before this
    # was measured against exactly one set of physical parameters that we chose. DR
    # perturbs them per trial so the reported rate means "robust to this much
    # uncertainty" rather than "works on our one model".
    #   * mass      -- real cartridges vary with fill and scale build-up
    #   * friction  -- surface finish, wetness, wear
    #   * cell height -- THE fixture is never exactly where the robot thinks it is.
    #     The whole cell (bench, socket, tray, bin, tank, nest, booth) shifts, while
    #     the robot's commanded heights do NOT. That is a calibration error, which is
    #     the single most common real-world cause of a working cell going wrong.
    dr: bool = False
    dr_scale: float = 1.0                 # multiplier on all three magnitudes
    dr_mass: float = 0.20                 # +-20%
    dr_friction: float = 0.30             # +-30%
    dr_table: float = 0.005               # +-5 mm

    # --- honesty labels shown on the HUD --------------------------------------
    clean_caveat: str = "cleaning modeled as dip + dwell; chemistry not simulated"
    deposit_caveat: str = "scale deposits are visual only; fit/mass unchanged"


CFG = RefurbConfig()

# Process table. Each route is an ordered list of stage names; the phase builder
# expands them. Swapping in DrinkPrime's real process means editing this table.
PROCESS = {
    "clean": ["EXTRACT", "INSPECT", "REINSTALL"],
    "light": ["EXTRACT", "INSPECT", "CLEAN", "REINSPECT", "REINSTALL"],
    "heavy": ["EXTRACT", "INSPECT", "DISCARD", "REPLACE"],
}
COND_NAMES = [c[0] for c in CFG.cond_counts]


# ============================================================ image processing
def _hsv(rgb):
    a = rgb.astype(np.float32) / 255.0
    mx, mn = a.max(2), a.min(2)
    return np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0), mx


def image_features(rgb, cfg=CFG):
    """Grade one rendered frame. Returns None if no part is in view.

    This is deliberately simple, explainable CV -- threshold + region statistics --
    because it has to be defensible to a customer, not impressive to a reviewer.
    """
    s, v = _hsv(rgb)
    part = v > cfg.v_part
    if part.sum() < 500:
        return None
    ys, xs = np.where(part)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    h = y1 - y0
    band = np.zeros_like(part)
    band[y0 + int(cfg.band[0] * h): y0 + int(cfg.band[1] * h), x0:x1 + 1] = True
    body = part & band & (s < cfg.s_lug)
    if body.sum() < 300:
        return None
    vb = v[body]
    return {"coverage": float((vb > cfg.v_deposit).mean()),
            "tex": float(vb.std()),
            "npx": int(body.sum())}


def classify(feats, cfg=CFG):
    """feats: list of per-view features. Merge, then apply the frozen thresholds."""
    feats = [f for f in feats if f]
    if not feats:
        return "heavy", float("nan")      # can't see it -> fail safe to replace
    cov = max(f["coverage"] for f in feats)
    tex = max(f["tex"] for f in feats)
    score = cov + cfg.tex_w * tex
    if score < cfg.t_clean:
        return "clean", score
    if score < cfg.t_light:
        return "light", score
    return "heavy", score


# ============================================================ scene helpers
def deposit_ids(model):
    return [i for i in range(model.ngeom)
            if (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, i) or "").startswith("dep")]


def set_deposits(model, dep, n, rng):
    """Reveal a random subset of the deposit pool. Cleaning later HIDES these same
    geoms, so the camera observes the identical mechanism before and after."""
    for g in dep:
        model.geom_rgba[g][3] = 0.0
    if n <= 0:
        return []
    chosen = list(rng.choice(dep, size=min(n, len(dep)), replace=False))
    for g in chosen:
        model.geom_rgba[g][3] = 1.0
        model.geom_rgba[g][:3] = np.clip(np.array([0.90, 0.90, 0.86]) + rng.normal(0, 0.04, 3), 0.5, 1.0)
    return chosen


def sample_condition(rng, cfg=CFG):
    i = rng.choice(len(cfg.cond_counts), p=list(cfg.cond_weights))
    name, lo, hi = cfg.cond_counts[i]
    return name, int(rng.integers(lo, hi + 1))


# ============================================================ inspection eval
def inspect_eval(n, cfg=CFG, seed0=0, verbose=True):
    """Classifier-only evaluation: no arm, no manipulation. Renders presentations
    with realistic jitter and grades them. Fast, and isolates vision error from
    mechanical error -- they are reported separately by design."""
    model = mujoco.MjModel.from_xml_path(cfg.xml)
    dep = deposit_ids(model)
    spent_vadr = model.joint("spent_free").dofadr[0]
    r = mujoco.Renderer(model, cfg.cam_h, cfg.cam_w)
    adr = model.joint("spent_free").qposadr[0]
    rows = []
    for k in range(n):
        rng = np.random.default_rng(seed0 + k)
        truth, ndep = sample_condition(rng, cfg)
        set_deposits(model, dep, ndep, rng)
        base = model.light_diffuse.copy()
        model.light_diffuse[:] = np.clip(base * rng.uniform(0.75, 1.25), 0, 1)
        yaw0 = rng.uniform(0, 2 * np.pi)
        tilt = rng.normal(0, np.deg2rad(2.0))
        pos = np.array(cfg.inspect_xyz) + rng.normal(0, 0.003, 3)
        feats = []
        data = mujoco.MjData(model)
        mujoco.mj_resetDataKeyframe(model, data, model.key("home").id)
        for vw in range(cfg.inspect_views):
            yaw = yaw0 + vw * (2 * np.pi / cfg.inspect_views)
            cy, sy = np.cos(yaw / 2), np.sin(yaw / 2)
            ct, st = np.cos(tilt / 2), np.sin(tilt / 2)
            q = np.array([cy * ct, cy * st, sy * st, sy * ct])
            data.qpos[adr:adr + 3] = pos
            data.qpos[adr + 3:adr + 7] = q / np.linalg.norm(q)
            mujoco.mj_forward(model, data)
            r.update_scene(data, camera="inspect")
            feats.append(image_features(r.render(), cfg))
        model.light_diffuse[:] = base
        pred, score = classify(feats, cfg)
        rows.append({"seed": seed0 + k, "truth": truth, "pred": pred,
                     "n_dep": ndep, "score": score})
    if verbose:
        report_inspection(rows, n)
    return rows


def confusion(rows):
    M = {t: {p: 0 for p in COND_NAMES} for t in COND_NAMES}
    for r in rows:
        M[r["truth"]][r["pred"]] += 1
    return M


def false_clean_rate(rows):
    """THE number: a part that genuinely needs work, graded as needing none.
    This is the error that puts a bad cartridge back into a customer's unit.
    The opposite error (clean part sent for replacement) only wastes a part."""
    risky = [r for r in rows if r["truth"] in ("light", "heavy")]
    if not risky:
        return 0.0
    return sum(r["pred"] == "clean" for r in risky) / len(risky)


def report_inspection(rows, n):
    M = confusion(rows)
    acc = sum(M[c][c] for c in COND_NAMES) / n
    print(f"INSPECTION: {n} presentations | accuracy {acc*100:.1f}%")
    print(f"  {'truth\\pred':>12} " + " ".join(f"{p:>7}" for p in COND_NAMES) + "     acc")
    for t in COND_NAMES:
        tot = sum(M[t].values())
        a = M[t][t] / tot * 100 if tot else 0
        print(f"  {t:>12} " + " ".join(f"{M[t][p]:>7}" for p in COND_NAMES) + f"  {a:>6.1f}%")
    fc = false_clean_rate(rows)
    print(f"  FALSE-CLEAN RATE: {fc*100:.1f}%  <-- the error that matters "
          f"(needs work, graded clean)")
    over = sum(1 for r in rows if r["truth"] == "clean" and r["pred"] != "clean")
    ct = sum(1 for r in rows if r["truth"] == "clean")
    print(f"  over-treatment  : {over/ct*100:.1f}%  (clean part sent for work - wasteful, not unsafe)"
          if ct else "")
    return {"accuracy": acc, "false_clean_rate": fc, "confusion": M}


# ============================================================ phase helpers
GRIP_OPEN, GRIP_CLOSED = 0.0, 240.0


def _resolve(tgt, dyn):
    """A phase target is either a fixed xyz, or ("KEY", z) taking xy from `dyn`
    at runtime -- needed because where a cleaned part gets staged is not known
    until it has been placed."""
    if isinstance(tgt[0], str):
        return np.array([*dyn[tgt[0]], tgt[1]], dtype=float)
    return np.array(tgt, dtype=float)


def _insertion_phases(body, det_key, grasp_z, cfg, reinstall=False):
    """v3's insertion sequence, verbatim in structure, parameterised by which
    cartridge is being installed and where it was perceived."""
    S = cfg.sock
    if reinstall:
        # already holding the part: go straight to alignment. Z targets are PART
        # centre heights, converted to wrist targets at runtime (see PART_REF).
        return [
            # NO PRE-INSERT on a reinstall. PRE-INSERT uses the coarse centering law
            # tcp + (SOCK - cart_xy) -- the same integrator that caused the v2 wedge.
            # With a firm body grip it is harmless; with the loose cap grip the part
            # is a pendulum on a compliant joint and that law excites it (measured:
            # swings 17 mm off-axis and tilts 40 deg, then slips out). ORIENT LUGS
            # already centres the part to <1 mm, so INSERT's tip-following law -- the
            # one proven safe against contact -- owns the entire descent.
            ("ORIENT LUGS",  (*S, 0.232),      GRIP_CLOSED, 1.2, 0.005, 0.6,  "yaw", 16.0, body),
            ("INSERT",       (*S, 0.118),      GRIP_CLOSED, 0.3, 0.005, 0.12, "yaw", 24.0, body),
            ("DROP-SEAT",    (*S, 0.126),      GRIP_OPEN,   0.8, 0.005, 0.3,  False, 4.0,  body),
            ("REGRIP ALIGN", (*S, 0.131),      GRIP_OPEN,   0.4, 0.003, 0.3,  False, 6.0,  body),
            ("REGRIP CAP",   (*S, 0.131),      GRIP_CLOSED, 1.0, 0.012, 0.5,  False, 3.0,  body),
            ("TWIST-LOCK",   (*S, 0.131),      GRIP_CLOSED, 1.4, 0.006, 0.5,  False, 4.0,  body),
            ("RELEASE",      (*S, 0.131),      GRIP_OPEN,   0.8, 0.012, 1.0,  False, 3.0,  body),
            ("RETREAT",      (*S, 0.34),       GRIP_OPEN,   0.4, 0.030, 1.0,  False, 4.0,  None),
        ]
    return _pick_phases(body, det_key, grasp_z) + _insert_tail(body, cfg)


def _pick_phases(body, det_key, grasp_z):
    """pick a standing cartridge (tray or staging nest) with the proven BODY grip"""
    return [
        ("APPROACH",     (det_key, 0.28),      GRIP_OPEN,   0.1, 0.015, 1.0,  False, 6.0,  body),
        ("DESCEND",      (det_key, grasp_z),   GRIP_OPEN,   0.3, 0.008, 0.6,  False, 5.0,  body),
        ("GRASP",        (det_key, grasp_z),   GRIP_CLOSED, 1.2, 0.012, 1.0,  False, 3.0,  body),
        ("LIFT",         (det_key, 0.35),      GRIP_CLOSED, 0.2, 0.020, 1.0,  False, 4.0,  body),
    ]


def _insert_tail(body, cfg):
    S = cfg.sock
    return [
        ("TRANSIT",      (*S, 0.35),           GRIP_CLOSED, 0.5, 0.012, 0.5,  False, 8.0,  body),
        ("RECOVER GRIP", (*S, 0.131),          GRIP_CLOSED, 0.6, 0.012, 0.5,  False, 3.0,  body),
        ("RECOVER LIFT", (*S, 0.30),           GRIP_CLOSED, 0.3, 0.020, 0.6,  False, 6.0,  body),
        ("ORIENT LUGS",  (*S, 0.24),           GRIP_CLOSED, 1.2, 0.005, 0.6,  "yaw", 16.0, body),
        ("PRE-INSERT",   (*S, 0.19),           GRIP_CLOSED, 0.6, 0.004, 0.25, "yaw", 14.0, body),
        ("INSERT",       (*S, 0.126),          GRIP_CLOSED, 0.3, 0.005, 0.12, "yaw", 14.0, body),
        ("DROP-SEAT",    (*S, 0.126),          GRIP_OPEN,   0.8, 0.005, 0.3,  False, 4.0,  body),
        ("REGRIP ALIGN", (*S, 0.131),          GRIP_OPEN,   0.4, 0.003, 0.3,  False, 6.0,  body),
        ("REGRIP CAP",   (*S, 0.131),          GRIP_CLOSED, 1.0, 0.012, 0.5,  False, 3.0,  body),
        ("TWIST-LOCK",   (*S, 0.131),          GRIP_CLOSED, 1.4, 0.006, 0.5,  False, 4.0,  body),
        ("RELEASE",      (*S, 0.131),          GRIP_OPEN,   0.8, 0.012, 1.0,  False, 3.0,  body),
        ("RETREAT",      (*S, 0.34),           GRIP_OPEN,   0.4, 0.030, 1.0,  False, 4.0,  None),
    ]


STAGE_OF = {}
for _n in ("PERCEPTION", "APPROACH SPENT", "DESCEND CAP", "GRIP CAP", "UNTWIST", "EXTRACT"):
    STAGE_OF[_n] = "EXTRACT"
for _n in ("CARRY TO INSPECT", "PRESENT A", "FLIP", "PRESENT B",
           "CARRY TO RECHECK", "RECHECK A", "FLIP2", "RECHECK B"):
    STAGE_OF[_n] = "INSPECT"
for _n in ("CARRY TO TANK", "DIP", "AGITATE", "LIFT OUT", "DRAIN"):
    STAGE_OF[_n] = "CLEAN"
for _n in ("CARRY TO BIN", "DISCARD", "CLEAR BIN"):
    STAGE_OF[_n] = "REPLACE"
for _n in ("CARRY TO NEST", "LOWER TO NEST", "RELEASE PART", "STEP BACK",
           "CARRY TO STAGE", "PLACE"):
    STAGE_OF[_n] = "REINSTALL"
for _n in ("APPROACH", "DESCEND", "GRASP", "LIFT", "TRANSIT", "RECOVER GRIP",
           "RECOVER LIFT", "ORIENT LUGS", "PRE-INSERT", "INSERT", "DROP-SEAT",
           "REGRIP ALIGN", "REGRIP CAP", "TWIST-LOCK", "RELEASE", "RETREAT"):
    STAGE_OF[_n] = "INSTALL"


# ============================================================ the refurb trial
def run_trial(seed, frame_cb=None, cfg=CFG):
    rng = np.random.default_rng(seed)
    model = mujoco.MjModel.from_xml_path(cfg.xml)
    data = mujoco.MjData(model)
    insp_r = mujoco.Renderer(model, cfg.cam_h, cfg.cam_w)

    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "link_tcp")
    fresh_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cartridge")
    spent_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "spent_cartridge")
    arm = [f"joint{i}" for i in range(1, 8)]
    dof_ids = np.array([model.joint(n).dofadr[0] for n in arm])
    qpos_ids = np.array([model.joint(n).qposadr[0] for n in arm])
    act_ids = np.array([model.actuator(f"act{i}").id for i in range(1, 8)])
    grip_id = model.actuator("gripper").id
    jnt_range = np.array([model.joint(n).range for n in arm])
    dep = deposit_ids(model)
    spent_vadr = model.joint("spent_free").dofadr[0]

    # --- domain randomization ---------------------------------------------
    dz = 0.0
    if cfg.dr:
        k = cfg.dr_scale
        for bid in (fresh_id, spent_id):
            f = 1.0 + rng.uniform(-cfg.dr_mass, cfg.dr_mass) * k
            model.body_mass[bid] *= f
            model.body_inertia[bid] *= f
        for gid in range(model.ngeom):
            if model.geom_bodyid[gid] in (fresh_id, spent_id):
                model.geom_friction[gid] *= (
                    1.0 + rng.uniform(-cfg.dr_friction, cfg.dr_friction) * k)
        # shift the whole cell vertically; the robot's targets stay put
        dz = float(rng.uniform(-cfg.dr_table, cfg.dr_table) * k)
        floor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "floor")
        for gid in range(model.ngeom):
            if model.geom_bodyid[gid] == 0 and gid != floor_id:
                model.geom_pos[gid][2] += dz
        hid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "housing")
        model.body_pos[hid][2] += dz
        for sname in ("inspect_pt", "tank_pt", "nest_pt", "bin_center"):
            sid_ = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, sname)
            if sid_ >= 0:
                model.site_pos[sid_][2] += dz
    seat_z = cfg.seat_z + dz

    mujoco.mj_resetDataKeyframe(model, data, model.key("home").id)

    # --- condition of the returned cartridge -------------------------------
    truth, n_dep = sample_condition(rng, cfg)
    set_deposits(model, dep, n_dep, rng)
    base_light = model.light_diffuse.copy()
    model.light_diffuse[:] = np.clip(base_light * rng.uniform(0.80, 1.20), 0, 1)

    # --- spent cartridge: installed and twist-locked ------------------------
    lock_yaw = rng.uniform(*cfg.lock_yaw_range)
    b = model.joint("spent_free").qposadr[0]
    data.qpos[b:b + 3] = [*cfg.sock, seat_z]
    data.qpos[b + 3:b + 7] = [np.cos(lock_yaw / 2), 0, 0, np.sin(lock_yaw / 2)]

    # --- fresh cartridge in the tray, kept clear of the staging spot --------
    for _ in range(200):
        spawn = np.array(cfg.spawn_c) + rng.uniform(-cfg.spawn_jitter, cfg.spawn_jitter, 2)
        if np.linalg.norm(spawn - np.array(cfg.stage_xy)) > cfg.stage_clearance:
            break
    yaw0 = rng.uniform(0, 2 * np.pi)
    a_ = model.joint("cartridge_free").qposadr[0]
    data.qpos[a_:a_ + 3] = [*spawn, SPAWN_Z + 0.002 + dz]
    data.qpos[a_ + 3:a_ + 7] = [np.cos(yaw0 / 2), 0, 0, np.sin(yaw0 / 2)]
    mujoco.mj_forward(model, data)

    dyn = {"FRESH": spawn + rng.normal(0, PERCEPTION_NOISE, 2),
           "STAGE": np.array(cfg.stage_xy, dtype=float)}
    grasp_z = SPAWN_Z + GRASP_OFF
    IX = cfg.inspect_xyz
    present_z = IX[2] + cfg.cap_hang        # tcp height that centres the part on the camera axis
    TK = cfg.tank_xy

    # --- phase table: common prefix; the route is appended after grading ----
    P = [
        ("PERCEPTION",       None,                  GRIP_OPEN,   0.8, None,  1.0,  False,  2.0,  None),
        ("APPROACH SPENT",   (*cfg.sock, 0.30),     GRIP_OPEN,   0.1, 0.015, 1.0,  False,  6.0,  None),
        ("DESCEND CAP",      (*cfg.sock, cfg.cap_tcp), GRIP_OPEN, 0.3, 0.006, 0.4, False,  6.0,  None),
        ("GRIP CAP",         (*cfg.sock, cfg.cap_tcp), GRIP_CLOSED, 1.0, 0.012, 0.5, False, 3.0, "spent"),
        ("UNTWIST",          (*cfg.sock, cfg.cap_tcp), GRIP_CLOSED, 0.5, 0.008, 0.5, "yaw", 10.0, "spent"),
        ("EXTRACT",          (*cfg.sock, 0.30),     GRIP_CLOSED, 0.3, 0.020, 0.18, "yaw", 10.0, "spent"),
        ("CARRY TO INSPECT", (IX[0], IX[1], present_z), GRIP_CLOSED, 0.5, 0.012, 0.5, False, 10.0, "spent"),
        ("PRESENT A",        (IX[0], IX[1], present_z), GRIP_CLOSED, 0.6, 0.010, 0.4, False, 5.0, "spent"),
        ("FLIP",             (IX[0], IX[1], present_z), GRIP_CLOSED, 0.4, 0.012, 0.5, "flip", 8.0, "spent"),
        ("PRESENT B",        (IX[0], IX[1], present_z), GRIP_CLOSED, 0.6, 0.010, 0.4, False, 5.0, "spent"),
    ]
    # Set the part DOWN, release it while stationary, and only then withdraw. An
    # earlier version opened the jaws in the same phase as the 300 mm withdrawal, so
    # the part was carried partway up and dropped -- it landed on its side and every
    # downstream ORIENT LUGS timed out. Place/release/withdraw must be three phases.
    # REINSTALL: put the part straight back in, still held by its cap. An earlier
    # version set it down at a staging spot and re-gripped it by the body, which
    # failed every time -- the cap grip's hang offset is unstable (42-83 mm), so the
    # part arrived tilted, toppled on release, and every downstream ORIENT LUGS timed
    # out on a cartridge lying on its side. The fix is this project's own recurring
    # lesson: reference the PART, not the tool. The approach heights below are the
    # part's desired centre height; the wrist target is derived each step from the
    # LIVE measured hang offset, so the same numbers work for a 4 mm body grip and an
    # 80 mm cap grip alike.
    # REINSTALL: set the part into the chamfered staging nest, release, then re-grip
    # it by the BODY and run the proven insertion. Inserting straight from the cap
    # grip was tried and fails -- that grip's hang offset wanders 42-83 mm, so the
    # part arrives tilted and is dropped. The nest exists so the weak grip only has
    # to get the part roughly over a hole, and the chamfer does the rest.
    NST = cfg.nest_xy
    NEST_PLACE = [
        ("CARRY TO NEST",  (*NST, 0.30),        GRIP_CLOSED, 0.5, 0.012, 0.5, False, 10.0, "spent"),
        ("LOWER TO NEST",  (*NST, 0.30),        GRIP_CLOSED, 0.4, 0.010, 0.10, False, 12.0, "spent"),
        ("RELEASE PART",   (*NST, 0.30),        GRIP_OPEN,   1.0, 0.030, 0.10, False,  4.0, "spent"),
        ("STEP BACK",      (*NST, 0.34),        GRIP_OPEN,   0.3, 0.030, 0.8, False,  5.0, None),
    ]
    NEST_PICK = _pick_phases("spent", "STAGED", grasp_z)
    TANK = [
        ("CARRY TO TANK",  (*TK, 0.30),         GRIP_CLOSED, 0.4, 0.015, 0.5, False,  9.0, "spent"),
        ("DIP",            (*TK, cfg.dip_tcp),  GRIP_CLOSED, 0.4, 0.008, 0.3, False,  7.0, "spent"),
        ("AGITATE",        (*TK, cfg.dip_tcp),  GRIP_CLOSED, 0.2, 0.030, 0.5, "agit", 8.0, "spent"),
        ("LIFT OUT",       (*TK, 0.30),         GRIP_CLOSED, 0.3, 0.020, 0.35, False, 8.0, "spent"),
        ("DRAIN",          (*TK, 0.30),         GRIP_CLOSED, 0.8, 0.020, 0.5, False,  4.0, "spent"),
    ]
    RECHECK = [
        ("CARRY TO RECHECK", (IX[0], IX[1], present_z), GRIP_CLOSED, 0.5, 0.012, 0.5, False, 10.0, "spent"),
        ("RECHECK A",        (IX[0], IX[1], present_z), GRIP_CLOSED, 0.6, 0.010, 0.4, False, 5.0, "spent"),
        ("FLIP2",            (IX[0], IX[1], present_z), GRIP_CLOSED, 0.4, 0.012, 0.5, "flip", 8.0, "spent"),
        ("RECHECK B",        (IX[0], IX[1], present_z), GRIP_CLOSED, 0.6, 0.010, 0.4, False, 5.0, "spent"),
    ]
    # Cleaning happens AFTER the part is re-gripped by its BODY. Dipping it while
    # still held by the cap drops it ~7 s into the wet sequence, every time.
    ROUTE_CLEAN = NEST_PLACE + NEST_PICK + _insert_tail("spent", cfg)
    ROUTE_LIGHT = NEST_PLACE + NEST_PICK + TANK + RECHECK + _insert_tail("spent", cfg)
    ROUTE_HEAVY = [
        ("CARRY TO BIN",     (*cfg.bin_xy, 0.30),   GRIP_CLOSED, 0.4, 0.015, 0.5,  False,  9.0,  "spent"),
        ("DISCARD",          (*cfg.bin_xy, 0.26),   GRIP_OPEN,   1.0, 0.020, 0.6,  False,  4.0,  "spent"),
        ("CLEAR BIN",        (*cfg.bin_xy, 0.34),   GRIP_OPEN,   0.2, 0.030, 1.0,  False,  4.0,  None),
    ] + _insertion_phases("fresh", "FRESH", grasp_z, cfg)
    ROUTES = {"clean": ROUTE_CLEAN, "light": ROUTE_LIGHT, "heavy": ROUTE_HEAVY}

    FOLLOW = ("DROP-SEAT", "REGRIP ALIGN", "REGRIP CAP", "TWIST-LOCK", "RELEASE",
              "RECOVER GRIP", "DISCARD")
    CONTINUOUS_DWELL = ("INSERT",)

    q_des = data.qpos[qpos_ids].copy()
    ik_data = mujoco.MjData(model)
    dt = model.opt.timestep
    base_step = 2.0 * dt
    wp, dwell_left, phase_t = 0, P[0][3], 0.0
    servo_yaw, flip_from, flip_to, agit_from = 0.0, None, None, None
    twist_from = insert_end_yaw = None
    hold_e = None
    retries = untwist_retries = 0
    aborted = False
    t_limit = 180.0

    part_ref = False
    part_lost = False
    hang_ref = None
    feats_a, feats_b, feats_r = [], [], []
    pred = pred_score = None
    verified_clean = None
    route = None
    stage_times = {}

    def capture():
        insp_r.update_scene(data, camera="inspect")
        return image_features(insp_r.render(), cfg)

    while data.time < t_limit and wp < len(P):
        name, tgt, grip, dwell, tol, spd, servo, max_s, btag = P[wp]
        cart_id = spent_id if btag == "spent" else fresh_id
        cmat = data.xmat[cart_id].reshape(3, 3)
        stage_times.setdefault(STAGE_OF.get(name, "?"), data.time)

        if name == "PERCEPTION":
            data.ctrl[act_ids] = q_des
            data.ctrl[grip_id] = grip
            data.qfrc_applied[dof_ids] = data.qfrc_bias[dof_ids]
            mujoco.mj_step(model, data)
            dwell_left -= dt
            if dwell_left <= 0:
                wp += 1; dwell_left = P[wp][3]; phase_t = 0.0
            if frame_cb:
                frame_cb(model, data, name, STAGE_OF.get(name, ""), seed,
                         dict(truth=truth, pred=pred, route=route, verified=verified_clean))
            continue

        # ---- yaw command --------------------------------------------------
        if servo == "yaw":
            servo_yaw -= np.clip(lug_err(cmat), -0.0025, 0.0025)
            sm = data.site_xmat[site_id].reshape(3, 3)
            ym = np.arctan2(-sm[1, 0], sm[0, 0])
            ym += 2 * np.pi * np.round((servo_yaw - ym) / (2 * np.pi))
            servo_yaw = float(np.clip(servo_yaw, ym - v3.YAW_LEAD_MAX, ym + v3.YAW_LEAD_MAX))
        elif servo == "flip":
            # turn the part 180 deg so the camera sees the other face. Single-view
            # occlusion was the dominant inspection error -- see PAIN_JOURNAL.
            if flip_from is None:
                flip_from = servo_yaw
                flip_to = servo_yaw + (np.pi if abs(servo_yaw + np.pi) < abs(servo_yaw - np.pi) else -np.pi)
            servo_yaw = flip_from + (flip_to - flip_from) * min(1.0, phase_t / 1.2)
        elif servo == "agit":
            pass          # yaw is held; agitation is vertical (see the z term below)
        elif name == "TWIST-LOCK":
            if twist_from is None:
                twist_from = servo_yaw
                insert_end_yaw = np.arctan2(cmat[1, 0], cmat[0, 0])
            servo_yaw = twist_from + np.deg2rad(TWIST_DEG) * min(1.0, phase_t / 1.2)
        tmat = down_mat(servo_yaw)

        # ---- lateral command ----------------------------------------------
        tgt_arr = _resolve(tgt, dyn)
        cart_xy = data.xpos[cart_id][:2]
        tcp_xy = data.site_xpos[site_id][:2]
        if name != "INSERT":
            hold_e = None
        if name == "INSERT":
            tip = data.xpos[cart_id] + cmat @ np.array([0.0, 0.0, -CART_HALF])
            if hold_e is None:
                hold_e = np.clip(tcp_xy - tip[:2], -GRIP_ECC_MAX, GRIP_ECC_MAX)
            tgt_arr[:2] = tip[:2] + hold_e
            tgt_arr[2] = max(tgt_arr[2], data.site_xpos[site_id][2] - Z_LAG)
        elif name in ("ORIENT LUGS", "PRE-INSERT"):
            tgt_arr[:2] = tcp_xy + (np.array(cfg.sock) - cart_xy)
        elif name in ("UNTWIST", "EXTRACT"):
            tgt_arr[:2] = np.array(cfg.sock)
        elif name == "AGITATE":
            # dip + dwell + agitate, agitation along the grip's strong axis
            tgt_arr[2] = cfg.dip_tcp + cfg.agitate_amp_z * np.sin(
                2 * np.pi * cfg.agitate_hz * phase_t)
        elif name in FOLLOW:
            tgt_arr[:2] = cart_xy

        if name in ("LOWER TO NEST", "RELEASE PART"):
            hang_live = float(np.clip(
                data.site_xpos[site_id][2] - data.xpos[cart_id][2], 0.02, 0.12))
            tgt_arr[2] = cfg.nest_release_part_z + hang_live + dz
        if name in ("CARRY TO INSPECT", "PRESENT A", "FLIP", "PRESENT B",
                    "CARRY TO RECHECK", "RECHECK A", "FLIP2", "RECHECK B"):
            # Put the PART on the camera axis, not the wrist. cap_hang was a fixed
            # 83 mm constant; the real hang is ~52 mm and unstable, so the part was
            # presented 31 mm high -- off the backdrop, cropped, and the segmentation
            # then swallowed bench and shadow (npx 187k of 307k). Coverage read 0.0
            # and every part graded "clean": accuracy 90% on the calibration rig but
            # 53% in the actual cell, with a 34.8% false-clean rate. No contact here,
            # so tracking live is safe and self-correcting.
            hang_live = float(np.clip(
                data.site_xpos[site_id][2] - data.xpos[cart_id][2], 0.02, 0.12))
            tgt_arr[2] = cfg.inspect_xyz[2] + hang_live
        if part_ref and name in ("ORIENT LUGS", "PRE-INSERT", "INSERT"):
            # LATCH the hang offset once, while the grip is known-good -- do not track
            # it live. Tracking it is an integrator against a failing grip: as the
            # part slips down, hang grows, the wrist target rises, the wrist chases it
            # upward and the part slips further. Measured runaway: hang 52 -> 161 mm
            # inside one phase. Same defect family as the v2 insertion wedge.
            if hang_ref is None:
                hang_ref = float(np.clip(
                    data.site_xpos[site_id][2] - data.xpos[cart_id][2], 0.0, 0.12))
            tgt_arr[2] = tgt_arr[2] + hang_ref
            if name == "INSERT":
                tgt_arr[2] = max(tgt_arr[2], data.site_xpos[site_id][2] - Z_LAG)

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

        # ---- lost-part guard. If the workpiece leaves the jaws, every law that
        # references it starts chasing a part lying on the bench: the tip-following
        # target follows it laterally and the arm walks away (measured: wrist driven
        # to 700 mm). Detect it and fail the trial honestly instead.
        if (grip == GRIP_CLOSED and btag and
                (data.site_xpos[site_id][2] - data.xpos[cart_id][2]) > cfg.lost_hang):
            part_lost = True
            aborted = True
            break

        yaw_ok = True
        if servo == "yaw":
            yaw_ok = abs(lug_err(cmat)) < np.deg2rad(4)

        # ---- completion ----------------------------------------------------
        if name == "UNTWIST":
            done = abs(lug_err(cmat)) < v3.UNTWIST_TOL
        elif name == "EXTRACT":
            done = data.xpos[cart_id][2] > seat_z + 0.085
        elif name in ("FLIP", "FLIP2"):
            done = phase_t > 1.2
        elif name == "AGITATE":
            done = phase_t > cfg.clean_dwell_s
        elif name == "DISCARD":
            done = (np.linalg.norm(data.xpos[cart_id][:2] - np.array(cfg.bin_xy)) < v3.BIN_XY_TOL
                    and data.xpos[cart_id][2] < v3.BIN_Z_MAX + dz)
        elif name == "LOWER TO NEST":
            done = abs(data.xpos[cart_id][2] - cfg.nest_release_part_z) < 0.006
        elif name == "RELEASE PART":
            done = data.xpos[cart_id][2] < 0.080 + dz   # it has dropped into the nest
        elif name == "PLACE":
            # Judge the PART: it must be low AND still upright. The cap-grip hang
            # offset is unstable (measured 42-83 mm) so a wrist-height gate places
            # from an unknown height; and a fast descent tips the part over through
            # the weak cap grip, after which it topples on release and every
            # downstream ORIENT LUGS times out. Hence: slow descent, part-referenced
            # height, and an uprightness term.
            done = ((data.xpos[cart_id][2] - cfg.cart_half) < 0.020
                    and cmat[2, 2] > 0.990)
        elif name == "TWIST-LOCK":
            done = phase_t > 1.2
        elif name in ("ORIENT LUGS", "PRE-INSERT"):
            done = (np.linalg.norm(data.xpos[cart_id][:2] - np.array(cfg.sock)) < ENTRY_TOL
                    and abs(data.site_xpos[site_id][2] - tgt_arr[2]) < 0.008
                    and yaw_ok and cmat[2, 2] > 0.9986)
        elif name == "INSERT":
            done = (data.site_xpos[site_id][2] < 0.129 and cmat[2, 2] > INSERT_UPRIGHT
                    and data.xpos[cart_id][2] < INSERT_DEPTH_Z)
        elif name == "DROP-SEAT":
            done = data.xpos[cart_id][2] < seat_z + 0.008
        else:
            done = np.linalg.norm(tgt_arr - data.site_xpos[site_id]) < tol and yaw_ok

        if done:
            dwell_left -= dt
        elif name in CONTINUOUS_DWELL:
            dwell_left = dwell

        if dwell_left <= 0:
            # ---- on leaving a phase: capture images, grade, branch, clean ----
            if name == "PRESENT A":
                feats_a.append(capture())
            elif name == "PRESENT B":
                feats_b.append(capture())
                pred, pred_score = classify(feats_a + feats_b, cfg)
                route = pred
                part_ref = False        # reinstall re-grips by the body via the nest
                P = P + ROUTES[pred]
            elif name == "AGITATE":
                # cleaning removes the SAME deposit geoms the camera graded, so the
                # re-check observes the identical mechanism -- not a material swap.
                set_deposits(model, dep, 0, rng)
            elif name == "RECHECK B":
                # BOTH views, like the first inspection. Using only this one view
                # missed 2 of 5 deliberately-uncleaned parts in a falsification test:
                # deposits on the far face are invisible, so a dirty part reads clean.
                # The FLIP2 phase exists precisely to expose the other face.
                feats_r.append(capture())
                verified_clean = classify(feats_r, cfg)[0] == "clean"
            elif name == "STEP BACK":
                # re-perceive the part where it actually came to rest
                dyn["STAGED"] = data.xpos[spent_id][:2] + rng.normal(0, PERCEPTION_NOISE, 2)
            elif name == "RECHECK A":
                feats_r.append(capture())      # dedicated list: the pre-clean features
                                               # must not leak into the verification

            wp += 1; phase_t = 0.0
            flip_from = agit_from = None
            while wp < len(P) and P[wp][0].startswith("RECOVER"):
                wp += 1
            if wp < len(P):
                dwell_left = P[wp][3]
                if P[wp][0] == "INSERT":
                    hold_e = None
        elif phase_t > max_s:
            if name in ("INSERT", "DROP-SEAT") and retries < 2:
                retries += 1
                # On the REPLACE route the part may have been dropped, so recovery
                # re-grips first. On a REINSTALL the part is still in the jaws, so
                # returning to alignment is both sufficient and correct.
                tgt_phase = "RECOVER GRIP" if any(p[0] == "RECOVER GRIP" for p in P) else "ORIENT LUGS"
                idx = [i for i, p in enumerate(P) if p[0] == tgt_phase]
                if idx:
                    wp = idx[-1] if tgt_phase == "ORIENT LUGS" else idx[0]
                    dwell_left, phase_t = P[wp][3], 0.0
                    continue
            if name in ("UNTWIST", "EXTRACT") and untwist_retries < 2:
                untwist_retries += 1
                wp = next(i for i, p in enumerate(P) if p[0] == "DESCEND CAP")
                dwell_left, phase_t = P[wp][3], 0.0
                continue
            aborted = True
            break

        if frame_cb:
            frame_cb(model, data, name, STAGE_OF.get(name, ""), seed,
                     dict(truth=truth, pred=pred, route=route, verified=verified_clean))

    # ---- verification (v2/v3 criteria, unchanged) --------------------------
    installed_id = fresh_id if route == "heavy" else spent_id
    ipos = data.xpos[installed_id]
    imat = data.xmat[installed_id].reshape(3, 3)
    xy_off = float(np.linalg.norm(ipos[:2] - np.array(cfg.sock)))
    upright = float(imat[2, 2])
    rel_twist = (abs(np.rad2deg(wrap_pi(np.arctan2(imat[1, 0], imat[0, 0]) - insert_end_yaw)))
                 if insert_end_yaw is not None else 0.0)
    seated = (not aborted) and xy_off < 0.006 and ipos[2] < seat_z + 0.008 and upright > 0.95
    locked = bool(seated and rel_twist > 30.0)

    spos = data.xpos[spent_id]
    binned = bool(np.linalg.norm(spos[:2] - np.array(cfg.bin_xy)) < v3.BIN_XY_TOL
                  and spos[2] < v3.BIN_Z_MAX + dz)

    correct_route = bool(pred == truth)
    # routing compliance = did the arm MECHANICALLY execute the route it chose,
    # independent of whether that choice was correct. Vision error and mechanical
    # error are reported separately on purpose.
    if route == "heavy":
        route_done = bool(binned and locked)
    else:
        route_done = bool(locked and not binned)
    end_to_end = bool(correct_route and route_done)

    return {
        "seed": int(seed), "truth": truth, "pred": pred, "route": route,
        "score": float(pred_score) if pred_score is not None else float("nan"),
        "n_dep": int(n_dep), "correct_route": correct_route,
        "route_done": route_done, "end_to_end": end_to_end,
        "verified_clean": verified_clean,
        "locked": locked, "seated": bool(seated), "binned": binned,
        "xy_offset_mm": float(xy_off * 1000), "twist_deg": float(rel_twist),
        "aborted": bool(aborted), "part_lost": bool(part_lost), "retries": int(retries),
        "untwist_retries": int(untwist_retries),
        "cycle_s": float(data.time), "phases_done": int(wp), "n_phases": len(P),
        "dr_dz_mm": float(dz * 1000),
    }


# ============================================================ eval
def evaluate(n, cfg=CFG, seed0=0):
    rows = [run_trial(s, cfg=cfg) for s in range(seed0, seed0 + n)]
    M = confusion(rows_as_inspection(rows))
    acc = sum(M[c][c] for c in COND_NAMES) / n
    fc = false_clean_rate(rows_as_inspection(rows))
    comp = sum(r["route_done"] for r in rows) / n
    e2e = sum(r["end_to_end"] for r in rows) / n
    by_route = {}
    for rt in COND_NAMES:
        sel = [r for r in rows if r["route"] == rt]
        if sel:
            by_route[rt] = {"n": len(sel),
                            "cycle_s": float(np.mean([r["cycle_s"] for r in sel])),
                            "route_done": sum(r["route_done"] for r in sel) / len(sel)}
    ver = [r for r in rows if r["route"] == "light"]
    stats = {
        "trials": n, "seed_range": [seed0, seed0 + n - 1],
        "inspection_accuracy": acc, "false_clean_rate": fc,
        "routing_compliance": comp, "end_to_end": e2e,
        "clean_verified_rate": (sum(bool(r["verified_clean"]) for r in ver) / len(ver)) if ver else None,
        "confusion": M, "by_route": by_route, "results": rows,
    }
    json.dump(stats, open(cfg.stats_path, "w"), indent=1)
    print(f"EVAL v4 refurb: {n} trials (seeds {seed0}-{seed0+n-1})")
    print(f"  inspection accuracy : {acc*100:.1f}%")
    print(f"  FALSE-CLEAN RATE    : {fc*100:.1f}%   <-- the error that matters")
    print(f"  routing compliance  : {comp*100:.1f}%   (arm executed the route it chose)")
    print(f"  end-to-end success  : {e2e*100:.1f}%   (right action AND unit finished correctly)")
    if ver:
        print(f"  cleaning verified   : {stats['clean_verified_rate']*100:.1f}% of {len(ver)} cleaned parts "
              f"re-graded clean on a fresh render")
    for rt, d in by_route.items():
        print(f"  route {rt:<6}: n={d['n']:3d}  cycle {d['cycle_s']:5.1f}s  completed {d['route_done']*100:5.1f}%")
    report_inspection(rows_as_inspection(rows), n)
    return stats


def rows_as_inspection(rows):
    return [{"truth": r["truth"], "pred": r["pred"] or "heavy"} for r in rows]


# ============================================================ rendering
STAGE_SEQ = ["EXTRACT", "INSPECT", "CLEAN", "REPLACE", "INSTALL"]


def make_frame_cb(frames, model, cfg=CFG):
    from PIL import Image, ImageDraw
    main_r = mujoco.Renderer(model, 720, 1280)
    wrist_r = mujoco.Renderer(model, 216, 288)
    font, font_b, font_s = _font("mono", 20), _font("mono_bold", 22), _font("mono", 15)
    state = {"n": 0}
    spf = max(1, int(round(1.0 / FPS / model.opt.timestep)))
    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "link_tcp")
    spent_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "spent_cartridge")
    fresh_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "cartridge")

    def cb(m, d, phase, stage, seed, info):
        state["n"] += 1
        if state["n"] % spf:
            return
        main_r.update_scene(d, camera="main")
        img = Image.fromarray(main_r.render())
        wrist_r.update_scene(d, camera="wrist")
        wr = Image.fromarray(wrist_r.render())
        draw = ImageDraw.Draw(img, "RGBA")
        px, py = 1280 - 288 - 16, 720 - 216 - 16
        draw.rectangle([px - 3, py - 3, px + 288 + 3, py + 216 + 3], fill=(255, 255, 255, 220))
        img.paste(wr, (px, py))
        draw.text((px + 6, py + 4), "WRIST CAM", font=font_s, fill=(255, 255, 255, 230))

        tcp = d.site_xpos[site_id]
        sp, fr = d.xpos[spent_id], d.xpos[fresh_id]
        truth, pred = info.get("truth"), info.get("pred")
        route, ver = info.get("route"), info.get("verified")
        grip = "CLOSED" if d.ctrl[mujoco.mj_name2id(
            m, mujoco.mjtObj.mjOBJ_ACTUATOR, "gripper")] > 100 else "OPEN"
        verdict = "inspecting..." if pred is None else f"{pred.upper()}  ->  {route.upper()} route"
        lines = [
            f"PHASE     {phase}",
            f"t         {d.time:6.2f} s     GRIPPER {grip}",
            f"TCP       x{tcp[0]*1000:7.1f} y{tcp[1]*1000:7.1f} z{tcp[2]*1000:6.1f} mm",
            f"RETURNED  z{sp[2]*1000:6.1f} mm   (actual condition: {truth})",
            f"CAMERA    {verdict}",
        ]
        if ver is not None:
            lines.append(f"RE-CHECK  after cleaning: {'READS CLEAN' if ver else 'STILL DIRTY'}")
        draw.rectangle([12, 12, 790, 12 + 24 + len(lines) * 26], fill=(10, 14, 20, 180))
        draw.text((24, 20), f"REFURBISHMENT CELL - INSPECT / CLEAN / REPLACE (seed {seed})",
                  font=font_b, fill=(120, 200, 255, 255))
        for i, ln in enumerate(lines):
            draw.text((24, 50 + i * 26), ln, font=font, fill=(235, 240, 245, 255))

        x0, y0 = 24, 12 + 24 + len(lines) * 26 + 14
        for st in STAGE_SEQ:
            # only show steps this route actually performs -- a greyed chip for a
            # stage that never runs implies work the cell did not do
            if st == "CLEAN" and route in ("heavy", "clean"):
                continue
            if st == "REPLACE" and route in ("clean", "light"):
                continue
            w = int(draw.textlength(st, font=font)) + 26
            on = (st == stage)
            draw.rectangle([x0, y0, x0 + w, y0 + 32],
                           fill=(41, 121, 255, 235) if on else (255, 255, 255, 38))
            draw.text((x0 + 13, y0 + 6), st, font=font,
                      fill=(255, 255, 255, 255) if on else (170, 180, 195, 255))
            x0 += w + 8
        note = cfg.clean_caveat if stage == "CLEAN" else cfg.deposit_caveat
        draw.text((24, 700), note, font=font_s, fill=(160, 172, 188, 235))
        frames.append(np.asarray(img).copy())
    return cb


def render_trial(idx, seed, speed=1):
    import imageio
    model = mujoco.MjModel.from_xml_path(CFG.xml)
    frames = []
    res = run_trial(seed, frame_cb=make_frame_cb(frames, model))
    frames = frames[::max(1, speed)]
    imageio.mimsave(f"refurb_{idx}.mp4", frames, fps=FPS, codec="libx264", quality=8,
                    pixelformat="yuv420p")
    print(f"refurb_{idx}.mp4: {len(frames)} frames ({len(frames)/FPS:.1f}s) | "
          f"route={res['route']} truth={res['truth']} end_to_end={res['end_to_end']}")
    return res


def make_cards():
    import imageio
    from PIL import Image, ImageDraw
    st = json.load(open(CFG.stats_path))
    fb = lambda n: _font("sans_bold", n)
    fr = lambda n: _font("sans", n)
    fm = lambda n: _font("mono", n)

    def card(lines, fname, secs, table=None):
        img = Image.new("RGB", (1280, 720), (13, 17, 23))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, 1280, 6], fill=(41, 121, 255))
        y = 96
        for txt, fnt, col in lines:
            d.text(((1280 - d.textlength(txt, font=fnt)) / 2, y), txt, font=fnt, fill=col)
            y += fnt.size + 20
        if table:
            for row in table:
                d.text(((1280 - d.textlength(row, font=fm(24))) / 2, y), row,
                       font=fm(24), fill=(190, 200, 215))
                y += 30
        imageio.mimsave(fname, [np.asarray(img)] * int(FPS * secs), fps=FPS,
                        codec="libx264", quality=8, pixelformat="yuv420p")

    card([
        ("REFURBISHMENT CELL", fb(58), (235, 240, 245)),
        ("Inspect, clean, or replace - simulation POC", fr(30), (150, 160, 175)),
        ("", fr(8), (0, 0, 0)),
        ("A used unit arrives with a filter cartridge locked inside. The robot", fr(25), (150, 160, 175)),
        ("removes it, LOOKS at it with a camera, and decides what it needs:", fr(25), (150, 160, 175)),
        ("", fr(8), (0, 0, 0)),
        ("clean -> put straight back    scaled -> wash, re-check, put back", fr(25), (120, 200, 255)),
        ("damaged -> bin it and install a new one", fr(25), (120, 200, 255)),
        ("", fr(8), (0, 0, 0)),
        ("DrinkPrime automation study - Phase 0 (pre-hardware)", fr(21), (110, 120, 135)),
    ], "card_v4_title.mp4", 5.0)

    M, n = st["confusion"], st["trials"]
    fc = st["false_clean_rate"] * 100
    tbl = ["            graded:  clean   light   heavy"]
    for t in COND_NAMES:
        tbl.append(f"  actually {t:<6}    " + "".join(f"{M[t][p]:>7}" for p in COND_NAMES))
    card([
        ("RESULTS", fb(54), (235, 240, 245)),
        (f"{n} randomized trials, held out from tuning", fr(25), (150, 160, 175)),
        ("", fr(8), (0, 0, 0)),
        (f"FALSE-CLEAN RATE: {fc:.1f}%", fb(52), (80, 220, 130) if fc < 2 else (255, 190, 80)),
        ("the error that matters - a part that needs work, passed as clean", fr(23), (150, 160, 175)),
        ("", fr(8), (0, 0, 0)),
        (f"inspection accuracy {st['inspection_accuracy']*100:.0f}%   |   "
         f"every route completed {st['routing_compliance']*100:.0f}%   |   "
         f"end-to-end {st['end_to_end']*100:.0f}%", fr(24), (150, 160, 175)),
        ("", fr(8), (0, 0, 0)),
    ], "card_v4_end.mp4", 7.0, table=tbl + [
        "", "remaining errors are all on the SAFE side:",
        "light parts over-graded as heavy (a wasted cartridge),",
        "never a dirty part passed as clean.",
        "", "cleaning = dip + dwell; chemistry not simulated."])
    print("cards written")


def concat(parts, out, tag=None, stride=1.0):
    """Stitch clips. stride>1 decimates the TRIAL frames and stamps a speed tag, so a
    compressed cut can never be mistaken for real-time."""
    import imageio
    from PIL import Image, ImageDraw
    writer = imageio.get_writer(out, fps=FPS, codec="libx264", quality=8,
                               pixelformat="yuv420p")
    f_tag = _font("sans_bold", 26)
    for path, is_trial in parts:
        rd = imageio.get_reader(path)
        frames = [f for f in rd]
        rd.close()
        if is_trial and stride > 1.0:
            idx = [int(round(i * stride)) for i in range(int(len(frames) / stride))]
            frames = [frames[i] for i in idx if i < len(frames)]
        for fr_ in frames:
            if is_trial and tag:
                im = Image.fromarray(fr_)
                d = ImageDraw.Draw(im, "RGBA")
                w = int(d.textlength(tag, font=f_tag)) + 28
                d.rectangle([1280 - w - 20, 20, 1280 - 20, 62], fill=(255, 190, 80, 230))
                d.text((1280 - w - 6, 27), tag, font=f_tag, fill=(20, 24, 30, 255))
                fr_ = np.asarray(im)
            writer.append_data(fr_)
    writer.close()
    print(f"{out} written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect-eval", type=int)
    ap.add_argument("--eval", type=int)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--stats", default=None, help="write stats to this path")
    ap.add_argument("--dr", type=float, default=None,
                    help="enable domain randomization at this scale (1.0 = mass +-20%%, friction +-30%%, cell height +-5mm)")
    ap.add_argument("--render", nargs="+")
    ap.add_argument("--cards", action="store_true")
    ap.add_argument("--concat", action="store_true")
    a = ap.parse_args()
    if a.render:
        render_trial(int(a.render[0]), int(a.render[1]),
                     int(a.render[2]) if len(a.render) > 2 else 1)
        raise SystemExit
    if a.cards:
        make_cards(); raise SystemExit
    if a.concat:
        trials = [(f"refurb_{i}.mp4", True) for i in (1, 2, 3)]
        concat([("card_v4_title.mp4", False)] + trials + [("card_v4_end.mp4", False)],
               "refurb_cell_v4_full.mp4")
        concat([("card_v4_title.mp4", False)] + trials + [("card_v4_end.mp4", False)],
               "refurb_cell_v4.mp4", tag="1.8x SPEED", stride=1.8)
        raise SystemExit
    if a.inspect_eval:
        inspect_eval(a.inspect_eval, seed0=a.seed0)
    elif a.eval:
        evaluate(a.eval, seed0=a.seed0)
