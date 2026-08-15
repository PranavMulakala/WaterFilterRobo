"""V8 [intake] -- REAL-photo triage: blind grading packs + an exact-CI scorer.

    ../venv/bin/python v5_real_triage.py --prep PHOTOS/ --labels grades.csv --out /tmp/real_pack
    ../venv/bin/python v5_real_triage.py --score /tmp/real_pack/answers.json --key /tmp/real_pack_key.json
    ../venv/bin/python v5_real_triage.py --selftest

WHAT THIS IS FOR. The founder is sending REAL photos of incoming water-purifier units
plus the operator's grade for each, and wants image classification built on them. This
file is the intake harness: it turns a photo dump + labels CSV into a BLIND grading pack,
and scores committed answers with the asymmetric metrics this project leads with. It is
the real-image counterpart of `v5_vlm_triage.py` and reuses its protocol on purpose --
shuffled case ids that carry no unit id and no grade, the key in a separate file OUTSIDE
the pack, answers committed before the key is opened.

GRADES ARE THE FOUNDER'S OUTCOME DEFINITIONS [verbal, 2026-08-12], AND ONLY THOSE.
easy = "device not changed", medium = "some parts changed", hard = "entire device
changed" (dp_process.FOUNDER_VERBAL; secondhand, relayed by Teja, not in writing). Those
define what each grade MEANS -- what happened to the unit at the plant -- not what an
operator SEES on an incoming one. THE VISUAL CRITERIA REMAIN UNDEFINED. A grader working
from this pack is therefore doing the honest zero-shot task: predict the outcome from
pixels with no visual rubric, because no one has given us one and inventing one would
mean the score measured our hints instead of the grader. This label must travel with
every number this file produces.

WHERE A FINE-TUNED CLASSIFIER SLOTS IN. At roughly 100+ labelled units there is enough
data to train a small classifier instead of grading zero-shot. It slots in as a drop-in
replacement for the GRADER ONLY: it reads the same blind pack (--prep is unchanged) and
writes the same answers.json, which the same --score judges with the same metrics and the
same exact CIs. Nothing else moves. That is deliberate -- if the protocol or the scorer
changed at the same time as the grader, the zero-shot number and the fine-tuned number
would stop being comparable, and the comparison IS the evidence that fine-tuning paid.

WHY BLIND, AND WHY IT IS PROCEDURAL, NOT CRYPTOGRAPHIC. The likely grader (Claude, or a
script Claude wrote) has filesystem access to the labels CSV and the key. No amount of
shuffling prevents a grader from simply reading the answers off disk -- the protocol
removes the *accidental* leaks (unit ids in filenames, grades in the transcript, truth
inferable from file order) and makes the deliberate one auditable: answers.json is
committed BEFORE the key or the CSV is opened, and the file order in the git history is
the real guarantee. Same stance as v5_vlm_triage, where it is spelled out at length.

WHY THE CI IS THE HEADLINE, NOT THE RATE. The first real batch will be n = 10..40. At
that size a 0/12 missed-hard is NOT evidence of a 0% missed-hard rate -- its exact 95%
upper bound is 26.5%, i.e. the data is consistent with missing one hard unit in four.
Every rate this file prints carries an exact Clopper-Pearson interval (pure Python, by
bisection on the binomial CDF -- scipy is not in the venv, checked 2026-08-15), and the
scorer says out loud when n is too small to distinguish 0% from 20%. Quoting the bare
rate from a small batch is how a founder gets told a comforting number that the next
twenty units contradict.

NO MUJOCO, DELIBERATELY. This file imports no simulation, no arm, no scene -- real
photos have no ground-truth pools and no seeds, and nothing here should drag in a physics
engine (or its load-time cost, or its version pinning) to score a JSON file against a
CSV. The only third-party import is PIL, used solely by --selftest to draw its fixture
images; --prep copies photo BYTES VERBATIM and never decodes them (pixel fidelity matters
for the future fine-tune, and a lossy re-encode would silently change the training data).
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
import random
import shutil
import sys
from datetime import datetime

# Mirrors v5_triage.GRADES. NOT imported from there: v5_triage pulls in mujoco, and this
# file's contract is zero MuJoCo. The order matters -- reports print in this order.
GRADES = ("easy", "medium", "hard")

# ---------------------------------------------------------------- founder definitions
# Single source of truth is dp_process.FOUNDER_VERBAL (data-only module, no MuJoCo, safe
# to import). The inline copy below exists so --score still runs if this file is used
# away from the repo -- and when dp_process IS importable, the two are ASSERTED equal, so
# they cannot drift apart silently. That pattern is the PAD_STANDOFF lesson: "unified"
# constants that are actually two copies rot in exactly the way that flatters a claim.
_FOUNDER_DEFS = {"easy": "device not changed",
                 "medium": "some parts changed",
                 "hard": "entire device changed"}
_FOUNDER_DATE = "2026-08-12"


def founder_definitions():
    try:
        import dp_process
        defs = dict(dp_process.FOUNDER_VERBAL["grade_definitions_by_outcome"])
        date = dp_process.FOUNDER_VERBAL["date"]
        assert defs == _FOUNDER_DEFS and date == _FOUNDER_DATE, (
            "dp_process.FOUNDER_VERBAL changed but v5_real_triage's inline copy did not "
            f"-- update BOTH. dp_process says {defs!r} @ {date!r}")
        return defs
    except ImportError:
        return dict(_FOUNDER_DEFS)


# ---------------------------------------------------------------- grade normalisation
# Tolerant on CASE and on the obvious spellings; deliberately INTOLERANT of numbers.
# An operator sheet that says 1/2/3 is ambiguous in direction (is 1 the easy one or the
# urgent one?), and guessing the direction is a truth-affecting guess -- the whole scorer
# would silently measure our coin flip. Unknown grades abort loudly with the offenders
# listed, and a human decides.
_GRADE_ALIASES = {
    "easy": "easy", "ez": "easy", "e": "easy", "device not changed": "easy",
    "medium": "medium", "med": "medium", "m": "medium", "moderate": "medium",
    "some parts changed": "medium",
    "hard": "hard", "hrd": "hard", "h": "hard", "entire device changed": "hard",
}


def norm_grade(raw):
    """'  Easy ' -> 'easy'; unknown -> None (caller collects offenders and aborts)."""
    s = " ".join(str(raw).strip().strip("'\"").casefold().split())
    return _GRADE_ALIASES.get(s)


def _die(msg):
    print(f"ERROR: {msg}")
    sys.exit(2)


# ---------------------------------------------------------------- labels CSV
# Header names the founder might plausibly use, in priority order (so a sheet with both
# 'unit_id' and 'id' takes the specific one). Extra columns are tolerated and ignored --
# the operator's sheet will have remarks/dates/whatever, and requiring a clean two-column
# file would just mean someone hand-edits it, which is where transcription errors enter.
_UNIT_HEADERS = ("unit_id", "unitid", "unit id", "unit no", "unit_no", "unit number",
                 "unit_number", "device_id", "device id", "unit", "serial", "serial_no",
                 "s no", "sno", "id")
_GRADE_HEADERS = ("grade", "condition", "triage", "class", "label", "severity")


def load_labels(path):
    """CSV -> {unit_id: grade}. Loud on unknown grades, conflicting duplicates, or an
    unrecognisable header. utf-8-sig because Excel exports open with a BOM."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        if rdr.fieldnames is None:
            _die(f"{path} is empty")
        norm_hdr = {" ".join(h.strip().casefold().replace("_", " ").split()): h
                    for h in rdr.fieldnames if h}
        ucol = next((norm_hdr[k.replace("_", " ")] for k in _UNIT_HEADERS
                     if k.replace("_", " ") in norm_hdr), None)
        gcol = next((norm_hdr[k] for k in _GRADE_HEADERS if k in norm_hdr), None)
        if ucol is None or gcol is None:
            _die(f"could not find a unit-id and a grade column in {path}. "
                 f"Headers found: {rdr.fieldnames}. Accepted unit headers: "
                 f"{_UNIT_HEADERS}; grade headers: {_GRADE_HEADERS}")
        labels, bad, dup_warned = {}, [], set()
        for i, row in enumerate(rdr, start=2):          # start=2: header is line 1
            uid = (row.get(ucol) or "").strip()
            raw = (row.get(gcol) or "").strip()
            if not uid and not raw:
                continue                                 # blank line, common in exports
            if not uid:
                bad.append(f"line {i}: empty unit id (grade {raw!r})")
                continue
            g = norm_grade(raw)
            if g is None:
                bad.append(f"line {i}: unit {uid!r} has unknown grade {raw!r}")
                continue
            if uid in labels:
                if labels[uid] != g:
                    bad.append(f"line {i}: unit {uid!r} relabelled {labels[uid]!r} "
                               f"-> {g!r} -- conflicting duplicate")
                elif uid not in dup_warned:
                    print(f"  note: unit {uid!r} appears twice with the same grade; "
                          "deduplicated")
                    dup_warned.add(uid)
                continue
            labels[uid] = g
    if bad:
        _die("labels CSV rejected -- fix these rows and re-run "
             "(grades must map to easy/medium/hard; numeric grades are refused on "
             "purpose, the direction of a 1/2/3 scale is a guess we will not make):\n  "
             + "\n  ".join(bad))
    if not labels:
        _die(f"{path} parsed but contains no labelled units")
    return labels


# ---------------------------------------------------------------- photo matching
# TWO conventions, documented here because the founder's dump will arrive in one of them:
#   (a) FILENAME-STEM PREFIX:  unit12_front.jpg, unit12-back.jpg, unit12.jpg -> unit12.
#       The unit id must be the START of the stem and be followed by a separator (or be
#       the whole stem). LONGEST id wins, so unit12_front.jpg goes to unit12, never to a
#       unit1 that also exists -- and 'unit1' + '2' is not a separator anyway.
#   (b) FOLDER-PER-UNIT:  unit12/IMG_0031.jpg -> unit12, matched on any parent directory
#       name (nearest first) under PHOTO_DIR, same prefix rule.
# If (a) and (b) disagree for one file (a photo named unit7_x.jpg sitting inside
# unit12/), that is ambiguous and prep ABORTS listing it -- guessing would silently pair
# a photo with the wrong truth, which corrupts the key, which corrupts every score after.
_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp",
               ".tif", ".tiff"}
_SEPARATORS = "_-. ()[]"


def _prefix_match(name, uids_longest_first):
    s = name.casefold()
    for uid in uids_longest_first:
        u = uid.casefold()
        if s == u or (s.startswith(u) and s[len(u)] in _SEPARATORS):
            return uid
    return None


def match_photos(photo_dir, unit_ids):
    """-> ({unit_id: [relpaths]}, [stray relpaths]). Aborts on ambiguity."""
    uids = sorted(unit_ids, key=len, reverse=True)
    by_unit = {u: [] for u in unit_ids}
    strays, conflicts = [], []
    for root, dirs, files in os.walk(photo_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in sorted(files):
            if fn.startswith(".") or os.path.splitext(fn)[1].lower() not in _PHOTO_EXTS:
                continue                                 # .DS_Store, thumbnails, etc.
            rel = os.path.relpath(os.path.join(root, fn), photo_dir)
            stem_uid = _prefix_match(os.path.splitext(fn)[0], uids)
            dir_uid = None
            for part in reversed(os.path.dirname(rel).split(os.sep)):
                if part:
                    dir_uid = _prefix_match(part, uids)
                    if dir_uid:
                        break
            if stem_uid and dir_uid and stem_uid != dir_uid:
                conflicts.append(f"{rel}: filename says {stem_uid!r}, "
                                 f"folder says {dir_uid!r}")
                continue
            uid = stem_uid or dir_uid
            (by_unit[uid] if uid else strays).append(rel)
    if conflicts:
        _die("ambiguous photo-to-unit matches -- rename or move these and re-run:\n  "
             + "\n  ".join(conflicts))
    return by_unit, strays


# ---------------------------------------------------------------- prep (pack builder)
def prep(photo_dir, labels_csv, pack_dir, key_path=None, shuffle_seed=20260815):
    """Build the blind pack. Prints ONLY counts and paths -- never a unit id of a packed
    photo, never a grade, never the class prior. (Stray/unmatched filenames ARE printed:
    they pair with no truth, and silently dropping a photo is the worse failure.)"""
    labels = load_labels(labels_csv)
    by_unit, strays = match_photos(photo_dir, list(labels))
    missing = [u for u, ps in by_unit.items() if not ps]
    if missing:
        _die("labelled units with NO matching photo (conventions: unit-id filename "
             "prefix, e.g. unit12_front.jpg, or folder-per-unit, e.g. unit12/x.jpg):\n  "
             + "\n  ".join(missing))
    for s in strays:
        print(f"  SKIPPED (matches no labelled unit): {s}")

    os.makedirs(pack_dir, exist_ok=True)
    existing = [e for e in os.listdir(pack_dir)]
    if existing:
        # A half-old half-new pack would let stale images sit beside a fresh key --
        # the key would then be WRONG for those cases, invisibly. Refuse.
        _die(f"pack dir {pack_dir} is not empty ({len(existing)} entries) -- "
             "refusing to mix packs. Point --out at a fresh directory.")
    if key_path is None:
        key_path = pack_dir.rstrip(os.sep) + "_key.json"
    pack_abs = os.path.abspath(pack_dir)
    if os.path.commonpath([pack_abs, os.path.abspath(key_path)]) == pack_abs:
        _die(f"key path {key_path} is INSIDE the pack dir. The key must live outside "
             "the directory the grader is handed -- that separation is the protocol.")

    # SHUFFLE the unit->case assignment. The CSV almost certainly arrives sorted by
    # something (date received, or worse, by grade), and a case order that mirrors it
    # would hand the grader the operator's ordering for free. Seeded so a re-run of prep
    # on the same inputs rebuilds the identical pack (auditable), and the seed is
    # recorded in the key. Determinism is not a leak here: reproducing the shuffle
    # requires the CSV, and a grader with the CSV has the answers anyway -- see the
    # docstring on why this blind is procedural.
    units = list(labels.items())
    random.Random(shuffle_seed).shuffle(units)

    width = max(2, len(str(len(units) - 1)))
    cases, n_photos = {}, 0
    for i, (uid, grade) in enumerate(units):
        cid = f"c{i:0{width}d}"
        cdir = os.path.join(pack_dir, cid)
        os.makedirs(cdir)
        entries = []
        # Packed names are img00/img01/... with ONLY the extension kept. The original
        # name is dropped entirely -- not just the unit id: the operator's suffixes
        # ("_front" is harmless, but nothing stops a "_scrapped") are text we cannot
        # audit, so none of it crosses into the pack. The orig name lives in the key,
        # where the view labels remain available to anyone analysing AFTER unblinding.
        # Bytes are copied verbatim (see docstring); the sha256 makes every packed image
        # traceable to its source file, so the pack<->key pairing is self-auditing.
        for j, rel in enumerate(sorted(by_unit[uid], key=str.casefold)):
            ext = os.path.splitext(rel)[1].lower()
            dst = f"img{j:02d}{ext}"
            shutil.copyfile(os.path.join(photo_dir, rel), os.path.join(cdir, dst))
            with open(os.path.join(cdir, dst), "rb") as f:
                sha = hashlib.sha256(f.read()).hexdigest()
            entries.append({"orig": rel, "packed": dst, "sha256": sha})
            n_photos += 1
        cases[cid] = {"unit_id": uid, "grade": grade, "photos": entries}

    _write_instructions(pack_dir, len(units))
    with open(key_path, "w") as f:
        json.dump({"created": datetime.now().isoformat(timespec="seconds"),
                   "photo_dir": os.path.abspath(photo_dir),
                   "labels_csv": os.path.abspath(labels_csv),
                   "pack_dir": pack_abs, "shuffle_seed": shuffle_seed,
                   "n_cases": len(units), "founder_defs": founder_definitions(),
                   "founder_defs_provenance": f"verbal {_FOUNDER_DATE}, secondhand, "
                                              "outcome definitions -- visual criteria "
                                              "undefined",
                   "cases": cases}, f, indent=2)
    print(f"\nwrote {len(units)} cases ({n_photos} photos) to {pack_dir}")
    print(f"key -> {key_path}  (OUTSIDE the pack, on purpose)")
    print("GRADE FIRST: write answers.json per INSTRUCTIONS.md, THEN --score. "
          "Do not open the key or the labels CSV until answers.json is committed.")
    return key_path


def _write_instructions(pack_dir, n):
    d = founder_definitions()
    text = f"""# Triage grading -- read this whole file before opening any image

This directory is a BLIND grading pack of {n} cases (one directory per case,
c00/, c01/, ...). Each case holds one or more photos of a SINGLE water-purifier
unit awaiting refurbishment. Case order is shuffled and carries no information.

## Your task

Assign every case exactly one grade: easy, medium, or hard.

## The only grading guidance you get

These are the founder's definitions, verbatim [verbal, {_FOUNDER_DATE}]. They are
OUTCOME definitions -- what ended up happening to the unit at the plant:

- easy   = "{d['easy']}"
- medium = "{d['medium']}"
- hard   = "{d['hard']}"

Predict, from the photos alone, which outcome each unit will need. No visual
criteria are provided, DELIBERATELY: nobody has defined what an operator sees
that predicts the outcome, and this pack measures the honest zero-shot
condition. Any visual hint from us would make the score measure our hint.

## What to produce

Write `answers.json` IN THIS DIRECTORY -- one entry per case, lowercase:

    {{"c00": "easy", "c01": "hard", ...}}

Every case must appear; the scorer refuses partial sets. No abstaining: if
unsure, commit your best guess. Uncertainty is expressed by the confidence
interval on the score, never by leaving cases blank.

## Protocol rules (these make the result valid)

1. Grade from PIXELS ONLY. Do not read image metadata (EXIF, GPS, timestamps,
   file sizes). Camera metadata is preserved for pixel-fidelity reasons and is
   out of bounds.
2. Do not open the key file or the labels CSV until answers.json is written and
   committed. The key is stored OUTSIDE this directory on purpose.
3. answers.json first, key second -- in that order, always. The commit order in
   the git history is the real guarantee.
"""
    with open(os.path.join(pack_dir, "INSTRUCTIONS.md"), "w") as f:
        f.write(text)


# ---------------------------------------------------------------- exact binomial CI
# Clopper-Pearson, pure Python. scipy is NOT in this venv (checked 2026-08-15) and this
# file will not add a dependency for one function: the interval is defined by two
# monotone root-finds on the binomial CDF, and bisection nails those to machine-level
# precision in 100 iterations. Definition (two-sided, conf=0.95, alpha/2 = 0.025):
#   lower = the p at which P(X >= k | n, p) = alpha/2   (0 when k = 0)
#   upper = the p at which P(X <= k | n, p) = alpha/2   (1 when k = n)
# "Exact" means guaranteed >= 95% coverage for every true p -- conservative, never
# optimistic, which is the correct direction for a number a founder will act on.
def _binom_cdf(k, n, p):
    """P(X <= k), X ~ Binomial(n, p). Term-wise in log space via lgamma so it stays
    finite for any n we will ever see (comb(n, k) overflows float64 well below n where
    lgamma still has ~1e-14 relative error)."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0
    lp, lq = math.log(p), math.log1p(-p)
    lc = math.lgamma(n + 1)
    s = 0.0
    for i in range(k + 1):
        s += math.exp(lc - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                      + i * lp + (n - i) * lq)
    return min(s, 1.0)


def _bisect_root(f, lo=0.0, hi=1.0, iters=100):
    """Root of an INCREASING f on [lo, hi]. 100 halvings -> interval ~1e-30, i.e. the
    answer is exact to float64; each step is one cheap CDF evaluation."""
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if f(mid) < 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def cp_interval(k, n, conf=0.95):
    """Exact Clopper-Pearson (lo, hi) for k successes in n trials."""
    if n == 0:
        return (0.0, 1.0)       # no data: the interval is everything. Honest, useless.
    a2 = (1.0 - conf) / 2.0
    lo = 0.0 if k == 0 else _bisect_root(
        lambda p: (1.0 - _binom_cdf(k - 1, n, p)) - a2)   # P(X>=k) rises with p
    hi = 1.0 if k == n else _bisect_root(
        lambda p: a2 - _binom_cdf(k, n, p))               # P(X<=k) falls with p
    return lo, hi


def _fmt_rate(k, n):
    """'25.0%  (1/4)  [0.6%, 80.6%]' -- rate, COUNTS, exact CI, always together. A bare
    rate from n=12 is the misleading half of a claim; the counts and the interval are
    the honest half, so the formatter refuses to separate them."""
    if n == 0:
        return "   --   (0/0)   UNMEASURED -- no units of this kind in the set"
    lo, hi = cp_interval(k, n)
    return f"{k / n * 100:5.1f}%  ({k}/{n})  [{lo * 100:.1f}%, {hi * 100:.1f}%]"


# ---------------------------------------------------------------- scoring
def _metrics(rows):
    """Same asymmetric metrics as v5_triage.report / v5_vlm_triage._metrics, as COUNTS
    (k, n) rather than bare rates, because every one gets a CI attached downstream.
      MISSED-HARD: true hard graded easier (easy OR medium). The headline -- a hard unit
        sent back onto the line carries damage no later stage remedies.
      FALSE-EASY: true medium/hard graded easy -- work that needed doing, skipped.
      OVER-TREATMENT: true easy graded up -- costs money, not safety. Reported last."""
    M = {t: {p: 0 for p in GRADES} for t in GRADES}
    for r in rows:
        M[r["truth"]][r["pred"]] += 1
    n_hard = sum(M["hard"].values())
    n_needs = sum(sum(M[t].values()) for t in ("medium", "hard"))
    n_easy = sum(M["easy"].values())
    return {
        "n": len(rows),
        "confusion": M,
        "accuracy": (sum(M[g][g] for g in GRADES), len(rows)),
        "missed_hard": (M["hard"]["easy"] + M["hard"]["medium"], n_hard),
        "false_easy": (M["medium"]["easy"] + M["hard"]["easy"], n_needs),
        "over_treat": (M["easy"]["medium"] + M["easy"]["hard"], n_easy),
        "recall": {g: (M[g][g], sum(M[g].values())) for g in GRADES},
    }


def score(answers_path, key_path, stats_out=None):
    key = json.load(open(key_path))
    ans_raw = json.load(open(answers_path))
    if not isinstance(ans_raw, dict):
        _die(f"{answers_path} must be a JSON object "
             '{"c00": "easy", ...} -- got ' + type(ans_raw).__name__)
    cases = key["cases"]

    # REFUSE partial or mismatched sets. A grader who answers only the confident cases
    # is selecting the sample by its own difficulty -- the resulting rate measures the
    # grader's confidence threshold, not its accuracy. All-or-nothing, like the sibling.
    missing = sorted(set(cases) - set(ans_raw))
    extra = sorted(set(ans_raw) - set(cases))
    if missing:
        _die(f"answers missing {len(missing)} case(s): {', '.join(missing)} -- "
             "refusing to score a partial set")
    if extra:
        _die(f"answers contain case ids not in this key: {', '.join(extra)} -- "
             "wrong pack/key pairing?")
    bad = [f"{c}: {ans_raw[c]!r}" for c in sorted(ans_raw)
           if norm_grade(ans_raw[c]) is None]
    if bad:
        _die("un-normalisable grades in answers (need easy/medium/hard):\n  "
             + "\n  ".join(bad))

    rows = [{"case": c, "unit_id": cases[c]["unit_id"], "truth": cases[c]["grade"],
             "pred": norm_grade(ans_raw[c])} for c in sorted(cases)]
    m = _metrics(rows)

    print(f"\nREAL-PHOTO TRIAGE -- {m['n']} cases, zero-shot, blind")
    print("  Grades are the founder's OUTCOME definitions [verbal 2026-08-12]; the")
    print("  visual criteria are undefined, so this measures a grader predicting his")
    print("  outcomes from pixels with no rubric. Label travels with every number.\n")
    print(f"  {'metric':<24}{'rate   (k/n)   exact 95% CI'}")
    print(f"  {'-' * 62}")
    # Missed-hard FIRST. Leading with accuracy buries the error class that matters --
    # same ordering discipline as every triage report in this repo.
    for lab, k in (("MISSED-HARD   <- lead", "missed_hard"),
                   ("false-easy", "false_easy"),
                   ("accuracy", "accuracy"),
                   ("over-treatment", "over_treat")):
        print(f"  {lab:<24}{_fmt_rate(*m[k])}")

    print(f"\n  per-class recall")
    for g in GRADES:
        print(f"    {g:<10}{_fmt_rate(*m['recall'][g])}")

    print(f"\n  confusion  truth\\pred{'easy':>8}{'medium':>8}{'hard':>8}")
    for g in GRADES:
        row = m["confusion"][g]
        print(f"    {g:<19}{row['easy']:>8}{row['medium']:>8}{row['hard']:>8}")

    wrong = [r for r in rows if r["pred"] != r["truth"]]
    if wrong:
        print(f"\n  misgraded {len(wrong)}/{m['n']}:")
        for r in wrong:
            tag = ""
            if r["truth"] == "hard":
                tag = "  <- MISSED-HARD" + (" (also false-easy)"
                                            if r["pred"] == "easy" else "")
            elif r["truth"] == "medium" and r["pred"] == "easy":
                tag = "  <- false-easy"
            print(f"    {r['case']}  unit {r['unit_id']}: truth {r['truth']:<7} "
                  f"graded {r['pred']:<7}{tag}")

    # SAY WHAT n CANNOT SETTLE. The exact upper bound of a 0/n result is
    # 1 - (alpha/2)^(1/n); it drops below 20% only at n >= 17 hard units. Below that, a
    # perfect score and a 1-in-5 miss rate are indistinguishable, and the report must
    # say so in words -- a reader who skips the CI column still meets this sentence.
    n_hard = m["missed_hard"][1]
    n_min = math.ceil(math.log(0.025) / math.log(0.8))    # smallest n: 0/n upper < 20%
    if n_hard == 0:
        print("\n  WARNING: NO hard units in this set. Missed-hard -- the metric this")
        print("  project leads with -- is UNMEASURED here, not zero. Do not quote a")
        print("  missed-hard figure from this run at all.")
    elif n_hard < n_min:
        ub0 = 1.0 - 0.025 ** (1.0 / n_hard)
        print(f"\n  NOTE ON WHAT n CAN SETTLE: with {n_hard} hard units, even a perfect "
              f"0/{n_hard} missed-hard")
        print(f"  would carry an exact 95% upper bound of {ub0 * 100:.1f}%. This run "
              "cannot distinguish a")
        print(f"  0% missed-hard rate from a 20% one; that takes >= {n_min} hard units.")

    # The scored artifact is written NEXT TO THE ANSWERS, never into sim_poc/, and its
    # name deliberately does not match stats*.json -- that namespace is the protected
    # sim baselines, which any bare eval overwrites (a lesson this repo has already
    # paid for). CIs are stored in the file so the artifact is self-auditing: nobody
    # can later quote its rate without the interval sitting in the same row.
    if stats_out is None:
        stats_out = os.path.join(os.path.dirname(os.path.abspath(answers_path)),
                                 "scored_" + os.path.basename(answers_path))
    payload = {"n": m["n"], "confusion": m["confusion"], "rows": rows,
               "answers": os.path.abspath(answers_path),
               "key": os.path.abspath(key_path),
               "scored_at": datetime.now().isoformat(timespec="seconds"),
               "label": "Zero-shot blind grading of REAL photos. Grades are the "
                        "founder's OUTCOME definitions [verbal 2026-08-12]; visual "
                        "criteria undefined. Rates carry exact Clopper-Pearson 95% CIs "
                        "-- quote the interval, not the point."}
    for name in ("accuracy", "missed_hard", "false_easy", "over_treat"):
        k, n = m[name]
        lo, hi = cp_interval(k, n) if n else (0.0, 1.0)
        payload[name] = {"k": k, "n": n, "rate": (k / n if n else None),
                         "ci95": [lo, hi]}
    with open(stats_out, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nwrote {stats_out}")
    return m


# ---------------------------------------------------------------- selftest
# Proves the pipeline END TO END before a single real photo exists: builds a synthetic
# pack, grades it with two KNOWN errors, and asserts the confusion matrix, the headline
# counts, and the CI mathematics to reference values. The fixture deliberately contains
# every trap the matcher and normaliser claim to handle -- a unit id that is a prefix of
# another (u1 / u12), a folder-per-unit photo, mixed-case and alias grades, a stray
# photo, and the two loud error paths. A harness whose first run is on the founder's
# real data is a harness being debugged in front of the founder.
def selftest(keep=False):
    import contextlib
    import re
    import tempfile
    from PIL import Image

    tmp = tempfile.mkdtemp(prefix="v5_real_triage_selftest_")
    try:
        photos = os.path.join(tmp, "photos")
        pack = os.path.join(tmp, "pack")
        key_path = os.path.join(tmp, "key.json")
        os.makedirs(photos)

        units = [  # (unit_id, grade-as-the-operator-might-type-it, photo relpaths)
            ("u1", "Easy", ["u1.jpg"]),                       # prefix of u12/u10/u11
            ("u2", "easy", ["u2.jpg"]),
            ("u3", "EASY", ["u3-left.jpg", "u3-right.jpg"]),  # multi-photo, dash sep
            ("u4", "ez", ["u4.png"]),                         # alias + png
            ("u5", "Medium", ["u5.jpg"]),
            ("u6", "med", ["u6.jpg"]),
            ("u7", "medium", ["u7.jpg"]),
            ("u8", "m", ["u8.jpg"]),
            ("u9", "hard", ["u9.jpg"]),
            ("u10", "HARD", [os.path.join("u10", "IMG_0001.jpg")]),  # folder-per-unit
            ("u11", "h", ["u11.jpg"]),
            ("u12", "Hard", ["u12_front.jpg", "u12_back.jpg"]),      # the prefix trap
        ]
        all_photos = [p for _, _, ps in units for p in ps] + ["bench_misc.jpg"]
        for i, rel in enumerate(all_photos):                  # stray ^ matches no unit
            path = os.path.join(photos, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            Image.new("RGB", (64, 48), ((i * 37) % 256, (i * 91) % 256,
                                        (i * 53) % 256)).save(path)
        labels_csv = os.path.join(tmp, "grades.csv")
        with open(labels_csv, "w") as f:                      # extra column, tolerated
            f.write("Unit_ID,Grade,notes\n")
            f.write("".join(f"{u},{g},operator remark {u}\n" for u, g, _ in units))

        # ---- prep, with the transcript captured: the blinding assertions below run
        # against what prep PRINTED, not just what it wrote -- seed 1950 was burned by
        # a print statement, so the transcript is part of the attack surface.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            prep(photos, labels_csv, pack, key_path)
        out = buf.getvalue()
        assert "12 cases (14 photos)" in out, out
        assert key_path in out and "bench_misc.jpg" in out, out
        for g in ("easy", "medium", "hard", "ez"):
            assert not re.search(rf"\b{g}\b", out, re.I), f"grade {g!r} leaked:\n{out}"
        for _, _, ps in units:
            for p in ps:
                assert os.path.basename(p) not in out, f"photo name leaked: {p}\n{out}"

        # ---- pack structure: nothing but case dirs, imgNN.ext, INSTRUCTIONS.md
        names = sorted(os.listdir(pack))
        assert names == sorted([f"c{i:02d}" for i in range(12)] + ["INSTRUCTIONS.md"])
        for cid in names:
            if cid == "INSTRUCTIONS.md":
                continue
            for fn in os.listdir(os.path.join(pack, cid)):
                assert re.fullmatch(r"img\d\d\.(jpg|png)", fn), fn
        instr = open(os.path.join(pack, "INSTRUCTIONS.md")).read()
        for verbatim in ("device not changed", "some parts changed",
                         "entire device changed", _FOUNDER_DATE):
            assert verbatim in instr, verbatim
        assert "u12_front" not in instr and "u9.jpg" not in instr

        # ---- key correctness: right units, right grades, the traps resolved right
        keyd = json.load(open(key_path))
        by_uid = {c["unit_id"]: c for c in keyd["cases"].values()}
        assert set(by_uid) == {u for u, _, _ in units}
        assert [by_uid[f"u{i}"]["grade"] for i in (1, 5, 9)] == GRADES_LIST3
        assert sorted(p["orig"] for p in by_uid["u12"]["photos"]) == \
            ["u12_back.jpg", "u12_front.jpg"], "prefix trap: u12 photos wrong"
        assert [p["orig"] for p in by_uid["u1"]["photos"]] == ["u1.jpg"], \
            "prefix trap: u1 swallowed a u12/u10/u11 photo"
        assert by_uid["u10"]["photos"][0]["orig"] == os.path.join("u10", "IMG_0001.jpg")
        assert by_uid["u12"]["photos"][0]["packed"] == "img00.jpg"

        # ---- fabricate answers: TWO deliberate errors.
        #   u9  truth hard -> answered easy    (the missed-hard, also a false-easy)
        #   u2  truth easy -> answered medium  (over-treatment)
        # u5 is answered "Medium" -- correct but case-variant, exercising the
        # normaliser on the SCORING side too.
        case_of = {c["unit_id"]: cid for cid, c in keyd["cases"].items()}
        answers = {cid: c["grade"] for cid, c in keyd["cases"].items()}
        answers[case_of["u9"]] = "easy"
        answers[case_of["u2"]] = "medium"
        answers[case_of["u5"]] = "Medium"
        ans_path = os.path.join(pack, "answers.json")
        json.dump(answers, open(ans_path, "w"))

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m = score(ans_path, key_path)
        sout = buf.getvalue()

        # ---- the confusion matrix, exactly
        assert m["confusion"] == {
            "easy": {"easy": 3, "medium": 1, "hard": 0},
            "medium": {"easy": 0, "medium": 4, "hard": 0},
            "hard": {"easy": 1, "medium": 0, "hard": 3}}, m["confusion"]
        assert m["accuracy"] == (10, 12)
        assert m["missed_hard"] == (1, 4), m["missed_hard"]
        assert m["false_easy"] == (1, 8), m["false_easy"]
        assert m["over_treat"] == (1, 4)
        assert "MISSED-HARD" in sout and "(1/4)" in sout
        assert "cannot distinguish" in sout, "small-n note missing (n_hard=4 < 17)"
        assert os.path.exists(os.path.join(pack, "scored_answers.json"))

        # ---- CI mathematics against reference values.
        # 0/12 upper = 1 - 0.025^(1/12) = 0.264648 -- the spec's own example (26.5%),
        # and 0/10 upper = 0.308504 is the textbook Clopper-Pearson value.
        lo, hi = cp_interval(0, 12)
        assert lo == 0.0 and abs(hi - 0.2646467) < 2e-4, (lo, hi)
        assert abs(cp_interval(0, 10)[1] - 0.3085042) < 2e-4
        lo, hi = cp_interval(12, 12)
        assert hi == 1.0 and abs(lo - 0.7353533) < 2e-4, (lo, hi)
        # Defining equations, i.e. the bisection actually solved the root:
        for k, n in ((1, 4), (10, 12), (3, 40)):
            lo, hi = cp_interval(k, n)
            assert abs((1.0 - _binom_cdf(k - 1, n, lo)) - 0.025) < 1e-7, (k, n)
            assert abs(_binom_cdf(k, n, hi) - 0.025) < 1e-7, (k, n)
        # Symmetry: lower(k, n) = 1 - upper(n-k, n) by the interval's construction.
        assert abs(cp_interval(3, 7)[0] - (1 - cp_interval(4, 7)[1])) < 1e-9
        # And the printed line for the missed-hard row carries counts + interval:
        assert re.search(r"25\.0%\s+\(1/4\)\s+\[0\.6%, 80\.6%\]", sout), sout

        # ---- loud-error paths: unknown grade, and a labelled unit with no photo.
        for csv_body, must_mention in (
                ("unit_id,grade\nx1,meh\n", ("x1", "meh")),
                ("unit_id,grade\nx1,easy\nx2,easy\n", ("x2",))):
            d2 = os.path.join(tmp, f"err_{must_mention[0]}")
            os.makedirs(os.path.join(d2, "ph"))
            Image.new("RGB", (8, 8)).save(os.path.join(d2, "ph", "x1.jpg"))
            cpath = os.path.join(d2, "g.csv")
            open(cpath, "w").write(csv_body)
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    prep(os.path.join(d2, "ph"), cpath, os.path.join(d2, "pack"))
                raise AssertionError(f"prep should have died on {must_mention}")
            except SystemExit as e:
                assert e.code == 2
                for tok in must_mention:
                    assert tok in buf.getvalue(), (tok, buf.getvalue())

        print("SELFTEST PASSED")
        print(f"  pack: 12 cases / 14 photos, key outside pack, prefix trap (u1/u12) "
              "resolved, folder-per-unit matched, stray skipped")
        print(f"  transcript blind: no grade word, no matched filename in prep output")
        print(f"  score: confusion exact, accuracy 10/12, missed-hard 1/4, "
              "false-easy 1/8, over-treatment 1/4")
        print(f"  CI: 0/12 -> [0.0%, 26.5%]; 0/10 -> [0.0%, 30.9%]; 12/12 -> "
              "[73.5%, 100.0%]; defining equations to 1e-7; small-n note fires")
        print(f"  error paths: unknown grade and photo-less unit both abort loudly")
    except BaseException:
        print(f"SELFTEST FAILED -- fixture kept at {tmp}")
        raise
    else:
        if keep:
            print(f"  fixture kept at {tmp}")
        else:
            shutil.rmtree(tmp)


# selftest expects u1/u5/u9 to normalise to this, in GRADES order -- module level so
# the assertion reads as one line up there.
GRADES_LIST3 = ["easy", "medium", "hard"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Blind grading packs + exact-CI scoring for REAL unit photos. "
                    "Read the module docstring; the honesty labels in it are part of "
                    "every number this prints.")
    ap.add_argument("--prep", metavar="PHOTO_DIR",
                    help="build a blind pack from a photo dir (with --labels, --out)")
    ap.add_argument("--labels", metavar="CSV",
                    help="operator labels: unit_id,grade columns (extras tolerated)")
    ap.add_argument("--out", metavar="PACK_DIR", help="pack output dir (must be empty)")
    ap.add_argument("--key", metavar="KEY_JSON",
                    help="key path (prep: default <PACK_DIR>_key.json, must be outside "
                         "the pack; score: required)")
    ap.add_argument("--shuffle-seed", type=int, default=20260815,
                    help="unit->case shuffle seed, recorded in the key (default "
                         "%(default)s)")
    ap.add_argument("--score", metavar="ANSWERS_JSON",
                    help="score committed answers against --key")
    ap.add_argument("--stats-out", metavar="PATH",
                    help="scored-artifact path (default: scored_<answers> beside the "
                         "answers file; never sim_poc/stats*.json)")
    ap.add_argument("--selftest", action="store_true",
                    help="synthetic end-to-end check of prep+score+CI math")
    ap.add_argument("--keep", action="store_true",
                    help="with --selftest: keep the fixture dir")
    a = ap.parse_args()
    if a.selftest:
        selftest(keep=a.keep)
    elif a.prep:
        if not (a.labels and a.out):
            ap.error("--prep needs --labels and --out")
        prep(a.prep, a.labels, a.out, a.key, a.shuffle_seed)
    elif a.score:
        if not a.key:
            ap.error("--score needs --key")
        score(a.score, a.key, a.stats_out)
    else:
        ap.print_help()
        sys.exit(1)
