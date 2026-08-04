# DrinkPrime source documents

The 13 official documents this project's process model is built from. All present in
this directory. The transcription is [`sim_poc/dp_process.py`](../../sim_poc/dp_process.py).

Provenance: Waterwala Labs Pvt Ltd. Forwarded by founder Vijender Reddy via Karthik
Gannoju (Yuv Industries, the plant operator). Received 2026-08-04.

**Two structural facts about the set.** The ten work instructions are REVISION R0 dated
11-04-2024 and are **all unsigned** — PREPARED / REVIEWED / APPROVED / ISSUED BY is blank
on every page of every one. The three QC pages carry **no header block at all**: no
reference, no revision, no date. They are A3 landscape plotted from AutoCAD, and are the
only uncontrolled documents here.

| Stage | Ref | Title | Drive file ID |
|---|---|---|---|
| 1 | 0024DPCRO001 | Device Checking Process | `1zE4mDZjOi5J_MYCJHQYFRHWWFXNYzCfZ` |
| 2 | 0024DPCRO002 | Cabinet Cleaning Process | `1e-9uAd0j19ERsz5YFvLGrX2k-4XrJflx` |
| 3 | 0024DPCRO003 | Back Panel & Top Cover Cleaning | `1z8zoet6BLxC-c8ALdsfgyKrRbH6CMSkS` |
| 4 | 0024DPCRO004 | Device Assembly Process | `1-QLQV8y2DpoDDrvGXeHCKvVoa2UTPDWq` |
| 5 | 0024DPCRO005 | Sticker Pasting Process | `1X6mVKG0r0D-gnDz6iqrxQCLFZSh2VBFC` |
| 6 | **0024DPNAP0008** | Final Testing Process | `15o7jReblrt2pbP_fMUn3ktOTW-XShcuV` |
| 7 | 0024DPCRO007 | Device Packing | `1PQ9SYjaNSfir8dvEME2xlqFHFeSb5a1P` |
| 8 | 0024DPCRO008 | Accessories Packing | `1233qQfT9WEGfgboB3N7gRYObx4eByX1r` |
| 9 | **0024DPNAP0001** | Pump Assembly Process | `1hso6jLu23RU5GKVAXp2lGVfiM9T0yzrG` |
| 10 | 0024DPCRO0010 | Membrane Assembly | `1nNffcKtSIcXUnhziKZHCMo-xUzMBbKfE` |
| QC | *(none printed)* | Quality Control Process, page 1 | `19kp0xC9MY8CbtoGII5JIz5-iwnU-P3R6` |
| QC | *(none printed)* | Quality Control Process, page 2 | `1DV7FxH8UgDwVFZVJeE-DJCUj-NAEC5jd` |
| QC | *(none printed)* | Quality Control Process, page 3 | `1DpY5ueaSlBqL8B5_RR2uRetj73xkfEuu` |

⚠️ **Two ID series run in parallel and their numeric suffixes alias.** `0024DPCRO001` is
Stage 1 but `0024DPNAP0001` is Stage 9; `0024DPCRO008` is Stage 8 but `0024DPNAP0008` is
Stage 6. Never key on the number alone. There is no `CRO006` and no `CRO009` — an earlier
version of this manifest listed Stage 9 as `0024DPCRO009`, which does not exist.

Derived analysis (a summary, **not** a source — it omits Stage 10's pressurisation step
and mis-attributes Annexure 1; read the PDFs): *DrinkPrime Refurb Process — Deep Analysis
& Robot Feasibility Map*, `1yrgoexHAsBVF0oLstgjpxOV6aPndGGWjUOHcRLR93gY`.

## Reading these files

The three QC pages are **100% vector line art** — 228 / 291 / 65 drawing objects, zero
raster images. Text extraction returns an unordered bag of labels **with no edges**, so
the graph topology is invisible to it. That is not a minor loss: it is how 8 of the 13
`REFER QC ANEXURE n` ovals got bound to the wrong node in our first transcription.
**Render the pages and look at them.** There is no `pdftoppm` on this machine; PyMuPDF is
in the venv and does it without installing anything:

```bash
cd /Users/pranavmulakala/WaterFilterRobo && ./venv/bin/python -c "import fitz; d=fitz.open('docs/drinkprime/QUALITY CONTROL PROCESS - PAGE 1.pdf'); d[0].get_pixmap(dpi=300).save('/tmp/qc1.png')"
```

**Hidden content, QC page 1.** Two white-filled rectangles (content-stream xrefs 21 and
22, DeviceRGB, appended after the AutoCAD export) paint over an ellipse reading
**"QC WILL MONITOR"** attached to VISUAL INSPECTION. Blank those two streams and
re-render to see it. The text was never removed from the text layer, so this reads as
someone whiting out an annotation in a PDF editor rather than concealing anything — and
the content is unremarkable. Noted because it is checkable.

**Graphics inventory, whole set:** two distinct raster images total — a 240×168 px
DrinkPrime logo repeated 18 times, and a 1×29 px table-border artifact in Stage 7. There
is **not a single photograph, exploded view, dimensioned drawing or annotated
illustration in any of the 13 files.**

## Not in this set — these are the asks

**QC Annexures 1–13.** *Most* accept/reject branches defer to one; **none are included.**
Five nodes defer to no annexure at all: VISUAL INSPECTION (the Easy/Medium/Hard triage),
UV LAMP, UV BALAST, CHECK INDIVIDUAL PART BEFORE LINE ASSEMBLY, and POST FILTER's
"@ actual condition" flow check.

⚠️ **Correction to an earlier version of this file:** Annexure 1 does **not** define the
Easy / Medium / Hard triage. On the rendered chart its ellipse attaches to
**CABINET / STICKERS CHECKING**, a later node. Annexure 1 is a cabinet/sticker cosmetic
accept-reject spec — useful to us for the cleaning station's verification criterion, but
asking only for it will *not* answer the founder's image-processing bar.

**The Easy / Medium / Hard criteria are deferred to no document anywhere in this set.**
The VISUAL INSPECTION fan-out has no annexure attached at all. So the right ask is
open-ended: *what document, if any, defines them — and if none does, do operators grade
by eye, by a wear indicator, or by feel?* Either answer unblocks work; "by feel" would
mean camera-only inspection is the wrong architecture.

Also referenced but absent: the **"Allow & Not allowed Spec. & visual Photo"** cards
(Stage 1 §8), the **LED indication Chart** (Stage 1), and the **wiring diagram** (Stage 4).

Also absent from the whole corpus: **any tolerance** (not one `±`), **any torque value**,
**any mass**, cycle time / takt, daily volume, the Easy/Medium/Hard split percentages,
cabinet outer dimensions, and **any disassembly / teardown work instruction** — the exact
motion `sim_poc3.py` and `sim_poc4.py` model has no documented counterpart here.

**STL/STEP CAD**, priority order: **membrane bowl, membrane cap, and the membrane
O-ring** (Stage 10 — the O-ring is in the material table and in no activity step, and it
is the sealing element of the joint we claim to model). Item codes `100059` / `100031` /
`100099` in Stage 9 are the only part numbers in the set and are the natural key for the
request.
