# Advisor feedback — Anirudh, San Francisco, 2026-08-08

**PROVENANCE: SECONDHAND.** Pranav's manager met Anirudh in person; this is Pranav's
relay of the manager's account. No transcript, no recording, no direct contact. Treat
every line as paraphrase, exactly as `PROJECT_CONTEXT.md` treats founder claims.
**Anirudh stated he does not know how DrinkPrime's refurbishment process actually works** —
he is a robotics advisor, not a source of truth on their line.

## What he said (three points)

1. **Look at YAM arms; consider two arms at a station.**
2. **Don't rely on Claude-Code-written scripted policies — "hard-coded coordinates."**
   Look into VLAs and π0 (https://www.pi.website/blog/pi0).
3. **The simulation looks robotic and slow** — it should move like a real arm and could be
   much faster.

## Assessment, with the numbers checked (2026-08-09)

### 3 is the most valuable, and it exposed an error of ours

The arm **stops at all 323 raster points**; each stop costs ~0.52 s of which **0.40 s is two
mandatory `wipe_stall_s` windows**. It looks like pecking because it is pecking.

**Our V6 feed-rate sweep answered the wrong question.** It tested *moving faster between
stops* (9.6%, and the contact model destabilised at speed 1.5/2.0) and concluded "dead
lever". It never tested **not stopping**. A row is ~7 points x 36 mm ~ 250 mm, currently
~3.6 s; as one continuous stroke at 150 mm/s it is ~1.7 s. **~2x on the 81% of the cycle
that is cleaning, and it fixes the appearance — one job, both complaints.**
Requires continuous force control along a path instead of per-point stall detection; that
is what the ACF was put in for. THIS IS THE TOP TECHNICAL NEXT STEP.

### 1 is the right instinct, wrong phase — and deserves a measurement, not a rebuttal

YAM (I2RT), verified 2026-08-09: **$2,999–$4,999**, 6-DoF, **2–4 kg payload**, 780 mm reach,
CAN bus, marketed for *"real-world research and embodied AI data collection."*
**No published repeatability** — normal for a research arm, and the absence is the signal:
industrial arms always publish it.

- Our measured peak wipe force is **32.9 N (~3.4 kg equivalent)**, at or above a standard
  YAM's 2 kg nominal. YAM Ultra (4 kg) would be the minimum candidate.
- 2,000 units/day is continuous industrial duty; a research arm is not sold for that.
- **BUT the cost arithmetic genuinely changes the answer:** ~4 YAMs = 1 xArm7 ($11K). Our
  measured split (clean 118 s vs membrane 46 s) makes a 2-arm pipeline worth ~1.4x, not 2x
  — but at a quarter of the price that may still win on cost-per-unit-throughput.

**Action: finish the arm-count trade study (A/B/C, unfinished) with YAM as option D.**
Answer the two-arm question with numbers rather than explaining our topology.

> **DONE 2026-08-09 — `TRADE_STUDY.md`. Two numbers on this page are superseded by it.**
> The **~1.4×** above came from the clean-vs-membrane split alone; with load/triage/verify
> overheads and the class mix averaged in — and with V7's faster clean — a 2-arm pipeline
> is worth **1.13×**. Neither figure is wrong for what it computed. And the framing turned
> out to matter less than the volume: **one cell already does ~328 units/day against an
> estimated 130–200 need**, so the arm-count question is moot in the expected range. The
> YAM cost arithmetic survives intact but never changes the cell count — it is the same
> cell with a cheaper arm, behind a decision rule fixed before his answer arrives.

*Does he know we do everything at one station?* Probably not in detail — and it barely
matters: two of his three points are topology-independent, and "two arms" is a sensible
prior for any cell with one long station and one short one, which is exactly our imbalance.

### 2 is directionally right; the prescription needs aiming

Fair part: ours is a **scripted policy**. Not literally hard-coded (we ray-cast surfaces per
point and close the loop on the MEASURED part pose), but it will not survive a different
device or an unmodelled variation.

Where the specific recommendation needs care: π0's demonstrated domain is **laundry folding,
table bussing, grocery bagging, box assembly** — unstructured, high-tolerance, household.
Ours is a fixtured station doing **1.5 mm clearance insertion** and force-controlled wiping
to a coverage spec. Replacing a measured 10/10 insertion with a learned policy on a task
where geometry already works is a downgrade. π0's own post calls generalist policies
*"still in their infancy"*, robustness a frontier. Its 8 training platforms (UR5e, Franka,
Trossen, ARX, Fibocom...) include **neither xArm7 nor YAM** — a platform gap on top of the
sim-to-real gap.

**Where a VLA genuinely earns its place here:**
- **TRIAGE grading** — currently hand-tuned HSV thresholds at 97.5%, brittle, and we have an
  open question about whether operators grade by *feel*. Strongest VLA case in the project,
  already in the backlog. Cheap, and measurable against a real baseline.
- **TEARDOWN** — there is **no disassembly work instruction anywhere in the 13 documents**.
  Unstructured and undocumented: exactly where scripting fails and learning wins.

**The bridge already exists:** `sim_poc/lerobot_export.py` writes LeRobot v2.1 datasets from
this cell. The scripted controller is the DATA GENERATOR for any learned policy — they are
not competitors. Caveats: successful episodes only (no recovery demos) and never
round-tripped through the real library.

## What none of this feedback touches

Every point is about HOW we build. **None asks whether we are building the right thing.**
The funding bar says *"cleans the filter with a solution"*; v5 CLEAN is a **dry wipe of the
cabinet exterior**; nobody has confirmed which was meant. As of 2026-08-09 the founder has
**not watched the v6 video** and has **not answered** the four questions sent 2026-08-04.
That is the real risk — not arm choice, not VLA.
