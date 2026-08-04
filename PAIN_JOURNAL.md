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
