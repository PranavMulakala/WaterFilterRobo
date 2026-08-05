# Pain Journal — every gotcha is product research
Format: date | what happened | time lost | what would have prevented it

Companion: **[LEARNINGS.md](LEARNINGS.md)** — the same journey written as concepts
rather than incidents, in plain English. This file is what went wrong; that one is
what we now understand.

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
## v4 Phase D — LeRobot dataset export (2026-08-02)

- 2026-08-02 | The action stream was already in the simulator and did not need
  reconstructing: `data.ctrl` IS the commanded joint position the controller sent, so
  the demonstration can be recorded through the existing `frame_cb` hook without
  touching the controller at all. Sanity-checked that it is a real command and not a
  copy of the state — mean |action - state| is 0.016 rad of tracking error. Had that
  been ~0 it would have meant we were logging the measured state twice and calling one
  of them an action, which would train a policy to predict where it already is. | 0 |
  **verify that your action and observation are actually different signals** — a
  degenerate action channel is silent and fatal
- 2026-08-02 | Exporting only successful episodes is correct AND a bias worth writing
  down. A policy trained on failures learns the failures — but the controller has
  retry logic that fires on ~7% of cycles, and skipping failed trials means the
  dataset contains **no recovery demonstrations at all**, which is exactly the
  behaviour imitation policies are worst at acquiring. Recorded in the dataset card
  rather than left implicit. | 0 | dataset selection criteria belong in the dataset,
  next to the data, not in the head of whoever generated it
- 2026-08-02 | Validated the export structurally (parquet rows == declared length,
  video frames == rows, contiguous frame_index, continuous global index,
  episodes_stats.jsonl present as v2.1 requires) and then said plainly, in the code
  and the card, that this is **NOT** a round-trip through the real `lerobot` library.
  It would be very easy to write "LeRobot v2.1 dataset" and let the reader assume it
  loads. | 0 | name the verification you did NOT do, especially when the thing you
  did do looks thorough

## v4 Phase C — domain randomization (2026-08-02)

- 2026-08-02 | **I shipped a silent no-op flag and read the smoke test as success.**
  Added `--dr` / `--stats` to the eval CLI with a `str.replace` anchored on
  `if a.eval:` when the file actually said `elif a.eval:`. `str.replace` on a
  non-matching pattern does nothing and returns happily, so both flags were parsed and
  discarded. My "smoke test" printed plausible numbers and I accepted them without
  checking that the DR banner had printed. Four parallel sweep runs then produced
  **byte-identical nominal results** and each silently overwrote the others' stats
  file. Four independent reviewers all caught it; I had not. | ~40 min | **a config
  flag that is silently ignored is worse than one that crashes** — it reads as "this
  variable has no effect", which is a wrong scientific conclusion rather than an
  error. Fixes now in place: the eval prints its resolved CONFIG line before running,
  and every scripted edit asserts its anchor matched before writing
- 2026-08-02 | Corollary worth keeping: **"the smoke test passed" is not a verification
  unless you name in advance what the test would show if the change had NOT applied.**
  Here the tell was one line of banner text and a `dr_dz_mm` column that would read
  0.0. Both were available and I looked at neither. The DR verification now asserts
  `dr_dz_mm != 0` directly
- 2026-08-02 | Reviewers surfaced a real coverage gap in a metric I had been quoting:
  **`clean_verified_rate` = 100% is not coverage.** Only parts routed to CLEANING get
  re-inspected, so the 7 light parts wrongly graded heavy were binned and never
  re-graded — the metric structurally cannot see the dominant error class. A
  verification rate is only meaningful alongside what it is blind to | 0 | report the
  denominator of every "verified" number, not just the rate

- 2026-08-02 | The obvious fix for the DR height sensitivity was **tried and it made
  things worse.** Pick heights are absolute z, so a cell sitting 5 mm high should mean
  every grasp misses by 5 mm — referencing the measured part height looked like the
  same "reference the part, not the tool" lesson that had paid off four times already.
  Measured: routing **90.0 -> 85.0%** at ±5 mm, aborts 6 -> 9, nominal unchanged.
  Reverted. Commanding an absolute descent and letting the gripper contact the surface
  is evidently more forgiving than aiming at a measured height — compliance beats
  precision here. | ~25 min | **a lesson that generalised four times still does not
  generalise a fifth by default.** The reason it kept working before was that those
  loops closed on a part in free flight; a pick ends in contact, where softness is
  worth more than accuracy
- 2026-08-02 | The DR sweep would have produced a nonsense conclusion if the RNG had
  not been separated. DR draws initially came from the trial's own `rng`, consuming
  values and shifting everything downstream, so a DR-on run got **different parts,
  spawns and lock angles** than DR-off. The tell was the per-route counts moving
  (11/22/27 -> 23/21/16) between configs that were supposed to be the same 60
  scenarios, and it showed up as DR apparently *improving* accuracy 86.7 -> 93.3%.
  With an independent stream the scenarios are byte-identical across configs and
  inspection accuracy is flat at 86.7%, which is the physically sensible answer —
  mass, friction and table height cannot affect a camera. | ~20 min | **any A/B where
  the treatment draws randomness must draw it from a separate stream**, or you are
  comparing two different experiments and calling the difference an effect

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

- 2026-08-04 | Read the real work instructions (13 Waterwala Labs PDFs) and found the
  summary of them had dropped a step. The condensed analysis described Stage 10 as
  "membrane → bowl → cap tighten → dip → verify". The source (3.6 → 3.7) plugs the
  permeate outlet with an END PLUG, closes the reject outlet with a BALL VALVE, and
  pressurises the assembly to 80–90 PSI air BEFORE dipping it. The dip is a bubble
  test on a pressurised part, not a wash. Building the station from the summary would
  have produced a demo missing the very step that makes its pass/fail meaningful — and
  the customer would have spotted it, in their own document, in the first meeting.
  | ~25 min | when a summary and a primary source both exist, the primary source is
  not optional. A derived doc is a search index, not an input
- 2026-08-04 | Our twist-lock is NOT their cap. The analysis called our cycle "nearly
  one-to-one" with Stage 10; the work instruction says the membrane cap is threaded and
  "tightened with the help of spanner tool", i.e. multi-turn rotation to a torque
  criterion. Ours is a 55° indexed bayonet. Same task CLASS (align → insert → rotate to
  secure), different motion. Caught before it went in a pitch. | ~0 min | "our demo is
  basically their process" is exactly the claim to re-derive from the source before
  saying it out loud — it is the most flattering possible conclusion, which is why it
  needs the most checking
- 2026-08-04 | The labels exist; the definitions don't. Stage 1 and the QC flow both
  route every returned unit to Easy / Medium / Hard, and both defer the actual criteria
  to QC Annexure 1, which is not in the document set (Annexures 1–13 are all absent).
  So we can grade the two visual features they name — chassis dents/scratches,
  crimping — but any class boundary would be ours wearing their vocabulary. Recorded in
  `dp_process.py` as a hard warning in the dump rather than a comment someone can skim
  past. | ~15 min | when adopting a customer's vocabulary, check whether you got the
  words or the definitions. Inheriting the words alone silently converts our guess into
  their spec

- 2026-08-04 | **Text-extracting a vector flow chart silently invented a specification.**
  The three QC pages are 100% vector line art (228/291/65 drawing objects, zero raster).
  `get_text()` returns every node label and NOT ONE EDGE. The "REFER QC ANEXURE n" ovals
  attach to their governing box by a drawn leader line — so with the lines gone, each
  oval bound to whatever label happened to be nearest in reading order. **8 of the 13
  annexure bindings came out wrong**, including the one this project's headline ask was
  built on: we told ourselves Annexure 1 defines Easy/Medium/Hard, and it actually
  governs CABINENT / STICKERS CHECKING three nodes downstream. The triage has no
  annexure at all. We were one meeting away from asking the founder for a document that
  would not have answered the question. Fix: render the pages and read them as images.
  | ~90 min incl. re-transcription | an extraction is only as good as the modality it
  used. Text extraction on a diagram does not fail loudly — it returns confident,
  well-formed, wrong structure. Ask "what did this format DROP?" before trusting it
- 2026-08-04 | The renderer wasn't installed and nothing said so until the read failed.
  `Read` on a PDF needs `pdftoppm` (poppler), absent on this Mac. Thirteen subagents hit
  it simultaneously; all thirteen recovered on their own via PyMuPDF, which was already
  in the venv. Cost was ~0 because the fallback existed, but the failure mode is worth
  recording: the capability gap was invisible until the moment of use, and the tool that
  did work was already installed as a transitive dependency nobody had noticed.
  | ~10 min | environment probes belong in setup.sh, not in the middle of a task. Add a
  "what can this box actually do" check
- 2026-08-04 | **The first reachability study failed the gate for three reasons, and all
  three were bugs in the STUDY.** Front-face coverage came back 10%. Before touching the
  cell: (a) the camera standoff was hardcoded at 0.545 m when the optics need 0.293 m to
  frame a 450 mm box at fovy 75 — that pushed the far side of the orbit to x = 1.05
  against a measured max planar reach of 0.93 m, so "unreachable" was the true answer to a
  question nobody should have asked; (b) it demanded a full 360° orbit when the
  classifier only needs two separated views; (c) it demanded an exact-normal press when
  a compliant wiping pad conforms over ~30°. Corrected, front face went 10% → 83% → 100%
  at the right placement. The report now prints strict AND relaxed side by side so the
  relaxation cannot hide. | ~40 min | when a gate fails, suspect the gate first. A test
  that over-constrains reports a real number about an unreal task — and "we relaxed the
  spec until it passed" is indistinguishable from honest work unless both numbers ship
- 2026-08-04 | Whited-out content in a customer document. QC page 1 has two white-filled
  rectangles (content-stream xrefs 21, 22, DeviceRGB) appended AFTER the AutoCAD export,
  painting over an ellipse reading "QC WILL MONITOR" attached to VISUAL INSPECTION.
  Blanking the two streams and re-rendering recovers it. Almost certainly someone tidying
  a note in a PDF editor — the text was never removed from the text layer, which is not
  what concealment looks like, and the content is unremarkable. Recorded because a claim
  about a customer's document has to be checkable, and because rendering alone would have
  missed it in the other direction: the text layer and the visible page DISAGREE.
  | ~15 min | when text extraction and the render disagree, that is signal, not noise.
  Neither one is the document

- 2026-08-04 | **The reachability study measured a box that wasn't there.** `_set_cabinet`
  wrote `geom_size = [width/2, depth/2, height/2]` (width along X) while `raster_test`
  placed the front face at `cx +/- depth/2` (depth along X). With a 250 x 180 mm cabinet
  that put every front/back raster target **35 mm INSIDE the solid box** and every
  left/right target 35 mm outside it. Five of six face-coverage numbers were measuring
  nothing real, and the front-face "collisions" were the arm being told to reach into the
  middle of a solid object. Only `top` was accidentally correct, because Z was consistent.
  Everything reported from V5-0 before this had to be re-run; the placement decision
  changed as a result (x=0.62 -> 0.58). | ~35 min | axis conventions need to be asserted,
  not commented. The fix was renaming w/d/h to width/depth/height AND a test that every
  face plane coincides with the real surface -- the second is what would have caught it
- 2026-08-04 | **A backdrop is scenery to us and a wall to the robot.** Added a matte
  panel across +Y for the inspection background. Right-face raster coverage went from
  89.6% (bare probe scene) to **0.0%** in the real scene, because the arm must swing its
  elbow past y=0.40 to press on a +Y surface. Nothing in the scene looked wrong; the panel
  is 6 mm thick and reads as decoration. Fixed by deleting it and widening the single +X
  panel, which still fills the background at every framed camera azimuth. | ~25 min |
  ANYTHING added to a scene is an obstacle until proven otherwise. Re-run the reachability
  gate against the REAL scene, never only the simplified probe -- the probe passed
- 2026-08-04 | **The failure reason lied, and sent me hunting the wrong bug.** The raster
  tried a cone of tool orientations per point and, on failure, recorded the reason from
  whichever orientation happened to be tried LAST. One point reached its target with
  **0.0 mm position error** and was rejected for collision -- and was reported as
  "unreachable". I spent 20 minutes looking for a kinematic problem that did not exist.
  Fixed: if any orientation actually reached the point, report the binding constraint
  (collision/joint_limit); "unreachable" now means genuinely out of reach. | ~20 min |
  a diagnostic that aggregates over retries must report the MOST INFORMATIVE outcome, not
  the last one. Wrong-but-plausible error messages cost more than no error message
- 2026-08-04 | **One failed point silently zeroed a whole face.** The raster warm-started
  each IK solve from the previous success. If the FIRST point of a face failed, the seed
  never advanced, every later point cold-started into a bad basin, and the face reported
  0% -- a number driven by iteration order, not by the robot. It is indistinguishable from
  a genuine unreachable face. Fixed by falling back to the cold seed per point, making the
  result order-independent. | ~15 min | any warm-started search needs a fallback, or its
  first failure becomes its final answer. Test: does shuffling the input order change the
  result? If yes, the result is not a measurement
- 2026-08-04 | **Revealing a hidden geom made it BLACK.** The three condition pools were
  written with `material="soilmat" ... rgba="0 0 0 0"` and revealed by setting alpha to 1.
  In MuJoCo a geom's own `rgba` OVERRIDES its material colour, so every patch appeared
  black regardless of its material -- brown dirt, white scratches and grey dents rendered
  identically. The classifier would have been fed three visually identical classes. v4 got
  this right by writing the material's RGB into the geom and zeroing only alpha; that
  detail was not obvious from reading v4 and had to be rediscovered from a render.
  | ~10 min | if a value can be specified in two places, find out which one wins BEFORE
  building on it -- and look at the picture, because this was invisible in every assertion
  I had written

- 2026-08-04 | Smoke-testing the CLI with `--eval 2` **overwrote the committed baseline
  stats** with 2-trial data. `stats.json`, `stats_v3.json` and `stats_v4.json` are the
  recorded baselines the whole project measures against, and any run of the eval clobbers
  them regardless of trial count. Caught immediately by `git diff`, and the full evals
  were re-run to restore them -- but a smoke test should not be able to destroy the
  reference data. | ~20 min of re-running | either the eval should refuse to write stats
  below some trial count, or the committed baselines should live somewhere the eval
  cannot reach. Verification runs must not have side effects on recorded results

- 2026-08-04 | **The v4 keyframe trap, verbatim, one project later.** CLAUDE.md has
  recorded since v2 that "the keyframe `home` predates the cartridge free joint -- its
  qpos must be set explicitly after `mj_resetDataKeyframe`". The v5 scene inherits the
  same `home` from xarm7.xml, which declares only 13 arm+gripper values; MuJoCo zero-fills
  the rest. Result: anyone resetting to `home` teleports the pad tool to the WORLD ORIGIN,
  20 mm inside the bench, with a degenerate zero quaternion. Nothing in V5-A resets that
  way, which is exactly why it survived every check I wrote -- a landmine armed for the
  first controller that does. `home` can't be fixed in xarm7.xml without touching three
  validated cells, so the scene now emits its own complete `v5home`. | ~25 min | a gotcha
  written in a doc is not a fix. This one was DOCUMENTED, and recurred anyway, because
  documentation doesn't run. It's an assertion now
- 2026-08-04 | **A 4 mm decorative strip buried 7 pieces of ground truth.** The front
  facia accent stands proud of the cabinet face across a 60 mm z-band. Seven condition
  patches were sampled behind it -- physically invisible from every camera at every
  index angle. The classifier would have been graded against defects it is structurally
  incapable of seeing, capping accuracy for a reason with nothing to do with vision, and
  it would have looked like a vision problem. | ~15 min | when ground truth is placed
  procedurally, assert it is OBSERVABLE, not just that it exists. "Is it there?" and
  "can the sensor see it?" are different questions and only the first was being asked
- 2026-08-04 | **The compliant pad crushed through its own mount, and its compliance
  wasn't the number we declared.** Two independent bugs in one geom. (a) `solimp` width
  0.012 on a pad of half-thickness 0.010: contact impedance never reached full stiffness
  before full penetration, measured at **18.6 mm of penetration at 20 N through a 10 mm
  pad**. A wiping pass is well inside that range, so V5-C would have been built on a tool
  that does not exist. (b) MuJoCo AVERAGES `solref` between the two geoms in a contact
  unless one sets `priority`; the declared 0.045 was silently acting as 0.0325 against the
  post, and would have differed against every other surface. Fixed both, then swept the
  parameters and found two otherwise-sensible settings with a solver instability that
  spiked penetration to 12-17 mm at 40 N and recovered at 60 -- non-monotonic, i.e. the
  pad passes through its mount at one load and not at a higher one. Final values give
  1.4-4.6 mm across 0-60 N, monotonic. | ~45 min | contact parameters are not
  declarations, they are inputs to a negotiation between two geoms and a solver. MEASURE
  the force/penetration curve and require MONOTONICITY -- a single spot-check at one load
  would have passed the unstable settings
- 2026-08-04 | **CELL_SPEC said the indexer carries "a ~5 kg device"; the modelled device
  was 21.28 kg.** No geom in the cabinet carried a mass or density, so MuJoCo filled the
  solid boxes at its 1000 kg/m3 default -- a water-filled cabinet. The 5 kg was neither
  measured nor flagged, in a document whose own preamble promises every number is read out
  of the simulation. Nothing in V5-0/V5-A depends on it (the study is kinematics-only) but
  the indexer sizing does. Now an explicit 8.0 kg placeholder, labelled as an open ask.
  Setting it on the main box alone left the cover, facia and back panel at default density
  and the total came out 9.48 kg -- caught within one minute by `v5_check_spec.py`, which
  is precisely why that check exists. | ~20 min | a physical parameter nobody set still
  HAS a value, and it is whatever the engine defaults to. Grep the scene for geoms with
  neither mass nor density before quoting any mass anywhere

- 2026-08-04 | **The triage classifier's search region took four rounds, and each round's
  false positives looked like real defects.** The dent channel is the safety-critical one
  (dents have no remedy in any of the ten stages), and it kept filling with things that
  were not dents: (1) a projected 2D BOUNDING BOX swallowed the turntable rim, the bench
  edge and the device's own cast shadow -- measured 3381 of 3398 dent pixels on no defect
  geom at all; (2) a convex hull of a CIRCUMSCRIBED box, sized to cover every index angle
  at once, was still 154 mm half-extent against a 90 x 125 mm device and left ~1000 false
  px per view; (3) a hull at the COMMANDED index angle, lifted clear of the bench, still
  left 62.6% of the dent channel as structural edge; (4) PER-FACE regions finally fixed
  it -- 7.1% edge, 86.2% real dents. The residue in round 3 was the shading STEP between
  two faces and the top-cover seam: long dark lines that survive erosion and read as
  compact. Inside a single face there is no such step. | ~2 h | a defect detector's
  hardest problem is the part's own geometry, not the defect. Segment to a region where
  the only thing that can be anomalous IS a defect -- per feature, not per object
- 2026-08-04 | **A background threshold cut the defects out of the image.** `v_bg` was
  0.30, chosen to separate the device (0.788) from the backdrop (0.085). Dents render at
  0.298. So every dent fell BELOW the background threshold, was excluded from the body
  mask, and became a HOLE -- and the erosion that follows then chewed a ring around each
  hole, which is what the classifier was actually measuring. Units with 14-17 dents
  detected ZERO real dent pixels while reporting thousands of false ones. Visible
  immediately in a mask overlay as black squares where the dents were; invisible in every
  number. | ~30 min | a threshold that separates foreground from background must also sit
  clear of the DARKEST thing you care about finding. Check a threshold against every
  class, not just the two it was drawn for
- 2026-08-04 | **The calibration number was the overfit, not the held-out number.** Fitted
  two thresholds on 45 calibration seeds: 88.9% on calibration, 73.3% held out -- and the
  instinct is to distrust the held-out figure. Refitting on 100 calibration seeds gave
  74.0% ON CALIBRATION. The calibration score CONVERGED DOWN to the held-out score once
  there was enough data; the 88.9% was two thresholds fitted to 45 points. | ~15 min |
  when calibration and held-out disagree, the cheap check is to enlarge the CALIBRATION
  set and watch which number moves. The one that moves is the one that was lying
- 2026-08-04 | **I burned a held-out set by looking at it twice.** Ran the 60-seed eval
  (200-259), changed the frozen thresholds, ran it again. That is two looks, and the
  better of the two numbers is no longer a clean held-out result no matter how it is
  described. Also, with 60 units split three ways there were only 12 EASY units, so that
  cell's accuracy swung 41.7% -> 0.0% between the runs on a difference of five units.
  Resolution: report both looks openly and re-evaluate on FRESH untouched seeds (300+)
  with a bigger sample. | ~0 | a held-out set is consumed by use. Decide the number of
  looks BEFORE running, size the eval so the smallest class has enough units to be
  meaningful, and keep a reserve of seeds nobody has rendered

- 2026-08-04 | **A diagonal scratch has a square bounding box.** The triage classifier
  tells a scratch from a dent by shape, and the first shape test was the bounding-box
  aspect ratio. A 40 px scratch at 45 degrees has a ~30x30 bounding box -- aspect 1.0,
  i.e. "perfectly compact" -- so it was counted as a DENT. Scratch geoms are placed at
  uniformly random angles, so MOST scratches defeated the test, and the two errors were
  the same defects counted in the wrong channel: dents over by +3.2 per unit, scratches
  under by -3.2. Replacing the bbox with the principal-axis ratio from the pixel
  covariance (rotation invariant) took the count error to +0.3 / -0.4 and the held-out
  accuracy from 55.0% to 90.0%. | ~40 min | any shape descriptor computed from an
  axis-aligned box encodes the axes, not the shape. If the thing being measured can
  arrive at any angle, the descriptor has to be rotation-invariant -- and the failure is
  silent, because a wrongly-classified defect is still a detected defect
- 2026-08-04 | Scratches fragment before they are counted. A 1-2 px line, anti-aliased and
  then thresholded, breaks into a dashed row of specks -- each speck compact, each
  therefore a "dent". Fixed with a morphological closing (dilate then erode, radius 2)
  before component labelling. Separately, a size floor was needed: measured, real defect
  components run a median 114 px while spurious ones from residual edges run a median 2 px
  (p95 = 18), so a 25 px floor keeps 94% of real defects and removes 96% of spurious.
  Both numbers came from measuring the two populations, not from picking a round number.
  | ~30 min | when counting objects rather than pixels, the failure modes are splitting
  and merging. Measure the size/shape distribution of TRUE and FALSE components
  separately before choosing any cutoff

- 2026-08-04 | **A parallel-jaw grip is the wrong way to hold a process tool, and it took
  five fixes to prove it.** V5-C's wiping pad was first held in the gripper. Failures, in
  order: (1) a ROUND shank pivots in parallel jaws -- the pad's offset from the TCP went
  from (21.7, 0, 36.4) mm wrist-down to (87.6, 0, -16.1) mm wrist-horizontal, most of a
  right angle, coverage 0%; (2) keying the shank cut that to 9.6 mm but the tool still
  CREPT 60-70 mm across one face's raster; (3) that creep was INSENSITIVE to grip command
  (245 vs 255) and press depth (3.0 vs 1.5 mm), which rules out friction and rules in
  grip geometry. Replaced with a modelled TOOL CHANGER (weld equality, engaged only
  inside a 4 mm / 4 deg capture envelope, welding at the pose actually achieved): drift
  0.26 mm across the whole job. | ~3 h | when a fix is insensitive to the knob you think
  governs it, stop turning the knob. And a compliant grip is not a compliance STRATEGY --
  ours was absorbing path error by slipping, which looked like it worked right up until
  the coverage metric was believed
- 2026-08-04 | **Fixing the grip made the forces worse, and that was the honest outcome.**
  With the tool positively coupled, median contact force went from ~1 N (a slipping grip
  transmits little) to 101 N, peak 933 N. Nothing absorbed path error any more. Two
  causes: (a) the pad's geom ORIGIN is its centre, so commanding the centre onto the face
  plane buried it by half a thickness -- 12.5 mm of penetration before any press at all;
  (b) the arm's ~1.5 mm positioning error lands directly on the force when the coupling is
  rigid. The slipping grip had been acting as an accidental, terrible compliance element.
  Real surface-finishing cells use BOTH a changer (for location) and an active contact
  flange (for force) -- that is now a hardware recommendation in CELL_SPEC. | ~1 h |
  removing a bad mechanism can make the numbers worse while making the cell more honest.
  The force was always there; the grip was hiding it by failing
- 2026-08-04 | **Press depth had no effect on contact force, which was the clue.** Sweeping
  the commanded press 2.5 -> 1.0 -> 0.0 mm moved the median force 60.7 -> 60.3 -> 61.1 N.
  A parameter that does not move the thing it should move is not a weak parameter, it is
  the wrong parameter. Counting the pad's contact partners found 1.2 M contacts with
  `cab_backpanel` (153 k above 100 N): the face-plane calculation read `cab_body` only,
  while the back panel stands 10 mm PROUD of it, so at index 180 the raster drove the pad
  10 mm into the panel. | ~40 min | when a knob does nothing, stop tuning and ask what is
  actually generating the quantity. `mj_contactForce` per partner answered it in one run
- 2026-08-04 | **V5-C's coverage number was never a coverage problem. Four bugs in the
  motion layer, and a gate that was green while measuring the wrong quantity.** The task
  was "close the last of the 36.7% miss rate"; the assumption was press depth, raster
  pitch or face edges. It was none of them. `v5_clean_diag.py` SUBCLASSES the real cell
  (overriding `wipe`, `move`, `surface_x`, `front_face_plane`) rather than reimplementing
  the loop, so every number below comes out of the controller that actually ships.
  (1) **The rotary indexer never reaches 270 deg.** `d.ctrl[tt] = np.deg2rad(270)` = 4.712
  rad against an actuator `ctrlrange` of +-3.1416, and MuJoCo clamps ctrl silently. The
  fourth face pass re-wiped the back panel while one SIDE face was never presented at all
  -- seed 801 missed 3/3 right and 4/4 left, ~20% of patches, on every seed.
  (2) **The arm does not reach its commanded poses, anywhere in the cycle.** Every
  SAFE / TO FACE / RETRACT missed by 100-400 mm; the raster ran from the wrong place.
  Cause: `link1` against `link6` at 130-271 N with joint 4 pinned at its 30 Nm limit --
  arm SELF-COLLISION. The tool-changer moves (wrist pointing DOWN) arrive at 1.9-2.6 mm;
  everything with the wrist pointing HORIZONTALLY folds.
  (3) **34.2% of raster points were silently skipped.** `surface_x` casts a ray from
  x = 0.20 toward +X -- straight through the space the arm and pad occupy while wiping.
  When it lands on `xarm_gripper_base_link` (x61), `link7` (x33), `link4` (x26) or the pad
  itself, it returns None and the raster `continue`s: no wipe, no force sample, no entry
  in the contact stats. So the published "contact during raster 74.4%" is 74.4% OF THE
  POINTS THAT RAN, and the true figure over the planned raster is ~49%.
  (4) **The wiping tool is 105 mm from wrist to pad face; V5-0 sized the cell assuming
  45 mm.** `PAD_STANDOFF = 0.045` was a guess made before the tool existed. Those 60 mm
  come off the wrist's X, pushing it toward its own base -- the one direction a 7-DoF arm
  cannot go. Controlled sweep, same solver, one input changed: side faces 17/22 -> 4/22,
  top 15/25 -> 8/25. The arm riser, the other thing that changed since V5-0, costs
  NOTHING (`--riser` sweep flat at every diameter to 250 mm; feasibility identical with
  its collisions disabled). | ~3 h | the diagnostic that mattered was splitting "the IK
  never solved it" from "the arm did not track it" -- one line comparing where `q_des`
  puts the TCP against where the measured arm is. Before that split, four different bugs
  all looked like one vague "coverage is low"
- 2026-08-04 | **A green gate measuring a quantity the controller does not use.**
  `v5_reach.py --indexed` PASSES, and it is honest: every face is >= 95% reachable inside
  a **30 degree tilt cone**, which a compliant pad genuinely allows. But `v5_clean.py`'s
  `tool_mat_face()` returns a FIXED exact-normal frame and never tilts, so the cleaner
  runs in the STRICT column -- which the same run prints as front 83.3%, **right 27.1%,
  left 27.1%**, top 62.5%. `V5_PLAN.md`'s indexed table still quotes **83% for all four
  vertical faces**; that is not reproducible from the current code and scene, and the
  four-identical-numbers shape is the same smell that caught the 700.0 N clamp. Worse,
  re-running the placement sweep with the real 105 mm standoff shows **no placement
  serves every face at exact normal**: x >= 0.62 gives 15-17/22 on all four verticals and
  **0/25 on the top**, x = 0.54 gives 15/25 top and **0/22 on both sides**. | ~1 h |
  a gate only protects the thing it measures. This one relaxed by 30 degrees for a
  documented physical reason and then nothing checked that the consumer used the
  relaxation. Report strict alongside relaxed -- v5_reach already does -- and make the
  CONSUMER assert which column it is entitled to
- 2026-08-04 | **A planner that cannot see its own tool, and a tolerance the arm cannot
  hold.** Both fell out of replacing v5_clean's blind resolved-rate servo with
  plan-then-execute. (1) The pad is a free body on a weld equality, so it does NOT follow
  the arm when joints are moved in a planning copy -- its pose there is stale. The first
  planner therefore EXCLUDED the tool from its collision test, which left nothing checking
  whether a 60 mm pad would reach below the platter. Fix: reconstruct the weld transform
  (one quaternion multiply) and carry the tool, flange at its FREE extension because that
  is the longest it can be. Rule: the ARM may touch nothing, the PAD may touch the device
  and nothing else. (2) Wipe moves waited for the TCP within 4 mm. Under contact at that
  extension, 0.8 deg of joint lag IS 14 mm -- unreachable -- so every top-face point and
  60% of front-face points ran the full 2.5 s timeout pressing at full command: peak
  326 N, 74.8% in band, flange driven to 59 mm on a 30 mm stroke. Replaced with a STALL
  detector (seated >= 5 N and no longer closing). First attempt was "contact for 0.1 s",
  which fired on the first graze while the wrist was still 20-90 mm out and cost 11 points
  of coverage. | ~2 h | the giveaway for (2) was that the plan error was 0.00 mm at every
  single point while the achieved error was 14-59 mm. Plan quality and tracking are
  different measurements and separating them is worth doing FIRST, every time
- 2026-08-04 | **Identical numbers across two disjoint seed ranges -- and this time it was
  NOT a bug.** The held-out run (seeds 900-907) returned force, tilt, contact and
  raster figures identical to the development run to every decimal, which is exactly the
  smell that caught the 700.0 N clamp and the 0.854 surface probe. Checked before
  reporting: the cleaning trajectory is OPEN-LOOP and seed-independent -- the raster,
  the planned poses and the contact are the same for every unit, and the seed only moves
  the soil decals, which are non-colliding. So identical is correct, and the real finding
  is that those figures have NO seed variance: they are n = 1, not n = 8, and quoting
  them as an 8-unit spread would be the dishonest reading. `report()` now prints that
  warning on every run. | ~15 min | the smell test is worth running even when it comes
  back clean -- the answer here was not "false alarm" but "your force statistic has one
  sample and you were about to call it eight"
- 2026-08-04 | **The sabotage test passed n/n and the verifier was blind.** V5-D's first
  run scored honest-verified 10/10 AND sabotaged-caught 10/10 -- V5_PLAN's stated exit
  criterion, met exactly -- while letting **9 of 10 honestly-cleaned units pass with soil
  still on them**. Every one of the 12 residual patches was on the TOP face. Cause: the
  triage camera sits at z = 0.400 and the device top face at z = 0.450, i.e. BELOW the
  plane of that face (cos(normal, view) = +0.076), so `face_regions` returns the four
  VERTICAL faces only -- while V5-C wipes five faces and counts five in its coverage
  number. The killer is that the two blind spots COINCIDE: the top face is also where
  V5-C cleans worst (29.2% exact-normal reachability, 0/48 arrival in the V5-C
  diagnosis). **The station fails precisely where it cannot check.** Fixed by adding a
  second camera (`verify_top`) and grading the top face through it; false verifies
  9/10 -> 0/10 on the same seeds. | ~2 h | a falsification test with only a SABOTAGE arm
  measures nothing -- sabotage everything and a blind checker still catches it, because
  enough dirt lands where it can see. The diagnostic that mattered was reporting the
  HONEST arm's residual truth alongside its verdict, which turns "verified" into
  "verified, and here is what was still on it". Report FALSE VERIFIES next to the
  sabotage rate, always
- 2026-08-04 | **An exit criterion can be met vacuously, and this one was.** "Honest
  cleanings verified; sabotaged cleanings caught, n/n" was written into V5_PLAN months
  before the station existed, and it is satisfiable by a check that sees four of five
  faces. Criteria written before the thing they measure cannot anticipate where it will
  be blind. | ~0 | when a criterion is met on the first attempt, that is a reason to
  distrust it, not to celebrate. Ask what a broken version of the system would score
- 2026-08-04 | **The coverage gap and the force spike were ONE defect, and it was the IK
  picking a different arm every 27 mm.** V5-C's top face left residue and V5-C's force band
  would not close; both were chased separately for hours. Root cause: a 7-DoF arm has many
  joint configurations for the same tool pose, `plan_pad` returned the FIRST feasible one,
  and adjacent raster points therefore landed in different branches. Measured joint-space
  step between neighbouring points: **5.78 rad for a 37 mm move** on the top face, 32 of 90
  points above 0.5 rad on face 90, 32 of 120 on face 0 -- and **0 of 120 on face 180**,
  which was the only pass that had ever behaved. The executor interpolates at 0.02 rad/step
  inside a 2.5 s budget, so a branch jump cannot finish; on the way it swept the pad in a
  wide arc, measured 257 mm off target and 37 mm past the face edge, which is also where
  every force spike came from. Fix: prefer the solution nearest the previous configuration
  (0.35 rad/joint, against a 0.11-0.19 rad median that the geometry needs). Coverage
  94.6 -> 100%, in-band force 88.1 -> 99.1%, peak 271 -> 111 N, all from one change.
  | ~2 h | the tell was there the whole time and I had already printed it: ONE pass with
  zero jumps and four with dozens. When one instance of a repeated thing works and the
  others do not, diff the instances before diffing the theory. Also: a median that looks
  healthy (-2.4 mm) beside a min that does not (-233 mm) means outliers, not bias -- read
  both before reaching for a systematic explanation
- 2026-08-04 | **"Validated to 60 N" was hiding that the model BREAKS at 80 N.** The pad's
  force/penetration curve had only ever been swept to 60 N, and everyone (me included)
  read that as "validated so far" rather than "we have no idea past here". Swept properly:
  0.97 / 1.68 / 1.94 / 2.11 / 2.16 / 2.19 mm at 0-60 N, then **20.25 mm at 80 N** -- twice
  the pad's own half-thickness -- and non-monotonic above (21.6 at 120, 12.2 at 200). The
  cleaning cycle's 111 N peak was a real transient (0.012% of samples, 0.04 s) at a sane
  3.70 mm penetration, which made "it's fine, it's rare" very tempting. It is not fine:
  rarely inside a broken region is not outside it. Fixed instead -- the >60 N excursions
  were on exactly the two passes that still had IK branch jumps, so declining those points
  (`hard_joint_jump`) took the peak to 34.5 N with ZERO coverage cost. | ~1 h | the ceiling
  of a validation sweep is not a property of the hardware, it is a property of how far
  someone bothered to sweep. Probe past it and RECORD where it breaks, or the number gets
  quoted as a rating. `v5_check_scene` now prints 80/120/200 N without asserting them
- 2026-08-04 | **Shadowed `ok` and the eval died after printing its headline.** Added
  `ok = peak <= force_hi` inside `report()`, where `ok` already held the list of successful
  rows. The report printed COVERAGE, MISSED SPOTS and the force line, then died on
  `for r in ok` -- so the summary looked complete on screen while `stats_v5_clean.json` was
  never written and still held the PREVIOUS run's numbers. I only noticed because the JSON
  said peak 111 N while the console said 34.5 N. | ~10 min | the crash was harmless only by
  luck: a partial report that dies BEFORE the write is safe, one that dies after is a file
  half-updated. Compare the console against the artifact whenever both exist -- that
  disagreement was the entire signal
- 2026-08-04 | **The "monotonic to 60 N" pad curve was a COARSE-GRID ARTIFACT, and I had
  already published it.** Gate 1 swept 0/5/10/20/40/60 N, found it monotonic, and I wrote
  that the model "breaks between 60 and 80 N". Building V5-E the scene check failed on the
  pad -- and a fine sweep showed 45 N clean, **50 N BREAKS (11.6 mm on a 10 mm pad)**,
  55 N fine, 60 N breaks, 65 N fine. Intermittent solver instability, not a material
  property, and the original grid simply never sampled 50. Checked against the committed
  pre-V5-E scene: it breaks at 50 N identically, so this is pre-existing and NOT a V5-E
  regression -- but the published characterisation was the wrong SHAPE, not just the wrong
  number. Ceiling corrected 60 -> 45 N; cleaning peaks at 34.5 N so the conclusion stands.
  | ~40 min | a monotonicity check is only as good as its grid, and a coarse grid over a
  region with intermittent instability will report whatever the sample points happen to
  hit. Sweep finely inside the range you intend to CLAIM, and print the failure region
  instead of inferring it. The gate also took `max(-dist)` over EVERY contact in the
  scene, so adding the membrane station made it fail on a contact unrelated to the pad --
  filter to the geom you are actually measuring
- 2026-08-04 | **Four scene bugs in one V5-E sitting, three of them already in this file.**
  (1) `euler="0 0 30"` on the bowl wall segments -- xarm7.xml sets `compiler angle="radian"`,
  so that is 30 RADIANS; the ring of boxes was flung into the bench and the arm riser.
  (2) The `v5home` keyframe predates the three new joints, so MuJoCo zero-filled them and
  put the bowl AND the membrane element at the world origin, inside the riser: 174 contacts
  at spawn. **The keyframe block's own comment warns about exactly this**, from the last
  two times. (3) 12 wall segments 22 mm wide on a 173 mm circumference -- 91 mm of overlap.
  (4) The membrane element spawned 36 mm INSIDE its nest. | ~50 min | if a scene file
  carries a comment saying "if you add a joint, this string is part of the change", that is
  a checklist, not decoration. `v5_check_scene` catches spawn interpenetration in one run
  and should be the FIRST thing executed after any geometry edit, not the last
- 2026-08-04 | **V5-E's first "held-out" run returned 10.06 turns and 6.00 Nm on all TEN
  units, to the decimal.** The seed varied only the membrane element's position on its
  nest -- and nothing in the cap tightening depends on it, so ten seeds measured one unit
  ten times. Third instance of this exact defect in the repo (700.0 N force clamp; 0.854
  surface probe on every face), and the smell test caught it again. Fixed by varying what
  actually differs between real assemblies: O-ring friction (0.90 +- 0.13) and squeeze
  (3.0 +- 0.22 mm), and the angle the cap is presented engaged at. Turns then spread
  9.13-10.02. Note torque at cutoff stays 6.00 on every unit and that is CORRECT -- a
  torque-limited driver stalls at its limit by definition -- so the two identical-looking
  columns need opposite interpretations, and the report says which is which. | ~25 min |
  before believing an n-unit spread, ask what path the seed takes to reach the measurement.
  If you cannot name it, there isn't one
- 2026-08-04 | **Four V5-E modelling traps, none of them about the robot.** (1) A hinge and
  a slide tied by an equality is a screw -- but the cap is a CHILD body of the bowl, and
  MuJoCo excludes contacts between bodies connected by a joint, so the cap wound 49 mm down
  through its own O-ring without ever loading it. Explicit `<pair>` entries override the
  filtering. (2) Coaxial cylinder-on-cylinder flat contact generates nothing usable; the
  O-ring only worked once it became a ring of SPHERES. (3) The cap crushed straight through
  the seal at ~500 N until a hard rim was added for it to seat on -- a seal with nothing
  behind it is just a soft obstacle. (4) The bubble grader gated on LOW saturation and
  scored ZERO both ways: the bubbles are translucent white over blue water, so they take
  the water's hue and are not desaturated. Brightness alone separates them 0 px vs 3266.
  | ~1.5 h | every one of these is the physics engine's contact model, not the controller.
  Probe the mechanism in isolation BEFORE wiring a cycle around it -- the screw test that
  found three of them is fifteen lines
- 2026-08-04 | **Two stations computed the same global differently, and wiring them
  together silently broke the classifier.** V5-F's first route run graded seed 1500 truth
  EASY -> predicted HARD, a two-class jump the published confusion matrix says never
  happens. Ground-truth counts were identical on both paths; only the prediction differed.
  Cause: `v5_triage.load_scene()` sets `CAB_TOP = 0.220` from a freshly-loaded MjData while
  `v5_clean._sync_triage_globals()` computes **0.460** from the live model -- and the
  FROZEN TRIAGE THRESHOLDS WERE CALIBRATED AGAINST 0.220, so its per-face search quads
  cover about the lower half of each face. Grading the full face with half-face thresholds
  reads far more defect area and grades harder. Both are self-consistent; they are not
  interchangeable. Fixed by capturing v5_triage's own globals at construction and restoring
  them before every grade: 1 wrong in 1 became 0 wrong in 12. | ~35 min | MODULE-LEVEL
  GLOBALS SET BY A LOADER ARE SHARED STATE, and two stations in one process will fight over
  them. The tell was that the truth counts matched exactly while the verdict did not --
  when inputs agree and outputs do not, the difference is in state neither call passed
  explicitly. Also worth noting the calibrated region is HALF the face: that is not wrong
  (the thresholds were frozen against it and hold out at 97.5%), but nobody knew it
