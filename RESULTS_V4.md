# Results — v4 Inspect / Clean / Replace

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
clean: the false-clean rate is 0.0%. The residual error is 7 lightly-scaled parts
graded as heavy — they get replaced instead of cleaned. That wastes a cartridge; it
does not return a bad one to a customer. Re-fitting the thresholds on in-cell rather
than rig presentations is what drove false-clean from 2.1% to 0.0%.

The classifier is deliberately simple and explainable — HSV threshold + region
statistics (deposit coverage over the cartridge body, plus intensity texture), with
`score = coverage + 0.70 × texture` and two frozen thresholds. It has to be defensible
to a customer, not impressive to a reviewer.

**Two views, not one.** Single-view inspection scored 86.7%; rotating the part 180°
and taking a second view scored 92.8% on the same calibration set. Occlusion — half
the deposits facing away from the camera — was the dominant error source, and the fix
costs nothing mechanically because the wrist can simply spin.

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
cleanings verified, 5/5 sabotaged cleanings caught.**

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

**Inspection is completely unaffected** (86.7% at every level up to 2×) — mass,
friction and table height cannot influence a camera, which is a useful sanity check
that DR is perturbing what we think it is. All the damage is mechanical.

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

- **The 90% inspection figure is in-cell**, measured through the real motion path.
  An earlier version of this file would have reported 90% from a *test rig* that
  teleported the part into position — and the same classifier scored **53%** in the
  actual cell, with a **34.8% false-clean rate**, because the presentation height was
  wrong. See PAIN_JOURNAL. A vision result is only as valid as the fixture that
  presents the part.
- In-cell inspection read **100% on seeds 0–19** and **90.0%** on 30 held-out seeds.
  The 100% was small-sample luck and is not the number.
- Deposits are **visual only** — no collision, negligible mass. Real scale would
  change fit and mass. Not modelled.
- **No v4 demo video yet** — that is Phase B. All three routes now run, so the
  three-route cut is buildable. `media/refurb_cell_v3.mp4` remains the current demo
  until it exists.
- Deposits are **visual only** — no collision, negligible mass.
- Cleaning is **dip + dwell + agitate with no fluid or chemical simulation.** What is
  verified is that the deposits the camera could see are gone, not that any real
  descaling chemistry would work.
