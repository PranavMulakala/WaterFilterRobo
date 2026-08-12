# Stroke feed 0.20 → 0.30: measured answer, and why I did not land it

**Short version.** New full MEDIUM cycle is **2:27.5** (147.5 s), down from **2:34.9** (154.8 s).
That is **−7.4 s, −4.8%**. The clean station itself goes **108.13 → 100.83 s**.

I measured this. I did **not** change any config value — see "What I changed" below.

---

## 1. What I checked first

- `sim_poc/v5_clean.py` `CleanConfig.stroke_feed` — currently `0.20`, carrying a ~30-line
  comment that explains why it is 0.20 **and not 0.30**. This is not an arbitrary default;
  0.30 was measured, was clean, and was deliberately declined. That changes the shape of
  the question from "is 0.30 safe?" to "do we want to spend the margin we chose to keep?"
- The committed feed sweep `sim_poc/sweep_stroke_feed.json` (seeds 2100–2103) — 0.30 is
  already in it at 104.1 s, 100% coverage, 0 missed of 81, 22.62 N.
- `CLAUDE.md` + `HANDOVER.md` for the published cycle decomposition:
  **CLEAN 108.1 + VERIFY 10.0 + MEMBRANE 36.7 = 154.8 s = 2:34.9.**
- That `v5_clean.py` already has a **`--feed` CLI override**, so the number can be obtained
  without touching the shipping default.
- That the clean trajectory is documented as **open-loop and seed-independent for timing**
  (only coverage and missed spots vary with seed), so one unit gives the exact station
  time, not a sample of it. That is what made this answerable inside the time box.

---

## 2. What I actually ran

Three commands, all on **seed 2120**, which the ledger records as already spent
(2120–2135, the published V7.1 16-unit validation). I did not burn a fresh seed for a
timing probe. `--budget` writes no files.

```
cd sim_poc
../venv/bin/python v5_clean.py --budget 2120 --stroke              # baseline
../venv/bin/python v5_clean.py --budget 2120 --stroke --feed 0.3   # candidate
../venv/bin/python v5_clean.py --run    2120 --stroke --feed 0.3   # speed asserts
```

**The baseline reproduced the published number exactly: 108.13 s vs the published 108.1 s.**
That is the check that makes the rest of this trustworthy.

| | feed 0.20 (shipping) | feed 0.30 | delta |
|---|---|---|---|
| **CLEAN station** | **108.13 s** | **100.83 s** | **−7.30 s (−6.8%)** |
| STROKE (pad on surface) | 83.15 s (76.9%) | 75.85 s (75.2%) | −7.30 s |
| retract / rotate / approach | 19.56 s (18.1%) | 19.56 s (19.4%) | 0 |
| tool latch / unlatch | 5.42 s (5.0%) | 5.42 s (5.4%) | 0 |
| coverage (seed 2120) | 100%, 0 missed of 17 | 100%, 0 missed of 17 | — |
| peak contact force | 22.62 N | 22.62 N | 0 |
| worst in-plane tracking | 15.20 mm | 15.17 mm | ≈0 |
| peak tool speed | 1007.4 mm/s | 1007.4 mm/s | 0 |
| peak joint speed | 2.462 rad/s | 2.462 rad/s | 0 |
| raster planned / skipped | 323 / 0 | 323 / 0 | 0 |

**Full cycle:** 100.83 + 10.0 (VERIFY) + 36.7 (MEMBRANE) = **147.5 s = 2:27.5**.

*Caveat on that arithmetic:* it assumes VERIFY and MEMBRANE are unchanged by feed. They
should be — VERIFY is indexer-bound and MEMBRANE starts from the same post-verify pose —
but I did not measure it. The honest confirmation is a true-1× render (command in §6).

---

## 3. The interesting finding: feed is now a shallow lever, and `stroke_accel` is why

Raising feed 50% bought 6.8%. That non-proportionality is the real result here.

Fit the two measured points to `stroke_time = A + B/v`:

```
83.15 = A + B/0.20      75.85 = A + B/0.30
  →  B = 4.38 m        A = 61.25 s
```

So of the **9.61 m** of swept path, only about **4.4 m actually runs at the commanded
feed**. The other **~61 s inside the STROKE bucket does not respond to feed at all.**

The `--run` output says why: **94 corners slowed per unit** over 9.61 m — a corner roughly
every **102 mm**. With `stroke_accel = 0.60 m/s²`, the distance needed to reach feed is
`v²/2a`:

- at **0.20**: 0.033 m each side → 0.067 m needed vs 0.102 m available → *just* reaches 0.20
- at **0.30**: 0.075 m each side → 0.150 m needed vs 0.102 m available → **never reaches 0.30**
  (triangular peak ≈ `sqrt(0.60 × 0.102)` ≈ **0.25 m/s**)

**Hypothesis, with the arithmetic above as support but not yet directly falsified:
`stroke_accel` — 0.60 m/s², an untouched default that has never been swept — is the
binding constraint above ~0.20 m/s, not `stroke_feed`.** Raising `stroke_feed` past ~0.20
mostly raises a number the arm does not reach between corners. This also explains the
published curve cleanly: 0.10 → 0.20 bought ~35 s; 0.20 → 0.30 buys 7.3 s, for the same
+0.10 m/s.

**Ceiling implied:** even at infinite feed the station floor is 61.25 + 19.56 + 5.42 ≈
**86 s**, i.e. a full cycle around **2:13**. Consistent with CLAUDE.md's "under 2:00 is not
reachable on anything measured clean" — and it means feed alone cannot get you there.

---

## 4. Concerns with actually shipping 0.30

**These are real but they are not force or tracking concerns.** Worth saying clearly,
because the usual objections genuinely do not bite here:

*Not a problem:* peak force is **identical** (22.62 N both) — the force peak lives in the
SEAT, which runs at `stroke_seat_scale` 0.20× and is untouched by `stroke_feed`. Tracking
is **15.20 → 15.17 mm**; the following-error clamp made it feed-independent, so the
pre-clamp feed cliff mechanism does not operate. Both hard speed assertions pass with
identical values (the peaks are set by free-space moves, not the sweep).

The three that do bite:

1. **DWELL — the one that matters, and no amount of testing fixes it.** The model removes
   soil on **contact**, not dwell. With a 60 mm pad, a surface point spends **0.300 s**
   under it at 0.20 and **0.200 s** at 0.30 — a 33% cut in rub time that **the simulation
   is structurally blind to**. Real cream on real soil may care. This is not a margin
   preference; it is a known model blind spot, and it is exactly the documented reason
   0.20 was chosen over 0.30.

2. **Margin.** 0.30 is the **fastest value ever measured on this station**. Shipping at it
   leaves 1.0× headroom instead of today's 1.5×. Direct precedent in this same file:
   `step_frac` 1.30 was faster, passed 16 units, and was **declined** at 8% margin.

3. **Evidence depth.** 0.30 rests on **4 units / 81 patches** (2100–2103). 0.20 rests on
   **16 units / 273 patches** (2120–2135) plus a 10-unit sabotage battery and 0/10 false
   verifies. Coverage failure is a rare event; 4 units is not a substitute for 16.

---

## 5. What I changed

**Nothing.** I used the existing `--feed 0.3` CLI override. `CleanConfig.stroke_feed` is
still `0.20` in the committed file. No stats or sweep artifact was written — verified with
`git diff --stat -- sim_poc/stats*.json sim_poc/sweep*.json` (empty).

I deliberately did not edit the default, for three reasons: it would silently invalidate
the published 108.1 s / 16-unit figure in `CLAUDE.md`, `HANDOVER.md` and
`stats_v5_clean_stroke.json`; CLAUDE.md's hard rules require held-out validation before a
config change is believed, and I am time-boxed out of running one; and see the concurrency
note in §7.

**The one-line change, if you want it after validation** — `sim_poc/v5_clean.py`, the
`stroke_feed` field:

```python
-    stroke_feed: float = 0.20
+    stroke_feed: float = 0.30
```

The ~30-line comment block above it would need rewriting too — it currently argues *for*
0.20 by name, so flipping the value without the prose would leave the file contradicting
itself.

---

## 6. Validation I would run (stated, not run — outside the time box)

**First, book the seeds in CLAUDE.md before running anything.** Next free block is 2200+.
Reserve **2200–2215** as "V7.4 feed-0.30 held-out validation" and **2216–2225** as its
sabotage battery.

**Second, protect the published artifact** — `--eval --stroke` writes to the exact filename
that holds the published 0.20 number:

```
cp sim_poc/stats_v5_clean_stroke.json /tmp/stats_v5_clean_stroke.PUBLISHED.json
```

Then:

```
cd sim_poc
../venv/bin/python v5_clean.py --eval 16 --stroke --feed 0.3 --seed0 2200
```
Expect coverage 100% mean **and worst**, 0 missed of ~270, peak ~22.6 N (ceiling 45 N),
in-band ~100%, tilt max 30°, tcp ~1007 mm/s, joint 2.46 rad/s. Anything short of 100%
coverage / 0 missed kills it outright. Runtime ≈ 25 min (my single unit took ~90 s wall).

```
../venv/bin/python v5_clean.py --sabotage 10 --stroke --feed 0.3 --seed0 2216
```
Expect 10/10 caught, 0/10 false verifies.

```
../venv/bin/python v5_video.py --realtime 2120 --stroke
```
Gives the **true-1× full cycle** instead of my 147.5 s arithmetic.

Gates (cheap, and unaffected — no scene change): `v5_check_scene.py`,
`v5_check_spec.py`, `v5_reach.py --indexed`. `v5_check_spec.py` asserts config statically,
so it matters specifically if the default is edited.

---

## 7. Two things you should know that I did not go looking for

**A concurrent session is editing `sim_poc/v5_clean.py` right now.** Git reported the tree
clean at session start. My three measurements finished at 11:30:19 and 11:31:59; the file
was modified at **11:33:08** and again at **11:33:23**, by something outside this session.
**All my numbers therefore ran against clean HEAD and are reproducible from committed
code** — but the working tree is no longer clean, and you have ~89 insertions of
uncommitted "V7.4" servo-tracking-metric work in there.

**That in-flight edit currently has a live `NameError`.** The refactor deleted the
assignment `tcp_now = d.geom_xpos[self.pad_face]` but left a reference to `tcp_now` in the
new servo-metric block. `grep -n "tcp_now" v5_clean.py` returns exactly **one** line — the
use, with no definition anywhere in the file. Since `stroke_servo_metric` defaults to
`True`, this will crash **every** `--stroke` run on the first stroke step. It parses fine,
so no syntax check catches it.

I did **not** touch it — it is someone else's work, mid-save, and it may well be fixed
seconds later. Flagging it rather than fixing it.

---

## 8. Recommendation

**Don't ship 0.30 for 7.4 s. Sweep `stroke_accel` instead.** My measurement says ~61 s of
the 83 s stroke bucket is feed-independent, and points at the acceleration limit and the
94 corner slowdowns as where that time actually lives. `stroke_accel` (0.60 m/s²) and
`stroke_corner_deg` (25°) are both untouched defaults that have **never** been swept. That
is a bigger lever than the 7.3 s on the table, and it is the diagnose-before-tuning move
this project's own history keeps rewarding — V6 swept `speed`, got 9.6%, and called feed a
dead lever, because it never asked whether to stop at all.

**If you want 0.30 anyway, it is defensible** on everything the sim *can* measure — force,
tracking, tilt, speed limits and coverage are all unchanged or identical. Run the 16-unit
+ sabotage validation in §6, and record the **dwell** caveat as an explicit honesty label,
because that is the one axis the simulation cannot speak to at any sample size.

**One more thing worth checking before optimising at all:** "cleaning *feels* slow" is a
perceptual complaint, and V7.3's whole lesson was that a visual complaint turned out to be
a measurement defect — twice in three days. **25 s of every cycle (23%) is
retract/rotate/index plus tool latch**, visible dead time that *no* feed change touches. If
you are watching the realtime video, that may be what reads as slow, and 0.30 will not fix
it.
