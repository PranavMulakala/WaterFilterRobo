# Does the peak force in `stats_v5_clean.json` still reproduce?

**Short answer: yes — exactly, to all 16 significant digits. The number in the file is
correct. What is wrong is the README, which quotes two different, older peak-force figures
in the customer-facing summary. That is almost certainly what looked off.**

Committed value: `f_max = 23.925980963125905` N (published as **23.9 N**, point mode, full
coverage, seeds 900–907).

---

## Plan

The skill's order of operations, applied literally:

1. Run the three gates first — they write nothing, and a gate that has silently started
   failing means the bug is older and wider than the thing I came to look at.
2. Establish **provenance** before running anything: when was the stats file last written,
   and has anything that could move it changed since?
3. Archive the stats files before touching anything, because any bare `--eval` overwrites a
   committed baseline.
4. Reproduce the number by the cheapest route that cannot overwrite the baseline.
5. Give the reproduction a **control** — don't just re-run and nod at a matching number.

---

## 1. Gates — all three pass

```
cd sim_poc
../venv/bin/python v5_check_scene.py      PASS  (V5-A SCENE CHECK: ALL PASS)
../venv/bin/python v5_check_spec.py       PASS  (CELL_SPEC CHECK: ALL 50 VALUES MATCH)
../venv/bin/python v5_reach.py --indexed  PASS  (every vertical face + top 100% in the 30° cone)
```

One WARN in the spec gate, documented and expected: *"worst-case tool speed bound 6.95 m/s
at the home pose … this bound sums all 7 joints slewing at once, so it is loose by design."*

---

## 2. Provenance — the file is one commit behind the code, and that is the first thing worth knowing

```
stats_v5_clean.json   last written at  407fd2f  (V7.2)
v5_clean.py           last modified at 5b6d786  (V7.3)  ← HEAD
```

So the committed baseline was **not** re-derived after the most recent change to the code
that produces it. That is exactly the shape of a stale number, and it is why the question is
a fair one.

What V7.3 actually changed in `v5_clean.py` (88 insertions):

- `verify()` gained `drive=True` — it now **drives** the arm to PARK and **drives** the
  turntable through the inspection angles instead of teleporting `d.qpos`.
- Two new primitives, `_goto` and `_index_to`, both of which call `_tcp_tick()`.
- `_index_to(..., nearest=True)` picks the nearest equivalent indexer angle.

**Why that cannot move this file:** the `--eval` path (`v5_clean.py`, ~line 2625) calls
`c.run(seed)` in a loop and **never calls `verify()`**. Forces are accumulated only inside
`Cell.run` via the `log=forces` argument threaded into `move_planned`, and `f_max` is
`float(f.max())` over that list. `verify()` contributes no force samples and no
`_tcp_tick()` calls to an eval row.

I also confirmed the **scene is untouched** since the baseline was written —
`git log 407fd2f..HEAD -- sim_poc/make_scene_v5.py ufactory_xarm7/refurb_scene_v5.xml` is
empty. A scene change is the thing that would genuinely move contact force (the free-body
keyframe trap moved peak force by 1 N once already), and there wasn't one.

That is an argument, not a measurement. So I measured.

---

## 3. What I actually ran

Archived first (`_archive/` is gitignored):

```bash
mkdir -p _archive/stats_2026-08-12_pre_check
cp sim_poc/stats*.json _archive/stats_2026-08-12_pre_check/
```

`v5_clean.py --run SEED` prints the full run row and **writes no file** — the three
`open(..., "w")` sites in the module are in `falsify()`, `sweep()` and the `--eval` branch,
none of which `--run` reaches. One unit is ~36.7 s wall. Because the force figure is
documented as seed-independent, a single unit is enough to test the aggregate — and testing
that claim is itself the control.

| run | source | `f_max` (N) |
|---|---|---|
| committed `stats_v5_clean.json` | — | **23.925980963125905** |
| `v5_clean.py --run 900` | working tree | **23.925980963125905** |
| `v5_clean.py --run 907` | working tree | **23.925980963125905** |
| `v5_clean.py --run 900` | **pristine HEAD**, isolated `git worktree` | **23.925980963125905** |

Every other force-adjacent field reproduces bit-for-bit as well, and the per-unit counters
multiply up to the committed aggregates exactly:

| field | per-unit run | committed (n=8) |
|---|---|---|
| `f_med` | 13.200530928402014 | — |
| `in_band` | 1.0 | 1.0 |
| `contact_frac` | 0.9951518010403972 | `contact_run` / `contact_planned` 0.9951518010403972 |
| `raster_planned` | 323 | 2584 = 323 × 8 ✓ |
| `raster_infeasible` | 17 | 136 = 17 × 8 ✓ |
| `tilt_mean` | 8.4640522875817 | `tilt_mean_deg` 8.4640522875817 |
| `tilt_zero_frac` | 0.3627450980392157 | `exact_normal_frac` 0.3627450980392157 |
| `tcp_speed_max` | 1.0054303493881895 m/s | `tcp_speed_max_mms` 1005.4303493881895 |
| `joint_speed_max` | 2.4609641242715665 | 2.4609641242715665 |

### The control, and what it proved

Seed 900 is `truth: easy` with 13 soil patches; seed 907 is `truth: medium` with 11. Two
different units — and **every force, tilt, raster and speed field is identical to the last
digit**. Only `truth`, `soil0` and `cleaned` differ.

That is the repo's documented open-loop, seed-independent property, confirmed by measurement
rather than quoted. It has a consequence worth stating plainly:

> **`f_max` is an n = 1 quantity.** The `"n": 8` in the file governs coverage and missed
> spots. The force number carries exactly as much evidence as one unit, and re-running one
> seed is therefore a *complete* check of it, not a partial one.

`traps.md` flags this pattern ("identical numbers are not always a bug — but always check").
I checked: here it is correct, and it is the reason the cheap check is sufficient.

### The one command I did **not** run

Per the time-box:

```bash
cd sim_poc && ../venv/bin/python v5_clean.py --eval 8      # --seed0 defaults to 900
```

That is the command that fully re-derives the file — and it **overwrites**
`stats_v5_clean.json`. Expected result: byte-identical to the committed file (100% coverage,
0 missed of 129, `f_max` 23.925980963125905). Cost ≈ 5 min wall (8 × ~36.7 s). I'd archive
first and `git diff -- sim_poc/stats_v5_clean.json` afterwards to confirm it came back clean.

---

## 4. So why does it look off? Three stale copies of this number are still live

The stats file is right. The **documentation disagrees with it**, and one of the disagreeing
places is the README:

| location | says | status |
|---|---|---|
| `README.md:18` | peak **34.5 N** | pre-V6 / Gate-1 era figure |
| `README.md:105` | peak **32.9 N** | **pre-clamp**, superseded at 837a5cd |
| `sim_poc/v5_check_scene.py:228` | prints *"it peaks at 34.5 N"* | stale hardcoded string, **printed on every gate run** |
| `sim_poc/trade_study.py:335` | `wipe_n = 32.15` | pre-clamp; feeds a live risk figure |
| `meetings/anirudh_feedback_2026-08-08.md:39` | 32.9 N | dated meeting record — arguably correct to leave as history |

Meanwhile `CLAUDE.md`, `HANDOVER.md:13`, `HANDOVER.md:108` and the skill's own
`gates-and-baselines.md` all correctly carry **23.9 / 23.93 N**.

The history is legitimate — peak force really did fall 32.94 → 23.93 N when the arm's
published speed limits were adopted (837a5cd), because slower approaches land more gently.
The README simply never got updated. If the number was inspected next to the README, it
would look wrong by ~9 N.

There is a second-order oddity that may also have contributed: the **shipping** mode
(continuous stroke) peaks *lower* than the point raster — 22.6 N vs 23.9 N — which is
counterintuitive if you expect continuous sweeping to be harsher. It is real and explained:
the peak lives in the **seat** at the start of each run, not in the sweep, and
`stroke_seat_scale` approaches contact at 0.20× the sweep rate.

---

## 5. Concerns

**a) Concurrent session, and it moved the file underneath me.** `sim_poc/v5_clean.py` was
clean at the start of this session (`git status` showed only `?? .claude/`) and is now
` M`. Another session is mid-implementation of a **V7.4 servo-tracking metric**
(`stroke_servo_metric`, `_cmd_pad_pos`, a fourth `MjData` named `self.fk`). In its current
state that code is **incomplete**:

- `self._path_dev(...)` is **called at line 1502 but never defined** anywhere in the file.
- `tcp_now` is **referenced at line 1520**, but its only assignment
  (`tcp_now = d.geom_xpos[self.pad_face]`) was deleted with the inline block it replaced.

Both are inside `stroke_run`, so they affect `--stroke` only and cannot touch point mode.
I have **not** touched, stashed, reverted or committed that work — flagging it for whoever
owns it, since a mid-refactor tree is the expected explanation. **This is also why I re-ran
seed 900 against a pristine HEAD worktree**: with the tree changing under me, a working-tree
run alone would not have supported an attribution to HEAD. The worktree was removed
afterwards; the remaining `scratchpad/wt` worktree belongs to the other session and I left
it alone.

**b) A retracted figure is still live in the README.** Separate from force, but the same
class of problem and higher stakes: `README.md:104` still advertises *"V6 TARGETED CLEAN
(opt-in) … 0/24 residue on fresh units, sabotage caught 15/15 … full cycle 2:33"*, and
`README.md:58` says *"true 1× (2:33 cycle)"*. Per `HANDOVER.md`'s RETRACTIONS section that
mode is **WITHDRAWN** — it failed its own 0/24 residue bar under the clamp (seed 1844 left
residue and failed verify; one unit hit 98.67 N) — and **2:33 is RETRACTED outright**. The
retraction was recorded in HANDOVER but never propagated to the README.

**c) `trade_study.py` still prices risk off the pre-clamp force.** `wipe_n = 32.15` drives
the YAM payload-utilisation figure ("82% of a YAM Ultra's rating before the tool"). At the
current ~22–24 N that becomes roughly 57–62%, which *weakens* one of the arguments against
option D. It does not change the outcome — the arm is final (xArm7, `DECISIONS.md`) and the
study's headline is that arm count is moot at the expected volume — but it is a superseded
number inside a live decision artifact.

**d) `f_max` is n = 1 and the file does not say so.** Nothing is wrong with the value; the
risk is that `"n": 8` sitting next to it invites quoting the force as an 8-unit spread. The
repo already knows this (`report()` prints the warning); the JSON does not carry it.

---

## 6. What I did not change

- No stats file was written. `git diff -- sim_poc/stats*.json` is **empty**.
- No fresh seeds were burned. 900 and 907 are inside the already-spent published 900–907
  block, so the ledger is unchanged and no held-out range was consumed.
- The other session's uncommitted work is untouched.

---

## Recommendation

1. **No action on `stats_v5_clean.json`.** The peak force reproduces exactly at HEAD,
   verified three ways including against a pristine checkout. Keep quoting **23.9 N**.
2. **Fix `README.md`** — it is the customer-facing doc and it is the likely source of the
   impression. Three edits: peak force at line 18 (34.5 → 23.9 N) and line 105
   (32.9 → 23.9 N), and remove or mark-as-withdrawn the targeted-clean row at line 104 plus
   the 2:33 reference at line 58.
3. **Fix the stale string in `v5_check_scene.py:228`.** A gate that prints "it peaks at
   34.5 N" on every run actively teaches the wrong figure to the next person who reads it.
4. **Decide on `trade_study.py:335`.** Either update `wipe_n` to the current measured value
   and re-run the study, or label it explicitly as the pre-clamp figure. Leaving an untagged
   superseded number in a doc whose stated discipline is that every number carries a source
   tag is the worst of the three options.
5. **Optional but cheap:** when the point baseline is next legitimately re-run, consider
   adding an `f_max_n: 1` (or a note field) so the seed-independence caveat travels with the
   artifact rather than only with `report()`'s console output.
6. If you want the belt-and-braces confirmation, run `v5_clean.py --eval 8` (≈5 min) after
   archiving, and confirm `git diff` on the stats file comes back empty. I expect it to.

None of the above is a retraction: the published 23.9 N is correct and unchanged. Items 2–4
are stale *copies* of a number that was already corrected, not a number that needs
correcting.
