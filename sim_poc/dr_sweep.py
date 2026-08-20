"""Domain randomization over the FULL ROUTED CYCLE -- backlog item 4, run unattended.

    ../venv/bin/python dr_sweep.py            # POINT mode, paired OFF/ON on 2300-2315
    ../venv/bin/python dr_sweep.py --stroke   # STROKE mode (the shipping default),
                                              # paired OFF/ON on 2316-2331
    ../venv/bin/python dr_sweep.py --n 8 --seed0 S

Each mode's bare invocation reproduces its own published number and writes its own
tagged file (stats_v5_dr.json / stats_v5_dr_stroke.json) -- a stroke run must never
land in the committed point-mode artifact, the same rule v5_clean's filename tags
enforce. Both defaults sit inside the ledger's reserved DR block (2300-2331).

WHAT IS PERTURBED, per unit, drawn from the unit's own seeded rng:
    cabinet mass        x U(0.8, 1.2)        (+-20%; the 8.0 kg is itself a placeholder)
    device geom friction x U(0.7, 1.3)       (+-30%, slide component, cabinet + panels)
    device height       + U(0, 5) mm         (spawned proud, DROPS onto the platter --
                                              never interpenetrated, which would be an
                                              explosion test, not a calibration test)

WHAT THIS MEASURES AND WHAT IT CANNOT. The planner reads the LIVE model (that is a
design decision this repo defends), so a static height offset is partly absorbed by the
planner's own measurement -- the perturbation still changes contact dynamics, drop
settling, and the mass/friction of everything the pad pushes on, but this is NOT a
camera-calibration study. v4's DR (sim_poc4 --dr) remains the precedent for the
fixed-belief kind; the v4 result stands: usable envelope ~ +-2.5 mm of cell-position
error.

PAIRED, DELIBERATELY: every seed runs once with DR off and once with DR on, so any
difference is attributable to the perturbation and not to the unit mix. Writes a
mode-tagged file; no published baseline is touched. The OFF arm doubles as the
control: the cleaning trajectory is open-loop and seed-independent, so its force and
tracking figures must reproduce the published baseline's before the ON arm means
anything.
"""
import argparse
import dataclasses
import json

import numpy as np
import mujoco

import v5_clean as CL
import v5_route as RT


def perturb(cell, seed):
    """Apply this unit's draw to the LIVE model. Returns what was drawn, for the row."""
    rng = np.random.default_rng(seed + 990_000)     # distinct stream from the unit's own
    m, d = cell.m, cell.d
    cab_body = m.body("cabinet").id
    mass_k = float(rng.uniform(0.8, 1.2))
    fric_k = float(rng.uniform(0.7, 1.3))
    dz = float(rng.uniform(0.0, 0.005))
    m.body_mass[cab_body] *= mass_k
    # friction on every geom the cabinet body carries (cab_body, panels, cover)
    for g in range(m.ngeom):
        if m.geom_bodyid[g] == cab_body:
            m.geom_friction[g, 0] *= fric_k
    # spawn proud and let it drop -- the settle is part of the perturbation
    m.body_pos[cab_body][2] += dz
    mujoco.mj_forward(m, d)
    # settle: 0.4 s of free physics before the cycle starts, so the drop is not
    # happening under the first wipe
    for _ in range(int(0.4 / cell.dt)):
        d.ctrl[cell.act] = cell.q_des
        d.qfrc_applied[cell.dof] = d.qfrc_bias[cell.dof]
        mujoco.mj_step(m, d)
    return {"mass_k": mass_k, "fric_k": fric_k, "dz_mm": dz * 1000}


def run(n, seed0, stroke=False):
    # STROKE is the shipping clean mode; the committed point-mode result answered the
    # question for the mode nobody quotes. Same replace() idiom as v5_clean's own CLI so
    # the module-level CFG (which the point baseline reproduces from) is never mutated.
    cfg = dataclasses.replace(CL.CFG, stroke=True) if stroke else CL.CFG
    rows = []
    for k in range(n):
        seed = seed0 + k
        for dr in (False, True):
            # FRESH CELL PER RUN: perturb() edits the model in place, and model edits
            # must never leak across runs -- that is how a sweep contaminates itself.
            cell = RT.RouteCell(cfg)
            cell.reset(seed)
            draw = perturb(cell, seed) if dr else {"mass_k": 1.0, "fric_k": 1.0,
                                                   "dz_mm": 0.0}
            # run the CLEAN station (the contact-heavy part DR actually stresses);
            # keep_route-level scope out: triage cameras and membrane run on their own
            # stations and their DR story is v4's calibration lesson, not this sweep's
            r = CL.Cell.run(cell, seed)
            rows.append({"seed": seed, "dr": dr, **draw,
                         "coverage": r["coverage"], "missed": r["missed"],
                         "soil0": r["soil0"], "f_max": r["f_max"],
                         "in_band": r["in_band"],
                         "device_shift_mm": r["device_shift_mm"],
                         "tcp_speed_max": r["tcp_speed_max"],
                         # stroke tracking: the mechanism behind every stroke coverage
                         # cliff so far, and the thing a friction change would move.
                         # Zero in point mode (same convention as the run() dict).
                         "stroke_inplane_err_mm": r.get("stroke_inplane_err_mm", 0.0),
                         "stroke_track_med_mm": r.get("stroke_track_med_mm", 0.0)})
            print(f"  seed {seed} dr={int(dr)}: cov {r['coverage']*100:5.1f}%  "
                  f"missed {r['missed']}  fmax {r['f_max']:5.2f} N  "
                  f"track {r.get('stroke_inplane_err_mm', 0.0):5.1f} mm  "
                  f"(mass x{draw['mass_k']:.2f} fric x{draw['fric_k']:.2f} "
                  f"dz {draw['dz_mm']:.1f} mm)", flush=True)
    off = [r for r in rows if not r["dr"]]
    on = [r for r in rows if r["dr"]]
    st = {"n": n, "seed0": seed0, "stroke": stroke,
          "spec": "mass U(0.8,1.2) fric U(0.7,1.3) dz U(0,5)mm, paired off/on",
          "off": {"cov_worst": min(r["coverage"] for r in off),
                  "missed": sum(r["missed"] for r in off),
                  "f_max": max(r["f_max"] for r in off),
                  "track_worst_mm": max(r["stroke_inplane_err_mm"] for r in off)},
          "on": {"cov_worst": min(r["coverage"] for r in on),
                 "missed": sum(r["missed"] for r in on),
                 "f_max": max(r["f_max"] for r in on),
                 "track_worst_mm": max(r["stroke_inplane_err_mm"] for r in on)},
          "rows": rows}
    stats = f"stats_v5_dr{'_stroke' if stroke else ''}.json"
    with open(stats, "w") as f:
        json.dump(st, f, indent=2)
    print(f"\nwrote {stats}")
    for tag in ("off", "on"):
        s = st[tag]
        print(f"  {tag.upper():3s}: worst cov {s['cov_worst']*100:.1f}%  missed "
              f"{s['missed']}  fmax {s['f_max']:.2f} N  "
              f"track worst {s['track_worst_mm']:.1f} mm")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=16)
    ap.add_argument("--seed0", type=int, default=None,
                    help="default reproduces the mode's published number: "
                         "2300 point / 2316 stroke (both inside the reserved DR block)")
    ap.add_argument("--stroke", action="store_true",
                    help="run the shipping continuous-stroke mode instead of point")
    a = ap.parse_args()
    seed0 = a.seed0 if a.seed0 is not None else (2316 if a.stroke else 2300)
    run(a.n, seed0, stroke=a.stroke)
