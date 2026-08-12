# Does the peak force in `stats_v5_clean.json` still reproduce?

**Short answer: yes — bit-for-bit, to all 16 significant digits. The number is correct.
But I found three reasons it *looks* wrong, one of which is a real defect in the repo, plus
two things you should know that you didn't ask about — including a file being edited
underneath me mid-check.**

---

## 1. The plan

The value in question is `f_max: 23.925980963125905` (point mode, full coverage, seeds
900–907).

Before running anything I wanted to answer three questions in order, because each one can
kill the next:

1. **Is the committed file even what HEAD says it is?** (i.e. no uncommitted drift)
2. **Has the code moved under the stats file since it was last generated?** A number that
   "reproduces" against stale code is not the question worth asking.
3. **Can I reproduce it cheaply enough to fit the time-box?**

Question 3 had a promising answer built into the project. `report()` prints, and CLAUDE.md
repeats, that:

> THE TRAJECTORY IS OPEN-LOOP AND SEED-INDEPENDENT. The raster, the planned poses and the
> contact are identical for every unit; the seed only moves the soil. So force, tilt and
> raster figures above have NO seed variance — they are effectively n = 1.

If that claim is true, then **a single unit determines `f_max` exactly**, and I can test
reproduction without running the 8-unit eval (which would also have overwritten the
committed baseline — forbidden by the constraints and by CLAUDE.md's hard rules). If the
claim is false, the single-unit run would *disagree* with the file, which is itself a
finding. Either way the run is informative, so it was the right first experiment.

---

## 2. What I checked, and what I actually ran

### 2a. The file matches HEAD

```
git status --porcelain          # only `?? .claude/` at session start
git show HEAD:sim_poc/stats_v5_clean.json
```

Byte-identical to the working copy. No uncommitted drift. ✅

### 2b. The code HAS moved under the stats file — and I checked whether it matters

This is the part that nearly made the answer "no".

```
git log --oneline -10 -- sim_poc/v5_clean.py        # last: 5b6d786 (V7.3, HEAD)
git log --oneline -10 -- sim_poc/stats_v5_clean.json # last: 407fd2f (V7.2)
```

**HEAD (V7.3) modified `sim_poc/v5_clean.py` by +94 lines and did *not* regenerate
`stats_v5_clean.json`.** The committed stats file was produced by V7.2 code.

So I read the V7.3 diff rather than assuming. Its hunks are confined to lines 621–826 and
consist of exactly three things:

- a new `_goto()` — drives the arm to a joint target instead of teleporting
- a new `_index_to()` — rotates the indexer under normal limits, with `nearest=True`
- `verify()` changed from `verify()` to `verify(drive=True, frames=None)`

Then the decisive check — who calls the new methods:

```
grep -n "_index_to\|_goto" sim_poc/v5_clean.py
624:    def _goto(...)        # definition
653:    def _index_to(...)    # definition
791, 797, 820:               # all three call sites are inside verify()
```

And the point-mode eval path (`__main__`, `elif a.eval:`) is:

```python
c = Cell(CFGX)
for k in range(a.eval):
    rows.append(c.run(a.seed0 + k))
st = report(rows)
```

**`c.run(seed)` only — `verify()` is never called.** (`verify()` is called from
`run_with_backstop()`, which is the *targeted* mode, and from `falsify()`, which writes
`stats_v5_verify.json`.) So V7.3 is inert for this file's numbers.

That is a conclusion from reading, though — so I still ran it.

### 2c. The reproduction run (what I actually executed)

```
cd sim_poc && ../venv/bin/python v5_clean.py --run 900
```

**36.8 s wall clock.** `--run` prints the row and writes nothing (confirmed in the
`__main__` block and by `git status` afterwards — no stats file was touched).

| field in `stats_v5_clean.json` | committed (n=8) | my `--run 900` (n=1) | |
|---|---|---|---|
| `f_max` | 23.925980963125905 | **23.925980963125905** | ✅ all 16 digits |
| `contact_run` / `contact_planned` | 0.9951518010403972 | 0.9951518010403972 | ✅ |
| `in_band` | 1.0 | 1.0 | ✅ |
| `tilt_mean_deg` | 8.4640522875817 | 8.4640522875817 | ✅ |
| `tilt_max_deg` | 30.0 | 30.0 | ✅ |
| `exact_normal_frac` | 0.3627450980392157 | 0.3627450980392157 | ✅ |
| `tcp_speed_max_mms` | 1005.4303493881895 | 1005.4303493881895 | ✅ |
| `joint_speed_max_rad_s` | 2.4609641242715665 | 2.4609641242715665 | ✅ |
| `raster_planned` | 2584 | 323 × 8 = 2584 | ✅ |
| `raster_infeasible` | 136 | 17 × 8 = 136 | ✅ |
| `coverage` / `missed` | 1.0 / 0 | 1.0 / 0 | ✅ |

Two things worth drawing out:

- **The peak force reproduces exactly, not approximately.** Contact-rich MuJoCo is not
  obliged to do that, so this is a strong result.
- **It also empirically confirms the seed-independence claim** the project has been
  asserting. The 8-unit aggregate equals unit 1 *exactly* on every force/tilt/speed/raster
  field. Only `soil` genuinely varies (seed 900 carries 13 of the 129 patches).

### 2d. Gates

Both pass, and neither writes anything:

- `v5_check_spec.py` → `CELL_SPEC CHECK: ALL 50 VALUES MATCH`
- `v5_check_scene.py` → `V5-A SCENE CHECK: ALL PASS`

(Minor doc drift: CLAUDE.md says `v5_check_spec.py` asserts "all 39 numbers in
`CELL_SPEC.md`". It now asserts 50.)

---

## 3. So why does it look off? Three reasons — one is a real defect

The number is right, so the suspicion is worth explaining rather than dismissing.

### (i) There is a stale figure in the code, right next to the ceiling — **REAL DEFECT**

`sim_poc/v5_clean.py`, immediately above `force_hi: float = 45.0`:

```
    # Cleaning peaks at 34.5 N, comfortably inside the stable region.
    force_hi: float = 45.0
```

**34.5 N is a pre-clamp number.** The measured peak has been 23.93 N since the arm speed
clamp landed on 2026-08-10 (837a5cd), which nearly halved peak contact force. Anyone who
opens the config block to sanity-check the JSON reads 34.5, compares it to 23.93, and
concludes the stats file is stale — when in fact the *comment* is. This is my best guess at
what prompted the question, and it should be fixed.

### (ii) The file records a measured value above its own stated limit

```json
"tcp_speed_max_mms": 1005.4303493881895,
"tcp_speed_limit_mms": 1000.0,
```

At a glance that reads as a violation. It isn't — `report()` asserts
`vmax <= vlim * 1.10`, with a documented 10% servo-overshoot allowance (the governor bounds
the *commanded* Cartesian rate at 80% of rating; a position servo overshoots while closing
an error, on ~0.16% of steps, all free-space). But the JSON records the limit **without**
the allowance, so the schema invites exactly this misreading.

### (iii) There are a lot of peak-force numbers in CLAUDE.md and they are easy to cross

For this file the correct comparator is **23.93 N**. Nearby numbers that are *not* it:

| number | what it actually is |
|---|---|
| 34.5 N | pre-clamp V5-C point mode (and the stale comment above) |
| 32.94 N | pre-clamp point mode, re-baseline table |
| **23.93 N** | **current point mode — this file** |
| 22.62 N | current stroke mode, `stats_v5_clean_stroke.json`, seeds 2120–2135 |
| 22.04 N | stroke mode on the older 1920–35 seeds |
| 32.15 / 34.66 N | pre-clamp stroke |

Note CLAUDE.md quotes the stroke peak as **22.6 N** in the V7-STROKE block and **22.04 N**
in the re-baseline table; the committed stroke file is 22.62 on a different seed range.
Both statements are individually defensible but the pair is confusing.

---

## 4. Two things you did not ask about

### (a) The V7.3 gap held by luck of scoping, not by any guard

V7.3 changed `v5_clean.py` and left `stats_v5_clean.json` alone. That turned out fine —
I verified it and the number reproduces. But nothing in the repo *enforces* that a change
to the cleaning module invalidates the cleaning baseline. It was safe only because the new
code happened to be reachable solely from `verify()`. The same commit shape with one line
inside `run()` would have silently invalidated a published headline. A cheap guard (record
the `git rev-parse HEAD` of the code that produced each stats file, and have the gates warn
when `v5_clean.py` is newer than `stats_v5_clean.json`) would close this.

### (b) V7.2's "physics byte-identical" claim overreaches by one station

`f_max` moved at V7.2: `23.92629255727511` → `23.925980963125905`, a delta of **3.1e-4 N
(0.0013%)**. Immaterial in magnitude — solver reordering, not a physical change.

But that commit (407fd2f) changed **both** the clean loop (the `_rotating` opening-wait
fix) **and** the scene (`refurb_scene_v5.xml`, +39 lines of cap ridge geoms), and its
message asserts *"Physics byte-identical with them present."* That claim was verified for
the **membrane** station (37.98 s, align 0.28 mm, seat 1.28 mm, 9.70 turns) and is **not**
true of the cleaning peak force, which moved in the 4th decimal. I cannot attribute the
delta to the geoms versus the loop change without a bisect, and I did not run one. Worth a
wording correction, not a re-measurement.

---

## 5. ⚠️ Concurrent edit — `v5_clean.py` changed underneath me during this check

**`sim_poc/v5_clean.py` is being actively modified right now by something outside this
session. I did not write it and I did not revert it.**

- At session start: `git status` showed only `?? .claude/` — the file was clean.
- Mid-session it showed `M sim_poc/v5_clean.py` at +20 insertions.
- Minutes later: **+89 insertions / −33 deletions**, mtime advancing to 11:32:42.

The content is coherent, in-house-style "V7.4" work: a servo-tracking metric
(`stroke_servo_metric: bool = True`), a **fourth `MjData`** (`self.fk`) for forward
kinematics of the *commanded* configuration, and `stroke_servo*` / `stroke_ds`
accumulators. It is scoped to stroke mode and its own comment claims the trajectory is
byte-identical whether on or off, asserted on seed 1920.

**Does this invalidate my result? No.** My run loaded the file at ~11:30:25 and finished at
11:31:02; the earliest modification evidence is 11:32:42. More decisively, the run
reproduced **all 16 digits** of `f_max` and every other field — which would not happen if
in-flight edits had perturbed the point-mode trajectory. My reproduction is against the
committed code.

I snapshotted the in-flight diff (read-only) to
`…/scratchpad/v7.4_inflight.diff` in case it is useful.

Two things follow: whoever is editing should know a baseline check was running against that
file, and **the point baseline should be re-run once V7.4 settles** — `self.fk =
mujoco.MjData(m)` lands in `Cell.__init__`, which *all* modes execute, so the "stroke-only"
scoping deserves confirmation rather than assumption.

---

## 6. The command I did NOT run

Per the time-box, and because it would overwrite a committed baseline:

```
cd /Users/pranavmulakala/WaterFilterRobo/sim_poc
../venv/bin/python v5_clean.py --eval 8 --seed0 900
```

**Expected:** ~5 minutes wall clock (36.8 s/unit × 8). It should rewrite
`stats_v5_clean.json` **byte-identically** — coverage 100%, missed 0 of 129,
`f_max` 23.925980963125905, `in_band` 1.0, tcp 1005.43 mm/s, joint 2.4610 rad/s.

Verify with `git diff -- sim_poc/stats_v5_clean.json` — **expect an empty diff.**

If any force/tilt/speed/raster field moves, that is a genuine regression rather than
seed noise, because those fields are seed-independent and I have now shown that unit 1
alone determines them. (Run it only when `v5_clean.py` is not being edited.)

---

## 7. Recommendation

1. **Believe the number.** 23.93 N is correct and reproduces exactly. Nothing to fix in
   `stats_v5_clean.json`.
2. **Fix the stale comment** above `force_hi` in `v5_clean.py` — "Cleaning peaks at 34.5 N"
   should read 23.93 N (point) / 22.62 N (stroke), post-clamp. This is the most likely
   source of the suspicion.
3. **Record the allowance in the JSON**, or rename the field, so `tcp_speed_max_mms`
   exceeding `tcp_speed_limit_mms` stops reading as a violation.
4. **Reconcile the stroke peak force** quoted in CLAUDE.md (22.6 vs 22.04) against the
   committed `stats_v5_clean_stroke.json` (22.62, seeds 2120–2135).
5. **Add a staleness guard** so a change to `v5_clean.py` without a matching baseline
   re-run is caught by a gate rather than by someone's instinct.
6. **Re-run the point baseline after V7.4 lands**, using the command in §6.

### Confidence

High on the headline (bit-for-bit reproduction is about as strong as this gets). High on
V7.3 being inert here (verified by call-site analysis *and* by the reproduction). Medium on
my *diagnosis* of why it looked wrong — the stale 34.5 N comment is the best candidate but
I am inferring your reasoning; if you were comparing against something else, tell me which
number and I will chase that specific discrepancy.
