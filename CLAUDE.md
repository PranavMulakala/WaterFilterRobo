# Project: Water Filter Robot — Sim POC (DrinkPrime)

Instructions for Claude Code / any AI agent working in this repo.

## WHERE THE WORK IS — read this first (updated 2026-08-04)

**Current phase: v5, the three-stage funded demo. Plan of record: `V5_PLAN.md`.**

| phase | state |
|---|---|
| V5-0 reachability | **DONE** — passes at cabinet x=0.58; `v5_reach.py` |
| V5-A unit-scale scene | **DONE** — `make_scene_v5.py`, 5 faces, rotary indexer, tool changer |
| V5-B triage | **DONE — 97.5%** on 120 fresh units (700–819); `v5_triage.py` |
| V5-C cleaning | **DONE — 100%** coverage (8/8, 900–907), 0 missed of 129; force **100%** in band, peak **23.9 N** inside the **45 N** ceiling. **V7 continuous stroke: 180.9 → 108.1 s/unit**, full MEDIUM cycle **2:27.3** — see below |
| V5-D verification + sabotage test | **DONE** — honest verified **10/10** with **zero** residue, false verifies **0/10**, sabotage caught **10/10** (1200–1209); needed a 2nd camera |
| V5-E membrane (Stage 10) | **DONE** — **element really inserted 10/10** (aligned 0.30 mm median vs 1.5 mm clearance, seated 1.31 mm off-axis); threaded cap stalls on torque, median **9.40 turns** @ 6.00 N·m, 336 N preload; bubble test **10/10** honest pass, **10/10** sabotage caught, **0** false pass (**1800–1809**). Cap is PRESENTED engaged on the first thread — a fixture action, declared de-scope, not a robot motion |
| V5-F route wiring | **DONE, with a named caveat** — route-plan compliance, right-route and end-to-end reported SEPARATELY on 1700–1727; false-easy **0**, missed-hard **0**. `MEMBRANE_INSERT` is now MEASURED; **`ROUTE_TO_SCRAP_APPROVAL` is still UNBACKED** — no motion delivers a unit anywhere, it passes by being named. **The earlier "end-to-end 28/28" is RETRACTED** — see below |
| V5-G video | **DONE** — `v5_video.py --render SEED`; per-station on-frame caveats, `media/v5_cell_medium.mp4` + `v5_cell_hard.mp4`. **Re-rendered 2026-08-05** after 11f9ea9 silently broke it: the video called `reset_mem()` (which now leaves the bowl OPEN) and then drove `capdrv` directly, so it filmed a bowl with no element and tightened an invisible non-colliding cap while the HUD printed STALLED unconditionally. **The render path must call the evaluated methods** |

**All v5 phases are DONE (V5-0 through V5-G) — but "done" is not "physically complete".**
An external audit (`codex-review` branch, `REVIEW_V5_E_F_G_END_TO_END.md`) raised ~17
findings. Now fixed: the V5-F end-to-end metric (P0); the 1604/1607 ledger half (P0);
**`MEMBRANE_INSERT`, which is a real measured motion as of 2026-08-05** (P0); the inverted
CAB_TOP account (P1); V5-E re-measured on genuinely fresh seeds 1800–1809, which also
retires the contaminated-1400s finding (P0); missing route margins (P1); the overstated
"routes are theirs, not invented" (P1).

**Still open, and the HARD handoff is the one that matters.** `ROUTE_TO_SCRAP_APPROVAL`
is an **UNBACKED** step: no robot, indexer, conveyor or fixture motion delivers a unit
anywhere — it is a software decision. Worse, `v5_route` sets `steps_ok = True`
**unconditionally** for that route, so a HARD unit scores an end-to-end success on a correct
grade plus a matching trace alone. **That is why the headline to quote is FULLY BACKED
(22/28), not end-to-end (26/28)** — the 4-unit gap is exactly those HARD units.
**HARD physical handoff: 0/6 implemented.** Also open: V5-G has no DR envelope; CELL_SPEC
gaps; three over-length LEARNINGS entries; the leak result is a measured image of a
*modelled* outcome (torque sets `seal_holds`, which sets the bubbles) and has no independent
falsification — a damaged O-ring at full torque would not be caught.

The other things worth doing are not code: put the open questions to the founder — what defines Easy/Medium/Hard, and whether the funding bar's *"cleans the filter with a solution"* means v4's cartridge dip rather than v5's dry cabinet wipe — and re-derive the placeholder membrane geometry when the CAD lands.

**V7-STROKE (2026-08-09; re-baselined 2026-08-10; FEED RAISED 2026-08-11) —
CONTINUOUS-STROKE CLEANING. Full-coverage clean 180.9 → 108.1 s (1.67× on the station),
and with the V7.2 membrane work the full MEDIUM cycle is 3:46.2 → **2:27.3** at 100% coverage, **0 missed of 273** on 16
fresh units (2120–2135), peak force 22.6 N — BELOW the point raster's own 23.93 N — 100%
in band, sabotage 10/10 caught, 0/10 false verifies (2140–2149).**

**THE SPEED CLAMP PAID FOR ITSELF (2026-08-11).** Adopting the arm's published limits
looked like a pure cost — it slowed the cycle and forced the 2:33 retraction. It was not.
The clamp's following-error limit made pad tracking **FEED-INDEPENDENT**, and tracking was
the *mechanism* behind the old feed cliff. Re-swept on fresh 2100–2103, worst in-plane
tracking error is **15.2 mm at every feed from 0.05 to 0.30 m/s**, and coverage is 100%
with 0 missed at every one — where pre-clamp, 0.15 lost 2 patches and 0.30 lost 3. So the
feed doubled 0.10 → **0.20** and the clean station went 146.6 → **111.4 s**.

**That identity — the same 15.2 mm at every feed — is the finding.** It is not "we tried
faster and nothing broke"; it is "the thing that used to break no longer operates".
0.20 rather than the fastest tested 0.30, for margin (1.5× to the fastest verified value)
and because our model removes soil on CONTACT, not dwell: at 0.20 a surface point spends
0.30 s under the pad, at 0.30 only 0.20 s, and the sim is blind to a rub being too brief.

**Row pitch went the OTHER way and was NOT touched.** Post-clamp the row cliff moved *in*:
1.5 R holds 100%, **1.7 R loses a patch** (pre-clamp 1.7 held). `row_frac` stays at 1.20 R
— 1.42× margin. A fix in one place moved a cliff in another, in both directions. *All numbers in this
block below the sweep table are PRE-CLAMP and are kept because the reasoning they support
is unchanged; the shipping figures are the ones in this paragraph and in the re-baseline
table further down.* The arm no longer stops at all 323 raster points: it
seats once per contiguous run and then SWEEPS the path under continuous flange
compression, which is what the ACF was added for. `CleanConfig.stroke` (DEFAULT OFF —
point mode is the published baseline and stays byte-identical).

**This corrects an error of OURS, and the correction is the valuable part.** V6 measured
that the cycle IS the raster and that per-point cost is FIXED rather than travel-bound —
both true — then swept `speed`, which only moves the arm faster BETWEEN stops, got 9.6%,
and concluded "feed rate is a dead lever". **The question never asked was whether to stop
at all.** Each point is floored by TWO 0.20 s `wipe_stall_s` windows (the first sets the
reference error, the second compares), so ~0.40 s of a ~0.52 s point is the arm standing
still agreeing it has arrived.

**THE ADVISOR'S ~2× WAS OPTIMISTIC AND THE REASON IS A MEASURED CLIFF.** It assumed the
pad could sweep as fast as we liked. Swept on fresh 1900–1903, full coverage:

| stroke_feed | cycle | coverage | missed | peak N |
|---|---|---|---|---|
| 0.05 m/s | 224.3 s | 100% | 0/71 | 34.55 |
| **0.10 (now)** | **136.7 s** | **100%** | **0/71** | 34.66 → **32.15** with the gentle seat |
| 0.15 | 112.0 s | 97.8% | **2** | 35.02 |
| 0.20 | 102.0 s | 97.8% | **2** | 35.06 |
| 0.30 | 94.9 s | 96.7% | **3** | 35.11 |

The cause is TRACKING, not sampling: the pad's IN-PLANE departure from the commanded path
grows with feed (median 3.2 → 3.8 mm, worst 18 → 21 mm), and a displaced band leaves a gap
the raster geometry says should not exist. **Same lesson as `step_frac`, one level down —
geometry is only a promise if the arm actually goes where the geometry says.**

**THE FORCE PEAK IS IN THE SEAT, NOT THE SWEEP.** Logging every contact over 20 N with its
phase put all six top events in the SEAT (driving into the surface at the start of a run,
on face 180 where the back panel stands 10 mm proud), none in the sweep. Approaching
contact at `stroke_seat_scale` 0.20× the sweep rate costs **0.6 s/unit** and takes the peak
34.66 → **32.15 N**. *Driving INTO a surface and sliding ALONG one are different motions
with different force budgets; one "speed" knob for both is what made V6 ask the wrong
question.*

**ROW PITCH: the cliff moves but we did NOT spend the margin.** Point mode is a LATTICE
problem (worst gap at a cell centre, `step/√2`, cliff 1.414 R). A stroke sweeps a BAND, so
the only gap is between rows and the cliff moves to 2.000 R. `row_frac` is nevertheless
held at **1.20 R** — identical row geometry to the published raster — so the stroke result
isolates one variable. Measured on 1910–1913, 1.70 R was the only wider pitch that held
100%, and 1.85/2.00/2.20 all lost a patch: an **empirically ragged** band, not a clean
slope, which is exactly why the geometric bound is not spent.

**TARGETED + STROKE IS MEASURED AND REJECTED** (and as of 2026-08-10 targeted mode itself
is withdrawn — see the clamp block above). On fresh 2000–2015 it ran **98.2 s median —
SLOWER than targeted alone (74.7 s, pre-clamp)** — and one unit in 16 (seed 2006, in a re-clean round)
produced **91.5 N**, twice the 45 N model-validity ceiling. Recorded, not shipped, not
tuned past. **The two are SUBSTITUTES, not complements:** both remove the same per-point
stall cost. Full coverage sweeps 5 long serpentines (7 runs, 9.5 m) so the per-run seat
amortises; targeted leaves many short segments, each paying its own seat, so stroke ADDS
seats instead of removing stops.

**V7.2 (2026-08-11) — THE OPENING WAIT, THE MEMBRANE STATION, AND A VISIBLE THREAD.**
Cycle **2:36.7 → 2:27.3**. Three separate things, all validated:

1. **The first face waited 2.5 s for a rotation nobody commanded.** `reset()` leaves the
   indexer at 0 and the first face IS 0, yet the loop still retreated to SAFE and then
   dwelled 1.2 s for the indexer to settle. Now both are conditional on the angle actually
   changing (`_rotating`). The retreat-then-index ordering is still enforced for every
   face that DOES rotate — that sequencing exists because rotating with the arm over the
   device swept the tool through the cabinet, and that reason cannot apply when nothing
   rotates. **Clean 111.4 → 108.1 s, and peak tool speed 1063 → 1007 mm/s** as a bonus:
   that redundant SAFE move was one of the fastest repositioning moves in the cycle.
2. **Membrane 45.3 → 39.1 s.** `carry_speed` 0.10 → 0.20 and a new `hold_floor_s` 0.4 →
   0.20 (16 `_hold` calls per unit were each floored at 0.4 s before their VELOCITY test
   was believed — 6.4 s of pure floor). **The V6 membrane sweep was STALE for exactly the
   reason the cleaning feed sweep was**: it predates the arm-speed clamp. Re-swept on 6
   seeds with the accuracy gates — insert 6/6, cap placed 6/6, stall 6/6, and the margins
   got BETTER (worst placement error 1.74 → 1.90 mm inside a 4 mm capture, worst
   pre-insert alignment 1.74 → 0.97 mm). **`drive_rate` is a DEAD LEVER** — identical time
   at 12/16/20/24 rad/s; the spin is limited by the actuator, not the command.
3. **The cap now LOOKS like a screw.** It always WAS one — `cap_rot` and `cap_z` are tied
   by the `capthread` equality — but it rendered as a plain cylinder. 30 helical ridges,
   `contype`/`conaffinity` 0 and mass 0, so they cannot touch anything or shift inertia.
   **Physics byte-identical with them present** (same 37.98 s, align 0.28, seat 1.28,
   turns 9.70) — asserted by re-running the membrane eval, not assumed.

**UNDER 2:00 IS NOT REACHABLE ON ANYTHING WE HAVE MEASURED CLEAN.** The fastest measured
combination (feed 0.30 + row 1.50) is clean 90.7 s + membrane 39.1 = **2:09.8**, and row
1.50 sits at 1.13× margin to its measured cliff — below the 1.18× this project has
required since `step_frac`. 2:00 needs feed above 0.30 or row pitch at 1.7, neither of
which has been shown safe. Recorded rather than taken.

**Honesty label that must travel with the stroke number:** our model removes soil on
CONTACT, not on DWELL. At 100 mm/s any surface point spends **0.60 s** under the 60 mm pad
versus ~1.0 s in point mode. A shorter rub is free here and would **not** be free with real
cream. That is a modelling limit, not a result.

**ARM SPEED LIMITS ADOPTED 2026-08-10 — and this RE-BASELINED every cleaning number.**
Found by a human watching the video, **not by any metric**: every number this station
reports is about CONTACT (force, coverage, tilt), so free-space motion appeared in no
number, no assertion and no gate. Measured before: peak joint **5.71 rad/s (327 °/s)**
against a published 180 °/s, and peak tool **3020 mm/s** against a published 1 m/s.
Pre-existing across v5, v6 and v7.

**IT TOOK THREE FIXES, AND THE FIRST TWO WERE WRONG IN INSTRUCTIVE WAYS.**

1. **Clamping the SETPOINT rate is not clamping the ARM.** With `ARM.joint_rate` held to
   the published 3.14 rad/s the measured joint speed was still **5.71 rad/s**. A position
   servo does not track the setpoint's velocity, it chases the setpoint's ERROR — so when
   the planner hands over a configuration the arm is far from, the servo sprints.
2. **`ARM.max_follow_err` (0.25 rad) is what actually bounds joint speed** → 2.46 rad/s
   (141 °/s), 22% inside the rating. **DO NOT tighten it to chase the tool-speed figure:
   the force cliff is at 0.14 rad (89.5 N, twice the validity ceiling), and 0.15 sits 7%
   from it.** This project already refused 8% margin on a merely-missed-spot failure.
3. **Tool speed is a CARTESIAN quantity and needs a Cartesian governor** (`_advance`
   scales the setpoint increment by `|J dq|/dt`, commanding `max_tcp_speed *
   tcp_cmd_margin` = 0.80 m/s). Peak tool **3020 → 1063 mm/s**; the residual 6% is servo
   overshoot on 0.16% of steps, all in free-space moves.

**THE RE-BASELINE — and the clamp made the cell BETTER, not just more honest:**

| | before | after |
|---|---|---|
| peak joint speed | 5.71 rad/s (327 °/s) | **2.46 (141 °/s)** ✓ |
| peak tool speed | 3020 mm/s | **1063 mm/s** ✓ |
| point clean (900–907) | 186.8 s, 100%, 0/129, **32.94 N** | 180.9 s, 100%, 0/129, **23.93 N** |
| stroke clean (1920–35) | 137.3 s, 100%, 0/256, **32.15 N** | 146.6 s, 100%, 0/256, **22.04 N** |
| mean press tilt | 11.7° | **8.5°** |
| exact-normal presses | 20.0% | **36.3%** |
| stroke sabotage (1940–49) | 10/10 caught, 0 false | unchanged |
| membrane (1890–99) | 10/10, 0 false pass | unchanged (element align 0.39 → 0.79 mm, bound 1.5) |
| route (1700–27) | 28/28 · 26/28 · 22/28 | **byte-identical** |

**Peak contact force nearly HALVED (32.9 → 23.9 N) and the press geometry improved** —
slower approaches land more gently, and better tracking means the planner's smaller-tilt
solutions are actually reachable.

**TARGETED CLEANING IS WITHDRAWN UNDER THE CLAMP.** Re-validated on its own published
seeds (1840–47 + 1860–75): **1 of 24 units left residue and FAILED verify** (seed 1844,
402.9 s, backstop exhausted at 2 re-cleans) and one unit hit **98.67 N**. Its published
claim was 0/24 residue. **The 2:33 headline is RETRACTED** — not "2:33 became X", but *the
configuration that produced it no longer meets its own acceptance bar*. Full coverage is
the shipping mode and is clean. Same failure signature as targeted+stroke (91.5 N) and the
follow-err cliff: **sparse visits plus a rate-limited approach break the stall detector.**

**Every stepping loop now calls `_tcp_tick()`, `report()` asserts peak joint speed HARD
against the datasheet and peak tool speed with a documented 10% servo-overshoot
allowance, and `v5_check_spec.py` asserts the config statically.** *Measure from VELOCITY
STATE, never position differences* — the first version of this metric differenced pad
positions and read **51 m/s**, because the cell teleports several times per cycle (verify
parks the arm, `couple()` snaps the weld, the membrane station materialises the cap).

**V6-SPEED (2026-08-05 evening) — TARGETED CLEANING + FAST MEMBRANE: full MEDIUM cycle
231 s → 152.5 s median, at ZERO residue.** `CleanConfig.targeted` (DEFAULT OFF — full
coverage stays the shipping mode; "all surfaces covered" is the customer's criterion).
Targeted wipes only ±1-row bands around seen soil, skips soil-free faces, spot-visits
leftovers, and a **VERIFY-triggered backstop** re-cleans up to twice (last round = full
sweep of dirty faces). **Acceptance is the CAMERA's, never the plan's.** HONESTY LABEL:
soil *locations* are ground truth standing in for camera localisation; the residue check
is a real camera. Validated fresh: **0/24 units with residue (1840–1847, 1860–1875)**,
sabotaged cleaning caught **15/15** through the backstop. Clean cycle 186.8 → **~75–120 s**
(median 74.7 on 1860–75; recleans fire on ~1 in 6 units and are included). Membrane:
`drive_rate` 4→12 rad/s and carry 0.05→0.10 m/s, swept with the sabotage gate — loaded
turns unchanged, worst seat 1.48 mm vs 1.47 (bound 1.8), fresh 1850–1859 10/10 honest,
10/10 caught, 0 false pass. **The bug that cost the most was MY OWN optimisation:** an
early-exit indexer wait (angle-arrived ≠ settled) broke coverage in BOTH modes and was
chased through five targeting mechanisms before being found; the 1.2 s dwell is restored
with a warning comment. Sub-60 s at zero residue is NOT achievable on one arm — the tilt
band and backstop ARE the accuracy; the throughput path is parallel cells.

**V6 — CYCLE TIME. The diagnosis was that the cycle IS the raster, and the raster
oversampled by 2.2×.** `v5_clean.py --budget SEED` prints where the seconds go. On the old
config: **STROKE 91.3%, all overhead 7.2%** (tool changer + five turntable rotations +
every retract and approach). Optimising the sequencing that took four bugs to get right
would have bought nothing.

Per-point cost is **fixed, not travel-proportional** — 0.38–0.85 s, unchanged when the
stride grew 37% — because each wipe point is floored by **two 0.20 s `wipe_stall_s`
windows**. So cycle time tracks POINT COUNT, and only point count.

On a square lattice the worst uncovered point is a cell centre at `step/√2`, so coverage
needs `step ≤ R√2 = 1.414 R`. `step_frac` was **0.95 R** — 2.2× the points for no coverage
benefit. Swept on fresh 1810–1817, confirmed held-out 1830–1837:

| step_frac | cycle | pts | coverage | missed |
|---|---|---|---|---|
| 0.95 (was) | 254.7 s | 468 | 100% | 0 |
| **1.20 (now)** | **186.8 s** | **323** | **100%** | **0** |
| 1.30 | 163.8 s | 272 | 100% | 0 |
| 1.414 | 141.5 s | 224 | **97.4%** | **4** |

**1.30 is faster and passed 16 units — and was NOT taken.** Coverage failure is a RARE
EVENT (a spot is missed only if soil lands in a cell-centre gap), so 16 units × ~18 patches
cannot prove a 2.4 mm gap band is closed. 1.414 is a cliff; 1.30 sits 8% from it, 1.20 has
18% margin.

**FEED RATE IS A DEAD LEVER — DO NOT RAISE `speed`.** Swept at step_frac 1.20 on 1820–1827:
best case 186.8 → 168.8 s (**9.6%**), because points are stall-window-bound not travel-bound.
Worse, `speed` 1.5 and 2.0 produced **108 N against the 45 N ceiling** with coverage at 75%
on the worst unit, while 3.0 and 4.0 were clean again — **non-monotonic in both force and
time**, the same signature CLAUDE already records for this contact model above 45 N. Almost
certainly solver instability, NOT diagnosed to the bottom. Either way the lever is not worth
9.6%.

**TRUE MEDIUM CYCLE: 230.96 s (3 min 51 s)** — CLEAN 186.8, insert 25.6, tighten 17.4, dip
1.2. **TRIAGE and VERIFY cost ZERO simulated seconds** (pure rendering), so a real cell is
slightly slower than this, not faster. `v5_video.py --realtime` renders one cycle whose
RUNTIME EQUALS the cycle time — frame-count timing understated it by 15.1% and had to be
re-timed against the simulated clock.

**Every station's number is in the phase table above and reproduces from its own
`--eval`.** The rest of this section is the reusable engineering lessons, kept because
each one cost real time to learn.

**MEMBRANE_INSERT IS NOW A REAL MOTION (2026-08-05).** It used to be a bare string: the
arm never touched the element. It *could not* have — the cap overhangs the whole bore
(r=34 mm) 20 mm above a 155 mm rim, so a 72 x 42 mm element had no path in, and retracting
the cap up its own thread does not help because **the gripper assembly (tcp+0.005..tcp+0.185,
radii to 99 mm) must occupy exactly the space the cap retracts into.** Measured, not argued.
The fix is the order the real process uses: the bowl is **OPEN** while the element goes in,
and the cap is then *presented engaged on the first thread* — which is verbatim the
de-scope `v5_membrane` has always declared. Presenting the cap is a **fixture action, not a
robot motion**, and is labelled that way everywhere. Insertion is 10/10, aligned to 0.30 mm
median against 1.5 mm radial clearance. **The tightening physics is untouched:** re-run on
the SAME seeds (1400–1409) the turn median moved 9.68 → 9.75 and seal peak 341 → 345 N.
Two things that made it work, both reusable: **align on the PART, not the wrist** (the flat
pads constrain only Y, so the element rides on friction in X and slid 19 mm in the jaws
during a fast carry), and **transit OVER the station** (the direct path from home shoved the
bowl 53.7 mm off its post).

**V5-F's end-to-end figure was RETRACTED on 2026-08-05, and the lesson is about metrics,
not motion.** `v5_route.run_route()` picked the route plan from the **predicted** grade and
then scored compliance as *"steps_done == plan"* — so it asked only whether the cell
executed the plan its own prediction chose, never whether that prediction was right. A
misgraded unit that completed its **wrong** route counted as a full end-to-end success. The
published words were *"right route AND every step of it succeeded"*; the code checked the
second half only. Published 28/28 → **actually 27/28** on that run (seed 1517, truth EASY →
graded MEDIUM, is in the committed artifact). Re-measured after the fix on fresh seeds
1700–1727: **route-plan compliance 28/28, right-route 26/28, end-to-end 26/28.**
**A METRIC THAT SCORES A PREDICTION AGAINST ITSELF MEASURES NOTHING.** `grade_correct` is
now required for `end_to_end` and is written to the stats file so the artifact is
self-auditing. Route-plan compliance is KEPT as a separate metric — it is a real thing to
measure and it is honestly 28/28 — but it must never again be reported as end-to-end.
Corollary worth keeping: the classifier was not touched, and 26/28 is **consistent** with
triage's 97.5% (P(≥2 errors in 28) ≈ 0.15). The old 27/28 was never evidence routing beat
triage, and the new 26/28 is not evidence it regressed.

**The lesson from closing them, and it is the reusable one.** Both the coverage gap AND the
unclosed force band were ONE defect: a 7-DoF arm has many configurations for the same pose,
and the planner took the first it found, so raster points 27 mm apart landed in different
IK branches — up to **5.78 rad of joint motion for a 37 mm step**. The executor cannot
cover that in its budget, and on the way it sweeps the pad across the device. Face 180 had
zero jumps and was the only pass that ever behaved; that contrast is what located it.
`plan_pad` now prefers the solution nearest the previous configuration
(`max_joint_jump = 0.35` rad). **Cost, and quote it with the tilt figure:** exact-normal
presses fell 42.7% → 8.8%, mean tilt 7.4° → 18.2°, still inside the 30° cone.

**And V5-D's lesson:** its first run met the stated exit criterion (*honest verified n/n,
sabotaged caught n/n*) with a check passing 9 of 10 dirty units — the triage camera sits at
z = 0.400, the top face at z = 0.450, so it graded four faces while cleaning covered five,
**and the face it could not see was the face cleaning missed.** A `verify_top` camera fixed
it and is a CELL_SPEC hardware requirement. Always report the FALSE-VERIFY rate next to the
sabotage rate; a sabotage arm alone cannot detect a blind verifier. V5-C's five fixes are
landed; see V5_PLAN "V5-C DIAGNOSIS", "V5-C RESULT" and "V5-C REOPENED". Coverage went
**64.7% → 94.6% → 100%**, 0 raster points skipped, tool drift 0.03 mm. None of it came
from tuning — it was four bugs in the motion layer plus two more that fell out of them:

1. **The indexer never reached 270°** — `deg2rad(270)` vs `ctrlrange` ±π, clamped
   silently. Now ±360°, and the cycle indexes *forward* to 360° for the top pass.
2. **The arm self-collided** and missed every waypoint by 100–400 mm. The cleaner now
   **plans then executes**: smallest feasible tilt, collision- and limit-checked, driven
   as a joint target. Plan error 0.00 mm at every point.
3. **34.2% of raster points were silently skipped** — `surface_x` rayed through the arm.
   Now rays only the cabinet's geoms, and **counts** anything it declines to attempt.
4. **The tool is 105 mm wrist-to-pad; V5-0 assumed 45 mm.** The 30° tilt cone is
   mandatory, not optional — it is now **imported from `v5_reach`** so gate and consumer
   cannot drift. Placement stays at x = 0.58.
   *Correction, same day: that claim was only half true when first written. The cone was
   unified; `PAD_STANDOFF` was NOT, so the gate went on planning a 45 mm tool. Now unified
   at 105 mm. The gate still PASSES (relaxed 100% everywhere) but every STRICT figure
   roughly halves — front/back 47.9%, sides 14.6%, top 29.2%. Those are the honest
   exact-normal numbers and they are why the cone is load-bearing.*

**Force is CLOSED, and the ceiling was itself corrected.** In-band 100%, peak **34.5 N**.
The pad's curve is clean and repeatable to **45 N** — not 60: "monotonic to 60" was a
coarse-grid artifact that never sampled 50 N, where the contact solver goes unstable
(11.6 mm on a 10 mm pad). Above 45 N it fails *intermittently* — 50 breaks, 55 is fine,
60 breaks — so it is solver behaviour, not the pad. Present before V5-E (verified against
the pre-V5-E scene), so not a regression. `force_hi` is 45 N and `v5_clean` asserts the
peak against it every run.

**Do not quote a force/tilt/raster figure as an n-unit spread.** The cleaning trajectory
is open-loop and seed-independent — only coverage and missed spots vary with the seed.
`report()` prints this on every run.

**`V5_PLAN.md`'s indexed table was wrong for the side faces (83% → actually 27% strict)**
and is corrected in place.

**The cell now needs TWO tool components, and both are modelled:** a tool changer for
LOCATION (`toollock` weld, 4 mm/4° capture envelope, coupling drift 0.16 mm) and an
ACTIVE CONTACT FLANGE for FORCE (`acf` slide joint, 800 N/m over 30 mm). Do not remove
either. A parallel-jaw grip on a shank does NOT work — creep was insensitive to grip
force and press depth; see PAIN_JOURNAL 2026-08-04.

**Seed ledger — held-out sets are consumed by use.** Spent: 200–259, 300–419, 500–619,
700–819 (triage), 1000–1009 + 1100–1109 (V5-D), 800–807 (cleaning; re-used for DIAGNOSIS only, against the
already-published number). Calibration lives at 9000+. **The next cleaning evaluation
needs a fresh range — **900–907 are now SPENT too** (they produced the published 94.6%),
so allocate BY NAMED PHASE, never by a floating start alone — a large range starting at
1728 can still collide with a reserved block. Reserved: 1000–1309 V5-D and Gate 1;
**1400–1409 V5-E paired diagnostic (development seeds, PERMANENTLY — never a
generalisation claim)**; 1500–1539 V5-F; 1700–1727 V5-F metric re-measure;
**1800–1809 the V5-E pre-speed headline**; **2100–2103 V7.1 post-clamp feed sweep**; **2110–2113 V7.1 row sweep**; **2120–2135 V7.1 held-out validation (the published 16-unit number)**; **2140–2149 V7.1 sabotage**; **1810–1817 V6 stride sweep**; **1820–1827 V6 feed sweep**; **1830–1837 V6 stride validation**; **1840–1847 + 1860–1875 V6-speed targeted-clean fresh validation**; **1850–1859 V6-speed membrane (superseded)**; **1880–1889 V6-ARM development (burned)**; **1890–1899 V6-ARM membrane headline (arm places cap + holds driver)**;
**1900–1907 V7 stroke FEED sweep** (1900–1903 used); **1910–1917 V7 ROW-PITCH sweep**
(1910–1913 used, and re-used for the PAIRED point-vs-stroke check against the same units);
**1920–1935 V7 stroke held-out validation — the published 16-unit number**;
**1940–1949 V7 stroke sabotage battery**; **1950 BURNED** (a render probe printed its
truth to the transcript — one command, one seed, gone); **1960–1999 VLM-vs-HSV paired
triage comparison**; **2000–2015 targeted+stroke (the REJECTED mode)**.
Next free block: **2200+**.
**Demo/rendered (outcomes watched, never held-out again): 1604, 1607, and the reel's
1700 / 1704 / 1702** — the reel deliberately films units that are ALREADY rows in
`stats_v5_route.json`, so the footage is traceable to a published artifact instead of
burning fresh seeds to show the same thing.**
Use it once and look at it once.
**1604 and 1607 are BURNED for evaluation** — they are the V5-G demo seeds, rendered and
watched frame by frame, so their outcomes are known and they can never be a held-out set
again. *(An earlier note here said "start at 1600" and V5_PLAN said "rendering consumes no
evaluation seeds". Rendering consumes no seeds only in the sense that it writes no stats
file; a seed you have LOOKED AT is spent regardless of what wrote it.)* Note each v5
script's `--seed0` default reproduces its published number rather than a spent range:
`v5_clean.py` defaults to 900, `v5_route.py` to 1700.

## First steps every session
1. Read `V5_PLAN.md` (plan + all v5 results), `CELL_SPEC.md` (the real-cell build doc),
   `PROJECT_CONTEXT.md` (business background), `RESULTS_V4.md` (v4 numbers), and
   `LEARNINGS.md` (concepts the humans already have — do not re-explain them).
   `docs/drinkprime/README.md` covers the 13 source documents.
2. Set up if needed: `cd ~/WaterFilterRobo && ./setup.sh` (do NOT use a bare
   `python3 -m venv` — see below). The venv lives at the repo root, so commands from
   `sim_poc/` use `../venv/bin/python`.
3. Confirm the baselines before changing anything (from `sim_poc/`):
   `sim_poc2.py --eval 25` (100%), `sim_poc3.py --eval 25` (100%),
   `sim_poc4.py --eval 60 --seed0 200` (86.7% / 0.0% false-clean / 100% routing).
   All three should reproduce the committed `stats*.json` **byte-identically**.
4. Confirm the v5 gates: `v5_check_scene.py`, `v5_check_spec.py`,
   `v5_reach.py --indexed`. All three must pass before touching the scene. None of them
   writes anything (only `v5_reach.py --sweep` writes `reach_v5.json`), so they are safe
   to run.
5. **The v5 baselines are protected recorded results too**, and are reproduced by
   `v5_triage.py --eval 120` (97.5%) and `v5_clean.py --eval 8` (100% coverage); both
   `--seed0` defaults now reproduce the published number. Running either with a different seed range OVERWRITES the
   committed stats file with a number that is not the published one.

## Environment — read this before debugging an install
- **Requires Python 3.10+.** Apple's system `python3` is 3.9, which has no MuJoCo
  wheel; pip falls back to a source build and fails with the misleading
  `RuntimeError: MUJOCO_PATH environment variable is not set`. `setup.sh` handles this.
- Dependencies are **pinned in `requirements.txt` on purpose.** Contact-rich physics
  is not reproducible across MuJoCo versions — the same seeds gave 84% on the
  original engine and 88% on MuJoCo 3.11. Do not bump versions casually; if you do,
  re-run the eval and update `RESULTS.md`.
- `--render` and `--cards` need TrueType fonts. The font path is resolved at runtime
  with a fallback chain; on Linux install `fonts-dejavu`.

## Codebase map
- `sim_poc2.py` — the whole system: xArm7 in MuJoCo, randomized cartridge spawn
  (±40 mm, 360° yaw), simulated perception (1 mm noise), closed-loop yaw servo,
  3 mm-clearance bayonet insertion through a chamfer funnel, drop-seat + regrip-cap
  + 55° twist-lock, and retry-on-stall.
  CLI: `--eval N` | `--render idx seed speed` | `--cards` | `--concat`
- `sim_poc3.py` — **v3 refurbishment cell: the cartridge SWAP cycle.** Extends v2 by
  import (`ik_step`, `down_mat`, the yaw servo law, the tip-following compliant
  descent and every insertion constant are reused, and the insertion half of the
  phase table is v2's verbatim). New half: EXTRACT (grip cap → untwist out of the
  bayonet → lift through the slots) then DISCARD (carry to bin → drop). Writes
  `stats_v3.json`; success = old cartridge binned AND new one seated+locked.
  CLI: `--eval N` | `--render idx seed speed` | `--cards` | `--concat`
- `ufactory_xarm7/cartridge_scene_v3.xml` — v2 scene plus a spent cartridge that
  starts seated **and twist-locked** (locked lug axis 25–50°, randomized per seed;
  the slot gap spans ~72–108°, so anything outside ~[64,116]° is captive), an open
  bin at (0.46, 0.0), and dull "spent" materials.
- `docs/drinkprime/` — **the 13 source PDFs.** See its README before reading them.
  **The three QC pages are pure vector line art: text extraction returns labels with NO
  EDGES.** Render them (PyMuPDF is in the venv; there is no `pdftoppm` on this machine)
  and look at them. Text-extracting them mis-bound 8 of 13 annexures once already.
- `sim_poc/dp_process.py` — **DrinkPrime's REAL process, as data.** Data only — no
  MuJoCo, no side effects. Holds `STAGES` (10 stages w/ materials, tools, activities,
  the plant's own section-tagged checks, scrap streams, and OUR feasibility tier),
  `QC_NODES` (+ the corrected annexure map), `PRESSURES`, `CONTRADICTIONS`,
  `SCRAP_STREAMS`, `V5_ROUTES`, `MISSING`. Run it for a dump. **The plant's text and our
  judgement live in separate fields on purpose — do not blur them, do not add a step
  that isn't in a source document, and DO NOT FIX THE SOURCE TYPOS** (`ANEXURE`,
  `CABINENT`, `APPERANCE`, `PRESSUE`, `SOLINOID`, `MEMBARANE`, `Rubbing component`) —
  they identify the source and they matter for string matching.
- `V5_PLAN.md` — the three-stage funded demo (TRIAGE / CLEAN / MEMBRANE), the plan of
  record, the V5-0 reachability result, and the one-week cut list.
- `sim_poc/v5_reach.py` + `ufactory_xarm7/cabinet_probe_v5.xml` — **V5-0 reachability
  study (DONE, PASSES at x=0.58).** Kinematics only, no dynamics.
  `--nominal` | `--sweep` | `--scene` (validate the REAL scene, not just the probe).
  Writes `reach_v5.json`. Reports strict (exact-normal) alongside relaxed (30° tilt cone)
  coverage — keep it that way, the gap is large (top face 100% relaxed, 63% strict).
  **Axis convention: depth→X, width→Y, height→Z.** Getting this wrong measured faces
  35 mm inside the box and invalidated five of six numbers; don't reintroduce `w/d/h`.
- `CELL_SPEC.md` — **the document you build and program the REAL cell from.** Frames,
  the sim→xArm-SDK coordinate conversion, station coordinates, tolerances, tooling, the
  rotary-indexer spec, a build checklist, and an explicit "what the simulation does NOT
  tell you". Every number is read out of the model, not typed from memory. Regenerate the
  numbers if the scene changes.
- `sim_poc/make_scene_v5.py` → `ufactory_xarm7/refurb_scene_v5.xml` — **V5-A unit-scale
  scene (DONE).** A GENERATOR (fixed seed), not hand-written geoms. Device on a **rotary
  indexer** at x=0.58, three condition pools — soil(40)/scratch(28)/dent(20) →
  EASY/MEDIUM/HARD, each grounded in a quoted stage — plus tool post, compliant wiping
  pad, matte backdrop, computed cameras. **Edit the generator, never the XML.**
  - **The rotary indexer (`tt`) is a COMMANDED AXIS, not scenery.** It is what takes the
    back face from 0% (unreachable at every fixed placement) to 100%, and it removes the
    camera-separation vs front-coverage trade-off. Verify with `v5_reach.py --indexed`.
  - Pools are on **all FIVE exposed faces** — front, top, left, right **and the back
    panel's outer surface** — because the rotary indexer made the back reachable. Cleaning
    coverage therefore means **"of all five exposed faces"**. *(This reverses an earlier
    "four reachable faces only, keep that wording" instruction that survived here long
    after the fifth face went in at c19bac0. `make_scene_v5.py` added it precisely because
    leaving the back clean "would have quietly flattered any cleaning number V5-C
    produces" — so the stale wording was flattering the number in exactly the way the
    scene change was meant to prevent.)*
  - Pool geoms must carry their **material's RGB with alpha 0** — a geom's `rgba`
    overrides its material, so `rgba="0 0 0 0"` reveals as BLACK and destroys the whole
    point of three visually distinct classes.
  - **Never add a geom to this scene without re-running `v5_reach.py --scene`.** A 6 mm
    backdrop panel that looked like scenery cost an entire face (89.6% → 0%).
- `sim_poc/v5_check_scene.py` — **run after regenerating the scene.** ~25 structural
  assertions (patches on-face and outward-facing, flush cover, indexer carries the device
  and its pools, pad rests on its post, no spawn interpenetration). The scene LOADED FINE
  through all five V5-A bugs; loading is not validation.
- `sim_poc/trade_study.py` + `TRADE_STUDY.md` — **the arm-count decision artifact, options
  A/B/C/D.** A CALCULATOR, not a spreadsheet in prose: every economic number in the doc is
  produced here, and the two things we are waiting on are single constants at the top
  (`YAM_LOAD_EVIDENCE`, `DAILY_VOLUME`). **Every number carries a source tag —
  `[measured]` / `[published]` (with URL) / `[assumed]` (with a range) — and there are no
  untagged numbers.** Headline: **one xArm7 cell does ~328 units/day against an estimated
  130–200 need, so the arm-count question is moot at the expected volume.** B (2-arm
  pipeline) is worth only **1.13×** for 2× the arms because a pipeline runs at its slowest
  station — and **the faster V7 made cleaning, the worse B got.** C (fixed brushes) is the
  real throughput lever ($71 per unit/day vs $130) and is gated by one measured number: a
  **64.1 mm radial swing per quarter turn** on a 180×250 mm box against our **30 mm**
  flange — plus it cleans BLIND, which costs the per-patch evidence that is the product.
  D (YAM) needs its unknowns priced as risk: our 32.1 N sustained wipe is **3.28 kg
  equivalent = 82% of a YAM Ultra's rating before the tool**, and **YAM publishes no
  repeatability at all** against our ±0.5 mm-class needs.
- `sim_poc/v5_vlm_triage.py` + `RESULTS_VLM_TRIAGE.md` — **[demo] VLM-vs-HSV triage,
  run BLIND.** `--render N --seed0 S` writes shuffled `u00.png…` plus a separate
  `key.json`; grade into `vlm.json`; `--score` joins them. **Result on 40 paired fresh
  units (1960–1999): both 97.5%. The VLM removed HSV's one false-easy and added one
  MISSED-HARD** — it traded the safe error for the unsafe one, and missed-hard is the
  metric this project leads with. Two discordant pairs, one each way: **no statistical
  evidence of any accuracy difference (McNemar p = 1.0)**, and the run cannot distinguish
  0% missed-hard from ~20%. **The blinding is load-bearing, not ceremony** — the grader
  wrote the harness and can read `sample_condition`, so images carry no seed and no class,
  the render loop prints the INDEX ONLY, and answers are committed before the key is
  opened. Seed 1950 was burned by a probe that printed its truth before the protocol
  existed; that is the leak the design prevents.
- `sim_poc/v5_check_spec.py` — **run after ANY scene change.** Asserts all 39 numbers in
  `CELL_SPEC.md` against the live model, plus the joint limits against the UFACTORY
  datasheet. CELL_SPEC's entire value is that its numbers were read from the model rather
  than typed; that decays silently the moment the scene moves. **If this fails, update
  CELL_SPEC.md — never relax the assertion.**
- `sim_poc.py` — simpler v1 (plain pick-and-place), kept for reference.
- `ufactory_xarm7/cartridge_scene_v2.xml` — the scene: socket collar (band
  58–100 mm), 45° chamfer funnel with lug gaps (spans z 98.5–126.1 mm), pedestal
  seat at 45 mm, cartridge (radius 21.5 mm, half-length 55 mm) with 2 lugs at local
  z = −49 mm. **Geometry MUST stay consistent with the constants in `sim_poc2.py`**
  (`SPAWN_Z=0.068`, `SEAT_Z=0.100`, `GRASP_OFF=0.004`, `CHAMFER_TOP_Z=0.1261`,
  `seat_tcp=0.110`).
- `ufactory_xarm7/xarm7.xml` — arm model (MuJoCo Menagerie) + added wrist camera.
- `stats.json` — last eval output. See `RESULTS.md` for the current headline number.

## Hard rules
- **PORTABILITY — THE ARM IS NOT DECIDED (added 2026-08-09).** There is a live chance we
  move off the xArm7 to YAM (`TRADE_STUDY.md`, option D; the decision rule is that xArm7
  stays the default unless Anirudh's reply carries **first-hand** YAM-under-load
  evidence). Therefore:
  1. **Do NOT re-run reachability or CELL_SPEC validation for YAM kinematics.** That is
     wasted work until the arm is final. `v5_reach` and `v5_check_spec` stay xArm7-only.
  2. **All NEW code plans in the PART/CELL frame, never the arm frame.** Feed rates are
     tool-on-surface speeds, targets are pad points on a face, tolerances are process
     tolerances. `v5_clean.stroke_run` is the worked example: `stroke_feed` is m/s of pad
     along the surface, and the joint-rate limit is applied as a constraint on top rather
     than being the unit the path is written in.
  3. **Arm-specific constants live in ONE marked block.** `v5_clean.ArmProfile` (joint and
     actuator names, IK seed/damping/gain/iterations, the setpoint rate limit, the
     branch-jump thresholds, and datasheet reach/payload/repeatability). An arm swap is a
     new profile plus one re-validation run, not a rewrite. Joint LIMITS and the mount
     pose are deliberately NOT in the profile — they are read from the model, for the same
     reason CELL_SPEC's numbers are read from the model.
- After ANY controller or scene change, run `../venv/bin/python sim_poc2.py --eval 25`,
  `sim_poc3.py --eval 25` **and** `sim_poc4.py --eval 60 --seed0 200` from `sim_poc/`, and report both success rates
  against the recorded baselines (v2: 100% locked; v3: 100% full swap). **Never
  claim a fix without an eval.** v3 imports v2, so a v2 change moves v3 too.
- **Report the margin, not just the rate.** A pass/fail rate hid a systemic defect
  once already (every trial was jamming; only the tail failed). When evaluating a
  change, also report peak cartridge tilt during INSERT — median and max. A change
  that raises the pass rate while leaving tilt high got lucky and will not
  generalise.
- **Validate on held-out seeds.** Tuning on seeds 0–24 and reporting 0–24 is
  overfitting. Confirm on seeds 25+ before believing a result.
- Never weaken the success criteria at the end of `run_trial` (`xy_off < 0.006`,
  `upright > 0.95`, `rel_twist > 30`) or special-case seed numbers to make a number
  go up. That is a failure, not a result.
- Do not break the CLI interface or the `stats.json` schema.
- **Running ANY eval overwrites `stats*.json`, including `--eval 2`.** Those files are
  the recorded baselines the whole project is measured against. Never smoke-test the CLI
  with a small `--eval N` without re-running the full baselines afterwards, and check
  `git diff -- sim_poc/stats*.json` before finishing.
- Append every gotcha, surprise, or manual workaround to `PAIN_JOURNAL.md` — it is
  deliberate product research for a possible robotics-devtools product.
- **Every session that lands a significant change appends a `LEARNINGS.md` entry.
  Written for the humans, not for agents.** Plain English, zero unexplained jargon,
  ≤15 lines, three sections: what we built (one sentence), the concept behind it
  (explained to a smart reader who is new to robotics), and why it matters for the
  real robot. This is how two software engineers compress a robotics education into
  a couple of months — treat it as a first-class deliverable, not a changelog.
  `PAIN_JOURNAL.md` records what went wrong; `LEARNINGS.md` records what we now
  understand. If a new term appears without an explanation, that is a bug in the file.
- Small incremental changes; explain the **physics** reasoning, not just the code.

## Known physics gotchas (learned the hard way — see PAIN_JOURNAL.md)
- The gripper's finger PADS sit ~25 mm ABOVE the `link_tcp` site. Grasp height is
  tuned so the pads land mid-body; changing `GRASP_OFF` blindly breaks the grasp.
- Commanded wrist yaw maps to NEGATIVE physical yaw (sign flip in `down_mat`).
- The keyframe `home` predates the cartridge free joint — its qpos must be set
  explicitly after `mj_resetDataKeyframe`.
- Position actuators sag under gravity; `qfrc_applied` gravity compensation is on.
- IK plans on the COMMANDED config (`ik_data`), not measured state — do not "fix" this.
- A lateral-correction law of the form `target = current + error` is an **integrator
  that winds up against contact**. When the part is jammed and cannot move, the wrist
  walks sideways indefinitely and torques the part. This caused the original wedge.
- **Untwisting through a cap grip loses 16–18% of the commanded rotation to
  torsional slip** (22 mm contact patch transmitting torque through friction). Never
  dead-reckon a twist from wrist angle — close the loop on the MEASURED CARTRIDGE
  yaw, or the lug axis lands ~10° short of the slot and the lift jams.
- **Calibrate vision through the real motion path, never on a teleported part.** The
  v4 classifier scored 90% on a rig that placed the part perfectly and 53% in the
  cell, because the presentation height used an assumed grip offset instead of the
  measured one. A vision model is only as valid as the fixture presenting the part.
- **A fixture must clear the part's LARGEST feature.** The staging nest was sized to
  the 21.5 mm body and interfered with the 34 mm bayonet lugs by exactly 7 mm. When
  something will not seat, ask MuJoCo for the contact list before theorising.
- **`euler="0 0.785 th"` on a chamfer ring is WRONG** — it tilts every plate about the
  same world Y axis, not radially, making a pinwheel that overhangs the bore. The
  socket only survives it because its bad plates land in the bayonet slot gaps. Use
  explicit `xyaxes`. Do not copy that pattern to a full ring.
- **Do wet/dynamic work only after re-gripping by the BODY.** The cap grip is weak and
  its hang offset is unstable (42-83 mm). It is fine for
  a short carry-and-drop (v3) and NOT fine for presentation, dipping or re-insertion.
  Anything needing precision must re-grip the part by its body first.
- **A drop in simulation is not automatically a real failure.** Anirudh (2026-08-02):
  sim-side drops and lost friction are *sometimes* artifacts of the simulator, up to
  outright geometry bugs where a gripper passes through the part — "obviously in the real
  world, you're not going to have that." He said *sometimes*, not usually, and he did NOT
  question the 16–18% untwist slip (he read it back approvingly as the gripper losing
  friction). This does not overturn the cap-grip finding above, which is measured and
  reproducible; it means the finding is a hypothesis about the real cell until a real
  gripper holds a real cartridge.
- Extraction has **no chamfer**. Going in, the funnel centres the part mechanically;
  going out, the lugs must thread back up 3 mm slot channels with no lead-in. During
  UNTWIST/EXTRACT the wrist holds the socket axis exactly — any commanded lateral
  motion there is pure risk.

## Backlog (priority order)
0a. **Refurb v4 — inspect / clean / replace. PHASE A DONE; all three routes run.**
   `sim_poc4.py` + `cartridge_scene_v4.xml`. Inspection (real CV on rendered pixels)
   **works: 86.7% in-cell on 60 held-out seeds (200–259), 0.0% false-clean, no heavy
   part ever graded clean.** (An earlier 90.0% / 3.7% was the smaller 30-seed run.) Routing decision works. REPLACE route 100%. **Routing compliance 100%**
   on 60 held-out trials, all three routes 100%, end-to-end 86.7% (capped by vision,
   not mechanics), **false-clean rate 0.0%**. Fixed by a chamfered staging nest: the
   part is set down and re-gripped by its BODY, and the wet work happens after that
   re-grip — a cap-gripped part is dropped ~7 s into a dip. **Next: Phase B — the
   three-route video (90 s labelled 1.8x + a full-length honest cut).** See
   `RESULTS_V4.md`.
   **Before investing further in the classifier, ask DrinkPrime how their own workers
   grade a cartridge** (Anirudh, 2026-08-02): visual inspection, a wear indicator or
   colour change, or *feel*? There is no single off-the-shelf classifier for this. If the
   wear is clearly visual an off-the-shelf VLM may beat the hand-tuned HSV thresholds; if
   workers grade by feel, camera-only inspection is the wrong architecture and the 86.7%
   is measuring the wrong thing. A custom trained model is a later problem, not this one.
0b. ~~**Refurb v3 — cartridge swap cycle.**~~ **DONE 2026-08-02.** `sim_poc3.py` +
   `cartridge_scene_v3.xml`: extract a twist-locked spent cartridge, bin it, install
   a fresh one. 100% over 125 trials (25 + 100 held-out). See `RESULTS_V3.md`.
1. ~~**LeRobot dataset logging**~~ **DONE** — `sim_poc/lerobot_export.py` writes a
   LeRobot v2.1 dataset (parquet + per-camera mp4 + meta/, incl. `episodes_stats.jsonl`).
   8-dim state/action, wrist + overhead cameras. Structurally validated;
   **NOT round-tripped through the real lerobot library** — that remains unverified.
   Only successful episodes are exported, so the set contains no recovery demos.
   `--validate-only` re-checks an existing dataset. Datasets are gitignored (~6 MB/ep).
2. ~~**Swap in real geometry when the refurb docs arrive.**~~ **DOCS LANDED 2026-08-04.**
   All 13 source documents (10 stage work instructions + 3 QC flow pages) are
   transcribed in `sim_poc/dp_process.py`; the plan is
   `V5_PLAN.md`. What they changed:
   - Our cycle approximates **Stage 10, Membrane Assembly** — a real, named station.
   - But their cap is **threaded, spanner-tightened (multi-turn to a torque
     criterion)**, not our 55° indexed bayonet. Same task class, different motion. Do
     not repeat the "nearly one-to-one" claim without that qualifier.
   - Their dip is a **bubble test on an assembly pressurised to 80–90 PSI** with the
     permeate end-plugged and the reject valve closed — not a wash. So the camera check
     is *their* acceptance criterion.
   - **NO document in the set defines Easy/Medium/Hard.** (Corrected 2026-08-04: an
     earlier note here said Annexure 1 defines them — it does not, it governs
     CABINENT / STICKERS CHECKING. The triage fan-out has no annexure at all.) Any
     triage class boundary is OURS wearing their vocabulary. Label it that way every
     single time it is reported, and ask the founder open-endedly.
   - **HARD is not a dead end** — their chart forks it into RECTIFIABLE (rejoins the
     line) and NON RECTIFIABLE (scrap approval, cost > 80–90%).
   - **45 PSI vs 80 PSI contradiction** on the assembled-device leak test (stages 4/6 vs
     QC page 3). Recorded in `CONTRADICTIONS`, not reconciled. Ask before building any
     leak-test station.
   - **There is no teardown/disassembly work instruction in the corpus.** The extraction
     motion v3/v4 are built on has no documented counterpart. Worth knowing before
     claiming the sim mirrors their process.
   - Deformables (Teflon, stickers, harness, tubing) are a **deliberate de-scope**,
     recorded in PITCH_NOTES §9 as a decision, not a gap.
   Still blocked on: **what defines Easy/Medium/Hard** — the top ask, and it must be
   asked OPEN-ENDED because no document in the set defines it (Annexure 1 is the
   cabinet/sticker cosmetic spec, useful for CLEAN verification, not the triage);
   **QC Annexures 1–13**; **membrane bowl + cap + O-ring STL/STEP** (now outranks the
   cartridge); **cabinet outer dimensions AND mass**; and **whether the final leak test
   is 45 or 80 PSI**. Per Anirudh (2026-08-02) a
   manufacturer almost certainly already has the CAD and it can be asked for without the
   physical device. All 13 source PDFs are checked in at `docs/drinkprime/` — read its
   README before opening them. See `meetings/anirudh_call_2_transcript.md`.
3. Config dataclass to replace magic numbers (geometry, speeds, tolerances).
4. Domain randomization: mass ±20%, friction ±30%, table height ±5 mm; re-eval.
5. Second scene: screw-down station with torque-limited driver.

**Commercial context for prioritization:** the founder has indicated $20–30K of
funding for arms if the refurb process can be credibly simulated. Refurb fidelity is
therefore the gating item, ahead of polish on the insertion cycle.
