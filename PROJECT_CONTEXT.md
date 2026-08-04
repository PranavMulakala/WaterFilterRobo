# Water Filter Robotics Project — Context Brief
*Last updated: Aug 4, 2026. Purpose: give a new collaborator the BUSINESS context in one
read — the people, the idea, the advice, the economics.*

> **This file is not the technical status.** For where the build actually stands, read
> **[CLAUDE.md](CLAUDE.md)** (opens with "WHERE THE WORK IS"), then
> **[V5_PLAN.md](V5_PLAN.md)** for v5 results and **[RESULTS_V4.md](RESULTS_V4.md)** for
> v4. This file went three days stale once while quoting an 84% figure that had already
> become 100%, which is why the split is now explicit.

## The people

- **Pranav Mulakala** (Atlanta) — software engineer, driving research and (likely) hands-on build.
- **Teja** (West Coast) — Pranav's manager at their day job, now effectively co-founder. Knows the founder of DrinkPrime personally. Proposed the original idea.
- **Anirudh Pai** — Pranav's friend; co-founder of **Proprio Robotics (YC S26)**, which builds autonomous robots for the data center lifecycle (server assembly, maintenance, decommissioning). Acting as an informal advisor (declined formal advisor role for now — too busy; will review plans and send resources).

## The idea (current form)

Long-term vision: "Thumbtack/handyman services, but robots do the work." Near-term wedge: **DrinkPrime** — an Indian (Bangalore) water-purifier-subscription company (~1,000 units manufactured/day; the manufacturing entity named in their documents is Waterwala Labs). Teja knows the founder, who said he'd happily look at a demo.

**The wedge narrowed and then widened again, deliberately.** It began as "automate ONE station of the assembly line" — probably cartridge insertion or housing screw-down. On 2026-08-02 the founder said **refurbishment is their biggest pain point**, so refurb became the target. On 2026-08-04 their **real process documents landed** — 13 files: 10 stage work instructions plus 3 QC flow-chart pages — and the build is now a **three-station refurb cell** modelled on their actual documented process: TRIAGE (grade the incoming unit), CLEAN (Stages 2–3), MEMBRANE ASSEMBLY (Stage 10). See [V5_PLAN.md](V5_PLAN.md).

Approach is still an off-the-shelf arm (xArm7) plus, eventually, imitation-learned policies — but everything shipped so far is a **scripted** controller. Our advisor was explicit that scripting is fine at the demo stage and does not prove the approach survives things moving; see PITCH_NOTES.

Secondary idea (Teja's, under research): **software to help robotics companies launch and manage deployments** ("ERP for robotics" / picks-and-shovels). Current conclusion: real but crowded at the fleet-ops layer (Formant, InOrbit, Viam) and data layer (Foxglove, $40M Series B); the open gap is robot-learning ops (teleop data collection → LeRobot datasets → fine-tune → eval → deploy). Verdict so far: a *second* startup — do the DrinkPrime deployment first, document every workflow pain as product research, revisit with Proprio as design partner.

## Key advice received (Anirudh call, Jul 31)

1. Validate before hardware. Get willingness-to-pay numbers first. Start in simulation.
2. Task rule: "if it could be done simply, it's already been done" — target physical-AI tasks.
3. Stack: fine-tune π0.5 (OpenPi), LeRobot dataset format, Modal GPUs, teleop demos.
4. Hardware: YAM arms ~$3K; xArm 5/7 = $6K/$11K; real system = tens of thousands eventually.
5. Sales: video demo → pre-order with discount + money-back clause, signed BEFORE full build. Consider a DrinkPrime grant.
6. Expectations: no working product for years; near-term = demos + signed pre-orders.
7. Fundraising: market size + founder credibility; signed customer fixes both. YC after demo+commitment.
8. Location: robotics is in-person; robot lives with the hands-on person. Decision pending.

## Economics warning

Indian assembly labor ≈ $1.50–2.50/hr. Robot must beat that or win: consistency/quality, 24/7 operation — or train cheap in India, sell in expensive-labor markets.

**This is the honest weak point of the whole thesis, and PITCH_NOTES says to raise it
before the customer does.** One update from the 2026-08-02 call, relayed secondhand
through Teja rather than heard directly: **the founder's stated constraint is throughput,
not cost** — he can hire people and is not paying them much, but he does not think it is
fast enough. Treat that as a lead to verify with him, not as an established fact. Do not
quote the "10K" labour figure from that call: it is internally contradictory (stated both
as a total and as per-worker), names no time period, and was flagged as hypothetical by
the speaker.

## Where this stands commercially (updated Aug 4)

1. **Founder interest is confirmed, verbally.** He has indicated **$20–30K for arms** if
   the refurb process can be credibly simulated, with an explicit bar of *image
   inspection plus a cleaning step*. **Still not in writing** — that remains the gate on
   any hardware purchase. Budget guidance unchanged: ≤$10K split & go; $50K+ rethink.
2. **Their real process documents landed** (2026-08-04): 13 files in total — 10 stage
   work instructions and 3 QC flow-chart pages, transcribed as data in `sim_poc/dp_process.py`. The build is now modelled
   on their documented stages rather than on a generic cartridge swap.
3. **The top open ask is what defines Easy / Medium / Hard** — and it must be asked
   open-ended, because **no document in the set defines it**. If their operators grade by
   *feel* rather than by eye, camera-only inspection is the wrong architecture and we
   should stop investing in the classifier. Full ask list in V5_PLAN.
4. Still open from the original list: Pranav's LeRobot / OpenPi ramp; deciding the robot's
   home base; and formalising co-founder structure and equity.

*(This section previously said "Sim POC DONE … 84% locked over 25 randomized trials" and
"hardware ON HOLD until founder interest confirmed". Both were superseded within days —
the 84% became 100% over 200 trials, and the founder confirmed interest. Technical
numbers do not belong in this file; that is why they now live in CLAUDE.md.)*

## Key resources

- OpenPi: github.com/Physical-Intelligence/openpi
- LeRobot: github.com/huggingface/lerobot
- Modal: modal.com (ask for startup credits)
- Proprio: propriorobotics.com
- Urban Company NATIVE factory tour: youtu.be/xD1BOm5c0ms
- Analogs: Revise Robotics (YC), CynLr (Bangalore), stealth teleop company.
