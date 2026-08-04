# Cell specification — v5 refurbishment cell

**Purpose: this is the document you build and program the real cell from.** Every number
here is read out of the simulation that produced the results in `V5_PLAN.md`, not typed
from memory. Where the simulation cannot tell you something, it says so rather than
guessing.

Generated against `sim_poc/ufactory_xarm7/refurb_scene_v5.xml` (from
`sim_poc/make_scene_v5.py`), MuJoCo 3.11.0 / numpy 2.5.1 / Python 3.12.13 (pinned).

---

## 1. The robot

**UFACTORY xArm7**, 7-DoF, 700 mm reach, 3.5 kg rated payload, ±0.1 mm repeatability.

**Our model's joint limits were checked against the UFACTORY datasheet and match on all
seven joints:**

| joint | model | datasheet |
|---|---|---|
| J1 | −360° … 360° | −360° … 360° |
| J2 | −118° … 120° | −118° … 120° |
| J3 | −360° … 360° | −360° … 360° |
| J4 | −11° … 225° | −11° … 225° |
| J5 | −360° … 360° | −360° … 360° |
| J6 | −97° … 180° | −97° … 180° |
| J7 | −360° … 360° | −360° … 360° |

So **a pose that solves in this simulation is inside the real arm's joint envelope.**
The reachability study additionally rejects any pose that comes within 1° of a limit, so
there is margin on top.

**Payload utilisation is 6%.** The heaviest thing the arm carries is the wiping pad tool
at **0.220 kg** against a 3.5 kg rating. Payload is not a constraint anywhere in this
cell — which also means a heavier, stiffer tool is affordable if V5-C wants one.

**Reach envelope, measured from the model** by sampling 200,000 random poses within the
joint limits and recording the TCP position relative to the `link_base` origin:

| | measured |
|---|---|
| max planar (XY) distance, base → TCP | **0.928 m** |
| max spherical distance, base → TCP | 1.194 m |

> **Do not compare these directly with the datasheet's 700 mm.** They use different
> reference points: ours is measured from the mounting flange to our TCP (which is
> 172 mm beyond the gripper base, and the flange sits 267 mm below J1), while UFACTORY's
> figure is the nominal working radius. The numbers above are useful for checking that
> our own stations are in range — not for restating the robot's specification.

Every station in §3 sits comfortably inside it: rotary indexer at 0.580 m planar radius,
device front face 0.490 m, tool post 0.453 m.

---

## 2. Coordinate frames — read this before typing any number into the SDK

The simulation's world origin is **directly under the arm's mounting point, at bench-top
height**. That is *not* the same as the robot's own base frame:

```
world z = 0            bench top surface
world z = 0.120        arm kinematic root (`link_base`) — the mounting flange
```

> ⚠️ **There is NO riser in the simulation.** The 120 mm offset is inherited from the
> stock arm model (`xarm7.xml`, unchanged from MuJoCo Menagerie); it is not a modelled
> fixture. Nothing occupies 0 < z < 0.117 near the arm axis, so **no arm-to-riser
> clearance has ever been checked, and no riser diameter or footprint is specified.**
>
> This is not academic. Injecting a virtual riser column into the reachability study
> vetoes poses: at 150 mm diameter, 6 of 380 accepted poses are lost and side-face
> **exact-normal** coverage falls from 83% to 27%; at 250 mm diameter, 32 of 406 are lost
> and it falls to 67%. (30°-cone coverage stays 100% in both cases.) `link5` passes as
> low as **z = 103 mm within 75 mm of the base axis** — right where a riser would be.
>
> **Before quoting any reachability number as riser-inclusive, add a riser geom of the
> real diameter and re-run `v5_reach.py --indexed`.**

When you build the real cell you must either reproduce a 120 mm rise, or subtract 120 mm
from every Z coordinate below.

### Converting a sim coordinate to an xArm SDK coordinate

The xArm Python SDK works in **millimetres**, relative to the **robot base frame**:

```
x_sdk_mm = x_world * 1000
y_sdk_mm = y_world * 1000
z_sdk_mm = (z_world - 0.120) * 1000
```

### Tool centre point

Our TCP is the site `link_tcp`, **172 mm along +Z from the `xarm_gripper_base_link`
frame**. Set the real robot's TCP offset to match, or every Cartesian command will be off
by that amount.

> ⚠️ **The gripper's finger pads sit roughly 25 mm ABOVE `link_tcp`.** The TCP is *not*
> the contact point. This has bitten this project twice (see PAIN_JOURNAL); every grasp
> height in v2/v3/v4 is tuned around it. Measure the real pad offset before reusing any
> grasp height.

### Wrist camera

Mounted on `xarm_gripper_base_link` at local **(0.060, 0, 0.030) m**, optical axis
`zaxis = (0.39, 0, −0.92)`, **fovy 75°**, rendered at 640×480 for inspection.

> ⚠️ **Hand-eye calibration is required on the real cell and is not modelled here.** The
> simulation knows the camera-to-TCP transform exactly. A real one does not — you have to
> measure it. v4 already demonstrated what happens when a presentation transform is
> assumed instead of measured: the classifier scored 90% on a rig and **53% in the cell**.

---

## 3. Station positions

All coordinates in metres, sim world frame. Convert with §2 before use.

| station | X | Y | Z | notes |
|---|---|---|---|---|
| arm mounting flange | 0.000 | 0.000 | 0.120 | 120 mm above bench; **riser not modelled** (§2) |
| **rotary indexer** (disc centre, top face) | 0.580 | 0.000 | 0.010 | ⌀350 mm, 10 mm proud of bench |
| **device** (footprint centre, base) | 0.580 | 0.000 | 0.010 | stands on the indexer |
| tool post (top face) | 0.300 | −0.340 | 0.020 | ⌀110 mm flat plate |
| pad tool (stem axis, at rest) | 0.300 | −0.340 | 0.040 | body origin |
| inspection backdrop (panel face) | 0.854 | 0.000 | 0…0.720 | matte, 920 × 720 mm |
| bench top | — | — | 0.000 | 1100 × 1200 mm working area |

### Device (placeholder dimensions)

**180 (depth, X) × 250 (width, Y) × 450 (height, Z) mm, 8.0 kg.** All four are
**placeholders** — no DrinkPrime document gives a cabinet envelope *or* a mass
(`dp_process.MISSING`). V5-0 established that device size is not on the critical path
(front+top coverage stays **83–100%** across 200–350 mm wide by 300–550 mm tall, measured
at x = 0.50 on a 15-point raster), so the dimensions can be swapped when the real figures
arrive without invalidating the layout.

> ⚠️ **The 8.0 kg is a stated stand-in, not a measurement.** Left to MuJoCo's default
> density the solid box came out at **21.3 kg** — an artifact of filling it with water,
> not a purifier. Nothing in V5-0/V5-A depends on it (the reachability study is
> kinematics-only), but the indexer's sizing does, so it must not be an accident.
> **Device mass is an open ask.**

> ⚠️ **The size envelope was only swept at x = 0.50, not at the specified x = 0.58.**

---

## 4. Rotary indexer — the one piece of extra hardware this cell needs

**Specification:** a low-profile rotary stage, ⌀350 mm platter, continuous or 90°-indexed
rotation about vertical, top surface 10 mm above the bench. Repeatability ±0.5° is ample.
A stepper-driven indexing table or a small servo positioner is the standard part class.

**Payload: not yet known.** No source document gives a device mass; the simulation
carries the 8.0 kg placeholder above (9.0 kg including the platter). Get the real device
mass before sizing this.

**Cost: not yet quoted.** This is a commodity class (welding positioners, vision cells),
but no figure here has been sourced from a supplier. Price it before committing to it.

**Why it is not optional.** With the device fixed, V5-0 measured:

- the **back face unreachable at every placement tested** (0/48 raster points, 8 placements)
- camera view separation trading directly against front-face coverage — you can have 5
  views 158° apart with 92% front coverage, or 3 views 90° apart with 100%

Both are the same limitation: a fixed part can only be approached from the side the arm
lives on. **With the indexer, every vertical face rotates into the front working position
and is measured at 100% coverage** (83% even at exact-normal press), and camera
separation becomes arbitrary.

| face presented | index angle | coverage | at exact-normal |
|---|---|---|---|
| front | 0° | **100%** | 83% |
| right | 90° | **100%** | 83% |
| back | 180° | **100%** | 83% |
| left | 270° | **100%** | 83% |
| top | (none) | **100%** | 63% |

**This is the cheapest fix available.** The alternative to a ~$1–2K indexing table is a
second arm, a linear rail, or accepting that one face of every device never gets cleaned.

It is modelled as a **commanded axis** (`tt`, a position actuator), not as scenery,
because on the real cell it will be one — it needs a controller, wiring and a place in
the motion sequence, and a demo that hides an axis understates its own integration cost.

---

## 5. Tooling

**Wiping pad tool.** 40 mm ⌀ × 90 mm cylindrical stem (grasped), 60 × 60 × 20 mm
compliant pad face. Total 0.220 kg.

The stem diameter is deliberately close to the 43 mm cartridge body that the entire grasp
sequence in v2/v3/v4 was validated against, so the existing grasp constants transfer
instead of needing a new grasp.

**The pad is deliberately compliant** (`solref="0.045 1"`, `solimp="0.55 0.88 0.012"`).
This is the low-cost industrial answer to surface following: a sprung or foam-backed pad
keeps contact by geometry, so the controller does not have to close a force loop. The
reachability study allows a **30° tilt cone** off the surface normal on that basis.

> ⚠️ **The compliance values are plausible, not validated.** Nothing has yet pressed this
> pad against a surface under contact — that is V5-C. Treat the tilt-cone allowance as an
> assumption under test, and note the gap it is covering: the top face is 100% reachable
> within the cone but only **63% at exact-normal press**.

**Standoff during a cleaning pass:** TCP held **45 mm** off the target surface (the pad
occupies the gap).

---

## 6. Tolerances and calibration

**Required fixture placement accuracy: ±2.5 mm — carried over from v4, NOT measured on
this cell.**

> ⚠️ ±2.5 mm is the largest cell-position error tested in v4 (the cartridge cell) with no
> measured loss, over 60 held-out trials per level at four levels. **The v5 stations —
> indexer, device, tool post — have never been swept.** Treat it as the best available
> starting figure and re-derive it once V5-C exists.

It comes from v4's domain-randomization sweep, which shifted the whole cell vertically
while the robot's commanded heights stayed fixed — i.e. a calibration error:

| cell position error | routing compliance | end-to-end |
|---|---|---|
| 0 | 100% | 86.7% |
| **±2.5 mm** | **100%** | **86.7%** |
| ±5 mm | 90.0% | 78.3% |
| ±10 mm | 55.0% | 48.3% |

**So: locate fixtures to better than ±2.5 mm, and re-calibrate if anything moves by more
than that.** That is a checkable acceptance criterion for the cell build.

**Read the row labels carefully — this sweep is compound.** Position, mass and friction
scale together, so part variation cannot be separated from calibration error. The rows
are, in full: DR off; **±2.5 mm / ±10% mass / ±15% friction**; ±5 mm / ±20% / ±30%;
±10 mm / ±40% / ±60%. So the "no measurable loss" row is the one with ±10% mass, not
±20%, and the level that carried ±20% mass and ±30% friction *also* lost 10 points of
routing compliance. **We have not run a position-only sweep, so we cannot claim mass and
friction are individually harmless.**

What *is* separable: inspection accuracy was flat within noise at every level
(86.7–91.7%), i.e. mass and friction do not affect the camera.

One counter-intuitive result worth honouring: referencing picks to a *measured* surface
height instead of commanding an absolute descent was implemented, measured, and **made
things worse** (routing 90.0% → 85.0% at ±5 mm). Commanding an absolute descent and
letting the tool contact the surface is more forgiving. Do not "improve" this.

---

## 7. What the simulation does NOT tell you

Read this section before quoting any number from §1–6 to a customer.

- **Hand-eye calibration** — assumed exact here; must be measured on the real cell (§2).
- **Real device dimensions** — placeholder (§3). Open ask.
- **Contact behaviour of the pad** — modelled, not validated (§5). V5-C.
- **Cycle time** — the sim's per-route times (41–54 s in v4) are simulated seconds under
  our own speed limits, not a takt time. DrinkPrime has given us no takt figure either.
- **Fluid and chemistry** — not simulated at all. Cleaning removes the same geometry the
  camera graded; it does not model CIF cream, detergent or descaling chemistry.
- **The Easy/Medium/Hard criteria** — the class names are DrinkPrime's; the boundaries
  are ours, because no document in the set defines them. See `dp_process.MISSING`.
- **Gripper force control** — the model uses a position-controlled gripper. Real force
  limits are untested.
- **Deformables** — Teflon tape, stickers, harnesses and tubing are a deliberate
  de-scope, not an oversight. See PITCH_NOTES §9.
- **All §4 coverage numbers are kinematic feasibility, not cleaning performance.** They
  say the arm can put the tool there, not that a wipe would clean it.
- **The ±2.5 mm tolerance is inherited from the v4 cartridge cell**, not measured on the
  v5 stations (§6).
- **Device mass** — 8.0 kg is a placeholder; no source document gives one (§3).
- **The 120 mm riser is not modelled**, so no arm-to-riser clearance has been checked and
  a real riser will cost some exact-normal side-face poses (§2).
- **The rotary indexer has not been priced** (§4).

---

## 8. Build checklist

1. Bench with a **1100 × 1200 mm** clear working area. (Bench *flatness* has not been
   studied — the ±2.5 mm figure in §6 is about where fixtures are *located*, not surface
   finish.)
2. Mount the xArm7 so its base flange sits **120 mm above the bench top** at the origin
   of §3 — or drop every Z by 120 mm. **The riser footprint is undefined**: add a riser
   geom of the real diameter to the scene and re-run `v5_reach.py --indexed` before
   trusting the §4 numbers (§2).
3. Install the **rotary indexer** at (580, 0) mm, top face 10 mm above the bench.
4. Fit the **tool post** at (300, −340) mm, top face 20 mm above the bench.
5. Fit the **matte backdrop** at X = 854 mm, spanning ±460 mm in Y and 0–720 mm in Z.
   **Nothing else may be placed on the +Y side of the device** — a 6 mm panel there cost
   an entire face of coverage in simulation before it was found and removed.
6. Set the robot **TCP offset to 172 mm** along the gripper base +Z, then **measure the
   actual finger-pad offset** and record it.
7. Perform **hand-eye calibration** for the wrist camera and record the transform.
8. Verify every fixture is within **±2.5 mm** of the coordinates in §3.
9. Re-fit the inspection thresholds **in-cell**, through the real motion path — never on
   a bench rig. v4 lost 37 points of accuracy to exactly that mistake.
