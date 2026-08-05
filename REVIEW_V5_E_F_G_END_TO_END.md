# Review: V5-E through V5-G and current repository state

**Verdict:** do not present the current repository as “all v5 phases DONE” or quote
V5-F as 28/28 end-to-end. The committed route artifact contains a triage error, but the
metric still calls the trial successful. The evidence supports 28/28 **route-plan
compliance** and 27/28 (**96.4%**) “right route and every step succeeded,” before addressing
the more fundamental fact that membrane insertion and physical scrap routing do not occur.

**Reviewer role:** static/adversarial review and rival planning only. I did not run an eval,
render, calibration, held-out seed, scene generator, or any command that writes a recorded
baseline. I did not modify `main`.

**Committed range reviewed:** `1aa12e7..c394900`:

- `9a13e3a` — V5-E membrane
- `fe752fb` — V5-F route wiring
- `c394900` — V5-G video

The committed V5-E Python, generator, and stats blobs are byte-identical to the work-in-
progress snapshot reviewed in `REVIEW_V5_E_AND_RECENT_COMMITS.md`; its V5-E findings remain
unresolved.

## Ranked findings

### [P0 — wrong] V5-F end-to-end is 27/28, not 28/28

The report defines end-to-end as “right route AND every step of it succeeded” at
`sim_poc/v5_route.py:30` and repeats that wording at line 169. The implementation never
checks whether the selected route is right for the generated truth:

```python
# sim_poc/v5_route.py:142-152
out["routing_ok"] = bool(steps_done == list(plan))
...
out["end_to_end"] = bool(out["routing_ok"] and out["clean_ok"]
                             and out["leak_ok"])
```

`routing_ok` asks only whether the code appended the strings in the plan selected by its own
prediction. Seed 1517 is the counterexample already committed in
`sim_poc/stats_v5_route.json:179-212`:

```json
{
  "seed": 1517,
  "truth": "easy",
  "grade": "medium",
  "route": "medium",
  "routing_ok": true,
  "end_to_end": true
}
```

A read-only recomputation from the artifact gives:

```text
n=28, truth==grade: 27, accuracy: 0.9642857142857143
wrong: seed 1517, easy -> medium, routing_ok=true, end_to_end=true
```

This directly refutes:

- `V5_PLAN.md:1042-1043`: end-to-end **28/28**;
- `V5_PLAN.md:1055-1057`: “seeing none across 40”;
- `CLAUDE.md:17`: end-to-end **28/28**; and
- `LEARNINGS.md:637-639`: “every one routed correctly and completed.”

The correct split from the existing artifact is:

- route-plan compliance: **28/28** — the cell followed the plan its prediction selected;
- triage/right-route accuracy: **27/28 (96.4%)**;
- right route plus reported downstream success: **27/28 (96.4%)**.

The easy-to-medium error is overtreatment rather than the dangerous false-easy error, but it
is still not the right route. Add `grade_correct = grade == truth`; require it for
`end_to_end`; preserve route-plan compliance as a separate metric; and correct every quoted
28/28 claim. Because this is a controller/metric change, the builder—not the reviewer—must
perform the required fresh-seed eval.

### [P0 — overstated] “Full loop” success is awarded for strings that have no physical action

The medium route claims `MEMBRANE_INSERT`, but the route code does not insert the membrane:

```python
# sim_poc/v5_route.py:120-124
self.reset_mem(seed)
tg = self.tighten()
steps_done += ["MEMBRANE_INSERT", "CAP_TIGHTEN"]
```

The exact line that makes the claimed step pass is line 123: it appends
`"MEMBRANE_INSERT"`. `v5_membrane.py:123-125` jitters the loose element on its nest, but no
later cycle code reads or moves `self.elem_q`. `v5_membrane.py:309-316` resets, tightens the
already-engaged cap, records pressure state, reveals bubble proxies, and teleports/dips the
assembly. It never performs element pick, alignment, insertion, or cap engagement.

The hard route has the same defect:

```python
# sim_poc/v5_route.py:100-103
steps_done.append("ROUTE_TO_SCRAP_APPROVAL")
out["scrap_gate"] = True
```

There is no robot or indexer motion delivering a unit to a gate. The committed hard video is
a 3.3-second static labelled outcome, not a delivery. Therefore these claims are not
supported by the code:

- `LEARNINGS.md:637`: “the full loop”;
- `LEARNINGS.md:645-646`: “It delivers those units to a human approval gate”;
- `V5_PLAN.md:1034-1036`: routing correctly means “delivered to the gate”; and
- `CLAUDE.md:20`: “All v5 phases are DONE.”

Either narrow the names to what exists—**cap-tightening proxy**, **synthetic-bubble image
check**, and **software handoff decision**—or add physical membrane insertion and physical
outfeed before calling this a complete route. Prior v3/v4 pick-and-place on different
geometry does not prove either new action.

### [P0 — wrong] The held-out seed ledger is already contaminated in two places

#### V5-E 1400–1409 were tuning seeds

`V5_PLAN.md:969` calls 1400–1409 “fresh ... looked at once.” The same file at
`V5_PLAN.md:1009-1013` says the first ten-run result was inspected, found to be effectively
n=1, and then fixed by adding new randomized inputs. The code itself records the intervention:

```python
# sim_poc/v5_membrane.py:126-138
# The first version varied only the element's position ...
# and every one of ten "held-out" units returned 10.06 turns ...
for g in self.oring:
    self.m.geom_friction[g][0] = ...
    self.m.geom_size[g][0] = ...
self.d.qpos[self.cap_rot_q] = ...
```

The first result informed the code change and the same 1400–1409 seeds produced the final
headline. Under the binding rule “held-out sets are consumed by use,” they are development
seeds, not one-shot evidence.

#### V5-G consumed 1604 and 1607 while the ledger still says start at 1600

`V5_PLAN.md:1121` says “Rendering consumes no evaluation seeds.” That is false under this
project's own ledger rule. `v5_video.render_unit()` runs the actual seeded path:

- `v5_video.py:135`: `c.grade(seed)`;
- `v5_video.py:162`: the real cleaning run with that seed; and
- `v5_video.py:175`: membrane reset with that seed.

The committed, inspected videos use seeds 1604 and 1607, while `CLAUDE.md:87` still directs
the next evaluation to start at 1600. Those outcomes are no longer hidden. Mark 1604 and
1607 spent/demo and allocate a contiguous range that excludes every inspected seed. A render
need not overwrite stats to consume held-out evidence.

### [P1 — wrong] V5-E's verifier and “truth” share the same torque boolean

The code defines seal truth from torque:

```python
# sim_poc/v5_membrane.py:223
"seal_holds": bool(tq >= self.mcfg.torque_pass_nm)
```

It uses that same boolean to create the image:

```python
# sim_poc/v5_membrane.py:232-233
self.m.geom_rgba[g][3] = 0.0 if holds else 0.85
```

Then it calls the originating boolean workpiece truth and computes false pass against it at
lines 323-331. Thus 10/10 sabotage caught and 0 false pass establish only that the camera can
see bubble graphics commanded by the torque threshold. They cannot falsify the seal model,
pressure retention, or the causal assumption torque ⇒ sealed.

Keep the useful pixel-visibility test, but rename the metric synthetic-bubble detection. An
independent sabotage matrix should include damaged/missing O-ring at high torque, false torque
stall, forced bubbles under nominal torque, camera occlusion/lighting, and a sealed/no-bubble
negative control.

### [P1 — wrong] The cap is neither the claimed exact 2 mm-pitch screw nor a four-turn driver

The scene declares a 2 mm/turn equality at `make_scene_v5.py:753-759`; the plan calls it a
“real screw” at `V5_PLAN.md:948-953`. The published workpiece values violate that relation
under load. For seed 1400, reconstructing the starting phase using the exact RNG sequence at
`v5_membrane.py:122-138` gives:

```text
initial cap_z                 -0.200631 mm
9.9743706 turns at 2 mm/turn -19.948741 mm additional
expected final               -20.149372 mm
recorded final               -17.086809 mm
constraint error               3.062563 mm (15.20%)
```

Across the ten honest rows, loaded thread error is about 14.93–15.34%. The exact reporting
lines are `v5_membrane.py:157-159` for turns and `v5_membrane.py:199-202` for cap travel.

Separately, `make_scene_v5.py:91` declares `MEM_TURNS_MAX = 4.0  # driver stroke, turns`, but
its only effect is the XML comment at lines 755-756. The actual controller accepts up to 14
turns (`v5_membrane.py:62`) and the result needs a median 9.68. The `cap_z` range at
`make_scene_v5.py:679` permits about 15 turns.

Report maximum loaded pitch error; either enforce the four-turn hardware stroke and redesign
the engagement geometry, or remove the four-turn claim. Do not publish “exact thread,” four-
turn stroke, and a ten-turn result together.

### [P1 — overstated] The V5 route mapping is ours, not “theirs, not invented”

`v5_route.py:6-8` and `V5_PLAN.md:1021-1023` say the routes are DrinkPrime's and “theirs,
not invented.” `dp_process.py` says the opposite:

```python
# dp_process.py:28-29
# V5_ROUTES describes what OUR CELL does -- a deliberate subset
```

The source chart sends EASY, MEDIUM RECTIFIABLE, and HARD RECTIFIABLE to a merge above
`UNIT TESTING` (`dp_process.py:479-489`). It does not say EASY → cabinet cleaning or MEDIUM
→ Stage 10 membrane rebuild. The route notes admit the modelling choices:

```python
# dp_process.py:666-673
"We model the cosmetic path ..."
"Cosmetic plus a stage-10 membrane subassembly rebuild."
```

The grade names and scrap fork topology are sourced; the mapping from grade to the three demo
stations is ours. Say exactly that everywhere.

### [P1 — gap] V5-G is marked done without its planned domain-randomization envelope

The plan of record defines V5-G at `V5_PLAN.md:190` as:

```text
DR sweep on the new stations; video; docs | Envelope stated as a spec, as in v4
```

Commit `c394900` adds video code, two videos, cameras, and prose. It adds no V5 domain-
randomization sweep, result artifact, or station envelope. A repository search finds the
planned sweep only in the phase table and the general backlog. `CELL_SPEC.md:336-363` still
states that ±2.5 mm is inherited from v4 and never measured on the V5 stations.

Therefore V5-G is partially done, not done according to its own exit definition. Either
reopen it for the builder to run the predeclared perturbation sweep on fresh seeds or amend
the plan explicitly and explain why the envelope was descoped.

### [P1 — wrong] CELL_SPEC is not a safe build document in its current state

`CELL_SPEC.md` says it is the document used to build the real cell, but it contains live
contradictions and obsolete hardware values:

- lines 287-300 specify a parallel-jaw shank; lines 302-305 immediately say that section
  “WILL BUILD THE WRONG CELL”;
- line 317 reports median 13.1 N and peak 271 N, while the committed current result is peak
  34.508 N and 100% in band;
- line 319 specifies `solref="0.045 1"`, `solimp="0.55 0.88 0.012"`; the generator's exact
  live values are `solref="0.035 1"`, `solimp="0.80 0.99 0.003 0.5 2"` at
  `make_scene_v5.py:595-597`;
- lines 324-327 say contact has not been tested and top strict reach is 63%; current indexed
  top strict reach is 29.2%;
- lines 329-330 specify 45 mm standoff; the shared current tool standoff is 105 mm;
- lines 336-342 say V5 station tolerance has never been swept, which also refutes V5-G done;
- the build checklist at lines 404-435 omits the required tool changer/active contact flange,
  membrane station, leak-test fixtures, `verify_top`, `verify_dip`, `demo_dip`, and scrap
  handoff;
- checklist lines 410-412 call the riser footprint undefined even though §2 says it is
  modelled and swept.

The riser table is independently non-reproducible. `CELL_SPEC.md:70-79` says every face is
100% at every diameter and directs the reader to `v5_reach.py --riser`. The safe command's
actual output was:

```text
riser dia   front    top   left  right  front strict  sides strict
none        100.0  100.0   83.3    0.0          22.9           0.0
120 mm      100.0  100.0   83.3    0.0          22.9           0.0
150 mm      100.0  100.0   83.3    0.0          25.0           0.0
200 mm       91.7  100.0   83.3    0.0          25.0           0.0
250 mm       91.7  100.0   83.3    0.0          68.8           0.0
```

The exact code that makes the reproduction claim wrong is `v5_reach.py:673`: `riser_sweep`
calls the fixed-device `raster_test`, not `indexed_test`. The current default 150 mm design
does separately pass `--indexed` at 100% relaxed on all faces; this finding is about the
false sweep table and command, not a claim that the default placement fails.

`v5_check_spec.py` does not protect most of these values or any membrane geometry/cameras.
Rebuild CELL_SPEC from the current model and extend the checker to cover the hardware that
the build actually requires; do not leave a wrong primary instruction followed by a warning.

### [P1 — wrong] The V5-F “two different CAB_TOP worlds” account is false in current code

`v5_route.py:56-70`, `V5_PLAN.md:1061-1074`, and `LEARNINGS.md:649-655` say
`v5_triage.load_scene()` computes `CAB_TOP=0.220` and that frozen triage thresholds cover
roughly the lower half of each face. The exact current line that refutes the claim is:

```python
# sim_poc/v5_triage.py:428
mujoco.mj_forward(model, data)
```

The body/geom world positions are populated before lines 430-437 compute the extents. Safe,
seed-free probes returned:

```text
v5_triage.load_scene(): CFG_CAB_XY=(0.58, 0.0), CAB_BASE=0.01, CAB_TOP=0.46
RouteCell._tr_globals:  (..., 0.01, 0.46)
```

`git blame` attributes that `mj_forward` line to `c19bac0`, before V5-F. The capture/restore
code currently preserves 0.46, not 0.22. Remove the false causal story and the unnecessary
mutable-global workaround unless a historical commit or reproducible test demonstrates the
claimed 0.22 state. If seed 1500 once changed verdicts, find the actual state difference.

### [P1 — fragile] Published numbers do not reproduce from the documented default CLIs

`CLAUDE.md:22-23` says every station's number reproduces from its own `--eval`. It does not:

- `v5_membrane.py --eval 10` runs only ten honest trials and overwrites the paired 20-row
  artifact; the committed result requires `--sabotage 10`;
- `v5_route.py --eval 12` defaults to spent development seeds 1500–1511 and overwrites the
  28-row headline from 1512–1539; reproducing it requires `--eval 28 --seed0 1512`;
- CLAUDE's protected-baseline instructions list only V5 triage and cleaning, omitting V5-E
  and V5-F despite calling their artifacts recorded results.

Document exact artifact-producing commands beside each baseline and make safe defaults
reproduce—not replace—the committed result. The reviewer did not execute them.

### [P1 — gap] V5-F drops the margins that the hard rules require

The route report stores pass rates, residue, turns, and torque, but not the existing cleaning
force/tilt/raster margins or membrane preload/stall/thread-tracking margins. At
`v5_route.py:115`, only coverage is copied from the cleaning result. Lines 128-130 copy only
turns, torque, and bubble pixels from membrane. `report()` at lines 159-200 reports no
physical margin beyond median turns.

The binding rule is “report the margin, not just the rate.” Preserve the downstream station
metrics in every route row and show at least peak force versus 45 N, tilt versus 30°,
skipped/infeasible raster counts, final/stall preload, and thread-constraint error. A composed
system should not discard the evidence that made its components credible.

### [P2 — wrong] The V5-C planned-contact denominator still excuses infeasible points

The committed clean result contains 136 infeasible points of 3744 planned. The report's
formula at `v5_clean.py:1139-1147` penalizes only `raster_skipped`:

```python
cf_planned = cf.mean() * (1 - rs / max(rp, 1))
ri = sum(r.get("raster_infeasible", 0) for r in ok)
```

Using the artifact's own values, planned-contact is approximately
`0.997850 * (1 - 136/3744) = 96.16%`, not 99.8%. This does not refute 100% soil coverage;
pad overlap can clean a patch whose centre waypoint was declined. It refutes only the label
“contact during planned raster.” Include both skipped and infeasible points in that
denominator.

### [P2 — fragile] The beyond-validity pad sweep still includes unrelated contacts

`v5_check_scene.py:197-198` correctly filters the asserted 0–45 N curve to contacts involving
the pad. The 50–120 N diagnostic at line 220 immediately reintroduces the old defect:

```python
hi.append(max([-c.dist for c in d.contact[:d.ncon]] or [0]))
```

That maximum can come from any membrane, fixture, arm, or pad contact. Apply the same pad-geom
filter. Lines 207-213 also retain a stale “60 N ceiling” explanation while lines 226-228 and
the current result correctly use 45 N.

### [P2 — dead] `v5_clean_diag.py` no longer instruments raster execution

`DiagCell` overrides `move()` at `v5_clean_diag.py:106-143` to populate `self.pts` and
`self.moves`. The current cleaning raster no longer calls `move()`; it calls
`move_planned()` at `v5_clean.py:980` and `1051` (and for all planned approaches/retracts).
`DiagCell` does not override `move_planned`.

Therefore `_pt` is never set for current raster points, `pts` does not contain the promised
one row per raster point, and the move-based tracking diagnostics miss the execution path
they claim to diagnose. Update the hook or mark the script historical so it cannot emit
apparently authoritative empty/partial diagnostics.

### [P2 — overstated] The video caveats omit the two largest implementation shortcuts

The committed videos are valid H.264 at 1280×720/30 fps; the medium video is 62.53 s and the
hard video 3.30 s. The HUD and caveats are legible, and separating `demo_dip` from the
measurement camera is good instrumentation practice. But the on-frame membrane caveat at
`v5_video.py:42-45` says only that geometry is placeholder and bubbles are torque-derived.
It does not disclose that:

- the arm never moves or inserts `mem_elem`; and
- `dip_and_grade()` teleports the bowl into the bin at `v5_membrane.py:244-255`.

The verify caveat at `v5_video.py:40-41` also says the top “is the face cleaning misses” in
the present tense even though the published current cleaning result is 100% with zero missed
spots. Say it was the historically missed face that exposed the first verifier.

The HUD silently slices every value to 68 characters at `v5_video.py:79`, visibly truncating
the medium route plan. Wrap or abbreviate it with an explicit ellipsis. Show at least one
sabotaged/failing leak check if the video is meant to communicate falsification rather than
only the happy path.

### [P2 — fragile] The video duplicates the cap controller instead of calling the measured path

The evaluated controller is `MemCell.tighten()` at `v5_membrane.py:165-207`. The video
reimplements its loop at `v5_video.py:177-200`. Any future stall, timeout, control, or logging
fix can diverge between evidence and footage. Add a frame callback to `tighten()` and render
the evaluated path, as cleaning already does, rather than maintaining a second controller.

### [P2 — wrong/gap] Repository-facing status documents contradict one another

The top of CLAUDE says every V5 phase is done, while the user-facing/current-context docs say:

- `README.md:17-18`: clean is 94.6%, membrane not built;
- `README.md:44-47`: no V5 video and V5-G not started;
- `README.md:55-57`: force open, membrane/routing/video not started;
- `README.md:184-191`: V5-D/E/F/G and force closure are next;
- `PROJECT_CONTEXT.md:21` and `67-69`: only two stations exist and route wiring is absent;
- `RESULTS_V4.md:3-6`: membrane assembly not started.

`README.md:169-171` also says the simulation proves the task mechanically achievable by an
off-the-shelf arm. That is too broad while the new membrane station contains no arm motion,
the hard outfeed is a label, the geometry is placeholder, and the customer's recorded
funding bar is a wet filter clean rather than the V5 dry cabinet wipe.

Choose one honest status vocabulary and update all entry points together. Recommended:
V5-C/D closed; V5-E cap-tightening + synthetic-bubble subtest demonstrated but held-out claim
invalid and manipulation absent; V5-F software route composition demonstrated at 27/28 right
route, physical insert/outfeed absent; V5-G video complete, V5 domain-randomization envelope
open.

### [P3 — wrong] New LEARNINGS entries violate the binding format

CLAUDE requires every significant-change entry to be at most 15 lines with three sections.
The new entries occupy:

- V5-E: `LEARNINGS.md:602-633` — 32 lines;
- V5-F: `LEARNINGS.md:635-662` — 28 lines;
- V5-G: `LEARNINGS.md:664-695` — 32 lines.

They also repeat refuted claims: exact real-thread behaviour at lines 613-616, every route
correct at 637-639, the false 0.22/0.46 account at 649-655, and a “full cycle” at 666-668
that omits the non-manipulation/teleport caveats. Compress and correct them rather than
waiving a binding rule after the fact.

## Safe checks performed

No command below consumes a held-out seed or writes a protected result.

- `v5_check_scene.py`: **ALL PASS**. The printed beyond-validity diagnostic remains subject
  to the unrelated-contact finding above.
- `v5_reach.py --indexed`: **PASS**; relaxed coverage 100% on front/right/back/left/top;
  strict 47.9/14.6/47.9/14.6/29.2%.
- `v5_reach.py --scene`: **PASS** for its fixed-scene criterion; fixed right/back are 0%,
  which is why indexed operation is load-bearing.
- `v5_reach.py --riser`: completed; output quoted in the CELL_SPEC finding.
- `dp_process.py`: completed.
- `v5_check_spec.py`: all displayed numeric, joint-limit, and platter checks passed, then
  the process exited 1 when headless CoreGraphics prevented renderer creation
  (`CGL: invalid CoreGraphics connection`). This is an environment limitation, not evidence
  that the model check failed; the visual portion remains unverified in this session.
- `v5_membrane.py --help`, `v5_route.py --help`, `v5_video.py --help`: completed without
  executing a trial.
- Both main and codex-review worktrees were clean before this report was written.

## What the changes did well

- The committed artifacts retain per-seed rows; that transparency is what made the 1517
  contradiction directly auditable.
- V5-F reuses the measured cleaning and membrane classes rather than copying those station
  implementations. Route-plan compliance really is 28/28 under its narrow definition.
- The V5-E prose clearly labels placeholder geometry, logged pressure state, synthetic
  bubbles, inferred pressure hold, and the project-chosen torque. The remaining task is to
  make the phase name and metric scope as narrow as those caveats.
- The V5-G HUD puts caveats on the image, stamps speed-up, and correctly separates a demo
  camera from the calibrated measurement camera.
- Current V5-C/D evidence remains the strongest part of V5: all-five-face cleaning, zero
  residue on the committed set, peak 34.5 N below the 45 N model-validity ceiling, and a
  second-camera verifier with an explicit false-verify arm.

## Competing closeout plan

1. **Correct claims before adding code.** Change V5-F to 28/28 plan compliance and 27/28
   right-route/end-to-end; correct CLAUDE, V5_PLAN, README, PROJECT_CONTEXT, RESULTS_V4,
   CELL_SPEC, LEARNINGS, and the video caveats as one documentation transaction.
2. **Repair the seed ledger.** Mark 1400–1409 as V5-E development and 1604/1607 as demo-
   inspected. Reserve a genuinely unseen contiguous range only after metrics, controller,
   scene, and sabotage matrix are frozen.
3. **Choose V5-E's real scope.** The fast honest close is “torque-limited cap proxy plus
   synthetic-bubble visibility check.” A full Stage-10 close requires membrane pick,
   insertion, engagement, physical carry/dip, and CAD-derived geometry.
4. **Make the verifier independent.** Add high-torque bad-seal and camera-blindness cases;
   separate leak scenario truth from the image rendered from it.
5. **Reconcile the screw mechanics.** Enforce or remove the four-turn stroke, report loaded
   pitch error, and measure O-ring versus rim torque contribution. The current 5.9 N·m
   derivation mixes O-ring force with the rim's coefficient/radius.
6. **Fix composition metrics and margins.** Require `grade == truth` for end-to-end and
   carry clean force/tilt/raster plus membrane preload/thread/stall margins into route stats.
7. **Finish the V5-G exit definition.** Have the builder run the predeclared V5 perturbation
   sweep on fresh seeds and publish the actual station envelope. The reviewer does not run
   evals.
8. **Regenerate the build document.** Make CELL_SPEC internally singular—one current tool,
   one standoff, current cameras/stations, checked live values—and expand `v5_check_spec.py`
   so a green gate protects the real build-critical fields.

## Highest-value three actions

1. Retract/correct 28/28 end-to-end and the “all phases done” claim before either reaches a
   founder or hardware decision.
2. Decide whether V5-E is a narrow cap/bubble proxy or full membrane assembly; then use an
   independent sabotage matrix and genuinely fresh seeds.
3. Rebuild CELL_SPEC and produce the missing V5 domain-randomization envelope before any
   hardware is sourced.

## Not verified in this review

- No protected v2/v3/v4/V5 eval or baseline reproduction was run, by explicit role rule.
- No calibration, render command, scene generation, or seed-bearing single trial was run.
- The visual portion of `v5_check_spec.py` could not run in the headless session.
- No real hardware, CAD, fluid/gas physics, detergent chemistry, torque specification,
  Easy/Medium/Hard definition, rectification cost model, or V5 tolerance envelope exists in
  the reviewed evidence.
- The LeRobot export remains structurally validated only, not round-tripped through the real
  LeRobot library, as the repository already discloses.
