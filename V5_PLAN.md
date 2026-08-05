# v5 Plan — the three-stage funded demo

Written against the **real** process: **13 Waterwala Labs documents** — 10 stage work
instructions (Ref 0024DPCRO001–0010, 0024DPNAP0008) **plus** 3 QC flow-chart pages, R0,
11-04-2024. Thirteen TOTAL, not thirteen work instructions plus three more; the older
phrasing here read as 16 and was miscopied into two other files. The process
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
  first sabotage test **wrongly PASSED 2 of 5** (caught 3 of 5), because verification
  classified on one view where the
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
| front | 0° | **100%** | ~~83%~~ **47.9%** |
| right | 90° | **100%** | ~~83%~~ ~~27%~~ **14.6%** |
| **back** | **180°** | **100%** | ~~83%~~ **47.9%** |
| left | 270° | **100%** | ~~83%~~ ~~27%~~ **14.6%** |
| top | — | **100%** | ~~63%~~ **29.2%** |

> ### ⚠️ The exact-normal column was wrong TWICE — both corrected 2026-08-04
> **Second correction, same day, found by a completeness critic.** The whole strict column
> was measured with `PAD_STANDOFF = 0.045` — a guess made before the wiping tool existed.
> The built tool is **105 mm** wrist-to-pad. Unifying that into `v5_reach.py` roughly
> halves strict coverage again: front and back **47.9%**, sides **14.6%**, top **29.2%**.
> The gate's PASS verdict is unchanged, because it is judged on the relaxed 30° column,
> which is still 100% everywhere. **This is precisely why the tilt cone is load-bearing
> rather than a nicety.** It also means V5-C's fix 5 — "the cone is imported from the gate
> so gate and consumer cannot drift" — was only half done: the cone was unified, this
> number was not.
>
> The first correction, below, still stands and is the more instructive one:
> `v5_reach.py --indexed`, run today against the committed scene, prints **right 27.1%,
> left 27.1%** strict — not 83%. The 83% here assumed indexing makes the four vertical
> faces equivalent. It does not: the cabinet is 250 mm wide and 180 mm deep, so rotating a
> side face into the front position puts its surface **35 mm closer to the arm** than the
> front face ever is. Four identical numbers across four genuinely different geometries
> was the same smell that caught the 700.0 N force clamp, and it should have been checked
> then. **The relaxed column is unchanged and still 100% — the gate passes on that, and
> honestly.** What broke is that `v5_clean.py` presses at exact normal only, so the
> cleaning station is operating in the 27% column while a green gate reports the 100% one.

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
- pools sit on **all five exposed faces**, the back panel included — `v5_check_scene.py`
  asserts exactly this ("all five exposed faces carry pools"), having previously asserted
  the reverse. *(This line said "four reachable faces only; the back face carries none"
  long after the fifth face went in, and it sat under a "verified by the build check"
  heading while the build check asserted the opposite. It is the one line left in the
  repo that could have re-narrowed the cleaning claim back to four faces.)*
- the pad tool **rests stably** on its post (2.4 mm settle, all contact on `post_base`)
- no initial interpenetration anywhere (`ncon = 0` at spawn)
- the reachability gate **re-run against the real scene**, not the probe: identical
  numbers on every face

> **⚠️ SUPERSEDED — the limit below was closed in commit c19bac0.** `_faces()` now emits a
> **fifth face**: the back panel's outer surface (local x 0.090–0.100, y ±0.119,
> z 0.020–0.430), because the rotary indexer made it reachable. Coverage now means
> **"of all five exposed faces"**, and V5-C's 94.6% is measured that way. The paragraph is
> kept because the *reasoning* — that the wording must travel with the number — still
> stands; only the face count changed.

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

---

## V5-B RESULT — triage, 90.0% on 120 fresh units

> **⚠️ SUPERSEDED — the shipping triage result is 97.5%, not the 90.0% below.**
> `sim_poc/stats_v5_triage.json` and CLAUDE.md both record **97.5% on 120 fresh units
> (seeds 700–819), false-easy 2.5%, missed-hard 0.0%** — reproduce with
> `v5_triage.py --eval 120 --seed0 700`. Note false-easy **rose** 0.0% → 2.5% as accuracy
> improved, which is the direction that matters and must be reported. Everything below is
> the earlier 500–619 run; its *reasoning* (why counting instances beat pixel fractions,
> and why the principal-axis ratio beat the bounding box) is still the live explanation,
> but **its numbers and confusion matrix are stale — do not quote them.** There is no
> RESULTS_V5.md, so this banner is the only thing correcting them.

`sim_poc/v5_triage.py`. Fixed station camera + rotary indexer showing all four faces;
arm parked clear of frame (measured 0.000% arm pixels, vs 4.28% at the home pose).

**Design change from the plan, made deliberately.** V5_PLAN specified the arm orbiting
its wrist camera — correct when the device could not move. The indexer changed that. A
fixed camera with a rotating device is simpler, is what real rotary vision cells do,
needs **no hand-eye calibration** (the largest un-modelled risk in the wrist-camera
plan), and leaves the arm free during inspection.

### The number

**120 units, seeds 500–619, never previously rendered, single evaluation:**

| | |
|---|---|
| accuracy | **90.0%** |
| **false-easy rate** | **0.0%** |
| **missed-hard rate** | **0.0%** |
| over-treatment | 16.7% |

| truth ╲ pred | easy | medium | hard | acc |
|---|---|---|---|---|
| easy | 40 | 8 | 0 | 83.3% |
| medium | 0 | 28 | 4 | 87.5% |
| hard | 0 | 0 | 40 | **100%** |

Calibration (seeds 9000–9099, disjoint) read 93.0% — a **3-point** calibration-to-held-out
gap, against 15.6 points for the version before it. That gap closing is the evidence it
is not overfit.

**The decision rule is now legible to a customer:** *more than 3 dents → HARD; else more
than 5 scratches → MEDIUM; else EASY.* Those are counts of actual defects, directly
comparable to the ground-truth bands.

### It only works because of one fix, and the fix is the lesson

The first version measured **pixel fractions** and scored **55.0%** on 120 held-out units
while **never once saying "easy"** — the easy and medium scratch-fraction distributions
overlapped, so no threshold existed and no tuning could have helped.

Counting defect *instances* instead required telling a scratch from a dent by shape. The
first shape test used the **bounding-box aspect ratio** — and a 40 px scratch at 45° has a
~30×30 bounding box, i.e. aspect 1.0, i.e. "perfectly compact". Scratches are placed at
uniformly random angles, so **most of them defeated the test entirely** and were counted
as dents. Replacing it with the principal-axis ratio from second moments (rotation
invariant) took the per-unit count error from +3.2 dents / −3.2 scratches to
**+0.3 / −0.4**, and the accuracy from 55% to 90%.

### Can this reach ~100%? Yes, and that is the problem with wanting it to

The three classes are separated **by construction**: easy has 0–2 scratches, medium has
9–22, and nothing lives in between. A counter accurate to ±3 scratches therefore scores
~100% *by definition*. Pushing the remaining 10 points is a matter of tightening the
count, and it is achievable.

**What it would prove is that our counter counts — not that triage is solved.** The gaps
in those bands are ours. So is the easy/medium boundary itself: no DrinkPrime document
defines where "needs a wipe" ends and "needs scratch removal" begins
(`dp_process.MISSING`). A 100% here would be a measurement of our own label design.

What the number *does* support, and what is safe to say in the room:
- the **safety-critical half is solid** — 40/40 HARD units caught, missed-hard 0.0%, and
  a missed HARD is the one error with no recovery, since dents have no remedy in any of
  the ten stages;
- **false-easy is 0.0%** — nothing needing real work has ever gone down the cosmetic path;
- the architecture (fixed camera, indexed device, explainable threshold on counted
  defects) is the right shape for the founder's image-processing bar.

### Process notes

- **Seeds 200–259 and 300–419 were consumed** during development — 200–259 was evaluated
  twice across a threshold change, and 300–419 was used for the 55.0% pixel-fraction
  result. The 90.0% above is on 500–619, which had never been rendered, looked at once,
  and not tuned against.
- Earlier, fitting two thresholds to 45 calibration seeds read 88.9% on calibration and
  73.3% held out. Refitting on 100 seeds read **74.0% on calibration** — the calibration
  score converged *down* to the held-out score. The calibration number was the overfit.


---

## V5-C DIAGNOSIS — coverage was never the problem

64.7% coverage / 74.4% raster contact reproduced byte-identically before anything was
touched (seeds 800–807, `stats_v5_clean.json` unchanged). Then it was instrumented rather
than tuned. `sim_poc/v5_clean_diag.py` **subclasses** the shipping `Cell` and overrides
`wipe`, `move`, `surface_x` and `front_face_plane`; it does not reimplement the cycle, so
every number below comes out of the controller that actually runs.

**Four causes, none of them the wipe.**

| # | cause | evidence | scope |
|---|---|---|---|
| 1 | **The indexer never reaches 270°.** `deg2rad(270)` = 4.712 rad vs actuator `ctrlrange` ±3.1416; MuJoCo clamps `ctrl` silently. | commanded 270° → achieved **180.0°**, every seed. Face 4 re-wipes the back panel; one side face is never presented. | ~20% of patches |
| 2 | **The arm self-collides and stops tracking.** `link1`~`link6` at 130–271 N, joint 4 pinned at its 30 N·m limit. | every SAFE / TO FACE / RETRACT misses by **100–400 mm**; tool-changer moves (wrist *down*) arrive at 1.9–2.6 mm. | whole cycle |
| 3 | **34.2% of raster points are silently skipped.** `surface_x` rays from x = 0.20 through the space the arm occupies. | ray lands on `xarm_gripper_base_link` ×61, `link7` ×33, `link4` ×26, the pad ×14 → `None` → `continue`. | 154 of 450 points |
| 4 | **The built tool is 105 mm wrist-to-pad; V5-0 sized the cell at 45 mm.** | controlled sweep, one input changed: sides **17/22 → 4/22**, top **15/25 → 8/25**. | the placement |

**Cause 3 also corrupts the published metric.** Skipped points log no force sample, so
"contact during raster 74.4%" is 74.4% *of the points that ran*. Over the planned raster
it is ≈ **49%**. That number should not be quoted until the probe is fixed.

**The arm riser is exonerated.** It was the other thing that changed since V5-0. `--riser`
is flat at every diameter to 250 mm, and feasibility is identical with its collisions
disabled (sides 4/22 both ways). Not the cause.

### The placement study, redone with the tool that exists

`sim_poc/v5_clean_place.py`. Exact normal, kinematics only, same solver at every point.

| x | standoff | front | idx 90 | idx 180 | idx 270 | top | mean |
|---|---|---|---|---|---|---|---|
| 0.54 | 45 mm | 16/22 | 12/22 | 15/22 | 11/22 | **23/25** | 67.5% |
| 0.54 | **105** | 4/22 | **0/22** | 6/22 | **0/22** | 15/25 | 21.1% |
| **0.58** | **105** | 16/22 | **2/22** | 15/22 | **2/22** | 8/25 | **38.2%** |
| 0.62 | **105** | 16/22 | 15/22 | 15/22 | 15/22 | **0/25** | 55.5% |
| 0.70 | **105** | 16/22 | 17/22 | 17/22 | 16/22 | **0/25** | 60.0% |

**There is no placement at which the built tool can press exact-normal on all five
faces.** The verticals want the device pushed out; the top wants it pulled in; the current
x = 0.58 is the worst of both. This is V5-0's "no single placement serves every face"
finding again — but the crossover moved once the real tool length went in, and it now
lands on the wrong side of the working position.

**So the tilt cone is not optional, it is load-bearing.** V5-0 relaxed to a 30° cone for a
real physical reason (a compliant pad conforms), reported strict alongside relaxed, and
every face is 100% relaxed. `v5_clean.py`'s `tool_mat_face()` throws that away — it
returns one fixed exact-normal frame. Restoring it is what makes the station feasible at
all; no amount of press or raster tuning reaches faces the arm cannot hold square to.

### Fix order

1. Wrap the index command into (−180°, 180°] — one line, no design trade-off.
2. Probe the surface with the arm parked, or ray only the cabinet's geoms, and **count**
   skipped points instead of `continue`-ing silently.
3. Let the wipe use the 30° cone the gate already assumes — pick the tilt per point, as
   `v5_reach._try_point` does.
4. Re-run `v5_clean_place.py` after (3) and re-pick x. Then update CELL_SPEC.
5. Make the consumer assert its column: a station pressing at exact normal must gate on
   `strict`, not on `coverage`.

**Held-out seeds:** 800–807 were re-used here for *diagnosis only*, against the already
published number. The next evaluation needs a fresh range (900+).

---

## V5-C RESULT — all five fixes landed, 64.7% → 94.6% held out

Fixes applied in the order set out above. Each was measured on its own; the scene change
in fix 1 sent every gate round again.

| fix | what changed | measured effect |
|---|---|---|
| 1 | indexer `ctrlrange` ±180° → **±360°**, and the cycle indexes **forward to 360°** for the top pass instead of unwinding to 0° mid-move | 270° now achieved (was clamped to 180°); the fifth face is presented |
| 2 | `surface_x` rays **only the cabinet's own geoms**, one at a time, instead of a scene-wide `mj_ray` from x = 0.20 | probe-miss skips **34.2% → 0%**; skipped points are now **counted**, not silent |
| 3 | plan-then-execute: per point, the **smallest tilt in the 30° cone** that is reachable, limit-clear and collision-free; drive to that **joint** configuration | no self-collision; plan error **0.00 mm** at every raster point |
| 4 | placement re-checked through the cleaner's own planner | **x = 0.58 stays** — with the cone every placement is 100%; no CELL_SPEC coordinate moves |
| 5 | the cone is **imported from `v5_reach`**, not restated | gate and consumer cannot drift apart again |

Two further defects fell out of fix 3 and were fixed with it:

- **The planner was blind to its own tool.** The pad is a free body on a weld, so it does
  not follow the arm in a planning copy. The first version excluded it from the collision
  test — which meant nothing checked whether the 60 mm pad would reach below the platter.
  It now reconstructs the weld transform and carries the tool, with the flange at its
  free extension (the longest the tool can be). Rule: the **arm** may touch nothing; the
  **pad** may touch the device and nothing else.
- **A 4 mm wrist tolerance is unholdable under load.** 0.8° of joint lag is 14 mm at that
  extension, so every top-face point and 60% of front-face points ran the full 2.5 s
  timeout pressing at full command — peak **326 N**, only **74.8%** in band. Wipe moves
  now end on a **stall detector** (in contact, seated ≥ 5 N, and no longer closing on the
  target). First attempt used "contact for 0.1 s", which fired on the first graze and cost
  11 points of coverage; the stall test is the one that holds.

### The numbers

Held out on seeds **900–907, never previously run, looked at once**:

| | |
|---|---|
| coverage | **94.6%** mean, 85.7% worst |
| missed spots | **8 of 129** (6.2%) — Stage 3's own QC check |
| raster skipped | **0** probe-miss + **0** no-feasible-pose of 3744 planned points |
| contact during raster | **77.5% of PLANNED points** (the honest denominator) |
| contact force | median **13.1 N**, peak 271 N |
| in force band | 88.1% |
| press angle | 42.7% at exact normal, mean tilt 7.4°, max 30° (= the gate's cone) |
| tool coupling drift | **0.03 mm** (was 0.16) |

Development seeds 800–807 read 95.8% — a **1.2-point** gap to held out.

> **The trajectory is open-loop and seed-independent.** The raster, the planned poses and
> the contact are identical for every unit; the seed only moves the soil. So force, tilt
> and raster figures have **no seed variance at all** — they are effectively n = 1 and
> must not be quoted as an 8-unit spread. Only coverage and missed spots actually vary.
> `report()` prints this warning with every run.

### What is NOT closed

**In-band force is 88.1%, and the peak is 271 N — beyond where our own contact model is
validated.** (60 N is where the pad's measured force/penetration curve stops being
monotonic; it is a model-validity limit, not a component rating. Do not present it as
"4.5x the pad's rating".) The
cause is located, not fixed: the front face and the top face still never reach their
planned pose (0% and 42% arrival, 14–37 mm steady-state error), so they press longer and
harder than the other three. Both are the faces where the wrist ends up closest to the
arm's own base — the 105 mm tool length again. The placement sweep shows the required
tilt falling from 10.9° at x = 0.58 to 6.8° at x = 0.70, so **moving the device out is the
obvious next lever**, at the cost of the top face, which wants it closer. That is a real
trade and it should be measured under contact, not kinematically.

**A 100%-coverage variant exists and was rejected.** Leaving the old arrival-only
termination in place gives 100% coverage on both seed ranges — bought by pressing 2.5 s at
every point, with peak 326 N and 74.8% in band. Coverage paid for in force-seconds a real
cell would not spend is exactly the kind of number this project distrusts, so the stall
detector ships and the 94.6% is the honest figure.

---

## V5-D RESULT — the verification, and what it says about V5-C

`v5_clean.py --sabotage N`. Each seed is run **twice** — once cleaned honestly, once with
soil removal withheld while the arm still moves, still presses and still logs contact.
Paired, so the two arms differ in exactly one thing.

The check re-inspects the unit **just cleaned** (the live model, not a fresh spawn) and
reuses `v5_triage`'s own `face_regions` and `image_features` rather than a second
implementation — so the verifier and the grader cannot drift apart. That was v4's exact
failure: its first sabotage test wrongly passed 2 of 5 dirty parts because verification
looked through one camera view while the inspection it checked used two.

### The first run passed the exit criterion and was worthless

Seeds 1000–1009, verifier using the triage camera alone:

| | |
|---|---|
| honest cleanings verified | **10/10** ✅ |
| sabotaged cleanings caught | **10/10** ✅ |
| **false verifies** | **9/10** ❌ |
| where that residue sat | **12 of 12 patches on the top face** |

V5_PLAN's stated exit criterion — *honest verified, sabotaged caught, n/n* — was met
**exactly**, by a check that was letting nine out of ten dirty units through.

**Why: the two blind spots are the same face.** The triage camera sits at z = 0.400 and
the device's top face at z = 0.450 — *below* the plane of that face, cos(normal, view)
= +0.076 — so `face_regions` returns the four **vertical** faces only. And the top face is
where V5-C cleans worst (29.2% exact-normal reachability; it was the pass that never
reached its planned pose). **The station fails precisely where it cannot check.**

### The fix is a second camera, and it is a hardware requirement

`verify_top` — mounted on the −Y side above the top plane, clear of the arm's working
volume over the device. Deliberately *not* added to `face_regions`: V5-B's triage result is
frozen at 97.5% and grades the four vertical faces from `inspect`; this is the **cleaning**
station's extra eye. Same projection, same hull-mask format, same feature extractor.

Same seeds, before and after:

| seeds 1000–1009 | 4-face verifier | 5-face verifier |
|---|---|---|
| false verifies | **9/10** | **0/10** |
| honest verified | 10/10 | **1/10** |
| sabotaged caught | 10/10 | 10/10 |

Honest verification *fell* — which is the check becoming honest, not regressing. Those
nine units were always dirty; only now does anything say so.

### The number — seeds 1100–1109, fresh, looked at once

| | |
|---|---|
| **sabotaged cleanings caught** | **10/10** |
| **false verifies** | **0/10** |
| honest cleanings verified | **6/10** |
| residue on the top face | 24 of 179 patches (13.4%) |

### What this does to V5-C's headline

**94.6% coverage is 60% under DrinkPrime's own acceptance criterion.** Stage 3 asks to
*"check for any missed spots"* — that is **binary per unit**, not a mean over patches. Four
of ten units still carry soil, all of it on the top face. The mean flatters a station that
fails 40% of the time on the customer's own test.

So V5-C is **not done**, and V5-D is what proves it. The open force item and this are the
same defect wearing two hats: the top face never reaches its planned pose, so it presses
longest, hardest and least effectively.

**Seeds consumed:** 1000–1009 (verifier development and the before/after) and 1100–1109
(the held-out headline). Start at 1200.

---

## V5-C REOPENED — the top face, and it was one root cause all along

V5-D said V5-C was not done. It was right, and the defect turned out to be the same one
behind the unclosed force band.

**The diagnosis.** The top-face pad was measured up to **257 mm off target** and sweeping
**37 mm past the face edge** on one side while stopping **29 mm short** on the other. But
the *median* error was only −2.4 mm — so it was not a systematic offset, it was a handful
of catastrophic points. Measuring the joint-space step between adjacent raster points
found them:

| pass | points > 0.35 rad | worst |
|---|---|---|
| WIPE 0 | 32 of 120 | 5.10 rad for a 44 mm step |
| WIPE 90 | 32 of 90 | 4.98 rad |
| **WIPE 180** | **0 of 120** | 0.37 rad |
| WIPE 270 | 22 of 90 | 2.39 rad |
| WIPE top | 1 of 48 | **5.78 rad for a 37 mm step** |

**A 7-DoF arm has many configurations for the same pose, and the planner was taking the
first one it found.** Adjacent raster points 27 mm apart landed in different branches. The
executor interpolates at 0.02 rad/step with a 2.5 s budget, so a 5.78 rad jump cannot
complete — and on the way it sweeps the pad in a wide arc across the device, which is
exactly the 257 mm excursion and exactly where the force spikes came from. Face 180 had
**zero** jumps and was the only pass that ever behaved.

**The fix: prefer the solution nearest the previous one.** `plan_pad` still tries smallest
tilt first and returns immediately when continuity is acceptable (≤ 0.35 rad/joint, against
a 0.11–0.19 rad median that the geometry actually requires); only when the nearest-in-tilt
answer would tear the arm across its workspace does it keep looking. Plus the warm seed now
resets to each face's own approach pose instead of carrying over from the far side of the
device.

### Same seeds as the published baseline (900–907)

| | before | after |
|---|---|---|
| coverage | 94.6% | **100.0%** |
| units at 100% | 3/8 | **8/8** |
| missed spots | 8 of 129 | **0 of 129** |
| in force band | 88.1% | **99.1%** |
| peak force | 271 N | **111 N** |
| contact during raster | 77.5% | **93.4%** |
| raster skipped / infeasible | 0 / 0 | 0 / 0 |

**The force band closed without being touched.** It was never a press-depth problem — it
was the pad being dragged across the device by branch jumps.

**The honest cost:** exact-normal presses fell from 42.7% to **8.8%**, mean tilt 7.4° →
**18.2°**, max still 30° and inside the cone the gate allows. The planner now trades press
angle for joint-space continuity, deliberately. That trade is real and should be quoted
whenever the tilt figure is.

### V5-D re-run, fresh seeds 1200–1209, looked at once

| | |
|---|---|
| honest cleanings verified | **10/10** |
| **soil actually left on honest units** | **0 patches** |
| false verifies | **0/10** |
| sabotaged cleanings caught | **10/10** |

The paired design is what makes that trustworthy: on the *same* seeds the sabotaged arm
leaves **170** patches, so the soil was there and was removed — this is not "nothing to
clean". Under DrinkPrime's own binary per-unit criterion the station now passes **10/10**,
against 6/10 before.

**Sample size, stated plainly:** 8 units at 100% coverage plus 10 units at zero residue is
**18 units**. The force, tilt and raster figures still have **no seed variance at all** —
the trajectory is open-loop and the seed only moves the soil.

**Seeds consumed:** 1200–1209. Start at 1300.

---

## GATE 1 — the 111 N question, closed by fixing it

**Asked:** extend the pad's compliance validation past 111 N, or justify the peak, or fix it.

**Extending it is not available.** The static rig (`v5_check_scene.py` §6 — press the pad
with a known force, measure penetration) run past its usual 60 N:

| N | 0 | 5 | 10 | 20 | 40 | **60** | 80 | 120 | 200 |
|---|---|---|---|---|---|---|---|---|---|
| penetration mm | 0.97 | 1.68 | 1.94 | 2.11 | 2.16 | **2.19** | **20.25** | 21.64 | 12.18 |

The curve **breaks between 60 and 80 N** — an 18 mm jump to twice the pad's own
half-thickness, non-monotonic above that. So 60 N is a **model-validity ceiling**, and no
amount of sweeping makes it higher.

> ### ⚠️ CORRECTED during V5-E — the ceiling is **45 N**, not 60
> The table above is itself a **coarse-grid artifact**. It samples 0/5/10/20/40/60 and
> never tries 50 — where the contact solver goes unstable (**11.6 mm** of penetration on a
> 10 mm pad). Swept finely the curve is clean and repeatable to **45 N** and
> *intermittently* unstable above: **50 breaks, 55 is fine, 60 breaks, 65 is fine.** That
> is the solver, not the pad, so "breaks between 60 and 80" was the wrong shape of claim.
>
> **Not a regression from V5-E.** Verified against the committed pre-V5-E scene, which
> breaks at 50 N identically — the instability was always there and the grid hid it.
>
> Gate 1's *conclusion* is unchanged and better supported: cleaning peaks at **34.5 N**,
> and 30/35/40/45 N all read a clean 2.13–2.19 mm. `force_hi` is now **45 N**, the gate
> sweeps a fine grid inside it, and the beyond-validity probe prints 50/55/60/80/120 so
> the non-monotonic shape is on the page rather than inferred.

**Justifying the peak was tempting and wrong.** The 111 N was a genuine transient — 0.012%
of contact samples, 0.04 s of 307 s, at 3.70 mm penetration where the model still behaves.
But "rarely in the broken region" is not "outside the broken region", and a founder video
should not rest on that distinction.

**So: fixed.** The >60 N excursions were on exactly the two passes that still had IK branch
jumps, because a jump drags the pad across the device. `plan_pad` now **declines** a point
whose nearest solution exceeds `hard_joint_jump = 0.60` rad rather than executing the
swing, and counts it.

| seeds 900–907 | before continuity fix | after continuity | **after refusal** |
|---|---|---|---|
| coverage | 94.6% | 100.0% | **100.0%** |
| peak force | 271 N | 111 N | **34.5 N** |
| in force band | 88.1% | 99.1% | **100.0%** |
| contact during raster | 77.5% | 93.4% | **99.8%** |
| raster points declined | 0 | 0 | **136 of 3744 (3.6%)** |
| exact normal / mean tilt | 42.7% / 7.4° | 8.8% / 18.2° | 19.5% / 11.6° |

**The whole cycle now operates inside the validated band** — zero samples above 60 N,
peak 34.5 N. The 3.6% of declined points cost **no coverage at all**, because the pad's
30 mm radius overlaps enough that those points were redundant. Deep-penetration outliers
(up to 18 mm at low force) also vanished — they were the branch-jump transits.

**Two things now assert the ceiling instead of assuming it.** `v5_check_scene.py` probes
80/120/200 N and *prints* where the model breaks, deliberately without asserting
monotonicity there. `v5_clean.py`'s report flags the peak `OK` or
`*** OUTSIDE MODEL VALIDITY ***` against `force_hi` on every eval — the consumer asserting
its own column, the same pattern as importing the tilt cone from the reachability gate.

**V5-D re-run, fresh seeds 1300–1309:** honest verified **10/10** with **zero** residue,
false verifies **0/10**, sabotaged caught **10/10** (193 patches present on the sabotaged
arm, so the soil was there).

**Seeds consumed:** 1300–1309. Start at 1400.

---

## V5-E RESULT — membrane assembly, Stage 10

`sim_poc/v5_membrane.py`. Subclasses V5-C's `Cell`, so the planner and motion layer are
inherited rather than re-derived — the same extends-by-import rule v4→v3→v2 followed.

### The threaded cap is a real screw, and it stalls on torque

MuJoCo has no screw joint, so one is built: a hinge and a slide tied by an equality,
`cap_z = −(pitch/2π)·cap_rot`, 2 mm pitch. Tracking measured at **−6.315 mm against
−6.266 expected**. The driver is a velocity actuator whose **forcerange IS the torque
limit**, so it stalls the way a nutrunner stalls.

**This is NOT our v2/v3/v4 55° indexed bayonet and must never be called equivalent.** The
class of problem transfers (align → engage with clearance → rotate to secure); the motion
does not. Their cap is threaded and spanner-tightened to a torque criterion.

**Stall is detected on AXIAL PROGRESS, not rotation.** Measured: the cap advances at
~1250 µm/s on free thread, 588 µm/s as the seal loads, and **43 µm/s** once seated — a 30×
collapse. Rotation rate only decays gently (3.9 → 0.54 rad/s over 20 s) and never crosses a
clean threshold; a rate-based detector reported `stalled=False` on a cap plainly seated at
6.00 N·m.

The torque is **real friction against a real preload**: 178 N × 1.1 × 0.030 m ≈ 5.9 N·m
against a measured 6.0. The O-ring is 12 soft spheres the cap compresses, with a hard rim
behind them so the cap seats instead of crushing through.

### The number — fresh seeds 1400–1409, paired, looked at once

| | |
|---|---|
| achieved turns | median **9.68**, range 9.13–10.02 |
| torque at cutoff | **6.00 N·m** every unit — *that is the definition of a torque-limited stall, not an artifact* |
| seal preload | median **333 N**, peak 341 N |
| stalled on torque | **10/10** |
| tighten OK (workpiece) | **10/10** |
| honest units pass the bubble test | **10/10** |
| false FAIL | **0/10** |
| **sabotaged units caught** | **10/10** |
| **FALSE PASS** | **0/10** ← the dangerous error |

Sabotage = cap driven only 4 turns, so the seal is never preloaded (0.20 N·m against a
5.4 N·m pass threshold). Bubble pixels: **0** on every sealed unit, **1642–2878** on every
unsealed one.

### Honest labels, all of them

- **Bubbles are a PROXY.** Revealed as a modelled consequence of the torque the workpiece
  achieved. **There is no fluid or gas simulation anywhere in this repo.** What stays real
  is that the grader only ever sees pixels — the pass/fail is *caused*, not asserted. The
  rule (`val > 0.95`) was frozen on calibration seed 9000+ with bubbles forced on and off:
  **0 px sealed, 3266 px leaking**, so the 40 px threshold sits ~80× clear of both.
- **End plug, ball valve and the 85 PSI charge are LOGGED STATE**, not gas physics.
- **That the charge is HELD through the dip is OUR inference** from the 3.6 → 3.7 ordering.
  Stage 10 does not say it explicitly.
- **The torque figure is OURS.** Stage 10 says only *"Ensure the cap is tightened properly
  with the spanner"* — a qualitative criterion, no number anywhere in the corpus.
- **Geometry is PLACEHOLDER.** Swap-in point is the `MEM_*` block in `make_scene_v5.py`,
  against item codes 100059 / 100031 / 100099.
- **Stage 10's 80–90 PSI is NOT the contested figure.** The unreconciled 45-vs-80 PSI
  contradiction is the *assembled-device* test and is deliberately untouched here.
- **The arm does not manipulate in this station yet.** The driver is a station fixture and
  the dip is a teleport. V5-E's claim is about the thread and the bubble check; the
  pick-and-place it would need is what v3/v4 already demonstrate at 100%.

### The bug worth keeping

The first run returned **10.06 turns and 6.00 N·m on all ten "held-out" units, to the
decimal** — because the seed varied only the element's position on its nest, which nothing
in the tightening depends on. n = 1 wearing n = 10, the same defect as the 700.0 N clamp
and the 0.854 surface probe. Fixed by varying what actually differs between real
assemblies: **O-ring friction and squeeze, and the angle the cap is presented engaged at.**

**Seeds consumed:** 1400–1409. Start at 1500.

---

## V5-F RESULT — route wiring, end to end

`sim_poc/v5_route.py`. `RouteCell` subclasses `MemCell` → `Cell`, so triage, cleaning,
verification and the membrane station are the ones already measured, not reimplementations.
The routes come from `dp_process.V5_ROUTES` — **theirs, not invented**.

### The fork this cell refuses to decide

Their chart splits HARD into **RECTIFIABLE** and **NON RECTIFIABLE** on whether
rectification cost exceeds **80–90% — of what, no document in the set says.** Our
classifier outputs three grades and has no cost model, no price list and no labour figure,
so it **cannot** make that call, and a cell that guessed would be scrapping units on a
number it invented.

So HARD routes to **SCRAP_APPROVAL**, a *human decision gate*, and the cycle stops there —
which is exactly what `V5_ROUTES['hard_non_rectifiable']` already says we do. **Routing a
HARD unit correctly means "delivered to the gate", not "repaired."** That the fork is
undecidable from the documents joins the open-ask list.

### RETRACTION, 2026-08-05 — the first published end-to-end figure was wrong

**"end-to-end 28/28" is retracted. The correct figure for that run was 27/28**, and the
metric that produced it has been fixed. `run_route()` selected `plan` from the **predicted**
grade and then defined `routing_ok = (steps_done == plan)`, so it only ever asked *"did the
cell execute the plan its own prediction chose?"* — never whether that prediction matched
the unit's truth. `end_to_end` was built on it, so a misgraded unit that completed its
**wrong** route scored as a full end-to-end success. The published wording —
*"right route AND every step of it succeeded"* — asserted a check the code did not perform.
Seed 1517 (truth EASY → graded MEDIUM) is the counterexample, and it is in the committed
artifact of the original run.

`grade_correct` is now a field, is **required** for `end_to_end`, and is in the stats file
so the artifact audits itself. Route-plan compliance survives as its own metric: *"the cell
did what it decided to do"* is real and worth measuring, it was genuinely 28/28, and it is
neither deleted nor merged into end-to-end. Nothing else changed — not the classifier, not
its thresholds, not the routes, not a success criterion.

### The number — fresh seeds 1700–1727, looked at once

Re-measured after the fix, on seeds never previously run. *(Not 1600–1607: 1604 and 1607
are the V5-G demo seeds and were watched frame by frame, so they are burned.)*

| | |
|---|---|
| route-plan compliance | **28/28 (100%)** — executed the plan its prediction selected |
| right route (grade == truth) | **26/28 (92.9%)** — capped by triage |
| **end-to-end** | **26/28 (92.9%)** — right route AND every step succeeded |
| false-easy | **0/28** |
| missed-hard | **0/28** |
| easy route | 12/12 |
| medium route | 10/10 |
| hard → scrap-approval gate | 4/6 *(6 units routed there; 2 of them were truth MEDIUM)* |
| CLEAN + VERIFY_CLEAN | **22/22** verified with zero residue |
| CAP_TIGHTEN + VERIFY_LEAK | **10/10** passed, turns median 9.31, leak false-pass **0** |

**Both misgrades are seeds 1701 and 1715, truth MEDIUM → graded HARD.** Every mechanical
step still ran correctly; the two failures are triage errors propagating, which is exactly
what end-to-end is supposed to expose and what the old metric hid. Both are in the
**over-treatment** direction — a repairable unit sent to the human scrap-approval gate. That
is wasteful, not unsafe, and a person at that gate sees the unit before anything is scrapped.
**false-easy is 0/28**, and that remains the error that would matter.

**What 26/28 does and does not establish.** Triage is 97.5%, so ~0.7 errors in 28 units are
expected and **P(≥2 errors) ≈ 0.15** — 2 errors is entirely ordinary, **not** evidence that
routing has regressed or that triage is worse than published. Read the other direction too:
the earlier 27/28 was **not** evidence routing beats triage. End-to-end is capped by triage
and always will be — every wiring error this test can show is a triage error propagating.
Across both corrected route runs, right-route is **53/56 (94.6%)**, still consistent with
97.5%. Measuring a 2.5% rate properly needs a few hundred units, not fifty-six.

*(The earlier first look at 1500–1511 gave "12/12" under the broken metric. It is not
re-scored here — those rows were not kept — so it should not be quoted at all.)*

### The bug worth keeping — reading a model before the kinematics have run

> **CORRECTED 2026-08-05.** This section originally said `v5_triage.load_scene()` computes
> `CAB_TOP = 0.220` and that the frozen triage thresholds were calibrated against a
> half-face region — describing two internally-consistent conventions that were merely
> "not interchangeable". **Both claims are false and the explanation was inverted.**
> `load_scene()` calls `mj_forward` and returns **0.46**, v5_triage's module-level defaults
> are *already* `(0.58, 0.0) / (0.09, 0.125) / 0.010 / 0.46`, and the thresholds are
> therefore calibrated against the **full** face. The corrected account follows.

Seed 1500 graded **truth EASY → predicted HARD**, a two-class jump the published confusion
matrix says never happens. The counts were identical on both paths; only the *prediction*
differed. Cause: `v5_triage`'s face-projection constants are **module-level globals**, and
`v5_clean._sync_triage_globals()` writes them from `self.d.geom_xpos`. Called before
`mj_forward` has run, that array is **all zeros**:

| | `CFG_CAB_XY` | `CAB_BASE` | `CAB_TOP` | |
|---|---|---|---|---|
| `load_scene()` | (0.58, 0.0) | 0.010 | **0.46** | correct |
| `_sync` on **unforwarded** data | (0.00, 0.0) | −0.220 | **0.22** | garbage |
| `_sync` after `mj_forward` | (0.58, 0.0) | 0.010 | **0.46** | correct |

**The tell is `BASE == −TOP`.** With every position still at the origin, each geom spans
0 ± its own half-extent, so "the cabinet" becomes a box centred on the world origin whose
height is just the largest half-size (`cab_body`, 0.22). The device also lands at x = 0 —
the more damaging half — so the projected face quads miss the part and the grader returns
**HARD for every unit**. Measured: 4 of 7 sampled seeds flip, seed 1500 among them.

There are **not** two valid conventions here; there is one correct value and one
uninitialised read. `RouteCell` captures v5_triage's own
globals at construction and restores them before every grade; grading went 1 wrong in 1 to
**0 wrong in 12**.

**What that guard is worth today, stated honestly.** `verify()` is the only caller of
`_sync_triage_globals()`, and in the current cycle it always runs *after* `mj_forward` —
where it writes values **identical** to the captured ones at every indexer angle
(0/90/180/270/360 all checked). So the restore is currently a **no-op**: insurance against
call ordering, not a live fix. The root cause is that `v5_clean.Cell.__init__` never
forwards its `MjData`. Correcting *that* is a controller change requiring a full re-eval,
so it is deliberately not done. **The reusable lesson is the one the wrong story obscured:
reading `geom_xpos` before `mj_forward` does not fail loudly — it returns a coherent-looking
model centred on the origin.**

**Seeds consumed:** 1500–1511 (first look) and 1512–1539 (the retracted run), plus
**1700–1727 (the corrected headline, 2026-08-05)**. Also burned: **1604 and 1607**, the
V5-G demo seeds — rendered and watched, so never held-out again. **Start at 1728.**

---

## V5-G RESULT — the video, and the camera that must not move

`sim_poc/v5_video.py --render SEED [--speed N]`. Renders a full route cycle with a HUD:
live workpiece metrics, the route plan, stage chips, a stamped speed-up, and — the part
that matters — **the caveat for whatever is on screen at that moment.**

`media/v5_cell_medium.mp4` (62 s @ 4×, the full TRIAGE → CLEAN → VERIFY → MEMBRANE → DIP
line) and `media/v5_cell_hard.mp4` (the scrap-approval gate).

**Every station carries its own on-frame caveat**, because a video is where overstatement
is easiest and hardest to catch:

| station | on-frame text |
|---|---|
| TRIAGE | class NAMES are DrinkPrime's, BOUNDARIES are ours |
| CLEAN | no cream, detergent or chemistry is simulated |
| VERIFY | re-inspected through a SECOND camera — the triage camera cannot see the top face |
| MEMBRANE | threaded, multi-turn to torque — not our bayonet; geometry is PLACEHOLDER |
| **DIP** | **BUBBLES = MODELLED FROM TORQUE, NOT FLUID SIM** |
| SCRAP | HARD forks on rectification cost; we have no cost model → human gate |

**Numbers before pictures, deliberately.** `--render` existed nowhere in v5 until every
station had been measured. A video is a claim; the evidence should predate it.

### The bug worth keeping — a demo camera and a measurement camera are not the same object

The first cut framed the dip badly, so I re-aimed `verify_dip` for a better shot. The next
render showed **17835 bubble px → FAIL on a unit that had just stalled at 6.00 N·m and was
sealed** — a false fail, against a station that had published **0/10**.

`verify_dip` is a **measurement fixture**: the bubble threshold is frozen against its exact
pose and the ROI is projected from it. Moving it slid bright water and bin edge into the
ROI. *"A vision result is only as valid as the fixture that presents the part"* — the
v4 lesson that cost 37 points of accuracy — **applies to the camera as much as to the
part.**

Fixed by adding a separate `demo_dip` camera with no measurement role. `verify_dip` is back
at its calibrated pose and **V5-E reproduces exactly**: median 9.68 turns, 10/10 honest
pass, 0 false fail, 10/10 sabotage caught, 0 false pass, `stats_v5_membrane.json`
byte-identical.

**Demo seeds:** 1607 (medium), 1604 (hard). **Both are now BURNED for evaluation.**
*(This line previously read "rendering consumes no evaluation seeds." That is true only in
the sense that rendering writes no stats file. These two seeds were rendered and watched
frame by frame, so their outcomes are known — they can never serve as held-out units again,
and the ledger in `CLAUDE.md` now says so.)*
