# VLM vs HSV on TRIAGE — a paired, blind comparison  **[demo]**

*2026-08-09. Reproduce: `sim_poc/v5_vlm_triage.py`. Artifact:
`sim_poc/stats_v5_vlm_triage.json` (carries every unit's truth, both predictions and the
ground-truth defect counts, so the table below is auditable line by line).*

## Why this and not a VLA for motion

Anirudh's second point was "don't rely on scripted policies, look at VLAs / π0". The
assessment in `meetings/anirudh_feedback_2026-08-08.md` accepted the direction and aimed
it: replacing a **measured 10/10 insertion** with a learned policy on a task where the
geometry already works is a downgrade, but **triage is hand-tuned HSV thresholds at 97.5%,
it is brittle, and it has an open question behind it — do DrinkPrime's operators grade by
eye or by feel?** So triage is where a vision model has something to prove, and where a
real baseline already exists to prove it against. This is that measurement.

## Three honesty labels that must travel with every number here

1. **This is Claude-as-VLM reading rendered PNGs in a conversation. It is NOT a deployed
   vision-language model.** No API call, no latency figure, no cost figure, no
   repeatability figure — the same grader run twice could differ and we have not measured
   that. Treat it as an *indication* of what a strong general VLM might do on this exact
   imagery, measured once.
2. **The class boundaries are OURS, not DrinkPrime's.** No document in their set defines
   Easy/Medium/Hard. Both graders are scored against a rubric we invented. The comparison
   between them is fair; the absolute numbers inherit that caveat. Hence **[demo]**.
3. **The images are simulated.** Real cabinets have specular highlights, print, stickers
   and uneven wear our renderer does not produce. A VLM's real-world advantage could be
   larger (it has seen actual scuffs) or smaller (our defects are unnaturally uniform in
   colour, which flatters a threshold).

## Method — and why it was run blind

40 fresh held-out units, **seeds 1960–1999**, paired: the same unit, the same rendered
frames, the same rubric, scored with the same asymmetric metrics `v5_triage.report` uses.
The two graders differ in exactly one thing — what reads the pixels.

**The blinding is not ceremony.** Claude wrote the harness and can read
`v5_triage.sample_condition`, so an un-blinded run would measure whether the grader
peeked, not whether it can see. So: images were written to `u00.png … u39.png` in
**shuffled** order under indices carrying no seed and no class; the answer key went to a
separate file; the render loop was changed to print **the index only**, never the seed;
and the grades were committed to `vlm.json` **before** the key was opened. The commit
order in git is the audit trail.

Each image is the four index views (0°/90°/180°/270°) the HSV pipeline already consumes,
cropped to the device using the *same* face regions, so neither grader sees a region the
other cannot — only at a sensible scale.

## Results — 40 paired units

| metric | HSV baseline | Claude-as-VLM |
|---|---|---|
| accuracy | **97.5%** | **97.5%** |
| **MISSED-HARD** ← the headline | **0.0%** (0/14) | **7.1%** (1/14) |
| false-easy | 3.6% (1/28) | **0.0%** (0/28) |
| over-treatment | 0.0% | 0.0% |

### Per class

| class | n | HSV recall | VLM recall |
|---|---|---|---|
| easy | 12 | 100.0% | 100.0% |
| medium | 14 | 92.9% | **100.0%** |
| hard | 14 | **100.0%** | 92.9% |

### Confusion

| | → easy | → medium | → hard |
|---|---|---|---|
| **HSV** easy | 12 | 0 | 0 |
| **HSV** medium | 1 | 13 | 0 |
| **HSV** hard | 0 | 0 | 14 |
| **VLM** easy | 12 | 0 | 0 |
| **VLM** medium | 0 | 14 | 0 |
| **VLM** hard | 0 | 1 | 13 |

### The only two disagreements, in full

| unit | truth | HSV | VLM | who was right | ground truth counts |
|---|---|---|---|---|---|
| seed 1994 | medium | **easy** | medium | VLM | 1 dent, 9 scratches, 13 soil |
| seed 1978 | hard | hard | **medium** | HSV | 6 dents, 22 scratches, 20 soil |

**Both disagreements are on band edges.** Seed 1994 has exactly 9 scratches — the bottom
of the medium band (9–22). Seed 1978 has exactly 6 dents — the bottom of the hard band
(6–18) — with 22 scratches, the very top of medium's range. These are the two hardest
units in the set, and each grader failed one of them.

## Where each wins — the honest paragraph

**On the number everyone quotes they are identical, and that number is not the point.**
Both graded 39 of 40 correctly. With two discordant pairs split one each way, there is no
statistical evidence whatsoever of a difference in accuracy (McNemar, p = 1.0), and this
run **cannot** distinguish a 0% missed-hard rate from about 20% — the 95% upper bound on
0/14 is roughly 3/14. Anyone quoting "the VLM matched our classifier" from n=40 is
overreading it.

**What the run does show is that the two fail in opposite directions, and the directions
are not equally bad.** The HSV thresholds erred *toward more work*: they sent a medium
unit down the easy route — a **false-easy**, a unit released with scratches nobody
addressed. The VLM erred *toward less work*: it graded a genuinely hard unit as medium — a
**missed-hard**, a unit with six dents pushed back onto the line when no downstream stage
can remedy dents. **On this project's own ranking of errors, that is the worse failure**,
and it is the metric we have always led with. So on a strict reading of the headline
metric, the hand-tuned thresholds win this round.

That reading should be held loosely for two reasons. First, one unit. Second, the failure
is legible: the VLM's miss was a unit sitting exactly on the dent boundary we invented,
and while grading it the counting was recorded as genuinely borderline. A threshold has no
such notion — it is decisive on principle, which is why it is both reliable near the
middle of a band and unimprovable near its edge.

**Where the VLM has the structural advantage is the thing this experiment could not
test.** The HSV classifier's 97.5% is 97.5% *on defects we generated as coloured decals in
a scene we built*. Its thresholds were fitted to those decals. Nothing in that number
survives contact with a real cabinet — a printed logo, a sticker edge, a specular
highlight on a scuff — whereas a general vision model has seen scuffed white plastic
before. **The honest conclusion is not "the VLM is as good"; it is that on synthetic
imagery a general model matches a hand-fitted classifier without being fitted to anything,
which is precisely the property that might survive the move to real photographs.** That is
worth a follow-up on real images and worth nothing without one.

**And it does not touch the open question underneath.** If DrinkPrime's operators grade a
cabinet partly by *feel*, camera-only triage is the wrong architecture and both graders are
measuring the wrong thing equally well. That question has been outstanding since
2026-08-04.

## Seeds

**1960–1999 are now spent** (40 units, this comparison). **Seed 1950 is separately burned** —
a render probe printed its truth to the session transcript before the protocol was in
place, which is exactly the leak the blinding was designed to prevent, caught early enough
to cost one seed. Ledger in `CLAUDE.md`.
