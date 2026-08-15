# HARD handoff — backing `ROUTE_TO_SCRAP_APPROVAL` with a motion

**DESIGN ONLY, 2026-08-15.** This file is the only artifact of this session: no scene, no
code, no existing document was touched, nothing was run that writes anything. Every number
below is read from the named file, not recalled; layout coordinates are from
`sim_poc/make_scene_v5.py` and `CELL_SPEC.md` §3; route figures are from the committed
`sim_poc/stats_v5_route.json` (seeds 1700–1727). Where a number is a placeholder, an
assumption, or ours rather than DrinkPrime's, it is labelled inline, every time.

---

## 1. The problem, in this repo's terms

The HARD non-rectifiable route is two steps: `TRIAGE → ROUTE_TO_SCRAP_APPROVAL`
(`dp_process.V5_ROUTES["hard_non_rectifiable"]`, whose own note says *"We stop at routing
it out of the line"*). The second step is **UNBACKED** in `v5_route.STEP_EVIDENCE`: it is
*"a software decision. NO robot or indexer motion"* — the string is all of it. Worse,
`run_route()` sets `steps_ok = True` **unconditionally** for that route, so a HARD unit
scores an end-to-end success on a correct grade plus a matching trace alone.

The committed artifact (seeds 1700–1727, n = 28):

| metric | value | what it asks |
|---|---|---|
| route-plan compliance | 28/28 | did the cell run the sequence it chose |
| right-route | 26/28 | was that sequence the right one for the unit's truth |
| end-to-end | 26/28 | right route AND every step "succeeded" |
| **fully backed** | **22/28** | end-to-end AND no step passed by being named |

Six units took the scrap route: seeds **1701, 1702, 1703, 1707, 1715, 1724**. Two (1701,
1715, truth MEDIUM) fail end-to-end on `grade_correct`. The other **four (1702, 1703,
1707, 1724, truth HARD) are the entire 26 → 22 gap**: each scored an end-to-end success
whose terminal action is a string. **Physical handoff: 0/6 implemented** (HANDOVER.md,
honesty label 5). The repo has already retracted one metric ("end-to-end 28/28") for
scoring a prediction against itself; this is the surviving instance of the same defect
class — a step that passes by being named — and it is why the quotable headline is 22/28.

**What "fully backed" must mean for a delivery step.** `MEMBRANE_INSERT` set the
precedent: it went from UNBACKED to MEASURED only when the arm actually moved the element
and the judgement was made **on the part** (0.30 mm median alignment against 1.5 mm
clearance). By the same standard, a step whose verb is *deliver* is backed when **the
unit's own measured pose ends inside a declared destination volume, upright, with no
teleport in the trace** — not when a beacon lights, and not when the step is reclassified.

---

## 2. What every mechanism needs first — the shared foundation

### 2.1 The cabinet has no joint

`make_scene_v5.py` builds the cabinet as a **rigid child of the turntable body** — no
freejoint (the freejoints in the scene are `padtool_free`, `bowl_free`, `elem_free`,
`capblank_free`; the cabinet has none). Nothing can move a welded child body. So every
mechanism below, including the flag-and-park camera check, starts with the same generator
edit:

- **`cab_free`**: a freejoint on the cabinet body.
- **`cab_lock`**: a weld equality holding the cabinet to the platter, **active by
  default** — the `toollock` idiom already in the scene (weld, 4 mm/4° capture, measured
  coupling drift 0.16 mm). Deactivating it is the release; on the real cell this is a
  pneumatic clamp or registration nest, and the weld's active flag is its command.
- **Keyframe qpos updated in the same commit.** This trap has bitten **four times**
  (`HANDOVER.md`); a new freejoint extends `nq` and `v5home` will otherwise spawn the
  cabinet at the world origin, 20 mm inside the bench.
- New actuators appended at the **end** of the actuator block, and the `ctrl layout (10):
  7 arm | 1 gripper | 1 tt | 1 capdrv` comment updated — every harness indexes `ctrl`.

**This is a re-baseline event and must be treated as one.** Adding a freejoint changes the
state vector; unlike the cap-thread ridges (`contype`/`conaffinity` 0, mass 0, asserted
byte-identical), a new joint plus an active weld carrying 22.6 N presses cannot be assumed
byte-identical. The clamp re-baseline is the template: archive `stats*.json` first, re-run
every protected eval at its published `--seed0`, and publish a before/after table. Expect
small drift; the V8 tray — a mere new collidable body — coincided with a 1.2 s membrane
shift that was recorded as *plausible but not isolated*. Budget for the same honesty here.

### 2.2 The clamp is real anyway — the weld currently hides a fixturing question

Tipping arithmetic on the placeholder cabinet (180 × 250 × 450 mm, 8.0 kg — **both
placeholders, open asks**; composite CG ≈ 0.23 m from the generator's 0.875/0.0625 mass
split):

- Restoring moment about the 90 mm half-depth base edge: 8.0 × 9.81 × 0.090 = **7.1 N·m**.
- The published peak wipe force, 22.6 N, applied horizontally near the top of a face
  (z ≈ 0.44 m): **9.9 N·m** of tipping moment.

**A merely free-standing cabinet tips under the cleaning pass this cell already performs.**
The rigid child body has been silently doing the clamp's job since V5-A. Building any
handoff forces this into the open, which is a gain independent of the metric: the real
cell needs a clamp, and after this work the model will say so instead of hiding it.
(All of §2.2's numbers inherit the mass/size placeholders and MuJoCo's default sliding
friction μ = 1.0 — the cabinet and platter geoms set no `friction` attribute. Re-derive
when real mass and CAD land.)

### 2.3 Bench occupancy — the only clear eject azimuth is −Y

Bench working area 1100 × 1200 mm: X ∈ [−0.20, 0.90], Y ∈ [−0.60, +0.60], top at z = 0.

| direction from the indexer (0.580, 0) | blocked by |
|---|---|
| +X | inspection backdrop at X = 0.854 (spans Y ± 0.46) |
| −X | arm riser ⌀150 at the origin, and the arm itself |
| +Y | water bin (X 0.409–0.591, Y 0.279–0.461), +Y backdrop at Y = 0.414, membrane station (0.340, 0.300) |
| **−Y** | **clear in the lane X ∈ [0.49, 0.67]**: tool post ends at X = 0.355, solution tray at X = 0.213, inspection camera sits at X = 0.100 |

A −Y eject lane in line with the indexer centre — X = 0.58 ± 0.09 (the cabinet's 180 mm
depth), from the platter edge at Y = −0.175 to the bench edge at Y = −0.60 — clears the
nearest fixture (tool post) by ~135 mm in X. Every placement below is a **candidate**, not
a decision: the solution tray taught that 3 of 4 plausible spots pass the reach gate and
the obvious one fails (all four vertical faces lost coverage). **`v5_reach.py --scene` and
`--indexed` decide, per the standing rule: never add a geom without re-running them** —
a 6 mm backdrop panel once cost an entire face.

### 2.4 The plant's words, and whose the destination is

Their QC chart's node is **"SEND FOR SCRAP APPROVAL (RECTIFICATION COST GREATER THAT
80-90%)"** — terminal, source typo preserved, and *80–90% of what is not stated*
(`dp_process.QC_NODES`). The fork is a **human decision gate**: this cell has no cost
model and `V5_PLAN.md` records that it refuses to decide the fork. Two more corpus facts
bear directly on mechanism choice:

- *"SEND"* is a verb of motion. A physical delivery is inside their vocabulary.
- The plant's scrap logistics are **already human**: *"rejected materials removed from the
  testing area DAILY"* (stage 1) and *"QC persons validate & certify rejections every
  2 hrs"* (stage 10 / QC page 3) — `dp_process.SCRAP_STREAMS`.

No document places a scrap area or names a fixture for it. **The destination — its
position, its geometry, the very existence of a staging zone on this bench — is OURS**,
and must be labelled ours every time it is reported, exactly like the triage boundaries.
The zone below is named **SCRAP_APPROVAL_STAGING**, not "scrap bin": the unit is
presented for a human decision, not disposed of. Calling it a scrap bin would decide the
fork we have refused to decide.

---

## 3. Mechanism A — INDEXER EJECT (pusher across the platter onto a flat staging lane)

### 3.1 Three sub-variants rejected on arithmetic before any build

- **Gravity tilt** (tilt the platter, let the unit slide): sliding on the default μ = 1.0
  interface starts at 45°; tipping starts at atan(0.125/0.23) ≈ **28°** across the width
  and atan(0.090/0.23) ≈ **21°** across the depth. **The unit topples long before it
  slides.** Sliding-before-tipping needs μ ≤ 0.45 (with the project's 1.18× margin,
  against the 28° edge), i.e. an engineered low-friction platter — which then has to
  carry the wipe forces of §2.2 — plus a new powered tilt axis under a 9 kg
  platter-plus-unit, and a tilted platter moves the device out of every camera
  calibration. Rejected.
- **Spin-eject on the existing `tt` axis**: lateral acceleration at the CG tips the unit
  at ω²r ≈ 5.2 m/s² (ω ≈ 7.2 rad/s at r = 0.1 m, ~69 rpm), below the ω ≈ 9.9 rad/s
  needed to overcome μ = 1.0 — **it topples before it slides**, and the departure
  tangent is uncontrolled anyway. Rejected.
- **Arm push**: sliding the unit needs μ·m·g = **78 N** at the default friction — 1.7×
  the 45 N ceiling of the only contact regime this sim has validated, and ~8 kgf against
  a 3.5 kg-rated arm. Even on a low-friction lane (~12 N at μ = 0.15) it would put the
  compliant *normal-press* pad tool into a sustained *lateral* shove — a sparse, novel
  contact pattern, which is exactly the signature behind this repo's two prior force
  blowups (91.5 N targeted+stroke; 98.67 N targeted-under-clamp). Rejected: the transfer
  gets a dedicated 1-DoF actuator whose force is a spec, not a hope.

### 3.2 The design

The existing commanded axis does what it is good at: **`tt` indexes the unit to the eject
azimuth** (180°, so the flat back panel — not the 4 mm-proud facia — meets the blade),
then a new linear **pusher** translates the unit across the platter, along a **flush
low-friction lane**, into a flat **staging zone** near the bench edge where a human can
reach it from outside the cell.

- **Lane**: a strip on the bench, top surface at z = 0.010 — **flush with the platter
  top**, so there is no 10 mm step for the leading base edge to catch on (the v4 staging
  nest fouled a part on exactly a clearance nobody checked; a step this size across a
  250 mm base pitches the unit ~2° and catches its edge). 2 mm gap to the platter rim so
  the platter still rotates freely. Lane friction set explicitly to **0.15 [assumed,
  PTFE-class — measure on the real strip]**, making the push force ~12 N instead of 78 N.
- **Pusher**: a slide-joint blade, ~180 × 40 mm face, contact face at **z ≈ 0.05 m** —
  far below the h < half-extent/μ = 0.83 m tip bound at μ = 0.15 (at μ = 1.0 the bound
  is 0.125 m, another reason the lane friction is engineered, not defaulted). Stroke
  ≈ 0.55 m, quasi-static at **0.05–0.10 m/s** → 6–11 s, on the HARD route only (which
  today costs ~0 s, since TRIAGE is camera-only). Candidate mounting: a rail east of the
  lane at X ≈ 0.76–0.80 (clear of the platter's 0.755 m X extreme, 54 mm clear of the
  +X backdrop), carrying the blade on an L-arm across the lane — subject to §2.3's gates.
- **SCRAP_APPROVAL_STAGING [ours]**: zone centre (0.58, −0.455), on the bench, flat. The
  250 mm footprint then spans Y −0.58…−0.33; worst-case within tolerance the leading edge
  overhangs the bench edge by ≤ 25 mm with the CG ≥ 100 mm inboard — stated, not ignored.
- **Sequence**: VERIFY-style drive, no teleports: arm to PARK (it is already there — the
  HARD route does no cleaning) → assert TCP outside the lane prism *from qpos* → `tt` to
  180°, **1.2 s settle dwell** (the dwell that may never be shortened) → `cab_lock`
  release → pusher extend → settle 1.0 s → predicate → pusher retract → flag for the
  human (the §5 beacon is reused here: the *approval* is still a human's).

### 3.3 Scene gains, in the generator's idiom (edit `make_scene_v5.py`, never the XML)

Bodies/geoms: `scrap_lane` (flush strip, explicit friction, **matte black** — the platter
taught that a mid-grey fixture reads as a dent, 2374 false pixels), `pusher_rail` +
`pusher_blade` (matte), `scrap_zone` **site** (visualisation-only, `contype`/`conaffinity`
0). Joints: `cab_free` (freejoint), `pusher_ext` (slide). Equalities: `cab_lock` (weld,
default active). Actuators: `pusher` (position, force-limited via `forcerange` — the
`capdrv` precedent: the limit is the spec). Plus the §2.1 keyframe and ctrl-comment edits.

### 3.4 The FULLY BACKED predicate — checkable, per unit, measured from state

`eject_ok` is true iff **all** of the following, measured from `d.qpos`/`d.qvel` (never
from `ctrl`, never from position differences across a step — the 51 m/s lesson):

1. `cab_lock` was active at cycle start and inactive only during EJECT (trace-asserted).
2. Throughout EJECT the cabinet's freejoint velocity stays ≤ 0.3 m/s and is continuous —
   **zero teleports**: no direct qpos write to `cab_free` outside `reset()`.
3. After a 1.0 s settle: base centre within **±50 mm** of (0.58, −0.455) [zone is ours];
   base z = 0.010 ± 3 mm (on the lane, not wedged); **upright ≥ 0.95** (cabinet +Z ·
   world +Z — v2's own success criterion, reused); yaw within ±10° of the eject azimuth.
4. The platter is **empty by camera**: `verify_top`'s ROI over the disc reads below the
   0.30 background threshold (matte platter) with device-coloured pixels < bound — the
   same class of check as VERIFY, and it reuses the existing second camera V5-D required.
5. Battery, on **fresh seeds entered in the ledger by named phase** (next free block
   2220+; 1700–1727 are spent, and 1702 is burned/demo): a dedicated
   `v5_scrap --eval N` — honest delivery **N/N**; sabotage (pusher disabled, stroke −50%,
   `cab_lock` left engaged, unit pre-tipped by fixture) **caught n/n with 0 false
   "delivered"** — a delivery check that cannot fail is not evidence, per V5-D. Report
   the margin, not just the rate: worst in-zone error, worst upright, peak push force.

With that in hand, `STEP_EVIDENCE["ROUTE_TO_SCRAP_APPROVAL"]` becomes **MEASURED**, the
unconditional `steps_ok = True` is deleted (`steps_ok = eject_ok` for the scrap route),
and a `delivered` field is added to the stats rows — additive, schema-compatible, the
`grade_correct` precedent.

### 3.5 Failure modes — an 8 kg cabinet sliding off a platter is not a small thing

- **Tipping**: pushed too high, too fast, or decelerated into a snag. Mitigated by blade
  height, quasi-static speed, and the upright term of the predicate; **sabotage row
  "pre-tipped unit" exists so a toppled delivery can never score.**
- **Jamming**: base edge on the platter/lane gap, or blade riding onto the facia. The
  flush lane and the 180° index address the known causes; `v5_check_scene` gains
  assertions (lane flush within tolerance, gap ≤ 2 mm, blade rest clear of the 0.154 m
  corner-sweep radius of the rotating cabinet, zero spawn interpenetration — the bin once
  spawned 6 mm inside the platter and this gate caught it in one run).
- **Swept volume**: the lane prism (X 0.49–0.67, Y −0.60…+0.175, z 0–0.47) is space the
  arm must never occupy during EJECT, and the rail/blade are new collidable bodies the
  pose planner must avoid for **every** route — the V8 tray showed a new collidable body
  can shift numbers it never touches. Paired renders before/after, same seed, per V8.
- **Vision contamination**: the zone sits ~50° off the inspection camera's axis against
  its 48° fovy — computed to be out of frame, **verify by render, then re-run triage at
  its published seeds and diff the stats file** (archive first; any bare `--eval`
  overwrites a baseline).
- **A misgraded unit gets delivered**: seeds 1701/1715 show ~2/28 truth-MEDIUM units
  reach this route. The mechanism should deliver them anyway — **catching the misgrade is
  the human gate's documented job**, and the exposure is triage's false-hard rate, which
  stays a separately reported number.

### 3.6 Choreography preconditions — written down, because unwritten ones get broken

The V8 dip broke V7.2's unwritten "arm arrives at face 0 from the tool lift" and nothing
errored (coverage 100 → 75%, force 22.6 → 98.3 N). The eject's preconditions, stated:

1. Arm TCP outside the lane prism, asserted from qpos, before `cab_lock` releases.
2. `tt` settled (the full 1.2 s dwell) before blade contact.
3. `cab_lock` re-engages only at `reset()`, with the next unit's spawn — never mid-cycle.
4. EJECT ends with the arm in a **named** configuration (it never left PARK), recorded in
   the trace, so a later station inherits a written pose, not a lucky one.
5. Nothing materialises into space the gripper or blade occupies (standing rule).

### 3.7 Cost, in this codebase's units

Generator edit (§3.3) + keyframe/ctrl updates + ~6 new `v5_check_scene` assertions + new
CELL_SPEC §3 rows and §8 checklist entries asserted by `v5_check_spec` (55 values today,
grows to ~62) + `v5_reach --scene`/`--indexed` re-runs + **the §2.1 freejoint re-baseline
of every published contact number** + two sweeps (lane μ × push speed; stroke margin) +
`v5_scrap` fresh-seed battery + the 28-unit route re-measure on a fresh block + a paired
video (render path calls the evaluated methods — the 11f9ea9 rule). Estimate **2–3
sessions**, of which the single largest item is not the mechanism but the re-baseline.

---

## 4. Mechanism B — POWERED TRANSFER SEGMENT (a carriage at the bench edge)

### 4.1 Model honesty first: MuJoCo has no conveyor

There is no belt primitive, and faking one by applying `xfrc` to the unit while "in
contact" would be a force with no mechanism — the same trick this repo refuses elsewhere
(a rendered liquid slab is not a fluid sim). The honest model is a **shuttle carriage**: a
flat bed on a linear slide joint, velocity- or position-driven, that genuinely carries the
unit; the carriage returns empty at cycle end (a fixture action, labelled). On the real
line the purchased part may be a belt; the sim's carriage is the measurable equivalent,
and at one-unit-at-a-time rates a shuttle tray is a defensible real design anyway.

### 4.2 The transfer is the hard part, and it is Mechanism A

Something must move the unit from the platter onto the bed. The arm cannot (§3.1
arithmetic: 78 N at default friction, an unvalidated lateral contact regime either way),
so the transfer is **exactly (a)'s pusher onto exactly (a)'s flush surface** — the
carriage bed top at z = 0.010, replacing the passive zone at the end of the lane.
**(b) is strictly (a) plus one powered axis.** It cannot be built first, only after.

Candidate geometry [ours, gate-checked before adoption]: bed ~200 × 450 mm at lane end,
travelling +X along Y ≈ −0.50 (just outside the +X backdrop's Y ± 0.46 span — 40 mm
clearance, thin enough to demand a `v5_check_scene` assertion) to a presentation position
at the bench's +X edge, where the unit faces the human from outside the arm's workspace.

### 4.3 Predicate

(a)'s predicate items 1–4 for the push-on transfer, with the zone replaced by: unit
footprint fully on the bed with ≥ 10 mm margin (from qpos + known half-extents), **then**
carriage joint at end-of-travel ± 2 mm (its own qpos — a real encoder analogue), unit
still upright ≥ 0.95 and within ±20 mm of its on-bed pose after the ride (it must ride,
not skate), platter empty by camera, plus the same sabotage battery extended with:
carriage disabled; unit deliberately placed half-on (must refuse to move); emergency-stop
mid-travel (unit must remain upright and the step must score FAILED, not delivered).

### 4.4 Failure modes and cost

Everything in §3.5, plus: the flush tolerance between lane and moving bed (a moving step
is worse than a fixed one); acceleration limits so the ride does not tip what the push
did not (bound: a ≤ g·(half-extent/CG) ≈ 3.8 m/s² across the depth, placeholder-derived,
so run it at ≤ 0.5 m/s² and never think about it); one more actuator in the ctrl layout;
the carriage as yet another collidable for the planner. Cost: **(a) + 1–2 sessions**, and
on the real cell it is the only mechanism class here that is a genuine new procurement
(the indexer precedent: commodity, but unpriced until quoted).

### 4.5 What it buys over (a)

A defined presentation pose **outside the cell** (a human never reaches over the bench),
controlled deceleration instead of a free settle, and the natural extension point if the
plant ever wants automated transport toward its scrap area. None of that is needed to
back the step; all of it is needed only at volumes where (a)'s single staging position
saturates. That is an evidence question — see §6.

---

## 5. Mechanism C — FLAG-AND-PARK (present, flag, human removes, cell verifies)

### 5.1 The design

The cell drives what it already has to a **registered SCRAP-PRESENT state** and stops:

- `tt` to a declared angle [ours; 0° is fine — the unit's front faces the aisle-side
  camera], arm at PARK. Both **driven, not teleported** — the VERIFY precedent: verify
  used to teleport, cost "zero seconds" for months, and now drives for a real 10.0 s.
- A **physical flag**: a small mast at the bench edge with a hinge joint and its own
  position actuator, ~90° throw. A flag and not a rendered lamp, deliberately: a
  commanded joint with measured qpos is evidence in this repo's sense; an emissive
  material toggled in software is another string. Non-colliding (`contype`/`conaffinity`
  0, the `tt_mark` idiom), small mass, out of every camera's device ROI, matte.
- A **human removes the unit** — in sim, a fixture action, labelled as such every time
  (the cap-presentation precedent: fixture actions are legal when declared). Two tiers:
  - **(c-min)** — no cabinet freejoint. Removal folds into the load/unload boundary that
    HANDOVER label 7 already declares unmodelled. Cheapest possible; verifies nothing
    about removal.
  - **(c-full)** — with §2.1's freejoint + weld, the fixture lifts the unit out
    (labelled teleport at the cycle boundary, never into occupied space), and the cell
    **verifies removal by camera** before accepting the next unit: `verify_top` ROI over
    the platter below the 0.30 background threshold, as in §3.4 item 4.

### 5.2 Predicate

`presented_ok` iff: `tt` qpos within ±0.5° of SCRAP-PRESENT (the indexer's own spec
repeatability), arm joints within ±0.01 rad of PARK, flag hinge ≥ 85° of its throw and
held 1.0 s — all from qpos, no teleports in the drive. **(c-full) adds** `removal_verified`:
platter-empty by camera after the fixture removal, and the **occupied-platter refusal**:
if the flag cycle completes with the unit still present (the sabotage arm), the next
unit's load must refuse, n/n, with 0 false "empty". Without that refusal the check is a
verifier that cannot fail, which V5-D showed is worth nothing.

### 5.3 What it is honestly worth — and the metric guard

This matches the plant best: scrap approval **is** a human gate in their chart, their
humans already clear rejects on a documented daily cadence, and `V5_PLAN.md` already
defines HARD success as *"delivered to the gate, not repaired"*. But the unit does not
move by any cell motion, so the step earns **PROXY, not MEASURED** — a real driven
presentation plus a measured flag plus (c-full's) real camera check on a fixture-staged
outcome, the same class as `LEAK_DIP`.

**And here is the trap, named so it cannot be walked into:** `fully_backed()` as coded is
`not row["unbacked_steps"]` — reclassifying the step to PROXY flips the headline to 28/28
**with no unit ever moving**. Doing that would be the retracted defect with a friendlier
face. The guard ships in the same commit as (c): `report()` and the stats file gain a
`hard_handoff` field (`UNBACKED | PROXY | MEASURED`) plus a `fully_backed_strict` that
additionally requires the terminal delivery step of any off-line route to be MEASURED.
**The quoted headline stays 22/28 until `hard_handoff: MEASURED`** — the label that
travels with (c) is *"HARD presentation is driven and flagged; removal is a fixture
action"*.

### 5.4 The blocking cost, which is (c)'s real price

(c) has one staging position: the platter. Every HARD unit halts the cell until a human
clears it. Arithmetic, not measurement: at the 2:36.1 measured cycle and this run's 6/28
hard-routed fraction (21.4%), a continuously fed cell raises the flag roughly **every
12 minutes**; at the estimated 130–200 units/day demand that is ~28–43 human visits/day.
Fine if someone works near the cell; fatal to throughput if the plant's *daily* removal
cadence is taken literally. Both inputs are labelled: the fraction is one 28-unit run,
the demand is `TRADE_STUDY.md`'s `[assumed]` range.

### 5.5 Cost

(c-min): generator edit (mast + hinge + actuator + registered-pose constants) + keyframe
update (a new joint extends nq — the 4× trap applies even here) + ~3 gate assertions +
CELL_SPEC rows + the `v5_route` drive-and-measure change + metric guard + fresh-seed
re-measure + re-run of the three protected evals with a stats diff to **assert** (not
assume) the published numbers are unchanged. **~1 session.** (c-full): + §2.1's
freejoint/weld and re-baseline. **~2 sessions**, nearly all of it (a)'s prerequisite work.

---

## 6. Recommendation

**Build (c-full) first. Then (a). (b) only on evidence that (a)'s staging position
saturates.**

Reasoning:

1. **(c-full) is the cheapest honest step and it is not throwaway.** It converts the bare
   string into a driven presentation, a measured flag, and a camera-verified removal with
   a sabotage battery — UNBACKED → PROXY — while introducing exactly the foundation (a)
   needs anyway: `cab_free`, `cab_lock`, the empty-platter check, and the freejoint
   re-baseline. Doing the re-baseline in a commit that adds **no new contact mechanism**
   isolates one variable: any drift in the published numbers is attributable to the
   freejoint + weld, not tangled with a pusher. That is the run-the-new-thing-alone rule.
2. **(c) matches the corpus better than anything else here.** Scrap approval is their
   human gate; reject-clearing is already a documented human function on their line; the
   fork's 80–90% criterion is unstated and this cell refuses to decide it. A cell that
   presents and waits is modelling their process; a cell that carts units to a bin of our
   invention is wearing their vocabulary — the tank-vs-cloth lesson, again.
3. **But (c) must not move the headline, and the guard ships with it** (§5.3). The
   22/28 → 28/28 claim requires the unit to move, so it requires (a).
4. **(a) over (b) is not close.** (b) is (a) plus one axis — its hard part, the transfer,
   *is* (a)'s pusher — so building (a) first loses nothing and defers the only genuinely
   new procurement. (a) also spends the existing commanded axis well: `tt` chooses the
   face that meets the blade, which is what an indexer is for.

**Evidence that justifies each escalation:**

- **(c) → (a):** the founder's answer on attendance — if no one works within minutes of
  the cell, §5.4's arithmetic says (c) blocks ~28–43 times/day and the cell needs to
  place units without a human; or the funded demo needs the 28/28 fully-backed number,
  which only a measured delivery provides. Ask him with §5.4's numbers attached — this
  joins the open-asks list either way, because the answer also sizes the staging zone.
- **(a) → (b):** measured saturation — HARD arrivals outpacing human clearing of a
  one-unit zone in a queueing pass at target volume; or the plant asking for delivery
  beyond the bench (their scrap area, not our bench edge). Absent either, (b) is
  hardware without a question.

Prerequisites that sharpen (but do not block) (a): the real cabinet **mass** and envelope
(every tipping and force number in §2–§3 inherits the placeholders) and a measured
platter/lane friction. All already on the open-asks list.

---

## 7. What this unblocks

Fully backed goes 22/28 → 28/28 **only if** the chosen mechanism actually moves units on
HARD routes to a measured destination — reclassification moves nothing, and the §5.3
guard makes that structural. The number is then **re-measured, never asserted**: a fresh
28-unit route run on a ledger-entered block (2220+ is next free; 1700–1727 are spent, and
running `v5_route` off its default `--seed0 1700` overwrites the published artifact, so
archive first). Expect the re-measure to land near 26/28 on `right_route` and
`end_to_end` regardless — those are triage-limited (97.5% classifier; P(≥2 errors in 28)
≈ 0.15) and no eject fixes a misgrade. That residue is not a flaw in the handoff: the
mechanism delivers, the human decides, and the ~2-in-28 misgraded deliveries are exactly
what the plant's approval gate exists to catch. What changes is the sentence under the
headline: every step of every route, including the one that ends off the line, will have
a motion and a measurement behind it — which is what "backed" has meant here since the
word was first needed.
