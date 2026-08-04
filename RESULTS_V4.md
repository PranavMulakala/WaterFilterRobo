# Results — v4 Inspect / Clean / Replace

> **v4 is no longer the current work.** The project moved to **v5** on 2026-08-04 — a
> unit-scale cell working on the whole purifier rather than one cartridge. Two of its
> three stations are built (TRIAGE, CLEAN); **membrane assembly is not started**, so v5
> does not yet reassemble anything. v5
> results live in **[V5_PLAN.md](V5_PLAN.md)**; current state is at the top of
> **[CLAUDE.md](CLAUDE.md)**. Read this file for the v4 numbers and for the vision
> lessons, which still govern.
>
> **What has actually been re-verified:** the DR-off 60-seed baseline (86.7% / 0.0% /
> 100%) reproduces `stats_v4.json` byte-identically, confirmed 2026-08-04. The
> domain-randomization rows, the 92.8% two-view calibration figure and the 8 mm / 8° nest
> capture envelope have **no committed artifact** — `stats_v4.json` holds only the DR-off
> run. Nor is one command enough to re-run them: `sim_poc4.py --dr SCALE` reproduces the
> **DR rows only**. The 92.8% two-view figure needs `inspect_views` edited in the frozen
> `RefurbConfig` (no CLI flag exists), and the 8 mm / 8° nest envelope and the 5/5
> sabotage result have **no reproduction path in committed code at all** — the sabotage
> was a temporary edit, and `grep -ri sabotag` over the repo's Python returns only a v5
> file saying the feature is not built yet. Do not read "v4 still reproduces" as covering
> any of these.

**All three routes run end to end. Routing compliance 100%, false-clean rate 0.0%,
end-to-end 86.7% — on 60 held-out trials.** Nothing here is tuned to flatter the
numbers; the section on what still limits it is at the bottom.

Measured on MuJoCo 3.11.0 / numpy 2.5.1 / Python 3.12.13 (pinned).

---

## What works

### Inspection — real image processing, validated

The arm presents the extracted cartridge to a fixed station camera; a frame is
**rendered and graded on its pixels**. Scale is real geometry (a pool of 44 deposit
geoms, a random subset revealed per trial), not a colour swap, so the classifier
cannot read back a value we wrote.

Thresholds are frozen, fit on calibration seeds 9000+ using **in-cell** presentations
(the arm actually holding the part), disjoint from every eval seed.

| Metric, 60 held-out trials (seeds 200–259) | Value |
|---|---|
| Inspection accuracy | **86.7%** |
| **False-clean rate** | **0.0%** |
| Routing compliance (arm executed the route it chose) | **100%** |
| End-to-end (right action **and** unit finished correctly) | **86.7%** |
| Cleaning verified by re-inspection | 100% of 22 |

Per-severity: clean **91.7%**, light **75.0%**, heavy **100%**.
Per-route completion: clean **100%** (11/11, 41.6 s), light **100%** (22/22, 53.5 s),
heavy **100%** (27/27, 40.7 s).

**Every remaining error is on the safe side.** Nothing that needs work is passed as
clean: the false-clean rate is 0.0%. The 8 errors are **7 lightly-scaled parts graded
heavy** (replaced instead of cleaned — wastes a cartridge, does not return a bad one to a
customer) and **1 clean part graded light** (washed unnecessarily). 52 of 60 correct is
the 86.7%. *(This paragraph said "7" for both, which did not reconcile with the file's own
86.7% or with its clean-91.7% line, i.e. 11 of 12.)* Re-fitting the thresholds on in-cell rather
than rig presentations is what drove false-clean from 2.1% to 0.0%.

The classifier is deliberately simple and explainable — HSV threshold + region
statistics (deposit coverage over the cartridge body, plus intensity texture), with
`score = coverage + 0.70 × texture` and two frozen thresholds. It has to be defensible
to a customer, not impressive to a reviewer.

**Two views, not one — and this is already banked, not still on the table.** On the
calibration set, single-view scored 86.7% and rotating the part 180° for a second view
scored 92.8%. Occlusion — half the deposits facing away from the camera — was the dominant
error source, and the fix costs nothing mechanically because the wrist can simply spin. So
`inspect_views = 2` is the shipped default, and **the 86.7% headline above is already the
two-view result** on held-out seeds 200–259. The two numbers are not comparable: 92.8% is
calibration, 86.7% is held out.

### Routing decision

The classifier's grade selects the route. That decision is live in every trial.

### REPLACE route — 100%

Heavily-damaged parts: extract → inspect → bin → install a fresh cartridge → lock.
**27/27 on held-out seeds.** This is the v3 path, unchanged.

### Cleaning motion

Dip + dwell + vertical agitation in a solution tank. **No fluid or chemical
simulation.** Cleaning removes the same deposit geoms the camera graded, so a
re-check observes the identical mechanism — success is verified from an image, not
asserted. Verified on 100% of 22 cleaned parts, and falsification-tested (below).

---

## How the re-installation was fixed

Both reinstall routes were **0%** before Phase A. Two changes fixed them.

**1. A chamfered staging nest.** The part is set into a shallow cup with a 45° lead-in
and re-gripped by its **body** — the firm grip the whole insertion sequence was
validated against. The cap grip only has to get the part roughly over a hole; the
chamfer does the rest. Measured capture envelope: seats reliably up to **8 mm lateral
offset and 8° tilt**, and the arm delivers ~3°.

Two bugs had to be found first. The nest was sized to the 21.5 mm cartridge **body**
and interfered with the 34 mm bayonet **lugs** by exactly 7.0 mm. And the chamfer ring
copied the socket's `euler="0 0.785 θ"`, which tilts every plate about the same world
Y axis rather than radially — a pinwheel overhanging its own bore. The socket survives
that only because its malformed plates land where the bayonet slot gaps are.

**2. Wet work happens after the re-grip.** Dipping a cap-gripped part drops it ~7 s in,
every time. Nest first, re-grip by the body, then clean.

## Cleaning verification is falsifiable

Cleaning removes the same deposit geoms the camera graded, and success is verified by
re-inspecting on a fresh render. To prove that check is real, the cleaning was
**deliberately sabotaged** so deposits were left in place — the re-check must then
fail the part. It initially passed 2 of 5 sabotaged parts, because it classified on a
single view while the main inspection used two. With both views: **5/5 honest
cleanings verified, 5/5 sabotaged cleanings caught** — 5 sabotaged + 5 honest trials,
2026-08-02, from a **temporary edit to the cleaning branch**. There is no sabotage harness
in committed code and no artifact in `stats_v4.json`, so this number cannot currently be
re-run. Building that harness properly is V5-D.

## Robustness — how much error the cell tolerates (Phase C)

Every number above is measured on **one** set of physical parameters that we chose.
Domain randomization perturbs them per trial: cartridge mass ±20%, friction ±30%, and
a vertical shift of the **whole cell** (bench, socket, tray, bin, tank, nest, booth)
while the robot's commanded heights stay put — i.e. a calibration error, the most
common real-world reason a working cell stops working.

All four configurations run the **identical 60 scenarios** (verified: DR is drawn from
an independent RNG stream, so the parts, spawns and lock angles are byte-identical
across configs).

| | inspection | false-clean | routing | end-to-end | aborts |
|---|---|---|---|---|---|
| **DR off** | 86.7% | 0.0% | **100%** | 86.7% | 0 |
| **±2.5 mm / ±10% mass / ±15% friction** | 86.7% | 0.0% | **100%** | 86.7% | 0 |
| **±5 mm / ±20% / ±30%** | 86.7% | 0.0% | **90.0%** | 78.3% | 6 |
| **±10 mm / ±40% / ±60%** | 91.7% | 2.1% | **55.0%** | 48.3% | 27 |

**Almost all the damage is mechanical, but "inspection is completely unaffected" is too
strong** — an earlier version of this paragraph said exactly that, and the table above
contradicts it: at ±10 mm inspection reads 91.7% and **false-clean leaves 0.0% for 2.1%**.
The headline safety metric does *not* hold across the whole DR range, and a sentence
claiming vision is untouched buries the one place it is not. See the "flat within noise"
paragraph below, which is the version that survived review.

**The usable envelope is about ±2.5 mm of cell-position error**, where there is no
measurable loss at all. At ±5 mm the cell still runs but loses ~9 points of
end-to-end. At ±10 mm it breaks down.

Inspection accuracy is flat within noise across all four levels (86.7–91.7%; on n=60
that spread is ~1.2 sigma). That is the expected result — once the part is presented on
the camera axis, mass and friction barely change what the camera sees — and it is a
useful sanity check that the DR is perturbing mechanics rather than vision.

**This converts the simulation into a requirement:** a real cell would need its
fixtures located to better than ±2.5 mm, and would need re-calibration if anything
moved by more than that. That is a concrete, checkable spec discovered before buying
hardware — and a more useful thing to hand a customer than a success rate.

One honest note: the obvious fix — referencing the measured part height instead of an
absolute descent — was implemented, measured, and **made things worse** (routing
90.0 → 85.0% at ±5 mm). It was reverted. Commanding an absolute descent and letting
the gripper contact the surface is more forgiving than aiming at a measured height.

## What still limits it

End-to-end is **capped by vision, not mechanics** — routing compliance is 100%, so
every trial that fails does so because the classifier graded the part wrong, not
because the arm failed. The weakest cell is light-vs-heavy (75%).

### For the record — the blocker this replaced

Before Phase A both re-installation routes scored **0%**, and routing compliance was
50%. The cause was that a **seated cartridge can only be gripped by its cap** — the
collar and chamfer occlude the body below z = 126 mm — and that grip is a small
friction patch carrying a 110 mm lever. v3 never exposed it because it only carried
the part ~5 s to a bin, where precision did not matter. Asking the same grip to
survive presentation, a tank dip and a re-insertion dropped the part every time: the
hang offset wandered between 42 mm and 83 mm and the part left the jaws around 20 s in.

**This is a real finding about the task, not just about our code.** If a robot cannot
hold this cartridge by its cap through a wet process, a real cell will need a fixture
too. That is a design input for DrinkPrime, discovered in simulation before anyone
bought hardware — see PITCH_NOTES.

---

## Honesty notes

- **The headline inspection figure is in-cell**, measured through the real motion path.
  An earlier version of this file reported 90% from a *test rig* that teleported the
  part into position — and the same classifier scored **53%** in the actual cell, with a
  **34.8% false-clean rate**, because the presentation height was wrong. See
  PAIN_JOURNAL. A vision result is only as valid as the fixture that presents the part.
- **The number came down as the sample grew, and that is the point.** In-cell inspection
  read **100% on seeds 0–19**, then **90.0% / 3.7% false-clean** on 30 held-out seeds,
  then **86.7% / 0.0%** on 60. The 100% was small-sample luck; **86.7% on seeds 200–259
  is the number**, and `stats_v4.json` records 60 trials. Reproduce with
  `sim_poc4.py --eval 60 --seed0 200` — a 30-seed run overwrites that baseline with the
  superseded figure.
- Deposits are **visual only** — no collision, negligible mass. Real scale would
  change fit and mass. Not modelled.
- **The v4 demo video shipped** (Phase B): `media/refurb_cell_v4.mp4`, ~81 s, all three
  routes with the live camera verdict on screen, trial footage at a clearly-labelled
  1.8×; `media/refurb_cell_v4_full.mp4` is the uncompressed 2:16 cut for true cycle
  times. *(This bullet said "no v4 demo video yet" for two phases after the video
  existed — and the duplicate "deposits are visual only" line it sat next to is now
  folded into the one above.)*
- Cleaning is **dip + dwell + agitate with no fluid or chemical simulation.** What is
  verified is that the deposits the camera could see are gone, not that any real
  descaling chemistry would work.
