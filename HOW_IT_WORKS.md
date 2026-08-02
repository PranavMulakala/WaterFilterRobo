# How It Works — a plain-English walkthrough

*Written for people who are not robotics engineers. No prior knowledge assumed.
If you want the code-level detail instead, see [ARCHITECTURE.md](ARCHITECTURE.md).*

---

## 1. What this project actually is

DrinkPrime assembles about **1,000 water purifiers a day** in Bangalore. Somewhere
on that line, a person picks up a filter cartridge and installs it into a housing.
We want to find out whether a robot could do that one job.

Buying a robot arm to find out costs $6,000–$11,000 and weeks of setup. So instead
we built the whole thing **in a physics simulator** first — a piece of software that
models gravity, friction, and collisions accurately enough that if the robot can't
do it in simulation, it definitely can't do it in real life.

Think of it as a wind tunnel. Nobody builds the plane first.

**What you're looking at in this repo:** a simulated UFACTORY xArm7 (a real,
purchasable robot arm) doing the cartridge-insertion job 25 times in a row, with
the part in a different random position and rotation every time, and a score for
how often it succeeded.

---

## 1b. The refurbishment cycle — the current headline

DrinkPrime told us **refurbishment is their biggest pain point**, so that is now the
main thing being simulated. A refurb starts from a *used* unit: the old cartridge is
already installed and locked in place. The robot has to do a full **swap**:

| Stage | What happens |
|---|---|
| **EXTRACT** | Grip the old cartridge's cap, **untwist** it out of its lock, lift it straight out |
| **DISCARD** | Carry it across to a bin and drop it in |
| **INSERT** | Find the fresh cartridge in the tray (random position and rotation) and install it |
| **LOCK** | Twist 55° to lock, then verify |

**It completes 125 out of 125 randomized swap cycles**, taking about 33 seconds each.

Getting the old one *out* turned out to be the interesting half, for a reason that's
easy to miss: **there is no funnel on the way out.** Going in, the cone-shaped lead-in
around the socket physically guides the cartridge into place — that's why it tolerates
a 3 mm gap. Coming out, the tabs have to thread back up through those same narrow
slots with nothing guiding them.

And the untwist has to be applied by **gripping the cap and rotating** — a small
contact patch, turning the part through friction alone. It slips: we measured the
wrist turning 79° while the cartridge only turned 66°, so **about 17% of the rotation
is lost.** If the robot had simply assumed "turn 55° and it's unlocked," it would have
stopped ~10° short of alignment and the part would have jammed on the way up. It works
because the robot watches *the cartridge* rather than trusting its own wrist, and keeps
turning until the part is genuinely lined up.

> A general lesson worth keeping: **measure the thing you care about, not the thing
> you're holding.**

**Important caveat.** This is the *generic* swap cycle. Real refurbishment probably
also involves descaling, replacing filter media, checking gaskets and seals, and
testing — none of which is modelled, because we don't know their process yet. The
founder's process video and tech documents will tell us whether this swap is the right
demo or just the first scene of it.

## 2. The job the robot has to do

The cartridge doesn't just drop in. It's a **bayonet mount** — the same mechanism
as a camera lens or a bayonet light bulb. Two little tabs ("lugs") stick out of the
side of the cartridge near its base. The socket has two matching slots. To install it:

1. **Line up** the tabs with the slots.
2. **Push straight down** through the opening.
3. **Twist** about 55° so the tabs slide under the rim and lock.

Get the rotation wrong by more than a few degrees and the tabs hit solid wall
instead of the slots. That's what makes this a real manipulation problem rather
than a pick-and-place demo.

Here's the full sequence the robot runs, every trial:

| Step | What happens |
|---|---|
| **Perception** | A simulated camera locates the cartridge lying in the parts tray |
| **Approach / Descend / Grasp** | Move over it, come down, close the gripper |
| **Lift / Transit** | Pick it up and carry it over to the socket |
| **Orient lugs** | Rotate the wrist until the tabs point at the slots |
| **Pre-insert** | Hover with the cartridge's base just above the socket opening |
| **Insert** | Lower it in through a 3 mm gap |
| **Drop-seat** | Open the gripper; the part settles onto its seat |
| **Regrip / Twist-lock** | Grab the cap and twist 55° to lock it |
| **Verify** | Check it's actually seated, upright, and rotated |

## 3. Why it's harder than it looks

Three things make this genuinely difficult, and they're worth understanding because
they're the same things that will bite us on real hardware:

**The part is never in the same place twice.** Every trial, the cartridge spawns at
a random position (up to 4 cm off in any direction) and a **completely random
rotation** (anywhere in a full 360°). The robot is not replaying a recorded motion —
it has to look, decide, and re-plan every single time. This is the difference
between a demo and a system.

**The camera isn't perfect.** We deliberately add 1 mm of random error to every
position the "camera" reports, and 1° to every angle, because real cameras have
error. The robot has to succeed *despite* being slightly wrong about where the part is.

**There's only 3 mm of room.** The gap between the cartridge and the socket wall is
about the thickness of two stacked coins. And the robot is holding a 110 mm-long
part by its top — like trying to post a letter while holding the far end of a ruler.
Small angle errors at the top become large position errors at the bottom.

---

## 4. What "84%" or "100%" actually means

We run the whole job **N times from scratch**, each with a different random starting
position — these are called **seeds** (seed 7 always produces the same random layout,
so results are repeatable and we can re-run a specific failure).

A trial only counts as a success if, at the end, the cartridge is:
- within 6 mm of the socket centre,
- sitting at the correct height (fully seated, not perched),
- upright (not tilted), **and**
- rotated more than 30° from where it entered (i.e. genuinely locked, not just resting).

If any of those fail, the trial is a failure. **"84% success" means 21 out of 25
complete runs finished with a properly locked cartridge.**

## 5. The thing we learned that actually matters

The original version scored 84%, and the four failures looked like four unlucky
edge cases to be patched individually.

They weren't. When we measured **how far the part tilted** during insertion — rather
than just pass/fail — it turned out that **every single trial was jamming.** The
typical "successful" run still tilted about 20°, ground against the opening, and
eventually wobbled itself free. The four "failures" were simply the ones that tilted
past roughly 40° and never recovered.

So the real number wasn't "84% success." It was **"100% jam rate, with an 84% chance
of recovering from the jam."** Same score, completely different problem — and a
completely different fix.

> **The transferable lesson:** a pass/fail metric hid the actual physics. Measuring
> the *margin* — how close each run came to failing — is what revealed the real
> defect. This is now the single most useful engineering insight from the project,
> and it's the kind of thing we're logging in [PAIN_JOURNAL.md](PAIN_JOURNAL.md) as
> research for a possible second product.

---

## 6. What simulation proves — and what it doesn't

**It does prove:** the task is geometrically and mechanically achievable by an
off-the-shelf arm; the strategy is sound; we know what the hard parts are; and we can
show a founder a working demo before spending a rupee on hardware.

**It does not prove:** that real cartridge tolerances match our model, that a real
camera will localise the part this well, that real friction behaves like simulated
friction, or that the cycle time survives contact with a real production line.
Simulation is necessary, not sufficient. The standard industry experience is that
sim-to-real transfer always costs more than expected.

**Honest framing for the founder conversation:** this de-risks the *approach*. It
doesn't de-risk the *deployment*.

---

## 7. Where the money question sits

Indian assembly labour runs roughly **$1.50–2.50/hour**. A robot cell has to beat
that, or win on something labour can't offer — consistency, 24/7 operation, quality
records. That maths, not the robotics, is what decides whether this becomes a
business. It's the main thing to get from the DrinkPrime founder call.

---

## 8. Try it yourself

You don't need to understand the code to run it. See the
[Quick start](README.md#quick-start) in the README — it's three commands, and the
last one prints the success rate.
