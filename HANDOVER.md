# HANDOVER — state as of 2026-08-12

**Read `CLAUDE.md` first** (phase table + seed ledger are authoritative). This is the
five-minute version. `git log` is the detailed one; every commit message carries its
own evidence.

## Where things stand

| thing | state |
|---|---|
| v2 insert / v3 swap / v4 refurb loop | 100% / 100% / 86.7% — byte-locked baselines |
| v5 TRIAGE | 97.5% on 120 fresh units, missed-hard 0.0%, false-easy 2.5% |
| v5 CLEAN — full coverage, point raster | 100% coverage, 0 missed of 129, peak **23.9 N** under a 45 N ceiling, **180.9 s** |
| **V7 CLEAN — full coverage, CONTINUOUS STROKE (default)** | **100% on 16 fresh units, 0 missed of 273, peak 22.6 N, 100% in band, sabotage 10/10, 0 false verifies — 108.1 s (1.67× on the station)** |
| ~~V6 targeted clean~~ | **WITHDRAWN 2026-08-10.** Under the arm-speed clamp it left residue on **1 of 24** units and failed verify on one (seed 1844, backstop exhausted), with one **98.67 N** contact. Its published claim was 0/24. |
| targeted + stroke | **MEASURED AND REJECTED** (pre-clamp) — 98.2 s median, slower than targeted alone, and a 91.5 N contact on 1 of 16 |
| v5 VERIFY | honest 10/10 verified, 0/10 false verifies, sabotage caught 10/10. **Costs 10.0 s — the arm DRIVES clear and the indexer ROTATES each face past the camera. It used to teleport both, which is why it was recorded as free.** |
| **V6-ARM membrane** (36.7 s, V7.3) | arm **inserts element** (10/10, worst seat 1.61/1.8 mm), **places the cap** (10/10, worst 1.86 mm into a 4 mm capture envelope) and **holds the driver**; stalls 10/10, leak 10/10, sabotage caught 10/10, **0 false pass** (1890–99) |
| routing | declared-trace 28/28 · right-route 26/28 · **fully backed 22/28** ← quote this one · false-easy 0/28 (byte-identical after the clamp) |
| **full MEDIUM cycle** | **2:34.9** (V7.3, `media/v7_clean_stroke_realtime.mp4`) — ONE CONTINUOUS take, no teleports, and VERIFY is counted (10.0 s) for the first time. True-1×. *The 2:33 / 2:44.5 TARGETED figures are RETRACTED — full coverage is now FASTER than the retracted shortcut, without the shortcut.* |

## The five honesty labels that must travel with any demo

1. Easy/Medium/Hard **names** are DrinkPrime's; the **boundaries are ours** (asked, unanswered).
2. Targeted cleaning's dirt **locations** are ground truth standing in for camera
   localisation; the **residue check is a real camera** and catches sabotage 15/15.
3. Membrane: the arm does insert + cap-place + driver-hold. **Thread-start engagement
   (4 mm/4° capture) and spindle reaction torque are MODELLED.** The cap carries a
   **pick stem** — a design-for-automation feature we added, not a stock part.
4. HARD route = software decision, **no physical handoff (0/6 implemented)**.
5. Leak result is a **measured image of a modelled outcome**: torque → `seal_holds` →
   bubbles → camera. A damaged O-ring at full torque would pass. Not independently falsified.
6. **The arm's FREE-SPACE moves are ~3× faster than the real xArm7 can go.** The setpoint
   rate limit is 10 rad/s against a published 180 °/s (3.14 rad/s), and the pad reaches
   **3.0 m/s** against a published 1 m/s TCP limit. **Contact motion is unaffected** (the
   sweep runs at 93 mm/s median), so coverage/force/tilt are all sound — but the ~20 s of
   repositioning inside every cycle time is optimistic. See next step 1.

## Open with the founder — sent 2026-08-04 evening, STILL UNANSWERED as of 2026-08-09

Grading criteria; annexure scans; 45-vs-80 PSI; CAD (bowl/cap/O-ring); and the one that can
invalidate work: **does "cleans the filter with a solution" mean the v4 cartridge dip or v5
cabinet cleaning?** Plus, added by V6: **manual cycle time and daily refurb volume** —
without them no speedup claim has a denominator. He has also **not watched the v6 video**.

## Done this session (2026-08-09 evening) — all three advisor items closed

1. **CONTINUOUS-STROKE CLEANING — DONE, 1.36× not 2×.** See the V7 block in `CLAUDE.md`.
   The advisor's ~2× assumed the pad could sweep as fast as we liked; there is a
   **measured coverage cliff between 100 and 150 mm/s** caused by tracking, not sampling.
2. **VLM-vs-HSV TRIAGE — DONE, [demo].** 40 paired fresh units, graded blind.
   **Both 97.5%.** The VLM fixed HSV's one false-easy and introduced one **missed-hard** —
   it traded the safe error for the unsafe one, and missed-hard is the metric we lead with.
   Two discordant pairs, one each way: **no statistical evidence of any difference**
   (McNemar p = 1.0). `RESULTS_VLM_TRIAGE.md`.
3. **TRADE STUDY — DONE, AND NOW CLOSED.** `TRADE_STUDY.md` +
   `sim_poc/trade_study.py` stay as the record; the workstream is **CANCELLED**.
   **PRODUCTION ARM = xArm7, FINAL (2026-08-10) — see `DECISIONS.md`.** Anirudh confirmed
   **no first-hand YAM experience**, so the pre-committed decision rule resolved to xArm7;
   his own industrial shortlist (UR / Elite / UFACTORY) independently contained ours. YAM
   is re-scoped to a future **teleop / data bench**, which is what it is actually sold for.
   Purchase remains gated on founder funding. The study's own headline made it moot anyway:
   one cell does ~385 units/day against a 130–200 need.

## Done 2026-08-12 — documentation drift, and a skill that found it

- **A project skill** at `.claude/skills/refurb-cell-discipline/` — the measurement and
  validation discipline as an instruction document for any agent working here, with two
  reference files (gates/baselines, recurring traps) and three evals. **A/B measured on six
  subagent runs: 13/13 checks with it, 12/13 without.** Honest and modest — `CLAUDE.md` is
  auto-loaded and already enforces most of it; what the skill adds is procedural
  completeness (all three gates, archive before overwriting).
- **The exercise found real rot, which is what made it worth doing.** Fixed: four stale
  force figures in `README.md` (34.5/32.9 N → 23.9 N post-clamp), a **gate** printing
  34.5 N, a stale comment above `force_hi`, and `TRADE_STUDY.md`'s tables regenerated
  (328 → **385 units/day**).
- **One real defect:** `v5_clean.py` tagged its stats filename by *mode* but not by
  *parameter*, so `--stroke --feed 0.30` would have overwritten the published 0.20 stroke
  baseline under the same name. Now tagged `_feed{x}` / `_row{x}`; verified.
- **A retraction that goes against us, recorded as such:** the clamp cut peak wipe force
  32.2 → 22.0 N, so `TRADE_STUDY.md`'s payload objection to a YAM Ultra fell from **82% of
  its rating to 56%**. The xArm7 decision is unchanged but **no longer rests on payload** —
  it rests on YAM's unpublished repeatability and the duty cycle. Corrected in place.

## Next steps, ranked

1. **Chase the founder.** Still unanswered since 2026-08-04, and the "cleans the filter
   with a solution" question can still invalidate v5 CLEAN entirely.
2. **The v4-style solution dip — REQUESTED AND NOT YET BUILT.** Asked for directly on
   2026-08-12 and interrupted before it started. **Start by checking `sim_poc/dp_process.py`:
   no source document in the 13-PDF corpus describes cleaning a filter in a solution** (their
   dip is an *80–90 PSI bubble leak test*, not a wash), so this step would be OURS wearing
   their vocabulary and must be labelled that way. v4's cartridge dip is the nearest prior
   art and it is a cartridge, not a cabinet. Scope it, price the cycle-time cost, then build.
3. **If throughput ever becomes the constraint**, option C (fixed brushes) is the lever —
   but it cleans blind, which costs the per-patch evidence that is the actual product.
   Parked, not open: see `DECISIONS.md`.

## RETRACTIONS — 2026-08-10, from adopting the arm's published speed limits

**One number quoted externally is RETRACTED outright and two are superseded.** Recorded
here rather than silently overwritten.

### 1. RETRACTED: **"2:33 per unit"** (and the 2:44.5 V6-ARM variant)

That figure was the full MEDIUM cycle with **targeted cleaning**. Re-validated on its own
published seeds (1840–47 + 1860–75) under the clamp, that mode **no longer meets its own
acceptance bar**: **1 of 24 units left residue and failed verification** (seed 1844 —
402.9 s, coverage 96%, backstop exhausted at two re-cleans) and one unit reached **98.67 N**,
twice the 45 N model-validity ceiling. Its published claim was **0/24 residue**.

**This is not "2:33 became a bigger number".** The configuration that produced 2:33 is
withdrawn. If anyone has been shown 2:33, the correction is: *the fast cleaning mode was
withdrawn when we adopted the arm's real speed limits; the shipping mode is full coverage
at **3:11.9**.* Same failure signature as targeted+stroke (91.5 N) and the follow-error
cliff — **sparse visits plus a rate-limited approach break the stall detector**, and that
is now a known interaction, not a mystery.

### 2. SUPERSEDED: **"3:51"** → **3:46.2** (full-coverage point raster)

Barely moved, and *downward* — slower approaches overshoot less, so fewer points run to
their timeout. No claim depended on the difference.

### 3. SUPERSEDED: **"3:03"** → **3:11.9** (V7 full-coverage stroke, quoted internally only,
committed 2026-08-09). The V7 gain is now **1.23× on the cleaning station / 1.18× on the
full cycle**, down from 1.36×, because the clamp made point mode faster and stroke slower.

### What got BETTER, and it is the part worth quoting

| | before | after |
|---|---|---|
| peak contact force, point | 32.94 N | **23.93 N** |
| peak contact force, stroke | 32.15 N | **22.04 N** |
| mean press tilt | 11.7° | **8.5°** |
| exact-normal presses | 20.0% | **36.3%** |
| peak joint speed | 5.71 rad/s (327 °/s) | **2.46 (141 °/s)**, 22% inside the rating |
| peak tool speed | 3020 mm/s | **1063 mm/s** |

**Peak force nearly halved and the press geometry improved.** Slower approaches land more
gently, and better tracking makes the planner's smaller-tilt solutions reachable. Coverage,
missed spots, sabotage catch, false verifies, membrane and every route headline are
unchanged; `stats_v5_route.json` is byte-identical.

### Earlier flag, still true

`stats_v5_clean.json` was temporarily unreproducible between `b388669` and `5b14b0e` (the
`cap_blank` keyframe bug) and `stats_v5_route.json` carried its inflated 33.947 N. Both
fixed 2026-08-09; every route headline was unchanged then too.

## Traps that will bite you first

- **Peak joint speed and peak tool speed are ASSERTED in `report()` and `v5_check_spec.py`.** They exist because free-space motion was in no metric for three phases of work. Do not relax them.
- Any bare `--eval` overwrites a committed baseline. Every default `--seed0` reproduces its
  published number. **Seed ledger: next free 2200+.**
- **Never** raise `CleanConfig.speed` — 9.6% at best, and the contact model goes
  non-monotonic (108 N through a 45 N ceiling at speed 1.5/2.0, clean again at 3.0/4.0).
- **Never** shorten the 1.2 s indexer dwell. Angle-arrived ≠ settled; a 4 s "saving" broke
  coverage in BOTH modes and cost most of a session to find.
- Adding any free body? Set its qpos from `m.qpos0` in the **same commit** — `v5home`
  predates them and `mj_resetDataKeyframe` spawns them at the origin. (Happened **4×** —
  the fourth was `cap_blank`, and `v5_check_scene.py` had been failing on it unread.)
- Never materialise/teleport geometry into space the gripper currently occupies.
- `v5_video` render paths may only **add frame callbacks**. A duplicated physics loop has
  rotted and silently filmed a stale system **twice**. And the inverse bit us on
  2026-08-09: `step_to`, `_hold` and `_glide` all *accept* `frames` and never emitted
  any, so ~37 s of a 183 s cycle filmed nothing and the uniform re-time turned that into
  25% duplicated frames. **If you add a stepping loop, emit frames from it.**
- Never text-extract the QC PDFs — render them.
- `venv` is gitignored; rebuild with `./setup.sh` (Python 3.9 has no MuJoCo wheel).
