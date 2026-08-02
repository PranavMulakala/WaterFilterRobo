# Pitch Notes — DrinkPrime

*Working notes for the customer conversation, kept next to the demo so the framing and
the open questions don't live in a text thread. Not a deck. Last updated 2026-08-02.*

> **Confidence marking.** Everything below is tagged:
> **[demo]** = shown by the simulation in this repo, reproducible by running it.
> **[verbal]** = told to us, not yet in writing — treat as a hypothesis, confirm before
> it goes in a deck or a plan.
> **[open]** = we don't know yet.
>
> The single fastest way to damage this deal is to repeat a **[verbal]** number back to
> the customer as if it were established fact.

---

## 1. Where we actually are

**[demo]** A simulated UFACTORY xArm7 completes the full refurbishment swap cycle —
extract a spent cartridge out of its bayonet twist-lock, bin it, install a fresh one
from a randomized pose, lock and verify — **125 out of 125 randomized trials, no
failures**, ~33 s per cycle. Video: [media/refurb_cell_v3.mp4](media/refurb_cell_v3.mp4).
Numbers: [RESULTS_V3.md](RESULTS_V3.md).

**[demo]** The underlying insertion cycle alone: 200/200. It was 88% before this
week's work, and only 72% on unseen cases — that gap is itself a talking point about
how we measure, not just what we built.

**[open]** This is the **generic** swap. It does not model DrinkPrime's actual refurb
steps, because we haven't seen them.

## 2. The commercial shape

The structure worth stating plainly, because it's the whole reason this is interesting:

> **DrinkPrime is the customer, and they run their own plant. The volume story is
> their own growth, not a third party.**

- **DrinkPrime** — Bangalore water-purifier subscription business, **[verbal]** ~1,000
  units/day manufactured. Refurbishment is their **biggest pain point**, and
  **[verbal]** they are **expanding to 100 cities** — which is *why* it's the pain
  point: refurb volume scales with the installed base, not with new sales, so it grows
  faster than everything else and lands on them all at once. **[verbal]** They run
  **their own plant**. Teja knows the founder personally.
- **[verbal]** Funding bar (2026-08-02, explicit): **$20–30K for robot arms** for a
  *complete refurb simulation*, specifically including **(a) image-processing
  inspection of the unit's condition** and **(b) a cleaning step where the arm cleans
  the filter with a solution**. See §3.

So the buyer and the volume are the same organisation. A cell that serves DrinkPrime's
own refurb line across a 100-city footprint is the product — there is no separate
"scale customer" to graduate to, and no third-party relationship to broker.

**[open] Contract manufacturers as a someday-hypothesis — explicitly unvalidated.**
If the cell works for DrinkPrime, the same station plausibly sells to contract
manufacturers of purifiers or filter elements. Nobody has validated this: no named
account, no volumes, no intro path. Keep it out of any deck and out of any
conversation with the founder. It is a note-to-self, not a strategy.

> **Correction, 2026-08-02.** An earlier version of this section named **Ronch
> Polymers** as "the assembler" and "the real scale customer", with **[verbal]**
> volumes of 500K purifiers + 4.5M filter elements/year. **That is wrong — DrinkPrime
> has its own plant.** Removed. Worth noting *why* this is recorded rather than
> quietly deleted: it is the second time in two days that a **[verbal]** figure moved
> materially, which is exactly what the confidence tagging at the top of this file
> exists to catch. Had that number gone into a deck as fact, it would have been
> presented to the founder as a claim about his own supply chain that he knows to be
> false. Keep tagging.

## 3. The two asks (current)

**Ask 1 — define the funding bar, in writing.**
The founder has seen the demo. What *specifically* does he need to see to release
funding? If this isn't it, we want the bar defined before building further. Also worth
pinning: is the $20–30K a grant, a pre-payment against delivery, milestone-based, or
equity? Who signs off, and on what timeline?

*Why it's phrased this way:* asking an open "what's your bar?" with nothing attached
invites an expensive answer. Anchor it against the demo that already exists.

**Ask 2 — the plant process video, tech documents, and a physical device.**
This is the gating item for everything technical. Their real process is what turns a
generic swap into *their* line.

## 4. Open questions for the founder

**Process — what actually happens during a refurb**
- What are the real steps? Descaling, filter-media replacement, gasket/seal
  inspection, testing, cosmetic work — we're guessing at all of these.
- Is cartridge replacement even the *common* case, or one branch of many? What
  fraction of returned units need which treatment?
- What does the unit look like when it arrives — dirty, scaled, damaged, disassembled?
- Is there a test/QA step at the end, and what does it measure?
- Cartridge SKU, real geometry, real tolerances.

**Operations — what "good" costs**
- Current manual process: how many people, what cycle time per unit, what rework or
  defect rate?
- Units refurbished per day vs manufactured per day.
- Cycle-time budget: our 33 s is meaningless without knowing the line's takt time.
- Where physically would a cell go, and what's the floor/power/safety envelope?

**Commercial**
- Labour cost per station per hour, and shifts per day.
- Willingness to pay: capex per cell, or per-unit pricing?
- What would make this a *purchase* rather than a pilot?

## 5. The economics we have to beat

**[verbal, from project context]** Indian assembly labour runs roughly **$1.50–2.50 per
hour**. A robot cell must beat that, or win on something labour can't offer:
consistency, 24/7 operation, auditable quality records, or hazardous/unpleasant work.

This is the honest weak point of the whole thesis and we should raise it before the
customer does. Two framings that survive it:
1. **Quality and traceability**, not labour arbitrage — a refurb line where every unit
   has a recorded, identical process.
2. **Train cheap in India, sell into expensive-labour markets** — the deployment is the
   product, the Indian line is the proving ground.

## 6. What the demo proves — and what it doesn't

Use this verbatim. Overclaiming here is the fastest way to lose technical credibility
with anyone who knows robotics.

**It proves:** the manipulation is mechanically achievable by an off-the-shelf ~$11K
arm; the strategy is sound; we know where the difficulty actually sits; and we can
demonstrate it before spending on hardware.

**It does not prove:** that real cartridge tolerances match our model, that a real
camera localises parts this well, that real friction behaves like simulated friction,
or that cycle time survives a real production line. Sim-to-real transfer reliably costs
more than expected.

**One-line framing:** *this de-risks the approach, not the deployment.*

## 7. Credibility details worth keeping in the room

Small, specific, and true — these land better than adjectives:

- **The untwist slips 16–18%.** Turning the cartridge by its cap loses that much of the
  commanded rotation to friction. Dead-reckoning the wrist would leave the part ~10°
  short of alignment and jam it. We measured it and closed the loop on the part
  instead. **[demo]**
- **We test what we didn't tune on.** The insertion controller scored 88% on its own
  test cases and 72% on unseen ones — we found that by looking, and report both.
  **[demo]**
- **Every trial used to jam.** The original 84% wasn't "four bad cases"; measuring how
  far the part tilted showed a 100% jam rate with an 84% recovery rate. Same score,
  different problem, different fix. **[demo]**

That last one is the strongest signal we know how to measure things properly — which is
what someone should want before funding a robotics team.

## 8. Advice we're working from

**[verbal, Anirudh Pai — Proprio Robotics, YC S26, informal advisor]**
- Validate before hardware; start in simulation. *(done)*
- Video demo → pre-order with a discount and a money-back clause, **signed before** the
  full build. Consider a DrinkPrime grant.
- Target physical-AI tasks: "if it could be done simply, it's already been done."
- Stack for the learned-policy phase: π0.5 / OpenPi, LeRobot dataset format, Modal GPUs.
- Expect no working product for years; near-term output is demos and signed commitments.

## 9. Status

| Item | State |
|---|---|
| Generic swap-cycle sim | **Done** — 125/125 **[demo]** |
| Demo video for the founder | **Ready** — `media/refurb_cell_v3.mp4` |
| Funding bar | **Named [verbal]** — complete refurb sim w/ image inspection + cleaning. Still needs to be IN WRITING (Ask 1) |
| v4 inspect / clean / replace loop | In progress |
| Plant video / tech docs / device | **Open** — Ask 2, gating. Expected within days |
| Real cartridge geometry | Blocked on Ask 2 |
| LeRobot data logging | Next technical item |
| Hardware purchase | **On hold** until funding is confirmed in writing |
