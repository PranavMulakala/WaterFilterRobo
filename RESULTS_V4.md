# Results — v4 Inspect / Clean / Replace  ⚠️ PARTIALLY COMPLETE

**Status: the decision half works and is validated. The re-installation half does not.**
This file reports what was measured, including what failed. Nothing here is tuned to
flatter the numbers.

Measured on MuJoCo 3.11.0 / numpy 2.5.1 / Python 3.12.13 (pinned).

---

## What works

### Inspection — real image processing, validated

The arm presents the extracted cartridge to a fixed station camera; a frame is
**rendered and graded on its pixels**. Scale is real geometry (a pool of 44 deposit
geoms, a random subset revealed per trial), not a colour swap, so the classifier
cannot read back a value we wrote.

| Seeds | Accuracy | False-clean rate |
|---|---|---|
| Calibration rig, 9000+ (thresholds fit here, then frozen) | 93.9% | — |
| **In-cell, held-out seeds 200–229** | **90.0%** | **3.7%** |

Per-severity on the held-out block: clean **100%** (3/3), light **78.6%** (11/14),
heavy **100%** (13/13).

**No heavily-damaged cartridge was ever graded clean, on any run.** Every false-clean
is a lightly-scaled part. That is the safest available error distribution: the
dangerous error (bad part returned to a customer) does not occur; the errors that do
occur are light parts occasionally passing, and clean parts occasionally sent for
unnecessary cleaning — wasteful, not unsafe.

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

## What does not work

**Both re-installation routes fail: 0%.** A cartridge that is clean, or that has been
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
- **No demo video for v4.** The requested cut shows three routes back to back; two of
  them do not work. A video showing only the working route would misrepresent the
  state of the build. `media/refurb_cell_v3.mp4` remains the current honest demo.
