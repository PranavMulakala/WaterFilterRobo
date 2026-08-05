# `v5_cell_reel.mp4` — what you are looking at, minute by minute

Companion to `media/v5_cell_reel.mp4` (5:57, **1.5× speed**, stamped top-right on every
frame). Regenerate with `v5_video.py --reel --speed 1.5`; the chapter list below is printed
by that command and also written to `sim_poc/reel_chapters.txt`.

---

## The one-paragraph version

A used purifier arrives. A fixed camera grades it Easy / Medium / Hard. The grade picks a
route. **Easy** gets cleaned and re-inspected. **Medium** gets that plus a membrane rebuild
and a leak check. **Hard** stops at a human decision. All three run end to end in this reel,
on three real units from the published evaluation.

---

## THE SINGLE MOST IMPORTANT THING TO SAY OUT LOUD

**The arm does exactly two jobs in this whole video: it CLEANS, and it INSERTS THE MEMBRANE
ELEMENT.** Everything else you see is cameras, a station driver, or bookkeeping.

| what you see | who does it |
|---|---|
| Turntable rotating during TRIAGE / VERIFY | **Position is set, not driven.** No motor is simulated, and the arm is parked clear |
| Pad wiping all five faces | **THE ARM.** Real contact, real forces, real coverage |
| Element lifted into the bowl | **THE ARM.** Real pick, carry, alignment and release |
| **Cap spinning on top of the bowl** | **NOT the arm — a station driver.** See below |
| Assembly moving into the water bin | **Nothing moves it. It is teleported** |
| "→ SCRAP APPROVAL" | **Nothing physical at all.** A software decision |

If someone watches this and comes away thinking the robot screws the cap on, we have
misled them. It doesn't.

---

## Chapters

| time | what | arm working? |
|---|---|---|
| 0:00 | Title card | — |
| **0:05** | **EASY route — seed 1700** | |
| 0:05.0 | TRIAGE — 0.8 s | no |
| 0:05.8 | CLEAN — **2 min 35 s** | **YES** |
| 2:40.5 | VERIFY — 2 s | no |
| **2:42.5** | **MEDIUM route — seed 1704** | |
| 2:42.5 | TRIAGE — 0.8 s | no |
| 2:43.3 | CLEAN — **2 min 35 s** | **YES** |
| 5:18.1 | VERIFY — 2 s | no |
| 5:20.1 | MEMBRANE — 13.8 s | **YES** (insert only) |
| 5:33.9 | DIP — 3 s | no |
| **5:36.9** | **HARD route — seed 1702** | |
| 5:36.9 | TRIAGE — 0.8 s | no |
| 5:37.7 | SCRAP — 2.5 s | no |
| 5:40.2 | Stats card | — |
| 5:48.2 | "What is not real" card | — |

**The shape of that table is the honest summary.** Of 5 minutes 57 seconds, about
**5 min 10 s is the arm cleaning** and about **10 s is the arm inserting the element**.
Everything else takes seconds because nothing physical is happening.

---

## Station by station

### TRIAGE — 0.8 seconds, and that's why you missed it

**Nothing moves.** The arm parks out of shot; the turntable is *stepped* to four positions;
a fixed camera takes one picture at each. Those four pictures are run through real image
processing — it separates the device from the background and measures defect area and shape
— and the unit is graded.

- **It is 0.8 s because it is four photographs, not a motion.** In a real cell it would be
  about as fast.
- **Watch the `GRADED` line in the HUD**, and compare it to `TRUTH` just above. The reel
  shows three units where they match.
- The camera never moves and never needs calibrating to the arm. That was deliberate.
- **The caveat on frame:** the class *names* Easy/Medium/Hard are DrinkPrime's; the
  *boundaries* between them are ours. No document in their set defines them. That is the
  top open question with the customer.

### CLEAN — the long one, and the only sustained robot work

The arm drives to a tool post, **latches a wiping pad through a tool changer** (not a
grip — a parallel-jaw grip on a process tool was measured to let it creep 60–70 mm), then
wipes **all five exposed faces**, rotating the turntable between them.

Things worth pointing at while it plays:

- `COVERAGE` climbing in the HUD, and `peak 34.5 N` — the contact force is real and is held
  in a band. The pad model is validated to 45 N and we never exceed it.
- The **retract → rotate → approach** ordering. Rotating while the arm is still over the
  device once swept the tool through the cabinet and knocked it out of the jaws — face 0
  wiped correctly and every face after was "wiped" with an empty gripper while the force log
  still looked healthy.
- **Caveat on frame:** no cream, detergent or chemistry is simulated. What is verified is
  that *the soil the camera could see* is gone. This is a **dry wipe of the cabinet
  exterior** — which is exactly the open question we have asked the founder about.

### VERIFY — 2 seconds, cameras only

The unit is re-photographed and re-graded **through a second camera**, and residue is
counted. No arm motion.

The second camera is not decoration. The triage camera sits at z = 0.400 and the top face
at z = 0.450 — it is *below* the top plane, so it grades four faces while cleaning covers
five. The first version of this check passed 9 of 10 units that were still dirty, and **the
face it could not see was the face cleaning missed.** Watch the `VERIFY residue 0 →
VERIFIED` line.

### MEMBRANE — 13.8 seconds, and this is the new capability

Two different things happen here and they must not be blurred:

1. **The arm really inserts the element.** Watch the `DEMO MEM` inset bottom-right. It picks
   the element off its nest, carries it, corrects its own aim, lowers it into the bowl and
   releases. The HUD prints
   `INSERT aligned 0.24 mm → seated 1.49 mm off-axis, IN`.
   The bore has **1.5 mm of radial clearance**, so this is a genuinely tight fit. It works
   because the cell measures *the element*, not the wrist — the jaws grip flat, so the part
   slides sideways inside them under its own inertia and the wrist never knows.

2. **The cap is NOT fitted or turned by the arm.** ← *this is the spinning you noticed*
   - The bowl arrives **open** (it has to — a fitted cap overhangs the whole bore 20 mm
     above the rim, and the element is 72 mm long; there is no path in).
   - The cap is then **presented by the fixture**, already engaged on the first thread.
   - It is then spun by a **station driver** — a separate torque-limited actuator, like a
     bench nutrunner. **The arm is not touching it.**
   - What *is* real is the screw itself: a genuine multi-turn thread, an O-ring it
     compresses, and a driver that **stalls on torque** rather than counting turns. Watch
     `TIGHTEN 9.35 turns 5.15 N·m seal 129 N` climb and then stop.

   Thread-*starting* — getting a cross-threadable cap onto a bowl — is a research problem
   in its own right and is a declared de-scope, not an oversight.

### DIP — 3 seconds, and nothing carries it

The sealed assembly is put in a water bin and watched for bubbles. This is **DrinkPrime's
own acceptance test** (Stage 10: plug the permeate outlet, close the reject valve, charge to
80–90 PSI, submerge, look for bubbles).

- **The arm does not carry it there. The assembly is teleported.** v3 and v4 already
  demonstrate pick-and-place at 100%; the claim here is about the *thread* and the *bubble
  check*, so a second pick-and-place was deliberately not re-built.
- **The bubbles are modelled from the cap torque, not computed from fluid.** There is no
  fluid or gas simulation anywhere in this project. What stays real is that a camera has to
  actually *see* the bubbles to fail the part — so the verdict is *caused* by how well the
  cap tightened, rather than read out of a variable.
- The falsification matters more than the pass: deliberately under-tighten the cap and the
  check catches it **10 times out of 10**, with **zero** false passes.

### SCRAP — 2.5 seconds, and it is honest about doing nothing

DrinkPrime's chart splits HARD into *rectifiable* and *non-rectifiable* on whether repair
would cost more than 80–90% — **of what, no document says.** We have no cost model, no price
list and no labour rate, so the cell **refuses to make that call** and routes the unit to a
person.

**No robot, turntable, conveyor or fixture motion delivers the unit anywhere.** It is a
software decision, and the frame says so. This is why the reel's headline number is
**22/28 fully backed** rather than 26/28 — the 4-unit gap is exactly these HARD units.

---

## The two end cards

**Stats card (5:40).** Everything measured, on held-out units the cell had never seen.
It leads with **FULLY BACKED 22/28**, not the flattering 26/28, for the reason above.

**"What is not real" card (5:48).** Six things we say before anyone asks. With a technical
founder this card is an asset, not an apology — it is the difference between a demo and a
claim.

---

## If they ask one hard question, it will be this

> *"So what did the robot actually prove it can do?"*

It cleans a whole device to 100% coverage under real contact forces, and it puts a part into
a hole with 1.5 mm to spare, ten times out of ten, correcting its own aim from the part
rather than the wrist. It also grades a device from pixels at 97.5% and never once graded a
scrap-class unit as good.

It has **not** shown that it can start a thread, carry an assembly to a test bath, or move a
reject unit off the line. Those are stated, not hidden — and two of the three are ordinary
pick-and-place that earlier versions already do at 100%.
