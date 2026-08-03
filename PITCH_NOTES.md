# Pitch Notes — DrinkPrime

*Working notes for the customer conversation, kept next to the demo so the framing and
the open questions don't live in a text thread. Not a deck. Last updated 2026-08-02
(after Anirudh call 2 — see [meetings/anirudh_call_2_transcript.md](meetings/anirudh_call_2_transcript.md)).*

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

**[open] Market size — Pranav's own research, unsourced. Do not repeat to the founder.**
From the 2026-08-02 call: India ~**$2.7 B** today, growing to **"7.5" in about four years**
— *the unit is never actually spoken on the recording*, and the sector is not named in the
same sentence. Source is "what researchers say" via a Perplexity session, i.e. third-hand.
Anirudh neither supplied nor endorsed it; his whole response was "yeah, I guess it makes
sense." Filed here only so it isn't rediscovered and mistaken for something we were told.

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

**Ask 2a — the cartridge STL or STEP file. Ask for this now, separately.**
**[verbal, Anirudh Pai 2026-08-02]** The CAD file does not depend on the device shipment
and is the fastest route to real geometry: "just literally ask him for like the STL file
or the step file... which I assume they have because they're the ones who make the
components," and it can be asked for "right now" because "they don't really need the real
object for that." Reverse-engineering a physical part into a simulation is much harder
than importing a file someone already has. Caveat: that they hold such a file is Anirudh's
inference from the fact that they manufacture, not something DrinkPrime has confirmed.

## 4. Open questions for the founder

**Process — what actually happens during a refurb**
- What are the real steps? Descaling, filter-media replacement, gasket/seal
  inspection, testing, cosmetic work — we're guessing at all of these.
- Is cartridge replacement even the *common* case, or one branch of many? What
  fraction of returned units need which treatment?
- What does the unit look like when it arrives — dirty, scaled, damaged, disassembled?
- Is there a test/QA step at the end, and what does it measure?
- Cartridge SKU, real geometry, real tolerances.
- **How do your workers decide a cartridge is spent?** Do they inspect it visually, is
  there a wear indicator or colour change, or do they go by *feel*? **[verbal, Anirudh
  Pai 2026-08-02]** — he named this as the *first* thing to establish before choosing any
  inspection approach: "there's no like a single classifier that will do this for you."
  This question gates the whole vision architecture. If the wear is clearly visual, an
  off-the-shelf VLM may be enough. If they grade by feel, a camera cannot do the job at
  all and our 86.7% is measuring the wrong thing.

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

> **[verbal, Pranav relaying the founder — 2026-08-02, unconfirmed by the founder]**
> **The bar he stated is throughput, not cost.** "He can find people and he's not paying
> them too much. But the issue is that he thinks it's not as fast." Anirudh's only
> contribution here was the read-back "so your robots would have to be faster than a
> human," which Pranav ratified — so this is **not** advisor analysis, it is us relaying
> the customer, secondhand.
>
> If it holds, it re-points the whole section: **neither framing above addresses speed.**
> Our ~33 s swap and ~41–54 s refurb routes are currently compared against nothing. Get
> the line's takt time and the manual cycle time (§4) before claiming any advantage.
>
> **A labour number was said on the call and is unusable.** "10K per... two workers, two
> shifts, *hypothetically*" and then "10K wise total together... USD wise for each
> worker" — total-together and per-worker cannot both be true, no time period was ever
> stated, and Pranav flagged it as hypothetical himself. **Do not record it and do not
> reconcile it against the $1.50–2.50/hr line above.** Ask him what he actually meant.

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

**Two more limits, both from Anirudh 2026-08-02 [verbal]:**

- **It does not prove the approach survives things moving.** A hard-coded sequence
  produces useful actions only because every object sits in a known position; move them
  and "those actions won't be useful anymore... cause you hard coded them" — which is
  exactly where you have to train models. His own case: a data-center robot drives up to
  a rack and "it's not going to be the exact same position." He was explicit that
  scripting is fine *at this stage* ("this is like cool for like demo purposes"), so this
  is a limit on generalisation, not a verdict on the demo.
- **A failure seen in simulation is not automatically a real failure.** Drops and lost
  friction are *sometimes* artifacts of the simulator, up to geometry bugs where a
  gripper passes through the part. He said *sometimes*, not usually. This cuts both ways
  and belongs next to §7's cap-grip finding — which he did not question.

**One-line framing:** *this de-risks the approach, not the deployment.*

> **Correction to make about ourselves.** On the call the cell was described to Anirudh
> as fully static — "all like the pieces are just static." That understates what the repo
> does: the fresh cartridge spawns from a randomised pose (±40 mm, 360° yaw) across 125
> randomised trials, with simulated perception. Anirudh's script-vs-policy advice was
> given against that understated picture. Worth correcting with him, and worth not
> repeating — it gives away the one thing that makes the demo more than a canned
> animation.

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

**Call 2, 2026-08-02** — full transcript at
[meetings/anirudh_call_2_transcript.md](meetings/anirudh_call_2_transcript.md).

- **Stay on MuJoCo.** For simple objects the simulator "doesn't really matter." NVIDIA
  (Isaac) is "the most cutting edge" for complex assets — he named cables — and is what to
  move to *when you get there*, not before.
- **A sim demo mostly persuades us, not an audience.** Its purpose is our own
  understanding before spending on hardware. "Not many people will look at this and be
  like, oh, this is cool cause it's in simulation. Like people want to see robots in the
  real world... investors and shit." He qualified its persuasive value, he did not deny
  it — and he said nothing about the *founder*, who has already asked for a demo. Do not
  extend this to the customer.
- **He went real-first himself.** "Not for like what we're doing at the company... we do
  everything in real" — Proprio got a robot, collected data with it in the real world,
  teleoped it themselves rather than outsourcing, and "didn't need like too much data."
  Read "start in simulation" as advice for a team *learning the space*, not as how his
  company works. (The same turn also contains a contradictory "we had some sim.")
- **Budget ~7 hours per policy iteration.** Collect data, train, find the policy repeats
  the same mistake, re-collect — "you have to wait like another seven hours." Two or
  three policies a day. "You can't really get around that." No model or dataset size was
  attached to the figure.
- **Don't buy evaluation/monitoring tooling yet.** Proprio stands next to the arm and
  marks runs by hand. He's heard of YC companies doing camera-based auto-eval but "I
  don't know how good they are"; when starting, it "doesn't make too much sense to pay a
  lot of money for that kind of stuff."
- **90%+ is reachable in your own environment** on *some* tasks; the difficulty is
  someone else's environment, where "everything looks a little bit different." This is a
  real-robot learned-policy number, **not** a yardstick for our simulation scores.
- **On the robotics-devtools idea:** "a good idea" on a high level, but unfocused —
  companies already do automatic evaluation and automatic data annotation. "You just have
  to figure out specifically what you're going to do first."
- **Learn the concepts, not the tools** — "for the coding part, Claude can figure it out."
- OpenPI (Physical Intelligence) re-confirmed as the model he'd recommended.
- Proprio has **deprioritised decommissioning**: smaller market, and "a lot of these like
  people who like do decommissioning, they don't have too much money." A useful reminder
  to check that whoever owns the pain also owns a budget.

## 9. Status

| Item | State |
|---|---|
| Generic swap-cycle sim | **Done** — 125/125 **[demo]** |
| Demo video for the founder | **Ready, but verify the file first** — see note below |
| Funding bar | **Named [verbal]** — complete refurb sim w/ image inspection + cleaning. Still needs to be IN WRITING (Ask 1) |
| v4 inspect / clean / replace loop | Routes 100%, end-to-end 86.7% **[demo]**. Pranav on the 2026-08-02 call, re the gap: "I don't know what broke. So I got to go back and look into it" |
| Plant video / tech docs / device | **Open** — Ask 2, gating. Parts shipping; tech docs expected 2026-08-03, after the contact talks to DrinkPrime's technical executives **[verbal]** |
| Cartridge STL/STEP file | **Open — Ask 2a. Not yet requested.** Independent of the device; ask now |
| Real cartridge geometry | Blocked — but **not on the device**. Blocked on making Ask 2a |
| How workers grade a cartridge | **Open** — gates the inspection architecture (§4) |
| LeRobot data logging | Written (v2.1 export); **not round-tripped through the real library** |
| Hardware purchase | **On hold** until funding is confirmed in writing |

> **[open] Watch the demo file before it goes to the founder.** On the 2026-08-02 call,
> while screen-sharing, Pranav narrated visible wobble, loss of grip and repeated re-grip
> attempts in the clip on screen — "you see how it's wobbling and stuff and like it's
> losing its grip. It's not supposed to drop it that fast, right?" — then interrupted
> himself with "am I fucking, is this the right video, bro?" and could not immediately
> tell whether he was showing a clean run or a failed one. The transcript does not
> identify which file was open, and he separately describes the work as "the fourth
> version," so it may not have been `refurb_cell_v3.mp4` at all. This neither confirms nor
> contradicts the 125/125 **[demo]** figure. Action: watch the file end to end and confirm
> it shows what §1 claims before sending it to anyone.
