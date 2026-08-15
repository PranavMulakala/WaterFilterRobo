# HANDOVER — state as of 2026-08-12 (evening)

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
| **V8 SOLUTION station** (opt-in, `--solution`) | the arm CHARGES THE PAD from a tray before cleaning and re-dips when low. **100% coverage, 0 missed of 252, peak 22.62 N, 1 dip/unit, 0.00 s dry-pad contact** on 16 fresh units (2204–2219). Clean 108.1 → **114.4 s** (dip 6.34 s/unit). Force/tracking/tilt **byte-identical** to the dry baseline. **Paired render, seed 1704: 2:36.1 without the dip → 2:42.6 with it** |
| **V9 (2026-08-13)** | **inline verify** (10.0 s pass gone; battery row-identical paired + 10/10 fresh), **20 rad/s spindle** (the "dead lever" was a silent ctrlrange clamp; battery 10/10), **Stage 3 faithful: three cloths** (16/16 at 100%, 0 missed of 249, dry pad asserted never-charged), **O-ring blind spot MEASURED: 10/10 damaged seals pass the bubble check** |
| **full MEDIUM cycle — TWO configurations (V9, paired on seed 1704, true 1×)** | **BASE 2:28.6** (`media/v9_base_realtime.mp4`: CLEAN 108.1 / MEMBRANE 34.1 / SOLUTION 6.3 / VERIFY 0.0-inline) and **FULL STAGE 3 6:20.7** (`media/v9_stage3_realtime.mp4`: + RINSE 115.3 / DRY 114.1, 2 dips). *BASE supersedes V8's 2:36.1/2:42.6 (−14.0 s: inline verify −10.0, fast spindle −4.1, new posts +0.1). 6:20.7 is the honest price of the full three-cloth work instruction — never quote 2:28.6 as "Stage 3 compliant". Earlier figures 2:34.9 (V7.3) and the retracted 2:33 stand as recorded.* |

## The honesty labels that must travel with any demo

*Last audited 2026-08-12. Two entries in the previous version had gone stale and were
saying the opposite of the truth — see the note at the end.*

1. Easy/Medium/Hard **names** are DrinkPrime's, and as of 2026-08-12 the **outcome
   definitions are his too** *(verbal, relayed by Teja)*: EASY = device not changed,
   MEDIUM = some parts changed, HARD = entire device changed — which our routes already
   match. **The VISUAL criteria — what a camera sees on an incoming unit — are still
   ours and still unanswered.** He is sending a process video + real images within days
   and wants us to build the image classification.
2. Cleaning removes soil on **CONTACT, not on dwell**. At 200 mm/s a surface point spends
   ~0.30 s under the pad against ~1.0 s in point mode. A shorter rub is free here and would
   **not** be free with real cream. Modelling limit, not a result.
3. **v8 solution: the LOGISTICS of solution are modelled, the CHEMISTRY is not.** The pad
   is charged, spends its charge on contact and is re-dipped. Solution does not make soil
   easier to remove, because removal is binary on contact. The liquid is a rendered slab —
   there is no fluid simulation anywhere in this repo. `wring_s` is a drain dwell standing
   in for a squeeze the cell cannot perform. **Stage 3's rinse and dry passes are NOT
   built** — they need two more pads on two more posts.
4. Membrane: the arm does insert + cap-place + driver-hold. **Thread-start engagement
   (4 mm/4° capture) and spindle reaction torque are MODELLED.** The cap carries a
   **pick stem** — a design-for-automation feature we added, not a stock part.
5. HARD route = software decision, **no physical handoff (0/6 implemented)**.
6. Leak result is a **measured image of a modelled outcome**: torque → `seal_holds` →
   bubbles → camera. **A damaged O-ring at full torque DOES pass — measured 2026-08-13,
   10/10 damaged units missed** (`--oring` battery, 2280–2289). The model even shows the
   damage (seal preload halves) but nothing reads it and a real cell couldn't. The fix is
   hardware: an independent pressure-decay sensor on the 85 PSI charge line.
7. **TRIAGE still costs zero simulated seconds** — the arm parks and a camera renders. So
   every cycle time here remains an optimistic bound. Load/unload is unmodelled.
   **VERIFY's history, in one line: teleported (free, dishonest) → driven (10.0 s, V7.3)
   → inline (V9: graded during dwells the clean cycle already owns — not free, PRE-PAID,
   and measured identical to the driven pass).** Say "inline" wherever a V9 cycle time is
   quoted, or it reads like the retracted teleport.

> **Two labels were removed on 2026-08-12 because they had become false, and that is worth
> recording rather than quietly deleting.** The old label 2 described *targeted cleaning*,
> which was **WITHDRAWN** on 2026-08-10 after failing its own zero-residue bar under the arm
> speed clamp. The old label 6 warned that free-space moves ran **~3× the arm's rating** —
> true when written, **fixed by that same clamp**: peak joint speed is now 2.46 rad/s
> against a published 3.14, and peak tool speed 1007 mm/s against 1000, both asserted every
> run. A stale honesty label is worse than no label: it spends credibility warning about a
> defect that no longer exists, and it hides the fix.

## Open with the founder — sent 2026-08-04 evening, STILL UNANSWERED as of 2026-08-09

Grading criteria; annexure scans; 45-vs-80 PSI; CAD (bowl/cap/O-ring). Plus, added by V6:
**manual cycle time and daily refurb volume** — without them no speedup claim has a
denominator. He has also **not watched the v6 video**.

> **The "cleans the filter with a solution" question narrowed on 2026-08-12, from their own
> documents.** Stage 3 (`0024DPCRO003`) says *"Dip the CLOTH in the solution and wring out
> excess water"*, then wipe. That is the only "solution" in all 13 documents — the word
> appears three times, all in that stage, all about a cloth. The only immersion of a part
> anywhere is Stage 10's membrane assembly in a water bin, which is a pressurised bubble
> leak test, not a wash. **So it almost certainly means a solution-charged cloth wiping the
> cabinet, which is v5 CLEAN plus v8's dip — NOT a bath the device goes into.** Still ask
> him: this is our reading of his words against their documents, not his answer.

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

## Done 2026-08-12 (evening) — V8 SOLUTION STATION

- **The arm now charges its pad from a solution tray** before cleaning, and re-dips when the
  charge runs low. `--solution`, **default OFF** so every published dry number stays
  byte-locked. Held out on 16 fresh units (2204–2219): **100% coverage, 0 missed of 252,
  peak 22.62 N, 1 dip/unit, 0.00 s of dry-pad contact.** Clean station 108.1 → **114.4 s** (the dip measures **6.34 s/unit**),
  so the full cycle is **2:42.6** (paired against **2:36.1** dry on the same seed).

- **A 1.2 s figure was SUPERSEDED and it is not fully explained.** The dry cycle on seed
  1704 now measures **2:36.1**, where V7.3 published **2:34.9**. The whole difference is in
  the MEMBRANE phase (36.7 → 38.0 s). Ruled out by measurement: the clean station
  (`stats_v5_clean_stroke.json` byte-identical, CLEAN 108.1 s in both renders) and membrane
  accuracy (`stats_v5_membrane.json` byte-identical, 10/10 across the board). The only scene
  change is the solution tray — a new collidable body the pose planner must avoid — which is
  the plausible cause, **but the attribution was not isolated and is not claimed as
  measured.** Recorded rather than absorbed.
- **The corpus redirected the design and that is the headline.** The ask was a v4-style bath;
  Stage 3 says the **cloth** is dipped. A tank would have been our invention in their
  vocabulary. Recorded in `dp_process.py`'s Stage 3 note.
- **New metric: `dry_contact_s`** — seconds the pad spent pressing with nothing on it.
  It caught a sweep row (`charge_contact_s` 80) that scored **100% coverage through 0.9 s of
  dry wiping**, purely because no soil lay underneath. Shipped at 100 (1.24× margin), and
  the value is independently corroborated by DrinkPrime's own consumable ratio.
- **A precondition bug worth remembering:** V7.2's "skip the retreat when nothing rotates"
  assumed the arm arrives at face 0 from the tool lift. The dip broke that silently —
  coverage 100→75%, force 22.6→98.3 N — and the fix is that the dip is a **round trip** that
  restores the joint configuration, not just a sensible pose. Full account in `PAIN_JOURNAL`.
- **Named hardware gap:** Stage 3 needs three cloths (wash / clean-damp / dry) on three
  posts. `--rinse` and `--dry` **raise `NotImplementedError` with the reason** rather than
  no-op'ing.

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

1. **Chase the founder.** Still unanswered since 2026-08-04. **The "cleans the filter with
   a solution" question is now much narrower than it was** — Stage 3 of their own corpus
   says the CLOTH is dipped, and v8 builds exactly that — but it is still an inference we
   drew, not an answer they gave.
2. ~~The v4-style solution dip~~ **BUILT 2026-08-12, AND THE DOCUMENTS REDIRECTED IT.**
   Stage 3 says *"dip the CLOTH in the solution"* — the cloth, never the device — and that
   is the only "solution" in all 13 documents. So a bath was never the right build; a
   solution-CHARGED PAD was, and v5 CLEAN was already that motion, dry. See the V8 block in
   `CLAUDE.md`. **The remaining gap is hardware:** Stage 3 needs a wash cloth, a clean damp
   cloth and a dry cloth — three pads on three posts — and we have one. `--rinse`/`--dry`
   refuse with that reason rather than no-op'ing.
3. **Put the Stage 3 reading to the founder.** We now believe *"cleans the filter with a
   solution"* means a solution-charged cloth, on the strength of their own work instruction.
   That is an inference, not an answer, and it is the cheapest question left to ask.
4. **Decide whether v8 ships as the default.** It is opt-in (`--solution`) so every
   published dry-wipe number stays byte-locked. Turning it on costs ~6 s/unit and is the
   only configuration that matches the funding bar's wording. That is a founder call, not
   ours.
5. **If throughput ever becomes the constraint**, option C (fixed brushes) is the lever —
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
