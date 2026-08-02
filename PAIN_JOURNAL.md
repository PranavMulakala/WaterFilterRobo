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
