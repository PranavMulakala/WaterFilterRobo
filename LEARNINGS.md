# Learnings — robotics concepts, in plain English

A concept journal for two software engineers learning robotics by building one.
Written for **us**, not for agents or customers. Every term gets explained the first
time it appears; an unexplained term is a bug in this file.

`PAIN_JOURNAL.md` is *what went wrong and what it cost*. This is *what we now
understand that we didn't before*. One entry per significant update, ≤15 lines.

---

## 2026-08-01 — Making an arm go where you point it

**What we built:** The first working pick-and-place — the arm finds a cartridge and moves it.

**Inverse kinematics (IK).** An arm is controlled by joint angles: seven numbers. You
think "put the gripper *there*." Going from a desired hand position back to the joint
angles that achieve it is inverse kinematics — solving backwards. Forwards is easy
(given angles, where's the hand? geometry). Backwards is hard: many joint combinations
reach the same point, sometimes none do. So we don't solve it exactly — we nudge:
compute the small joint change that moves the hand closest to target, step, repeat every
few milliseconds. Gradient descent toward a pose.

**Why it matters:** Every motion on any arm we buy is this loop. Unstable in sim means
unstable — and expensive — on hardware.

---

## 2026-08-01 — Why the arm shook itself apart

**What we built:** A stable version of that loop, after the first one oscillated wildly.

**Open vs closed loop, and who you listen to.** Closed loop means correcting from what
you observe; open loop means executing a plan and hoping. Closed loop is usually right —
but our first version fed *measured* joint positions back into the planner, so the arm
chased its own lag and oscillated, like a thermostat reacting to its own draught. Fix:
plan against the **commanded** configuration and let the arm track it.

**Gravity compensation.** Gravity never stops and position-controlled motors sag under
it, so we add the exact torque that cancels it. Otherwise every position sits low.

**Why it matters:** Both are hardware problems, not sim artifacts. Real arms sag and
real feedback loops oscillate.

---

## 2026-08-02 — Where you hold something decides what you can do with it

**What we built:** A grasp that keeps the cartridge steady while the arm moves it.

**Grasp geometry.** We assumed "grab it and go." Wrong twice. First, the gripper's pads
sit ~25 mm *above* the point we treated as the fingertip, so the robot pinched the
cartridge by its cap and flipped it. Then: gripping at the centre of mass makes the part
see-saw, gripping high makes it swing like a pendulum. A 110 mm part held at one end is
a lever — small angle errors at the top become large position errors at the bottom.

**Why it matters:** Grasp choice is a design decision that constrains everything
downstream, not a detail. It came back to bite us twice more (wet processes, staging).
On real hardware it also sets how much force you can transmit before the part slips.

---

## 2026-08-02 — Funnels, and why 3 mm of clearance is survivable

**What we built:** Insertion into a socket with only 3 mm of space around the part.

**Peg-in-hole and the chamfer.** Putting a peg in a hole is a classic hard problem,
because the tolerance is tighter than your knowledge of where anything is. Manufacturing
solves it mechanically: a **chamfer**, a funnel-shaped lead-in around the hole. Land
anywhere in the funnel's mouth and sliding down the slope pushes the part to centre. The
*shape* corrects the error so the controller doesn't have to. It's input validation that
coerces instead of rejecting.

**Why it matters:** The cheapest robustness available, and it's free — a shape, not a
sensor or an algorithm. Any real cell should ask "can geometry solve this?" before "can
software solve this?"

---

## 2026-08-02 — The bug that taught us how to measure

**What we built:** The fix taking insertion from 84% to 100% over 200 trials.

**A metric that hid the physics.** We had 84% and assumed four unlucky edge cases. So we
measured something *continuous*: how far the cartridge tilted. Every trial was jamming —
median 21°. Never 84% success — a **100% jam rate with an 84% recovery rate.**

**Integrator windup against contact.** The cause: a law of the form *new target = where
I am + how far off I am*, recomputed each step. When the part is jammed and cannot move
the error never shrinks, so the wrist walks sideways forever and torques the part until
it wedges — a retry loop with no backoff, hammering a service that's already down.

**Why it matters:** Report **margin**, not pass rate. "How close was it to failing?"
finds what "did it fail?" cannot.

---

## 2026-08-02 — Testing on cases you didn't tune on

**What we built:** The evaluation discipline everything since is measured against.

**Held-out evaluation.** A train/test split. Each trial runs from a numbered seed, so
seed 7 always gives the same layout. It is very easy to fix bugs until seeds 0–24 pass
and then report seeds 0–24 — that number means nothing. Ours was worse than we thought:
the original scored 88% on its own seeds and **72%** on seeds it had never run.

**Reproducibility.** The same code and seeds gave 84% on one physics-engine version and
88% on another. Contact-rich physics isn't portable across versions, so dependencies are
pinned — a success rate without an engine version isn't a claim.

**Why it matters:** Every number we give the founder must be one we'd still get on cases
we didn't tune against. This rule has caught an overclaim four sessions running.

---

## 2026-08-02 — Getting a locked part back out

**What we built:** The swap cycle — remove a twist-locked cartridge, bin it, fit a new one.

**Bayonet mounts and captive parts.** It locks like a camera lens: push in, twist 55°,
two tabs slide under a rim. It then physically cannot be pulled out — we yanked with five
times its weight and it moved 3 mm. So removal has a mandatory ordering.

**Torsional slip — close the loop on the workpiece.** The only grip is the cap, and
turning by a small friction patch loses grip: wrist turned 79°, part turned 66°.
**16–18% vanished.** Dead-reckoning "I turned 55°" leaves you 10° short and jammed. It
works because the robot watches *the cartridge's* angle, not its own wrist.

**Why it matters:** Measure the thing you care about, not the thing you're holding.
Every real gripper slips; the question is whether the loop notices.

---

## 2026-08-02 — Teaching it to look at something

**What we built:** Camera inspection grading a cartridge clean, lightly scaled, or damaged.

**Actually doing image processing.** The easy fake: set a variable "this one's dirty,"
colour the part, have the "classifier" read the colour back — a lookup with extra steps.
Instead scale is real geometry: 44 deposits, a random subset visible per trial, so the
classifier must measure the picture. It separates part from background and scores deposit
coverage plus texture (how blotchy it is) — simple enough to explain to a customer.

**Occlusion.** One camera sees one side; deposits on the back look clean. A second view
180° round took accuracy 87% → 93%, free, because the wrist can just spin.

**Why it matters:** Vision is what makes this a robot making decisions rather than a
machine repeating motions.

---

## 2026-08-02 — A model is only as good as the jig holding the part

**What we built:** The fix that made the classifier trustworthy inside the real cell.

**Calibration must match deployment.** The classifier scored **90% on a test rig** and
**53% in the cell**, its dangerous error — dirty passed as clean — hitting 35%. The model
never changed. The rig teleported the part into place; the cell has the arm holding it,
and we took presentation height from an *assumed* grip offset. It sat 31 mm high.

**Asymmetric errors.** Mistakes don't cost the same. Dirty-graded-clean puts a bad part
in a customer's unit; clean-graded-dirty wastes a cartridge. We report them separately
and tune toward the safe one: **false-clean is 0%**, residual error is over-treatment.

**Why it matters:** Test perception through the motions you'll deploy with, and know
which error is expensive before optimising anything.

---

## 2026-08-02 — Fixtures — let the bench do the work

**What we built:** A staging nest that finally let a cleaned cartridge be reinstalled.

**Fixtures and compliance.** The cap grip is fine for a 5-second carry but drops the part
~7 s into a wet process. The answer wasn't a better controller, it was **a shaped piece
of metal.** A nest — a cup with a funnel rim — lets the robot set the part down roughly
and the shape stands it upright; it re-grips by the body. Tolerates 8 mm, 8° of tilt.

**Size to the largest feature.** We sized the nest to the 21.5 mm body and forgot the
lugs stick out to 34 mm. The simulator reported the interference as exactly −7.0 mm.

**Why it matters:** The instinct to fix everything in software is expensive. Ask what
shape makes the problem disappear — and do wet or dynamic work *after* getting a good
grip. You don't hold a jar by its lid to wash it.

---

## 2026-08-02 — Proving a check can actually fail

**What we built:** Verification that cleaning worked, by re-photographing the part.

**Falsification testing.** After washing, the cell re-inspects and must see the part
clean. It reported 100%, which alone is meaningless — a check that always passes is
indistinguishable from a check that *cannot* fail. So we **sabotaged the cleaning**,
leaving the dirt in place, and asked whether the check caught it. It wrongly passed 2 of
5: it used one camera view where the main inspection used two. Fixed, it now catches 5
of 5. This is mutation testing, applied to a robot.

**Why it matters:** Any number claiming something was "verified" needs a run where that
thing is deliberately broken. Otherwise you've measured your own optimism.

---

## 2026-08-02 — How much wrongness can it survive?

**What we built:** A robustness envelope — exactly how much error breaks the cell.

**Domain randomization.** Every number so far came from *one* set of physical parameters
we chose — trivially overfittable. So we vary them per trial: mass ±20%, friction ±30%,
and the bench shifted ±5 mm while commanded heights stay put — a **calibration error**,
the commonest reason a working cell stops working on Monday. Fuzzing, for physics. Result
is a spec, not a score: perfect to **±2.5 mm**, breaks down at ±10 mm.

**Compliance beats precision in contact.** We tried the "obvious" fix — aim picks at a
*measured* height rather than a fixed one — and it made things **worse**. A pick ends in
contact, where bumping the surface beats aiming precisely.

**Why it matters:** "It works" isn't a claim; "works within ±2.5 mm" is one a customer can check.

---

## 2026-08-02 — Turning a script into training data

**What we built:** Export of every successful run as data a learned policy can train on.

**Imitation learning, and what a demonstration is.** The goal is a **learned policy**: a
network that watches camera images and outputs joint commands, trained by copying
demonstrations. A demonstration pairs *observations* (camera frames + joint positions)
with *actions* (the joint positions commanded next), in **LeRobot** format.

**The trap we checked for:** action must genuinely differ from observation. Log the
measured position as both and you train a policy to predict where it already is — silent
and fatal. Verified a real 0.016 rad gap.

**Why it matters:** Scripted rules only handle what we anticipated; a learned policy is
how this survives cartridges we never modelled. Data is the bottleneck, so we start now.

---
