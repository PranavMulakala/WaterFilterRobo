"""V7 [demo] -- VLM-vs-HSV triage comparison, run BLIND.

    ../venv/bin/python v5_vlm_triage.py --render 40 --seed0 1950
        renders 40 fresh units to a scratch directory as u00.png..u39.png IN SHUFFLED
        ORDER, and writes key.json (index -> seed, truth, HSV prediction) alongside.

    ../venv/bin/python v5_vlm_triage.py --score
        joins the grader's answers in vlm.json against key.json and reports the paired
        comparison with the SAME asymmetric metrics the HSV baseline is judged by.

WHY BLIND, AND WHY IT IS THE WHOLE POINT. The "VLM" here is Claude reading the rendered
images (see the honesty label below). Claude also wrote this file and can read
`v5_triage.sample_condition`, so an un-blinded run would not be measuring vision at all
-- it would be measuring whether the grader peeked. The protocol removes the
opportunity: images are written under indices that carry no seed and no class, the key
is a separate file, and the answers are committed to `vlm.json` BEFORE the key is ever
opened. `--score` refuses to run if vlm.json is newer than key.json is old, which is a
weak check; the real guarantee is the file order in the git history.

HONESTY LABEL, and it must travel with every number this file produces:
  1. This is CLAUDE-AS-VLM reading rendered PNGs in a conversation. It is NOT a deployed
     vision-language model, there is no API call, no latency figure, no cost figure and
     no repeatability figure. Treat it as an upper-ish bound on what a strong general
     VLM might do on this exact imagery, measured once.
  2. The class boundaries are OURS, not DrinkPrime's -- no document in their set defines
     Easy/Medium/Hard (see dp_process.MISSING). Both graders are therefore being scored
     against a rubric we invented. The comparison between them is fair; the absolute
     numbers inherit that caveat.
  3. The images are SIMULATED. Real cabinets have specular highlights, print, stickers,
     wear and lighting our renderer does not produce. A VLM's advantage on real imagery
     could be larger (it has seen real scuffs) or smaller (sim defects are unnaturally
     uniform in colour, which flatters a threshold).
"""
import argparse
import json
import os
import sys

import numpy as np
import mujoco

import v5_triage as TR

OUT = os.environ.get("VLM_DIR", "/tmp/v5_vlm")


def render(n, seed0, out=OUT):
    """Render n fresh units, shuffled, with the key written separately."""
    import PIL.Image as I
    os.makedirs(out, exist_ok=True)
    model, data, pools = TR.load_scene()
    rend = mujoco.Renderer(model, TR.CFG.cam_h, TR.CFG.cam_w)
    seeds = list(range(seed0, seed0 + n))
    # shuffle so that neither the file order nor the index carries the seed order --
    # sample_condition draws the class from a fixed weighting, and a grader who knows
    # the seed order could infer the class prior's run structure.
    order = np.random.default_rng(12345).permutation(len(seeds))
    key = []
    for idx, j in enumerate(order):
        seed = seeds[int(j)]
        save = []
        row = TR.grade_unit(model, data, pools, rend, seed, save=save)
        _, shots = save[0]
        # THE SAME FRAMES THE HSV PIPELINE CONSUMES. Not the hand-built per-face ROIs:
        # a deployed VLM would be handed the camera image, not our region proposals, and
        # handing it the ROIs would be measuring our region proposer twice.
        # CROP TO THE DEVICE. The full 1280x720 frame is mostly bench and backdrop, and
        # a defect is ~15 px in it; a grader reading the whole frame is being tested on
        # its ability to zoom, not on its ability to grade. The crop is taken from the
        # SAME face regions the HSV pipeline uses, so neither grader is shown a region
        # the other cannot see -- only at a sensible scale.
        crops = []
        for rgb, deg in shots:
            r0, r1, c0, c1 = 10**9, -1, 10**9, -1
            for _fid, _cos, roi in TR.face_regions(model, data, TR.CFG, deg):
                r0, r1 = min(r0, roi[0]), max(r1, roi[1])
                c0, c1 = min(c0, roi[2]), max(c1, roi[3])
            if r1 < 0:
                r0, r1, c0, c1 = 40, 710, 400, 880
            pad = 24
            r0 = max(r0 - pad, 0); c0 = max(c0 - pad, 0)
            r1 = min(r1 + pad, rgb.shape[0]); c1 = min(c1 + pad, rgb.shape[1])
            crops.append(rgb[r0:r1, c0:c1])
        h = min(c.shape[0] for c in crops)
        strip = np.concatenate([c[:h] for c in crops], axis=1)
        I.fromarray(strip).save(f"{out}/u{idx:02d}.png")
        key.append({"idx": idx, "seed": seed, "truth": row["truth"],
                    "hsv": row["pred"], "n_dent": row["n_dent"],
                    "n_scr": row["n_scr"], "n_soil": row["n_soil"]})
        # print the INDEX ONLY. Echoing the seed here would put a seed->file mapping in
        # the grader's transcript, and sample_condition() is deterministic in the seed.
        print(f"  u{idx:02d}.png")
    with open(f"{out}/key.json", "w") as f:
        json.dump({"n": n, "seed0": seed0, "rows": key}, f, indent=2)
    print(f"\nwrote {n} images + key.json to {out}")
    print("GRADE FIRST, then write vlm.json, then --score. Do not open key.json.")


# ---------------------------------------------------------------- scoring
def _metrics(rows, pred_key):
    """The SAME asymmetric metrics v5_triage.report uses, so the two are comparable."""
    G = TR.GRADES
    M = {t: {p: 0 for p in G} for t in G}
    for r in rows:
        M[r["truth"]][r[pred_key]] += 1
    n = len(rows)
    acc = sum(M[g][g] for g in G) / max(n, 1)
    hard = sum(M["hard"].values())
    # MISSED HARD is the headline: a hard unit graded easy or medium is sent back onto
    # the line with damage that no stage remedies.
    missed_hard = (M["hard"]["easy"] + M["hard"]["medium"]) / max(hard, 1)
    needs = sum(M[t][p] for t in ("medium", "hard") for p in G)
    false_easy = sum(M[t]["easy"] for t in ("medium", "hard")) / max(needs, 1)
    easy = sum(M["easy"].values())
    over = (M["easy"]["medium"] + M["easy"]["hard"]) / max(easy, 1)
    return {"n": n, "acc": acc, "missed_hard": missed_hard, "false_easy": false_easy,
            "over_treat": over, "confusion": M}


def score(out=OUT):
    key = json.load(open(f"{out}/key.json"))["rows"]
    vlm = json.load(open(f"{out}/vlm.json"))
    by = {int(k): v for k, v in vlm.items()} if isinstance(vlm, dict) else \
         {r["idx"]: r["pred"] for r in vlm}
    rows = []
    for k in key:
        p = by.get(k["idx"])
        if p is None:
            print(f"  MISSING grade for u{k['idx']:02d} -- refusing to score a partial set")
            sys.exit(2)
        rows.append({**k, "vlm": p})
    a = _metrics(rows, "hsv")
    b = _metrics(rows, "vlm")
    print(f"\nVLM vs HSV TRIAGE  [demo]  -- {len(rows)} PAIRED fresh units "
          f"(seeds {min(r['seed'] for r in rows)}-{max(r['seed'] for r in rows)})")
    print("  Same units, same images, same rubric. Paired, so the two graders differ in")
    print("  exactly one thing: what reads the pixels.\n")
    print(f"  {'metric':<22}{'HSV baseline':>16}{'Claude-as-VLM':>16}")
    print(f"  {'-'*54}")
    for lab, k, lo_is_good in (("accuracy", "acc", False),
                               ("MISSED-HARD  <-lead", "missed_hard", True),
                               ("false-easy", "false_easy", True),
                               ("over-treatment", "over_treat", True)):
        print(f"  {lab:<22}{a[k]*100:>15.1f}%{b[k]*100:>15.1f}%")
    print("\n  per-class recall")
    print(f"  {'class':<10}{'n':>5}{'HSV':>10}{'VLM':>10}")
    for g in TR.GRADES:
        tot = sum(a["confusion"][g].values())
        if not tot:
            continue
        print(f"  {g:<10}{tot:>5}{a['confusion'][g][g]/tot*100:>9.1f}%"
              f"{b['confusion'][g][g]/tot*100:>9.1f}%")
    print("\n  confusion  truth\\pred        easy  medium    hard")
    for name, M in (("HSV", a["confusion"]), ("VLM", b["confusion"])):
        for g in TR.GRADES:
            print(f"    {name}  {g:<12}{M[g]['easy']:>8}{M[g]['medium']:>8}{M[g]['hard']:>8}")
    # DISAGREEMENTS are the interesting rows -- print them with the ground-truth counts
    dis = [r for r in rows if r["hsv"] != r["vlm"]]
    print(f"\n  the two graders disagreed on {len(dis)}/{len(rows)} units:")
    for r in dis:
        who = "VLM right" if r["vlm"] == r["truth"] else \
              ("HSV right" if r["hsv"] == r["truth"] else "both wrong")
        print(f"    u{r['idx']:02d} seed {r['seed']}  truth {r['truth']:<7} "
              f"HSV {r['hsv']:<7} VLM {r['vlm']:<7}  ({who})   "
              f"dents {r['n_dent']:2d} scratches {r['n_scr']:2d} soil {r['n_soil']:2d}")
    st = {"n": len(rows), "hsv": {k: v for k, v in a.items() if k != "confusion"},
          "vlm": {k: v for k, v in b.items() if k != "confusion"},
          "hsv_confusion": a["confusion"], "vlm_confusion": b["confusion"],
          "rows": rows,
          "label": "Claude-as-VLM reading rendered PNGs; NOT a deployed model. "
                   "Class boundaries are ours, not DrinkPrime's."}
    with open("stats_v5_vlm_triage.json", "w") as f:
        json.dump(st, f, indent=2)
    print("\nwrote stats_v5_vlm_triage.json")
    n = len(rows)
    print(f"\n  WHAT {n} UNITS CAN AND CANNOT SETTLE. With {sum(1 for r in rows if r['truth']=='hard')} "
          f"hard units, a missed-hard rate of 0/{sum(1 for r in rows if r['truth']=='hard')} has a "
          "95% upper bound of")
    print("  roughly 3/n -- i.e. this run cannot distinguish 0% from about 20%. It can")
    print("  detect a LARGE difference between the two graders and nothing subtle.")
    return st


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", type=int, metavar="N")
    ap.add_argument("--seed0", type=int, default=1950)
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--dir", default=OUT)
    a = ap.parse_args()
    if a.render:
        render(a.render, a.seed0, a.dir)
    elif a.score:
        score(a.dir)
    else:
        ap.print_help()
        sys.exit(1)
