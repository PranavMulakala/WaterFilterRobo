# Project: Water Filter Robot — Sim POC (DrinkPrime)

Instructions for Claude Code / any AI agent working in this repo.

## First steps every session
1. Read `PROJECT_CONTEXT.md` for the business background, `HOW_IT_WORKS.md` for the
   task, and `RESULTS.md` for the current numbers.
2. Set up if needed: `cd ~/WaterFilterRobo && ./setup.sh` (do NOT use a bare
   `python3 -m venv` — see below). The venv lives at the repo root, so commands from
   `sim_poc/` use `../venv/bin/python`.
3. Confirm the baseline before changing anything (from `sim_poc/`):
   `../venv/bin/python sim_poc2.py --eval 25` and `../venv/bin/python sim_poc3.py --eval 25`

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
- Append every gotcha, surprise, or manual workaround to `PAIN_JOURNAL.md` — it is
  deliberate product research for a possible robotics-devtools product.
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
- Extraction has **no chamfer**. Going in, the funnel centres the part mechanically;
  going out, the lugs must thread back up 3 mm slot channels with no lead-in. During
  UNTWIST/EXTRACT the wrist holds the socket axis exactly — any commanded lateral
  motion there is pure risk.

## Backlog (priority order)
0a. **Refurb v4 — inspect / clean / replace. PHASE A DONE; all three routes run.**
   `sim_poc4.py` + `cartridge_scene_v4.xml`. Inspection (real CV on rendered pixels)
   **works: 90.0% in-cell on held-out seeds, 3.7% false-clean, no heavy part ever
   graded clean.** Routing decision works. REPLACE route 100%. **Routing compliance 100%**
   on 60 held-out trials, all three routes 100%, end-to-end 86.7% (capped by vision,
   not mechanics), **false-clean rate 0.0%**. Fixed by a chamfered staging nest: the
   part is set down and re-gripped by its BODY, and the wet work happens after that
   re-grip — a cap-gripped part is dropped ~7 s into a dip. **Next: Phase B — the
   three-route video (90 s labelled 1.8x + a full-length honest cut).** See
   `RESULTS_V4.md`.
0b. ~~**Refurb v3 — cartridge swap cycle.**~~ **DONE 2026-08-02.** `sim_poc3.py` +
   `cartridge_scene_v3.xml`: extract a twist-locked spent cartridge, bin it, install
   a fresh one. 100% over 125 trials (25 + 100 held-out). See `RESULTS_V3.md`.
1. ~~**LeRobot dataset logging**~~ **DONE** — `sim_poc/lerobot_export.py` writes a
   LeRobot v2.1 dataset (parquet + per-camera mp4 + meta/, incl. `episodes_stats.jsonl`).
   8-dim state/action, wrist + overhead cameras. Structurally validated;
   **NOT round-tripped through the real lerobot library** — that remains unverified.
   Only successful episodes are exported, so the set contains no recovery demos.
   `--validate-only` re-checks an existing dataset. Datasets are gitignored (~6 MB/ep).
2. **Swap in real geometry when DrinkPrime's refurb video + device arrive.** The
   founder is shipping a process video, tech documents and possibly a physical unit.
   Those define the REAL refurb steps (descaling, filter media, gaskets, seals — we
   do not yet know), which determine whether the swap cycle is the right demo or
   merely the first scene of it. Do not over-invest in generic refurb content until
   they land. Replace the cartridge/socket geometry and re-run the eval.
3. Config dataclass to replace magic numbers (geometry, speeds, tolerances).
4. Domain randomization: mass ±20%, friction ±30%, table height ±5 mm; re-eval.
5. Second scene: screw-down station with torque-limited driver.

**Commercial context for prioritization:** the founder has indicated $20–30K of
funding for arms if the refurb process can be credibly simulated. Refurb fidelity is
therefore the gating item, ahead of polish on the insertion cycle.
