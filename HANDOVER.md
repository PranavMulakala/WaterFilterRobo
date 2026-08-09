# HANDOVER — state as of 2026-08-09

**Read `CLAUDE.md` first** (phase table + seed ledger are authoritative). This is the
five-minute version. `git log` is the detailed one; every commit message carries its
own evidence.

## Where things stand

| thing | state |
|---|---|
| v2 insert / v3 swap / v4 refurb loop | 100% / 100% / 86.7% — byte-locked baselines |
| v5 TRIAGE | 97.5% on 120 fresh units, missed-hard 0.0%, false-easy 2.5% |
| v5 CLEAN — full coverage (**default**) | 100% coverage, 0 missed of 129, peak 32.9 N under a 45 N ceiling, **186.8 s** |
| **V6 targeted clean** (opt-in) | **0/24 residue on fresh units**, sabotage caught 15/15, **~75–120 s** |
| v5 VERIFY | honest 10/10 verified, 0/10 false verifies, sabotage caught 10/10 |
| **V6-ARM membrane** | arm **inserts element** (10/10, worst seat 1.61/1.8 mm), **places the cap** (10/10, worst 1.86 mm into a 4 mm capture envelope) and **holds the driver**; stalls 10/10, leak 10/10, sabotage caught 10/10, **0 false pass** (1890–99) |
| routing | declared-trace 28/28 · right-route 26/28 · **fully backed 22/28** ← quote this one · false-easy 0/28 |
| **full MEDIUM cycle** | **2:11–2:45** (V6-ARM) / 3:51 (v5 full-coverage). True-1× videos for both |

## The five honesty labels that must travel with any demo

1. Easy/Medium/Hard **names** are DrinkPrime's; the **boundaries are ours** (asked, unanswered).
2. Targeted cleaning's dirt **locations** are ground truth standing in for camera
   localisation; the **residue check is a real camera** and catches sabotage 15/15.
3. Membrane: the arm does insert + cap-place + driver-hold. **Thread-start engagement
   (4 mm/4° capture) and spindle reaction torque are MODELLED.** The cap carries a
   **pick stem** — a design-for-automation feature we added, not a stock part.
4. HARD route = software decision, **no physical handoff (0/6 implemented)**.
5. Leak result is a **measured image of a modelled outcome**: torque → `seal_holds` →
   bubbles → camera. A damaged O-ring at full torque would pass. Not independently falsified.

## Open with the founder — sent 2026-08-04 evening, STILL UNANSWERED as of 2026-08-09

Grading criteria; annexure scans; 45-vs-80 PSI; CAD (bowl/cap/O-ring); and the one that can
invalidate work: **does "cleans the filter with a solution" mean the v4 cartridge dip or v5
cabinet cleaning?** Plus, added by V6: **manual cycle time and daily refurb volume** —
without them no speedup claim has a denominator. He has also **not watched the v6 video**.

## Next steps, ranked (see `meetings/anirudh_feedback_2026-08-08.md` for the reasoning)

1. **CONTINUOUS-STROKE CLEANING.** The arm stops at all 323 raster points; 0.40 s of each
   0.52 s stop is two `wipe_stall_s` windows. **Our V6 feed sweep tested "move faster
   between stops" and wrongly concluded the lever was dead — it never tested "stop
   stopping."** One continuous stroke per row ≈ 2× on 81% of the cycle AND fixes the
   "looks robotic" critique. Needs continuous force control along a path (what the ACF
   is for) instead of per-point stall detection. **Top technical item.**
2. **Finish the arm-count trade study** (A single / B two xArm7 / C fixed passive stations)
   **with YAM as option D** ($3–5K, 2–4 kg, no published repeatability). Geometry for C is
   banked in V5_PLAN: an overhead pad needs its own spindle (dead zone at the rotation
   axis), and a *box* on a turntable swings 64 mm in/out against a 30 mm flange stroke.
3. **VLM on TRIAGE only** — measurable against a real 97.5% baseline, and it de-risks the
   "do operators grade by feel?" question. Defer VLA-for-motion until real hardware.
4. If the founder stays silent, consider building the **v4-style solution dip** as a hedge —
   it is closer to the funding bar's literal wording than anything in v5.

## Traps that will bite you first

- Any bare `--eval` overwrites a committed baseline. Every default `--seed0` reproduces its
  published number. **Seed ledger: next free 1900+.**
- **Never** raise `CleanConfig.speed` — 9.6% at best, and the contact model goes
  non-monotonic (108 N through a 45 N ceiling at speed 1.5/2.0, clean again at 3.0/4.0).
- **Never** shorten the 1.2 s indexer dwell. Angle-arrived ≠ settled; a 4 s "saving" broke
  coverage in BOTH modes and cost most of a session to find.
- Adding any free body? Set its qpos from `m.qpos0` in the **same commit** — `v5home`
  predates them and `mj_resetDataKeyframe` spawns them at the origin. (Happened 3×.)
- Never materialise/teleport geometry into space the gripper currently occupies.
- `v5_video` render paths may only **add frame callbacks**. A duplicated physics loop has
  rotted and silently filmed a stale system **twice**.
- Never text-extract the QC PDFs — render them.
- `venv` is gitignored; rebuild with `./setup.sh` (Python 3.9 has no MuJoCo wheel).
