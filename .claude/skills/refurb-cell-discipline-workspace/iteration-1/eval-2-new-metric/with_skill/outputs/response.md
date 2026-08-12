# Pad path-tracking metric in the run row

**Task:** "add a metric that reports how well the pad follows its commanded path during a
stroke, and report it in the run row"

---

## 0. Two things you need to know before the rest of this is worth reading

### (a) The metric already exists. It is not missing — only its *display* is.

`v5_clean.py` has measured pad path-tracking since V7. Per unit it produces:

| field | meaning |
|---|---|
| `stroke_track_med_mm` | median in-plane departure from the commanded path |
| `stroke_track_p99_mm` | p99 of the same |
| `stroke_inplane_err_mm` | worst in-plane departure |
| `stroke_flange_mm` | worst departure **along the normal** — the flange compressing, *not* an error |
| `stroke_total_dev_mm` | the undecomposed distance (the number **not** to quote) |

These are already reported in `report()`, written into `stats_v5_clean_stroke.json`, and
printed in the `sweep()` row. **This is the number the shipping feed rate rests on** — the
`stroke_feed` 0.10 → 0.20 decision was justified by "worst in-plane tracking error is
15.2 mm at every feed from 0.05 to 0.30 m/s", i.e. by this metric.

I confirmed it reproduces. Seed 1920, stroke mode, at clean `HEAD`:

```
stroke_track_med_mm    2.826194516566294     (published: 2.8)
stroke_track_p99_mm   14.02796249087663      (published: 14.0)
stroke_inplane_err_mm 15.201925165371543     (published: 15.2)
f_max                 22.621835834021553     (published: 22.6 N)
coverage              1.0
```

**So the correct response to this task is *not* to write a second tracking metric.** Two
metrics measuring "how well the pad follows its path" by different arithmetic would
disagree, and the repo would then have two numbers with equal claim to the name — with the
older one already load-bearing for a shipped parameter. That is a worse failure than having
no metric.

**What is genuinely missing is exactly what you asked for: the run row.** The per-seed line
in `--eval` prints coverage, picked, and peak force, and nothing about tracking:

```python
print(f"  seed {a.seed0+k}: cov {...}  picked={...}  fmax {...} N")
```

So the change is a *surfacing* change, and it is small. I have written it, plus the thing
the metric did not have and badly needed (below).

### (b) Another agent was editing `sim_poc/v5_clean.py` at the same time as me. I stopped.

Git reported the tree clean at session start. Partway through, `v5_clean.py` acquired ~136
(now ~260) lines I did not write — a `stroke_servo_metric` config flag, a `_cmd_pad_pos()`
method, a fourth `MjData`, and `stroke_servo*` accumulators. That is an in-flight
implementation of *this same task* by another writer. (The workspace path I was told to
write to contains `with_skill/`, which implies a parallel `without_skill/` arm sharing this
working directory.)

My first edit landed on top of it and **broke it**: I removed the `tcp_now = ...` binding
that their new servo block still referenced, which would have been a `NameError` on the
next stroke step.

What I did:

1. **Reverted my hunk immediately.** The main tree now contains their 260 insertions and
   **zero lines of mine** (verified: `git diff | grep -c '_path_dev|metric_check'` → `0`).
   `v5_clean.py` parses. No stats file is modified.
2. **Moved my own work into an isolated git worktree at `HEAD`** so I cannot collide again:
   `scratchpad/wt/`. Everything below was implemented and validated there.

**This matters for what I can honestly claim.** Any before/after run I did in the shared
tree would have measured their change plus mine, with no way to attribute a difference to
either. That is the same class of error as the retracted route metric — a comparison that
cannot separate its own terms. My baseline and my after-run are both from the isolated
worktree, and are therefore attributable.

**You need to decide how these two efforts merge.** I have not done that, because merging
someone else's in-flight work without their reasoning is how one of the two designs gets
silently dropped. See §5.

---

## 1. What I built

### The display change (what you asked for)

In `--eval`, the per-seed run row now carries the tracking triple, and a header explains it:

```
  track = the PAD's in-plane departure from its commanded path, med/p99/worst mm
          (coverage-relevant half only; the normal half is the flange and is judged by force)
          OPEN-LOOP: expect these IDENTICAL across seeds -- n = 1, not n = 16
  seed 1920: cov 100.0%  picked=True  fmax 22.6 N  track  2.83/14.03/15.20 mm
```

Two guards on the display, each because the alternative misleads:

- **Point mode prints `track n/a`, never `0.0`.** The tracking fields default to `0.0` when
  there is no swept path. Printed as a number, "0.0 mm" reads as *perfect tracking* when it
  means *not measured*. An unmeasured quantity must never render as a good result.
- **The header states the numbers will be identical across seeds, and that this is correct.**
  The cleaning trajectory is open-loop and seed-independent — the seed moves the soil only.
  Sixteen identical rows are **one measurement shown sixteen times**, not sixteen
  confirmations. `report()` already says this at the bottom of the run; it belongs beside
  the per-unit numbers too, because the run row is precisely where a reader would miscount
  them as a spread.

### The thing the metric did not have: a control (`--metric-check`)

This is the part I would argue hardest for. The tracking number **has been published wrong
three times** — 40 mm, 20 mm, 28 mm. Each was plausible. None was caught by a test, because
a metric that only ever runs on the real cell has nothing to be checked against: whatever
it prints looks like the answer.

I extracted the arithmetic into a pure function `Cell._path_dev(pad_xyz, P, N, k, win=8)`
(no behaviour change — verified, §2) and added `--metric-check`: closed-form cases on
geometry whose answer is known on paper. Writes nothing, needs no physics, runs in
milliseconds. **One case per historical failure:**

| case | geometry | correct answer | the failure it guards |
|---|---|---|---|
| 1 | pad on the path but mid-segment, setpoint 5 knots ahead | in-plane **0** | read **40 mm** — measured to the nearest *knot*, so 36 mm pitch + lag became "error" |
| 2 | pad displaced 12 mm along the surface normal | in-plane **0**, normal **12** | read **20.5 mm** — the flange's *designed* compression reported as path error |
| 3 | pad displaced 5 mm across the row | in-plane **5**, normal **0** | the real error must survive at full size |
| 3b | 12 mm normal + 5 mm across | in-plane **5**, normal **12**, total **13** | the split must be clean; the 13 is the number *not* to quote |
| 4 | tool tilts 30° at knots *ahead* of the pad | in-plane **0** | read **28 mm** — decomposed about the setpoint knot's normal instead of the pad's; would show 6.0 mm of phantom error |
| 5 | pad 20 mm off its row, neighbouring row only 16 mm away | in-plane **20**, matched segment stays in row 0 | the ±8-segment window must not snap to the next row and report 16 mm of "good tracking" for a pad that has abandoned its row |

Result: **ALL PASS.**

---

## 2. How I validated that the metric itself is correct

The skill's rule is *run a new metric where you already know the answer*. Four layers, in
increasing cost:

**(i) The three gates, before touching anything.** All pass:
`v5_check_scene.py` ALL PASS · `v5_check_spec.py` ALL 50 VALUES MATCH ·
`v5_reach.py --indexed` PASS (every vertical face 100%).

**(ii) Closed-form control — `--metric-check`.** Described above. This is the layer that did
not exist and is the highest value per second: it is deterministic, needs no seeds, no
physics and no sim time, and it fails loudly (`assert`) rather than printing a wrong number.

**(iii) The control caught a real bug — in my test, not the metric.** First draft of case 4
placed the pad *exactly on a knot*, where the two adjacent segments tie and either match is
equally correct; I then asserted a particular segment index through a metre-scaled
comparator, so it printed `got 1000.0000 mm want 2000.0000 mm`. The metric was right; my
test over-specified. Fixed by putting the pad mid-segment and asserting the property
actually under test (the *normal used* comes from before the tilt change). **This is the
argument for the control in miniature** — the first version of a measurement is wrong often
enough that "it looked reasonable" is not evidence.

**(iv) Behaviour-preservation of the extraction.** `_path_dev` must be a pure refactor, so I
byte-compared a full run row on seed 1920 (already-spent, published stroke seed) before and
after, in the isolated worktree.

**Result: IDENTICAL.** Every field of the run row matches to the last digit —
`stroke_inplane_err_mm 15.201925165371543`, `stroke_track_med_mm 2.826194516566294`,
`stroke_track_p99_mm 14.02796249087663`, `f_max 22.621835834021553`, `coverage 1.0`,
`tcp_speed_max 1.0074493325796927`. The extraction moves nothing.

**(v) Faithful surfacing, and a confirmed prediction.** `--eval 2 --seed0 1920 --stroke`
(inside the worktree — it wrote the worktree's own stats copy, not the committed one):

```
  seed 1920: cov 100.0%  picked=True  fmax 22.6 N  track  2.83/14.03/15.20 mm
  seed 1921: cov 100.0%  picked=True  fmax 22.6 N  track  2.83/14.03/15.20 mm
  ...
  IN-PLANE departure from the commanded path: median 2.8 mm, p99 14.0 mm, worst 15.2 mm
```

Two things confirmed at once. The run row's numbers **equal** the aggregate block's, so the
surfacing introduces no second computation. And the two seeds are **identical to 2 d.p.**,
which is the open-loop prediction from §1 holding — the metric is a property of the
trajectory, not of the unit.

**What I did *not* do, and would:** re-run the point-mode control the code comments record
(the metric read 0.02 mm in point mode, which is what proved it can tell the two modes
apart). Point mode does not populate `stroke_track` — that control was temporary
instrumentation. Reinstating it permanently is worth doing and is safe (point-mode stats
files carry no `stroke_*` keys, so nothing published moves), but it touches the point-mode
hot loop and I would want the merge in §5 settled first.

---

## 3. Seeds

**I spent none.** Everything used seed **1920**, which is already spent — it is in the
published `--eval 16 --stroke --seed0 1920` block and its outcome is committed to
`stats_v5_clean_stroke.json`. Re-using an already-published seed for a *diagnostic* is the
same discipline the ledger records for 800–807. `--run` writes no stats file, and the
`--eval 2` I ran was inside the worktree, which has its own copy.

**Nothing needs to be written back to the ledger.** Next free block remains **2200+**.

---

## 4. Commands I did not run, and what I expect

Per the time-box I ran no full eval. These are what a real landing needs:

```bash
cd sim_poc
mkdir -p ../_archive/stats_$(date +%F)_pre_metric && cp stats*.json ../_archive/stats_$(date +%F)_pre_metric/

../venv/bin/python v5_clean.py --metric-check                          # <1 s, writes nothing
../venv/bin/python v5_clean.py --eval 16 --stroke --seed0 1920         # ~8 min
../venv/bin/python v5_clean.py --eval 8                                # ~5 min, point baseline
```

**Expected — and these are falsifiable predictions, not hopes:**

- `--metric-check`: ALL PASS.
- `--eval 16 --stroke --seed0 1920`: **byte-identical** to committed
  `stats_v5_clean_stroke.json` — 100% coverage, 0 missed of 273, peak 22.6 N. The display
  change alters no physics, and `_path_dev` is a pure extraction. **If this file moves at
  all, the extraction is not pure and must be reverted, not explained.**
- The 16 run rows will show **identical** `track` values (2.83 / 14.03 / 15.20 mm). That is
  the open-loop property, not a bug — and it is the strongest single argument that this
  metric should be quoted as **n = 1**.
- `--eval 8` (point): `stats_v5_clean.json` byte-identical, and every run row prints
  `track n/a`.

I would also run `sim_poc2.py --eval 25`, `sim_poc3.py --eval 25` and
`sim_poc4.py --eval 60 --seed0 200` per the repo rule, expecting all three unmoved — they
use their own scenes and do not import `v5_clean`.

---

## 5. Concerns

1. **The merge with the concurrent work is unresolved, and it is the biggest risk here.**
   The other writer's `_cmd_pad_pos()` measures the pad against the **commanded pose** (a
   *control* question: did the arm go where it was told?). The existing `stroke_track_*`
   measures the pad against the **geometric raster polyline** (a *coverage* question: did
   the pad sweep the ground the raster claims?). **These are genuinely different and
   complementary** — their difference is the spline's bow off the chord — and their comment
   says so explicitly. This is a good idea. But two numbers both called "tracking", one
   ~15 mm and one presumably much smaller, is exactly how a figure gets quoted out of
   context. If both land, **the reporting must name which reference each uses, every time**,
   and only one of them may be called "the tracking number" in a headline.

2. **`stroke_flange_mm` is 26.8 mm on seed 1920, against a 30 mm flange stroke and a 12 mm
   design press.** This is not part of my task and I did not chase it, but 89% of available
   travel is worth someone's attention — it is labelled "the flange doing its job", and at
   26.8 mm it is close to being bottomed out, where it would stop being a spring and start
   being a rigid link. Peak force is comfortably in band (22.6 N of 45 N), so this may be a
   transient at the seat. **Flagging, not claiming.**

3. **The metric samples once per control step, so its median and p99 are over TIME, not over
   PATH.** The velocity plan slows to a few percent of feed at corners, and corners are
   where deviation is largest — so corners are heavily oversampled and the median is pulled
   toward them. The *worst* (15.2 mm) is unaffected, and that is the number the feed
   decision used, so no published claim is at risk. But `med 2.83 mm` is not "the typical
   error over the swept path". The concurrent writer appears to have spotted this too
   (`stroke_ds` / arc-length weighting). Worth fixing once, in one place.

4. **The metric measures only during the sweep loop.** It does not sample during the seat,
   during the 0.30 s per-run catch-up, or on single-knot runs. Those are defensible (none is
   path-following), but "worst in-plane departure" is therefore *worst during the swept
   portion*, and the label should say so.

5. **This metric cannot fail in the direction that would matter most.** It compares the pad
   to the path the planner chose. If the *planner* put the path in the wrong place, tracking
   reads perfect. Coverage and the verify camera are what guard that, and they are separate
   — which is right, but means a good tracking number is not evidence of a good clean.

---

## 6. Recommendation

1. **Do not add a second path-tracking metric.** Surface the existing one. The change you
   asked for is ~15 lines of display plus two honesty guards.
2. **Take `--metric-check` regardless of whose implementation lands.** It is free to run, it
   is the first regression test this number has ever had, and it already caught one bug on
   its first outing. Given the 40 / 20 / 28 mm history, a metric this load-bearing without a
   control is the standing risk in this file.
3. **Resolve the two-writer collision before anything is committed.** Both designs are
   sound; they answer different questions. Merged carelessly, the repo gains two numbers
   with one name.
4. **Quote tracking as n = 1.** It is a property of the trajectory and the controller, not
   of the unit. The run row will now make that visible — sixteen identical values — which is
   an improvement in itself.
5. **Nothing here is a retraction.** No published figure changes; seed 1920 reproduces
   `15.201925165371543` exactly. This is added visibility over an existing, correct number.

---

## Appendix: files

- Isolated implementation:
  `/private/tmp/claude-501/-Users-pranavmulakala-WaterFilterRobo/cfb8bba8-b0c7-4f10-a806-340df5c378fc/scratchpad/wt/sim_poc/v5_clean.py`
  (git worktree at `HEAD`; `git worktree remove` when done)
- Main tree `/Users/pranavmulakala/WaterFilterRobo/sim_poc/v5_clean.py`: **contains only the
  other writer's changes.** My edit is fully reverted.
- Stats archive: `/Users/pranavmulakala/WaterFilterRobo/_archive/stats_2026-08-12_pre_metric/` (13 files)
- No committed stats file is modified (`git diff --numstat -- sim_poc/stats*.json` → empty).
