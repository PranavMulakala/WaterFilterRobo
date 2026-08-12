---
name: refurb-cell-discipline
description: Measurement and validation discipline for the DrinkPrime refurb-cell MuJoCo simulation in this repo. Use this whenever you are about to change the simulation, run an eval, sweep a parameter, build or read a metric, pick a seed, or quote a cycle time / coverage / force / accuracy number — and before trusting any figure you find in the docs. Use it even when the request sounds like simple tuning ("make it faster", "raise the feed rate", "why is this number off"), because the recurring failure mode in this repo is not a broken robot, it is a measurement that was quietly wrong. Also use it before claiming anything got better.
---

# Refurb cell — how to change this thing without publishing a false number

## The one idea

Every number in this repo is a claim someone will act on. A founder is being asked for
$20–30K on the strength of them. The repo's whole value is that its numbers are true, and
the honest ones have sometimes been unflattering — the arm-count study concluded the
question was moot, a cleaning mode was withdrawn, a quoted cycle time was retracted.

Almost every serious defect found here has been a **measurement that was quietly wrong**,
not a robot that was broken. The arm ran at 3× its rated speed for three phases of work.
A verification pass was recorded as costing zero seconds because it teleported. A coverage
metric measured the wrong reference frame and read 20 mm when the true answer was 3 mm.
None of those were caught by a test. Two were caught by a human watching a video.

So the habits below are not ceremony. Each one exists because its absence cost a day.

## The discipline applies to the number, not to the work

This is the failure mode of taking the section above too seriously, and it is a real one:
reading all this and then declining to build, hedging the deliverable, or handing back a
list of caveats instead of a result. That is not rigour, it is the appearance of rigour.
The project is not asking anyone to be cautious — it is asking for figures that survive
contact with a founder, and you cannot produce one of those without doing the work.

The distinction that matters: **build the thing, then be exact about what you measured.**
An honest "here is the change, and here is the one number it moved, and here is the number
I could not close" is worth far more than a refusal. The repo's best moments look like
that — the arm-count study shipped a conclusion that made its own subject moot, and the
targeted-cleaning mode was built, measured, and *then* withdrawn on evidence. Both required
building first.

If you genuinely cannot validate something in the time available, deliver it with the gap
named and labelled — an `UNBACKED` step is a legitimate artifact here and there is prior
art for it. Silence about the gap is the only unacceptable option.

## Before you change anything

**1. Run the three gates.** They write nothing, so they are always safe:

```bash
cd sim_poc
../venv/bin/python v5_check_scene.py      # ~25 structural assertions
../venv/bin/python v5_check_spec.py       # 50 CELL_SPEC values + the arm speed limits
../venv/bin/python v5_reach.py --indexed  # reachability with the rotary indexer
```

A gate that used to pass can start failing without anyone noticing. On 2026-08-09 the
scene gate had been failing at HEAD for two commits — a free body was spawning inside the
arm riser on every reset, perturbing every cleaning run — and the failure had simply not
been read. **If a gate fails, stop and find out why before changing anything.** The bug is
usually older and wider than the thing you came to do.

**2. Confirm the baseline you are about to move actually reproduces.** If it does not, you
have found a second bug and you cannot attribute anything to your change until it is
resolved. Exact commands and current published values: `references/gates-and-baselines.md`.

**3. Archive the stats files first.** Any bare `--eval` overwrites a committed baseline —
including `--eval 2`. These files are the record the project is measured against.

```bash
mkdir -p ../_archive/stats_$(date +%F)_pre_change
cp stats*.json ../_archive/stats_$(date +%F)_pre_change/
```

## Choosing seeds

The ledger lives in `CLAUDE.md`. Read it, take the next free block, and **write back what
you spent, by named phase** — a bare "start at N" invites a collision with a reserved range.

Two rules that are easy to get wrong:

- **A seed you have LOOKED AT is spent.** Not just one you wrote a stats file from. If you
  rendered it, printed its ground truth, or watched it frame by frame, it can never be a
  held-out set again. One seed was burned this way by a single probe that printed
  `truth: hard` into a transcript before a blind protocol existed.
- **Tuning on a range and reporting that range is not a result.** Sweep on one block,
  confirm on a fresh one. The repo has caught over-claims this way in four consecutive
  sessions.

## Building or reading a metric

This is where the most time has been lost, so it gets the most space.

**Run a new metric where you already know the answer.** A metric is a new experiment and
deserves a control. A path-tracking metric here read 40 mm, then 20 mm, then 28 mm across
three attempts — each plausible, each wrong for a different reason (distance to the wrong
knot; decomposed about the wrong knot's normal; and then reporting the active contact
flange's *designed* compression as "error"). What finally settled it was running the same
metric through point mode, where the answer had to be ~0. It read 0.02 mm. That proved the
metric could tell the two modes apart, which made the stroke number believable.

**Measure motion from velocity state, never from position differences.** This cell teleports
several times per cycle — `verify()` parks the arm, `couple()` snaps a weld, the membrane
station materialises a cap. A position difference across a teleport is a discontinuity, not
a speed. Differencing pad positions once reported **51 m/s**. Use `mj_objectVelocity` and
`d.qvel`, which a `qpos` teleport does not touch.

**Decompose before you report.** A single number that mixes two physical quantities will
mislead you about which constraint you are breaking. Departure *across* a surface is a
coverage question; departure *along* its normal is the compliance flange doing its job.
Reported together they made a working spring look like a defect.

**A teleport is a measurement hole.** Anything the sim does instantaneously is work the
real cell still has to do, and it will appear in no total. `verify()` cost "zero simulated
seconds" for months purely because it teleported the arm and the turntable. It really costs
10 s. When you see a direct `d.qpos[...] = ` outside a reset path, it is either a fixture
action that must be labelled as such, or a motion that should be driven.

## Sweeping a parameter and choosing a value

**Do not ship next to a cliff.** The convention here is roughly **1.18× margin or better**
between the value you ship and the nearest measured failure. This has been applied against
its own convenience more than once: `step_frac` 1.30 was faster, passed 16 units, and was
declined at 8% margin; a following-error value that satisfied a published limit was
declined at 7% because the cliff beyond it was a 89.5 N contact.

Rare-event failures deserve extra suspicion. A coverage miss only happens when soil lands
in a gap, so a 16-unit pass does not prove a 2.4 mm band is closed — it proves it is rarely
hit.

**When the control layer changes, every sweep whose *conclusion* depended on the old
dynamics is stale — not just the tests guarding your change.** This has now happened twice.
Adopting the arm's published speed limits silently removed the mechanism behind a coverage
cliff, so a feed rate that had been pinned for safety could be doubled; the same change
also moved a *row-pitch* cliff the other way, tighter. One fix moved two cliffs in opposite
directions. Re-running both sweeps cost under an hour and was worth 35 s/unit.

**A dead lever is a finding worth recording.** `drive_rate` was swept and set in the belief
it mattered; it produces identical time at 12/16/20/24 rad/s because the actuator limits the
spin, not the command. Write those down so nobody re-tunes them.

## Reporting a result

- **Report the margin, not just the rate.** A pass/fail rate once hid a systemic defect —
  every trial was jamming, only the tail failed.
- **Know which figures actually vary.** The cleaning trajectory is open-loop and
  seed-independent: force, tilt and raster figures are effectively **n = 1**, not n = 16.
  Only coverage and missed spots vary with the seed. Do not quote the others as a spread.
- **Lead with the asymmetric error.** Missed-hard before accuracy; false-verify beside
  sabotage-caught. A check that cannot fail is not evidence, and a sabotage arm on its own
  is exactly that.
- **If a number you are changing was shown to anyone, flag it as a retraction rather than
  silently updating it.** Say plainly whether the old figure was wrong, or merely
  superseded, or produced by a configuration that no longer meets its own bar — those are
  three different statements. `HANDOVER.md` has a RETRACTIONS section for this.

## After the change

Re-run the gates and the baselines that could have moved, and say plainly which ones are
byte-identical and which moved. Then:

- Append to `LEARNINGS.md` — plain English, ≤15 lines, written for two software engineers
  learning robotics: what we built, the concept behind it, why it matters for the real
  robot. No unexplained jargon.
- Append to `PAIN_JOURNAL.md` — what went wrong, time lost, what would have prevented it.
- Commit with the evidence in the message, and push. The repo is the source of truth.

## What the honest labels are

These travel with any demo or quoted figure; do not drop them to make a claim cleaner:

1. Easy/Medium/Hard **names** are DrinkPrime's; the **boundaries are ours**, still unconfirmed.
2. Cleaning removes soil on **contact, not dwell** — the sim cannot see a rub being too brief.
3. No cream, detergent or chemistry is simulated. v5 CLEAN is a **dry wipe of the cabinet
   exterior**, and the funding bar says *"cleans the filter with a solution"*. That gap is
   unresolved and it outranks any speed number.
4. The membrane leak result is a **measured image of a modelled outcome** — torque sets
   `seal_holds`, which sets the bubbles. A damaged O-ring at full torque would pass.
5. The HARD route is a **software decision**; no motion delivers a unit anywhere (0/6).
6. Triage and the dip are **not** free: see the teleport note above before quoting a cycle.

## The source documents

The 13 DrinkPrime PDFs (transcribed as data in `sim_poc/dp_process.py`) are the only ground
truth about their process. **Before adding a process step, check whether any of them
describes it.** If the step is ours, that is allowed — but it must be labelled ours every
single time it is reported, the way the Easy/Medium/Hard boundaries are. A step that quietly
acquires their authority is the worst outcome available here.

`CLAUDE.md` carries the other two rules (don't fix the source typos; never text-extract the
vector QC flow charts). Both are load-bearing; re-read them before touching `dp_process.py`.

## Reference files

- `references/gates-and-baselines.md` — exact commands, what each writes, and the current
  published value for every protected baseline. Read before running any eval.
- `references/traps.md` — the recurring physics and simulation gotchas, each with the
  evidence that produced it. Read when something behaves impossibly.
