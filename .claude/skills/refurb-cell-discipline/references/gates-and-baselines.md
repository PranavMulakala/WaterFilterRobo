# Gates and protected baselines

Read this before running any eval. Everything here is run from `sim_poc/` using the repo
venv at `../venv/bin/python` — a bare `python3` is macOS's 3.9, which has no MuJoCo wheel
and fails with a misleading `MUJOCO_PATH` error.

## The three gates — safe, they write nothing

| command | checks |
|---|---|
| `../venv/bin/python v5_check_scene.py` | ~25 structural assertions: patches on-face and outward-facing, flush cover, indexer carries the device and its pools, pad rests on its post, **no interpenetration at the `v5home` keyframe** |
| `../venv/bin/python v5_check_spec.py` | all 50 `CELL_SPEC.md` numbers against the live model, joint limits against the UFACTORY datasheet, and the arm speed config against its published rating |
| `../venv/bin/python v5_reach.py --indexed` | every vertical face and the top ≥95% inside the 30° tilt cone |

`v5_reach.py --sweep` is the only reach command that writes (`reach_v5.json`).

**If `v5_check_spec` fails, update `CELL_SPEC.md` to match the model — never relax the
assertion.** The spec's entire value is that its numbers were read from the model rather
than typed, and that decays silently the moment the scene moves.

## Protected baselines — each of these OVERWRITES a committed stats file

Archive first. Each `--seed0` default reproduces the published number; changing it
overwrites the baseline with a figure that is not the published one.

| command | writes | published result |
|---|---|---|
| `sim_poc2.py --eval 25` | `stats.json` | 100% locked |
| `sim_poc3.py --eval 25` | `stats_v3.json` | 100% full swap |
| `sim_poc4.py --eval 60 --seed0 200` | `stats_v4.json` | 86.7% end-to-end, **0.0% false-clean**, routing 100% |
| `v5_triage.py --eval 120` | `stats_v5_triage.json` | 97.5%, missed-hard 0.0%, false-easy 2.5% |
| `v5_clean.py --eval 8` | `stats_v5_clean.json` | 100% coverage, 0 missed of 129, peak 23.9 N |
| `v5_clean.py --eval 16 --stroke --seed0 2120` | `stats_v5_clean_stroke.json` | 100%, 0 missed of **273**, peak 22.6 N |
| `v5_clean.py --eval 16 --stroke --solution --seed0 2204` | `stats_v5_clean_stroke_solution.json` | 100%, 0 missed of 252, **0.00 s dry-pad contact**, 1 dip/unit |
| `v5_clean.py --sabotage 10 --seed0 2140 --stroke` | `stats_v5_verify_stroke.json` | 10/10 caught, **0/10 false verifies** |
| `v5_membrane.py --sabotage 10 --seed0 1890` | `stats_v5_membrane.json` | 10/10 inserted, 10/10 stalled, 10/10 leak pass, **0 false pass** |
| `v5_route.py --eval 28 --seed0 1700` | `stats_v5_route.json` | 28/28 compliance · 26/28 right-route · **22/28 fully backed** ← quote this one |

`v5_clean.py` tags its output filename by mode, so a `--stroke` or `--targeted` run cannot
land in the point-mode baseline. Preserve that if you add a mode.

## v2 / v3 / v4 are independent

They use their own scenes (`cartridge_scene_v2/3/4.xml`) and their own controllers, and do
not import `v5_clean.ArmProfile`. A v5-only change cannot move them — but the repo rule is
to run them anyway and report all three against the recorded baselines, because `v3`
imports `v2` and a change to `sim_poc2.py` moves both.

## Current headline figures

- Full MEDIUM cycle, true 1×: **2:34.9** — CLEAN 108.1 s, VERIFY 10.0 s, MEMBRANE 36.7 s.
  Clip: `media/v7_clean_stroke_realtime.mp4`.
- Shipping clean mode: **full coverage, continuous stroke**. `stroke_feed` 0.20 m/s,
  `row_frac` 1.20 R.
- Targeted cleaning is **WITHDRAWN** (failed its own 0/24 residue bar under the arm-speed
  clamp) and the **2:33** figure that came from it is **retracted**.
- Next free seed block: **2200+** (check `CLAUDE.md`, which is authoritative).

## Reproducibility

Dependencies are pinned on purpose. Contact-rich physics is not reproducible across MuJoCo
versions — the same code and seeds scored 84% on one engine version and 88% on 3.11.0, with
one seed flipping outcome at zero code change. **A success rate quoted without an engine
version is not a reproducible claim.** If you bump anything in `requirements.txt`, re-run
everything and expect numbers to move.

## The seed0 in the command IS part of the baseline

The row above said `--seed0 1920` until 2026-08-12, and it was wrong: 1920–1935 is the
**pre-clamp V7** validation (256 patches), while the committed file is the **post-clamp
V7.1** run at 2120–2135 (273 patches). Running the stale command overwrote the published
baseline with a different experiment — and it was nearly invisible, because the cleaning
trajectory is seed-independent, so **coverage, missed, peak force and in-band all matched to
every decimal.** The only fields that moved were `soil` and `seed0`.

Two things follow. **Diff the stats file, don't eyeball the printout** — the printout looked
perfect. And when a phase supersedes an earlier one, **update every command that names the
old seed block in the same commit**, because a stale `--seed0` in a reference doc is a
loaded gun pointed at a protected file.

## V9 additions (2026-08-13)

New tagged stats files — same protection rule, each is its own experiment:

| command | writes | published result |
|---|---|---|
| `v5_clean.py --sabotage 10 --seed0 2220 --stroke --inline-verify` | `stats_v5_verify_stroke_inline.json` | inline verify battery (row-identical to the end-pass battery on the 2140–2149 paired diagnostic) |
| `v5_membrane.py --sabotage 10 --seed0 2242 --fast-spindle` | `stats_v5_membrane_fast.json` | 10/10 across the board at 20 rad/s rundown |
| `v5_membrane.py --oring 10 --seed0 2280` | `stats_v5_membrane_oring.json` | **10/10 damaged-seal units PASS the bubble check** — the measured blind spot |
| `v5_clean.py --eval 16 --stroke --solution --inline-verify --rinse --dry --seed0 2260` | `stats_v5_clean_stroke_solution_inline_rinse_dry.json` | FULL STAGE 3 (three cloths) |

The datasheet TCP assertion is on the **arm's wrist** (`arm_tcp_speed_max`); the pad keeps
its own 1.25× sprung-tool bound. The pad can ring briefly faster than the arm moves — that
is the compliance, not the servo.

## V10 additions (2026-08-19)

| command | writes | published result |
|---|---|---|
| `v5_clean.py --eval 16 --stroke --solution --inline-verify --buff --seed0 2344` | `stats_v5_clean_stroke_solution_inline_buff.json` | 16/16 at 100%, 0 missed of 332, 23.35 N, reaction 0.29/0.47 N·m |
| `v5_clean.py --sabotage 10 --seed0 2360 --stroke --inline-verify --buff` | `stats_v5_verify_stroke_inline_buff.json` | 9/10 caught + 1 vacuous zero-soil draw (seed 2364), 0 false, 0 would-escape |
| `v5_clean.py --buff-sweep N --seed0 S --stroke --buff` | `sweep_buff.json` | rate table; 15 rad/s is a measured solver cliff (90.6 N) |

The spec gate now asserts **63 values** (buff post, disc radius, motor torque/speed, tool
mass). A sabotaged-cleaning unit that drew ZERO soil is a vacuous case, not an escape —
check `sab_left` before reading `sab_pass`.
