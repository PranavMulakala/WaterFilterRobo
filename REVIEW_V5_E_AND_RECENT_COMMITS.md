# Review: recent commits and V5-E work in progress

**Reviewer role:** static/adversarial review only. I did not run any eval, render, calibration,
or held-out seed. I did not modify `main`.

**Committed range reviewed:** `72409d0..1aa12e7`.

**Moving WIP snapshot reviewed (2026-08-05):**

- `sim_poc/v5_membrane.py` blob `58f593afb9dcab8be4a03a37d425a3fe708244b4`
- `sim_poc/make_scene_v5.py` blob `8a9f1d1fb8f1a9a2e1540dc39deb8c9b22ebbe37`
- generated XML blob `deae495ea3c88bd467f2aa4a77d444f6b4ff8b65`
- `stats_v5_membrane.json` blob `d3e3308e4b274eae0eec55c941b620a582a573ee`

The main worktree was changing during review. Findings about WIP are therefore tied to those
blob IDs, not to an eventual commit.

## Findings

### [P0] Seeds 1400–1409 are tuning seeds, not one-shot held-out evidence

The first stats snapshot inspected during this review reported the same honest result for all
ten seeds: 10.0578 turns. The builder then changed the unit randomization and reran the same
1400–1409 range; the later stats blob reports a 9.13–10.02-turn spread.

The WIP plan simultaneously says:

- `V5_PLAN.md:969`: “fresh seeds 1400–1409, paired, looked at once”; and
- `V5_PLAN.md:1009-1014`: the first ten-run result was inspected, found to be effectively
  n=1, then fixed by adding O-ring/thread variation.

Both cannot be true. The first result informed the code change, and the same seeds were then
rerun. Per the binding seed ledger, 1400–1409 must be recorded as spent debugging/calibration
seeds. They cannot support the final V5-E rate. Allocate a new untouched range only after the
controller, scene, grading rule, success criteria, and sabotage matrix are frozen.

### [P1] V5-E is documented as membrane assembly but never inserts the membrane

`v5_membrane.py:1` describes “element into bowl,” and `make_scene_v5.py:677` calls
`mem_elem` “the membrane element the arm inserts.” The actual cycle at
`v5_membrane.py:309-316` does only:

1. reset;
2. tighten the already-engaged cap;
3. set logged pressure state;
4. reveal bubble proxies; and
5. teleport/dip/grade.

`mem_elem` is jittered at `v5_membrane.py:123-125`, but no later code reads or moves its body.
The WIP plan partially discloses that the arm does not manipulate the station, but then V5-E
should be named and closed as a **threaded-cap + rendered-bubble subtest**, not “membrane
assembly, Stage 10.” Prior v3/v4 pick-and-place success does not prove insertion of this new
part into this new placeholder bowl with its own clearances.

### [P1] The false-pass test is circular and cannot falsify the seal model

The code defines seal truth directly from torque:

```python
# v5_membrane.py:223
"seal_holds": bool(tq >= self.mcfg.torque_pass_nm)
```

It then uses that exact boolean to create the observation:

```python
# v5_membrane.py:232-233
self.m.geom_rgba[g][3] = 0.0 if holds else 0.85
```

Finally, it calls the same boolean `truth_seal` and measures false pass against it at
`v5_membrane.py:322-331`.

Therefore the 10/10 sabotage result tests only whether the camera threshold sees bubbles that
the torque threshold commanded the renderer to show. It does not test whether torque predicts
a seal, pressure is retained, or the O-ring physics leak. The proxy disclosure is good, but
“false pass” must be scoped to **synthetic bubble visibility**, not leak verification.

A meaningful rival sabotage matrix must break the shared cause: missing/damaged O-ring or a
false torque stall while bubbles are independently present; camera occlusion/lighting while
bubbles are present; and a sealed/no-bubble negative control. Otherwise verifier and oracle
are two views of the same boolean.

### [P1] The reported turn count violates the claimed 2 mm/turn screw relation under load

The plan claims at `V5_PLAN.md:950-952` that the cap is tied by
`cap_z = -(pitch/2pi)*cap_rot` at 2 mm/turn and cites a low-load tracking check of -6.315 mm
versus -6.266 mm. The actual published-candidate rows do not maintain that relation.

Example from `stats_v5_membrane.json`, reconstructing the initial cap phase using the exact
RNG sequence at `v5_membrane.py:122-138`:

- seed 1400 starts at -0.200631 mm from the randomized engaged phase;
- 9.9743706 driven turns at 2 mm/turn imply a final -20.149372 mm;
- recorded final `cap_z` is -17.086809 mm;
- constraint error: 3.062563 mm, or 15.20% of expected final travel.

Across the ten honest rows, the error is 14.93–15.34%. The exact code that reports the two
inconsistent workpiece values is `v5_membrane.py:157-159` (turns) and
`v5_membrane.py:199-202` (`cap_z_mm`). The exact claimed coupling is generated at
`make_scene_v5.py:741-747`.

Until this is resolved, “achieved turns” is not a reliable physical margin. Either make the
screw constraint sufficiently rigid and verify error under peak seal load, or report the
thread-constraint error beside turns and stop calling it an exact 2 mm-pitch screw.

### [P1] The declared four-turn driver stroke is comment-only and contradicted by the result

`make_scene_v5.py:91` declares `MEM_TURNS_MAX = 4.0  # driver stroke, turns`. Its only use is
the XML comment at `make_scene_v5.py:743-744`. It does not constrain a joint or controller.
`cap_rot` is unlimited, while `cap_z` permits 30 mm of negative travel at
`make_scene_v5.py:666-667`, equivalent to about 15 turns at the claimed pitch. The WIP
controller accepts up to 14 turns, and the proposed headline reports a 9.68-turn median.

Thus the model currently succeeds only by exceeding its declared driver stroke by about 2.4x.
Remove the false four-turn hardware claim or enforce it and redesign the starting geometry/
stroke. Do not publish both.

### [P1] The 5.9 N·m “friction against preload” calculation mixes two contact systems

`V5_PLAN.md:965-967` claims `178 N * 1.1 * 0.030 m ~= 5.9 N.m`, presenting this as a
cross-check that the measured driver torque comes from the reported seal preload. Those three
terms do not describe the same contacts:

- `v5_membrane.py:109` and `147-155` define `seal_load()` using only `mem_oring*` contacts;
- the explicit cap-to-O-ring pair uses friction **0.9** at `make_scene_v5.py:709-710`, and
  the O-ring mean radius is 0.028 m at `make_scene_v5.py:92`;
- friction **1.1** and radius about 0.030 m belong to the separate hard-rim contacts at
  `make_scene_v5.py:712-713`, which `seal_load()` does not measure.

Using the measured O-ring terms gives about `178 * 0.9 * 0.028 = 4.49 N.m`, not 5.9 N.m.
The unreported rim contact may supply the remainder, but that must be measured rather than
borrowing its coefficient while retaining the O-ring's force. The exact code line that makes
the published derivation invalid is the O-ring-only filter at `v5_membrane.py:150-154`.
Report a contact-torque breakdown (O-ring versus rim) before claiming the 6 N.m actuator limit
is independently explained by modeled friction.

### [P2] “Contact over planned raster” omits the infeasible points it says it penalizes

In committed `v5_clean.py`, `cf_planned` discounts only `raster_skipped`:

```python
# current main v5_clean.py:1139-1148
rp = sum(r.get("raster_planned", 0) for r in ok)
rs = sum(r.get("raster_skipped", 0) for r in ok)
cf_planned = cf.mean() * (1 - rs / max(rp, 1))
ri = sum(r.get("raster_infeasible", 0) for r in ok)
```

But `ri` is also a set of planned points the station declined to execute. The committed stats
contain 136 infeasible points of 3744 planned, while the report still gives those points full
credit in `contact_planned`. Using the code's own aggregate numbers, the honest planned-contact
figure is approximately `99.785% * (1 - 136/3744) = 96.16%`, not 99.8%.

Coverage may still be 100% because pad overlap can clean a spot without centre-point contact;
this finding refutes only the planned-contact number, not the coverage result.

### [P2] The beyond-validity pad sweep still measures every scene contact

Commit `1aa12e7` correctly filters the asserted 0–45 N pad curve to contacts involving the
pad geom at `v5_check_scene.py:197-198`. The 50–120 N diagnostic immediately below still does:

```python
# v5_check_scene.py:220
hi.append(max([-c.dist for c in d.contact[:d.ncon]] or [0]))
```

That maximum includes unrelated membrane, fixture, and arm contacts, so the printed high-load
curve can change when unrelated scene geometry changes—the exact defect the low-load comment
says was fixed. Apply the same pad-geom filter to the high sweep before treating 50/55/60 N
values as evidence about the pad. Lines 207–213 also retain the superseded “60 N ceiling”
comment while lines 224–228 print 45 N.

### [P2] The new learning entry violates its binding format and overstates placeholder fidelity

The appended `LEARNINGS.md:602-633` entry is 32 lines, despite `CLAUDE.md` requiring every
significant-change entry to be at most 15 lines with three sections. It also says at
`LEARNINGS.md:613-616` that the cap moves 2 mm per turn and compresses the O-ring “exactly as
the real one does.” That conflicts with both the placeholder-geometry disclosure and the
15% loaded thread-constraint error above. Compress the entry and change the claim to what was
actually modeled: an invented 2 mm-pitch proxy compressing a discrete-sphere O-ring proxy.

## What the recent commits did well

- `176956a` retracts the unreproducible 92.8% two-view V4 claim rather than defending it.
- `4259066` exposes the first V5-D verifier as blind to the top face and adds a dedicated
  camera; reporting false verifies beside sabotage catches is the right discipline.
- `7a7d2cf` and `d013091` diagnose IK branch discontinuity rather than tuning around its
  effects, and report the tilt cost of continuity.
- `1aa12e7` correctly distinguishes a 45 N model-validity ceiling from a component rating and
  labels placeholder membrane geometry, logged pressure state, and bubble proxies.

Those strengths make the remaining V5-E overclaims especially fixable: the repo already has
the vocabulary and culture needed to narrow the claim honestly.

## Competing closeout plan

1. Mark 1400–1409 spent for V5-E development. Do all remaining iteration at 9000+.
2. Decide the actual V5-E scope:
   - **narrow close:** torque-limited threaded-cap proxy + synthetic-bubble camera check; or
   - **full close:** add and verify membrane pick/insertion plus cap/dip sequence.
3. Reconcile the 4-turn declaration, allowed 14 turns, cap start height, and required travel.
4. Add a thread-tracking assertion under peak seal load; report max pitch error, not one
   low-load example.
5. Split the oracles:
   - tightening truth from measured torque/preload/travel;
   - bubble-presence scenario independent of the image grader;
   - never describe the synthetic bubble oracle as gas/leak physics.
6. Freeze a sabotage matrix that includes a high-torque bad-seal case and a verifier-blindness
   case, not only early cutoff.
7. Have the builder run the required scene/spec/reach gates and protected baseline evals after
   the scene/controller is frozen. The reviewer does not run them.
8. Allocate a new one-shot range (provisionally 1500–1509 if still untouched), record it in the
   ledger before use, run once, inspect once, and publish margins plus rates.
9. Fix the two committed reporting/gate defects above independently of V5-E so V5-C's force
   evidence remains auditable.
