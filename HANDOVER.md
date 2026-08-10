# HANDOVER — state as of 2026-08-09 (evening)

**Read `CLAUDE.md` first** (phase table + seed ledger are authoritative). This is the
five-minute version. `git log` is the detailed one; every commit message carries its
own evidence.

## Where things stand

| thing | state |
|---|---|
| v2 insert / v3 swap / v4 refurb loop | 100% / 100% / 86.7% — byte-locked baselines |
| v5 TRIAGE | 97.5% on 120 fresh units, missed-hard 0.0%, false-easy 2.5% |
| v5 CLEAN — full coverage, point raster | 100% coverage, 0 missed of 129, peak 32.9 N under a 45 N ceiling, **186.8 s** |
| **V7 CLEAN — full coverage, CONTINUOUS STROKE (default)** | **100% on 16 fresh units, 0 missed of 256, peak 32.15 N (below point mode), 100% in band, sabotage 10/10, 0 false verifies — 137.3 s (1.36×)** |
| **V6 targeted clean** (opt-in, point raster) | **0/24 residue on fresh units**, sabotage caught 15/15, **~75–120 s** |
| targeted + stroke | **MEASURED AND REJECTED** — 98.2 s median (slower than targeted alone) and a 91.5 N contact on 1 of 16 |
| v5 VERIFY | honest 10/10 verified, 0/10 false verifies, sabotage caught 10/10 |
| **V6-ARM membrane** | arm **inserts element** (10/10, worst seat 1.61/1.8 mm), **places the cap** (10/10, worst 1.86 mm into a 4 mm capture envelope) and **holds the driver**; stalls 10/10, leak 10/10, sabotage caught 10/10, **0 false pass** (1890–99) |
| routing | declared-trace 28/28 · right-route 26/28 · **fully backed 22/28** ← quote this one · false-easy 0/28 |
| **full MEDIUM cycle** | **2:44.5** (V6-ARM targeted) / **3:03** (V7 full-coverage stroke; was 3:51 on the point raster). True-1× videos for both |

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
3. **TRADE STUDY — DONE.** `TRADE_STUDY.md` + `sim_poc/trade_study.py`. Headline: **one
   xArm7 cell does ~328 units/day; the estimated need is 130–200.** The arm-count question
   is moot at the expected volume. Two arms in a pipeline are worth **1.13×**, not 2× —
   and V7 made that *worse*, not better. Fixed brushes are the real lever ($71 vs $130 per
   unit/day) but clean blind. YAM stays option D behind a pre-committed decision rule.

## Next steps, ranked

1. **DECIDE: clamp the arm to its published speed?** ← the only open technical decision.
   Found 2026-08-09 by Pranav watching the video and saying the arm "flails". He was
   right, and no metric we had could have caught it — every number this station reports is
   about CONTACT (force, coverage, tilt), so free-space motion appears in none of them.
   Measured, split by phase:

   | phase | p50 | p99 | max |
   |---|---|---|---|
   | the sweep itself | 93 | 139 | 283 mm/s |
   | seat into contact | 64 | 850 | 894 mm/s |
   | reposition SAFE | 165 | 2501 | 2651 mm/s |
   | reposition TO TOP | 128 | 3005 | **3020 mm/s** |

   UFACTORY publish **180 °/s per joint and 1 m/s at the TCP**; we command 10 rad/s. This
   is PRE-EXISTING — v5, v6 and v7 all inherit the constant. Clamping to the published
   rate is **one line in `ArmProfile`** (which is what that block exists for) and measures:

   | | cycle | coverage | peak force |
   |---|---|---|---|
   | stroke, as shipped | 137.3 s | 100% | 32.15 N |
   | **stroke, physical** | **144.3 s** | **100%** | **27.35 N** |
   | point, as shipped | 186.8 s | 100% | 32.94 N |
   | **point, physical** | **180.8 s** | **100%** | 33.45 N |

   So it costs 7 s on stroke, makes point mode *faster*, and LOWERS peak force. **It is
   better on every accuracy metric.** Not adopted because it re-baselines every published
   cleaning/route number (~2 h of re-validation). `v5_video.py --physical` renders it;
   `media/v7_physical_speed.mp4` is that clip. **If in doubt, adopt it** — the current
   numbers are optimistic in a way a customer could check against a datasheet.
2. **Chase the founder.** Still unanswered since 2026-08-04, and the "cleans the filter
   with a solution" question can still invalidate v5 CLEAN entirely.
3. **If throughput ever becomes the constraint, option C (fixed brushes) is the lever** —
   but it cleans blind, which costs us the per-patch evidence that is the actual product.
4. If the founder stays silent, consider building the **v4-style solution dip** as a hedge —
   it is closer to the funding bar's literal wording than anything in v5.

## Consistency check against numbers already quoted — one flag, no retraction

Nothing shown to the founder or Anirudh is retracted. Two things are superseded and one
was temporarily unreproducible; all three are recorded rather than silently overwritten.

1. **FLAG — a published number was temporarily unreproducible, and is now restored.**
   `stats_v5_clean.json` (100% coverage, 0 missed, **peak 32.94 N**) was measured at
   `ffd1781`, *before* `cap_blank` existed. From `b388669` through `5b14b0e` the keyframe
   bug perturbed every cleaning run and the same command returned **33.9 N** and 136
   infeasible poses instead of 144. **The published figure was always the right one** — the
   scene was wrong, not the number — and after the keyframe fix `--eval 8` reproduces it
   exactly. **One committed artifact was carrying the bad figure: `stats_v5_route.json`
   was regenerated at `b388669` and recorded `f_max` 33.947 N on every cleaned unit. It
   now reads 32.935 N. Every route HEADLINE is unchanged** — compliance 28/28, right-route
   26/28, end-to-end 26/28, fully-backed 22/28, false-easy 0, missed-hard 0, clean verified
   22/22, leak 10/10 — so nothing derived from that file needs restating; only the force
   margin was ~1 N pessimistic. Membrane (10/10, 0 false pass) reproduces byte-identically.
2. **SUPERSEDED (internal, not shown to anyone).** `meetings/anirudh_feedback_2026-08-08.md`
   estimates a 2-arm pipeline at **~1.4×** from the clean-vs-membrane split alone. The
   trade study computes **1.13×** under a fuller model (load/triage/verify overheads,
   averaged over the class mix, and the faster V7 clean). Both are stated; the 1.4× was
   never wrong for what it computed.
3. **SUPERSEDED.** "Full MEDIUM cycle 3:51" for full-coverage cleaning is now **3:03**
   (`media/v7_clean_stroke_realtime.mp4`, true 1×). The V6 targeted headline (2:33) is
   unchanged — V7 does not help that mode and was measured not to.

## Traps that will bite you first

- Any bare `--eval` overwrites a committed baseline. Every default `--seed0` reproduces its
  published number. **Seed ledger: next free 2100+.**
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
