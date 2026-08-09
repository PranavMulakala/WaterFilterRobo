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

## 2026-08-04 — The robot kept changing its mind about how to stand

**What we built:** the fix that closed the cleaning station. Coverage went 94.6% → 100%,
and the force problem we'd been treating as separate vanished at the same moment — because
it was never separate.

**A robot arm with seven joints can reach the same point in many different ways** — same
hand position, same tool angle, elbow somewhere else entirely. Ours has seven. When we
asked it to touch a spot, our planner solved the maths and took the first answer it found.

**The trouble is we ask 400-odd times per device**, wiping in a grid 27 mm at a time. And
each time it solved from scratch, so two neighbouring spots could get two completely
different postures. Moving between them meant a huge contortion for a tiny step: at worst,
**five and a half radians of joint rotation to move the pad 37 millimetres**. The arm
couldn't finish that in the time allowed — and while attempting it, it dragged the pad in a
wide arc across the device. That arc is what was slamming the pad into things and spiking
the contact force.

**The giveaway was sitting in a table we'd already printed.** Of the five wiping passes,
one had *zero* of these jumps — and it was the only pass that had ever worked properly. Four
had dozens. When one instance of a repeated thing works and the rest don't, compare the
instances before theorising.

**The fix is one sentence: prefer the posture closest to the one you're already in.** Only
go looking further afield if there's no nearby answer. Everything moved at once — every
patch cleaned, contact force in range 99% of the time, peak force down from 271 N to 111 N.

**Why it matters:** we'd been treating "misses spots" and "presses too hard" as two
problems and had a separate plan for each. They were one. That's worth remembering: when
two symptoms resist separate fixes, check whether they share a cause before building two
solutions.

## 2026-08-04 — "Tested up to 60" doesn't mean "fine at 60"

**What we built:** the answer to a question we'd been dodging. Our wiping pad's squashiness
had been measured up to 60 newtons of force, and the robot was briefly hitting 111. So we
measured further.

**The curve doesn't tail off past 60 — it falls apart.** Up to 60 N the pad squashes a
sensible 2.2 mm. At 80 N our simulation says it squashes *20 mm* — twice as deep as the pad
is thick, i.e. straight through itself. Above that the numbers wander around meaninglessly.
So "validated to 60 N" never meant "we know it's fine to 60 and probably a bit beyond". It
meant "past here, the simulation is making things up."

**The tempting answer was to argue.** The 111 N was genuinely a blip — four hundredths of a
second out of five minutes of contact, and the pad wasn't visibly misbehaving at that
instant. It would have been easy to write a paragraph explaining why that's acceptable. But
*rarely* inside a region where your model is nonsense is not the same as *outside* it, and
that's not a distinction you want under a customer demo.

**So we fixed it instead**, and it cost nothing. The high-force moments all came from the
arm making an awkward contortion between two wiping spots and dragging the pad. Telling the
planner to skip those spots rather than attempt them dropped the peak from 111 N to 34.5 N
— comfortably inside the trustworthy range — with **no loss of cleaning at all**, because
the pad is wide enough that those spots were already covered by their neighbours.

**Why it matters:** the ceiling of a test is a fact about how far someone bothered to test,
not a fact about the hardware. If you don't probe past it, that number quietly gets quoted
as a rating. Our check now deliberately tests to 200 N and *prints where it breaks*.

## 2026-08-04 — Building a screw thread out of two simpler joints

**What we built:** the membrane station — screw the cap onto the filter housing until it's
properly tight, pressurise it, dip it, and watch for bubbles. Ten units: every one
tightened correctly and passed, and every deliberately-loosened one was caught.

**Their cap is not our cap, and we keep saying so.** Everything we'd built before twists a
part a fixed 55° and locks it — like a bayonet lightbulb. DrinkPrime's real cap is a
**screw thread**, wound down several turns and stopped when it's tight *enough*. Same
family of task, genuinely different motion, and we label it that way every time.

**The physics engine has no "screw".** It has hinges (rotate) and sliders (travel), so we
tied one to the other: for every turn, move down 2 mm. That single constraint is a thread.
The cap now winds down about ten turns and squashes a rubber O-ring, exactly as the real
one does.

**"Tight enough" is a force, not an angle** — and that's the interesting part. We don't
tell it to stop after N turns; we drive it until it *can't turn any more*. Real assembly
tools work this way, which is why a torque wrench clicks. What we report is what the tool
achieved: turns completed and the torque it stopped at. Detecting that stall took one
insight — watch how fast the cap is still *descending*, not how fast it's spinning. Descent
collapses 30-fold the instant it seats; spin just tails off vaguely.

**The bubbles are honest fakery, and the label is part of the work.** We simulate no air
and no water. Bubbles appear when the cap is under-tightened — a modelled consequence, not
computed physics. What stays real is that the camera has to actually *see* them to fail the
part, so the verdict is caused by the tightening rather than read from a variable. The demo
says this on screen.

**Why it matters:** the honest version of a demo is often "this bit is real, that bit is a
stand-in, here's the line between them." Drawing that line explicitly is what makes the
real bit believable.

## 2026-08-04 — Wiring the three stations together, and the decision we refused to make

**What we built:** the full loop. A used unit is graded, and its grade picks its route:
a light clean, or a clean plus a membrane rebuild, or out of the line entirely. Twenty-eight
fresh units, every one executing its route without a mechanical failure.

> **Corrected 2026-08-05.** This entry originally said *"every one routed correctly and
> completed."* That was false: one of the 28 was graded wrong, and the metric could not
> see it. The real figures are below, in *"The score that was grading its own homework."*

**The interesting part is the route we deliberately don't finish.** DrinkPrime's own chart
splits the worst grade in two: units worth repairing, and units to scrap — decided on
whether the repair would cost more than about 80–90%. Of what, none of their documents say.
We have no cost model, no price list, no labour rate. So the cell **doesn't decide**. It
hands those units off to a human approval gate and stops, and "routed correctly" for them
means *flagged for a person*, not *repaired*. (In the simulation that hand-off is a
decision, not a movement — nothing physically carries the unit anywhere.) Building a robot that guesses at a scrap
decision would be worse than building one that hands it over.

**A subtle failure when two stations met.** One station asked the simulator where the
device was *before* the simulator had worked out where anything is — so it got back a
device sitting at the origin, half its real height. The inspection station then looked for
the unit in the wrong place and condemned a spotless one as scrap. The clue was that both
paths agreed exactly on what the unit really was and disagreed on the verdict — when the
inputs match and the answers don't, the difference is hidden state nobody passed in.

> **Corrected 2026-08-05.** This originally described two stations each keeping its own
> "internally consistent" height, 0.22 m and 0.46 m, with thresholds tuned on half a face.
> Backwards: there was only ever one correct height (0.46 m), 0.22 m was an **uninitialised
> read**, and the thresholds were always full-face. Paragraph above is the corrected one.

**What that score does not mean.** Our grader is 97.5% accurate, so in forty units you'd
expect about one mistake. The end-to-end number can never beat the grader feeding it. We
report it that way.

**Why it matters:** a pipeline's honest score is the weakest link's score, and its honest
scope stops where its knowledge does.

## 2026-08-04 — The camera is part of the experiment

**What we built:** the video. A full cycle — grade the unit, clean it, check the clean,
rebuild the membrane, pressurise, dip, watch for bubbles — with a readout on screen showing
the real measurements as they happen.

**Every station puts its own caveat on the frame.** When the dip is on screen, the frame
says *bubbles are modelled from torque, not a fluid simulation*. When cleaning is on screen
it says no detergent is simulated. When the grader is on screen it says the class names are
the customer's but the boundaries are ours. If a caption would need a spoken footnote in the
room, it belongs printed on the picture instead.

**We wrote the video last on purpose.** No part of this cell could be filmed until it had
been measured. A video is a claim, and the evidence should exist before the claim does.

**Then the video nearly broke the thing it was filming.** The first dip shot was badly
framed, so we swung the camera round for a better angle. The next render failed a filter
housing that we had *just* watched tighten correctly and seal — a false failure, on a test
that had reported none all day.

The reason is worth keeping: **that camera isn't scenery, it's the measuring instrument.**
The bubble test works by counting bright pixels in a window projected from that exact
viewpoint. Move the camera and the window lands somewhere else — in our case on bright
water and a bin edge, which it dutifully counted as bubbles.

So the fix wasn't to re-tune anything. It was to give the video **its own camera**, and put
the measuring one back exactly where it was.

**Why it matters:** we already knew a vision result is only as good as the rig presenting
the part — that lesson cost us 37 points of accuracy earlier in the project. This is the
same lesson from the other end. If a number depends on a camera, that camera is apparatus.
Compose your shot with a different one.

## 2026-08-05 — The score that was grading its own homework

**What we built:** a fix to how the cell scores itself — its end-to-end number now checks
the unit went down the *right* route, not merely that it finished the route it chose.

**The concept: a test must compare against something the system does not control.** The cell
graded each unit, picked a route from that grade, then scored itself on "did I do every step
of the route I picked?" — marking its own paper against its own answer key. A misgraded unit
sailed through: wrong route, every step perfect, full marks. The missing comparison is the
unit's *actual* condition, which the cell does not choose. Adding it turned a published
28/28 into 27/28; 28 fresh units give 26/28, both misses cautious ones (sent to a human).

**Why it matters:** the same trap is everywhere on real hardware. "The gripper reached its
target" is not "the gripper reached the part." Any number where the robot supplies both the
question and the answer is a number that cannot fail.

## 2026-08-05 — A step that passes by being named

**What we built:** an evidence label on every step of the route — measured, proxy, or
unbacked — printed on every run, so a step with no motion behind it can't hide in a 28/28.

**The concept: naming an action is not performing it.** The cell records what it did as a
list of words and scores itself by checking that list matches the plan. Two of those words
have nothing behind them — nothing picks up or fits the membrane element, and nothing
carries a reject unit anywhere. The robot writes "MEMBRANE_INSERT", and the evidence the
step happened is that the word is there. Each step now declares what decides it: a measured
force, a modelled stand-in, or nothing. The headline numbers didn't move; the honesty did.

**Why it matters:** on real hardware the gap between *logged* and *happened* is where
silent failures live. A log line is written by the code that intended the action — not by
the world that received it.

## 2026-08-05 — The step the robot could not have done

**What we built:** the membrane insert, for real — the arm picks the filter element off its
nest and places it in the housing, 10/10, aligned to a third of a millimetre.

**The concept: check the part can physically get there before blaming the robot.** This step
had been faked for weeks. Implementing it, we found the cap sits 20 mm above the housing
mouth and covers it completely, while the element is 72 mm long — no path in at any accuracy.
Lifting the cap clear doesn't help: the gripper needs that exact space. The fix was the order
a person uses — housing open, element in, cap on after. What made the motion work: measure
the PART not the wrist, and travel OVER a workstation rather than through it.

**Why it matters:** "the robot can't do it" and "the world won't allow it" look identical in
a failure log, and only one of them is fixed by better control. We burned two prototypes
tuning a grip that was never going to fit.

## 2026-08-05 — The demo that quietly stopped filming the real thing

**What we built:** a fix to the video, which had started filming a machine that no longer
existed — and a seating test tied to the gap the part actually has to fit through.

**The concept: a demo that re-implements the system stops being evidence of it.** Making the
housing arrive open so the element could go in didn't reach the video, because the video
COPIED the tightening loop instead of calling it — so it filmed an empty housing and
"tightened" a cap that was invisible and collided with nothing, over a caption reading
STALLED that was printed unconditionally. It now calls the same routines the measurements
do. Related: our seating test allowed 6 mm of error in a hole with 1.5 mm of room.

**Why it matters:** a demo lies in two ways — showing what didn't happen, and passing a test
that could not fail. Both were live here, and both were invisible from the output, which
looked flawless.

## 2026-08-05 — The robot was cleaning everything twice

**What we built:** a cleaning pass a third faster — 4 min 15 s to 3 min 7 s per unit — at
the same 100% coverage and slightly *lower* contact force.

**The concept: measure where the time goes before you make anything faster.** The obvious
suspects were the fiddly bits — swapping tools, turning the table, moving between faces.
Timing showed those are **7%**; the pad on the surface is **91%**. So all that matters is
how many places it stops. The pad cleans a 60 mm circle but the robot stepped only 28.5 mm
— covering every spot about **twice**. Widening the step to what the geometry needs removed
a third of the stops. We then tried *moving the arm faster* and it barely helped: each stop
must hold still briefly to confirm the pad is pressing, so a faster arm just waits.

**Why it matters:** the instinct is to speed up the moving. The time was in *how many
times it stopped* — a number nobody had questioned since it was written.

## 2026-08-05 — Cleaning only where the dirt is, without losing the guarantee

**What we built:** an opt-in fast cleaning mode — wipe only where the camera saw dirt, then
a second camera checks and re-cleans anything left. Full cycle 3:51 → 2:33; on 24 fresh
units zero residue, and sabotaged cleaning was caught 15 of 15 times.

**The concept: a shortcut is safe only if a separate check can catch its mistakes.**
Skipping clean areas is a bet that the camera saw everything. The bet is covered two ways:
we wipe a small *band* around each dirty spot (a tilted pad sometimes presses edge-first
and misses the exact spot — a neighbour's pass gets it), and after cleaning, the verify
camera looks again and sends the arm back — escalating to a full wipe of any face that
still fails. The final word always belongs to the check, never the plan.

**Why it matters:** every fast path needs an independent judge. Our worst bug was our own
speed tweak (cutting a settle pause) — fast changes must re-earn every number downstream.

## 2026-08-09 — Wiping instead of pecking, and why it only bought 1.4x

**What we built:** the arm now *sweeps* each face in one continuous motion instead of
stopping at all 323 points. Full-coverage cleaning 3:07 → 2:17 per unit, with coverage
still 100% on 16 fresh units (0 spots missed of 256), the hardest press *lower* than
before (32.2 N vs 32.9 N), and sabotaged cleaning still caught 10 times out of 10.

**The concept: a robot that stops to check has to prove it arrived; one that sweeps has
to prove it stayed on the line.** Stopping at a point is safe because you can wait until
the arm is measurably there. Sweeping removes that check, so the risk moves: the arm now
lags behind the path it was told to follow, and a lagging arm drifts *sideways* on turns.
We measured that drift — about 3 mm typically — and found it grows with speed until, past
100 mm/s, the pad's swept band shifts enough to leave gaps. **So there is a speed cliff,
and it is a cliff, not a slope: 100 mm/s misses nothing, 150 mm/s starts missing spots.**
Two standard machining tricks keep it honest — slow down into corners, and let the path
curve smoothly through the points rather than blending across them.

**Why it matters:** we hoped for 2x and got 1.4x, because the advisor's estimate assumed
the arm could sweep as fast as we liked. It can't — accuracy sets the speed limit, and
the limit is a measured number, not a guess. Also worth knowing: this and last session's
"only clean where the dirt is" attack the *same* wasted time, so doing both gains nothing.
