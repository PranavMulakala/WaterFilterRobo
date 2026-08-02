# Pain Journal — every gotcha is product research
Format: date | what happened | time lost | what would have prevented it

- 2026-08-01 | v1: MuJoCo include paths break when scene XML lives outside the
  model folder (mesh paths resolve relative to main file). Moved scene into
  ufactory_xarm7/. | ~15 min | better error messages / scene scaffolding tool
- 2026-08-01 | v1: naive IK servo (chasing measured qpos) oscillated wildly;
  needed kinematic planning on commanded config + gravity compensation.
  | ~30 min | a "robot arm control starter" library with sane defaults
- 2026-08-01 | v1: keyframe reset silently teleported the free-joint cartridge
  to origin (keyframe predates the joint; zeros filled in). | ~20 min |
  keyframe/qpos dimension mismatch warning
- 2026-08-02 | v2: gripper pads sit ~25mm above link_tcp → robot pinched the
  part by its cap and flipped it. Discovered only via contact-pair tracing.
  | ~45 min | gripper contact visualization / grasp-quality checker
- 2026-08-02 | v2: grasp at center of mass = see-saw pivot; grasp high = pendulum
  swing. Physical insight, not code. | ~30 min | grasp planning heuristics doc
- 2026-08-02 | v2: first bayonet geometry was geometrically impossible (lugs
  trapped in slot channels at seat depth). Redesigned collar/pedestal. | ~40 min |
  CAD-level mechanism sanity check before sim
- 2026-08-02 | v2: fast 130mm descent wedged the part diagonally (peg-in-hole
  jam); fixed with staged slow descent + compliant follow (RCC-style) + 45°
  chamfer lead-in (standard DFM). | ~60 min | insertion-strategy playbook
- 2026-08-02 | v2: commanded wrist yaw = NEGATIVE physical yaw; closed-loop servo
  diverged until sign probe. | ~20 min | auto-calibrating servo sign
- 2026-08-02 | eval harness caught every one of these. Lesson: build --eval
  before believing anything. | 0 | this IS the product insight

## v3 session — fresh-machine setup + seed-12 diagnosis (2026-08-01)

- 2026-08-01 | ENV: `python3` on macOS is Apple's 3.9.6. MuJoCo ships no cp39
  wheel, so `pip install mujoco` fell back to a source build and died on
  `RuntimeError: MUJOCO_PATH environment variable is not set` — an error that
  says nothing about the real cause (unsupported Python). Fix: build the venv
  with `/opt/homebrew/bin/python3.12`. README's bare `python3 -m venv venv` is
  a trap on any stock Mac. | ~10 min | a pinned `requirements.txt` +
  `python_requires`, or a setup script that checks the interpreter version first
- 2026-08-01 | `--render` is DEAD on macOS: `make_frame_cb` hardcodes Linux font
  paths (`/usr/share/fonts/truetype/dejavu/...`) which don't exist on a Mac, so
  every render call raises FileNotFoundError before a single frame. Diagnosis
  had to go through the `frame_cb` hook instead (which needs no fonts — that
  hook turned out to be a perfectly good tracing seam). | ~10 min | font
  resolution via `PIL.ImageFont.load_default()` fallback, or bundling the .ttf
- 2026-08-01 | `--eval N` silently OVERWRITES stats.json. Running the documented
  `--eval 10` destroyed the 25-trial baseline — and `--cards` reads stats.json to
  render the "SEATED + LOCKED: 84%" end card, so the demo video would have
  silently started claiming a 10-trial number. Recovered the original from the
  zip. | ~5 min | eval should write stats_<N>.json, or refuse to clobber a
  larger run without --force. Demo artifacts should never read a mutable file
- 2026-08-01 | REPRODUCIBILITY: the 84% baseline is version-locked. On MuJoCo
  3.11.0 / numpy 2.5.1 the same seeds give 88% — **seed 12 flips from FAIL to
  LOCKED** with zero code change. Contact-rich sims are not portable across
  physics-engine versions; a success rate quoted without a pinned engine version
  is not a reproducible claim. Nothing in the repo pins anything. | ~15 min |
  lockfile + engine version stamped INTO stats.json and onto the demo end card
- 2026-08-01 | THE BIG ONE: peak cartridge tilt during INSERT, measured across
  all 25 seeds — **every single trial wedges on the chamfer.** Median peak tilt
  on the *passing* seeds is 20.3 deg (max 36.5); the failing seeds start at 42.7.
  It is one continuous distribution with no clean separation, not "4 bad seeds".
  The 84% is really "100% jam rate, 84% shake-it-off rate". A binary pass/fail
  eval hid a continuous margin, so the backlog framed this as 4 outliers to
  patch rather than one systemic defect. | 0 (this WAS the finding) | evals must
  report a continuous margin-to-failure, not just a success rate. Biggest
  product insight of the session: **binary success metrics hide physics.**
- 2026-08-01 | The retry logic is UNREACHABLE for the dominant failure mode.
  Retry fires only on an INSERT *timeout*, but INSERT's completion gate watches
  the TCP height (`site_xpos[tcp].z < 0.129`), not the part — and a wedged part
  still lets the wrist descend. So a jam exits INSERT reporting *success*, and is
  only noticed 1-2 phases later at DROP-SEAT, which has no retry branch. Seed 21
  aborted with 2 of 2 retries unused. Every other critical phase in this
  controller judges the PART; INSERT is the one that regressed to the TCP.
  | ~40 min | assertion that a phase's success gate references the same body its
  failure mode acts on; "did the thing I care about actually move?" checks
- 2026-08-02 | THE ACTUAL ROOT CAUSE, and it was not where the diagnosis said. The
  wedge came from the lateral law `tgt = tcp + (SOCK - cart_xy)`, recomputed every
  step: when the part is jammed and cannot move, the error never shrinks, so the
  wrist walks sideways without bound. **An integrator winding up against a contact
  constraint.** The first proposed fix — switch to the existing compliant branch
  earlier — was tested and made it WORSE (median tilt 20.5→24.4, max 36.5→50.7),
  because it removed the only recentering authority instead of bounding it. Lesson:
  correctly localising a defect is not the same as knowing the remedy, and a
  plausible one-line fix deserves the same eval as any other. | ~30 min | anti-windup
  is a solved problem in motion control and nobody applied it here; a "contact-aware
  setpoint" primitive would have prevented the whole class
- 2026-08-02 | SECOND windup, found only by fanning out 8 independent strategies:
  INSERT commanded a 64 mm ABSOLUTE z step, which saturates the per-joint rate clip.
  Two consequences, both invisible in the code: (a) the entire joint-rate budget goes
  to the descent, leaving none for lateral or rotational correction, and (b) clipping
  element-wise DISTORTS the direction in joint space, so the tool doesn't travel
  straight down — measured ~19 mm of lateral drift in the first second. Four separate
  agents converged on this independently. Fix: bounded feed lead + direction-
  preserving rate scaling. | ~0 (parallel search found it) | element-wise clipping of
  a Jacobian solution is a silent correctness bug, not a safety limit — this belongs
  in an "IK gotchas" doc
- 2026-08-02 | The retry logic was UNREACHABLE for the dominant failure, confirmed by
  re-breaking the controller on purpose: with the original wedging dynamics restored
  but the new detection+recovery in place, the score went 88%→92% and the retry
  counter went 2→3 as the DROP-SEAT retry fired for the first time ever. Deliberately
  re-introducing a bug to prove a fix does something is worth the 10 minutes — the
  first two "validations" of the recovery path showed 100% with ZERO retries, i.e.
  the path was never exercised and I nearly shipped it untested. | ~20 min | test
  coverage for recovery paths; a "was this branch ever taken?" counter in the eval
- 2026-08-02 | Fix 4 (require the dwell condition to hold continuously) was CORRECT in
  principle and catastrophic in practice: applied to all phases it dropped success to
  **4%**. ORIENT LUGS and PRE-INSERT gate on a part still swinging as a pendulum, and
  for them cumulative dwell is the right semantic — it accumulates evidence that the
  swing is decaying. Only INSERT was certifying a state it never reached. Scoped it to
  INSERT. | ~15 min | phase gates need to declare whether they're proving "settled" or
  "converging"; those need different timer semantics and the code had one timer
- 2026-08-02 | The 88% baseline was itself flattered by its own test set. On 50 seeds
  it had never been run against, the ORIGINAL code scores **72%**, with worst-case
  tilt 60.7 deg. Tuning and reporting on seeds 0-24 hid a third of the real failure
  rate. | 0 | held-out seeds should be the default in the eval harness, not something
  you remember to do
## v4 Phase B — the three-route video (2026-08-02)

- 2026-08-02 | Compressing a demo is an honesty decision, not an editing one. Three
  real routes are 135 s of cycle time and the target cut was 90 s, so the trial
  footage runs at **1.8x with a permanent on-screen tag**, and a full-length
  uncompressed cut ships alongside it. Cards are NOT sped up, so the stats are never
  skimmed past. Without the tag the video silently claims a cycle time the cell does
  not achieve. | 0 | speed-ramping a robot demo is so normal that nobody labels it;
  labelling it costs nothing and is the difference between a demo and a claim
- 2026-08-02 | The stage ribbon originally greyed out CLEAN on the already-clean
  route rather than hiding it, which implies the cell performed a cleaning step it
  skipped. Small, but it is exactly the kind of thing a customer notices and cannot
  un-notice. Hidden per-route now. | ~10 min | demo UI is a truth surface; a greyed
  step reads as "done" to anyone not reading carefully

## v4 Phase A — the staging nest (2026-08-02) — REINSTALL NOW WORKS

- 2026-08-02 | **I sized the staging nest to the wrong feature.** Gave it a 27 mm
  bore for a 21.5 mm cartridge body -- 5.5 mm clearance, generous -- and every drop
  test failed. The bayonet **lugs** stick out to r=34 mm. MuJoCo reported the
  penetration as exactly **-7.0 mm** = 34 - 27, and the solver resolved it by
  launching the part back out of the nest. A fixture must clear the part's LARGEST
  feature, not its nominal diameter. | ~40 min | the contact list gave the answer in
  one query and I spent half an hour on drop-envelope sweeps first -- ask the solver
  what it is touching BEFORE theorising about dynamics
- 2026-08-02 | **The socket's chamfer has a latent orientation bug that has been
  invisible for three versions.** `euler="0 0.785 th"` tilts every plate about the
  same world Y axis instead of radially, so a full ring becomes a pinwheel that
  overhangs its own bore. The socket survives it purely because its malformed plates
  land exactly where the bayonet slot GAPS are -- they do not exist. Copying the
  pattern to a nest with no gaps exposed it immediately. Rebuilt with explicit
  `xyaxes`. | ~30 min | **working geometry is not necessarily correct geometry.**
  Copying a pattern that works can transplant a bug into a context that has no luck
  protecting it
- 2026-08-02 | The cleaning verification was nearly theatre and a falsification test
  caught it. Sabotaged the cleaning so deposits were deliberately NOT removed, then
  asked whether the re-check still passed the part: **it wrongly passed 2 of 5.** The
  re-check was classifying on a single view while the main inspection used two -- and
  the FLIP2 phase existed for exactly that second view but its capture was never fed
  in. With both views: 5/5 honest cleanings verified, 5/5 sabotaged cleanings caught.
  | ~20 min | **any "verified" flag needs a test that deliberately breaks the thing
  it verifies.** A check that cannot fail is not a check
- 2026-08-02 | Re-fitting the classifier thresholds on IN-CELL presentations rather
  than the teleport rig moved accuracy 85.0 -> 86.7% and, more importantly, the
  false-clean rate **2.1% -> 0.0%** on 60 held-out trials. Same code, same classifier,
  same seeds -- only the calibration fixture changed. | ~15 min | second confirmation
  in one session that calibration fixture > model sophistication
- 2026-08-02 | The ordering insight that unblocked everything: **do the wet work
  AFTER re-gripping by the body.** Dipping a cap-gripped part drops it ~7 s in, every
  time. Nest first, re-grip, then clean. Obvious in hindsight, and it is exactly what
  a human would do -- you do not hold a jar by its lid to wash it. | 0 | a grip-
  strategy planner would have said this immediately; I found it by exhausting the
  alternatives

## v4 session — inspect / clean / replace (2026-08-02) — PARTIALLY COMPLETE

- 2026-08-02 | THE BIG ONE: **a classifier validated on a test rig scored 90%, and 37
  points lower in the actual cell.** Calibration presented the part by teleporting it
  to the inspection pose. In the real trial the ARM holds it -- and the presentation
  height came from a fixed `cap_hang = 83 mm` constant while the true hang is ~52 mm
  and unstable. The part sat 31 mm high: cropped, off the backdrop, and the
  segmentation swallowed bench and shadow (187k "part" pixels out of 307k). Coverage
  read 0.0, everything graded "clean" -- **53% accuracy and a 34.8% false-clean rate,
  the exact error we had called the dangerous one.** Fix was this project's own
  recurring lesson: put the PART on the camera axis using the measured hang, not the
  wrist at an assumed offset. Back to 90% in-cell, matching the rig. | ~50 min |
  **a vision model is only as valid as the fixture that presents the part.** Calibrate
  through the same motion path you deploy, never on a teleported ideal. Most
  transferable finding of the session
- 2026-08-02 | Small-sample luck nearly became a claim. In-cell inspection read
  **100% on seeds 0-19** immediately after that fix; on 30 held-out seeds it was
  **90.0%**. Twenty trials could not distinguish "fixed" from "lucky", and 100% is
  precisely the number most likely to be believed and repeated. | 0 | held-out
  evaluation has now caught an over-claim in three consecutive sessions
- 2026-08-02 | **BLOCKER, unresolved: the cap grip cannot retain the part through
  extended handling.** A seated cartridge can only be gripped by its cap -- the collar
  and chamfer occlude the body below z=126 mm -- and that is a small friction patch
  with a 110 mm lever hanging off it. v3 never exposed this because it only carried
  the part ~5 s to a bin. v4 asks it to survive inspection, a tank dip and a
  re-insertion, and the part is dropped every time: hang offset wanders 42-83 mm and
  it slips out ~20 s in. Consequence: REPLACE route 100%, both REINSTALL routes 0%.
  | ~2 h | grip quality needs to be a measured, reported quantity (hang drift over
  time), not an assumption
- 2026-08-02 | I re-implemented the v2 wedge defect twice, in new clothes, in one
  session. (a) I derived the wrist Z target from the LIVE hang offset -- so as the
  part slipped the target rose, the wrist chased it upward and it slipped further:
  hang 52 -> 161 mm inside one phase. (b) PRE-INSERT's coarse centering law
  `tcp + (SOCK - cart_xy)` is safe with a firm body grip but excites a pendulum on a
  loose cap grip -- the part swung 17 mm off-axis and tilted 40 deg. **Both are the
  same family as the original wedge: a loop closed on a workpiece that can stop
  tracking, driving a command that can keep growing.** Latching the reference fixed
  (a); deleting PRE-INSERT from the reinstall route fixed (b). | ~40 min | knowing a
  defect class does not stop you rebuilding it -- anti-windup wants to be a reusable
  primitive, not a lesson
- 2026-08-02 | A dropped part turns every part-referencing law into a pursuit
  controller. Once the cartridge left the jaws, the tip-following target tracked it
  lying on the bench and the arm walked itself to a 700 mm wrist height chasing it.
  Added an explicit lost-part guard (hang > 150 mm with jaws closed = fail honestly).
  | ~15 min | every servo-on-the-workpiece law needs a workpiece-present precondition
- 2026-08-02 | Placing a part is harder than picking one up, for a non-obvious reason:
  a 113 mm/s descent through a compliant grip tips the part, and releasing a tilted
  part topples it -- after which every downstream alignment gate times out on a
  cartridge lying on its side. Slowing the descent and gating release on BOTH height
  and uprightness helped, but did not fix it. | ~45 min | place operations need a
  compliant self-centering nest, not a flat surface and good intentions

## v3 session — refurbishment swap cycle (2026-08-02)

- 2026-08-02 | The extraction physics warning was CORRECT and the mitigation was
  free, because it was designed in rather than discovered. Untwisting through a
  friction grip on a 22 mm cap loses a measured **16–18% of the commanded rotation
  to torsional slip** (seed 0: wrist turned 79.2°, cartridge turned 65.6°). Dead-
  reckoning the wrist by −55° would have left the lug axis ~10° short of the slot
  and jammed the lift. It cost nothing only because the servo was closed on the
  MEASURED CARTRIDGE yaw from the first line of code — it just keeps commanding
  until the *part* reaches the slot axis. | ~0 min | this is the strongest argument
  yet for "close every loop on the workpiece, never on the tool"; it turned a
  predicted showstopper into an invisible 16% tax
- 2026-08-02 | Verified the bayonet is a REAL constraint before trusting any swap
  result: pulled the seated cartridge straight up with 15 N (5× its weight) at the
  locked angle — it rose 3.1 mm and stopped, lugs bottomed against the collar
  underside. At 90° (slots aligned) the same pull launched it 860 m. Without that
  check a "successful extraction" could have just been the part being yanked
  through geometry that never held it, and the whole refurb demo would have been
  worthless. | ~10 min | scene-level assertions ("this joint must resist X") should
  be a first-class test type, not something you think to write by hand
- 2026-08-02 | Anti-windup was applied to the untwist BEFORE seeing it fail, purely
  because it is the same shape as the v2 wedge: a loop closed on a part that can
  stop moving, driving a command that can keep growing. It never triggered in 125
  trials. That is the correct outcome and also means it is UNTESTED in anger — the
  same trap as the v2 recovery path, which looked fine until it was exercised with
  zero retries. Flagged rather than assumed. | 0 | "this guard never fired" needs to
  be surfaced by the eval, not discovered by reading code
- 2026-08-02 | The bin acceptance check nearly became a lie. First draft only tested
  xy-distance to the bin centre, which a cartridge still hanging in the gripper
  directly above the bin would pass. Added a height bound AND a separate `removed`
  check (part must be demonstrably out of the socket), so "discarded" cannot be
  satisfied by a part that never left the jaws. | ~10 min | success predicates for
  place/drop actions need a "and it is no longer attached to the robot" term; easy
  to forget, and it silently inflates the number

- 2026-08-01 | `dwell_left` is cumulative, not consecutive — it's only reset on a
  phase change, so it decrements on any step where `done` momentarily holds. A
  jammed insert whose TCP oscillates around the 129 mm threshold can burn the
  full 0.3 s dwell on transient touches and "complete" without the condition
  ever holding continuously. | ~10 min | dwell timers should reset when the
  condition goes false, unless cumulative is explicitly intended
