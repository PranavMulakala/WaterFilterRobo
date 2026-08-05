# Review: post-video V5 fixes through `11f9ea9`

**Verdict:** the original V5-F metric defect is correctly fixed, and the latest V5-E
commit adds a genuine robot-performed membrane-element insertion. The current headline is
still overstated in two different ways:

1. **`end-to-end 26/28` is not physical end-to-end success.** Four of those 26 successes
   are HARD routes whose only post-triage action is an unbacked string. The largest
   physically backed count in the committed 1700–1727 artifact is **22/28** (12 EASY plus
   10 MEDIUM), with the leak portion explicitly remaining a model proxy.
2. **V5-G no longer follows the evaluated membrane path.** `reset_mem()` now removes the
   cap, but `v5_video.py` neither inserts the element nor presents the cap before driving
   its joint. The committed video predates the insertion commit. It is not a video of the
   current full route.

The repository therefore should not say that every V5 phase is complete or that the
remaining work is “not code.” The metric repair is good; the physical and integration
claims still need narrower language or implementation.

**Reviewer scope:** static/adversarial review only. I rebased the isolated `codex-review`
worktree onto current `main` and reviewed `c394900..11f9ea9`. I did not run an eval,
calibration, render, seed-bearing trial, or any command that writes a protected baseline.
I did not modify `main`.

## 1. Original metric repair

The old 28/28 was wrong. `plan` came from the predicted grade, and `routing_ok` compared the
declared trace against that prediction-selected plan. Seed 1517 was truth EASY, predicted
MEDIUM, yet the wrong MEDIUM trace matched its own plan. The correct count for that old
artifact was **27/28 right-route**, not 28/28.

The repair is logically correct and preserves the distinction between route choice and
route execution:

```python
# sim_poc/v5_route.py:244-266
out["routing_ok"] = bool(steps_done == list(plan))
out["grade_correct"] = bool(grade == truth)
...
out["end_to_end"] = bool(out["grade_correct"] and out["routing_ok"] and steps_ok)
```

`routing_ok` was not redefined to duplicate `grade_correct`; no classifier or success
threshold changed in this metric fix; and no reviewed code special-cases seeds. The
committed replacement artifact is internally consistent: compliance 28, right-route 26,
end-to-end 26, with seeds 1701 and 1715 both MEDIUM→HARD.

The freshness claim for 1700–1727 cannot be proved from a committed artifact alone, but the
chosen range correctly avoids the watched demo seeds 1604/1607. A seed is spent when its
outcome is observed, regardless of whether the observer wrote a results file.

### Binomial claim

At an error probability of 0.025 over 28 independent trials:

```text
expected errors = 28 × 0.025 = 0.7
P(exactly 2)    = C(28,2) × .025² × .975²⁶ = 0.1223
P(2 or more)    = 1 - .975²⁸ - 28×.025×.975²⁷ = 0.15445
```

So “26/28 is statistically consistent with 97.5%” is fair in the narrow
failure-to-reject sense. It does **not** establish that the classifier did not regress;
28 units have little power to distinguish 92.9% from 97.5%. Applying the same reasoning to
old 27/28 and new 26/28 is even-handed only if the conclusion is “neither small sample
estimates a 2.5% error rate precisely.” Using it to say “not a regression” as an affirmative
fact would be unfalsifiable positioning.

## 2. `end-to-end 26/28` remains physically overstated

The exact line that makes every HARD route's downstream work pass is:

```python
# sim_poc/v5_route.py:260-266
if route == "hard_non_rectifiable":
    steps_ok = True
...
out["end_to_end"] = bool(out["grade_correct"] and out["routing_ok"] and steps_ok)
```

The only claimed downstream action is created by appending its name:

```python
# sim_poc/v5_route.py:180-183
if route == "hard_non_rectifiable":
    steps_done.append("ROUTE_TO_SCRAP_APPROVAL")
    out["scrap_gate"] = True
```

There is no robot, indexer, conveyor, or fixture motion delivering the unit to a gate.
The current stats artifact contains six predicted-HARD routes. Four are correctly graded
HARD units (1702, 1703, 1707, 1724), and all four count as end-to-end successes solely
because `steps_ok = True`. The two MEDIUM→HARD errors correctly fail `grade_correct`.

Therefore the defensible split is:

- declared-trace conformance: **28/28**;
- right-route: **26/28**;
- reported software end-to-end under the current definition: **26/28**;
- routes with no unbacked claimed action: **22/28 maximum**;
- HARD physical handoff: **0/6 implemented, 0/4 among right-route successes**.

The question “is this a larger or smaller overstatement than the retracted 28/28?” is
ambiguous. Against the one-error **metric** defect, the current physical overstatement is
larger: four unsupported successes versus one misclassification. Against the original
literal physical claim, it is smaller: the old artifact had only 11 EASY routes with no
unbacked action, because both its 10 MEDIUM insertions and seven HARD handoffs were bare
strings; the new implementation raises the physically backed maximum from **11/28 to
22/28**.

Prominent disclosure is acceptable for an intentionally scoped software-decision demo.
It is not a fix for a physical routing claim. Labelling does not change the 28/28 number;
it changes its required name and scope. Until the handoff exists, do not call 26/28 “right
route AND every step succeeded.”

## 3. “Route-plan compliance” is too strong a name for its evidence

The equality itself would fail if a step name were omitted, duplicated, or reordered:

```python
# sim_poc/v5_route.py:249-250
out["steps_done"] = steps_done
out["routing_ok"] = bool(steps_done == list(plan))
```

But the same controller selects `plan`, executes the branch, appends the fixed strings, and
scores that list. No omission/order fault-injection test exists in the reviewed repository.
Testing list mutation alone would prove Python list equality, not that a physical action
occurred. The current 28/28 shows that all selected branches emitted their expected trace
over this sample; it does not independently establish execution.

This is not mere pedantry because “compliance” ordinarily suggests the commanded work
happened. Prefer **declared-trace conformance**. If the existing name is retained, its
narrow definition must travel with every number, not appear only after the headline.

`PASS` should be classified as `META` or excluded from the evidence denominator. Calling a
bookkeeping terminator `UNBACKED` is technically candid but categorically noisy; it makes
all EASY/MEDIUM routes look as if they contain an unbacked action and dilutes attention from
the actual missing HARD handoff.

## 4. The leak result is a measured image of a modelled outcome

The code does not independently determine whether a seal leaks. Torque defines truth:

```python
# sim_poc/v5_membrane.py:386-399
def pressurise(self, tq):
    ...
    "seal_holds": bool(tq >= self.mcfg.torque_pass_nm)
```

That same boolean creates the bubbles:

```python
# sim_poc/v5_membrane.py:401-409
def emit_bubbles(self, holds):
    ...
    self.m.geom_rgba[g][3] = 0.0 if holds else 0.85
```

The pixel classifier at lines 445–482 is a real measurement of the rendered image, and the
dip pose is represented, albeit by teleport at lines 420–431. Thus it is fair to call
`VERIFY_LEAK` a measured **synthetic-bubble visibility** result. It is not fair to treat
10/10 as validation of leakage, pressure retention, torque→seal causality, or fluid
behaviour. The full leak-test outcome remains only as good as the unvalidated torque→bubble
model. A useful falsification matrix needs independent scenario truth: damaged/missing
O-ring at high torque, false torque stall, forced bubbles at nominal torque, no bubbles on
a known-good seal, and camera occlusion/lighting changes.

## 5. The membrane insert is genuine, but its success criterion is weak

`insert_element()` now performs real robot motion: it picks the free element, carries it,
aligns using measured element pose, lowers it into the open bowl, releases, retracts, and
then measures the element relative to the bowl. The route artifact was regenerated after
this code landed and contains `elem_inserted=true` for all ten MEDIUM routes. Calling the
narrow step `MEMBRANE_INSERT` MEASURED is honest.

The cap toggle does not turn that step into a fake. `cap_present(False/True)` is an idealized
external fixture action, and cap presentation is not listed as a robot step. That is a
legitimate de-scope if the claimed cell scope is explicitly “robot inserts element into an
open bowl; fixture presents an already-threaded cap; station tightens it.” It becomes fake
when compressed to “the robot performs membrane assembly” or “full autonomous route,” as
several entry-point documents and the video framing still do.

However, the 10/10 insertion rate is not yet strong evidence for a 1.5 mm-clearance task.
The exact acceptance thresholds are four to eight times wider than the cited clearance:

```python
# sim_poc/v5_membrane.py:84,90-91
align_tol_m: float = 0.0010       # against 1.5 mm radial clearance
seat_tol_m: float = 0.006
seat_z_max: float = 0.012

# sim_poc/v5_membrane.py:311-315
xy = float(np.linalg.norm(p[:2] - self.bowl_axis_xy()))
out["inserted"] = bool(xy < mc.seat_tol_m and abs(dz) < mc.seat_z_max and up > 0.95)
```

The fresh artifact's worst settled offset is **1.537 mm**, already just beyond the claimed
1.5 mm radial clearance, yet it passes because the actual threshold is 6 mm. The route
artifact reaches 1.588 mm and also passes. Reporting pre-release alignment against the
clearance while scoring post-release seating against 6 mm flatters the result.

Other undetected failure modes:

- The element is measured before cap presentation and tightening. `run()` caches `ins`,
  then materializes the cap and tightens it at lines 485–504; it never re-measures element
  retention, pose, collision, or damage afterward.
- Bowl position relative to its fixture is not part of success. Element and bowl may move
  together and still have a good relative `xy`.
- No insertion force/contact impulse, rim strike, penetration, or gripper-slip margin is
  reported.
- Upright `> 0.95` allows about 18.2° tilt, with no derivation against the narrow bore.
- Insertion variation is mainly ±4 mm nest XY; bowl pose, dimensions, fixture error, part
  tilt/height, and contact properties are not swept for this task.

Ten successes are a useful smoke demonstration, not a reliability claim. With 0 failures
in 10, the exact one-sided 95% lower bound on success is only about **74%**. Freeze a
physically derived criterion, add failure injections, then let the builder use genuinely
fresh seeds.

## 6. The paired 1400–1409 control is legitimate but does not prove “physics untouched”

Reusing known seeds as a paired regression diagnostic is sound. It is not held-out evidence,
but it no longer needs to be once the headline is moved to an unseen range. This is a
legitimate role change, not cheating, provided 1400–1409 remain permanently labelled
development/diagnostic and never re-enter a generalization claim.

What the pair establishes is narrower: on ten known scenarios, selected outputs remained
close after insertion was added (turns, torque, preload, stall, and current sabotage
verdict). It cannot establish that the physics is untouched. It would miss transient
contacts, cap-materialization impulse, final element displacement, bowl movement, loaded
thread-constraint error, unreported forces, different random inputs, and failures outside
those ten seeds. The code path and state sequence plainly changed, even though the scene XML
did not.

The committed artifact proves that rows 1800–1809 were recorded; it cannot prove those
seeds were never previously run or observed. That historical freshness claim is
**UNVERIFIABLE from Git alone**.

## 7. Latest changes did not reach the video or all status documents

### [P0 integration] V5-G now drives an absent cap and omits insertion

The latest V5-E reset explicitly removes cap collisions and visibility:

```python
# sim_poc/v5_membrane.py:171-175
# THE BOWL ARRIVES OPEN.
self.cap_present(False)
```

The V5-G path calls that reset and immediately starts its duplicated tightening loop:

```python
# sim_poc/v5_video.py:173-183
if route != "easy":
    c.reset_mem(seed)
    ...
    c.d.ctrl[c.capdrv] = mc.drive_rate
    mujoco.mj_step(c.m, c.d)
```

It never calls `insert_element()` or `cap_present(True)`. The absent/non-colliding cap can
eventually stall on its joint limit, and `pressurise(tq)` can then call that a held seal
because seal truth is torque alone. Line 202 unconditionally writes `STALLED` into the HUD
after the loop even if the stall predicate never held.

Commit `11f9ea9` changed neither `v5_video.py` nor either MP4. The committed medium video is
from `c394900`, when membrane insertion did not exist. README lines 49–51 call it the
current full route and line 71 says the current script regenerates it. Both claims are now
false. Fix the render path by using the evaluated methods with frame callbacks, re-render
on the already-burned demo seed, and put the fixture-presented-cap caveat on-frame.

### [P1 reproducibility] V5-E's default still reproduces the obsolete 1400 result

The published result is now the paired 1800–1809 artifact, but:

```python
# sim_poc/v5_membrane.py:594-600
ap.add_argument("--seed0", type=int, default=1400)
```

README lines 136 and 141–145 explicitly tell readers that bare `--sabotage 10` reproduces
the published number and name 1400 as its default. It instead overwrites the new baseline
with the known diagnostic range. This directly contradicts CLAUDE lines 36–37 (“Every
station's number ... reproduces from its own `--eval`”). Change the default and documented
artifact-producing command to 1800 only after protecting the ledger.

### [P1 ledger/docs] 1800–1809 are missing from the ledger and stale claims remain

CLAUDE's seed ledger at lines 130–142 marks ranges only through 1727 plus demo seeds; it does
not mark 1800–1809 spent. “Start at 1728” is unsafe as a general allocation instruction
because a sufficiently large range can overlap the new baseline. Reserve 1800–1809
explicitly and allocate the next range by named phase, not a floating start alone.

Current contradictions include:

- `V5_PLAN.md:1019-1055` still calls 1400–1409 fresh and says the arm does not manipulate
  in V5-E, directly contradicting the new section above it.
- `V5_PLAN.md:1246-1249` says V5-E reproduces exactly at the obsolete 9.68-turn result.
- `README.md:21-25,82` still publishes the old 9.68-turn, pre-insertion result.
- `PROJECT_CONTEXT.md:21,67-69` and `RESULTS_V4.md:3-6` still say membrane assembly and
  route wiring do not exist.
- `README.md:226-248` says all V5 work is done and remaining work is not code, despite the
  broken current video path, unbacked HARD handoff, missing V5 robustness sweep, and stale
  build spec.

These are not harmless archival notes: README is the customer-facing entry point,
V5_PLAN is the plan of record, and CELL_SPEC claims to be the build document.

## 8. Process verdict

The most serious process failure was declaring completion before identifying and reading
the complete source audit. It allowed a locally correct metric patch to be published while
the same headline still contained unbacked actions. The impossible cap-retraction advice,
two wasted control prototypes, and inverted CAB_TOP story are all versions of the same
habit: proposing or explaining before establishing the full physical/evidentiary state.

The most useful single corrective habit is an **evidence map before action**: inventory the
entire acceptance source; for every claimed step, identify the physical actor, feasible
swept volume, independent workpiece measurement, failure injection, seed status, and
customer-facing wording. Only then recommend a mechanism or declare completion.

The self-reporting is credible because the repository contains the failed approaches,
retractions, exact counterexamples, and accepted audit findings. It becomes performative
where candid disclosures coexist with unchanged headlines such as “all phases DONE” and
“end-to-end ... every step succeeded.” Candor is valuable evidence of process; it is not a
substitute for closing or narrowing the claim.

## Priority plan for the builder

1. **Correct the headline now.** Publish 28/28 declared-trace conformance, 26/28 right-route,
   and **22/28 routes without an unbacked claimed action**. Report HARD handoff as 0/6
   physically implemented until motion exists. Do not spend a new seed to correct wording.
2. **Repair V5-G integration.** Make video call the same insertion/tightening controller as
   evaluation, with frame callbacks; present the cap explicitly as a fixture action;
   re-render the already-burned 1607 demo; show the actual insertion and caveat.
3. **Freeze a physical insertion criterion.** Tie final XY/tilt/Z limits to geometry, verify
   the element after cap presentation and tightening, check bowl fixture pose and contact
   margins, and add omission/misalignment/slip/cap-collision sabotage tests.
4. **Fix reproducibility and the ledger.** Mark 1800–1809 spent, make the V5-E default
   reproduce that paired artifact, and reconcile README, V5_PLAN, PROJECT_CONTEXT,
   RESULTS_V4, CLAUDE, LEARNINGS, and CELL_SPEC in one docs pass.
5. **Choose physical scope.** Either implement a real handoff/outfeed and cap-presentation
   fixture, or narrow the demo to a software route decision plus fixture-assisted membrane
   substation. Both can be honest; the current hybrid headline cannot.
6. **Finish the predeclared V5-G robustness envelope and rebuild CELL_SPEC.** Only the
   builder should run the required evals, after criteria and seed allocations are frozen.
7. **Independently falsify the leak proxy** before treating it as more than synthetic-bubble
   image verification.

## Bottom line

- **Metric fix:** correct, distinct, and internally measured honestly; statistical wording
  is acceptable only as “not enough evidence to distinguish,” not proof of no regression.
- **Membrane insert:** a genuine new robot capability under a clearly fixture-assisted
  scope, but 10/10 is weak and its 6 mm success threshold does not support the 1.5 mm
  clearance framing.
- **End-to-end 26/28:** not trustworthy as literally stated; **22/28** is the maximum count
  with no unbacked claimed action, and even those include a declared leak proxy.
- **Completeness:** overstated. The latest change broke/staled the video path, left the seed
  default and ledger inconsistent, retained an unbacked HARD handoff, and did not complete
  the planned V5 robustness sweep or build-spec repair.
