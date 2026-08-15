"""DrinkPrime's REAL refurbishment process, as data.

SOURCE: 13 documents at docs/drinkprime/ --
  * 10 work instructions, all REVISION R0, dated 11-04-2024, refs
    0024DPCRO001-005, 0024DPCRO007, 0024DPCRO008, 0024DPCRO0010,
    0024DPNAP0008 (stage 6) and 0024DPNAP0001 (stage 9).
    NOTE the two ID series collide on their numeric suffix: CRO008 is stage 8 but
    NAP0008 is stage 6, and CRO001 is stage 1 but NAP0001 is stage 9. Never key on
    the number alone. There is no CRO006 and no CRO009.
  * 3 QC flow-chart pages, which carry NO header block at all -- no reference, no
    revision, no date, no signature block. They are A3 landscape, plotted from
    AutoCAD, and are the only uncontrolled documents in the set.
Forwarded by founder Vijender Reddy via Karthik Gannoju (Yuv Industries, the plant
operator). Received 2026-08-04.

** EVERY WORK INSTRUCTION IS UNSIGNED. ** PREPARED BY / REVIEWED BY / APPROVED BY /
ISSUED BY appears at the foot of every page of all ten WIs with all four cells blank.
These are uncontrolled drafts as issued. That bears on how much weight any number here
can carry.

This module is DATA ONLY -- no MuJoCo, no controller, no side effects.

Two things to keep straight, because conflating them is how a demo starts lying:
  * STAGES / QC_NODES / QC_EDGES describe what the PLANT does. Transcribed, not
    invented. SOURCE TYPOS ARE PRESERVED DELIBERATELY ("ANEXURE", "CABINENT",
    "APPERANCE", "PRESSUE", "SOLINOID", "MEMBARANE", "Rubbing component"). They
    identify the source and they matter for string matching. Do not tidy them.
  * V5_ROUTES describes what OUR CELL does -- a deliberate subset, every entry naming
    the real stage it stands in for. `tier` and `note` fields are OUR judgement.

Run `python dp_process.py` for a readable dump.

--------------------------------------------------------------------------------------
REVISION 2026-08-04: rebuilt after reading the rendered PDFs.
The first version of this file was built from Google Drive's TEXT extraction. The three
QC pages are 100% vector line art -- text extraction returns an unordered bag of labels
with NO EDGES -- so the "REFER QC ANEXURE n" ovals got bound to whatever node happened to
be adjacent in reading order. 8 of the 13 annexure bindings were wrong, including the one
this project's headline ask was built on. Corrected below against the rendered geometry.
See PAIN_JOURNAL 2026-08-04.
--------------------------------------------------------------------------------------
"""

from dataclasses import dataclass


# All ten work instructions are unsigned. Kept as a constant so it shows up in the dump.
WI_SIGNED = False

# ============================================================ feasibility tiers
# OUR engineering judgement about robot feasibility, not DrinkPrime's.
TIERS = {
    1: "demo now -- the sim already proves this class of motion",
    2: "feasible with fixtures/tooling, post-funding",
    3: "belongs on an instrumented test bench, not on an arm",
    4: "de-scoped: deformable materials, stays human",
}


@dataclass(frozen=True)
class Stage:
    n: int
    ref: str
    title: str
    materials: tuple        # (item, uom, qty) verbatim from MATERIAL REQUIRED
    tools: tuple            # verbatim from TOOLS REQUIRED -- the TABLE, not activity prose
    activities: tuple
    checks: tuple           # (section, text) -- section tags stop CHECKS/QC/RESPONSIBILITY blurring
    scrap: tuple
    safety: tuple
    tier: int
    note: str = ""          # ours


# ==================================================================== the stages
STAGES = (
    Stage(
        n=1, ref="0024DPCRO001", title="Device Checking",
        materials=(
            ("Sediment Filter Yarn", "Nos", "1"), ("Pre -carbon filter", "Nos", "1"),
            ("RO membrane", "Nos", "1"), ("FRT 450", "Nos", "1"),
            ("WIFI bot with flow sensor", "Nos", "1"), ("Float switch", "Nos", "1"),
            ("Solenoid Valve", "Nos", "1"), ("Pump - 100 GPD", "Nos", "1"),
            ("Post Carbon with Copper", "Nos", "1"), ("UV Filter With Choke", "Nos", "1"),
        ),
        tools=("Screwdriver x1", "Pipe Cutter x1", "Pressure Gauge x2",
               "1 liter Flow Rate measuring beaker x1", "Stop Watch x1"),
        activities=(
            "Devices are categorized into three types: Easy, Medium, and Hard",
            "Connect the field return device to an input water pressure of 1 kg for testing",
            "Filters should be scrapped if they have worked for more than 6 months from "
            "the manufacturing date",
            "Sediment and Pre-carbon flow rates should be a minimum of 1200 ml/min & above",
            "RO membrane flow rate should be a minimum of 180 ml/min & above",
            "FRT flow should be between a minimum of 380 ml/min & above",
            "Pump output pressure should be minimum of 60 psi & above with flow rate of "
            "1200 ml/min",
            "SV should be tested for cut off, cut in, open flow, and body clearances",
            "Conduct LED indication test WRT to LED indication Chart",
            "Conduct a 1-liter cut off test for the WIFI bot",
            "Perform float switch cut off and cut in tests",
            "Once device testing is complete, all 'OK' filters should be drained and put "
            "back in the device",
        ),
        checks=(
            ("6 CHECKS", "Check Chassis for dent & scratches"),
            ("6 CHECKS", "Check crimping should be perfect"),
            ("8 QC RESPONSIBILITY", "Line Quality person monitoring the process every "
                                    "1 hour once for smooth process"),
            ("8 QC RESPONSIBILITY", "Allow & Not allowed Spec. & visual Photo to provided "
                                    "to the line & monitor the process"),
        ),
        scrap=("Polythene covers in respective bins only",
               "Chassis carton boxes in respective bins only",
               "Rejected filters & spare materials in designated respective bins",
               "Rejected materials removed from the testing area DAILY"),
        safety=("Keep the materials away from the gangway",),
        tier=1,
        note="The Easy/Medium/Hard split is the founder's 'image processing' bar. "
             "CRITICAL: this document names the three classes but does NOT define them, "
             "and -- corrected 2026-08-04 -- NO QC ANNEXURE GOVERNS THE TRIAGE EITHER. "
             "The flow chart attaches no annexure oval to the VISUAL INSPECTION fan-out. "
             "The class boundaries are undocumented in this set, full stop. The two named "
             "VISUAL features (chassis dents/scratches, crimping) are theirs; any boundary "
             "we use is ours. The 'Allow & Not allowed Spec. & visual Photo' cards in "
             "8 QC RESPONSIBILITY are the closest thing to a definition and were NOT sent. "
             "The flow/pressure tests here are tier 3, not arm work.",
    ),
    Stage(
        n=2, ref="0024DPCRO002", title="Cabinet Cleaning",
        materials=(("Cabinet", "-", "1"), ("Power adaptor 2A", "-", "1"),
                   ("RO Housing", "-", "1"), ("Tank", "-", "1")),
        tools=("Cleaning brush x1", "Cif polish x1 (60 devices)",
               "Moto max cream x1 (100 devices)",
               "3M Rubbing component (or Equivalent) x1 (100 devices)",
               "Colin liquid 5 Ltr (300 devices)", "Cleaning Cloth x1",
               "Sand paper - Emery sheet x1"),
        activities=(
            "Apply CIF cream to a cleaning cloth",
            "Thoroughly clean the exterior of the device, ensuring all surfaces are covered",
            "If any scratch found on cabinet need use the Rubbing component for remove "
            "the scratches",
            "Use yellow cream for any areas that require additional cleaning power",
            "Wipe off the cream with a clean, damp cloth",
            "Use a heat gun to gently warm up the stickers to loosen the adhesive",
            "Carefully peel off the stickers without damaging the surface",
            "Clean the areas thoroughly to remove any remaining adhesive residue",
            "Position the new stickers as per the original location",
            "Use a squeezer to apply the stickers, ensuring there are no air bubbles",
            "Inspect the device for any remaining stains or marks; clean any remaining "
            "spots; verify no streaks or residues",
            "Check the adapter for damage; if functioning, clean it and place it back",
        ),
        checks=(
            ("6 CHECK", "Check the device for any scratches or damages"),
            ("8 Quality Check", "Ensure the device is completely clean, with no visible "
                                "stains or marks"),
            ("8 Quality Check", "Confirm that all the stickers are removed & verify the "
                                "adapter's functionality and cleanliness"),
        ),
        scrap=("Keep polythene covers in respective bins only",),
        safety=("Keep the materials away from the gangway",),
        tier=1,
        note="The wiping/polishing pass is tier 1. Coverage is the natural robot metric "
             "and the phrase 'ensuring all surfaces are covered' supports it -- but note "
             "that phrase is a QUALIFIER INSIDE AN ACTIVITY, not the stated acceptance "
             "criterion. The actual criteria are 6 CHECK and 8 Quality Check above, which "
             "say 'completely clean, no visible stains or marks'. Do not overstate this. "
             "The sticker work in this same stage is tier 4. Consumable ratios give a "
             "per-device cost handle. NOTE the heat gun and squeezer used in activities "
             "6-10 are NOT in this stage's TOOLS table -- they are only listed in stage 5.",
    ),
    Stage(
        n=3, ref="0024DPCRO003", title="Back Panel & Top Cover Cleaning",
        materials=(),
        tools=("Brush x1", "Cloth x1", "CIF polish & Rubbing Component or Equivalent x1 each",
               "Moto max x1", "Foam x1"),
        activities=(
            "Examine the top cover and back panel for any signs of wear, tear, or "
            "discoloration",
            "Note any areas that may need special attention during cleaning or possible "
            "replacement if damaged",
            "Gather: soft/microfiber cloth, mild detergent or cleaning solution, warm "
            "water, soft brush (optional), compressed air canister (optional)",
            "Mix a small amount of mild detergent with warm water",
            "Dip the cloth in the solution and wring out excess water",
            "Gently wipe down the top cover and back panel, paying attention to dirty or "
            "stained areas",
            "For hard-to-reach areas or detailed sections, use a soft brush",
            "If using compressed air, carefully blow away dust or debris from corners and "
            "crevices",
            "Use a clean, damp cloth to wipe away any remaining soap or cleaning solution",
            "Dry thoroughly with a dry cloth to prevent water spots or damage",
        ),
        checks=(
            ("5 CHECKS", "Check the device for any scratches or damage"),
            ("7 Quality Check", "Ensure that both the top cover and back panel are "
                                "securely attached and check for any missed spots during "
                                "cleaning"),
        ),
        scrap=(),
        safety=("Keep the materials away from the gangway",),
        tier=1,
        note="Same shape as stage 2 on a different face, and it OPENS with an inspection "
             "step -- so inspect/clean/re-inspect is their own loop, not our invention. "
             "'Check for any missed spots' is camera-checkable, i.e. the verification is "
             "falsifiable by design. OPEN QUESTION, relevant to v5 reachability: the top "
             "cover and back panel appear to be DETACHED during refurb (stage 6 lists 5 "
             "back-panel assembling screws, stage 7 re-attaches the back panel), but "
             "7 Quality Check says 'securely attached'. The set contains NO teardown work "
             "instruction, so this cannot be resolved from the documents. See CONTRADICTIONS. "
             "*** THIS IS THE ONLY 'SOLUTION' IN THE ENTIRE CORPUS. *** The word appears "
             "three times in all 13 documents and every one is here, in this stage, applied "
             "TO A CLOTH: 'Dip the cloth in the solution'. The only immersion of a PART "
             "anywhere is stage 10's membrane assembly into a water bin, which is a "
             "pressurised bubble LEAK TEST and explicitly not a wash. So the founder's "
             "funding bar -- 'cleans the filter with a solution' -- is most plausibly THIS "
             "stage, i.e. a solution-charged cloth wiping the device, NOT a tank the device "
             "is lowered into. v5's CLEAN station is the same motion with a dry pad; v8 adds "
             "the charge. NOTE ALSO that this stage needs THREE cloths in sequence -- wash, "
             "then 'a clean, damp cloth' to remove the soap, then 'a dry cloth'. A one-pad "
             "cell cannot perform it faithfully; that is a hardware gap, not a software one.",
    ),
    Stage(
        n=4, ref="0024DPCRO004", title="Device Assembly",
        materials=(("Material requirement slips will be issued by unit testing person "
                    "based on that parts are consumed", "-", "-"),),
        tools=("Pipe Cutter x1", "Wire cutter x1", "Screwdriver x1", "Nose Plyer x1",
               "Cutting plyer x1", "Bosch Battery Screwdriver x1", "Teflon Tape x1"),
        activities=(
            "Filter clam fixing: place the filters in their designated locations",
            "Attach the clamp filters and secure them with screws or bolts",
            "Ensure clamps are tight enough to hold the filters firmly BUT NOT TOO TIGHT "
            "to avoid damage",
            "Pump & SV fixing: position, attach mounting brackets, secure with screws/bolts",
            "Route the wiring harness so it does not interfere with other components; "
            "secure with cable ties; connect per the wiring diagram",
            "Insert the filters into their respective housings; ensure seated correctly",
            "Insert the RO membrane into its housing; ensure properly seated and the "
            "housing sealed tightly",
            "Use a filter wrench to tighten the filter housings IF REQUIRED",
            "Measure and cut the tubing to the required lengths",
            "Attach tubing with the appropriate connectors or fittings; secure with cable "
            "ties or clamps",
        ),
        checks=(
            ("6 CHECKS", "Ensure properly that there should be no leakage @ 45 Psi "
                         "(as per BIS)"),
            ("6 CHECKS", "Ensure that the float switch is working properly"),
            ("7 Final QC", "Inspect all connections"),
            ("7 Final QC", "Run air through the system to check for leaks in the tubing "
                           "or filter housings"),
            ("7 Final QC", "Power on the device and test the functionality of all "
                           "components (pump operation, SV opening/closing, air flow "
                           "through filters with leakage test)"),
            ("7 Final QC", "QC person performs a final inspection"),
        ),
        scrap=("Polythene covers/packing carton in the respective bins only",
               "Dust caps in the respective bins only"),
        safety=("Keep the material away from the gang way",
                "Keep the Device cabinets covered with polythene cover to avoid dust & "
                "scratches"),
        tier=2,
        note="Mixed. Filter/membrane insertion + wrench tightening is our motion class "
             "with a wrench-shaped end effector (tier 2). Screw-driving is solved with a "
             "torque driver (tier 2). Harness routing and tubing cut/route are tier 4. "
             "'Tight enough to hold firmly but not too tight to avoid damage' is THE ONLY "
             "force/preload constraint in all 13 documents -- and it is qualitative. "
             "Note also that this stage's MATERIAL section is a sentence, not a table: "
             "stage 1's test station drives stage 4's material issuance.",
    ),
    Stage(
        n=5, ref="0024DPCRO005", title="Sticker Pasting",
        materials=(),
        tools=("Hot Air gun", "Colin liquid", "Sticker Squeezer", "CIF polish cream"),
        activities=(
            "Remove the old sticker using a hot air gun",
            "Clean the area using CIF cream to ensure it is free from any residue",
            "Paste the new aesthetic sticker and apply with a squeegee",
        ),
        checks=(
            ("5 CHECKS", "Ensure that the rocker switch connections are done correctly"),
            ("7 Quality Check", "Ensure that Paste stickers are properly pasted or not and "
                                "check for any missed spots during cleaning"),
        ),
        scrap=("EPS sheet in the respective bin",),
        safety=("Keep the materials away from the gangway",),
        tier=4,
        note="Pure deformable handling. De-scoped, deliberately. ODDITY WORTH KEEPING: "
             "5 CHECKS in a sticker-pasting stage reads 'Ensure that the rocker switch "
             "connections are done correctly' -- nothing in this stage touches wiring. "
             "It is a copy-paste from another document. Their work instructions are not "
             "internally airtight, which is a reason to ask questions rather than infer. "
             "See also CONTRADICTIONS: stage 2 already removes and re-applies stickers.",
    ),
    Stage(
        n=6, ref="0024DPNAP0008", title="Final Testing",
        materials=(("Device", "Nos", "1"), ("Accessory pouch", "Nos", "1"),
                   ("Power adaptor 2A", "Nos", "1"),
                   ("Back panel assembling Screws", "Nos", "5")),
        tools=("Ball Valve x1", "Air regulator and pressure Gauge x1"),
        activities=(
            "Ensure that the sponsor code and PID are correctly mapped in the DP assembly app",
            "Record the materials used for the refurbishment process in the system",
            "Perform an air leak test by applying an input air pressure of 45 PSI; spray "
            "Colin to detect any leaks in the elbow assembly",
            "Inspect other parts and connections for leakage. Hold at this pressure for "
            "15 min. There shall not be any leakage water bubbles (sprayed Colin) or "
            "hissing noise",
            "Release the pressure by opening the open/close valve and turn off the "
            "pressurization pump",
            "Verify the functionality of the float cut off/cut in and adaptor",
            "Secure the float sensor with filament tape inside the tank lid in its "
            "original position",
            "Clean & pack the devices",
        ),
        checks=(("5 CHECKS", "Ensure that the back cover and Front facia are "
                             "aesthetically ok"),
                ("6 RESPONSIBILITY", "Operator & Line QC person")),
        scrap=(),
        safety=("Keep the material away from the gang way",),
        tier=3,
        note="The pressure test is bench work, not arm work -- worth SAYING to the "
             "founder, it shows judgement. The DP assembly app / PID mapping / material "
             "recording is the software-integration surface: their line already runs on a "
             "workflow system any robot cell has to talk to. NOTE the 5 back-panel "
             "assembling SCREWS in the material list, which conflicts with stage 7's "
             "filament tape -- see CONTRADICTIONS.",
    ),
    Stage(
        n=7, ref="0024DPCRO007", title="Device Packing",
        materials=(("Back Panel", "Nos", "1"), ("Filament Tape", "Mtr", "0.5"),
                   ('BOPP Tape 3" with DP Logo', "Mtr", "1"),
                   ('BOPP TAPE 1" TRANSPARENT', "Mtr", "0.5")),
        tools=("Tape Gun x1", "Microfiber cloth x1", "Permanent Marker x1", "CIF Cream x1"),
        activities=(
            "Verify accessories and adaptors; mark with a tick to indicate verification",
            "Assemble the back panel onto the device using filament tape",
            "Polish the device",
            "Perform a visual inspection",
            "Complete the packing process for shipment or storage",
        ),
        checks=(("7 QC CHECKS", "Ensure that the box should not open when we handle "
                                "the box"),
                ("7 QC CHECKS", "Ensure that the serial no. written, and the bar code "
                                "should be of the same no.")),
        scrap=(),
        safety=("Keep the materials away from the gangway",),
        tier=2,
        note="Barcode/serial matching is a camera task we could do; the taping is tier 4. "
             "The tick-mark verification is recorded with a permanent marker -- a paper "
             "trail a robot cell would have to replace with something.",
    ),
    Stage(
        n=8, ref="0024DPCRO008", title="Accessories Packing",
        # NB: this table's UOM and QTY columns are SWAPPED in the source -- every row
        # reads e.g. "TAP Assembly | 1 | NOS". Recorded as (item, uom, qty) corrected.
        materials=(("TAP Assembly", "NOS", "1"),
                   ("M5X50 NYLON SCREW ANCHOR (ROYAL PLUG PLASTIC ANCHOR OR GATTA)",
                    "NOS", "2"),
                   ('M5X50 WALL MOUNTING SCREW (2"/3")', "NOS", "2"),
                   ("Polycover -2 X 3", "NOS", "1"),
                   ("LABELING -LIST OF ITEM DETAILS", "NOS", "1")),
        tools=("Stapler", "Marker Pen"),
        activities=(
            "Once all accessories are packed securely, close it",
            "Seal it with packing Stapler, ensuring all seams are covered and secure",
            "Check the packing list label & cross verify all the materials available",
        ),
        checks=(("Final QC", "Inspect the sealed cover for any signs of damage or weak "
                             "points"),
                ("Final QC", "Ensure all labels are correctly placed and readable"),
                ("Final QC", "Packing-list verification")),
        scrap=(),
        safety=("Keep the materials away from the gangway",),
        tier=2,
        note="Kitting is classic pick-and-place. Feasible, unexciting, and not what the "
             "funding conversation is about. The M5x50 screws and the 2\"/3\" wall screw "
             "are among the only dimensioned parts in the whole document set.",
    ),
    Stage(
        n=9, ref="0024DPNAP0001", title="Pump Assembly",
        materials=(("PUMP CX 100-GPD", "No.", "1", "100059"),
                   ('PUMP ELBOW 1/4" (1/4" PF TO THREAD)', "Nos", "2", "100031"),
                   ("TEFLON TAPE", "MTR", "1", "100099")),
        tools=("Spanner", "End plug", "Pressure Gauge", "Colin"),
        activities=(
            'Take PUMP ELBOW 1/4" and wound the Teflon tape on the threaded portion with '
            "approx. 20 to 30 rounds",
            "Insert the elbows into the pump head thread and tighten with the help of "
            "spanner tool & make ensure without damage",
            "Check for leakage: pass 80-90 PSI air",
            "Spray Colin on the pump head threaded area",
            "Leak test passed: clean the pump head and move to production line, otherwise "
            "sent for rework",
        ),
        checks=(("6 CHECKS", "Ensure that all the connections are tightened properly"),),
        scrap=("Keep the scrap in the respective bins only",),
        safety=("Keep the material away from the gang way",),
        tier=4,
        note="Gated by Teflon winding, which is tier 4. The threading itself is tier 2. "
             "THE ONLY DOCUMENT IN THE SET WITH PART NUMBERS (100059, 100031, 100099) -- "
             "these are the natural key for a CAD request. Its reference is 0024DPNAP0001, "
             "NOT 0024DPCRO009; the first version of this file and the README both had "
             "that wrong.",
    ),
    Stage(
        n=10, ref="0024DPCRO0010", title="Membrane Assembly",
        materials=(("MEMBRANE BOWL", "No.", "1"), ("MEMBRANE CAP", "Nos", "1"),
                   ('MH ELBOW 1/4"(MEMBARANE ELBOW )', "Nos", "2"),
                   ('MEMBRANE "O-Ring"', "Nos", "1"),
                   ('PF ELBOW 1/4"  (1/4" PF TO THREAD )', "Nos", "1"),
                   ("TEFLON TAPE", "MTR", "1")),
        tools=("Spanner x1", "End plug x1", "Pressure Gauge x1", "Colin x1",
               "Ball valve x1", "PL4 Tube 0.5 Mtr", "Water Bin x1", "Cleaning Cloth x1"),
        activities=(
            '3.1 Take PF ELBOW 1/4" and MH ELBOW 1/4" (MEMBARANE ELBOW) and wound the '
            "Teflon tape on the threaded portion with approx. 20 to 30 rounds",
            '3.2 Insert the PUMP ELBOW 1/4" [sic -- stage 9\'s part name; this stage\'s '
            'table lists PF ELBOW] into the Membrane cap head thread & tighten with the '
            "help of spanner tool & make ensure without damage",
            '3.3 Insert the MH ELBOW 1/4" into the Membrane bowl Reject & outlet thread & '
            "tighten with the help of spanner tool & make ensure without damage",
            "3.4 Insert the membrane inside the bowl & close with the membrane cap assembly",
            "3.5 Ensure the cap is tightened properly with spanner assembly",
            "3.6 Check for leakage, pass the 80-90 PSI air in the inlet of the membrane "
            "cap head & close the outlet (Permeate) with End plug & close the reject "
            "outlet with ball valve",
            "3.7 Dip the membrane assembly in the water bin & Check for leakage",
            "3.8 Leak test passed, Clean the membrane and move to production line, "
            "otherwise sent for rework",
        ),
        checks=(("6 CHECKS", "Ensure that all the connections are tightened properly"),
                ("4.2 SCRAP DISPOSAL", "QC persons validate & certify the rejection every "
                                       "2 hrs. once in the line")),
        scrap=("Keep the scrap in the respective bins only",),
        safety=("Keep the material away from the gang way",),
        tier=1,
        note="The station our sim approximates: insert a cylindrical element into a bowl, "
             "secure by rotating a cap, dip in water, verify. THREE THINGS TO KEEP "
             "STRAIGHT: (a) the cap is THREADED and spanner-tightened -- multi-turn "
             "rotation to a torque criterion, NOT a 55-degree indexed bayonet like ours; "
             "(b) the dip follows a pressurisation to 80-90 PSI with the permeate "
             "end-plugged and the reject valve closed, so it is a BUBBLE TEST, not a wash "
             "-- though note the document never explicitly says the pressure is MAINTAINED "
             "through the dip, so that is our inference from the 3.6 -> 3.7 ordering; "
             "(c) there is a MEMBRANE O-RING in the material table that appears in NO "
             "activity step. It is the sealing element of the joint we claim to model. "
             "Any v5 membrane scene without it is modelling a joint that cannot seal.",
    ),
)

STAGE_BY_N = {s.n: s for s in STAGES}


# =================================================================== the QC flow
# Rebuilt 2026-08-04 from the RENDERED flow charts. The pages are pure vector line art;
# text extraction returns labels with no edges, which is how 8 of 13 annexure bindings
# came out wrong the first time.
#
# Node shape carries meaning: RECTANGLES are process steps; ELLIPSES are annotations or
# states, attached by dashed leaders. That is why LINE QC VALIDATION / APPROVAL is a
# comment on MOVE TO REJECTION BIN and not a step of its own.
#
# HIDDEN CONTENT, page 1: two white-filled rectangles (content-stream xrefs 21 and 22,
# DeviceRGB, appended AFTER the AutoCAD export) paint over an ellipse reading
# "QC WILL MONITOR" attached to VISUAL INSPECTION by a dashed leader. Blanking those two
# streams and re-rendering recovers it. The text was never removed from the text layer,
# so this reads as someone whiting out an annotation in a PDF editor, NOT as an attempt
# to conceal -- and the content is unremarkable. Recorded because a claim about a
# customer's document should be checkable.
@dataclass(frozen=True)
class QCNode:
    name: str
    outcomes: tuple
    annexure: int | None = None
    note: str = ""


QC_NODES = (
    # --- page 1: intake and triage
    QCNode("FIELD RETURN DEVICE", ("visual inspection",),
           note="Entry node of the whole chart."),
    QCNode("VISUAL INSPECTION", ("EASY", "MEDIUM", "HARD"), annexure=None,
           note="*** NO ANNEXURE ATTACHED. *** The first version of this file said "
                "Annexure 1 governs this node; it does not -- Annexure 1 hangs off "
                "CABINENT / STICKERS CHECKING, further down. The Easy/Medium/Hard "
                "criteria are deferred to NO named document anywhere in this set. "
                "Annotated by the whited-out ellipse 'QC WILL MONITOR'."),
    QCNode("EASY", ("-> merge vertex -> UNIT TESTING",),
           note="Its edge carries no label -- only MEDIUM and HARD are labelled "
                "RECTIFIABLE."),
    QCNode("MEDIUM", ("RECTIFIABLE -> merge vertex -> UNIT TESTING",)),
    QCNode("HARD", ("RECTIFIABLE -> merge vertex -> UNIT TESTING",
                    "NON RECTIFIABLE -> SEND FOR SCRAP APPROVAL"),
           note="HARD is NOT a dead end -- it forks. All three rectifiable paths converge "
                "on a single vertex above UNIT TESTING."),
    QCNode("SEND FOR SCRAP APPROVAL (RECTIFICATION COST GREATER THAT 80-90%)", ("terminal",),
           note="'GREATER THAT' is the source typo. 80-90% OF WHAT is not stated."),
    QCNode("UNIT TESTING", ("CABINENT / STICKERS CHECKING", "DEVICE FUNCTION")),
    QCNode("CABINENT / STICKERS CHECKING",
           ("OK -> CLEANING -> CABINENT ISSUED TO PRODUCTION -> (2)", "NOT OK -> SCRAP"),
           annexure=1,
           note="*** THIS is what Annexure 1 governs: cabinet/sticker cosmetic "
                "accept-reject. *** Directly relevant to our CLEAN station's verification "
                "criterion -- but it is NOT the triage definition."),
    QCNode("DEVICE FUNCTION", ("per-component trunk, 6 branches on page 1, "
                              "8 more on page 2 via connector (1)",)),
    QCNode("SEDIMENT / PRE CARBON FILTER CHECK PHYSICAL APPERANCE",
           ("ACCEPT -> MOVE TO PRODUCTION -> (2)", "REJECT -> SCRAP"), annexure=2,
           note="Then CHECK FLOW RATE/AT 1Kg/Cm2 PRESSUE INPUT WATER."),
    QCNode("POST FILTER CHECK PHYSICAL APPERANCE & DEVICE MFG PID",
           ("OK -> CHECK FLOW RATE @ ACTUAL CONDITION", "NOT OK -> SCRAP"), annexure=3,
           note="Its flow check is '@ ACTUAL CONDITION' -- NOT at 1 kg/cm2 -- and that "
                "check has ACCEPT/REJECT edges but no annexure of its own."),
    QCNode("FRT CHECK PHYSICAL APPERANCE",
           ("ACCEPT -> MOVE TO PRODUCTION -> (2)", "REJECT -> SCRAP"), annexure=4,
           note="'FRT' is never expanded anywhere in the document set."),
    QCNode("TDS CONTROLLER -> CHECK FLOW RATE & LEAKAGE TEST",
           ("ACCEPT -> CLEAN & MOVE TO PRODUCTION -> (2)", "REJECT -> SCRAP"), annexure=5,
           note="No input pressure is stated for this branch."),
    QCNode("SOLINOID VALVE",
           ("WORKING -> CHECK SV FLOW RATE -> SEND TO CLEANING PROCESS",
            "NOT WORKING -> CHECK WARRANTY"), annexure=6,
           note="Annexure 6 attaches to SEND TO CLEANING PROCESS. OUT WARRANTY forks to "
                "'vendor refurbish' OR 'scrap' with NO condition on either edge."),
    # --- page 2: components 7-14
    QCNode("PUMP", ("accept -> cleaning -> MOVE TO PRODUCTION -> (2)", "reject -> SCRAP",
                    "not working -> warranty branch"), annexure=7),
    QCNode("WIFI / BLE BOT", ("working -> cleaning -> MOVE TO PRODUCTION -> (2)",
                              "in-warranty -> vendor replacement",
                              "out-warranty -> SEND FOR REWORK"), annexure=8,
           note="Out-of-warranty goes to REWORK here, not scrap."),
    QCNode("UV HOUSING / QG TUBE", ("CHECK PHYSICAL DAMAGE -> cleaning -> production -> (2)",
                                    "scrap"), annexure=9),
    QCNode("RO MEMBRANE CHECK APPERANCE", ("accept -> MOVE TO PRODUCTION -> (2)",
                                           "reject -> SCRAP"), annexure=10,
           note="Flow rate at 1 kg/cm2 input water."),
    QCNode("ALL CONNECTORS", ("accept -> cleaning -> MOVE TO PRODUCTION -> (2)",
                              "reject -> SCRAP"), annexure=11,
           note="Printed 'ANEXURE11' with no space. This node was missing entirely from "
                "the first version of this file."),
    QCNode("POWER ADAPTOR WORKING FUNCTION",
           ("working -> CLEANING -> ACCESSORIES PACKING", "not working -> warranty branch"),
           annexure=12,
           note="THE ONE COMPONENT BRANCH THAT DOES NOT REACH connector (2). Its pass "
                "path dead-ends at ACCESSORIES PACKING, not at re-assembly."),
    QCNode("UV LAMP", ("cleaning -> MOVE TO PRODUCTION -> (2)", "scrap"), annexure=None,
           note="No annexure. The first version wrongly assigned it 10."),
    QCNode("UV BALAST", ("cleaning -> MOVE TO PRODUCTION -> (2)", "warranty branch"),
           annexure=None,
           note="No annexure. 'BALAST' is the source spelling. Out-warranty forks with no "
                "stated condition, same as the solenoid valve."),
    QCNode("CHECK WARRANTY (repeated sub-pattern)",
           ("INWARRANTY -> SEND VENDOR FOR REPLACEMENT",
            "OUT WARRANTY -> refurbish / rework / scrap, varies by component"),
           note="Not one node -- repeated under SV, UV BALAST, WIFI/BLE, PUMP and POWER "
                "ADAPTOR, with DIFFERENT outcomes each time. The '1 WEEK' timeline is "
                "printed only on the PUMP and POWER ADAPTOR branches, not universally."),
    # --- page 3: re-assembly and final QC
    QCNode("NEW MATERIAL ISSUED FROM STORE", ("CHECK INDIVIDUAL PART BEFORE LINE ASSEMBLY",),
           note="A SECOND, independent entry node -- new parts, not field returns."),
    QCNode("CHECK INDIVIDUAL PART BEFORE LINE ASSEMBLY",
           ("accept -> DEVICE ASSEMBLY", "reject -> MOVE TO REJECTION BIN"), annexure=None,
           note="MOVE TO REJECTION BIN is annotated by the ellipse 'LINE QC VALIDATION / "
                "APPROVAL' on a dashed leader -- line QC validates the REJECTION, which "
                "matches stage 10's 'QC persons validate & certify the rejection every "
                "2 hrs'. The first version made that ellipse a process node."),
    QCNode("DEVICE ASSEMBLY", ("FINAL LINE TEST @ 80PSI AIR PRESSURE",),
           note="Fed by connector (2) from all 13 cleared-component paths."),
    QCNode("FINAL LINE TEST @ 80PSI AIR PRESSURE",
           ("OK -> PACKAGING", "reject -> REWORK TO BE DONE"), annexure=13,
           note="*** 80 PSI here vs 45 PSI for the same operation in stages 4 and 6. "
                "See CONTRADICTIONS -- this one is a safety question. ***"),
    QCNode("FINAL QC CHECK DONE FOR THE LOT PRODUCTION WITH SAMPLING",
           ("ACCEPT -> MOVE TO FG STORE", "REJECT -> SENT ENTIRE LOT TO REWORK"),
           note="No AQL, no lot size, no sample size given."),
)

# Off-page connectors, which exist only as graphics.
QC_CONNECTORS = {
    "(1)": "Continuation of the single DEVICE FUNCTION component trunk from page 1 to "
           "page 2. Not a decision.",
    "(2)": "Collector for everything cleared for re-assembly: 6 sources on page 1, 8 on "
           "page 2, converging on DEVICE ASSEMBLY on page 3. POWER ADAPTOR is the one "
           "component branch that never reaches it.",
}


# ============================================================== pressure regimes
PRESSURES = {
    "input water test -- stage 1, and the QC sediment/pre-carbon, FRT, SV, pump and "
    "RO-membrane branches": "1 kg/cm^2 (stage 1 prints a bare '1 kg'; the QC chart "
                            "supplies the denominator in full)",
    "post-filter flow check": "'@ ACTUAL CONDITION' -- no pressure stated",
    "TDS controller flow & leakage test": "no pressure stated",
    "pump output acceptance -- stage 1": "60 psi minimum at 1200 ml/min",
    "assembled-device leak test -- stage 4 CHECKS, stage 6 activities": "45 PSI, per BIS",
    "pump subassembly leak test -- stage 9": "80-90 PSI air",
    "membrane subassembly leak test -- stage 10": "80-90 PSI air",
    "FINAL LINE TEST -- QC flow page 3": "80 PSI air  <-- CONTRADICTS the 45 PSI above",
}


# ============================================================== contradictions
# Recorded, not reconciled. Guessing which one governs is exactly the kind of invention
# this file exists to prevent.
CONTRADICTIONS = (
    ("PRESSURE, and it is a safety question",
     "Stage 4 CHECKS and stage 6 activities both specify 45 PSI (stage 4 adds 'as per "
     "BIS') for the assembled-device leak test, held 15 min. QC flow page 3 specifies "
     "FINAL LINE TEST @ 80PSI AIR PRESSURE for what appears to be the same operation. "
     "1.8x apart. It changes the regulator, the fixture, the containment and the safety "
     "case. ASK BEFORE BUILDING ANY LEAK-TEST STATION."),
    ("Back panel: screwed or taped?",
     "Stage 6 material list includes 'Back panel assembling Screws, Nos, 5'. Stage 7 "
     "activity 2 says 'Assemble the back panel onto the device using filament tape'. Two "
     "fastening methods for the same part in consecutive stages. This also blocks "
     "resolving whether the back panel is detached during cleaning -- which matters for "
     "v5, since the back face is unreachable by the arm (see V5_PLAN)."),
    ("Stickers applied twice, or one stage is redundant",
     "Stage 2 activities 6-10 remove old stickers with a heat gun and apply new ones with "
     "a squeezer. Stage 5 is an entire stage that does the same thing again. Neither "
     "references the other, and stage 2 does not even list the heat gun or squeezer in "
     "its TOOLS table -- stage 5 does."),
    ("Stage 10 names a part that is not in its own material list",
     "3.1 says take the PF ELBOW 1/4\". 3.2 then says insert the PUMP ELBOW 1/4\". "
     "PUMP ELBOW is stage 9's part (item code 100031) and appears nowhere in stage 10's "
     "material table. Copy-paste from the pump work instruction."),
    ("Stage 5's CHECKS belong to another process",
     "The Sticker Pasting Process 5 CHECKS reads 'Ensure that the rocker switch "
     "connections are done correctly'. Nothing in that stage touches wiring."),
    ("Reference-number series collide",
     "Two ID series run in parallel and their numeric suffixes alias: 0024DPCRO001 "
     "(stage 1) vs 0024DPNAP0001 (stage 9); 0024DPCRO008 (stage 8) vs 0024DPNAP0008 "
     "(stage 6). Never key on the number alone."),
    ("Stage 8's material table has its columns swapped",
     "Header reads S.NO. | ITEM NAME | UOM | QTY., but every data row reads e.g. "
     "'TAP Assembly | 1 | NOS' -- quantity in the UOM column, unit in the QTY column, "
     "for all five rows."),
)


# ============================================================= scrap topology
# v3/v4 model a single bin. The real line has at least six destinations.
SCRAP_STREAMS = (
    "polythene covers (stages 1, 2, 4)",
    "chassis carton boxes (stage 1)",
    "rejected filters & spare materials (stage 1)",
    "packing carton (stage 4)",
    "dust caps (stage 4)",
    "EPS sheet (stage 5)",
    "MOVE TO REJECTION BIN (QC page 3, line-assembly part rejects)",
    "CADENCE: rejected materials removed from the testing area DAILY (stage 1); "
    "QC persons validate & certify rejections every 2 hrs (stage 10, QC page 3); "
    "line QC monitors the process every 1 hour (stage 1)",
)


# ================================================================= our v5 subset
@dataclass(frozen=True)
class Route:
    grade: str
    stage_ref: int
    steps: tuple
    note: str = ""


# The class NAMES are DrinkPrime's. The class BOUNDARIES are OURS -- not because an
# annexure is missing, but because NO document in the set defines them at all.
#
# PARTIAL UPDATE 2026-08-12, VERBAL -- see FOUNDER_VERBAL below. The founder has now
# defined the grades BY OUTCOME (device not changed / some parts changed / entire device
# changed). That is a definition of what each grade MEANS, not of how to RECOGNISE one:
# the VISUAL criteria the camera needs are still undefined, so the triage station's class
# boundaries remain OURS and must go on being labelled that way.
TRIAGE_GRADES = ("easy", "medium", "hard")

# ============================================== founder statements, VERBAL only
# Everything in this block is SECONDHAND: relayed by Teja, same provenance chain as the
# Anirudh feedback. Nothing here is in writing. Do not blur these with the 13 source
# documents above (which are primary) or with our sim boundaries (which are ours).
FOUNDER_VERBAL = {
    "date": "2026-08-12",
    "provenance": "verbal, relayed by Teja -- secondhand, not recorded, not in writing",
    "grade_definitions_by_outcome": {
        # His words, as relayed. These are OUTCOME definitions -- what happened to the
        # unit -- not visual criteria a camera can apply to an incoming one.
        "easy": "device not changed",
        "medium": "some parts changed",
        "hard": "entire device changed",
    },
    "note_ours": "Checked against V5_ROUTES above, our route semantics already match "
                 "his outcomes: EASY = clean only (nothing replaced), MEDIUM = membrane "
                 "subassembly rebuilt (some parts changed), HARD non-rectifiable = "
                 "scrap/replace (entire device). That agreement is OUR observation, not "
                 "his confirmation. What remains undefined is the VISUAL criterion: what "
                 "an operator SEES on an incoming unit that predicts which outcome it "
                 "needs. Our soil/scratch/dent pools are a stand-in for that and must "
                 "keep being labelled OURS.",
    "incoming": "process VIDEO and REAL IMAGES promised within days; founder wants US "
                "to build the image classification. v5_real_triage.py is the intake "
                "harness (blind protocol, missed-hard headline, exact binomial CIs).",
}

V5_ROUTES = {
    "easy": Route(
        grade="easy", stage_ref=2,
        steps=("TRIAGE", "CLEAN_CABINET", "VERIFY_CLEAN", "PASS"),
        note="Their EASY edge carries no condition label -- it goes straight to unit "
             "testing. We model the cosmetic path: exterior wipe pass and re-inspect."),
    "medium": Route(
        grade="medium", stage_ref=10,
        steps=("TRIAGE", "CLEAN_CABINET", "VERIFY_CLEAN",
               "MEMBRANE_INSERT", "CAP_TIGHTEN", "LEAK_DIP", "VERIFY_LEAK", "PASS"),
        note="Their MEDIUM edge is labelled RECTIFIABLE. Cosmetic plus a stage-10 "
             "membrane subassembly rebuild."),
    "hard_rectifiable": Route(
        grade="hard_rectifiable", stage_ref=10,
        steps=("TRIAGE", "CLEAN_CABINET", "VERIFY_CLEAN",
               "MEMBRANE_INSERT", "CAP_TIGHTEN", "LEAK_DIP", "VERIFY_LEAK", "PASS"),
        note="CORRECTED 2026-08-04: HARD is not a dead end. Their chart forks it. The "
             "rectifiable branch rejoins the same line as MEDIUM."),
    "hard_non_rectifiable": Route(
        grade="hard_non_rectifiable", stage_ref=1,
        steps=("TRIAGE", "ROUTE_TO_SCRAP_APPROVAL"),
        note="NON RECTIFIABLE -> SEND FOR SCRAP APPROVAL (rectification cost greater "
             "that 80-90%). We stop at routing it out of the line."),
}

# v4 graded a CARTRIDGE; v5 grades a UNIT. Kept so the mapping is explicit.
V4_TO_REAL = {
    "clean": "stage 1 pass-through -- no plant analogue at cartridge scale",
    "light": "stage 2/3 cleaning, applied to a part instead of a cabinet",
    "heavy": "QC 'reject -> scrap' branch, Annexure 10 (RO MEMBRANE)",
}


# ================================================================== what we lack
MISSING = (
    "QC ANNEXURES 1-13 -- every accept/reject branch defers to one; ZERO are included. "
    "CORRECTED 2026-08-04: Annexure 1 governs CABINET/STICKER accept-reject, NOT the "
    "Easy/Medium/Hard triage. Asking only for 'Annexure 1' returns a cabinet cosmetics "
    "spec and does NOT answer the founder's image-processing bar.",
    "*** THE EASY / MEDIUM / HARD *VISUAL* CRITERIA. (Half-answered 2026-08-12: the "
    "founder verbally defined the grades BY OUTCOME -- see FOUNDER_VERBAL. Still missing "
    "is what an operator SEES that predicts the outcome.) No annexure and no document in this set "
    "defines them. The correct ask is open-ended: what document, if any, defines them -- "
    "and if none does, do operators grade by eye, by a wear indicator, or by FEEL? "
    "Either answer unblocks work; 'by feel' would mean camera-only inspection is the "
    "wrong architecture.",
    "The 'Allow & Not allowed Spec. & visual Photo' cards (stage 1, section 8) and the "
    "'LED indication Chart' (stage 1) -- both referenced, neither sent.",
    "The wiring diagram (stage 4).",
    "STL/STEP CAD. Priority parts: MEMBRANE BOWL, MEMBRANE CAP and the MEMBRANE O-RING "
    "(stage 10). Item codes 100059 / 100031 / 100099 (stage 9) are the only part numbers "
    "in the set and are the natural key for the request.",
    "ANY dimension beyond 1/4\" fittings, M5x50 screws and tape lengths. No cabinet "
    "envelope, no housing diameter, no membrane size, no tank capacity, no O-ring size, "
    "no thread pitch.",
    "ANY tolerance. There is not a single '+/-' in the corpus.",
    "ANY torque value, despite three stages saying 'tighten with spanner without damage' "
    "and 'not too tight to avoid damage'.",
    "ANY mass or weight -- so no gripper payload or arm sizing can be derived.",
    "Cycle time / takt per stage, daily refurb volume, line balance, operator count.",
    "The Easy/Medium/Hard split percentages -- we do not know the class priors.",
    "A DISASSEMBLY / TEARDOWN work instruction. The set runs Checking -> Cleaning -> "
    "ASSEMBLY. Nothing documents how covers come off, how filters are extracted, or how "
    "housings are opened. *** The exact motion sim_poc3/sim_poc4 model -- extracting a "
    "seated, twist-locked cartridge -- has NO work instruction in this corpus. ***",
    "A REWORK work instruction, despite three separate routes to 'SEND FOR REWORK'.",
    "Heat-gun temperature/standoff/dwell, emery grit, 'warm water' with no temperature, "
    "Teflon wrap direction, TDS target in ppm, sampling plan/AQL, gangway width.",
)


def _dump():
    print("DrinkPrime refurbishment process -- 10 work instructions (R0, 11-04-2024, "
          "ALL UNSIGNED)\n" + " " * 4 + "+ 3 QC flow-chart pages (no header, no revision, "
          "no date)\n")
    for s in STAGES:
        print(f"Stage {s.n:>2}  [{s.ref}]  {s.title}")
        print(f"          tier {s.tier}: {TIERS[s.tier]}")
        if s.materials:
            print("          materials:")
            for m in s.materials:
                code = f"  code {m[3]}" if len(m) > 3 else ""
                print(f"            - {m[0]}  [{m[1]} x{m[2]}]{code}")
        if s.tools:
            print(f"          tools: {'; '.join(s.tools)}")
        print("          activities:")
        for a in s.activities:
            print(f"            - {a}")
        if s.checks:
            print("          checks:")
            for sec, c in s.checks:
                print(f"            [{sec}] {c}")
        if s.scrap:
            print(f"          scrap: {'; '.join(s.scrap)}")
        if s.note:
            print(f"          OURS:  {s.note}")
        print()

    print("QC flow  (rebuilt from the rendered vector charts)\n" + "-" * 70)
    for q in QC_NODES:
        ann = f"   [ANEXURE {q.annexure}]" if q.annexure else ""
        print(f"  {q.name}{ann}")
        for o in q.outcomes:
            print(f"      -> {o}")
        if q.note:
            print(f"      note: {q.note}")
    print("\n  off-page connectors:")
    for k, v in QC_CONNECTORS.items():
        print(f"    {k}  {v}")

    print("\nPressure regimes\n" + "-" * 70)
    for k, v in PRESSURES.items():
        print(f"  {k}\n      {v}")

    print("\nCONTRADICTIONS IN THE SOURCE -- recorded, not reconciled\n" + "-" * 70)
    for title, body in CONTRADICTIONS:
        print(f"  * {title}\n      {body}")

    print("\nScrap topology (v3/v4 model ONE bin)\n" + "-" * 70)
    for s in SCRAP_STREAMS:
        print(f"  - {s}")

    print("\nv5 routes (OUR cell, a subset)\n" + "-" * 70)
    for g, r in V5_ROUTES.items():
        print(f"  {g:<22} (stage {r.stage_ref}): {' -> '.join(r.steps)}")
        print(f"  {'':22}  {r.note}")
    print("\n  WARNING: the grade NAMES are DrinkPrime's. The grade BOUNDARIES are OURS --")
    print("  and not because an annexure is missing, but because NO document in the set")
    print("  defines them at all. Say so wherever a triage number is reported.")

    print("\nStill missing -- ask for these\n" + "-" * 70)
    for m in MISSING:
        print(f"  - {m}")

    by_tier = {}
    for s in STAGES:
        by_tier.setdefault(s.tier, []).append(s.n)
    print("\nFeasibility summary\n" + "-" * 70)
    for t in sorted(by_tier):
        print(f"  tier {t}: stages {by_tier[t]}  -- {TIERS[t]}")


if __name__ == "__main__":
    _dump()
