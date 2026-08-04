# Water Filter Robot — Simulation POC

**Can a robot arm refurbish a water purifier?** This repo answers that in simulation,
before we spend anything on hardware.

**The current build (v5) works on the whole purifier**, modelled on DrinkPrime's own 13
work instructions, which landed on 2026-08-04. A used unit is placed on a rotary indexer
and the arm works around it in three stations:

- **TRIAGE** — a fixed camera grades the unit Easy / Medium / Hard from its pixels.
  **97.5%** on 120 fresh units, and **0.0% missed-hard** — nothing needing deep work has
  ever been sent down the fast path.
- **CLEAN** — the arm picks a wiping pad off a tool changer and rasters all five exposed
  faces. **94.6%** of soil removed on held-out units.
- **MEMBRANE ASSEMBLY** — not built yet; the earlier cartridge cycle is the stand-in.

**Before that (v4)** the same ideas ran on a single cartridge: extract it, grade it from
an image, and clean / lightly-wash / replace accordingly. Every route completes **100%**
of the time with a **0.0% false-clean rate**. That loop still runs and is still the best
end-to-end demo — see the videos below.

> **New here? Read [HOW_IT_WORKS.md](HOW_IT_WORKS.md).** It explains the whole thing in
> plain English with no robotics background assumed. This README is the summary and
> the instructions for running it.

---

## The demos

**[media/refurb_cell_v4.mp4](media/refurb_cell_v4.mp4)** — **the one to send people.**
All three routes back to back with the live camera verdict on screen (~81 s). Trial
footage runs at a clearly-labelled 1.8× so three real cycles fit; the stats cards are
not sped up.

**[media/refurb_cell_v4_full.mp4](media/refurb_cell_v4_full.mp4)** — the same thing
uncompressed and unedited (2:16), for anyone who wants to see true cycle times.

**[media/refurb_cell_v3.mp4](media/refurb_cell_v3.mp4)** — the earlier swap-only cycle.
**[media/cartridge_cell_v2.mp4](media/cartridge_cell_v2.mp4)** — insertion alone.

> **There is no v5 video yet.** That is phase V5-G and it is not started — no renderer
> exists for any v5 station. The v4 cut above is still the thing to send people.

---

## Where the project stands

| | |
|---|---|
| **v5 TRIAGE — grade a whole unit** | **97.5%** on 120 fresh units; **missed-hard 0.0%**, false-easy 2.5% |
| **v5 CLEAN — wipe five faces** | **94.6%** coverage held out; **force band not closed** (88.1%) |
| **v5 MEMBRANE / routing / video** | not started |
| **Refurb decision loop (v4)** | routing **100%**, end-to-end **86.7%**, false-clean **0.0%** (60 held-out) |
| **Refurb swap cycle (v3)** | **100%** (125/125 full cycles) |
| **Insertion cycle (v2)** | **100%** (200/200 trials) |
| Insertion was previously | 88% on its own test seeds, 72% on unseen ones |
| Seating accuracy | 1.7 mm (insert) / 2.0 mm (swap) |
| Cycle time | ~23 s insert, ~33 s full swap, ~20 s per cleaned unit |
| Physics engine | MuJoCo 3.11.0, pinned |
| Robot | UFACTORY xArm7 (a real, purchasable ~$11K arm) |
| Status | **Pre-hardware.** Simulation only. No robot has been bought. |

Full breakdowns: **[V5_PLAN.md](V5_PLAN.md)** (current work — v5 plan and every v5
result), **[RESULTS_V4.md](RESULTS_V4.md)** (the decision loop),
**[RESULTS_V3.md](RESULTS_V3.md)** (swap cycle) and **[RESULTS.md](RESULTS.md)**
(insertion). **[CELL_SPEC.md](CELL_SPEC.md)** is what you would build a real cell from.

> **Two numbers above carry caveats that must travel with them.** The class names
> Easy / Medium / Hard are DrinkPrime's; **the boundaries between them are ours**, because
> no document in their set defines them. And v5 cleaning is done on *coverage* but **not
> on force** — 88.1% of contact samples fall in band, with a peak beyond where our contact
> model is validated. Neither is a finished result.

> **Scope note.** The v2/v3/v4 cartridge work is a *generic* manipulation primitive. Their
> corpus contains **no teardown or disassembly instruction at all**, so the extraction
> motion those versions are built on has no documented counterpart in DrinkPrime's
> process. v5 is the version modelled on their actual stages.

---

## Quick start

Needs Python 3.10 or newer. Three commands:

```bash
git clone git@github.com:PranavMulakala/WaterFilterRobo.git
cd WaterFilterRobo && ./setup.sh
cd sim_poc && ../venv/bin/python sim_poc4.py --eval 60 --seed0 200
```

That runs 60 complete randomized refurb cycles on held-out seeds and prints inspection
accuracy, the false-clean rate, routing compliance and end-to-end success. Takes a few
minutes. `sim_poc3.py --eval 25` is the swap cycle alone; `sim_poc2.py --eval 25` the
insertion alone.

For the **current (v5)** stations:

```bash
../venv/bin/python v5_triage.py --eval 120        # grade 120 units  -> 97.5%
../venv/bin/python v5_clean.py  --eval 8          # clean 8 units    -> 94.6%
```

> **Every eval overwrites the `stats*.json` it belongs to, including a 2-seed smoke
> test.** Those files are the recorded baselines the project is measured against, and the
> default seed of each command is the one that reproduces the published number. Change the
> seed range and you overwrite a baseline with something else. Check
> `git diff -- sim_poc/stats*.json` before you finish.

> Don't run a bare `python3 -m venv venv`. On a stock Mac `python3` is Python 3.9,
> which has no MuJoCo build available, and the failure message points at something
> unrelated. `setup.sh` finds a suitable interpreter and says so plainly if it can't.

### Other things you can run

```bash
# watch it live in an interactive 3D viewer — drag to orbit
../venv/bin/python -m mujoco.viewer --mjcf ufactory_xarm7/refurb_scene_v5.xml    # current
../venv/bin/python -m mujoco.viewer --mjcf ufactory_xarm7/cartridge_scene_v3.xml # the v3 cell

# re-render one swap cycle as a video (output index, seed, speed)
../venv/bin/python sim_poc3.py --render 1 3 1

# rebuild the title/results cards and stitch the demo reel
../venv/bin/python sim_poc3.py --cards      # (or sim_poc2.py for the insert-only reel)
../venv/bin/python sim_poc3.py --concat
```

---

## What's in here

| File | What it is |
|---|---|
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | **Start here.** Plain-English explanation, no jargon |
| [RESULTS.md](RESULTS.md) | The numbers, the bug that was found, and how it was verified |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical detail: control loop, geometry, phase table |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Business context — the venture, the people, the economics |
| [PITCH_NOTES.md](PITCH_NOTES.md) | Customer-facing framing and the open questions for the founder |
| [LEARNINGS.md](LEARNINGS.md) | **The robotics concepts, in plain English.** Written for us, not for customers |
| [PAIN_JOURNAL.md](PAIN_JOURNAL.md) | Every gotcha hit, with time lost. Deliberate product research |
| [V5_PLAN.md](V5_PLAN.md) | **Current work** — the v5 plan and every v5 result |
| [CELL_SPEC.md](CELL_SPEC.md) | **What you would build the real cell from** — frames, stations, tolerances, tooling |
| [CLAUDE.md](CLAUDE.md) | Working rules for this repo, and the current state at the top |
| [RESULTS_V4.md](RESULTS_V4.md) | The v4 decision loop, and what limited it |
| [RESULTS_V3.md](RESULTS_V3.md) | The swap-cycle numbers, and why the untwist slips |
| `sim_poc/v5_triage.py` | **v5 station 1** — grade a whole unit from a fixed camera |
| `sim_poc/v5_clean.py` | **v5 station 2** — plan-then-execute wipe of all five faces |
| `sim_poc/make_scene_v5.py` | Generates the v5 scene from a fixed seed. **Edit this, never the XML** |
| `sim_poc/v5_reach.py` | Reachability study — can the arm get to every face at all |
| `sim_poc/v5_check_scene.py`, `v5_check_spec.py` | Gates: the scene is sane, and CELL_SPEC still matches the model |
| `sim_poc/dp_process.py` | DrinkPrime's real 10-stage process, as data. No side effects |
| `docs/drinkprime/` | Their 13 source PDFs. **Read its README first** — the QC pages are vector art and must be rendered, not text-extracted |
| `sim_poc/sim_poc4.py` | **v4 refurb loop** — inspection CV, routing, cleaning station |
| `sim_poc/sim_poc3.py` | **v3 refurb swap cycle** — extends v2 by import, adds extract + discard |
| `sim_poc/sim_poc2.py` | The insertion system — perception, planning, control, evaluation |
| `sim_poc/ufactory_xarm7/` | Robot model; `cartridge_scene_v3.xml` adds the spent cartridge + bin |
| `sim_poc/stats*.json` | The recorded baselines. Overwritten by any eval — treat as protected |
| `setup.sh`, `requirements.txt` | Environment setup, with versions pinned on purpose |

---

## What this proves, and what it doesn't

**It does prove** the task is mechanically achievable by an off-the-shelf arm, that the
strategy is sound, that we understand where the difficulty actually lies, and that we
can show a customer a working demo without buying anything first.

**It does not prove** that real cartridge tolerances match the model, that a real
camera localises the part this well, that real friction behaves like simulated
friction, or that the cycle time survives a real production line. Sim-to-real transfer
reliably costs more than expected.

Honest framing: **this de-risks the approach, not the deployment.**

---

## Next steps

1. **V5-D — prove the cleaning check can fail.** Re-inspect after cleaning, then run it
   with the cleaning deliberately disabled and confirm every unit is caught. v4's first
   attempt at this caught only 2 of 5, because verification used one camera view where
   the main inspection used two. Assume the same class of bug until it fails every part.
2. **V5-E membrane assembly**, **V5-F route wiring**, **V5-G video** — in that order.
3. **Close the V5-C force band.** Coverage is done; force is not.

**Blocked on DrinkPrime, in priority order:** what defines Easy / Medium / Hard (must be
asked open-ended — no document in their set defines it, and if their operators grade by
*feel* then camera-only inspection is the wrong architecture); QC Annexures 1–13; whether
the final leak test is 45 or 80 PSI (their documents say both, and it is a safety
question); CAD for the membrane bowl, cap and O-ring; and the cabinet's outer dimensions
and mass.

**Done since this list was last written:** the process documents landed and are
transcribed; LeRobot v2.1 export is written (structurally validated, *not* round-tripped
through the real library); and the domain-randomization sweep produced the ±2.5 mm
fixture-tolerance envelope in RESULTS_V4.

The founder has indicated **$20–30K of funding for robot arms** if the refurb process
can be credibly simulated, with an explicit bar of image inspection plus a cleaning step
— which is why refurb fidelity outranks polish on the insertion cycle. **That indication
is verbal, not in writing**, and hardware purchase stays on hold until it is.
