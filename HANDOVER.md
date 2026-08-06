# HANDOVER — state as of 2026-08-05 (V6-speed merged)

**Read `CLAUDE.md` first** (phase table + seed ledger are authoritative). This file is the
five-minute version for whoever picks the project up next.

## Where things stand

| thing | state |
|---|---|
| v2 insert / v3 swap / v4 refurb loop | 100% / 100% / 86.7%, byte-locked baselines |
| v5 TRIAGE | 97.5%, missed-hard 0.0% |
| v5 CLEAN (full coverage, **default**) | 100% coverage, 0 missed, peak 32.9 N, 186.8 s |
| **V6 targeted clean (opt-in)** | **0/24 residue fresh**, sabotage caught 15/15, ~75–120 s |
| v5 MEMBRANE (V6-ARM) | **arm inserts element, places cap (10/10, worst 1.86/4 mm) and holds the driver**; stalls 10/10, sabotage caught 10/10, 0 false pass (1890–99) |
| routing | compliance 28/28, right-route 26/28, **fully backed 22/28** — quote the last |
| **full MEDIUM cycle** | **2:33 median (V6)** / 3:51 (v5 full-coverage) — true-1× videos exist for both |

## The four honesty labels that must travel with any demo

1. Easy/Medium/Hard **names** are DrinkPrime's; the **boundaries are ours** (asked, unanswered).
2. Targeted cleaning's dirt **locations** are ground truth standing in for camera
   localisation; the **residue check is a real camera** and catches sabotage 15/15.
3. Membrane: **the ARM inserts the element, places the cap and holds the driver.** Thread-start *engagement* (4 mm/4° capture) and spindle reaction torque are modelled — the poses are real and enforced.
4. HARD route = software decision, **no physical handoff (0/6)**; bubbles modelled from torque.

## Open with the founder (sent 2026-08-04 evening, unanswered)

Grading criteria; annexure scans; 45-vs-80 PSI; **CAD (bowl/cap/O-ring)**; and the
scope question that can invalidate work: does "cleans the filter with a solution" mean the
cartridge dip (v4) or cabinet cleaning (v5)? **Plus, added by V6: manual cycle time and
daily refurb volume — without them no speedup claim has a denominator.**

## Sub-minute ask: answered

Not on one arm at zero residue (floor ≈ 2:10–2:35; the accuracy machinery IS the time).
2,000/day is a *cell count* problem: 4 cells ≈ 94 units/hr. Arm-count trade study
(A/B/C architectures) is **unfinished** — geometry for C is banked in the session notes;
feed-rate lever is dead (9.6%, and the contact model destabilises at some speeds).

## Traps that will bite you first

- Any bare `--eval` overwrites a committed baseline; every default `--seed0` reproduces
  its published number. Seed ledger: next free **1880+**.
- `stats_v5_route.json` turns figures change with membrane speed; e2e/right-route do not.
- Never text-extract the QC PDFs; render them.
- The contact model is not trusted above 45 N and is non-monotonic vs speed — do not raise
  `CleanConfig.speed`.
- `v5_video` render paths may only add frame callbacks; a duplicated physics loop rotted once.
