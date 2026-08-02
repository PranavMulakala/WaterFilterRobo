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
**15/15 on held-out seeds.** This is the v3 path, unchanged.

### Cleaning motion

Dip + dwell + vertical agitation in a solution tank. **No fluid or chemical
simulation.** Cleaning removes the same deposit geoms the camera graded, so a
re-check observes the identical mechanism — success is verified from an image, not
asserted. The motion executes; see below for why the verification does not yet report.

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

## What still limits it

End-to-end is **capped by vision, not mechanics** — routing compliance is 100%, so
every trial that fails does so because the classifier graded the part wrong, not
because the arm failed. The weakest cell is light-vs-heavy (75%).

### Superseded — the old blocker

**Both re-installation routes previously failed: 0%.** A cartridge that is clean, or that has been
cleaned, is supposed to go back into the unit. It does not.

**Cause — the cap grip cannot retain the part.** A seated cartridge can only be
gripped by its cap: the collar and chamfer occlude the body below z = 126 mm. That
grip is a small friction patch carrying a 110 mm lever. v3 never exposed the
limitation because it only ever carried the part ~5 s to a bin, where precision did
not matter. v4 asks the same grip to survive presentation, a tank dip and a
re-insertion — and the part is dropped every time. Measured: the hang offset wanders
between 42 mm and 83 mm, and the part leaves the jaws around 20 s in.

Consequences on held-out seeds 200–229:

| Metric | Value |
|---|---|
| Routing compliance (arm executed the route it chose) | 50.0% |
| End-to-end success (right action **and** unit finished correctly) | 43.3% |
| REPLACE route | 100% (15/15) |
| CLEAN / LIGHT routes | 0% (0/15) |

Both figures are dominated entirely by the reinstall failure.

### Proposed fix (not yet built)

A **chamfered staging nest** — a shallow cup with a 45° lead-in at the staging
position. The part is set down into it and re-gripped by the **body**, which is the
firm grip the whole insertion sequence was validated against. This is standard plant
practice, and it is the same chamfer trick the socket already uses and that this
project has already proven works at 3 mm clearance. Placing onto a flat tray was
tried and fails: a compliant grip tips the part on contact, and a tilted part topples
on release.

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
- Deposits remain **visual only**; real scale would change fit and mass.
