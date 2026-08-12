# Pad path-following metric — design, validation, and what the validation caught

Task: *"add a metric that reports how well the pad follows its commanded path during a
stroke, and report it in the run row."*

Everything below was measured on this machine. Where I did not run something, I say the
exact command and what I expect.

---

## 0. The first finding: a metric with this name already exists, and it answers a different question

Before writing anything I checked whether the number was already there. It largely is:

- `Cell.stroke_track` (`sim_poc/v5_clean.py:1580`) accumulates a per-step in-plane
  deviation and surfaces as `stroke_track_med_mm`, `stroke_track_p99_mm` and
  `stroke_inplane_err_mm` in the run row, printed by `report()` as *"IN-PLANE departure
  from the commanded path"*.
- That is where CLAUDE.md's *"worst in-plane tracking error is 15.2 mm at every feed"*
  comes from. I reproduced it exactly: seed 1920 gives `stroke_inplane_err_mm = 15.2019`.

So the useful move was **not** to build a duplicate. It was to find what the existing
number cannot say, and to fill in the actual gap.

**The existing metric measures the pad against the geometric raster polyline.** It is a
*coverage* statement — "did the pad sweep the ground the raster claims?" — and
`_catmull`'s own docstring says it deliberately **includes** the spline's bow off the
chord between knots (`v5_clean.py:1313`: *"That bow is measured, not assumed — see
stroke_path_error_mm in the run row"*).

The user asked how well the pad follows its **commanded** path. The commanded path is not
the polyline. The two decompose:

```
pad − polyline  =  (pad − commanded pad)  +  (commanded pad − polyline)
                        servo error            spline bow + discretisation
```

Today one number carries both, and **they have different owners**: the first is a
controller/feed problem, the second is a path-geometry problem. When the number moves you
cannot tell which knob to reach for. That is the real gap, and it is what I built.

Second, smaller gap: the loop samples once per **control step** while the pad's speed
varies ~50× along a run (the velocity plan drops to 8% of feed at a corner; `v_min` is 2%
of feed). So the published median is a median over **time**, and it over-weights exactly
the slow corners where deviation is worst. Coverage is a statement about **distance**.

---

## 1. What I implemented

All in `/Users/pranavmulakala/WaterFilterRobo/sim_poc/v5_clean.py`.

**`Cell._cmd_pad_pos()`** — forward kinematics of the *commanded* configuration `q_des`,
on a fourth scratch `MjData` (`self.fk`).

There is a trap here that produces a plausible-looking wrong number, and I want it on the
record because it is the project's recurring one: **you cannot read the pad geom out of
the scratch data after `mj_kinematics`.** The pad is a free body welded to the wrist by
the `toollock` equality, and `mj_kinematics` does not solve equalities — FK on a copied
qpos leaves the pad exactly where it already was, so the metric would read ~0 mm no matter
how far the arm lagged. That is the keyframe/free-body trap CLAUDE.md records having bitten
four times.

Instead I compose: take the pad's **measured** offset in the live TCP frame and re-apply it
to the **commanded** TCP frame. Holding that offset fixed between the two cancels flange
compression and coupling drift — which are measured separately and are not servo error —
leaving exactly the wrist's pose error mapped out to the pad.

**The three-way decomposition** (this is the part the validation forced — see §3):

| component | what it is | is it an error? |
|---|---|---|
| **normal** (`n̂`) | the active contact flange compressing | No — spoken for by the measured force band |
| **along-path** (`t̂`) | **lag**: how far behind its setpoint the arm runs | **No** — the pad sweeps the same ground, later |
| **cross-path** | pad pushed sideways off its own commanded track | **Yes** — this is the headline servo number |

`t̂` is orthogonalised against `n̂` before use: the row lies in the face, but the normal is
sampled per knot and the two are only *nearly* perpendicular. Without that step, flange
travel leaks into the lag term.

**New run-row fields:** `stroke_servo_med_mm`, `stroke_servo_p99_mm`, `stroke_servo_max_mm`
(cross-path); `stroke_servo_lag_med_mm`, `stroke_servo_lag_max_mm`;
`stroke_servo_norm_mm`; and distance-weighted twins `stroke_servo_{med,p99}_dw_mm`,
`stroke_track_{med,p99}_dw_mm`.

**The published numbers are not redefined.** `stroke_track_med_mm` / `_p99_mm` /
`stroke_inplane_err_mm` keep their exact old meaning and values. The distance-weighted
versions are *added alongside*, and the gap between them is itself the evidence that the
weighting matters. Silently moving a published number would have been the worse bug.

**Reported in the run row** — both senses of "run row":

```
  seed 1920: cov 100.0%  picked=True  fmax 22.6 N  path  2.8/15.2 mm med/max  servo-cross 2.45/26.21  lag 39.7 mm
```

Per-unit rather than aggregate-only on purpose: `report()` prints a mean-of-medians and a
max, which cannot show one unit tracking badly while the rest are fine.

**Config:** `CleanConfig.stroke_servo_metric = True`. On by default — a metric that is off
by default is a metric nobody reads — which is safe *because* of §2.

---

## 2. Validating that the metric itself is correct

This is the part I care most about, because a tracking metric that reads a plausible number
for the wrong reason is worse than no metric.

### 2a. It must not change the physics — **PASSED, and this is the strongest single check**

Adding per-step computation is only safe if the trajectory is bit-for-bit unchanged.
Measured, not assumed: ran seed 1920 before and after and diffed the run row field by field.

```
../venv/bin/python v5_clean.py --run 1920 --stroke
```

**All 33 pre-existing fields identical to the last digit** — `f_max
22.621835834021553`, `coverage 1.0`, `stroke_inplane_err_mm 15.201925165371543`,
`tcp_speed_max 1.0074493325796927`, `tilt_mean 8.4640522875817`, etc. 8 new fields added.
Cost: 29.63 s → 31.23 s wall clock, **+5.4%**, and **zero** simulated seconds (the cycle
clock is charged from simulated `t`, so no published cycle-time number can move).

### 2b. Arithmetic self-tests — **PASSED**

Synthetic vectors with known parts, no physics: built an error vector with normal 5,
along-path 13, cross-path 7, using a tangent deliberately **not** perpendicular to the
normal (the real case). The split recovers 5.000000 / 13.000000 / 7.000000 exactly, and
the three parts reconstruct the vector to 1e-9 (Pythagoras).

`_wpct` checked against a hand-computable case (value 1 carrying 90% of the distance,
value 100 carrying 10% → weighted median must be 1, p99 must be 100), against numpy at
equal weights (agrees to <0.01 on 5000 samples), and on degenerate inputs (empty list,
zero total weight) so it returns a number instead of crashing an eval at unit 14.

### 2c. Non-degeneracy — **PASSED**

Reads 2.45 mm median / 26.21 mm worst cross-path, 17.6 / 39.7 mm lag. Not zero (which
would mean the free-body trap), not absurd. Servo normal 25.6 mm sits right next to the
independently-computed `stroke_flange_mm` 26.8 mm, which is a useful cross-check that the
frames are right.

### 2d. Subclass survival — **PASSED**

`MemCell` and `RouteCell` override `reset()` and never call `Cell.reset()`. That is exactly
how the `tcp_speed_max` metric crashed on its first re-validation, so the accumulators are
initialised in `__init__`. Verified both construct and reset with the attributes present.

### 2e. Gates — **PASSED**

`v5_check_scene.py` ALL PASS; `v5_check_spec.py` ALL 50 VALUES MATCH. Point mode
(`--run 900`) still gives `f_max 23.925980963125905` — CLAUDE.md's published 23.93 N —
with all stroke fields zero. `git status` shows **only `v5_clean.py` modified; no stats
file touched.**

### 2f. Falsification: does it respond to the thing that causes servo error?

A metric that never moves is not evidence. Two independent knobs, **predictions registered
in the script docstrings before running**.

**Test 1 — `max_follow_err`**, the constant CLAUDE.md names as what actually bounds joint
speed. Stayed above 0.15 rad (force cliff is at 0.14). Seed 1920:

| max_follow_err | servo cross med/max | **lag med/max** | raster-path med/max | coverage |
|---|---|---|---|---|
| 0.18 | 2.67 / 29.88 | 18.48 / 41.14 | 3.47 / 20.53 | 100% |
| **0.25 (shipping)** | 2.45 / 26.21 | 17.65 / **39.70** | 2.83 / 15.20 | 100% |
| 0.40 | 2.76 / 31.33 | 18.40 / **67.43** | 3.66 / 22.25 | **75%** |

**Test 2 — `stroke_feed`.** My registered prediction: median lag = servo response time ×
feed, so lag/feed should be constant.

| stroke_feed | lag med/max | lag/feed | servo cross med/max | raster-path med |
|---|---|---|---|---|
| 0.10 | 13.89 / **26.12** | 138.9 ms | 2.00 / 23.21 | 2.60 |
| **0.20 (shipping)** | 17.65 / **39.70** | 88.2 ms | 2.45 / 26.21 | 2.83 |
| 0.30 | 16.93 / **50.20** | 56.4 ms | 2.60 / 26.30 | 2.96 |

**Result: half confirmed, and my prediction was refuted.** Reporting both.

- **Confirmed:** the metric is not a constant. Worst lag moves sharply and monotonically
  on *both* knobs — 39.7 → 67.4 mm loosening the clamp, 26.1 → 50.2 mm across the feed
  range. It responds to the servo.
- **Refuted:** lag/feed is 138.9 / 88.2 / 56.4 ms — **not** constant. Median lag is
  essentially flat across every condition tested (13.9–18.5 mm). My mechanism was wrong.
- **Also not confirmed:** tightening 0.25 → 0.18 did **not** reduce lag (41.1 vs 39.7).
  So the clamp binds only in the tail.

I have a hypothesis for the flat median — the stroke loop deliberately backs off the *arc
advance* when a step would demand more joint travel than the rate limit allows
(`ds *= lim/mx`), which stops the setpoint outrunning the arm, so lag saturates. **I did
not verify it**, and I have written into `report()` that the median's mechanism is not
explained and must not be quoted. What would test it: log how often that branch fires per
run and correlate with lag; if it fires on most steps at 0.30 and rarely at 0.10, that is
the mechanism.

---

## 3. The validation caught a real defect in my own metric — this is the main result

**My first implementation was wrong**, and the byte-identity check would never have found
it. It projected out only the surface normal and reported the rest as "in-plane servo
error". It read **18.46 mm median** against a 2.83 mm raster-path error.

A servo error six times the path error is not credible, and chasing it found the cause:
that number was almost entirely **along-path lag** — the setpoint legitimately running
ahead of the arm. The pad was not off the face; it was *behind*, on the same line.

This is precisely the mistake the existing metric already documents having made and fixed
one level down (`v5_clean.py:1421`): *"The first version measured [distance to the nearest
knot] and read 40 mm, almost all of which was the 36 mm segment length plus the arm's
along-path lag — neither of which is an error."* I made the same class of error one frame
over. The existing metric dodges it structurally by measuring distance to the *polyline*,
which removes along-path by construction; measuring against a *pose* does not get that for
free.

After the fix: cross-path **2.45 mm** median / 26.21 mm worst, lag reported separately at
17.6 / 39.7 mm. **The 18.46 mm I would have shipped as "servo tracking error" was 86%
an artefact of my own frame choice.**

The lesson worth keeping: *a tracking number is only meaningful once you say which
direction you subtracted, and "in-plane" is not specific enough on a curved swept path —
in-plane still contains the direction of travel.*

---

## 4. A substantive finding that falls out of the new number

CLAUDE.md's headline post-clamp result is that tracking is **feed-independent** — "the same
15.2 mm at every feed" — and that identity is called *the* finding, the reason feed was
doubled to 0.20.

That claim is **true of the quantity it measures**, and my data agrees: raster-path median
is 2.60 / 2.83 / 2.96 mm across 0.10 → 0.30, and cross-path servo is 2.00 / 2.45 / 2.60 mm.
Flat.

But **worst along-path lag is not feed-independent: 26.1 → 39.7 → 50.2 mm, roughly
doubling over the same range.** The existing metric cannot see this, because it projects
along-path out by construction.

This does **not** overturn the feed decision — lag genuinely costs no coverage, which is
what the decision rested on. But it means the claim should be stated more precisely:
*cross-path tracking is feed-independent; along-path lag is not.* That distinction matters
for the real cell, because lag is how **stale** the commanded pose is: it bounds where the
arm actually is when a stroke ends or is interrupted, and it is the number that would bite
if anything is ever closed on the commanded pose. Caveat: **n = 1 seed, 3 points.** Do not
quote it as a result until §5 is run.

---

## 5. What I did NOT run, and would (exact commands)

Per the time box, no multi-unit evals and no stats-file writes.

```bash
cd ~/WaterFilterRobo/sim_poc

# 1. Re-verify the published 16-unit stroke number is untouched.
../venv/bin/python v5_clean.py --eval 16 --stroke --seed0 1920
```
Expect coverage 100%, **0 missed of 273**, peak 22.04 N — byte-identical on every
pre-existing key. `stats_v5_clean_stroke.json` **will** show a diff: it gains the new
`stroke_servo_*` and `*_dw_mm` keys. That is an additive schema change, not a broken one,
but it must be eyeballed key-by-key before committing.

```bash
# 2. Confirm the point-mode baseline (protected).
../venv/bin/python v5_clean.py --eval 8
```
Expect 100% coverage, 0 missed of 129, peak 23.93 N, and stroke fields at zero.

```bash
# 3. Sabotage battery unchanged (the metric must not touch verification).
../venv/bin/python v5_clean.py --sabotage 10 --stroke --seed0 1940
```
Expect 10/10 caught, 0/10 false verifies.

Baselines `sim_poc2/3/4` are **not** required: nothing outside the v5 chain imports
`v5_clean`, and I confirmed the importers (`v5_membrane`, `v5_route`, `v5_video`)
construct and reset cleanly.

To turn §4 into a result rather than an observation: sweep feed × 4 fresh seeds from
**2200+** (next free block per the ledger) recording `stroke_servo_lag_max_mm`, and
allocate the block by named phase in CLAUDE.md's ledger before spending it.

---

## 6. Concerns

1. **The lag median is unexplained.** Stated as unexplained in `report()` rather than
   given a mechanism. My hypothesis is in §2f along with the test that would settle it.
2. **All physics evidence is n = 1 seed (1920).** Correct for the byte-identity check
   (the cleaning trajectory is open-loop and seed-independent, so one unit gives the exact
   answer), but the falsification tables are one seed and should not be quoted as spreads.
   `report()` already prints this warning for force/tilt/raster; it applies here too.
3. **Seed hygiene.** 1920 is already published *and* rendered, so an instrumentation
   determinism check on it makes no accuracy claim and consumes no held-out seed. Nothing
   fresh was spent. Seed 9000 (calibration range) was used for the subclass check.
3. **`report()` is getting long.** The stroke block is now ~20 lines of prose. Justified —
   every line prevents a specific misreading — but it is approaching the point where it
   should be a `--explain` flag with a terse default.
4. **The metric is honest about the arm, not about the cream.** It says where the pad
   *was*. CLAUDE.md's standing caveat still applies unchanged: the model removes soil on
   **contact, not dwell**, so nothing here tells you whether a rub was too brief.
5. **Not yet documented.** Per the standing rule, this change should append a
   ≤15-line plain-English `LEARNINGS.md` entry (the concept: *the difference between
   "did the robot go where the map said" and "did the robot go where you told it", and why
   lag along a path is free while lag across it is not*) and a `PAIN_JOURNAL.md` entry for
   the free-body FK trap in §1 and the frame error in §3. I did not write them because the
   task did not ask for docs; they are the next commit.

---

## 7. Recommendation

**Ship it, default on.** It costs 5.4% wall clock, zero simulated seconds, and the
trajectory is proven byte-identical.

Lead with **cross-path servo error (2.45 mm median / 26.2 mm worst on seed 1920)** as the
"how well does the pad follow its commanded path" number, always printed next to the
existing raster-path number, never instead of it. The pair is the point: when they diverge
you know whether to look at the controller or at the path geometry.

Report **along-path lag separately and explicitly labelled "not a coverage error"**. It is
the most interesting new number here — it is the only one that is not feed-independent —
but presenting it as tracking error would repeat exactly the mistake §3 describes.

Do not tune anything on these numbers yet. The falsification told me the metric responds;
it did not tell me it is calibrated, and one of my two registered predictions was refuted.
Run §5 first.
