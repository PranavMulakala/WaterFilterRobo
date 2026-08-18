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

**The riser is now modelled** (`arm_riser`, a ⌀150 mm column from the bench top to 4 mm
below the flange) and its cost has been **measured, not assumed**:

| riser ⌀ | front | right | back | left | top |
|---|---|---|---|---|---|
| none | 100% | 100% | 100% | 100% | 100% |
| 120 mm | 100% | 100% | 100% | 100% | 100% |
| **150 mm** | **100%** | **100%** | **100%** | **100%** | **100%** |
| 200 mm | 100% | 100% | 100% | 100% | 100% |
| 250 mm | 100% | 100% | 100% | 100% | 100% |

**A riser of any plausible diameter costs nothing.** Reproduce with
`v5_reach.py --riser`. So the pedestal footprint is *not* a design constraint, and you
can size it for stiffness rather than for clearance.

> ⚠️ **This reverses an earlier warning in this document**, which said a 150 mm riser
> would cut exact-normal side-face coverage from 83% to 27%. That measurement was taken
> against the FIXED-device design, where the arm had to reach around to press on a +Y
> surface — folding back toward its own base, exactly where a riser sits. **The rotary
> indexer removed that motion**: every face is now worked at the front position, with the
> arm extended away from its base. The riser is nowhere near it. Third thing the indexer
> paid for, after the unreachable back face and the camera-separation trade-off.
>
> The 150 mm default is still a **placeholder** — size it to the pedestal actually bought.

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

> ⚠️ **Hand-eye calibration is required if you use the wrist camera, and is not modelled
> here.** The simulation knows the camera-to-TCP transform exactly; a real one does not.
> v4 showed what that costs: a classifier scored 90% on a rig and **53% in the cell**
> because the presentation transform was assumed instead of measured.
>
> **The V5-B triage station does NOT use the wrist camera** — see below. That removes
> hand-eye calibration from the inspection path entirely, which was the single largest
> un-modelled risk in the original plan.

### Top-face verification camera (V5-D) — a SECOND camera, and it is required

| | |
|---|---|
| name | `verify_top` |
| position | **(0.300, −0.300, 1.050) m** |
| aim point | the device's top face centre, (0.580, 0, 0.460) m |
| field of view | **fovy 40°** |

**Why the cell needs two cameras, measured rather than assumed.** The `inspect` camera
below sits at **z = 0.400** and the device's top face at **z = 0.450** — *below* the plane
of that face, cos(top normal, view) = **+0.076** — so it can never see the top, and the
per-face search regions cover the four **vertical** faces only. The cleaning station wipes
**five** faces and its coverage number counts five.

Verified through the `inspect` camera alone, the V5-D falsification test caught **10/10**
sabotaged units and simultaneously passed **9 of 10** honestly-cleaned-but-still-dirty
ones — because the face the cleaner misses and the face the camera cannot see are the
**same face**. With `verify_top` the false-verify rate is **0/10**.

Mount it on the −Y side above the top plane, clear of the arm's working volume over the
device. It needs a one-off extrinsic survey, not hand-eye calibration — the arm parks
during verification, exactly as it does for triage.

### Inspection station camera (V5-B)

A **fixed** camera, not the wrist camera. With the device on a rotary indexer, a fixed
camera plus a rotating part is simpler, is what real rotary vision cells do, needs only a
one-off extrinsic survey instead of hand-eye calibration, and leaves the arm free during
inspection.

| | |
|---|---|
| position | **(0.100, −0.450, 0.400) m** |
| aim point | the device centre, (0.580, 0, 0.235) m |
| field of view | **fovy 48°** |
| resolution used | 1280 × 720 |

It sits on the −X side so the backdrop fills the frame behind the device, and is offset
in −Y to clear the arm.

### Arm park pose

The arm must be **clear of the inspection camera's frame** while a unit is graded.
Measured: at joint angles **(90°, −14.1°, 0°, 52.1°, 0°, 66.3°, 0°)** the arm occupies
**0.000%** of the inspect view, against **4.28%** at the home pose. Verified
collision-free, including against the +Y backdrop.

### Safe reset

Use the scene keyframe **`v5home`**, not the `home` inherited from the arm model. `home`
declares only the 13 arm+gripper values and MuJoCo zero-fills the rest, which puts the
pad tool at the world origin, 20 mm inside the bench. On the real cell the equivalent is:
**a "home" macro that does not command every axis will leave the ones it omits wherever
they were.**

---

## 3. Station positions

All coordinates in metres, sim world frame. Convert with §2 before use.

| station | X | Y | Z | notes |
|---|---|---|---|---|
| arm mounting flange | 0.000 | 0.000 | 0.120 | 120 mm above bench; **riser IS modelled** — `arm_riser`, ⌀150 mm, measured cost zero (§2) |
| **rotary indexer** (disc centre, top face) | 0.580 | 0.000 | 0.010 | ⌀350 mm, 10 mm proud of bench |
| **device** (footprint centre, base) | 0.580 | 0.000 | 0.010 | stands on the indexer |
| tool post (top face) | 0.300 | −0.340 | 0.020 | ⌀110 mm flat plate |
| pad tool (stem axis, at rest) | 0.300 | −0.340 | 0.040 | body origin |
| **solution tray** (basin centre, floor) | 0.140 | −0.360 | 0.008 | 130 mm square inner, 8 mm walls, 40 mm deep; liquid surface at Z = 0.028 |
| inspection backdrop, +X (panel face) | 0.854 | 0.000 | 0…0.720 | matte black, 920 × 720 mm |
| inspection backdrop, +Y (panel face) | 0.660 | **0.414** | 0…0.720 | matte black, 600 × 720 mm |
| **inspection camera** | 0.100 | −0.450 | 0.400 | fixed, fovy 48°, aims at (0.58, 0, 0.235) |
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

> **It must accept a command anywhere in a FULL revolution, and this is not a detail.**
> The model's actuator was specified ±180°, an unexamined default. The joint itself is
> unlimited so nothing failed loudly — but a 270° command was silently clamped to 180°,
> and the cleaning cycle then re-wiped the back panel while one side face was never
> presented at all, on every unit. A commodity indexer turns continuously; specify one
> that does, and make the command range explicit on the datasheet rather than assuming
> it. The cell drives 0° → 90° → 180° → 270° → 360°, all in one direction.

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
and is measured at 100% coverage** (within a 30° tilt cone — see the table's warning
below before quoting any exact-normal figure), and camera
separation becomes arbitrary.

| face presented | index angle | coverage | at exact-normal |
|---|---|---|---|
| front | 0° | **100%** | **47.9%** |
| right | 90° | **100%** | **14.6%** |
| back | 180° | **100%** | **47.9%** |
| left | 270° | **100%** | **14.6%** |
| top | (none) | **100%** | **29.2%** |

> ⚠️ **The exact-normal column was wrong twice and is now measured against the tool that
> exists.** It read 83% / 83% / 63% for two reasons, both corrected 2026-08-04:
> (1) it assumed indexing makes the four vertical faces equivalent — it does not, the
> cabinet is 250 mm wide and 180 mm deep, so a side face rotated to the front sits 35 mm
> closer to the arm; and (2) the whole column was measured with `PAD_STANDOFF = 0.045`, a
> guess predating the wiping tool. The built tool is **105 mm** wrist-to-pad.
>
> **The relaxed column is unchanged at 100% and the gate still passes on it.** That is the
> load-bearing fact: this cell only works because a compliant pad conforms over ~30°. A
> station that presses at exact normal would be operating in the right-hand column. Do not
> design one that does.

**This is the cheapest fix available.** The alternative to a ~$1–2K indexing table is a
second arm, a linear rail, or accepting that one face of every device never gets cleaned.

It is modelled as a **commanded axis** (`tt`, a position actuator), not as scenery,
because on the real cell it will be one — it needs a controller, wiring and a place in
the motion sequence, and a demo that hides an axis understates its own integration cost.

---

## 5. Tooling

**Wiping pad tool.** **Keyed rectangular shank, 60 × 40 × 90 mm** (grasped across the
40 mm dimension), 60 × 60 × 20 mm compliant pad face. Total 0.220 kg.

> ⚠️ **The shank must be keyed, not round.** With a 40 mm cylindrical shank the tool
> pivoted inside the jaws as soon as the wrist rotated from vertical to horizontal — the
> pad's offset from the TCP moved from (21.7, 0, 36.4) mm to (87.6, 0, −16.1) mm, roughly
> a right angle of rotation, and cleaning coverage was 0%. A flatted, keyed or
> D-profile shank is standard on robot tooling for exactly this reason.
>
> **This is not yet sufficient.** Even keyed, the tool still creeps ≈60–70 mm in the jaws
> over one face's raster — and that creep is insensitive to grip command (245 vs 255) and
> to press depth (3.0 vs 1.5 mm), which points at grip geometry or free play rather than
> friction. **A production cell should use a proper tool changer or a positively located
> tool holder, not a parallel-jaw grip on a shank.** See V5_PLAN, V5-C status.
>
> ### ⚠️ THIS SECTION IS OUT OF DATE AND WILL BUILD THE WRONG CELL
> Both components below are now **modelled and required**, not future work. Building from
> the text above gets you the parallel-jaw shank grip that was measured NOT to work (creep
> 60–70 mm across one face's raster, insensitive to both grip force and press depth).
>
> | component | what it does | modelled as | numbers |
> |---|---|---|---|
> | **tool changer** | LOCATION | `toollock` weld, `xarm_gripper_base_link`↔`padtool` | capture envelope 4 mm / 4°; measured coupling drift **0.03 mm** across a full job |
> | **active contact flange** | FORCE | `acf` slide joint, axis (0,0,1) | stiffness **800 N/m**, damping 12, stroke **−2 … +30 mm** |
>
> You need **both**. The changer alone gives a rigid coupling, and then the arm's ~1.5 mm
> path error lands straight on contact force. The flange alone cannot locate the tool.
> Read them out of `sim_poc/ufactory_xarm7/refurb_scene_v5.xml` before sourcing parts —
> these are catalogue items in any polishing or sanding cell, and **neither has been
> priced or sourced.** The pad's compliance is also no longer "not yet pressed": V5-C
> measured median **13.1 N** with a 271 N peak over 3744 raster points.

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

**The pad should be sourced as a POWERED BUFF (plant video, 2026-08-18).** The plant's
own cabinet polishing is a hand drill driving a foam buffing pad with Cif — the sim's
compliant pad-on-ACF is that tool class held still. A production cell should buy the
same thing the plant already trusts: a low-speed rotary buffing head on the compliance
flange. **The sim does not yet model the spin** (its removal is contact-binary, so a
spinning pad would change no measured number today) — modelling the reaction torque
through the tool changer is the named follow-up before sourcing.

**Membrane spindle (cap driver) — a purchased component with a two-number spec.**

| number | value | status |
|---|---|---|
| torque limit (stall criterion) | **6.00 N·m** | OURS — Stage 10 says only *"tightened properly with the spanner"*; no figure exists in the corpus. This is the number the whole leak result keys off and it must come from DrinkPrime or the cap CAD before a real cell is built |
| free (rundown) speed | **≥ 30 rad/s (~286 rpm)** headroom; operated at **20 rad/s (~191 rpm)** | any torque-controlled DC driver — 100–600 rpm rundown is the ordinary catalogue range |

> The model drives the cap with a velocity actuator whose `forcerange` IS the torque
> limit, so it stalls the way a real torque-limited driver stalls. **The speed and the
> torque are independent numbers on the same spec sheet**: raising the rundown speed
> from the original 6 rad/s to 20 changed the certified outcome by nothing — battery on
> fresh seeds 2242–2251: insert 10/10, cap placed 10/10, stall 10/10, leak 10/10,
> sabotage caught 10/10, 0 false pass; turns median 9.64 (baseline 9.53), peak seal
> 350 N (baseline ~345). The stall detector keys on AXIAL PROGRESS collapsing, which is
> rate-independent by construction and measured so.
>
> **Pressure-decay sensor (the O-ring fix): the plant already owns the instrument
> class.** Their final QC tests the assembled device with pneumatic air through a dial
> gauge on the line (plant video, 1:19–1:28). Specifying a transducer + hold-time
> criterion at the membrane station is an extension of equipment they already use, not
> new exotic hardware. Test pressure still unresolved (45 vs 80 PSI).
>
> ⚠️ **History worth keeping**: the spindle spent three versions capped at 6 rad/s by a
> `ctrlrange` nobody was looking at, while the commanded rate said 12 — MuJoCo clamps
> silently, and the sweep that concluded "drive rate is a dead lever" was sweeping the
> clamp, not the driver. The same silent clamp once cost a whole face of coverage
> (indexer, 270°). If a commanded value seems to do nothing, check the ctrlrange first.

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
- ~~**The 120 mm riser is not modelled**~~ — **superseded.** It is modelled (`arm_riser`,
  ⌀150 mm) and swept: it costs **nothing** at any diameter to 250 mm. §2 has the table.
  This bullet contradicted §2 for a whole phase; if you find another like it, §2 wins.
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
4a. Fit the **solution tray** at (140, −360) mm — 130 mm square inside, 40 mm deep, fill
   to 20 mm. Detergent-and-warm-water per Stage 3 (0024DPCRO003).
   > **Sizing is not arbitrary and the obvious number is wrong.** The pad is a 60 mm
   > square, so the feature that must clear the walls is its **84.9 mm diagonal**, not
   > its width. A 130 mm basin leaves 22.6 mm to a wall on the worst diagonal. Sizing to
   > 60 mm would repeat the v4 staging-nest failure (nest sized to a 21.5 mm body, fouled
   > 34 mm lugs by exactly 7 mm).
   > **Placement was chosen by the reach gate, not by eye.** The first location, (300,
   > −170) mm, looked obviously fine and cost coverage on **all four vertical faces**
   > (100% → 93.8% worst). Three of four candidates passed; this one is the closest to
   > the tool post that does. **Re-run `v5_reach.py --indexed` if you move it.**
   > **Stage 3's full sequence needs two more of these stations and is NOT built:** it
   > calls for a wash cloth, then a *clean damp* cloth, then a *dry* cloth. That is three
   > pads on three posts. Only the wash pad exists.
5. Fit **both matte-black backdrops**: the +X panel at X = 854 mm spanning ±460 mm in Y,
   and the +Y panel at Y = 414 mm spanning X = 360…960 mm. Both 0–720 mm in Z.
   > ⚠️ **This instruction is the reverse of an earlier version of this document.** The
   > +Y panel was originally banned, because with a FIXED device the arm had to reach
   > around to press on a +Y surface and a 6 mm panel there cost an entire face of
   > coverage (89.6% → 0%). The rotary indexer removed that requirement — every face now
   > rotates to the front working position — so the panel is safe and the triage camera
   > needs it. Re-verified with `v5_reach.py --indexed` after adding it: all faces still
   > 100%. **If the indexer is ever dropped from the design, this panel must go too.**
6. **Finish the indexer platter matte black** (or fit a matte black cover plate). This is
   a vision requirement, not cosmetic: in mid-grey the platter rendered above the
   background threshold, so its rim sat inside the search region and read as a large
   compact dark defect — i.e. as a dent. Measured 2374 false dent pixels against ~60 real
   ones before the finish was changed.
7. Set the robot **TCP offset to 172 mm** along the gripper base +Z, then **measure the
   actual finger-pad offset** and record it.
8. Survey the **inspection camera** extrinsics (§2). Hand-eye calibration is only needed
   if you also use the wrist camera; the triage station does not.
9. Verify every fixture is within **±2.5 mm** of the coordinates in §3.
10. Re-fit the inspection thresholds **in-cell**, through the real motion path — never on
    a bench rig. v4 lost 37 points of accuracy to exactly that mistake.
