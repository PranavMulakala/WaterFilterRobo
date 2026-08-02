# Water Filter Robot — Simulation POC

**Can a robot arm install a water-filter cartridge?** This repo answers that in
simulation, before we spend anything on hardware.

A simulated robot arm picks up a filter cartridge that has been dropped in a tray at a
random position and a random rotation, works out where it is, carries it to the
housing, lines up the bayonet tabs, inserts it through a 3 mm gap, and twists it 55°
to lock. **It currently succeeds on 200 out of 200 randomized attempts.**

> **New here? Read [HOW_IT_WORKS.md](HOW_IT_WORKS.md).** It explains the whole thing in
> plain English with no robotics background assumed. This README is the summary and
> the instructions for running it.

---

## The demo

**[media/cartridge_cell_v2.mp4](media/cartridge_cell_v2.mp4)** — three full runs with a
wrist-camera view and live telemetry. This is the file to send to people.

---

## Where the project stands

| | |
|---|---|
| **Success rate** | **100%** (200/200 randomized trials) |
| Previously | 88% on its own test seeds, 72% on unseen ones |
| Seating accuracy | 1.7 mm average |
| Cycle time | ~23 seconds |
| Physics engine | MuJoCo 3.11.0, pinned |
| Robot | UFACTORY xArm7 (a real, purchasable ~$11K arm) |
| Status | **Pre-hardware.** Simulation only. No robot has been bought. |

Full breakdown, including what was wrong and how each fix was verified:
**[RESULTS.md](RESULTS.md)**.

---

## Quick start

Needs Python 3.10 or newer. Three commands:

```bash
git clone git@github.com:PranavMulakala/WaterFilterRobo.git
cd WaterFilterRobo && ./setup.sh
cd sim_poc && ../venv/bin/python sim_poc2.py --eval 25
```

That last command runs 25 complete randomized attempts and prints the success rate.
It takes about a minute.

> Don't run a bare `python3 -m venv venv`. On a stock Mac `python3` is Python 3.9,
> which has no MuJoCo build available, and the failure message points at something
> unrelated. `setup.sh` finds a suitable interpreter and says so plainly if it can't.

### Other things you can run

```bash
# watch it live in an interactive 3D viewer — drag to orbit
../venv/bin/python -m mujoco.viewer --mjcf ufactory_xarm7/cartridge_scene_v2.xml

# re-render one attempt as a video (output index, seed, speed)
../venv/bin/python sim_poc2.py --render 1 12 1

# rebuild the title/results cards and stitch the demo reel
../venv/bin/python sim_poc2.py --cards
../venv/bin/python sim_poc2.py --concat
```

---

## What's in here

| File | What it is |
|---|---|
| [HOW_IT_WORKS.md](HOW_IT_WORKS.md) | **Start here.** Plain-English explanation, no jargon |
| [RESULTS.md](RESULTS.md) | The numbers, the bug that was found, and how it was verified |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical detail: control loop, geometry, phase table |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | Business context — the venture, the people, the economics |
| [PAIN_JOURNAL.md](PAIN_JOURNAL.md) | Every gotcha hit, with time lost. Deliberate product research |
| `sim_poc/sim_poc2.py` | The whole system — perception, planning, control, evaluation |
| `sim_poc/ufactory_xarm7/` | Robot model and the cartridge/socket scene |
| `sim_poc/stats.json` | Results of the last evaluation run |
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

1. **DrinkPrime founder call** — labour costs, willingness to pay, whether they'd ship
   us a real cartridge. This is the gating item; everything else waits on it.
2. **Log demonstrations in LeRobot format** — the bridge from this scripted controller
   to a learned policy (π0.5 / OpenPi), which is what would generalise to parts we
   haven't modelled.
3. **Domain randomization** — vary mass, friction and table height, then re-measure.
   A single fixed simulation is the easiest thing in the world to overfit to.
4. **Swap in real cartridge geometry** once DrinkPrime confirms the SKU.

Hardware purchase stays **on hold** until customer interest is confirmed.
