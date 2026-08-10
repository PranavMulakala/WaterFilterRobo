# Decision log

Irreversible or expensive choices, with the evidence that decided them and the evidence
that would reopen them. Newest first. A decision recorded here is CLOSED — do not re-argue
it in a session without new evidence of the kind named in "what would reopen this".

---

## 2026-08-10 — PRODUCTION ARM = **UFACTORY xArm7**. FINAL.

**Status: CLOSED. The arm-count trade study is CANCELLED as an open workstream.**
`TRADE_STUDY.md` and `sim_poc/trade_study.py` stay in the repo as the record of the
analysis, not as live work.

### What decided it

1. **Anirudh confirmed he has NO first-hand YAM experience.** The decision rule was fixed
   *before* his answer arrived, precisely so it could not be rationalised afterwards:
   *xArm7 remains the default unless the reply contains first-hand YAM-under-load
   evidence.* It did not. The rule resolved to xArm7 without further argument.
2. **His independent industrial shortlist — Universal Robots / Elite / UFACTORY —
   contained ours.** That is convergent evidence from someone who did not know what we
   had already chosen. It is worth more than the cost arithmetic that pointed at YAM.
3. **The payload margin is now closed, and closing it was a by-product of the speed
   clamp.** Peak wipe force **27.35 N** measured against the xArm7's **~34 N-equivalent**
   rating (3.5 kg × 9.81) = **80% utilisation**, with the tool carried by the arm rather
   than counted against the wipe. Before the clamp it was 32.15 N (94%). *We did not set
   out to fix this; adopting the published joint-speed limit lowered peak contact force as
   a side effect, and that is what turned a marginal payload into an acceptable one.*
4. **The trade study's own headline made the question moot anyway:** one cell does ~328
   units/day against an estimated 130–200/day need, so the arm was never the constraint.
   YAM's advantage was capex on an axis that does not bind.

### What this does NOT decide

- **Purchase remains gated on founder funding.** Nothing is ordered. The $20–30K bar is
  still [verbal] and still unconfirmed in writing.
- **YAM is not rejected — it is re-scoped.** It remains the candidate for a future
  **teleoperation / imitation-learning data bench**, which is what I2RT actually market it
  for ("real-world research and embodied AI data collection"). The objection recorded in
  `TRADE_STUDY.md` was always about the *force-heavy cleaning station*, never about YAM as
  a data-collection rig. Do not quote the payload objection against the teleop use.

### What would reopen this

Daily refurb volume coming back **above ~700/day** (where the cell count and therefore the
capex axis start to bind), or a hard requirement the xArm7 cannot meet that a different
arm can. Cost alone does not reopen it.

---

## 2026-08-10 — ADOPT the arm's PUBLISHED speed limits (180 °/s, 1 m/s TCP)

**Status: CLOSED. Adopted, with a full re-baseline.** See `HANDOVER.md` for the
retractions this forced.

Found because Pranav watched the V7 clip and said the arm "flails" — **not by any metric we
had.** Every number this station reports is about CONTACT (force, coverage, tilt), so
free-space motion appeared in no number, no assertion and no gate. Measured: repositioning
moves reached **3020 mm/s** against a published **1 m/s** TCP limit, and the setpoint rate
was **10 rad/s** against a published **3.14 rad/s**. Pre-existing across v5, v6 and v7.

### Outcome, measured

Adopted, and it is better on almost every accuracy metric rather than merely more honest:
peak contact force **32.15 → 22.04 N** (stroke) and **32.94 → 23.93 N** (point), mean press
tilt **11.7° → 8.5°**, exact-normal presses **20% → 36%**, coverage unchanged at 100% with 0
missed of 256, sabotage 10/10, membrane 10/10, route byte-identical. Peak joint speed
**5.71 → 2.46 rad/s** (22% inside the rating), peak tool **3020 → 1063 mm/s**.

**It took three attempts and the first two were instructive failures:**
1. Clamping the SETPOINT rate did not clamp the ARM (still 5.71 rad/s) — a position servo
   chases the setpoint's ERROR, not its velocity.
2. `max_follow_err` is what bounds joint speed. **It must NOT be tightened to chase the
   tool-speed figure** — the force cliff is at 0.14 rad (89.5 N) and 0.15 sits 7% from it.
3. Tool speed needed a Cartesian governor in `_advance`, because it is a Cartesian
   quantity.

### The price, and it is a real one

**Targeted cleaning is WITHDRAWN**, and with it the externally-quoted **2:33** figure —
under the clamp it left residue on 1 of 24 units and failed verification on one, with a
98.67 N contact. Full retraction in `HANDOVER.md`. The shipping mode is full coverage at
**3:11.9** per MEDIUM unit.

Peak joint speed is now asserted HARD in `report()` and statically in `v5_check_spec.py`;
peak tool speed with a documented 10% servo-overshoot allowance. This class of defect
cannot return silently.
