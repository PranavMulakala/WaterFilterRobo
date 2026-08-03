# Water Filter Robot — Simulation POC

**Can a robot arm refurbish a water purifier?** This repo answers that in simulation,
before we spend anything on hardware.

The headline task is the **refurbishment decision loop**. A used unit arrives with a
filter cartridge twist-locked inside it. The robot untwists it out of the bayonet
mount, holds it up to a camera, and — from the actual image — decides what it needs:

- **clean** → put it straight back in
- **lightly scaled** → wash it, re-check it with the same camera, put it back
- **damaged** → bin it and install a fresh one

Every route completes **100%** of the time, with a **0.0% false-clean rate** — it never
passes a part that needs work as clean.

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

---

## Where the project stands

| | |
|---|---|
| **Refurb decision loop (v4)** | routing **100%**, end-to-end **86.7%**, false-clean **0.0%** (60 held-out) |
| **Refurb swap cycle (v3)** | **100%** (125/125 full cycles) |
| **Insertion cycle (v2)** | **100%** (200/200 trials) |
| Insertion was previously | 88% on its own test seeds, 72% on unseen ones |
| Seating accuracy | 1.7 mm (insert) / 2.0 mm (swap) |
| Cycle time | ~23 s insert, ~33 s full swap |
| Physics engine | MuJoCo 3.11.0, pinned |
| Robot | UFACTORY xArm7 (a real, purchasable ~$11K arm) |
| Status | **Pre-hardware.** Simulation only. No robot has been bought. |

Full breakdowns: **[RESULTS_V3.md](RESULTS_V3.md)** (swap cycle) and
**[RESULTS.md](RESULTS.md)** (insertion, including the bug that was found and how each
fix was verified).

> **Scope note.** v3 is the *generic* swap cycle, built while we wait for DrinkPrime's
> real refurb process video, tech documents and possibly a physical unit. Actual
> refurbishment plausibly also involves descaling, filter-media replacement and gasket
> inspection — none of which are modelled yet, because we don't know them. That
> material will tell us whether the swap cycle is the right demo or the first scene of
> it.

---

## Quick start

Needs Python 3.10 or newer. Three commands:

```bash
git clone git@github.com:PranavMulakala/WaterFilterRobo.git
cd WaterFilterRobo && ./setup.sh
cd sim_poc && ../venv/bin/python sim_poc4.py --eval 30 --seed0 200
```

That runs 30 complete randomized refurb cycles on held-out seeds and prints inspection
accuracy, the false-clean rate, routing compliance and end-to-end success. Takes a few
minutes. `sim_poc3.py --eval 25` is the swap cycle alone; `sim_poc2.py --eval 25` the
insertion alone.

> Don't run a bare `python3 -m venv venv`. On a stock Mac `python3` is Python 3.9,
> which has no MuJoCo build available, and the failure message points at something
> unrelated. `setup.sh` finds a suitable interpreter and says so plainly if it can't.

### Other things you can run

```bash
# watch it live in an interactive 3D viewer — drag to orbit
../venv/bin/python -m mujoco.viewer --mjcf ufactory_xarm7/cartridge_scene_v3.xml

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
| [PITCH_NOTES.md](PITCH_NOTES.md) | Customer-facing framing, open questions for the founder, Ronch |
| [LEARNINGS.md](LEARNINGS.md) | **The robotics concepts, in plain English.** Written for us, not for customers |
| [PAIN_JOURNAL.md](PAIN_JOURNAL.md) | Every gotcha hit, with time lost. Deliberate product research |
| [RESULTS_V4.md](RESULTS_V4.md) | **Current numbers** — the decision loop, and what still limits it |
| [RESULTS_V3.md](RESULTS_V3.md) | The swap-cycle numbers, and why the untwist slips |
| `sim_poc/sim_poc4.py` | **v4 refurb loop** — inspection CV, routing, cleaning station |
| `sim_poc/sim_poc3.py` | **v3 refurb swap cycle** — extends v2 by import, adds extract + discard |
| `sim_poc/sim_poc2.py` | The insertion system — perception, planning, control, evaluation |
| `sim_poc/ufactory_xarm7/` | Robot model; `cartridge_scene_v3.xml` adds the spent cartridge + bin |
| `sim_poc/stats.json`, `stats_v3.json` | Results of the last insertion / swap evaluation |
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

1. **DrinkPrime's refurb process video + tech documents** (and possibly a physical
   unit) — the founder is shipping these. They define the REAL refurb steps, which
   decide whether this swap cycle is the right demo or just its first scene. Gating
   item; everything else waits on it.
2. **Log demonstrations in LeRobot format** — the bridge from this scripted controller
   to a learned policy (π0.5 / OpenPi), which is what would generalise to parts we
   haven't modelled.
3. **Domain randomization** — vary mass, friction and table height, then re-measure.
   A single fixed simulation is the easiest thing in the world to overfit to.
4. **Swap in real cartridge geometry** once DrinkPrime confirms the SKU.

The founder has indicated **$20–30K of funding for robot arms** if the refurb process
can be credibly simulated — which is why refurb fidelity now outranks polish on the
insertion cycle. Hardware purchase stays on hold until that is confirmed in writing.
