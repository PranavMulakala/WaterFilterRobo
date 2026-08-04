# Project: Water Filter Robot — Sim POC (DrinkPrime)

Instructions for Claude Code / any AI agent working in this repo.

## WHERE THE WORK IS — read this first (updated 2026-08-04)

**Current phase: v5, the three-stage funded demo. Plan of record: `V5_PLAN.md`.**

| phase | state |
|---|---|
| V5-0 reachability | **DONE** — passes at cabinet x=0.58; `v5_reach.py` |
| V5-A unit-scale scene | **DONE** — `make_scene_v5.py`, 5 faces, rotary indexer, tool changer |
| V5-B triage | **DONE — 97.5%** on 120 fresh units (700–819); `v5_triage.py` |
| V5-C cleaning | **PARTIAL** — tool holding solved (0.26 mm drift), **coverage only 44.7%** |
| V5-D verification + sabotage test | not started |
| V5-E membrane (Stage 10) | not started |
| V5-G video | not started |

**Immediate next task: model a compliance flange for V5-C.** Evidence: press depth
2.5→0.0 mm barely moved contact force (60.7→61.1 N), and with a rigid tool coupling the
arm's ~1.5 mm path error lands straight on the force. Real surface-finishing cells use a
changer for LOCATION plus an active contact flange for FORCE. Do not tune further — add
the component.

**Two things NOT to quote until fixed:**
- `stats_v5_clean.json` peak force reads **exactly 700.0 N on all 8 seeds** — identical
  across eight different soil layouts is a clamp, not a measurement. Cause unknown.
- V5-C coverage (44.7%) is not presentable.

**Seed ledger — held-out sets are consumed by use.** Spent: 200–259, 300–419, 500–619,
700–819 (triage), 800+ (cleaning). Calibration lives at 9000+. Use a FRESH range for any
new evaluation and look at it once.

## First steps every session
1. Read `V5_PLAN.md` (plan + all v5 results), `CELL_SPEC.md` (the real-cell build doc),
   `PROJECT_CONTEXT.md` (business background), `RESULTS_V4.md` (v4 numbers), and
   `LEARNINGS.md` (concepts the humans already have — do not re-explain them).
   `docs/drinkprime/README.md` covers the 13 source documents.
2. Set up if needed: `cd ~/WaterFilterRobo && ./setup.sh` (do NOT use a bare
   `python3 -m venv` — see below). The venv lives at the repo root, so commands from
   `sim_poc/` use `../venv/bin/python`.
3. Confirm the baselines before changing anything (from `sim_poc/`):
   `sim_poc2.py --eval 25` (100%), `sim_poc3.py --eval 25` (100%),
   `sim_poc4.py --eval 60 --seed0 200` (86.7% / 0.0% false-clean / 100% routing).
   All three should reproduce the committed `stats*.json` **byte-identically**.
4. Confirm the v5 gates: `v5_check_scene.py`, `v5_check_spec.py`,
   `v5_reach.py --indexed`. All three must pass before touching the scene.

## Environment — read this before debugging an install
- **Requires Python 3.10+.** Apple's system `python3` is 3.9, which has no MuJoCo
  wheel; pip falls back to a source build and fails with the misleading
  `RuntimeError: MUJOCO_PATH environment variable is not set`. `setup.sh` handles this.
- Dependencies are **pinned in `requirements.txt` on purpose.** Contact-rich physics
  is not reproducible across MuJoCo versions — the same seeds gave 84% on the
  original engine and 88% on MuJoCo 3.11. Do not bump versions casually; if you do,
  re-run the eval and update `RESULTS.md`.
- `--render` and `--cards` need TrueType fonts. The font path is resolved at runtime
  with a fallback chain; on Linux install `fonts-dejavu`.

## Codebase map
- `sim_poc2.py` — the whole system: xArm7 in MuJoCo, randomized cartridge spawn
  (±40 mm, 360° yaw), simulated perception (1 mm noise), closed-loop yaw servo,
  3 mm-clearance bayonet insertion through a chamfer funnel, drop-seat + regrip-cap
  + 55° twist-lock, and retry-on-stall.
  CLI: `--eval N` | `--render idx seed speed` | `--cards` | `--concat`
- `sim_poc3.py` — **v3 refurbishment cell: the cartridge SWAP cycle.** Extends v2 by
  import (`ik_step`, `down_mat`, the yaw servo law, the tip-following compliant
  descent and every insertion constant are reused, and the insertion half of the
  phase table is v2's verbatim). New half: EXTRACT (grip cap → untwist out of the
  bayonet → lift through the slots) then DISCARD (carry to bin → drop). Writes
  `stats_v3.json`; success = old cartridge binned AND new one seated+locked.
  CLI: `--eval N` | `--render idx seed speed` | `--cards` | `--concat`
- `ufactory_xarm7/cartridge_scene_v3.xml` — v2 scene plus a spent cartridge that
  starts seated **and twist-locked** (locked lug axis 25–50°, randomized per seed;
  the slot gap spans ~72–108°, so anything outside ~[64,116]° is captive), an open
  bin at (0.46, 0.0), and dull "spent" materials.
- `docs/drinkprime/` — **the 13 source PDFs.** See its README before reading them.
  **The three QC pages are pure vector line art: text extraction returns labels with NO
  EDGES.** Render them (PyMuPDF is in the venv; there is no `pdftoppm` on this machine)
  and look at them. Text-extracting them mis-bound 8 of 13 annexures once already.
- `sim_poc/dp_process.py` — **DrinkPrime's REAL process, as data.** Data only — no
  MuJoCo, no side effects. Holds `STAGES` (10 stages w/ materials, tools, activities,
  the plant's own section-tagged checks, scrap streams, and OUR feasibility tier),
  `QC_NODES` (+ the corrected annexure map), `PRESSURES`, `CONTRADICTIONS`,
  `SCRAP_STREAMS`, `V5_ROUTES`, `MISSING`. Run it for a dump. **The plant's text and our
  judgement live in separate fields on purpose — do not blur them, do not add a step
  that isn't in a source document, and DO NOT FIX THE SOURCE TYPOS** (`ANEXURE`,
  `CABINENT`, `APPERANCE`, `PRESSUE`, `SOLINOID`, `MEMBARANE`, `Rubbing component`) —
  they identify the source and they matter for string matching.
- `V5_PLAN.md` — the three-stage funded demo (TRIAGE / CLEAN / MEMBRANE), the plan of
  record, the V5-0 reachability result, and the one-week cut list.
- `sim_poc/v5_reach.py` + `ufactory_xarm7/cabinet_probe_v5.xml` — **V5-0 reachability
  study (DONE, PASSES at x=0.58).** Kinematics only, no dynamics.
  `--nominal` | `--sweep` | `--scene` (validate the REAL scene, not just the probe).
  Writes `reach_v5.json`. Reports strict (exact-normal) alongside relaxed (30° tilt cone)
  coverage — keep it that way, the gap is large (top face 100% relaxed, 63% strict).
  **Axis convention: depth→X, width→Y, height→Z.** Getting this wrong measured faces
  35 mm inside the box and invalidated five of six numbers; don't reintroduce `w/d/h`.
- `CELL_SPEC.md` — **the document you build and program the REAL cell from.** Frames,
  the sim→xArm-SDK coordinate conversion, station coordinates, tolerances, tooling, the
  rotary-indexer spec, a build checklist, and an explicit "what the simulation does NOT
  tell you". Every number is read out of the model, not typed from memory. Regenerate the
  numbers if the scene changes.
- `sim_poc/make_scene_v5.py` → `ufactory_xarm7/refurb_scene_v5.xml` — **V5-A unit-scale
  scene (DONE).** A GENERATOR (fixed seed), not hand-written geoms. Device on a **rotary
  indexer** at x=0.58, three condition pools — soil(40)/scratch(28)/dent(20) →
  EASY/MEDIUM/HARD, each grounded in a quoted stage — plus tool post, compliant wiping
  pad, matte backdrop, computed cameras. **Edit the generator, never the XML.**
  - **The rotary indexer (`tt`) is a COMMANDED AXIS, not scenery.** It is what takes the
    back face from 0% (unreachable at every fixed placement) to 100%, and it removes the
    camera-separation vs front-coverage trade-off. Verify with `v5_reach.py --indexed`.
  - Pools are on the **four reachable faces only**; the back carries none, so cleaning
    coverage means "of the reachable faces", not "of the device". Keep that wording.
  - Pool geoms must carry their **material's RGB with alpha 0** — a geom's `rgba`
    overrides its material, so `rgba="0 0 0 0"` reveals as BLACK and destroys the whole
    point of three visually distinct classes.
  - **Never add a geom to this scene without re-running `v5_reach.py --scene`.** A 6 mm
    backdrop panel that looked like scenery cost an entire face (89.6% → 0%).
- `sim_poc/v5_check_scene.py` — **run after regenerating the scene.** ~25 structural
  assertions (patches on-face and outward-facing, flush cover, indexer carries the device
  and its pools, pad rests on its post, no spawn interpenetration). The scene LOADED FINE
  through all five V5-A bugs; loading is not validation.
- `sim_poc/v5_check_spec.py` — **run after ANY scene change.** Asserts all 39 numbers in
  `CELL_SPEC.md` against the live model, plus the joint limits against the UFACTORY
  datasheet. CELL_SPEC's entire value is that its numbers were read from the model rather
  than typed; that decays silently the moment the scene moves. **If this fails, update
  CELL_SPEC.md — never relax the assertion.**
- `sim_poc.py` — simpler v1 (plain pick-and-place), kept for reference.
- `ufactory_xarm7/cartridge_scene_v2.xml` — the scene: socket collar (band
  58–100 mm), 45° chamfer funnel with lug gaps (spans z 98.5–126.1 mm), pedestal
  seat at 45 mm, cartridge (radius 21.5 mm, half-length 55 mm) with 2 lugs at local
  z = −49 mm. **Geometry MUST stay consistent with the constants in `sim_poc2.py`**
  (`SPAWN_Z=0.068`, `SEAT_Z=0.100`, `GRASP_OFF=0.004`, `CHAMFER_TOP_Z=0.1261`,
  `seat_tcp=0.110`).
- `ufactory_xarm7/xarm7.xml` — arm model (MuJoCo Menagerie) + added wrist camera.
- `stats.json` — last eval output. See `RESULTS.md` for the current headline number.

## Hard rules
- After ANY controller or scene change, run `../venv/bin/python sim_poc2.py --eval 25`,
  `sim_poc3.py --eval 25` **and** `sim_poc4.py --eval 30 --seed0 200` from `sim_poc/`, and report both success rates
  against the recorded baselines (v2: 100% locked; v3: 100% full swap). **Never
  claim a fix without an eval.** v3 imports v2, so a v2 change moves v3 too.
- **Report the margin, not just the rate.** A pass/fail rate hid a systemic defect
  once already (every trial was jamming; only the tail failed). When evaluating a
  change, also report peak cartridge tilt during INSERT — median and max. A change
  that raises the pass rate while leaving tilt high got lucky and will not
  generalise.
- **Validate on held-out seeds.** Tuning on seeds 0–24 and reporting 0–24 is
  overfitting. Confirm on seeds 25+ before believing a result.
- Never weaken the success criteria at the end of `run_trial` (`xy_off < 0.006`,
  `upright > 0.95`, `rel_twist > 30`) or special-case seed numbers to make a number
  go up. That is a failure, not a result.
- Do not break the CLI interface or the `stats.json` schema.
- **Running ANY eval overwrites `stats*.json`, including `--eval 2`.** Those files are
  the recorded baselines the whole project is measured against. Never smoke-test the CLI
  with a small `--eval N` without re-running the full baselines afterwards, and check
  `git diff -- sim_poc/stats*.json` before finishing.
- Append every gotcha, surprise, or manual workaround to `PAIN_JOURNAL.md` — it is
  deliberate product research for a possible robotics-devtools product.
- **Every session that lands a significant change appends a `LEARNINGS.md` entry.
  Written for the humans, not for agents.** Plain English, zero unexplained jargon,
  ≤15 lines, three sections: what we built (one sentence), the concept behind it
  (explained to a smart reader who is new to robotics), and why it matters for the
  real robot. This is how two software engineers compress a robotics education into
  a couple of months — treat it as a first-class deliverable, not a changelog.
  `PAIN_JOURNAL.md` records what went wrong; `LEARNINGS.md` records what we now
  understand. If a new term appears without an explanation, that is a bug in the file.
- Small incremental changes; explain the **physics** reasoning, not just the code.

## Known physics gotchas (learned the hard way — see PAIN_JOURNAL.md)
- The gripper's finger PADS sit ~25 mm ABOVE the `link_tcp` site. Grasp height is
  tuned so the pads land mid-body; changing `GRASP_OFF` blindly breaks the grasp.
- Commanded wrist yaw maps to NEGATIVE physical yaw (sign flip in `down_mat`).
- The keyframe `home` predates the cartridge free joint — its qpos must be set
  explicitly after `mj_resetDataKeyframe`.
- Position actuators sag under gravity; `qfrc_applied` gravity compensation is on.
- IK plans on the COMMANDED config (`ik_data`), not measured state — do not "fix" this.
- A lateral-correction law of the form `target = current + error` is an **integrator
  that winds up against contact**. When the part is jammed and cannot move, the wrist
  walks sideways indefinitely and torques the part. This caused the original wedge.
- **Untwisting through a cap grip loses 16–18% of the commanded rotation to
  torsional slip** (22 mm contact patch transmitting torque through friction). Never
  dead-reckon a twist from wrist angle — close the loop on the MEASURED CARTRIDGE
  yaw, or the lug axis lands ~10° short of the slot and the lift jams.
- **Calibrate vision through the real motion path, never on a teleported part.** The
  v4 classifier scored 90% on a rig that placed the part perfectly and 53% in the
  cell, because the presentation height used an assumed grip offset instead of the
  measured one. A vision model is only as valid as the fixture presenting the part.
- **A fixture must clear the part's LARGEST feature.** The staging nest was sized to
  the 21.5 mm body and interfered with the 34 mm bayonet lugs by exactly 7 mm. When
  something will not seat, ask MuJoCo for the contact list before theorising.
- **`euler="0 0.785 th"` on a chamfer ring is WRONG** — it tilts every plate about the
  same world Y axis, not radially, making a pinwheel that overhangs the bore. The
  socket only survives it because its bad plates land in the bayonet slot gaps. Use
  explicit `xyaxes`. Do not copy that pattern to a full ring.
- **Do wet/dynamic work only after re-gripping by the BODY.** The cap grip is weak and
  its hang offset is unstable (42-83 mm). It is fine for
  a short carry-and-drop (v3) and NOT fine for presentation, dipping or re-insertion.
  Anything needing precision must re-grip the part by its body first.
- **A drop in simulation is not automatically a real failure.** Anirudh (2026-08-02):
  sim-side drops and lost friction are *sometimes* artifacts of the simulator, up to
  outright geometry bugs where a gripper passes through the part — "obviously in the real
  world, you're not going to have that." He said *sometimes*, not usually, and he did NOT
  question the 16–18% untwist slip (he read it back approvingly as the gripper losing
  friction). This does not overturn the cap-grip finding above, which is measured and
  reproducible; it means the finding is a hypothesis about the real cell until a real
  gripper holds a real cartridge.
- Extraction has **no chamfer**. Going in, the funnel centres the part mechanically;
  going out, the lugs must thread back up 3 mm slot channels with no lead-in. During
  UNTWIST/EXTRACT the wrist holds the socket axis exactly — any commanded lateral
  motion there is pure risk.

## Backlog (priority order)
0a. **Refurb v4 — inspect / clean / replace. PHASE A DONE; all three routes run.**
   `sim_poc4.py` + `cartridge_scene_v4.xml`. Inspection (real CV on rendered pixels)
   **works: 86.7% in-cell on 60 held-out seeds (200–259), 0.0% false-clean, no heavy
   part ever graded clean.** (An earlier 90.0% / 3.7% was the smaller 30-seed run.) Routing decision works. REPLACE route 100%. **Routing compliance 100%**
   on 60 held-out trials, all three routes 100%, end-to-end 86.7% (capped by vision,
   not mechanics), **false-clean rate 0.0%**. Fixed by a chamfered staging nest: the
   part is set down and re-gripped by its BODY, and the wet work happens after that
   re-grip — a cap-gripped part is dropped ~7 s into a dip. **Next: Phase B — the
   three-route video (90 s labelled 1.8x + a full-length honest cut).** See
   `RESULTS_V4.md`.
   **Before investing further in the classifier, ask DrinkPrime how their own workers
   grade a cartridge** (Anirudh, 2026-08-02): visual inspection, a wear indicator or
   colour change, or *feel*? There is no single off-the-shelf classifier for this. If the
   wear is clearly visual an off-the-shelf VLM may beat the hand-tuned HSV thresholds; if
   workers grade by feel, camera-only inspection is the wrong architecture and the 86.7%
   is measuring the wrong thing. A custom trained model is a later problem, not this one.
0b. ~~**Refurb v3 — cartridge swap cycle.**~~ **DONE 2026-08-02.** `sim_poc3.py` +
   `cartridge_scene_v3.xml`: extract a twist-locked spent cartridge, bin it, install
   a fresh one. 100% over 125 trials (25 + 100 held-out). See `RESULTS_V3.md`.
1. ~~**LeRobot dataset logging**~~ **DONE** — `sim_poc/lerobot_export.py` writes a
   LeRobot v2.1 dataset (parquet + per-camera mp4 + meta/, incl. `episodes_stats.jsonl`).
   8-dim state/action, wrist + overhead cameras. Structurally validated;
   **NOT round-tripped through the real lerobot library** — that remains unverified.
   Only successful episodes are exported, so the set contains no recovery demos.
   `--validate-only` re-checks an existing dataset. Datasets are gitignored (~6 MB/ep).
2. ~~**Swap in real geometry when the refurb docs arrive.**~~ **DOCS LANDED 2026-08-04.**
   The 13 work instructions are transcribed in `sim_poc/dp_process.py`; the plan is
   `V5_PLAN.md`. What they changed:
   - Our cycle approximates **Stage 10, Membrane Assembly** — a real, named station.
   - But their cap is **threaded, spanner-tightened (multi-turn to a torque
     criterion)**, not our 55° indexed bayonet. Same task class, different motion. Do
     not repeat the "nearly one-to-one" claim without that qualifier.
   - Their dip is a **bubble test on an assembly pressurised to 80–90 PSI** with the
     permeate end-plugged and the reject valve closed — not a wash. So the camera check
     is *their* acceptance criterion.
   - **NO document in the set defines Easy/Medium/Hard.** (Corrected 2026-08-04: an
     earlier note here said Annexure 1 defines them — it does not, it governs
     CABINENT / STICKERS CHECKING. The triage fan-out has no annexure at all.) Any
     triage class boundary is OURS wearing their vocabulary. Label it that way every
     single time it is reported, and ask the founder open-endedly.
   - **HARD is not a dead end** — their chart forks it into RECTIFIABLE (rejoins the
     line) and NON RECTIFIABLE (scrap approval, cost > 80–90%).
   - **45 PSI vs 80 PSI contradiction** on the assembled-device leak test (stages 4/6 vs
     QC page 3). Recorded in `CONTRADICTIONS`, not reconciled. Ask before building any
     leak-test station.
   - **There is no teardown/disassembly work instruction in the corpus.** The extraction
     motion v3/v4 are built on has no documented counterpart. Worth knowing before
     claiming the sim mirrors their process.
   - Deformables (Teflon, stickers, harness, tubing) are a **deliberate de-scope**,
     recorded in PITCH_NOTES §9 as a decision, not a gap.
   Still blocked on: **what defines Easy/Medium/Hard** — the top ask, and it must be
   asked OPEN-ENDED because no document in the set defines it (Annexure 1 is the
   cabinet/sticker cosmetic spec, useful for CLEAN verification, not the triage);
   **QC Annexures 1–13**; **membrane bowl + cap + O-ring STL/STEP** (now outranks the
   cartridge); **cabinet outer dimensions AND mass**; and **whether the final leak test
   is 45 or 80 PSI**. Per Anirudh (2026-08-02) a
   manufacturer almost certainly already has the CAD and it can be asked for without the
   physical device. All 13 source PDFs are checked in at `docs/drinkprime/` — read its
   README before opening them. See `meetings/anirudh_call_2_transcript.md`.
3. Config dataclass to replace magic numbers (geometry, speeds, tolerances).
4. Domain randomization: mass ±20%, friction ±30%, table height ±5 mm; re-eval.
5. Second scene: screw-down station with torque-limited driver.

**Commercial context for prioritization:** the founder has indicated $20–30K of
funding for arms if the refurb process can be credibly simulated. Refurb fidelity is
therefore the gating item, ahead of polish on the insertion cycle.
