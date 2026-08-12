# Recurring traps

Read this when something behaves impossibly, or before adding a body, a metric, a stepping
loop, or a render path. Each entry cost real time at least once; several cost it repeatedly.
`PAIN_JOURNAL.md` has the full incident log.

## Scene and model

**Adding a free body silently breaks every reset.** The `v5home` keyframe carries an
explicit `qpos` for every joint. MuJoCo zero-fills anything the string does not cover, so a
new free joint spawns at the **world origin** — inside the arm riser and the bench. This has
now happened **four times** (cartridge, bowl+element, cap joints, `cap_blank`). The fourth
was live for two commits, perturbed every cleaning run, and moved peak force by 1 N.

Fix it in the **generator's keyframe string** (`make_scene_v5.py`), not in the consumer. A
per-consumer `qpos0` patch fixes one caller and leaves the landmine armed for the next —
which is exactly how the fourth occurrence survived, because `v5_membrane` had patched
around it and `v5_clean` had not. `v5_check_scene.py` catches this in one run.

**MuJoCo clamps `ctrl` to `ctrlrange` silently.** `deg2rad(270)` against a ±π range became
180°, so a whole face was never presented — on every seed, with no error anywhere. The only
symptom was a coverage percentage.

**Never materialise or teleport geometry into space the gripper currently occupies.** A cap
swap inside closed jaws threw a free body metres across the cell at some random phases, so
the single-seed test passed and 4 of 10 fresh seeds failed.

**Regenerate, never hand-edit the scene XML.** `make_scene_v5.py` is the source; the XML is
committed output. It round-trips byte-identically, so a diff after regeneration is a real
change. Re-run all three gates after any scene edit — a 6 mm backdrop panel that looked like
scenery cost an entire face (89.6% → 0%).

## Motion and control

**The commanded quantity is not the measured quantity.** Clamping the setpoint rate to the
arm's published 3.14 rad/s left the *measured* joint speed at 5.71 rad/s. A position servo
chases the setpoint's **error**, not its velocity, so a far-away planner handoff makes it
sprint. `ArmProfile.max_follow_err` is what actually bounds it. Assert on the measured value.

**Do not tighten the following-error clamp to chase the tool-speed figure.** The force cliff
is at 0.14 rad (89.5 N — twice the model-validity ceiling) and 0.15 sits 7% from it. Tool
speed is a Cartesian quantity and needs the Cartesian governor in `_advance` instead.

**A 7-DoF arm has many configurations for one pose, and taking the first IK solution is a
bug.** Adjacent raster points 27 mm apart landed in different branches — 5.78 rad of joint
motion for a 37 mm step. That single defect was simultaneously the coverage gap *and* the
force spikes, chased for hours as two problems. The tell: one of five passes had zero jumps
and was the only one that worked. **When one instance of a repeated thing works and the rest
do not, diff the instances.**

**A planner must model what the robot is carrying.** A tool held by a weld equality does not
follow the arm in a planning copy — reconstruct the weld transform, or the planner is blind
to the only part that touches anything.

**Driving INTO a surface and sliding ALONG one are different motions with different force
budgets.** One "speed" knob for both is what made an early feed sweep answer the wrong
question. Seating gently (`stroke_seat_scale`) cost 0.6 s and took peak force 34.7 → 32.2 N.

**Never shorten the 1.2 s indexer dwell.** Angle-arrived is not settled. A 4 s "saving" broke
coverage in both modes and cost most of a session to find. If it is ever revisited it needs
an angular-**velocity** criterion, not an angle threshold. (It *is* legitimate to skip the
dwell entirely when no rotation was commanded — a guard whose precondition is absent is
cost, not caution.)

**`target = current + error` is an integrator that winds up against contact.** When the part
is jammed and cannot move, the wrist walks sideways indefinitely. This has been
re-implemented in new clothes more than once.

## Metrics

**Frame errors dominate.** The toolpath is the **pad's**, not the wrist's — each knot picks
its own tilt from a discrete set and the pad hangs 105 mm off the flange, so a one-step tilt
change swings the TCP by centimetres while the pad slides smoothly. Parametrising by TCP arc
length invented 195 "corners" out of 304 knots and 20 mm of phantom error.

**Identical numbers are not always a bug — but always check.** Held-out force/tilt/raster
figures matching a development run to every decimal was correct: the cleaning trajectory is
open-loop and seed-independent. The real finding was that those figures are **n = 1**.

**A metric that scores a prediction against itself measures nothing.** Route "end-to-end"
once checked only that the cell executed the plan its own prediction chose, so a misgraded
unit completing the *wrong* route scored a success. Any claim of the form "X **and** Y"
needs one expression containing both terms.

## Rendering

**The render path must call the evaluated methods.** It has drifted twice — once filming a
bowl with no element while the HUD printed STALLED unconditionally. Render paths may only
**add frame callbacks**; a duplicated physics loop rots silently.

**A stepping loop that accepts `frames` must emit them.** Three primitives took the argument
and ignored it, so ~37 s of a 183 s cycle filmed nothing. `make_realtime` then stretches the
footage uniformly to match the true clock, which turns a gap that happened while the arm
stood still into duplicated frames *during the moving parts* — 25% of output frames were
duplicates. That is what "the video looks laggy" actually was.

**Two visual complaints in three days were measurement defects.** "It flails" was the arm
running 3× its rated speed. "It cuts out" was a station's worth of unbilled time. **If it
looks wrong in the video, check the number before you fix the picture.**

## Grasping and fixtures

- The gripper finger pads sit **~25–39 mm above `link_tcp`** depending on the grasp; the TCP
  is not the contact point. Measure it, do not inherit it.
- Commanded wrist yaw maps to **negative** physical yaw.
- A fixture must clear the part's **largest** feature — a nest sized to a 21.5 mm body
  fouled 34 mm lugs by exactly 7 mm.
- **Grip features are designed, not found.** When three grasp strategies fail on a part,
  change the part — a pick stem costs nothing in sim and little in reality.
- Untwisting through a cap grip loses **16–18%** of commanded rotation to torsional slip.
  Never dead-reckon a twist from wrist angle.
- Do wet or dynamic work only after re-gripping by the **body**.

## Environment

- Requires Python 3.10+; macOS system `python3` is 3.9 and has no MuJoCo wheel. Use
  `./setup.sh`, never a bare `python3 -m venv`.
- `venv/` is gitignored and the venv breaks if the folder is renamed.
- `--render` and `--cards` need TrueType fonts.
