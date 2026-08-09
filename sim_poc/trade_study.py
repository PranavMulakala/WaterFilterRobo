"""Arm-count trade study CALCULATOR -- options A / B / C / D.

    ../venv/bin/python trade_study.py            the whole sensitivity table
    ../venv/bin/python trade_study.py --md       markdown, for pasting into TRADE_STUDY.md

WHY THIS IS A SCRIPT AND NOT A SPREADSHEET IN A DOC. Every economic number in
TRADE_STUDY.md is produced here, so the doc can be regenerated when an input changes --
and the two inputs we are actually waiting on (Anirudh's YAM answer, the founder's
volume) are single constants at the top. CELL_SPEC's whole value is that its numbers
were read from the model rather than typed; this is the same discipline applied to the
money, for the same reason: typed numbers decay silently.

SOURCE TAGS. Every constant below carries one, and they are not decoration:
    [measured]  produced by our simulation, reproducible from a named command
    [published] a vendor or public figure, with a URL
    [assumed]   our estimate. States the assumption AND a plausible range, and any
                number that depends on it is reported across that range, not at a point.
"""
import argparse

# ============================================================ INPUTS
# ---------------------------------------------------------------- [open] SLOTS
# These two are the reason the study is not finished. Both are single constants;
# nothing else in the file has to change when they arrive.
#
# [open] 1 -- ANIRUDH'S YAM ANSWER. Question sent 2026-08-09: "Have you (or anyone you
#   trust) run a YAM/YAM Ultra under ~33 N sustained contact force, ~+-0.5 mm
#   repeatability needs, 16 hr/day duty? First-hand evidence only."
#   DECISION RULE, fixed BEFORE the answer so it cannot be rationalised afterwards:
#   xArm7 remains the default unless the reply contains FIRST-HAND YAM-under-load
#   evidence. "I've seen one" / "they look good" / a link does not move it.
YAM_LOAD_EVIDENCE = None        # None = unanswered; True/False when it arrives

# [open] 2 -- DAILY REFURB VOLUME. The founder has not given one. Everything downstream
#   is therefore reported as a SENSITIVITY, never a point estimate.
DAILY_VOLUME = None             # None = unknown; set an int when he answers
VOLUME_SCENARIOS = (100, 200, 400, 1000)

# ---------------------------------------------------------------- station times, seconds
# [measured] All from our own sim, reproducible. Commands in the comments.
T = {
    # v5_clean.py --eval 8                     (point raster, full coverage)
    "clean_point_full":     186.83,
    # v5_clean.py --eval 16 --stroke --seed0 1920   (V7 continuous stroke, full coverage)
    "clean_stroke_full":    137.30,
    # targeted + camera backstop, medians on fresh units
    "clean_point_targeted":  74.70,   # V6, seeds 1860-1875
    # TARGETED + STROKE IS NOT A SHIPPING MODE. Measured on fresh 2000-2015: 98.2 s
    # median (SLOWER than targeted alone) and one unit in 16 produced a 91.5 N contact,
    # twice the 45 N model-validity ceiling. The two optimisations are substitutes --
    # both remove the same per-point stall cost -- so stacking them only pays stroke's
    # per-run seat overhead many more times. Recorded, not shipped, not tuned past.
    "clean_stroke_targeted": None,
    # v5_membrane: insert 25.6 + tighten 17.4 + dip 1.2
    "membrane":              44.20,
    # TRIAGE and VERIFY cost ZERO SIMULATED SECONDS -- they are pure rendering, no
    # motion. A REAL cell must index the device past a camera and wait for a settle, so
    # the real cycle is SLOWER than anything below, never faster. [assumed] 8 s each,
    # range 4-15 s, from the 1.2 s indexer dwell x 4 faces plus exposure and transfer.
    "triage_real":            8.0,
    "verify_real":            8.0,
    # load/unload the device onto the indexer. NOT MODELLED AT ALL -- there is no
    # loading motion anywhere in v5. [assumed] 20 s, range 10-40 s.
    "load_unload":           20.0,
}

# ---------------------------------------------------------------- class mix
# [measured] observed on the 120-unit held-out triage eval (seeds 700-819):
# 39 easy / 47 medium / 34 hard. The class NAMES are DrinkPrime's; the BOUNDARIES are
# ours and remain unconfirmed -- so this mix is ours too. Flag it wherever it is quoted.
MIX = {"easy": 39 / 120, "medium": 47 / 120, "hard": 34 / 120}

# ---------------------------------------------------------------- arms
ARMS = {
    "xArm7": dict(
        price_usd=11_000,        # [published] ~$11-12K street; robotshop/ufactory list
        price_range=(11_000, 12_500),
        payload_kg=3.5,          # [published] ufactory.us xArm 7
        reach_mm=700,            # [published]
        repeatability_mm=0.1,    # [published] +-0.1 mm
        dof=7,
        rated_for_production=True,   # [assumed] it is sold as a cobot for industrial use
        url="https://www.ufactory.us/product/ufactory-xarm-7",
    ),
    "YAM": dict(
        price_usd=2_999, price_range=(2_999, 2_999), payload_kg=2.0,
        reach_mm=780, repeatability_mm=None, dof=6, rated_for_production=False,
        url="https://i2rt.com/products/yam-6-dof-arm"),
    "YAM Ultra": dict(
        price_usd=4_299, price_range=(4_299, 4_944), payload_kg=4.0,
        reach_mm=780, repeatability_mm=None, dof=6, rated_for_production=False,
        url="https://i2rt.com/pages/yam-arm"),
}

# ---------------------------------------------------------------- economics
# [assumed] EVERY NUMBER IN THIS BLOCK. None is sourced; each states its range.
ECON = dict(
    # From the brief. Consistent with PROJECT_CONTEXT's "$1.50-2.50/hr Indian assembly
    # labour" ([unsourced] there too) at 2 operators x 2 shifts x 8 h x 300 d:
    #   2 x 2 x 8 x 300 x $1.50 = $14,400 ... x $2.50 = $24,000.
    # DO NOT use the "10K" figure from the 2026-08-02 call -- PITCH_NOTES records it as
    # internally contradictory (stated both as a total and as per-worker) and hypothetical.
    labour_usd_yr=(16_000, 21_000),
    tooling_per_cell_usd=(6_000, 12_000),   # changer, ACF, pad, indexer, cameras, frame
    integration_usd=(15_000, 30_000),       # one-off: guarding, PLC, programming, FAT
    maint_frac_of_capex=(0.05, 0.10),       # $/yr as a fraction of arm+tooling capex
    uptime=(0.75, 0.90),                    # fraction of shift actually producing
    hours_per_shift=8,
    shifts=2,
    days_per_year=300,
)


# ============================================================ MODEL
def cycle_seconds(clean_s, membrane_s=T["membrane"], real_overheads=True):
    """Average CELL seconds per unit ARRIVING, across the class mix.

    EASY  -> load, triage, clean, verify, unload
    MEDIUM-> the same plus the membrane station
    HARD  -> load, triage, unload. NOTE: our HARD physical handoff is 0/6 implemented
             (it is a software decision, no motion delivers the unit anywhere), so this
             is what the cell would cost IF the handoff existed and were instant. It is
             the optimistic end.
    """
    base = 0.0
    if real_overheads:
        base = T["load_unload"] + T["triage_real"]
    easy = base + clean_s + (T["verify_real"] if real_overheads else 0)
    med = easy + membrane_s
    hard = base
    return MIX["easy"] * easy + MIX["medium"] * med + MIX["hard"] * hard


def throughput_per_hour(cycle_s, arms_in_parallel=1, uptime=0.85):
    """Units/hour. `arms_in_parallel` = independent cells working the same queue."""
    return 3600.0 / cycle_s * arms_in_parallel * uptime


def cells_needed(daily_units, cycle_s, uptime, hours, shifts):
    per_cell_per_day = throughput_per_hour(cycle_s, 1, uptime) * hours * shifts
    n = 1
    while n * per_cell_per_day < daily_units:
        n += 1
        if n > 50:
            break
    return n, per_cell_per_day


def capex(n_cells, arm_price, arms_per_cell, tooling, integration):
    return n_cells * (arms_per_cell * arm_price + tooling) + integration


# ============================================================ OPTIONS
def options(clean_s=None):
    """clean_s defaults to the SHIPPING mode: full coverage, continuous stroke.

    Full coverage is the default because "ENSURING ALL SURFACES ARE COVERED" is
    DrinkPrime's own Stage-2 wording, not a bar we chose. Pass T["clean_point_targeted"]
    to see the cell with the opt-in targeted mode enabled instead.
    """
    cst = clean_s or T["clean_stroke_full"]
    return {
        "A  1x xArm7, continuous stroke": dict(
            arm="xArm7", arms_per_cell=1, clean_s=cst, membrane_s=T["membrane"],
            note="one arm does triage/clean/membrane/verify; V7 stroke + targeted"),
        "B  2x xArm7, split stations": dict(
            arm="xArm7", arms_per_cell=2, clean_s=cst, membrane_s=T["membrane"],
            pipeline=True,
            note="arm 1 cleans, arm 2 does membrane; cycle = the SLOWER station"),
        "C  fixed brushes + 1x xArm7": dict(
            arm="xArm7", arms_per_cell=1, clean_s=None, membrane_s=T["membrane"],
            brush=True,
            note="passive powered brushes clean while the indexer turns; arm does membrane"),
        "D  YAM Ultra, same topology as A": dict(
            arm="YAM Ultra", arms_per_cell=1, clean_s=cst, membrane_s=T["membrane"],
            note="identical cell, cheaper arm; see the RISK block -- not a like-for-like"),
    }


# [assumed] OPTION C's cleaning time. A powered brush pressed on a rotating box cleans
# all four vertical faces in one revolution. At the 1.2 s/90 deg the indexer is already
# validated for, one revolution is ~5 s; allow 3 revolutions for coverage plus a
# separate top-face brush pass: 25 s, range 15-45 s.
BRUSH_CLEAN_S = 25.0
BRUSH_CLEAN_RANGE = (15.0, 45.0)
# [measured] THE CONSTRAINT THAT DECIDES WHETHER C IS BUILDABLE AT ALL. The cabinet is
# 180 x 250 mm, so a point on its surface swings between the half-width (90 mm) and the
# half-diagonal (sqrt(90^2 + 125^2) = 154.1 mm) from the rotation axis: a fixed brush
# must absorb 64.1 mm of radial travel every quarter turn. Our ACTIVE CONTACT FLANGE has
# 30 mm. So C cannot reuse the arm's compliance -- it needs its own sprung brush with
# >= 64 mm of travel (ordinary for car-wash hardware, but it is a REQUIREMENT, not an
# assumption), or a profile-following carriage.
BOX_RADIAL_SWING_MM = 64.1
ACF_STROKE_MM = 30.0


def evaluate(daily, opt, arm_price=None, uptime=0.85, verbose=False):
    a = ARMS[opt["arm"]]
    price = arm_price if arm_price is not None else a["price_usd"]
    if opt.get("brush"):
        cyc = cycle_seconds(BRUSH_CLEAN_S, opt["membrane_s"])
    elif opt.get("pipeline"):
        # A PIPELINE'S THROUGHPUT IS ITS SLOWEST STATION, not the sum -- and each
        # station's load is averaged over ARRIVING units, because not every unit visits
        # every station. Station 1 (load, triage, clean, verify) sees easy+medium for
        # the full job and hard for triage only. Station 2 (membrane) sees medium only.
        # Assumes a buffer between them, which is the generous assumption for B.
        s1 = (T["load_unload"] + T["triage_real"]
              + (MIX["easy"] + MIX["medium"]) * (opt["clean_s"] + T["verify_real"]))
        s2 = MIX["medium"] * opt["membrane_s"] + T["load_unload"]
        cyc = max(s1, s2)
    else:
        cyc = cycle_seconds(opt["clean_s"], opt["membrane_s"])
    n, per_cell_day = cells_needed(daily, cyc, uptime, ECON["hours_per_shift"],
                                   ECON["shifts"])
    tool = sum(ECON["tooling_per_cell_usd"]) / 2
    integ = sum(ECON["integration_usd"]) / 2
    if opt.get("brush"):
        tool += 8_000            # [assumed] brush station: motors, frame, sprung carriage
    cap = capex(n, price, opt["arms_per_cell"], tool, integ)
    maint = cap * sum(ECON["maint_frac_of_capex"]) / 2
    return dict(cycle_s=cyc, per_cell_day=per_cell_day, cells=n, capex=cap,
                maint_yr=maint, arms=n * opt["arms_per_cell"])


def payback_years(cap, maint, labour_yr, cells):
    """Years to repay capex out of displaced labour, net of maintenance.

    Displaced labour scales with the number of MANUAL STATIONS replaced, which we take
    as one per cell. [assumed] and the weakest link in the whole calculation: if one
    operator can tend two cells, or if the plant redeploys rather than removes people,
    this number is meaningless. The founder has said his constraint is THROUGHPUT, not
    cost (secondhand, unconfirmed) -- in which case payback is the wrong lens entirely
    and units/hour per dollar is the right one. Both are reported.
    """
    saved = labour_yr * cells - maint
    return (cap / saved) if saved > 0 else float("inf")


def main(md=False, clean_s=None):
    opts = options(clean_s)
    W = "|" if md else " "
    print("\n" + "=" * 96)
    print("ARM-COUNT TRADE STUDY -- sensitivity on DAILY REFURB VOLUME (unknown)")
    print("=" * 96)
    print(f"clean (shipping mode) = {opts['A  1x xArm7, continuous stroke']['clean_s']:.1f} s "
          f"[measured]   membrane = {T['membrane']:.1f} s [measured]")
    print(f"triage/verify/load = {T['triage_real']:.0f}/{T['verify_real']:.0f}/"
          f"{T['load_unload']:.0f} s [assumed]   uptime 0.85 [assumed 0.75-0.90]")
    print(f"class mix easy/medium/hard = {MIX['easy']:.2f}/{MIX['medium']:.2f}/"
          f"{MIX['hard']:.2f} [measured, but the BOUNDARIES are ours]")
    for daily in VOLUME_SCENARIOS:
        print(f"\n--- {daily} units/day " + "-" * 60)
        print(f"  {'option':<34}{'cycle s':>9}{'u/cell/d':>10}{'cells':>7}"
              f"{'arms':>6}{'capex $':>11}{'maint $/y':>11}{'payback y':>11}")
        for name, opt in opts.items():
            r = evaluate(daily, opt)
            lo = payback_years(r["capex"], r["maint_yr"], ECON["labour_usd_yr"][1],
                               r["cells"])
            hi = payback_years(r["capex"], r["maint_yr"], ECON["labour_usd_yr"][0],
                               r["cells"])
            pb = f"{lo:.1f}-{hi:.1f}" if lo < 90 else "never"
            print(f"  {name:<34}{r['cycle_s']:>9.1f}{r['per_cell_day']:>10.0f}"
                  f"{r['cells']:>7}{r['arms']:>6}{r['capex']:>11,.0f}"
                  f"{r['maint_yr']:>11,.0f}{pb:>11}")
    # ---- the throughput-normalised lens. If the founder's constraint really is
    # THROUGHPUT rather than cost (secondhand, unconfirmed), payback is the wrong
    # question and this is the right one: what does a unit/day of capacity cost?
    print("\n" + "=" * 96)
    print("COST PER UNIT/DAY OF CAPACITY  (the right lens if the constraint is "
          "THROUGHPUT, not cost)")
    print("=" * 96)
    print(f"  {'option':<34}{'u/hr':>8}{'u/day':>9}{'capex/1 cell':>14}"
          f"{'$ per unit/day':>16}")
    for name, opt in opts.items():
        r = evaluate(100, opt)          # 1 cell, volume-independent
        uhr = throughput_per_hour(r["cycle_s"], 1, 0.85)
        print(f"  {name:<34}{uhr:>8.1f}{r['per_cell_day']:>9.0f}{r['capex']:>14,.0f}"
              f"{r['capex']/r['per_cell_day']:>16,.0f}")

    print("\n" + "=" * 96)
    print("BREAKEVEN TABLE -- the volume at which each option needs another cell")
    print("=" * 96)
    print(f"  {'option':<34}" + "".join(f"{v:>9}" for v in VOLUME_SCENARIOS)
          + "     first step-up at")
    for name, opt in opts.items():
        cells = [evaluate(v, opt)["cells"] for v in VOLUME_SCENARIOS]
        per = evaluate(100, opt)["per_cell_day"]
        print(f"  {name:<34}" + "".join(f"{c:>9}" for c in cells)
              + f"     ~{per:.0f}/day")
    print("  (cells needed, at 2 shifts x 8 h x 0.85 uptime [assumed])")

    print("\n" + "=" * 96)
    print("WHERE THE ANSWER FLIPS")
    print("=" * 96)
    a = evaluate(200, opts["A  1x xArm7, continuous stroke"])
    print(f"  One xArm7 cell produces {a['per_cell_day']:.0f} units/day at 2 shifts and "
          f"0.85 uptime [assumed].")
    print(f"  So a SECOND CELL is needed above ~{a['per_cell_day']:.0f}/day, a third above "
          f"~{2*a['per_cell_day']:.0f}/day, and so on.")
    print(f"  The estimated 130-200/day [assumed, unconfirmed] sits "
          f"{'BELOW' if 200 < a['per_cell_day'] else 'AROUND'} that line -- i.e. ONE CELL "
          f"probably covers it.")
    b = evaluate(200, opts["B  2x xArm7, split stations"])
    print(f"\n  Option B (2 arms, split stations) has cycle {b['cycle_s']:.1f} s vs A's "
          f"{a['cycle_s']:.1f} s")
    print(f"  -- a {a['cycle_s']/b['cycle_s']:.2f}x gain for 2x the arms, because a "
          f"pipeline runs at its SLOWEST station")
    print(f"  and cleaning ({opts['A  1x xArm7, continuous stroke']['clean_s']:.0f} s) "
          f"dwarfs membrane ({T['membrane']:.0f} s). Two INDEPENDENT cells beat one "
          f"2-arm pipeline")
    print("  at every volume: 2.00x for the same 2 arms. B is only right if a station "
          "cannot be duplicated")
    print("  (one licence, one fixture, one camera rig) -- which is not our case.")
    print(f"\n  NOTE THE INTERACTION WITH V7: making the single arm FASTER at cleaning "
          f"makes B WORSE,")
    print(f"  not better. At the old {T['clean_point_full']:.0f} s clean the split was "
          f"more lopsided still.")
    c = evaluate(200, opts["C  fixed brushes + 1x xArm7"])
    print(f"\n  Option C is the biggest throughput lever on paper "
          f"({c['cycle_s']:.0f} s vs {a['cycle_s']:.0f} s) and it is")
    print(f"  gated by ONE MEASURED NUMBER: a {BOX_RADIAL_SWING_MM:.1f} mm radial swing "
          f"per quarter turn against a {ACF_STROKE_MM:.0f} mm flange.")
    print("  The arm's compliance cannot be reused; the brush needs its own >=64 mm "
          "sprung travel.")
    print("  It also cleans BLIND -- no per-patch verification, so the camera backstop "
          "becomes the only")
    print("  evidence of coverage. That is a real regression in what we can PROVE, "
          "which is our product.")
    print(f"\n  Option D saves ${ARMS['xArm7']['price_usd'] - ARMS['YAM Ultra']['price_usd']:,} "
          f"per arm. See the RISK block -- it is not a like-for-like swap.")
    print("\n" + "=" * 96)
    print("OPTION D RISK REGISTER  (unknowns priced as risk, not as zero)")
    print("=" * 96)
    wipe_n = 32.15
    kg_equiv = wipe_n / 9.81
    for arm in ("YAM", "YAM Ultra"):
        a_ = ARMS[arm]
        util = kg_equiv / a_["payload_kg"]
        print(f"  {arm:<10} payload {a_['payload_kg']} kg [published] vs our "
              f"{wipe_n:.1f} N sustained wipe = {kg_equiv:.2f} kg-equivalent "
              f"[measured] -> {util*100:.0f}% of rating")
        print(f"  {'':<10} BEFORE the ~1 kg tool, and that is a SUSTAINED push for the "
              f"whole clean cycle, not a lift.")
    print(f"  repeatability: xArm7 +-{ARMS['xArm7']['repeatability_mm']} mm [published]; "
          f"YAM NOT PUBLISHED [published absence, doc.i2rt.com]")
    print("  our tightest need: tool-changer capture 4 mm / 4 deg [measured], membrane "
          "seat 1.31-1.61 mm")
    print("  against a 1.8 mm bound [measured]. That is a +-0.5 mm-class requirement "
          "with no vendor number to check it against.")
    print("  duty: 2 shifts x 300 days is continuous industrial duty; YAM is marketed "
          "for 'research and embodied AI")
    print("  data collection' [published]. Not a defect -- a different product category.")
    print(f"\n  [open] YAM_LOAD_EVIDENCE = {YAM_LOAD_EVIDENCE} -- until this is True, "
          f"the decision rule keeps xArm7.")
    print(f"  [open] DAILY_VOLUME = {DAILY_VOLUME} -- until this is a number, read the "
          f"table, not a single row.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--targeted", action="store_true",
                    help="run the table with the opt-in targeted clean (74.7 s) "
                         "instead of the shipping full-coverage stroke")
    a = ap.parse_args()
    main(a.md, T['clean_point_targeted'] if a.targeted else None)
