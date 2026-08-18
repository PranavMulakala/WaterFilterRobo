# Refurbishment process video — transcript + shot log (received 2026-08-18)

Source: `refurbished_4.mp4` (1:47.8, 1080p, sent by the founder's side; the plant video
promised on 2026-08-12). Narrator: a plant engineer (name unknown), non-native English.

**Provenance of this transcript:** Whisper-medium (local) cross-checked word-by-word
against the video's own burned-in captions, plus the on-screen evidence (ERP field names,
product labels). Corrections applied where all sources agree are marked inline the first
time. Three spots are flagged `[?]` — Pranav to confirm.

## Corrected transcript

- [0:00] So this is the first process in the refurbishment*, where we disassemble the
  received devices. (*narrator says "republishment" throughout; captions say refurbishment)
- [0:04] So device will be disassembled based on the old PID and the new PID ("PID" per
  the captions; the ERP screen at 1:26 shows "Old Purifier ID / New Purifier ID"). So in
  the APK you can see disassemble operation starts with the old PID, and then whatever the
  new PID we are replacing, that PID gets scanned — and one more is, like, a **sponsor
  code** (real term: "Sponsor Code" is a field in their ERP, visible at 1:26).
- [0:16] This is how we do the refurbishment currently — that is the manual operation.
- [0:18] In the first process we polish the outer surface of the cabinet. There we check
  for the dents and damages. **If the dent is more, then only we proceed for the
  replacement. If the dents is minimal, then we polish it** using the buffing pad and also
  the brushes, with the required solutions and the **Cif polish** (narrator: "sif"; Cif
  bottles on the bench) which we use currently.
- [0:33] And the second thing is the back part of the cabinet, where it is also cleaned
  using the same solution, and also check for the dents and damages.
- [0:39] The second procedure is bowl cleaning. So in bowl cleaning we have impurities
  which is brownish in color or blackish in color, which is present inside the bowl. So
  this is also cleaned with the same Cif polish **and sanitizer**, and we use different
  brushes for different operations.
- [0:51] And once impurities are cleared, then the sticker gets replaced in the bowl, and
  the **elbows** are also replaced, because we have **salt contents** `[? "salt" is
  whisper's hearing; captions omit the word]` in the elbow.
- [0:58] Once the polishing operation is done, the next process is like wiring and
  assembly. So first operation is wiring, where he does connect the **bot, harness, SV,
  pump**, and the tubing will be done in the next stage, which is called as assembly zone.
- [1:09] So next operation is sticker change, where we remove the existing sticker from
  the device and replace it with a new one. So we use a **heat gun** to remove the old
  stickers, and with the help of the **blade** (captions; whisper heard "plate") we
  remove the current stickers.
- [1:19] So once the stickering is completed, then the device will be transferred into
  the final testing area, where device is tested using the **pneumatic air** (captions;
  whisper heard "wire"; a line gauge and air gun are on screen). You can see the device
  which is ready for testing. So you can see the testing operations right now.
- [1:28] The major challenges we are facing here is the **manpower, cycle time** `[? one
  phrase "manpower cycle time" or two listed challenges — captions split them]`, where
  based on the devices we have multiple cycle times. **Some devices take around 5
  minutes, and [if] the device comes with more dust on it** `[? whisper: "dust under
  it"]`, **it may go up to 15 to 20 minutes.**
- [1:39] **So the major challenge is to reduce the cycle time so that all the devices'
  cleaning will be remained under the 5 minutes, so that we can concentrate more on the
  productivity part of the work.**

## Shot log (timestamps ±1 s)

| t | shot | what is visible |
|---|---|---|
| 0:00–0:04 | Title: "Device Disassembly & Initial Testing" | dp purifier render |
| 0:04–0:13 | Teardown bench | worker (SSD polo) over a water tub, device open, spraying/loosening; wall carries a laminated DrinkPrime work instruction (same format as the 13 docs) |
| 0:14 | PID scan close-up | phone app scanning the barcode label on the INNER chassis; outer cabinet + front cover already OFF and set aside |
| 0:15 | Teardown output crates | sorted: RO membrane assemblies (teal caps) / inline cartridges with tubing pigtails / large white cartridges / pink inline SKU / tubing tangle — segregation by stream |
| 0:16–0:18 | Title: "Refurbishment Manual Process" | |
| 0:18–0:24 | Cabinet wash | detached panel wiped/scrubbed IN HAND; dent check narration |
| 0:25–0:27 | Fascia scrub | small yellow brush on a WET translucent fascia, droplets, Cif bottle |
| 0:28–0:33 | BUFFING | hand drill + yellow foam buffing pad pressed on the cabinet, held in hand; Cif Cleanboost + pink trigger spray |
| 0:33–0:39 | Title + back panel | "Front & Back Fascia Cleaning"; back part cleaned the same way |
| 0:39–0:51 | Title "RO Bowl Cleaning" + bench | crates of bowls; women cleaning; yellow tubs "Cream Polish" + MAX Cream Polish (= Stage 2's "Moto max cream"), Cif 5L jug, sanitizer, assorted brushes |
| 0:51–0:58 | Bowl sticker + ELBOW replacement | white elbow fitting swapped at the bowl port; red cutters, hex lever |
| 0:58–1:09 | Title "Wiring & Sub-Assembly" | base chassis: pump on black mounting plate, spade connectors, bot + harness + SV connect; blue membrane housing; "assembly zone" next |
| 1:09–1:19 | Title "Replacement Of Existing Stickers" | heat gun + blade removal, new dp sticker sheet applied |
| 1:19–1:28 | Title "Final QC & Mapping Stage" | red-shirt worker connects PNEUMATIC line to assembled stack; DIAL PRESSURE GAUGE on the line; Dell laptop with the ERP |
| 1:28–1:47 | Narrator close | challenges + the under-5-minutes target |

## The ERP screen (1:25–1:27), read at full resolution

`drinkprime.frappe.cloud/app/stock-entry` — Frappe/ERPNext "Stock Entry" list, 72 rows,
filters visible: **Old Purifier ID, New Purifier ID, Old Bot ID, New Bot ID, Sponsor
Code, Refurbishment…, Repack, API Sync Status, Customer Phone**. Row columns: type
"Repack", status chips ("Ready To…", "Validation…"), posting date 14-08-2026, a **grade
chip per unit — "Medium" (orange) ×8, "Hard" (red) ×1 visible** — then a ₹ amount per
unit (readable: 3,584.78 / 1,879.30 / 1,885.18 / 2,865.26-Hard / 1,984.35 / 1,803.05 /
1,888.85 / 1,877.83), then bot IDs (WIF…, CAPA…, STR…) and MAT-RPK-2… material codes.

**Implications: the grades ARE per-unit data in their system, with a rectification-cost
column beside them** — the "cost > 80–90%" scrap rule has a data source, and class priors
+ cost distributions are queryable. The right ask is now specific: an export of Stock
Entry with grade + cost + status for a few months.

## What this video settles / changes (against dp_process.py and the sim)

1. **Manual clean cycle time, finally: ~5 min typical, 15–20 min dirty, and the plant's
   own TARGET is "all devices under 5 minutes".** The denominator the speedup claims
   lacked. BASE sim cycle (wash+membrane+verify, 2:28.6) sits well inside their target;
   even FULL STAGE 3 (6:20.7) is at the boundary of their typical-to-bad range.
2. **Their cabinet polishing is already a POWERED ROTATING PAD** (drill + buffing pad,
   held in hand, panel sometimes detached). The sim's spinning-pad-on-ACF is not an
   approximation of a wipe — it is the literal tool class they use. Also strengthens
   option C (fixed brush/buff) as their-process-shaped.
3. **Panels are cleaned DETACHED (in hand), device disassembled first** — confirms the
   teardown reality the corpus lacked; v5's assembled-cabinet-on-turntable is a cell
   design choice, not their manual practice. Label accordingly.
4. **Triage criterion on camera: dent severity gates replace-vs-polish** ("if the dent is
   more, then only we proceed for the replacement") — an outcome-linked VISUAL criterion,
   still without a numeric threshold.
5. **PID + bot scanning against Frappe ERP with Sponsor Code** — identity/mapping flow
   exists; a robot cell would integrate by scanning the same PID (their vocabulary).
6. **Final leak test is PNEUMATIC AIR with a dial gauge on the line** — the independent
   pressure instrument Task 4's fix named already EXISTS at final QC (still unknown: the
   45-vs-80 PSI number). The membrane-station pressure-decay ask aligns with equipment
   they already own.
7. **Elbows are replaced due to deposits ("salt contents")** — matches the corpus's elbow
   replacement; new consumable detail.
8. **Bowl cleaning = Cif + sanitizer + different brushes; bowl sticker replaced;
   impurities brownish/blackish INSIDE the bowl** — v5 cleans the bowl's outside only;
   inside-bowl cleaning is manual-brush territory (unmodelled, now known).
9. Confirmed verbatim from Stage 2's tool list: Cif polish, cream polish (Moto Max),
   heat gun, blade/scraper, sticker replacement.

Open with the founder, sharpened by the video: the dent threshold (mm? visual chart?);
the pneumatic test pressure; a Stock Entry export (grades + costs + volumes).
