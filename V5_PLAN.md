# v5 Plan — the three-stage funded demo

Written against the **real** process: 13 Waterwala Labs work instructions (Ref
0024DPCRO001–0010, 0024DPNAP0008, + 3 QC flow pages, R0, 11-04-2024). The process
model is checked in as [sim_poc/dp_process.py](sim_poc/dp_process.py) — data only,
transcribed from the source PDFs, with our engineering judgement clearly separated
from their text. Run it for a dump.

**Baselines confirmed before planning anything** (2026-08-04, MuJoCo 3.11.0 /
numpy 2.5.1 / Python 3.12.13):

| | result |
|---|---|
| `sim_poc2.py --eval 25` | **100%** locked (25/25) |
| `sim_poc3.py --eval 25` | **100%** full swap (25/25) |
| `sim_poc4.py --eval 60 --seed0 200` | inspection **86.7%**, false-clean **0.0%**, routing **100%**, end-to-end **86.7%**, all three routes 100% |

All three reproduced the committed `stats*.json` **byte-identically**, which is a
free reproducibility check on the pinned stack.

---

## Two corrections to the brief, from the primary sources

Both change what v5 should build, so they come first.

**1. Stage 10's cap is a THREADED cap, not a bayonet.** Our twist-lock is a 55°
indexed bayonet — push in, rotate a fixed angle, two lugs capture under a rim. The
work instruction (3.5) says *"Ensure the cap is tightened properly with the spanner"*
onto a `MEMBRANE BOWL` / `MEMBRANE CAP` pair with threaded ports. That is **multi-turn
rotation terminated by a torque criterion**, not a fixed-angle twist. The *class* of
problem transfers (align → insert with clearance → rotate to secure); the *motion* does
not, one-to-one. The analysis doc's "nearly one-to-one" is a little generous and we
should not say it in the room without this qualifier.

**2. The dip is a pressurised bubble test, not a wash.** The brief has
`membrane → bowl → cap tighten → dip → verify`. The source (3.6 → 3.7) inserts a step
we were missing: *plug the permeate outlet with an END PLUG, close the reject outlet
with a BALL VALVE, pass 80–90 PSI air into the cap head inlet* — **then** dip and watch
for bubbles. This is good news. It means the camera check at the end of our cycle is
**their own acceptance criterion**, not a verification we invented to have something to
measure. It also gives the demo a pass/fail that is *physically caused* — under-tighten
the cap and it must bubble — instead of asserted.

**The gap that constrains everything else — and it is worse than "a missing annexure".**
Stage 1 and the QC flow both name Easy/Medium/Hard. On the **rendered** flow chart, the
VISUAL INSPECTION fan-out has **no annexure attached to it at all**. The Annexure 1
ellipse hangs off `CABINENT / STICKERS CHECKING`, a later node fed from UNIT TESTING —
it is a cabinet/sticker cosmetic accept-reject spec, not the triage definition.

So the honest statement is stronger than the one we started with: **the class names are
DrinkPrime's, and the class boundaries are undocumented in this set, full stop.** Not
"deferred to a document we don't have" — deferred to nothing. The two *features* are
theirs and named explicitly — "Check Chassis for dent & scratches" and "Check crimping
should be perfect" — so we can grade a real, named defect and be honest that only the cut
points are ours. Every artifact reporting a triage number must carry that sentence.

The nearest thing to a definition is Stage 1 §8's "Allow & Not allowed Spec. & visual
Photo to provided to the line," which is a separate artifact that was not sent. **So the
top ask is open-ended, not "send Annexure 1"** — asking only for Annexure 1 returns a
cabinet cosmetics spec and does not answer the founder's own image-processing bar.

*This correction cost nothing to find and would have been expensive to miss: our first
transcription was built from text extraction of a pure-vector flow chart, which drops
every edge. **8 of the 13 annexure bindings were wrong**, including this one. See
PAIN_JOURNAL 2026-08-04.*

**A third correction, to the route table.** `HARD` is not a dead end. Their chart forks
it: `RECTIFIABLE` rejoins the same line as MEDIUM, and `NON RECTIFIABLE` goes to
SEND FOR SCRAP APPROVAL (rectification cost greater that 80–90%). `V5_ROUTES` now has
`hard_rectifiable` and `hard_non_rectifiable` as separate routes.

**And a contradiction we must not resolve by guessing.** The assembled-device leak test
is **45 PSI** in Stage 4 CHECKS and Stage 6 (Stage 4 adds "as per BIS"), but the QC flow's
`FINAL LINE TEST` is **80 PSI** for what looks like the same operation. That is 1.8×, and
it changes the regulator, the fixture, the containment and the safety case. Recorded in
`CONTRADICTIONS`, not reconciled. **Ask before building any leak-test station.**

---

## The three stations

### Station 1 — TRIAGE (Stage 1 / QC entry node)

Classify an incoming **unit** Easy / Medium / Hard from rendered pixels.

**The key design call: move the camera, not the part.** Every grip finding in this repo
came from holding a part up to a fixed camera, and a cabinet is far too big and heavy
for that. The unit sits on the bench and the arm orbits the **wrist camera** around it.
This needs no grasp at all, which deletes the entire cap-grip failure mode from the
riskiest new station. It is also what a real cell would do.

The classifier architecture carries over unchanged and has earned it: two views,
explainable HSV + region statistics, thresholds frozen on calibration seeds 9000+
**presented in-cell**, evaluated on disjoint held-out seeds.

- **Dangerous error is `false-Easy`** — a unit needing deep work sent down the fast
  path. Report it separately and tune toward the safe side, exactly as false-clean was.
- Ground truth stays crisp (non-overlapping defect counts); the measurement difficulty
  comes from occlusion, lighting and pose, not from fuzzing labels.
- Defect features are theirs: dents/scratches on the chassis, discoloration.

### Station 2 — CLEAN (Stages 2 and 3)

An exterior wipe/polish pass over the cabinet with a tool-mounted pad.

**Their spec hands us the metric.** Stage 2: *"Thoroughly clean the exterior of the
device, ensuring all surfaces are covered."* Stage 3 QC: *"check for any missed spots
during cleaning."* So the number is **surface coverage %**, and it is their criterion,
not one we picked because it was easy to compute.

The real physics content is **maintaining contact while moving laterally**. On a
position-controlled arm you get that by commanding a small deliberate over-travel into
the surface and letting contact resolve it: too little and the pad lifts and misses
patches, too much and you stall the arm or shove the cabinet. That trade-off is
measurable, is a genuine robotics lesson, and is the first thing I expect to eat time.

- Discretise the target face into patches; a patch counts as cleaned when the pad
  passes within tolerance **and** normal force is inside the band.
- Verification re-inspects on a fresh render — and **must be sabotage-tested**. v4's
  first sabotage test caught only 2 of 5, because verification used one view where the
  main inspection used two. Assume this station has the same class of bug until a run
  with the cleaning deliberately disabled fails every part.
- Keep the tank dip, but move it into Station 3 and relabel it what it actually is: the
  Stage-10 leak-check dip.

### Station 3 — MEMBRANE ASSEMBLY (Stage 10)

Evolve the existing insert/twist/dip cycle toward the real sequence:

```
[Teflon tape + elbows — OUT OF SCOPE, presented pre-fitted]
  → membrane into bowl → cap on → tighten to torque
  → plug permeate + close reject → pressurise 80–90 PSI
  → dip in water bin → observe for bubbles → pass / rework
```

Two things become newly honest here:

- **Tighten to a torque criterion**, reporting achieved turns and torque at cutoff,
  instead of a fixed 55° twist. MuJoCo has no screw joint; model it as a hinge driven to
  a stall-detected stop, which is exactly what a torque-limited driver does.
- **Leak = bubbles, caused by under-tightening.** Emit bubble geoms at the seal when
  achieved torque is below threshold, so the check can fail for a physical reason.
  Label it precisely, in the same breath, as we label cleaning: *no fluid simulation —
  bubble emission is a modelled consequence of under-tightening, not computed from
  physics.* The dangerous error is a **false-pass on the leak test**; report it.

**Consistency note:** the elbows (3.2, 3.3) are mandatory in the real stage but their
precursor is Teflon winding, which we have de-scoped. So the bowl and cap are presented
with elbows **pre-fitted by a human**, and the demo says so. Demoing a step whose
required precursor we deleted would be the kind of quiet dishonesty this repo exists to
avoid.

---

## Deliberate scope boundary — deformables

Teflon tape winding (Stages 9, 10), sticker peel/apply with a heat gun (Stages 2, 5),
wiring-harness routing and tubing cut/route (Stage 4), filament taping (Stages 6, 7).

These are **out of scope on purpose, not overlooked** — recorded in PITCH_NOTES §10.
They are also, per Anirudh, exactly where the research frontier is, which makes them
the honest long-term differentiation rather than an embarrassment. Saying plainly which
steps stay human is a credibility asset in the funding conversation.

Worth saying in the room too: the flow-rate and pressure tests (Stages 1, 6, 9, 10) are
**tier 3 — instrumented bench work, not arm work.** Volunteering that we would *not*
automate them shows judgement and costs nothing.

---

## Plan of record

Ordered so that the riskiest unknown is settled first and nothing is built on top of an
unverified assumption.

| Phase | Work | Exit criterion |
|---|---|---|
| ~~**V5-0**~~ | ~~Reachability + scale study.~~ **DONE — PASSES at x = 0.58. See below.** | ✅ |
| ~~**V5-A**~~ | ~~Unit-scale scene.~~ **DONE — `make_scene_v5.py`, 20/20 structural checks pass, reachability re-verified on the real scene, baselines unmoved.** | ✅ |
| **V5-B** | TRIAGE classifier. Calibrate in-cell on seeds 9000+, freeze, eval held-out | Accuracy + **false-Easy** reported on ≥60 held-out seeds |
| **V5-C** | CLEAN coverage pass: contact-band descent, raster, coverage metric | Coverage %, missed-spot count, force band adherence |
| **V5-D** | Cleaning verification + **sabotage test** | Honest cleanings verified; sabotaged cleanings caught, n/n |
| **V5-E** | MEMBRANE: threaded cap to torque, plug/valve, pressurise, bubble check | Turns + torque at cutoff; leak **false-pass** rate |
| **V5-F** | Route wiring: triage grade selects the route; end-to-end eval | Routing compliance + end-to-end on held-out seeds |
| **V5-G** | DR sweep on the new stations; video; docs | Envelope stated as a spec, as in v4 |

Non-negotiable throughout: held-out seeds, margins reported alongside rates, asymmetric
error rates called out separately, success criteria never touched.

---

## V5-0 RESULT — the cell has a layout constraint, and it is a spec

`sim_poc/v5_reach.py` + `ufactory_xarm7/cabinet_probe_v5.xml`. Kinematics only: 6-DoF IK
to 4 mm / 4°, joint-limit margin > 1°, no arm contact. Full output in `reach_v5.json`.

> ### ⚠️ These numbers replace an earlier, wrong set
> The first V5-0 run had an **axis-convention bug**: the cabinet's collision box was
> built with width along X while the raster placed the front face at ±depth/2 along X.
> On a 250 × 180 mm cabinet that put every front/back target **35 mm inside the solid
> box** and every left/right target 35 mm outside it. Five of six faces were measuring
> nothing real. Three more bugs followed (see PAIN_JOURNAL 2026-08-04). Everything below
> is re-measured with all four fixed, and **the recommended placement changed from
> x = 0.62 to x = 0.58** as a result.

**Verdict: PASS, but only at one end of the bench.**

At the recommended placement — a 250 (W) × 180 (D) × 450 (H) mm device at **x = 0.58**:

| face | reachable in a 30° tilt cone | at exact-normal press | note |
|---|---|---|---|
| **front** | **100%** | 83% | the Stage-2 cabinet face |
| **top** | **100%** | 63% | the Stage-3 top cover |
| left / right | 90% | 19% | needs the tilt cone; failures are collisions |
| **back** | **0%** | 0% | **never reachable, at any placement tested** |

Camera orbit: **3 framed views, 90° apart** — enough for the two-view classifier.

**Placement is a genuine trade-off between the two stations.** Full-resolution sweep:

| x | front | top | left/right | framed views | best separation | gate |
|---|---|---|---|---|---|---|
| 0.46 | 79% | 100% | 100% | 5 | **158°** | fail |
| 0.50 | 92% | 100% | 98% | 5 | **158°** | fail |
| 0.54 | 100% | 100% | 94% | 3 | 45° | pass |
| **0.58** | **100%** | **100%** | **90%** | **3** | **90°** | **pass** |
| 0.62 | 100% | 100% | 85% | 3 | 90° | pass |

Pulling the device closer buys camera separation (5 views at 158°, which is what the
two-view classifier wants) and costs front-face coverage. Pushing it away does the
reverse. **x = 0.58 dominates the other passing options** — same 100% front as 0.62 with
better top (63% vs 38% exact-normal) and better sides (90% vs 85%). If V5-B finds triage
accuracy is the binding constraint, **x = 0.50 is the fallback** — but cost it on both metrics: it loses **8 points of
30°-cone front coverage (100 → 92) and 35 points of exact-normal front coverage
(83 → 48)**, and gains 68° of view separation.

**The real-cell answer to both problems is a rotary indexer — and it is now built and
measured, not recommended.** See below.

### The rotary indexer removes both limits

A low-profile rotating stage under the device is the standard industrial answer here —
the same part used in welding positioners, paint booths and vision cells — and it is
cheap next to a second arm or a linear rail. It is now in the scene as a **commanded
axis** (`tt`), not scenery, because on the real cell it will need a controller, wiring
and a place in the motion sequence.

Measured with `v5_reach.py --indexed`, rotating each vertical face into the front
working position:

| face presented | index | coverage | at exact-normal |
|---|---|---|---|
| front | 0° | **100%** | 83% |
| right | 90° | **100%** | 83% |
| **back** | **180°** | **100%** | **83%** |
| left | 270° | **100%** | 83% |
| top | — | **100%** | 63% |

**The back face goes from 0% at every fixed placement to 100%.** Camera separation
becomes arbitrary, so the placement trade-off above disappears entirely — x = 0.58 is now
simply the working position, not a compromise.

This is the same class of output as v4's ±2.5 mm calibration envelope: a concrete,
costed hardware requirement discovered in simulation before anyone bought anything. Full
build numbers are in [CELL_SPEC.md](CELL_SPEC.md).

**Three findings worth keeping.**

**1. Device size barely matters; placement dominates.** Across 200–350 mm wide and
300–550 mm tall the front+top mean only moves between 83% and 100% (coarse 15-point
raster at x = 0.50). But sliding the device along the bench swings the front face from
**79% (x = 0.46) to 100% (x = 0.54–0.62)** while the side faces move the opposite way,
100% → 85% — those are the full-resolution figures from the table above, not the coarse
scan. So the cabinet dimensions we are
still waiting on are **not** on the critical path — the bench layout is. That is a
useful thing to learn while blocked.

**2. There is no single placement that serves every face.** Front wants the device far
out; sides and camera views want it close. A real cell either accepts one compromise
placement or repositions between passes.

**3. The back face is unreachable everywhere.** Not marginal — 0/48 raster points at all
eight placements. An arm on this base cannot press on a surface facing directly away
from it, because it would have to reach past the device and then bend the wrist back on
itself.

*I had a hypothesis that their process does not clean the back in situ either — Stage 3
is a separate stage for "back panel & top cover," and Stage 7 re-attaches the back panel,
implying it is detached during refurb. **Checked against the sources: it cannot be
resolved from these documents, and I am not claiming it.*** The evidence points both
ways and the set contradicts itself:*

- *Stage 6's material list includes "Back panel assembling Screws, Nos, **5**" — implying
  it is unscrewed and re-screwed.*
- *Stage 7 activity 2 says "Assemble the back panel onto the device using **filament
  tape**" — a different fastening method for the same part, one stage later.*
- *Stage 3's own QC check says "Ensure that both the top cover and back panel are
  **securely attached**", which reads as in-situ.*
- *And the corpus contains **no disassembly or teardown work instruction at all** — it
  runs Checking → Cleaning → Assembly, with nothing describing how anything comes apart.*

*So: the 0% back face stands as an unexplained constraint on our side, not as a
match to their process. It goes on the question list, not in the pitch.*

**A note on how these numbers were reached, because it matters.** This study reported
"fail at 10%", then 83%, then 0% on one face — and **every one of those was a bug in the
test, not the cell**:

1. Camera standoff hardcoded at 0.545 m when the optics need 0.293 m, pushing the far
   orbit side to x = 1.05 against a measured max planar reach of 0.928 m.
2. A full 360° orbit demanded, when the classifier only needs two separated views.
3. An exact-normal press demanded, when a compliant pad conforms over ~30°.
4. The axis-convention bug above — faces measured 35 mm inside/outside the box.
5. A backdrop panel that was scenery to us and a wall to the robot (0% on one face).
6. Failure reasons reported from whichever retry ran last, so a point reached with
   **0.0 mm error and blocked by collision** was labelled "unreachable".
7. A warm-start chain where one failed point silently zeroed an entire face.

Each fix has a physical justification, and the report prints **strict (exact-normal)
alongside relaxed (within-cone)** coverage so the relaxation is visible rather than
buried. It matters: the top face is 100% relaxed but 63% strict at this placement.

**Kinematics only.** A pose reachable here can still fail under contact — that is V5-C's
problem. This is a necessary condition, not a sufficient one.

---

## V5-A RESULT — the unit-scale scene

`sim_poc/make_scene_v5.py` → `ufactory_xarm7/refurb_scene_v5.xml`. A **generator**, not
hand-written geometry: v4's 44 deposit geoms are an opaque block of numbers nobody can
audit, so here the pools come from a fixed seed with the placement rule written down.

**Three condition pools, and the reason there are three.** DrinkPrime's own documents
already distinguish them, so the taxonomy is grounded rather than invented:

| pool | source text | remedy in their process | our grade |
|---|---|---|---|
| **soil** (40) | Stage 2: *"Apply CIF cream… thoroughly clean the exterior"* | normal wipe | EASY |
| **scratches** (28) | Stage 2: *"If any scratch found on cabinet need use the Rubbing component"* | second, harder pass | MEDIUM |
| **dents** (20) | Stage 1 CHECKS: *"Check Chassis for dent & scratches"* | **none, in any of the ten stages** | HARD |

**What is theirs and what is ours:** the three features are theirs, quoted; the class
names are theirs; **the mapping between them and every numeric cut point is ours**,
because no document in the set defines the Easy/Medium/Hard boundaries. Defensible and
source-grounded — not validated.

Ground truth stays crisp (non-overlapping counts, as in v4); the difficulty comes from
occlusion, lighting and pose, not from fuzzing labels.

**Verified, not assumed** — every one of these is an assertion in the build check:

- all 88 patches lie **on** their face, normal outward, inside the face rectangle
- body and top cover are **flush**, so the visible surface and the raster plane agree
- pools sit on the **four reachable faces only**; the back face carries none
- the pad tool **rests stably** on its post (2.4 mm settle, all contact on `post_base`)
- no initial interpenetration anywhere (`ncon = 0` at spawn)
- the reachability gate **re-run against the real scene**, not the probe: identical
  numbers on every face

**One honest limit:** the pools sit on four faces (front, top, left, right), not the
back. That was originally *forced* — the back was unreachable — and with the rotary
indexer it no longer is, but the pools have not been regenerated onto five faces yet. So
for now the cleaning coverage number means **"coverage of the four soiled faces."** That
wording has to travel with the number. Extending to five faces is a one-line change to
`_faces()` in the generator and belongs with V5-C, where there will be a cleaning
controller to measure against.

---

## If we need a demo in one week

Five working days. The funding bar we have on record is **image inspection + a cleaning
step** — both are in the keep list, and the membrane station already exists.

**Keep**

1. **V5-0 reachability** — non-negotiable, half a day, and it is the one thing that can
   invalidate the rest.
2. **TRIAGE** at unit scale with the camera-orbit design and placeholder class
   boundaries, clearly labelled.
3. **CLEAN** as a coverage raster on the **front face only**, with the compliant-pad
   fallback below.
4. **MEMBRANE** as the *existing, working* v4 insert/twist/dip, re-labelled into
   Stage-10 vocabulary — with the caption stating plainly that our bayonet is a
   stand-in for their threaded cap, pending CAD.

**Cut**

| Cut | Why it is safe to cut |
|---|---|
| Threaded multi-turn cap + spanner torque model | The existing bayonet demos the same *class*; caption carries the difference |
| Elbow fitting, end plug, ball valve | Gated on de-scoped Teflon work anyway |
| Pressurisation + bubble detection | The best single item here — but it is new physics *and* new vision in the same week |
| Stage 3 (back panel, top cover, compressed air) | Same motion as Stage 2 on another face; adds no new claim |
| DR sweep on the new stations | v4's ±2.5 mm envelope is already the quotable spec |
| LeRobot export for v5 | Nothing downstream is consuming it yet |
| Scratch-specific rubbing-compound sub-pass | A second tool for no new claim |

**Do not cut, even under time pressure:** held-out evaluation, the false-Easy /
false-clean asymmetric split, and the cleaning **sabotage test**. They are cheap, and
they are the entire reason anyone should believe the numbers. Every time this project
skipped one it produced a number that later collapsed — 90% → 53% on the rig-calibrated
classifier, 88% → 72% on unseen seeds.

**Day shape**

- **Day 1** — V5-0 reachability, then cabinet scene + defect/soil pools
- **Day 2** — TRIAGE: calibrate in-cell, freeze, held-out eval
- **Day 3** — CLEAN: contact band + raster + coverage *(the risky day)*
- **Day 4** — verification + sabotage test; route wiring
- **Day 5** — 60-seed held-out eval, video, RESULTS_V5 / LEARNINGS / PAIN_JOURNAL

**The pre-planned fallback for Day 3.** If contact-following eats the day, drop to a
fixed-height raster with a **compliant (soft) pad geom**, so contact is guaranteed by
geometry rather than by control. That is the chamfer lesson applied a third time — ask
what shape makes the problem disappear before writing a controller — and it degrades the
result to "coverage achieved with a compliant tool" rather than losing the station.

**What one week cannot buy:** any claim that our geometry matches their parts. That is
gated on CAD and cabinet dimensions, not on effort.

---

## Asks, in priority order

1. **What defines Easy / Medium / Hard?** Ask it open-ended, because no document in the
   set defines them: *"Which document, if any, gives the Easy/Medium/Hard criteria — and
   if none does, do your operators grade by eye, by a wear indicator, or by feel?"*
   **Either answer unblocks work.** If a spec exists it hands us the boundaries the
   classifier is currently guessing. If the answer is "they just know" or "by feel", then
   camera-only inspection is the wrong architecture and we should stop investing in the
   classifier — which is the open question already sitting in CLAUDE.md backlog 0a. Ask
   for the Stage 1 §8 **"Allow & Not allowed Spec. & visual Photo"** cards by name.
2. **QC Annexures 1–13**, all of them. If the plant runs to a controlled flow chart, these
   live in the same folder as the PDFs we already have — a "forward the rest of the
   folder" ask, not a shipment. Annexure 1 is still worth having: it is the cabinet /
   sticker cosmetic accept-reject spec, which is exactly our CLEAN station's verification
   criterion. Just don't expect it to answer #1.
3. **Is the assembled-device final leak test 45 PSI or 80 PSI?** Stage 6 says 45 (per
   BIS); QC page 3 says 80. This is a safety question, not a spec question.
4. **STL/STEP CAD: membrane bowl, membrane cap, and the membrane O-ring.** These outrank
   the cartridge. Per Anirudh, a manufacturer almost certainly already has them and the
   ask does not require the physical device. Quote item codes `100059` / `100031` /
   `100099` (Stage 9) — the only part numbers in the entire set.
5. **Cabinet outer dimensions.** Cheap to answer. Note V5-0 found these are *not* on the
   critical path — bench layout dominates — so this dropped a rank.
6. Cycle time / takt per stage; daily volume; the Easy/Medium/Hard split percentages;
   which stage bottlenecks the line; and **whether a teardown/disassembly instruction
   exists** — the set has none, and the motion `sim_poc3`/`sim_poc4` model has no
   documented counterpart in it.
