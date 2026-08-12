# Bumping `stroke_feed` to 0.30 — the number, and what it costs

**Short answer: the clean station goes 108.13 s → 100.83 s, and the full MEDIUM cycle goes
2:34.9 → 2:27.5. I measured it, but I did not change the shipped default, and I recommend
you don't either until one cheap sweep is run. The reason is narrower and more specific
than the docs make it sound — see "The objection" below.**

---

## Plan

`stroke_feed` is a shipped value with a documented rationale, a 16-unit held-out validation
and a sabotage battery behind it, so "bump it to 0.3" is a shipping decision, not an edit.
My plan was:

1. Run the three gates before touching anything.
2. Archive the stats files (any `--eval` overwrites a committed baseline).
3. Check what evidence about feed 0.30 **already exists** before generating more.
4. Confirm the 108.1 s baseline actually reproduces at HEAD.
5. Measure 0.30 with exactly one variable changed, via the CLI override, not a config edit.
6. Decide whether the number is shippable on this repo's own margin convention.

---

## What I checked first

**The three gates — all PASS.**

| gate | result |
|---|---|
| `v5_check_scene.py` | ALL PASS (incl. no interpenetration at spawn, ncon = 0) |
| `v5_check_spec.py` | ALL 50 VALUES MATCH; setpoint rate 3.14 rad/s within the published rating |
| `v5_reach.py --indexed` | PASS — every vertical face and top 100% relaxed |

One `WARN` in the spec gate (worst-case tool-speed bound 6.95 m/s at the home pose) is
self-labelled as loose by design — it sums all 7 joints slewing at once. Not a regression.

**Stats archived** to `_archive/stats_2026-08-12_pre_feed030/` (13 stats + 4 sweep files)
before running anything.

**The evidence already existed.** `sim_poc/sweep_stroke_feed.json` is the post-clamp V7.1
feed sweep on seeds 2100–2103, and it already includes a 0.30 row:

| feed | cycle | coverage | missed | peak N | tracking med / p99 / worst |
|---|---|---|---|---|---|
| 0.05 | 235.53 s | 100% | 0/81 | 21.22 | 2.5 / 12.9 / 15.18 mm |
| 0.10 | 146.61 s | 100% | 0/81 | 22.04 | 2.6 / 13.5 / 15.24 mm |
| 0.15 | 121.64 s | 100% | 0/81 | 22.47 | 2.7 / 13.7 / 15.22 mm |
| **0.20 (shipped)** | **111.41 s** | 100% | 0/81 | 22.62 | 2.8 / 14.0 / 15.20 mm |
| **0.30 (requested)** | **104.11 s** | 100% | 0/81 | 22.62 | 3.0 / 14.2 / 15.17 mm |

So 0.30 is not an untried setting — it is the top row of the sweep that chose 0.20.

---

## What I actually ran

`--budget SEED` runs **one** unit and **writes nothing**. The cleaning trajectory is
documented as open-loop and seed-independent (`v5_clean.py:2447`), so one unit gives the
*exact* time budget rather than a sample of it — only coverage and missed spots vary with
seed. That makes this the right cheap instrument here, and it fits the time box (~30 s wall
each).

**Seed 2100 — already spent** (V7.1 post-clamp feed-sweep tuning block, and the exact block
the 0.30 row above came from). **No fresh seed burned; the ledger is unchanged, next free
block is still 2200+.**

```bash
cd sim_poc
../venv/bin/python v5_clean.py --stroke              --budget 2100   # shipped 0.20
../venv/bin/python v5_clean.py --stroke --feed 0.30  --budget 2100   # requested 0.30
```

| | 0.20 (shipped) | 0.30 (requested) | delta |
|---|---|---|---|
| **simulated cycle** | **108.13 s** | **100.83 s** | **−7.30 s (−6.8%)** |
| STROKE (pad on surface) | 83.15 s | 75.85 s | −7.30 s |
| retract/rotate/approach | 19.56 s | 19.56 s | **0.00** |
| tool latch/unlatch | 5.42 s | 5.42 s | **0.00** |
| coverage (this unit) | 100.0% | 100.0% | — |
| worst path error | 15.2 mm | 15.2 mm | — |
| device shift | 0.00 mm | 0.00 mm | — |

**Baseline reproduces exactly.** 108.13 s against the published CLEAN 108.1 s, and worst
path error 15.2 mm as documented.

### Two controls I ran because I didn't trust the tree

**(a) The working tree is dirty with someone else's in-flight work.** `sim_poc/v5_clean.py`
is modified (+91/−33, mtime today 11:32) with a V7.4 servo-tracking metric — and critically
it **refactors the path-deviation measurement** (`_path_dev`) that produces the 15.2 mm
figure. I did not make this change. My first two runs were therefore against modified code,
not HEAD, so I re-ran both against committed HEAD via a throwaway copy
(`git show HEAD:sim_poc/v5_clean.py`, run as a temp file, deleted afterwards — it writes
nothing under `--budget`):

- HEAD at 0.20 → **108.13 s**, 15.2 mm, identical per-face breakdown.
- HEAD at 0.30 → **100.83 s**, 15.2 mm, identical per-face breakdown.

Both byte-identical to the dirty-tree runs, which incidentally confirms that in-flight
change's own claim to be behaviour-neutral. **The tree is exactly as I found it** — I
touched no source file and no stats file (`git status` shows only that pre-existing
modification and the new `.claude/` directory).

**(b) A control on the instrument.** The committed 4-seed sweep's 0.20→0.30 delta is
111.412 − 104.114 = **7.298 s**. My independent 1-unit HEAD measurement gives 108.13 −
100.83 = **7.30 s**. Agreement to 0.01 s across a different code revision and a different
sample size. That is the "run the metric where you already know the answer" check, and it
confirms the single-unit budget is a valid stand-in for the sweep *on time*.

The constant 3.28 s offset between the sweep and my runs is fully explained: the sweep
predates V7.2's opening-wait fix (111.4 → 108.1 s). Nothing else moved.

---

## The new cycle time

The full MEDIUM cycle is CLEAN + VERIFY + MEMBRANE. Feed touches only the cleaning stroke —
verify (10.0 s) and membrane (36.7 s) are untouched, and the retract/rotate/latch buckets
above are provably unchanged (identical to the hundredth of a second).

| | CLEAN | VERIFY | MEMBRANE | **total** |
|---|---|---|---|---|
| now, feed 0.20 | 108.1 | 10.0 | 36.7 | **154.8 s = 2:34.9** |
| feed 0.30 | 100.8 | 10.0 | 36.7 | **147.5 s = 2:27.5** |

**2:34.9 → 2:27.5, a 7.3 s / 4.7% saving.**

⚠️ **Do not confuse this with the old 2:27.3.** V7.2 published 2:27.3, but that figure did
not count VERIFY at all (it was teleporting). 2:27.5 and 2:27.3 are near-identical numbers
with completely different composition. Anyone comparing them will draw a wrong conclusion.

**If you ship this, 2:34.9 is a supersession, not a retraction** — the old figure was
correct for its configuration. `HANDOVER.md` has a RETRACTIONS section; per the skill those
are three different statements and this one is the mild one. It should still be logged,
because 2:34.9 is in `HANDOVER.md:20` and has been shown externally.

---

## The objection — and it is not the one the docs imply

I want to be precise here, because the honest version is *weaker* than a naive reading of
`CleanConfig` suggests, and overstating it would be its own kind of dishonesty.

**There is no measured cliff at 0.30.** This is not the `step_frac` 1.30 situation and not
the `row_frac` 1.50 situation. Those both sit a measurable distance from an *observed
failure* (1.414 R lattice cliff; 1.70 R measurably loses a patch). For feed, post-clamp,
**every value from 0.05 to 0.30 is 100% coverage, 0 missed, tracking identically 15.2 mm,
and peak force identical to four significant figures (22.6209 N at 0.20 vs 22.6217 N at
0.30).** The following-error clamp made tracking feed-independent, which is exactly what
V7.1 recorded. So "0.30 is next to a cliff" would be a false statement.

**What 0.30 actually lacks is an envelope.** The 1.18× margin convention is measured
against the nearest *failure*, and for feed **no failure has ever been observed** — so the
convention cannot currently be evaluated at all. 0.20's stated rationale is "1.5× headroom
to the fastest verified setting", which is margin to the edge of the **tested range**, not
to a cliff. Shipping 0.30 means shipping at the exact top of everything ever measured, with
zero knowledge of what is above it. **That is fixable by measurement, and cheaply.**

**The blocking objection is dwell, and no sim run can retire it.** The code prints this
itself (`v5_clean.py:2455`): dwell per surface point under the 60 mm pad is `0.060 / feed`.

| mode | dwell per surface point |
|---|---|
| point mode (the original residue evidence) | ~1.0 s |
| stroke, 0.20 (shipped) | **0.30 s** |
| stroke, 0.30 (requested) | **0.20 s** |

Our model removes soil on **contact, not dwell**. `wipe()` requires measured contact force
over the patch — so **the coverage metric will report 100% at any feed whatsoever.** It
cannot fail for the reason we actually care about. A check that cannot fail is not evidence.
0.30 would put us at **one fifth** of the point-mode dwell that this station's residue
results were originally built on.

And this compounds with the standing honesty label that outranks any speed number: **v5
CLEAN simulates no cream, detergent or chemistry at all** — it is a dry wipe of the cabinet
exterior, while the funding bar says *"cleans the filter with a solution"*. We would be
halving contact time on a process whose actual cleaning mechanism is not modelled. That is a
bench/founder question, not a simulator question.

**The validation gap, scoped precisely.** 2100–2103 is the **tuning** block (4 units, 81
patches). Shipping 0.30 on it and quoting its own number is "tuning on a range and reporting
that range". Shipped 0.20 has a 16-unit held-out run (2120–2135, 273 patches, 0 missed) plus
a sabotage battery (2140–2149, 10/10 caught, 0/10 false verifies). 0.30 has neither.

But be precise about what a fresh eval would actually buy: force, tilt and tracking are
**seed-independent (n = 1)** on an open-loop trajectory, and are already known at 0.30
(22.62 N, 30° max, 15.2 mm). **The only thing a held-out run adds is coverage confidence** —
and coverage failure is a rare event, so even 16 units is weak evidence that a gap band is
closed.

---

## A finding worth recording: feed is close to a dead lever above 0.20

The per-step deltas in the committed sweep (valid despite the 3.28 s offset, since it is
constant):

| step | saving |
|---|---|
| 0.05 → 0.10 | −88.9 s |
| 0.10 → 0.15 | −25.0 s |
| 0.15 → 0.20 | −10.2 s |
| **0.20 → 0.30** | **−7.3 s** |

This is flattening *faster* than 1/v (the implied constant falls 8.89 → 7.49 → 6.14 → 4.38).
Two hard facts from my two budget runs explain why:

- **25.0 s of the cycle is completely feed-independent** — retract/rotate/approach 19.56 s
  and latch/unlatch 5.42 s were identical to the hundredth of a second at both feeds.
- **The stroke bucket is not cruise-dominated.** Effective average pad speed is
  9.61 m / 83.15 s = **0.116 m/s** at a commanded 0.20, and 9.61 m / 75.85 s = **0.127 m/s**
  at a commanded 0.30. **A 50% commanded increase bought a 9% effective increase.**

So most of the stroke bucket is spent somewhere the feed knob does not act — candidates are
the trapezoidal accel ramps, the corner slowdowns at serpentine row reversals
(`stroke_corner_deg` 25°), and the deliberately gentle seat (`stroke_seat_scale` 0.20). I
did **not** instrument which, so treat that as a hypothesis worth one measurement, not a
finding. The *finding* is the 9%-for-50% ratio itself, which is measured.

**This is structurally the same result as V6's "`speed` is a dead lever" and the membrane's
"`drive_rate` is a dead lever": the time is not going where the knob acts.** Worth writing
down so nobody re-tunes it. Even at infinite feed the clean station cannot go below ~25 s of
overhead plus a substantial ramp/corner floor.

**If you want real cycle time, `row_frac` is the bigger lever.** `sweep_row.json`: 1.20 →
1.50 R saves 16.9 s at n=4 with 100% coverage and 0 missed — more than twice what feed 0.30
buys. It is declined today at 1.13× margin to a *real, measured* cliff (1.70 R loses a
patch), which is below the 1.18× bar. That is a much better-posed trade than feed, because
there the cliff is known.

---

## Concerns

1. **Dwell is unfalsifiable in this simulator** (above). This is the one that matters and it
   does not go away with more compute.
2. **`--eval` filename tagging does not protect against a feed change.** `STATS =
   f"stats_v5_clean{_tag}.json"` encodes only `stroke`/`targeted`, **not feed**. So
   `--stroke --feed 0.30 --eval 16` would silently overwrite the *published 0.20* 16-unit
   stroke baseline with a 0.30 number under the same filename. The reference doc says mode
   tagging prevents cross-contamination — it does, across modes, but **not across feeds**.
   Archive first, or add feed to the tag.
3. **The tree is dirty with in-flight V7.4 work I did not make.** It reproduces HEAD exactly
   on everything I measured, so it did not affect my result — but you should know it is
   there before anyone commits, and whoever owns it should land it first.
4. **The `--stroke-sweep` value list is hardcoded** to `[0.05, 0.10, 0.15, 0.20, 0.30]`
   (`v5_clean.py:2601`), so probing above 0.30 needs a one-line edit to that list. That
   writes `sweep_stroke_feed.json`, a sweep artifact rather than a protected baseline — but
   it is committed, so archive it (I already did).

---

## Recommendation

**Don't flip the default on the strength of what exists today — but the work to justify it
is small and I'd say it's worth doing, because unlike `row_frac` there may be no cliff here
at all.**

Order of operations:

1. **Find out whether a feed cliff exists.** This is the missing piece, and it converts the
   objection from "untested envelope" into a real margin number. Edit the sweep list to
   `[0.20, 0.30, 0.40, 0.50, 0.60]` and run on a fresh block:
   ```bash
   cd sim_poc
   ../venv/bin/python v5_clean.py --stroke --stroke-sweep 4 --seed0 2200   # writes sweep_stroke_feed.json
   ```
   ~10 min. **Expected:** given tracking is clamp-bound and identical at 15.2 mm across the
   whole current range, I'd expect coverage to hold well past 0.30 and the eventual failure
   to come from the velocity planner failing to meet corner caps, or from `t_max` timeouts
   (`3.0 + 4.0·L/feed` shrinks as feed rises — watch `hit t_max`, which is 0/10 today).
   **If the first failure is at ≥0.45, then 0.30 clears the 1.18× bar on measurement rather
   than on caution, and I'd support shipping it.**

2. **Held-out validation at 0.30**, fresh block, coverage being the only thing it buys:
   ```bash
   cp stats_v5_clean_stroke.json ../_archive/    # NOT protected by the mode tag — see concern 2
   ../venv/bin/python v5_clean.py --stroke --feed 0.30 --eval 16 --seed0 2220
   ../venv/bin/python v5_clean.py --stroke --feed 0.30 --sabotage 10 --seed0 2240
   ```
   **Expected:** 100% coverage, 0 missed, peak 22.62 N, tracking 15.2 mm, 10/10 sabotage
   caught, 0/10 false verifies — because everything except coverage is seed-independent and
   already measured. A miss here would be the informative outcome.

3. **Ask the founder the dwell question**, because step 1 and 2 cannot answer it: *at 0.30
   m/s the pad is on any given spot for 0.20 s — is that enough for real soil?* This is
   entangled with the unresolved "with a solution" gap, which outranks the speed number
   anyway.

4. If it lands: append to `LEARNINGS.md` and `PAIN_JOURNAL.md`, update `HANDOVER.md`
   (2:34.9 → 2:27.5 as a **supersession**), re-run the three gates, and note that v2/v3/v4
   are untouched by a v5-only config change.

**On the config value: I did NOT change it.** `CleanConfig.stroke_feed` is still `0.20`. I
used the `--feed 0.30` CLI override so the shipped default and every committed baseline stay
exactly as they were. The change, if you want it after step 1, is one line at
`sim_poc/v5_clean.py:242`:

```python
stroke_feed: float = 0.20   ->   0.30
```

...and the ~30-line comment block above it documenting *why* 0.20 would need rewriting in
the same commit, since it currently argues explicitly for 0.20 over 0.30.

---

## Ledger

No fresh seeds consumed. Only seed **2100** was run, already spent as the V7.1 post-clamp
feed-sweep tuning block. **Next free block remains 2200+.** If you run the steps above they
would consume 2200–2203 (upper sweep), 2220–2235 (held-out), 2240–2249 (sabotage) — record
those by named phase in `CLAUDE.md` if so.

## Files touched

None. No source file, no stats file, no sweep file was modified. `git status` is as I found
it (the pre-existing V7.4 modification to `v5_clean.py`, plus the new `.claude/` directory).
Archive written to `_archive/stats_2026-08-12_pre_feed030/`.
