# Results — v3 Refurbishment Swap Cycle

**100% of full swap cycles completed, across 125 randomized trials.**

A "swap" is the complete refurb operation: remove the spent cartridge that is already
twist-locked into the unit, bin it, then install a fresh one from a randomized pose in
the tray and lock it. A trial counts only if **both** halves succeed.

Produced on MuJoCo 3.11.0 / numpy 2.5.1 / Python 3.12.13 (pinned — see
[requirements.txt](requirements.txt)).

---

## The numbers

| Seed range | Full swap | Old binned | New locked |
|---|---|---|---|
| 0–24 (written against) | **25/25 — 100%** | 25/25 | 25/25 |
| 25–74 (held out) | **50/50 — 100%** | 50/50 | 50/50 |
| 75–124 (held out) | **50/50 — 100%** | 50/50 | 50/50 |
| **Total** | **125/125 — 100%** | 125/125 | 125/125 |

Cycle time ~33 s (roughly two v2 cycles, as expected). Seating accuracy 2.0 mm mean.

**Margins** — the continuous measures, because a pass/fail rate hid a systemic defect
on this project once already:

| Measure | Median | Worst |
|---|---|---|
| Rotation lost to cap slip during untwist | 16% | 18% |
| Peak cartridge tilt during extraction | 8.2° | 9.0° |
| Untwist retries used | 0 | 0 |

These are tight and flat across all three blocks — held-out matches in-sample, which
is the opposite of an overfitting signature.

## Success criteria (not relaxed)

The new cartridge reuses v2's checks **verbatim**: `xy_off < 6 mm`, seated height,
`upright > 0.95`, `rel_twist > 30°`. Two terms were added for the old cartridge:

- `discarded` — inside the bin footprint (< 75 mm) **and** below 90 mm height.
- `removed` — demonstrably out of the socket.

The height and `removed` terms exist because the first draft of the bin check tested
only distance to the bin centre, which a cartridge **still hanging in the gripper**
directly above the bin would have passed. That would have inflated the number
silently.

---

## The interesting physics: the untwist slips, and that's fine

The prediction going in was that extraction would be harder than insertion, for two
reasons — both of which turned out to be real:

**1. There is no chamfer on the way out.** Going in, the 45° funnel mechanically
centres the part; that is the whole reason insertion tolerates a 3 mm clearance.
Coming out there is no lead-in at all: the lugs must thread back up through 3 mm slot
channels. The controller therefore holds the socket axis *exactly* during UNTWIST and
EXTRACT — any commanded lateral motion there is pure downside.

**2. The untwist is torsion through friction on a 22 mm cap.** A small contact patch
transmitting torque. It slips, measurably:

> Seed 0 — the **wrist** turned 79.2°, the **cartridge** turned 65.6°.
> **17% of the commanded rotation was lost to slip.**

Dead-reckoning the wrist by −55° would have left the lug axis roughly 10° short of the
slot, and the extraction lift would have jammed against the collar. It doesn't,
because the yaw servo is closed on the **measured cartridge yaw** — it simply keeps
commanding until the *part* reaches the slot axis, absorbing whatever slip occurs.
The slip became an invisible 16% tax instead of a failure mode.

That is the transferable lesson: **close the loop on the workpiece, never on the
tool.**

## Verification: is the bayonet even real?

A "successful extraction" is meaningless if the part was never actually captive. So
the lock was tested directly before trusting any swap result — pull the seated
cartridge straight up with 15 N (about 5× its own weight):

| State | Result |
|---|---|
| Locked (lug axis 35°) | rises **3.1 mm** and stops — lugs bottom out under the collar |
| Aligned (lug axis 90°) | leaves the socket entirely |

The mechanism genuinely holds. The robot has to untwist it.

## An honest caveat

The anti-windup clamp on the untwist command (`YAW_LEAD_MAX`) was written in from the
start, because a loop closed on a part that *can stop moving*, driving a command that
*can keep growing*, is the same shape as the defect that caused the v2 insertion
wedge. **It never triggered in 125 trials.** That is the desired outcome, but it also
means the guard is untested in anger — exactly the trap the v2 recovery path fell
into, where it looked healthy while never actually firing. Noted rather than assumed.

---

## What this is and isn't

This is the **generic** swap cycle, built while we wait for DrinkPrime's real refurb
process video, tech documents and possibly a physical unit. It demonstrates the hard
manipulation primitive — getting a captive part out of a bayonet mount and a fresh one
back in, unassisted, from randomized poses.

It does **not** yet reflect DrinkPrime's actual refurb steps. Real refurbishment
plausibly involves descaling, filter-media replacement, gasket and seal inspection,
and testing — none of which are modelled, because we don't know them yet. When the
founder's material arrives it will determine whether the swap cycle is the right demo
or **the first scene of it**.
