# Results

**Headline: 100% success across 200 randomized trials, up from 88%.**
Peak part tilt during insertion dropped from a median of 21° to 4°.

All numbers below were produced on **MuJoCo 3.11.0 / numpy 2.5.1 / Python 3.12.13**
(see [requirements.txt](requirements.txt) — the version matters, explained at the bottom).

---

## Before → after

| | Original | Fixed |
|---|---|---|
| Seeds 0–24 (the set the original was tuned on) | **88%** (fails 14, 18, 21) | **100%** |
| Seeds 25–74 (held out) | **72%** (14 failures) | **100%** |
| Seeds 25–99 (held out, 75 trials) | — | **100%** |
| Seeds 100–199 (never seen during tuning) | — | **100%** |
| Peak cartridge tilt during insert — median | 20.7° | **4.2°** |
| Peak cartridge tilt during insert — worst case | 49.1° (60.7° on held-out) | **9.5°** |
| Mean seating accuracy | 2.12 mm | **1.69 mm** |
| Cycle time | 18.1 s | 22.8 s |

**Total: 200/200 trials locked.** Held-out performance equals in-sample performance,
which is the opposite of the overfitting signature — a change that only worked on the
seeds it was tuned against would show a gap here.

Two things worth being blunt about:

- **The original was worse than it looked.** Its published 88% was measured on seeds
  0–24, the same seeds it had been developed against. On 50 seeds it had never seen,
  it scored **72%**. The "84%" in the original write-up was a still older run on a
  different MuJoCo version.
- **Speed got worse.** Cycle time rose from 18.1 s to ~23 s, about 27%. That is a real
  cost, paid for reliability: the insertion descent is now rate-limited instead of
  being commanded as one large step. If cycle time ever becomes the binding
  constraint on a real line, this is the first place to look.

---

## What was actually wrong

The original scored 84–88% and the four failing seeds looked like four unlucky edge
cases. They weren't. Measuring *how far the part tilted* during insertion — rather
than just pass/fail — showed that **every single trial was jamming.** The typical
"successful" run still tilted ~21°, ground against the chamfer, and eventually
wobbled free. The failures were simply the tail past ~40° that never recovered.

The true description was **"100% jam rate with an 84% recovery rate"** — same score,
completely different problem.

### Root cause: two integrators winding up against contact

**1. Lateral.** The insert steering law was

```python
tgt_arr[:2] = data.site_xpos[site_id][:2] + (SOCK - cart_xy)
```

which recomputes the wrist target as *(where the wrist is now) + (how far the part is
off)* on every step. When the part is jammed in the funnel and physically cannot move,
that error never shrinks — so the wrist keeps walking sideways, step after step, with
no bound. It is a positive-feedback integrator running against a contact constraint,
and it torques the gripped part until it wedges.

**2. Vertical.** INSERT commanded an absolute 64 mm downward step in one go. The IK
clips joint velocity *element-wise*, so a target that far away saturates the clip —
which (a) consumes the entire joint-rate budget on the descent, leaving nothing for
lateral or rotational correction, and (b) distorts the direction in joint space, so
the tool does not actually travel straight down. Measured: ~19 mm of lateral drift in
the first second of insertion.

### And the failure was invisible to the controller

INSERT declared itself complete on **wrist height alone** (`tcp_z < 0.129`). A wedged
part still lets the wrist descend past it, so jams reported *success*. The problem was
only noticed two phases later at DROP-SEAT, where the part failed to fall — and
DROP-SEAT had no retry path, so it aborted instantly. Seed 21 died with **0 of its 2
retries used.**

---

## The four fixes

| # | Fix | Effect |
|---|---|---|
| 1 | **Steer by the part's tip, not its centre**, with a bounded vertical feed lead and a direction-preserving rate limit | Prevents the wedge. Tilt 20.7° → 4.2° |
| 2 | **INSERT must judge the part** (upright *and* actually down in the bore), not just wrist height | Turns silent jams into honest timeouts |
| 3 | **Retry from DROP-SEAT too**, via a re-grip + lift-clear recovery | Recovers jams that do happen |
| 4 | **Continuous dwell for INSERT** — the completion condition must hold without interruption | Stops a bouncing wrist from certifying a state it never reached |

**Fix 1 — why the tip.** When a gripped part tilts, its *centre* swings sideways. A
controller that follows the centre therefore chases the tilt and amplifies it. The
part's bottom face is the thing actually inside the funnel, so that is what the wrist
should hang plumb over. The in-jaw offset is latched once at entry rather than
re-measured every step, so grip eccentricity doesn't get chased either.

**Fix 3 — why it needed a recovery phase.** The old retry jumped straight back to
ORIENT LUGS, whose target is 110 mm higher — so the arm ascended while the part might
still be hooked under the collar rim. Worse, when the retry came from DROP-SEAT the
gripper was *open*, so it went back to "orient the lugs" holding nothing. The new path
re-grips where the part actually is (a wedged part sits 20–35 mm off-axis), lifts
clear, and only then re-approaches.

**Fix 4 — scoped deliberately.** Applied to every phase, this rule **drops the success
rate to 4%** and is left in the code as a comment explaining why. ORIENT LUGS and
PRE-INSERT gate on a part still swinging like a pendulum; for them the *cumulative*
dwell is the correct semantic, because it accumulates evidence that the swing is
decaying. Only INSERT was certifying a settled state it had never actually reached.

### Each fix was measured independently

Rather than assume the fixes were all pulling their weight, the controller was
re-broken to isolate them. With the original wedging dynamics restored but fixes 2–4
left in place: **88% → 92%**, seed 18 rescued, and the retry counter rose from 2 to 3
as the new DROP-SEAT retry fired for the first time. So fixes 2–4 genuinely recover
from jams; fix 1 is what prevents them. Together they reach 100%, and on held-out
seeds the retry net still fires ~11 times per 175 trials and recovers every one — it
is load-bearing, not decoration.

---

## How this was verified

- **Held-out seeds.** Tuned on 0–24, validated on 175 seeds never used for tuning.
- **Independent adversarial review.** Eight control strategies were explored in
  parallel; the four that reached 100% were each handed to a separate reviewer whose
  explicit job was to *refute* the result — re-deriving the patch from a prose
  description, re-running it, and checking for metric gaming. None were refuted.
- **Anti-gaming checks.** The success criteria at the end of `run_trial`
  (`xy_off < 0.006`, `upright > 0.95`, `rel_twist > 30°`) are byte-identical to the
  original, as are `evaluate()` and the CLI. No seed is special-cased. The part was
  confirmed to be genuinely gripped and lifted (contact pairs checked), not dragged.
  Note the insertion entry tolerance was made **tighter** (2.5 mm → 1.5 mm), not looser.

## Reproducibility warning

The original 84% is **not reproducible** and neither, strictly, is this 100%. Running
the *unmodified* original code on MuJoCo 3.11 gives 88%, not 84% — and seed 12 flips
from failure to success with no code change at all. Contact-rich physics is sensitive
to solver details that change between engine versions.

This is why `requirements.txt` is pinned. **A success rate quoted without an engine
version is not a reproducible claim.** If you bump MuJoCo, re-run `--eval` and expect
the number to move.
