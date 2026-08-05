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

## 2026-08-04 — Why we said no to sticky tape

**What we built:** The real DrinkPrime process, transcribed from their own 13 work
instructions, and an explicit line through it marking what a robot can and cannot do.

**Rigid vs deformable.** To handle an object you need to know where it is. For a rigid
object that is six numbers — three for position, three for how it is turned — and they
are enough forever, because the shape never changes. A strip of Teflon tape, a sticker,
a wiring harness, a length of tubing has **no fixed shape**: it sags, stretches, sticks
to itself, and changes as you touch it. There is no small set of numbers to plan
against, and your camera cannot recover one. This is why "wind tape 20–30 turns onto a
thread" is a research problem while "put this cylinder in that hole" is an afternoon.
It isn't about how fiddly the job looks to a human — humans are *good* at floppy things.

**Same class, different motion.** Their membrane cap screws down under a spanner; ours
twists 55° like a camera lens. Both are "secure it by rotating," so what we learned
transfers — but the motions are not interchangeable, and saying they are would have
been caught by the customer reading their own document.

**Why it matters:** Knowing which steps are impossible *today* is worth as much as
making some steps work. It sets the boundary of what we can honestly sell, and it means
nobody buys an arm for a job it cannot do.

## 2026-08-04 — The diagram was the specification

**What we built:** A corrected model of DrinkPrime's real process, after finding our
first version had invented part of it.

**Extraction has a modality, and the wrong one fails quietly.** Their quality-control
process is a flow chart: boxes joined by arrows. We pulled the text out of it. Text
extraction returns every *label* and not a single *arrow* — so we got all the nouns and
none of the structure. Little oval notes reading "refer to Annexure 4" attach to a box by
a drawn line; with the lines gone, each note glued itself to whichever label happened to
sit nearest in reading order. **Eight of thirteen landed on the wrong box.** Nothing
errored. We got back a confident, well-formed, wrong process — including the belief that
a document called Annexure 1 defines their Easy/Medium/Hard grading, when it actually
covers cabinet scratches three steps later. That belief was about to become a question we
asked the customer.

**The fix is embarrassingly simple: look at it.** Render the page as a picture and read
it the way a person would.

**Why it matters:** We keep learning the same lesson in new costumes — measure the part,
not the gripper; calibrate through the real motion path, not a rig. Now: read the
document in the form it was drawn in. Every one of these is the same mistake, which is
**checking a proxy and believing you checked the thing.** The proxy is always cheaper,
always available, and never announces that it dropped something.

## 2026-08-04 — Can the arm even reach it? (and four bugs that said yes when it couldn't)

**What we built:** The scaled-up scene — a whole water purifier on the bench instead of a
110 mm cartridge — plus the study that checks the arm can actually work on it.

**Workspace.** An arm doesn't have a "range" like a person's. It has a *workspace*: a
3D region it can get its hand into, and at each point only some hand *angles* are
possible. So "can it reach the front of the cabinet?" is really "can it get its hand
there, pointing the right way, without folding into itself or hitting anything?" We
tested that before building anything, because if the answer is no, everything after it
is wasted. The answer turned out to depend almost entirely on **where the device sits on
the bench** — slide it 200 mm and front-face coverage goes 79% → 100% — and almost not
at all on how big the device is. So the cabinet dimensions we're still waiting on from
DrinkPrime aren't blocking us. The bench layout was the real question.

**The uncomfortable part.** The study said "10% coverage, fails". Then it said 83%. Then
0% on one face. Every one of those was a **bug in the test, not in the robot**: a camera
told to stand twice as far back as it needed, a face whose measurements were taken 35 mm
inside the solid box, a scenery panel that was invisible to us and a wall to the robot,
and an error message that said "can't reach" about a point it reached perfectly and was
merely bumping into. Four different ways to get a confident, wrong number.

**Why it matters:** A failing test is a claim about the world, and it can be wrong in
both directions. The habit that saved us is cheap: when a number surprises you, go and
*look* — render the picture, print the contact list, check the box is where you think.
Every bug above was invisible in the numbers and obvious in a screenshot.

## 2026-08-04 — The cheapest fix was a turntable

**What we built:** A rotating stage under the device — and the specification document
you'd hand to whoever builds the real cell.

**Some problems aren't controller problems.** The arm couldn't reach the back of the
cabinet. Not "struggled" — *couldn't*, from every one of eight positions we tried, at
every point on the face. And separately, the camera could either see the device from
well-separated angles **or** the arm could clean its front face properly, but not both:
moving the device closer helped one and hurt the other. Two problems, one cause — a part
that can't move can only be approached from the side the robot lives on.

**So we moved the part instead of the robot.** A low rotating platter under the device,
about the cost of a nice laptop, and every face turns to meet the arm in the one position
where it works best. Back face: 0% → 100%. The camera trade-off disappears entirely.
This is completely standard — it's what welding positioners and paint booths do — we
just had to stop trying to solve it with cleverness.

**Why it matters:** This is the same lesson as the funnel that guides the cartridge into
its socket, and the nest that holds it upright. **Ask what shape or mechanism makes the
problem disappear before writing a controller.** Three times now the answer has been a
piece of metal, not code. And a specific, costed piece of hardware ("you need a ~£1K
indexing table") is a far more useful thing to hand a customer than a success rate.

## 2026-08-04 — We asked four robots to attack our own work

**What we built:** Nothing new — we spent a run trying to break what we'd just built, and
succeeded twenty-two times.

**Adversarial review.** Rather than re-reading our own work (where you see what you meant,
not what you wrote), we set four independent reviewers on it with different jobs: check
every number against the simulation, hunt for physics bugs, find contradictions between
documents, and hunt for overclaiming. Then a second pass tried to *disprove* each
complaint, so only the ones that survived counted. Ten were wrong and got thrown out;
twenty-two were real.

**What it caught.** The wiping pad **crushed straight through its own mount** under a
normal press — 18.6 mm of squash on a 10 mm pad — so the tool we'd specified couldn't
exist. A decorative strip on the cabinet front was **burying seven of the dirt marks the
camera is graded on**, invisible from every angle; accuracy would have been capped for a
reason that looked like a vision problem and wasn't. The device weighed **21 kg** because
nobody set a weight and the simulator helpfully filled the box with water. And a reset
routine we'd inherited **teleported the pad tool into the bench** — a bug we had already
written down years-of-project-time ago, in a file, where it sat being true and doing
nothing.

**Why it matters:** That last one is the lesson. **A gotcha you documented is not a gotcha
you fixed** — documentation doesn't run. Everything caught here is now an automated check
that fails loudly. And the honest count for the day is thirteen bugs, every one of them in
our own measuring equipment rather than in the robot.

## 2026-08-04 — A result we didn't want, and why we kept it

**What we built:** The triage station — a camera that grades an incoming device
Easy / Medium / Hard. It half works, and the half that fails is worth more than a good
score would have been.

**The number: 55% correct.** Every badly-damaged unit was caught, 38 out of 38. Nothing
needing real work was ever waved through as fine. But the classifier **never once said
"Easy"** — it sends every cosmetically-fine device off for repair it doesn't need.

**Why we're not going to tune that away.** We checked *why* it fails, and it isn't the
setting we chose — it's the measurement. The "amount of scratching" we compute overlaps
between the easy units and the medium ones, so **no setting exists that separates them.**
A knob can't fix a ruler that can't tell the two apart. Fixing it means measuring
something different — counting individual scratches rather than totalling up scratched
pixels.

**The trap we walked into first.** We fitted the settings on 45 practice devices and got
89%. On devices it had never seen: 73%. The instinct is to think the 73% is unlucky. So
we re-fitted on 100 practice devices — and the practice score fell to **74%**. The 89%
was the lie; it was two settings tuned to 45 examples. **When your practice score and
your real score disagree, get more practice data and watch which number moves. The one
that moves was never real.**

**Why it matters:** We are failing on the one boundary DrinkPrime never defined — we
invented where "just needs a clean" ends and "needs scratch repair" begins. Failing there
is a reminder that we're being graded against our own guess. That's the strongest argument
yet for asking them how their people actually make this call.

## 2026-08-04 — Count the things, and don't measure them with a square

**What we built:** The triage grader again, properly. It went from 55% to **90%** correct
on 120 devices it had never seen — and the whole gain came from two ideas, not from tuning.

**Count what the label counts.** The grade is defined by *how many* scratches and dents a
device has. The first version measured the *fraction of the picture* that looked scratched
— a different quantity that happened to correlate. It correlated badly: lightly-scratched
and heavily-scratched devices produced overlapping fractions, so **no cut-off could ever
have separated them.** Switching to counting individual defects fixed a problem that no
amount of adjustment could.

**A diagonal line has a square box around it.** To tell a scratch from a dent we asked "is
this mark long and thin, or blobby?" — by measuring the box drawn around it. But a 40-pixel
scratch lying at 45° has a 30×30 box: perfectly square, so we called it a dent. Our
scratches sit at random angles, so **most of them fooled it.** Measuring the shape itself
rather than its box took the count error from ±3 defects per device to ±0.4.

**Why it matters:** Both bugs are the same mistake in different clothes — measuring
something *adjacent* to what you care about. And note the failure was silent: a
misclassified scratch is still a detected mark, so nothing looked broken. It only showed up
because we compared our counts against the truth, defect by defect.

**Honest footnote:** we could probably reach ~100% here, because we defined the categories
with clean gaps between them. That would prove our counter counts, not that the problem is
solved. The real test is DrinkPrime's own criteria, which we still don't have.

## 2026-08-04 — The robot needed a spring, not better aim

**What we built:** A compliance unit between the robot's wrist and the cleaning pad — and
before that, a proper tool coupling. Cleaning coverage went 0% → 65% across the day.

**Holding a tool is not the same as gripping a part.** We first had the robot pick the
wiping pad up in its fingers. It pivoted: a round shank in parallel jaws can rotate, and
the pad swung most of a right angle the moment the wrist turned sideways. We squared off
the shank — better, but it still crept 60–70 mm across a single face. The giveaway was
that squeezing *harder* didn't help, and pressing *lighter* didn't either. **When a fix
is insensitive to the knob you think controls it, the knob isn't the problem.** Real cells
don't grip process tools at all; they use a *tool changer* that locks mechanically. With
one modelled, movement dropped to 0.16 mm.

**And then the forces got worse — which was correct.** A position-controlled arm can only
be told *where* to go, not *how hard* to push. Ask it for a spot 2 mm inside a wall and it
will lean on that wall as hard as it takes. Our sloppy grip had been hiding this by
slipping; with a rigid tool, the arm's ~1.5 mm of aiming error landed straight on the
contact force — 58 N of scrubbing pressure.

**The fix is a spring, and it's a real product.** Put a sprung axis between the wrist and
the pad and the force stops depending on aim: the pad simply retracts. 3 mm of aiming
error now costs 2 N instead of tens. Force went 58 N → 17 N, and stayed in range 96% of
the time.

**Why it matters:** the cell needs *two* components where we assumed one — a changer for
**position**, a compliance unit for **force**. Neither is exotic; both are catalogue parts
used by every polishing and sanding cell. Knowing you must buy them, before you buy
anything, is the sort of answer this simulation exists to produce.

## 2026-08-04 — We were tuning the wipe. The robot was never getting there.

**What we found:** V5-C's cleaning coverage sat at 64.7%, and the obvious reading was
"press harder, raster tighter." We built instruments instead. Coverage was never the
problem: the arm fails to reach its commanded position through almost the whole cleaning
cycle, missing by 100–400 mm, and one of the five faces is never presented to it at all.

**A robot arm can collide with itself.** Reaching a point isn't one problem, it's two:
*can the hand get there*, and *can the rest of the arm get out of its own way*. Our wrist
was jammed against the shoulder hard enough that one motor sat pinned at its torque limit
for the entire move. The arm was straining against itself, and the only visible symptom
was a coverage percentage.

**Why it happened is a lesson about planning before you have the part.** Back when we
studied whether the arm could reach the cabinet, we assumed the wiping tool would hold the
wrist 45 mm off the surface. The tool we then actually built is 105 mm long. Those 60 mm
push the wrist *toward the robot's own base* — the one direction it cannot go. Same study,
same solver, one honest number changed: the two side faces go from mostly reachable to
almost entirely unreachable.

**And a green light was measuring the wrong thing.** Our reachability check passes because
it allows the pad to meet the surface at up to 30° off square — fair, since the pad is
soft and conforms. But the cleaning program always approaches dead square and never uses
that allowance. So the check was reporting on a robot that tilts, and we shipped one that
doesn't. Nothing connected the two.

**Why it matters:** the fix isn't a better wipe, it's admitting the tool changed the cell.
Real cells discover this when the tooling arrives and nothing reaches — we found it for
the price of an afternoon and a measuring script.

## 2026-08-04 — Look before you move: the robot now plans, then drives

**What we built:** the five fixes for the cleaning station. Coverage went **64.7% → 94.6%**
on units the code had never seen, with every raster point now actually attempted.

**The big one: stop steering, start planning.** The arm had been steering toward each
target the way you'd nudge a cursor — take a small step in roughly the right direction,
repeat. That works until the arm folds against itself, and then it is stuck, because
nothing in "step toward the goal" knows the goal is behind its own shoulder. Now it
*solves* for a whole arm posture first, checks that posture for collisions and for joints
jammed at their limits, and only then drives to it. Plan error at every point: zero.

**A planner has to know what the robot is carrying.** Our first version could not see its
own wiping pad — the pad is attached by a simulated latch rather than being part of the
arm, so when we asked "where would the arm be in this posture?", the pad stayed behind.
Which meant nothing checked whether a 60 mm pad would clip the turntable. It does now.

**"Get within 4 mm" is not a thing a loaded arm can promise.** At full stretch, less than
one degree of droop in a single joint is 14 mm at the hand. So the robot kept waiting for
an accuracy it could never reach — leaning on the cabinet at full pressure for two and a
half seconds at every single point. We now stop when the pad is properly seated *and has
stopped getting closer*, which is what "the wipe is done" actually means.

**Why it matters:** every one of these is the same shape — the machine was measuring
something adjacent to what mattered. And we kept the 94.6% rather than a 100% we could
have had by pressing longer and harder, because coverage bought with force is not
coverage.

## 2026-08-04 — We built a test that couldn't fail, and it passed

**What we built:** the check that proves the cleaning worked — re-photograph the unit
afterwards and look for leftover dirt — plus a deliberately sabotaged run to prove the
check can catch a dirty one. The first version passed every test we set it and was
worthless.

**The setup.** Clean ten units properly, and clean ten more with the wiping switched off
while the arm still goes through every motion. The check must pass the first ten and fail
the second ten. It did: 10 out of 10 both ways. That was the target we'd written down
months earlier, hit exactly.

**Then we asked a different question: of the units it passed, how many were actually
clean?** One. Nine of the ten it had just certified still had dirt on them.

**Why, and it is the kind of thing you only find by looking.** The camera sits slightly
*below* the top of the device, so it cannot see the top surface at all — it photographs
the four sides. And the top is exactly the surface our robot cleans worst, because it's
the hardest place for the arm to reach. **The machine fails in the one place it cannot
look.** Sabotage everything and the check still catches it, because enough dirt lands on
the sides. Sabotage nothing and it waves through the real failures.

**The fix was a second camera**, mounted above and to one side. False passes went from
nine in ten to zero. And the "success" rate of the honest cleaning *dropped* — which is
the check becoming truthful, not getting worse. Those units were always dirty.

**Why it matters:** the customer's actual standard is "any missed spots" — pass or fail,
per device. By that standard our cleaning station scores **6 out of 10**, not the 94.6%
of surface area we'd been quoting. A percentage averaged over a device can look excellent
while the thing fails every other unit. And a test that has never failed is not a test
you've passed — it's a test you haven't finished writing.
