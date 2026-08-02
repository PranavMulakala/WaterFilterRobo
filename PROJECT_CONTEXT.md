# Water Filter Robotics Project — Context Brief
*Last updated: Aug 1, 2026. Purpose: give any new Claude chat (or a new collaborator) full context on this project in one read.*

## The people

- **Pranav Mulakala** (Atlanta) — software engineer, driving research and (likely) hands-on build.
- **Teja** (West Coast) — Pranav's manager at their day job, now effectively co-founder. Knows the founder of DrinkPrime personally. Proposed the original idea.
- **Anirudh Pai** — Pranav's friend; co-founder of **Proprio Robotics (YC S26)**, which builds autonomous robots for the data center lifecycle (server assembly, maintenance, decommissioning). Acting as an informal advisor (declined formal advisor role for now — too busy; will review plans and send resources).

## The idea (current form)

Long-term vision: "Thumbtack/handyman services, but robots do the work." Near-term wedge: **DrinkPrime** — an Indian (Bangalore) water-purifier-subscription company (~1,000 units manufactured/day). Original angle was refurbishment of returned units; current focus is **automating ONE station of their assembly/refurb line** (likely filter-cartridge insertion or housing screw-down) as a POC, using an off-the-shelf robot arm + imitation-learned policies. Teja knows the founder, who said he'd happily look at a demo.

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

## Current next steps

1. Teja → DrinkPrime founder call: labor numbers, willingness-to-pay, ship parts to US, process video, pre-order/grant appetite.
2. Sim POC DONE — see cartridge_cell_v2.mp4 + sim_poc_v2.zip in this folder (84% locked over 25 randomized trials).
3. Hardware purchase ON HOLD until founder interest confirmed. Budget: ≤$10K split & go; $50K+ rethink.
4. Pranav ramp: LeRobot tutorials, OpenPi repo, maybe SO-101 kit.
5. Decide robot home base + formalize co-founder structure/equity.

## Key resources

- OpenPi: github.com/Physical-Intelligence/openpi
- LeRobot: github.com/huggingface/lerobot
- Modal: modal.com (ask for startup credits)
- Proprio: propriorobotics.com
- Urban Company NATIVE factory tour: youtu.be/xD1BOm5c0ms
- Analogs: Revise Robotics (YC), CynLr (Bangalore), stealth teleop company.
