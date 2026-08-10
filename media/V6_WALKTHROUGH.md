# `v6_cell_realtime.mp4` — what each part of the video shows

> ## ⚠️ SUPERSEDED — 2026-08-10
> **This clip films the arm running ~3× faster than a real xArm7 can move** (peak tool
> speed 3020 mm/s against a published 1 m/s; peak joint 327 °/s against 180 °/s). The
> published speed limits were adopted on 2026-08-10 and every cleaning number was
> re-baselined. **Do not show this clip as current.** The current true-1× clip is
> `media/v7_clean_stroke_realtime.mp4` (3:11.9, full-coverage continuous stroke).
> 
> **AND the mode it films — TARGETED cleaning — is WITHDRAWN.** Under the
> speed clamp it left residue on 1 of 24 units and failed verification on one,
> against a published claim of 0/24. **The 2:33 figure in the line below is
> RETRACTED.**

> See `HANDOVER.md` → RETRACTIONS and `DECISIONS.md`.


**2 min 33 s of robot time, played at true speed — the clip's length IS the cycle time.**
Every frame carries a plain-English caption (the STEP line, top-left) saying what the arm
is doing at that moment. This page is the same story in order.

## The one-sentence version for the founder

> One used purifier: graded from photos instantly, cleaned only where dirt was seen,
> re-checked by a second camera, new membrane fitted and pressure-tested — in about
> two and a half minutes, with the check — not the plan — having the final word.

## What you will see, in order

| roughly | caption on screen | what it means |
|---|---|---|
| 0:00 | title card | the total time, stated up front |
| 0:06 | *Turntable rotating…* | grading: four photos, no arm motion — instant |
| 0:10 | *Reaching for the cleaning pad / Locking the pad…* | the arm docks with a tool changer, like a drill picking its bit |
| 0:15 | *Wiping a side surface…* | **only surfaces where dirt was seen** — clean faces are skipped entirely |
| ~1:40 | *Turntable rotating…* between faces | the device turns; the arm stays put |
| ~2:00 | *Travelling over to the membrane element / Gripping…* | the membrane job starts |
| ~2:10 | *Fine-correcting aim, watching the ELEMENT not the wrist* | the key trick: it measures the part, not its own hand |
| ~2:15 | *Lowering the element into the housing (1.5 mm to spare)* | a 42 mm part into a 45 mm hole |
| ~2:20 | *Gripping the cap by its pick stem / Lowering the cap onto the housing mouth* | **the ARM places the cap**; landing within 4 mm / 4° engages the first thread (that engagement is modelled — the aim is real) |
| ~2:35 | *Holding the driver on the cap — spindle spins only while held* | **the ARM holds the driver**; the spindle only advances while the arm holds station — enforced, not narrated |
| ~2:30 | dip + bubbles | their own acceptance test; bubbles are modelled, the camera must still see them |
| end | two cards | where the time went, and what is *not* real |

## The honesty bar at the bottom of every frame

Each station shows its own caveat. The cleaning one reads: dirt locations are ground truth
standing in for camera localisation — **but the final residue check is a real camera**, and
when cleaning was deliberately sabotaged, that check caught it **15 times out of 15**.

## Numbers behind this exact video

- 24 fresh units cleaned this way: **zero residue on every one**
- membrane, arm doing every step (place + drive): 10/10 sealed, 10/10 sabotage caught, 0 false passes
- worst membrane seating: 1.48 mm off-centre, in a 1.8 mm budget
- the slow full-coverage mode still exists, unchanged, and remains the default
