# Arm-count trade study — how many arms, and which ones

*Written 2026-08-09. Numbers regenerate from `sim_poc/trade_study.py`; run it rather than
trusting this file if anything upstream has moved.*

**Every number in this document carries a source tag. There are no untagged numbers.**

| tag | means |
|---|---|
| `[measured]` | produced by our simulation, reproducible from a named command |
| `[published]` | a vendor or public figure, with a URL |
| `[assumed]` | our estimate — states the assumption and a plausible range |
| `[open]` | waiting on an answer; the doc is built so it plugs in without rework |

---

## Plain-language summary — read this first

**The arm-count question turns out not to be the interesting one, and the number that
settles it is one we already had.**

One cell, one xArm7, using the continuous-stroke cleaning built this session, does about
**330 units a day** on two shifts `[measured cycle, assumed uptime]` — and about **470** if
the opt-in "clean only where the dirt is" mode is enabled. The refurb volume nobody has
confirmed is somewhere around **130–200 a day** `[assumed]`. So a single arm has roughly
**1.7–2.4× the capacity that is probably needed**. You do not buy a second arm to sit idle.

That makes three of the four options answers to a question the volume does not ask:

- **A — one xArm7 (recommended).** Covers the likely volume with margin to spare.
- **B — two xArm7s splitting the work.** A pipeline runs at the speed of its *slowest*
  station. Cleaning takes far longer than the membrane job, so the second arm idles most
  of the time and the pair only runs about **1.13×** as fast as one arm `[measured]` — for
  twice the arm cost. And here is the sting: **the faster we make the single arm at
  cleaning, the worse this option gets.** If you genuinely need more throughput, two
  *independent* cells give a clean 2× for the same two arms.
- **C — fixed car-wash brushes plus one arm.** The biggest throughput lever on paper, and
  it is gated by one hard measured number: a box on a turntable **swings 64 mm in and out
  every quarter turn** `[measured]`, against the 30 mm of give our arm's spring-loaded
  flange has `[measured]`. So the brush needs its own sprung travel — ordinary car-wash
  hardware, but a requirement, not a detail. The real cost is different: **brushes clean
  blind.** We lose the per-patch evidence that is the actual product.
- **D — YAM arms (I2RT), $3.0–4.9K vs ~$11K.** Genuinely cheaper. Two things are not
  like-for-like. Our sustained wipe force is **32 N `[measured]`**, about **3.3 kg of push
  held for the whole cleaning cycle** — that is **82% of a YAM Ultra's 4 kg rating
  `[published]`** before you add the tool. And **YAM publishes no repeatability figure at
  all `[published absence]`**, while our tightest job needs about half a millimetre. The
  absence is the signal: industrial arms always publish it, research arms often don't.

**Recommendation: stay on one xArm7.** Not because YAM is bad — because at ~200 units a
day the arm is not the constraint, and swapping to an arm with no published precision
figure trades a known quantity for an unknown one in order to solve a problem we do not
have. Revisit if the volume answer comes back above **~330/day** (where a second cell is
needed) or **~700/day** (where fixed brushes become the only single-cell answer), or if
Anirudh produces first-hand evidence of a YAM working under this kind of sustained load.

**Two things would change this document, and both are outstanding:** the daily refurb
volume (founder), and first-hand YAM-under-load evidence (Anirudh). They are marked
`[open]` and live as two constants at the top of `trade_study.py`.

---

## 1. What each option is

### A — one xArm7, continuous stroke *(recommended)*
The cell as built. One arm: picks the pad off the changer, cleans all five exposed faces,
returns the pad, inserts the membrane element, places the cap, holds the driver. Triage
and verification are cameras, not motions.

### B — two xArm7s, split stations
Arm 1: load, triage, clean, verify. Arm 2: membrane insert, cap, tighten, dip. A buffer
between them.

### C — fixed powered brushes + one xArm7
Brushes on sprung carriages bear on the device while the existing rotary indexer turns it.
The arm is freed for the membrane work only.

> **The hard constraint, derived from the model.** The cabinet is 180 × 250 mm, so a point
> on its surface swings between the half-width (**90 mm**) and the half-diagonal
> (√(90² + 125²) = **154.1 mm**) from the rotation axis. **A fixed brush must absorb
> 64.1 mm of radial travel every quarter turn** `[measured]`, against the **30 mm** stroke
> of our active contact flange `[measured]`. The arm's compliance cannot be reused: the
> brush needs its own ≥64 mm sprung travel, or a profile-following carriage. That is
> ordinary car-wash hardware and it is a *requirement*, not a detail.
>
> Brush cleaning time is **25 s** `[assumed]` (range 15–45): one revolution at the
> already-validated 1.2 s per 90°, allow three revolutions plus a separate top-face pass.
> Option C's whole throughput advantage rests on this assumption, and it is ours.
>
> **The real cost is not mechanical.** Brushes clean **blind**. Today every patch is
> removed only where measured contact force passed over it, and that is *why* the coverage
> number means something. Under option C the camera backstop becomes the only evidence,
> which is a genuine regression in what we can *prove* — and what we can prove is the
> product.

### D — YAM / YAM Ultra (I2RT), same topology as A
Identical cell, cheaper arm.

---

## 2. Inputs, with sources

### Station times

| quantity | value | tag | source |
|---|---|---|---|
| clean, point raster, full coverage | 186.8 s | `[measured]` | `v5_clean.py --eval 8` |
| **clean, V7 continuous stroke, full coverage** | **137.3 s** | `[measured]` | `v5_clean.py --eval 16 --stroke --seed0 1920` |
| clean, targeted + camera backstop (V6, point) | 74.7 s median | `[measured]` | seeds 1860–1875 |
| clean, targeted + stroke | **REJECTED** — 98.2 s median (slower than targeted alone) and a 91.5 N contact on 1 of 16, twice the 45 N model-validity ceiling | `[measured]` | seeds 2000–2015 |
| membrane (insert 25.6 + tighten 17.4 + dip 1.2) | 44.2 s | `[measured]` | `v5_membrane.py` |
| triage | **0 simulated seconds** | `[measured]` | pure rendering — no motion exists |
| verify | **0 simulated seconds** | `[measured]` | pure rendering |
| triage, real cell | 8 s | `[assumed]` (4–15) | 1.2 s indexer dwell × 4 faces + exposure |
| verify, real cell | 8 s | `[assumed]` (4–15) | as above |
| load / unload onto the indexer | 20 s | `[assumed]` (10–40) | **not modelled anywhere in v5** |

> **The two zeros matter and they cut against us.** Triage and verify cost no simulated
> time because they are renders, not motions. A real cell must index the device past a
> camera and wait for it to settle. **Every cycle time in this document is therefore an
> optimistic bound, never a conservative one.**

### Class mix

`[measured]` on the 120-unit held-out triage eval (seeds 700–819): **39 easy / 47 medium /
34 hard**, i.e. 0.33 / 0.39 / 0.28.

> The class **names** are DrinkPrime's; the **boundaries are ours** and remain
> unconfirmed. So this mix is ours too. It changes the average cycle materially — hard
> units skip cleaning and membrane entirely — so if the founder's real mix differs, rerun.

### Arms

| | xArm7 | YAM | YAM Ultra |
|---|---|---|---|
| price | ~$11,000 `[published]` ($11.0–12.5K street) | $2,999 `[published]` | $4,299 `[published]` ($4,299–4,944 resellers) |
| payload | 3.5 kg `[published]` | 2 kg `[published]` | 4 kg `[published]` |
| reach | 700 mm `[published]` | 780 mm `[published]` | 780 mm `[published]` |
| **repeatability** | **±0.1 mm `[published]`** | **not published** | **not published** |
| DoF | 7 | 6 | 6 |
| marketed for | industrial cobot work `[published]` | "real-world research and embodied AI data collection" `[published]` | same |

Sources: [ufactory.us xArm 7](https://www.ufactory.us/product/ufactory-xarm-7),
[i2rt.com YAM](https://i2rt.com/products/yam-6-dof-arm),
[i2rt.com YAM arm series](https://i2rt.com/pages/yam-arm),
[doc.i2rt.com YAM docs](https://doc.i2rt.com/products/yam) — the docs site lists control
modes, CAN bus and motor series and **publishes no payload, reach or repeatability**,
which is why the absence is recorded as a finding rather than an oversight.

### Economics — every number here is `[assumed]`

| quantity | value | note |
|---|---|---|
| displaced labour | $16–21K/yr per cell | consistent with `PROJECT_CONTEXT`'s $1.50–2.50/hr `[unsourced]` at 2 operators × 2 shifts × 8 h × 300 d = $14.4–24K |
| tooling per cell | $6–12K | changer, active flange, pad, indexer, 2 cameras, frame |
| integration, one-off | $15–30K | guarding, PLC, programming, FAT |
| maintenance | 5–10% of capex/yr | |
| uptime | 75–90% | |
| shifts | 2 × 8 h, 300 d/yr | |

> **The "$10K" figure from the 2026-08-02 call is deliberately not used.** `PITCH_NOTES`
> records it as internally contradictory (stated both as a total and as per-worker), with
> no time period, and flagged as hypothetical by the speaker.

> **Payback may be the wrong lens entirely.** The founder's stated constraint is
> *throughput, not cost* — secondhand and unconfirmed. If that holds, the number to read
> is **cost per unit/day of capacity** (§4), not payback years.

---

## 3. Volume sensitivity — the core output

`[open]` **Daily refurb volume is unknown.** The founder has not answered. Estimate
130–200/day `[assumed]`. Everything below is therefore a sensitivity, not a point
estimate. Run at the **shipping** clean mode (full coverage, continuous stroke, 137.3 s) —
because *"ENSURING ALL SURFACES ARE COVERED"* is DrinkPrime's own Stage-2 wording, not a
bar we chose. `trade_study.py --targeted` reruns everything with the opt-in targeted mode.

**Cells needed, and where the answer steps:**

| option | 100/day | 200/day | 400/day | 1000/day | first step-up |
|---|---|---|---|---|---|
| **A** 1× xArm7, stroke | 1 | 1 | 2 | 4 | ~328/day |
| **B** 2× xArm7, split | 1 | 1 | 2 | 3 | ~371/day |
| **C** brushes + 1× xArm7 | 1 | 1 | 1 | 2 | ~710/day |
| **D** YAM Ultra, as A | 1 | 1 | 2 | 4 | ~328/day |

**Economics at each volume** (capex includes tooling and a one-off integration allowance;
payback is against $16–21K/yr displaced labour per cell, all `[assumed]`):

| volume | option | cycle s | units/cell/day | cells | arms | capex $ | maint $/yr | payback yr |
|---|---|---|---|---|---|---|---|---|
| **100/day** | A | 149.4 | 328 | 1 | 1 | 42,500 | 3,188 | 2.4–3.3 |
| | B | 132.1 | 371 | 1 | 2 | 53,500 | 4,013 | 3.1–4.5 |
| | C | 69.0 | 710 | 1 | 1 | 50,500 | 3,788 | 2.9–4.1 |
| | D | 149.4 | 328 | 1 | 1 | 35,799 | 2,685 | 2.0–2.7 |
| **200/day** | A | 149.4 | 328 | 1 | 1 | 42,500 | 3,188 | 2.4–3.3 |
| | B | 132.1 | 371 | 1 | 2 | 53,500 | 4,013 | 3.1–4.5 |
| | C | 69.0 | 710 | 1 | 1 | 50,500 | 3,788 | 2.9–4.1 |
| | D | 149.4 | 328 | 1 | 1 | 35,799 | 2,685 | 2.0–2.7 |
| **400/day** | A | 149.4 | 328 | **2** | 2 | 62,500 | 4,688 | 1.7–2.3 |
| | B | 132.1 | 371 | 2 | **4** | 84,500 | 6,338 | 2.4–3.3 |
| | C | 69.0 | 710 | **1** | 1 | 50,500 | 3,788 | 2.9–4.1 |
| | D | 149.4 | 328 | 2 | 2 | 49,098 | 3,682 | 1.3–1.7 |
| **1000/day** | A | 149.4 | 328 | 4 | 4 | 102,500 | 7,688 | 1.3–1.8 |
| | B | 132.1 | 371 | 3 | **6** | 115,500 | 8,663 | 2.1–2.9 |
| | C | 69.0 | 710 | **2** | 2 | 78,500 | 5,888 | 2.2–3.0 |
| | D | 149.4 | 328 | 4 | 4 | 75,696 | 5,677 | 1.0–1.3 |

**Where the answer flips**

- **Below ~328/day: one cell, any option. The choice is nearly irrelevant** — the arm is
  not the constraint. This bracket contains the whole 130–200/day estimate.
- **~328–371/day:** A needs a second cell before B does. This is the *only* window where
  B's pipeline earns anything, and it is 43 units/day wide.
- **Above ~400/day:** the ranking is set by cycle time, and **C pulls away** — it is the
  only option that still runs one cell at 400/day.
- **B never wins on arms.** At 400/day it uses 4 arms to do what A does with 2; at
  1000/day, 6 against 4. Two *independent* cells beat one 2-arm pipeline at every volume,
  because a pipeline runs at its slowest station and ours are 137 s against 44 s.
- **D never changes the cell count** — it is the same cell with a cheaper arm. It only ever
  moves capex, by ~$6.7K per arm.

## 4. Cost per unit/day of capacity

The right lens **if the founder's constraint really is throughput rather than cost**
(secondhand, unconfirmed — `PROJECT_CONTEXT`).

| option | units/hr | units/day | capex, 1 cell | **$ per unit/day of capacity** |
|---|---|---|---|---|
| A 1× xArm7, stroke | 20.5 | 328 | $42,500 | **$130** |
| B 2× xArm7, split | 23.2 | 371 | $53,500 | $144 |
| **C brushes + 1× xArm7** | 44.4 | 710 | $50,500 | **$71** |
| D YAM Ultra, as A | 20.5 | 328 | $35,799 | $109 |

On this lens **C is nearly twice as good as anything else and B is the worst option on the
board** — it buys 13% more throughput for 26% more capex. D beats A only because the arm is
cheaper; it produces exactly the same number of units.

## 5. Option D risk register — unknowns priced as risk, not as zero

| risk | evidence | severity |
|---|---|---|
| **Sustained force exceeds payload class** | our wipe is 32.2 N ≈ 3.3 kg-equivalent `[measured]`, held for the whole clean cycle. YAM 2 kg → 164% of rating; YAM Ultra 4 kg → 82%, **before** the ~1 kg tool. A push is not a lift, but the joint torques are comparable. | **high** — standard YAM is excluded outright; Ultra is marginal |
| **No published repeatability** | `[published absence]`. Our tightest needs: tool-changer capture 4 mm / 4° `[measured]`, membrane seat 1.31–1.61 mm against a 1.8 mm bound `[measured]` | **high** — this is a ±0.5 mm-class job with no vendor number to check against |
| **Duty cycle** | 2 shifts × 300 days is continuous industrial duty; YAM is marketed for research and data collection `[published]` | **medium** — not a defect, a different product category |
| **6-DoF vs 7-DoF** | our cleaner's posture-continuity fix exploits the 7-DoF null space to keep adjacent path knots in the same IK branch `[measured]`. A 6-DoF arm has discrete branches instead of a continuum | **medium** — needs re-validation, and `ArmProfile` exists so it is a config change |
| **Re-validation cost** | one full gate + eval pass | **low** — bounded, and deliberately not spent yet (see the portability rule in `CLAUDE.md`) |

**Decision rule, fixed before the answer so it cannot be rationalised afterwards:**
xArm7 remains the default **unless** Anirudh's reply contains *first-hand* evidence of a
YAM or YAM Ultra running under ~33 N sustained contact, ~±0.5 mm needs, 16 hr/day duty.
A link, a recommendation, or "they look good" does not move it. `[open]`

## 6. What would change the recommendation

| if this turns out to be true | then |
|---|---|
| volume comes back **above ~330/day** | the arm-count question becomes real; go to **two independent cells**, not a 2-arm pipeline |
| volume comes back **above ~700/day** | option **C** becomes the only single-cell answer, and the 64 mm sprung-brush requirement has to be engineered |
| Anirudh supplies **first-hand YAM-under-load evidence** | D becomes live; it saves ~$6.7K/arm and changes nothing else. Re-validate against `ArmProfile` — one profile, one gate + eval pass |
| the founder says *"cleans the filter with a solution"* means the **v4 cartridge dip** | **this entire study is about the wrong station.** Still outstanding since 2026-08-04, and it outranks everything here |
| operators grade by **feel**, not by eye | triage is the wrong architecture and the class mix driving these cycle times is wrong too |

## 7. What this study does not cover

- **Load/unload is `[assumed]` and unmodelled.** No motion anywhere in v5 puts a device on
  the indexer or takes it off. At 20 s of a 149 s cycle it is 13% of the answer.
- **The HARD route has no physical handoff** — 0 of 6 steps implemented. Hard units are
  costed as triage-only, which is the optimistic end.
- **Triage and verify cost zero simulated seconds.** Every cycle time here is an
  optimistic bound.
- **No reliability model.** MTBF, spares, changeover and operator intervention are absent;
  maintenance is a flat percentage of capex `[assumed]`.
- **One-cell-one-operator** is the labour assumption and it is the weakest link in the
  payback column. If one operator tends two cells, payback roughly doubles.

## 8. Reproducing this

```bash
cd sim_poc && ../venv/bin/python trade_study.py
```

`--targeted` reruns every table with the opt-in targeted clean (74.7 s) instead of the
shipping full-coverage stroke. The two `[open]` inputs are constants at the top of the
file: `YAM_LOAD_EVIDENCE` and `DAILY_VOLUME`.
