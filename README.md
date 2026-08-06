# Water Filter Robot — Simulation POC

**Can a robot arm refurbish a water purifier?** This repo answers that in simulation,
before we spend anything on hardware.

**The current build (v5) works on the whole purifier**, modelled on DrinkPrime's own
process documents — 13 files in total, 10 stage work instructions plus 3 QC flow-chart
pages — which landed on 2026-08-04. A used unit is placed on a rotary indexer
and the arm works around it in three stations:

- **TRIAGE** — a fixed camera grades the unit Easy / Medium / Hard from its pixels.
  **97.5%** on 120 fresh units. **Missed-hard is 0.0%** — no unit needing HARD-class work
  was ever graded below hard, and dents have no remedy in any of their ten stages, so
  that is the error with no recovery. **False-easy is 2.5%**: two MEDIUM units *were*
  graded easy and would have skipped the scratch-removal pass.
- **CLEAN** — the arm picks a wiping pad off a tool changer and rasters all five exposed
  faces. **100%** coverage on held-out units, **0** spots missed of 129, and every contact
  sample in the force band (peak **34.5 N**, inside the **45 N** the pad model is validated
  to). No cream, detergent or chemistry is simulated — what is verified is that the soil
  the camera could see is gone.
- **MEMBRANE ASSEMBLY** — Stage 10, their real named station: the threaded cap is driven
  multi-turn until it **stalls on torque** (median **9.40 turns** at 6.00 N·m), then the
  assembly is pressurised and dipped for a bubble check. **10/10** honest passes, **10/10**
  sabotaged units caught, **0** false passes. Their cap is threaded and spanner-tightened,
  *not* our v2/v3 bayonet, and the bowl/cap/O-ring geometry is a **placeholder** until CAD
  arrives.

Those three are wired together by a **routing** step that sends each unit down the route
its grade selects. On 28 held-out units, and these are four different questions:

| | |
|---|---|
| declared-trace conformance | **28/28** — the cell emitted the trace its own prediction selected |
| right route (grade == truth) | **26/28** — capped by triage |
| end-to-end (software) | **26/28** — right route, and every step its route *defines* succeeded |
| **fully backed** | **22/28** — …and no claimed action that nothing implements |

**Read the last row as the honest headline.** The 4-unit gap is the HARD route: it stops at
a **human scrap-approval gate**, and *nothing physically delivers the unit there* — it is a
software decision. Their chart forks HARD on rectification cost, we have no cost model, so
the cell refuses to make that call. **false-easy is 0/28.**

**Before that (v4)** the same ideas ran on a single cartridge: extract it, grade it from
an image, and clean / lightly-wash / replace accordingly. Every route completes **100%**
of the time with a **0.0% false-clean rate**. That loop still runs, and it is still worth
showing for one specific reason: **v4 dips the cartridge in a solution tank**, which is
closer to the funding bar's wording than v5's dry cabinet wipe. See the videos below.

> **New here? Read [HOW_IT_WORKS.md](HOW_IT_WORKS.md).** It explains the whole thing in
> plain English with no robotics background assumed. This README is the summary and
> the instructions for running it.

---

## The demos

**[media/v6_cell_realtime.mp4](media/v6_cell_realtime.mp4)** — **the V6 targeted cell at
true 1× (2:33 cycle)** — every frame carries a plain-English caption of what the arm is
doing. Same accuracy gates as v5, verified on 24 fresh units with zero residue.

**[media/v5_cell_realtime.mp4](media/v5_cell_realtime.mp4)** — **how long a unit actually
takes.** One complete MEDIUM cycle at **true 1×, no speed-up** — the clip's runtime *is* the
cycle time: **3 min 51 s** (clean 186.8 s, membrane + dip 44.1 s, triage/verify cost no
motion time). Rebuild with `v5_video.py --realtime`.

**[media/v5_cell_reel.mp4](media/v5_cell_reel.mp4)** — **the sped-up overview (2:24).**
All three routes end to end at a labelled **1.5×** (slow enough to dissect), then a stats
card, then a card listing everything that *isn't* real. **Read
[media/REEL_WALKTHROUGH.md](media/REEL_WALKTHROUGH.md) alongside it** — chapter times, what
happens at each station, and which parts the arm actually performs (it is two of them). **Each clip is a unit from the published eval set** — seeds
1700 / 1704 / 1702 are rows in `stats_v5_route.json`, so every number on screen can be
checked against the committed artifact. Rebuild with `v5_video.py --reel`.

**[media/v5_cell_medium.mp4](media/v5_cell_medium.mp4)** — the MEDIUM route alone, at a
labelled 4× — TRIAGE → CLEAN → VERIFY → MEMBRANE → DIP — with live workpiece metrics.

**[media/v5_cell_hard.mp4](media/v5_cell_hard.mp4)** — a HARD unit going to the
scrap-approval gate, which is where the cell deliberately stops.

**[media/refurb_cell_v4.mp4](media/refurb_cell_v4.mp4)** — **the v4 cartridge loop, still
worth showing** because it is the one that dips a part in **solution**. All three routes
back to back with the live camera verdict on screen (~81 s). Trial footage runs at a
clearly-labelled 1.8× so three real cycles fit; the stats cards are not sped up.

**[media/refurb_cell_v4_full.mp4](media/refurb_cell_v4_full.mp4)** — the same thing
uncompressed and unedited (2:16), for anyone who wants to see true cycle times.

**[media/refurb_cell_v3.mp4](media/refurb_cell_v3.mp4)** — the earlier swap-only cycle.
**[media/cartridge_cell_v2.mp4](media/cartridge_cell_v2.mp4)** — insertion alone.

> **Every station carries its own caveat printed on the frame**, because a video is where
> overstatement is easiest and hardest to catch: the triage class *names* are DrinkPrime's
> but the *boundaries* are ours; no detergent or chemistry is simulated; the dip's bubbles
> are **modelled from torque, not a fluid simulation**; the membrane geometry is a
> placeholder. Regenerate with `v5_video.py --render SEED`.

---

## Where the project stands

| | |
|---|---|
| **v5 TRIAGE — grade a whole unit** | **97.5%** on 120 fresh units; **missed-hard 0.0%**, false-easy 2.5% |
| **V6 TARGETED CLEAN (opt-in)** | wipes only where dirt was seen + camera-verified backstop: **0/24 residue on fresh units**, sabotage caught 15/15; clean ~75–120 s, **full cycle 2:33** |
| **v5 CLEAN — wipe five faces** | **100%** coverage held out (8/8), 0 missed of 129; force **100%** in band, peak **32.9 N** vs a **45 N** validity ceiling. **V6: 254.7 s → 186.8 s/unit (1.36×)** |
| **v5 VERIFY — prove the check can fail** | honest **10/10** verified with zero residue, **0/10** false verifies, sabotage caught **10/10** |
| **v5 MEMBRANE — Stage 10** | **arm really inserts the element 10/10** (aligned 0.30 mm median vs 1.5 mm clearance); cap stalls on torque, median **9.40 turns** @ 6.00 N·m; **10/10** honest pass, **10/10** sabotage caught, **0** false pass. **The cap is presented by a fixture, not fitted by the robot** |
| **v5 ROUTING — grade picks the route** | route-plan compliance **28/28**, right-route **26/28**, end-to-end **26/28**, false-easy **0/28** |
| **Refurb decision loop (v4)** | routing **100%**, end-to-end **86.7%**, false-clean **0.0%** (60 held-out) |
| **Refurb swap cycle (v3)** | **100%** (125/125 full cycles) |
| **Insertion cycle (v2)** | **100%** (200/200 trials) |
| Insertion was previously | 88% on its own test seeds, 72% on unseen ones |
| Seating accuracy | 1.7 mm (insert) / 2.0 mm (swap) |
| Cycle time (simulated, **not** a takt time) | ~23 s insert, ~33 s full swap, **~294 s** to clean one unit |
| Physics engine | MuJoCo 3.11.0, pinned |
| Robot | UFACTORY xArm7 (a real, purchasable ~$11K arm) |
| Status | **Pre-hardware.** Simulation only. No robot has been bought. |

Full breakdowns: **[V5_PLAN.md](V5_PLAN.md)** (current work — v5 plan and every v5
result), **[RESULTS_V4.md](RESULTS_V4.md)** (the decision loop),
**[RESULTS_V3.md](RESULTS_V3.md)** (swap cycle) and **[RESULTS.md](RESULTS.md)**
(insertion). **[CELL_SPEC.md](CELL_SPEC.md)** is what you would build a real cell from.

> **Caveats that must travel with the numbers above.** The class names Easy / Medium /
> Hard are DrinkPrime's; **the boundaries between them are ours**, because no document in
> their set defines them — that is the top open question for the founder. v5 CLEAN is a
> **dry pad wipe of the cabinet exterior**: no cream, detergent or solution is simulated.
> The membrane bowl, cap and O-ring are **placeholder geometry** pending CAD. The dip's
> bubbles are **modelled from cap torque, not a fluid simulation** — what stays real is
> that a camera has to actually see them to fail the part. And end-to-end is **capped by
> triage**: both routing misses are triage errors propagating, and 26/28 is statistically
> consistent with the grader's own 97.5%.

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
../venv/bin/python v5_triage.py   --eval 120     # grade 120 units   -> 97.5%
../venv/bin/python v5_clean.py    --eval 8       # clean 8 units     -> 100% coverage
../venv/bin/python v5_membrane.py --sabotage 10  # Stage 10 + bubble -> 10/10, 0 false pass
../venv/bin/python v5_route.py    --eval 28      # full routed cycle -> 26/28 end-to-end
../venv/bin/python v5_video.py    --render 1607  # re-render the v5 demo cut (writes no stats)
```

> **Each command's default `--seed0` is the one that reproduces its published number**
> (triage 700, clean 900, membrane 1400, routing 1700) — run them bare. Note the membrane
> baseline is the **paired** `--sabotage 10` run, which writes 10 honest *and* 10
> deliberately under-tightened units; a plain `--eval 10` writes a different, smaller
> result over the same file.

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
| `sim_poc/v5_clean.py` | **v5 station 2** — plan-then-execute wipe of all five faces, plus the verification + sabotage test |
| `sim_poc/v5_membrane.py` | **v5 station 3** — Stage 10: cap to torque, pressurise, dip, bubble check |
| `sim_poc/v5_route.py` | **The routing loop** — the grade selects the route; reports compliance, right-route and end-to-end separately |
| `sim_poc/v5_video.py` | Renders a full route cycle with per-station on-frame caveats |
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

**Every v5 phase (V5-0 through V5-G) is done.** The remaining work is not code:

1. **Ask the founder what defines Easy / Medium / Hard** — open-ended, because no document
   in their set defines it. Every triage boundary we use is ours wearing their vocabulary.
2. **Check what the funding bar actually means.** It is recorded as image inspection plus
   *"the arm cleans **the filter** with **a solution**"*. v5's CLEAN is a **dry wipe of the
   cabinet exterior** — different part, no fluid. v4's cartridge dip is much closer. Nobody
   has checked which was meant, and it changes what to build next.
3. **Re-derive the membrane geometry when the CAD lands.** The bowl, cap and O-ring are
   placeholders, so the turns-to-torque figure is a *mechanism* result, not a part result.

**Blocked on DrinkPrime, in priority order:** what defines Easy / Medium / Hard (must be
asked open-ended — no document in their set defines it, and if their operators grade by
*feel* then camera-only inspection is the wrong architecture); QC Annexures 1–13; whether
the final leak test is 45 or 80 PSI (their documents say both, and it is a safety
question); CAD for the membrane bowl, cap and O-ring; and the cabinet's outer dimensions
and mass.

**Done since this list was last written:** all five v5 stations (triage, clean, verify,
membrane, routing) plus the v5 video; the process documents landed and are transcribed;
LeRobot v2.1 export is written (structurally validated, *not* round-tripped through the
real library); and the domain-randomization sweep produced the ±2.5 mm fixture-tolerance
envelope in RESULTS_V4.

The founder has indicated **$20–30K of funding for robot arms** if the refurb process
can be credibly simulated, with an explicit bar of image inspection plus a cleaning step
— which is why refurb fidelity outranks polish on the insertion cycle. **That indication
is verbal, not in writing**, and hardware purchase stays on hold until it is.
