"""V5-A -- generate the unit-scale refurbishment scene.

Emits `ufactory_xarm7/refurb_scene_v5.xml`. Run it to regenerate; the XML is committed
so the sim does not depend on running this first.

WHY A GENERATOR. v4's 44 deposit geoms are hand-written into the scene XML as an opaque
block of numbers -- reproducible, but nobody can tell where they came from or check that
they land on the part. Here the pools are generated from a FIXED SEED with the placement
rule written down, so the numbers are auditable and the distribution can be changed
without hand-editing 80 lines.

WHAT THE THREE POOLS ARE, AND WHY THERE ARE THREE
-------------------------------------------------
This is the one design decision in V5-A that is doing real work, so it is spelled out.

DrinkPrime's own documents name three different kinds of surface condition and treat
them differently:

  * Stage 1, CHECKS:  "Check Chassis for dent & scratches"
  * Stage 2, activity: "Apply CIF cream ... Thoroughly clean the exterior"
  * Stage 2, activity: "If any scratch found on cabinet need use the Rubbing component
                        for remove the scratches"
  * Stage 3, activity: "Examine ... for any signs of wear, tear, or discoloration"

So THEIR process already distinguishes: dirt that wipes off with cream, scratches that
need a second, more aggressive pass with rubbing compound, and dents, which no cleaning
step in any of the ten stages addresses. That maps onto a three-way severity grade:

    soil       -> comes off with the normal wipe          -> EASY
    scratch    -> needs the rubbing-compound pass         -> MEDIUM
    dent       -> no documented remedy; cosmetic reject   -> HARD

** WHAT IS THEIRS AND WHAT IS OURS. ** The three FEATURES above are theirs, quoted. The
three CLASS NAMES (Easy/Medium/Hard) are theirs. The MAPPING between them, and every
numeric cut point, is OURS -- no document in the set defines the Easy/Medium/Hard
boundaries (see dp_process.MISSING). This is a defensible, source-grounded taxonomy, not
a validated one, and anything reporting a triage number has to say so.

Ground truth is kept CRISP -- non-overlapping counts per class, as in v4. The difficulty
the classifier has to overcome comes from occlusion, lighting and viewing pose, not from
fuzzing the labels. A classifier that scores well because we made the labels vague has
measured nothing.

FACE COVERAGE. Pools go on ALL FIVE exposed faces: front (-X), back (+X), top, left and
right. The back was excluded originally because V5-0 measured it unreachable at every
placement tested (0/48 raster points, eight placements); the ROTARY INDEXER removed that
limit -- every vertical face now rotates to the front working position at 100%. Back-face
pools sit on the BACK PANEL'S OUTER SURFACE, which is what is actually exposed.
So "coverage" now means coverage OF THE DEVICE, with no face silently excluded.
"""
import argparse
import numpy as np

# ------------------------------------------------------------------ cell layout
# Placement from V5-0 (sim_poc/v5_reach.py, reach_v5.json). See V5_PLAN.md.
# x = 0.58 dominates every other placement tested that passes the gate: front and top
# both 100% within the tilt cone, and it beats x = 0.62 on exact-normal top coverage
# (62.5% vs 37.5%) and on both side faces (89.6% vs 85.4%) at identical front coverage.
# Closer placements (0.46-0.50) give better camera separation -- 5 framed views at 158
# deg instead of 3 at 90 -- but drop front-face coverage to 67-85%. That trade-off
# between the TRIAGE station and the CLEAN station is real and is recorded in V5_PLAN;
# a turntable would remove it.
CAB_X = 0.58
CAB_Y = 0.0
# Real dimensions are an OPEN ASK -- no document in the set gives a cabinet envelope
# (dp_process.MISSING). These are a plausible countertop RO purifier and are a
# PLACEHOLDER. V5-0 found device size barely matters (83-100% front+top across
# 200-350 mm wide x 300-550 mm tall, coarse raster at x=0.50), so it is not on the
# critical path. Mass is a placeholder too -- see CAB_MASS.
CAB_DEPTH = 0.18      # X extent, front-to-back. Front face (-X) points at the arm base.
CAB_WIDTH = 0.25      # Y extent
CAB_HEIGHT = 0.45     # Z extent, standing on the bench at z = 0

TOOLPOST_XY = (0.30, -0.34)   # where the wiping pad lives when not held

# --- V9 STAGE 3 FAITHFUL (2026-08-13): the other two cloths. Stage 3 names THREE in
# sequence -- a wash cloth, "a clean, damp cloth" to remove the soap, and "a dry cloth"
# -- and a one-pad cell cannot perform that; --rinse/--dry used to raise
# NotImplementedError with exactly that reason. These are their posts. PLACEMENT IS
# GATED, NOT EYEBALLED: both spots passed `v5_reach.py --indexed` at 100% during the V8
# tray sweep (the tray's obvious spot cost coverage on all four vertical faces), and the
# gate is re-run with all three tools present before anything is built on them.
# (0.22, -0.44) was the first choice and the SCENE GATE rejected it before anything was
# built on it: the damp pad's face interpenetrated the solution tray's corner by 23 mm at
# the keyframe. The V8 sweep had passed that spot for the TRAY ALONE -- a clearance sweep
# is only valid for the set of bodies it was run with.
TOOLPOST_DAMP_XY = (0.14, -0.52)
TOOLPOST_DRY_XY = (0.30, -0.52)

# --- Solution tray (Stage 3, 0024DPCRO003). See the big comment at the geometry.
# Sited next to the tool post, on the same -Y side as the rest of the cleaning
# hardware, so charging the pad is a short move from picking it up. Clear of the
# rotary indexer, whose disc has radius 0.175 at x = 0.58 (so it starts at x = 0.405).
SOLUTION_XY = (0.14, -0.36)
SOL_INNER = 0.130             # inner basin, square. Pad half-DIAGONAL is 42.4 mm, so
                              # this leaves 22.6 mm to a wall on the worst diagonal.
SOL_WALL = 0.008
SOL_DEPTH = 0.040             # wall height above the floor
SOL_SURF = 0.028              # liquid surface height, z. Below the wall top by design:
                              # a full basin that a pad displaces would slop over, and
                              # nothing here simulates that.
SOL_SUBMERGE = 0.010          # how far the pad face is driven BELOW the surface
# ---------------------------------------------------------------- V5-E, Stage 10
# *** EVERY MEMBRANE DIMENSION BELOW IS INVENTED. *** No source document gives a bowl,
# cap, O-ring or membrane size (dp_process.MISSING). The ask is out to the customer for
# STL/STEP against the only three part numbers in the entire 13-document set --
#   100059 MEMBRANE BOWL | 100031 MEMBRANE CAP | 100099 MEMBRANE O-RING  (Stage 10)
# -- and THIS BLOCK IS THE SWAP-IN POINT. Replace the numbers here, re-run the gates, and
# nothing downstream should need touching. They are a plausible domestic RO housing.
MEM_XY = (0.34, 0.30)         # membrane station: bowl fixture
BIN_XY = (0.50, 0.37)         # water bin for the Stage-10 bubble test.
# 0.37, not 0.26: at 0.26 the bin's -Y wall sat exactly on the rotary indexer's
# 175 mm platter radius and spawned 6 mm interpenetrated. v5_check_scene catches
# that in one run, which is why it goes FIRST after any geometry edit.
MEM_BOWL_R = 0.032            # bowl outer radius
MEM_BOWL_H = 0.115            # bowl height
MEM_CAP_R = 0.034             # cap outer radius
MEM_THREAD_PITCH = 0.002      # m of axial travel per turn -- a coarse housing thread
MEM_TURNS_MAX = 4.0           # driver stroke, turns
MEM_ORING_R = 0.028           # O-ring mean radius, sits on the bowl rim
# Torque at which the driver stalls and stops. THIS IS OUR NUMBER, not theirs: Stage 10
# says only "Ensure the cap is tightened properly with the spanner" -- a qualitative
# criterion with no figure anywhere in the corpus. Anything quoting it says so.
MEM_TORQUE_NM = 6.0
BACKDROP_X = 0.86             # matte panel behind the device, from the arm's viewpoint
TT_RISE = 0.010               # rotary indexer disc height above the bench

# --- Membrane spindle FREE SPEED (V9, 2026-08-13). The ctrlrange of the capdrv velocity
# actuator = the fastest the purchased spindle motor spins unloaded. It was 6 rad/s
# (57 rpm), and that value was doing something nobody knew: MemConfig commanded
# drive_rate=12 and MuJoCo CLAMPED it to 6 SILENTLY -- the same trap as the indexer's
# deg2rad(270) against a +-pi ctrlrange. It is exactly why the V7.2 sweep found
# drive_rate "identical at 12/16/20/24": every one of those was the same 6 after the
# clamp. The dead lever was the ctrlrange.
#
# 30 rad/s (~286 rpm) is ordinary purchased hardware (torque-controlled DC nutrunners
# run 100-600 rpm rundown speeds) and is HEADROOM, not the operating point: the cell
# commands MemConfig.drive_rate (truth-restored to 6.0) or, in the declared fast-spindle
# configuration, MemConfig.spindle_rate. forcerange stays MEM_TORQUE_NM -- THE TORQUE
# CRITERION IS THE PRODUCT SPEC and does not move with motor speed. Raising ctrlrange
# with the command unchanged is physics-identical (the clamp only ever bit commands
# above 6); asserted by re-running the membrane battery on its published seeds.
SPINDLE_FREE_RADS = 30.0
# The arm's kinematic root sits 120 mm above the bench top -- an offset inherited from
# the stock arm model. Something must physically hold it there, and that something is an
# obstacle the arm can hit. It was NOT modelled until V5-C, so no arm-to-riser clearance
# had ever been checked while reachability numbers were being quoted.
# DIAMETER IS AN OPEN ASK -- it depends on the pedestal actually bought. 150 mm is a
# plausible column for an arm whose own base casting is 126 mm. `v5_reach.py --riser`
# sweeps it so the cost is measured rather than assumed.
RISER_DIA = 0.150
# PLACEHOLDER. No source document gives a device mass (dp_process.MISSING). Left to
# MuJoCo's default density the solid box came out 21.3 kg -- an artifact of filling it
# with water. A stated stand-in beats an accidental number.
CAB_MASS = 8.0                # kg, empty countertop RO purifier -- OPEN ASK
# Active contact flange: the compliance unit between the tool changer and the pad.
ACF_K = 800.0                 # N/m spring rate
ACF_C = 12.0                  # N.s/m damping
ACF_STROKE = 0.030            # m of travel
ACF_NOMINAL = 0.012           # m of commanded compression -> ~9.6 N
# Distributed across ALL FOUR cabinet geoms. Setting it on cab_body alone left the cover,
# facia and back panel at default density and the total came out 9.48 kg -- caught
# immediately by v5_check_spec.py, which is the point of that check existing.
# The front facia strip stands 4 mm proud of the front face across a z band. Condition
# patches placed behind it are physically buried and INVISIBLE FROM EVERY CAMERA at
# every index angle -- ground truth the classifier can never see, which silently caps
# accuracy. Exclude the band. (The real cabinet's facia would not collect body soil
# either, so this is also the physically right answer.)
FACIA_Z = (0.040, 0.100)

# pool sizes. Ground truth is the COUNT of each class revealed per trial; the counts are
# chosen so the three grades cannot overlap (see dp_process / V5_PLAN).
N_SOIL, N_SCRATCH, N_DENT = 40, 28, 20

SEED = 20260804


def _faces(depth, width, height):
    """(name, outward normal, plane point, in-plane axis u + extent, axis v + extent).

    Same axis convention as v5_reach._set_cabinet: depth->X, width->Y, height->Z, and
    the cabinet body origin sits on the bench so the box spans z in [0, height].
    Coordinates here are LOCAL to the cabinet body.
    """
    # BACK PANEL geometry -- pools on the back go on the PANEL'S OUTER SURFACE, not on
    # the body's back face, which the panel covers. Kept in sync with the geom emitted
    # below: the panel spans local x 0.090..0.100, y +-0.119, z 0.020..0.430.
    bp_x = depth / 2 + 0.010
    bp_w = 2 * (width / 2 - 0.006)
    bp_z0, bp_z1 = 0.020, height - 0.020
    return [
        ("front", (-1, 0, 0), (-depth / 2, 0, height / 2),
         (0, 1, 0), width, (0, 0, 1), height),
        ("top", (0, 0, 1), (0, 0, height),
         (1, 0, 0), depth, (0, 1, 0), width),
        ("left", (0, -1, 0), (0, -width / 2, height / 2),
         (1, 0, 0), depth, (0, 0, 1), height),
        ("right", (0, 1, 0), (0, width / 2, height / 2),
         (1, 0, 0), depth, (0, 0, 1), height),
        # FIFTH FACE, added once the rotary indexer made it reachable. It was excluded
        # while the back was unreachable at every placement (0/48 raster points), which
        # meant "coverage" could only ever mean "of the four soiled faces". With the
        # indexer every face rotates to the front working position at 100%, so leaving
        # the back clean would have quietly flattered any cleaning number V5-C produces.
        ("back", (1, 0, 0), (bp_x, 0, (bp_z0 + bp_z1) / 2),
         (0, 1, 0), bp_w, (0, 0, 1), bp_z1 - bp_z0),
    ]


def _sample(rng, faces, n, inset=0.82):
    """Scatter n points over the given faces, area-weighted so density is uniform.

    Rejects any front-face point that would land BEHIND the facia strip (FACIA_Z). A
    patch there is buried by a 4 mm-proud accent and cannot be seen from any camera at
    any index angle -- it would be ground truth the classifier is structurally unable to
    observe, which caps accuracy for a reason that has nothing to do with vision.
    """
    areas = np.array([su * sv for (_, _, _, _, su, _, sv) in faces], float)
    out = []
    while len(out) < n:
        i = rng.choice(len(faces), p=areas / areas.sum())
        name, n_hat, fc, u, su, v, sv = faces[i]
        a = (rng.random() - 0.5) * inset * su
        b = (rng.random() - 0.5) * inset * sv
        p = np.array(fc, float) + np.array(u, float) * a + np.array(v, float) * b
        if name == "front" and FACIA_Z[0] - 0.012 <= p[2] <= FACIA_Z[1] + 0.012:
            continue                      # buried behind the facia -- resample
        out.append((name, np.array(n_hat, float), p, np.array(u, float),
                    np.array(v, float)))
    return out


def _cam(eye, target, up=(0, 0, 1)):
    """MuJoCo camera xyaxes for an eye looking at a target.

    Hand-written xyaxes is how the v4 socket ended up with a pinwheel chamfer, and how
    this scene's first draft put every demo camera BEHIND the backdrop so the device was
    invisible. Compute it.
    """
    eye, target, up = map(lambda a: np.array(a, float), (eye, target, up))
    f = target - eye
    f /= np.linalg.norm(f)
    z = -f                                   # camera looks along -Z
    x = np.cross(up, z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return (" ".join(f"{c:.4f}" for c in eye),
            " ".join(f"{c:.4f}" for c in (*x, *y)))


def _xyaxes(n_hat, u):
    """Frame for a surface patch: local x along u, local z along the OUTWARD normal.

    x = u, y = n x u  =>  z = x cross y = u x (n x u) = n, since u is perpendicular to n.
    Getting this backwards points the patch's thickness axis INTO the cabinet, which
    still passes a careless "is the normal aligned" check written with abs().

    Deliberately NOT euler. PAIN_JOURNAL: `euler="0 0.785 th"` on a ring tilts every
    plate about the SAME world axis rather than radially, which built a pinwheel that
    overhung its own bore. Explicit xyaxes cannot go wrong that way.
    """
    y = np.cross(n_hat, u)
    return " ".join(f"{c:.5f}" for c in (*u, *y))


def build(seed=SEED, cab_x=CAB_X):
    rng = np.random.default_rng(seed)
    faces = _faces(CAB_DEPTH, CAB_WIDTH, CAB_HEIGHT)
    L = []
    add = L.append

    add(f'''<mujoco model="refurbishment cell v5 (triage / clean / membrane)">
  <!-- GENERATED by make_scene_v5.py (seed {seed}). Edit the generator, not this file. -->
  <include file="xarm7.xml"/>

  <statistic center="0.45 0 0.35" extent="1.25"/>

  <visual>
    <headlight diffuse="0.62 0.62 0.62" ambient="0.36 0.36 0.38" specular="0.22 0.22 0.22"/>
    <global azimuth="150" elevation="-25" offheight="720" offwidth="1280"/>
    <quality shadowsize="4096"/>
  </visual>

  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.82 0.87 0.93" rgb2="0.5 0.6 0.72"
             width="256" height="256"/>
    <texture name="floortex" type="2d" builtin="checker" rgb1="0.30 0.32 0.36"
             rgb2="0.36 0.38 0.42" width="256" height="256"/>
    <material name="floormat" texture="floortex" texrepeat="6 6" reflectance="0.05"/>
    <material name="benchmat" rgba="0.65 0.67 0.71 1" reflectance="0.1"/>
    <!-- cabinet: light warm grey plastic, like the real appliance -->
    <material name="cabmat" rgba="0.88 0.89 0.90 1" reflectance="0.12"/>
    <material name="faciamat" rgba="0.16 0.5 0.82 1" reflectance="0.2"/>
    <!-- V5-E membrane station -->
    <material name="bowlmat"  rgba="0.86 0.87 0.89 1" reflectance="0.12"/>
    <material name="capmat"   rgba="0.24 0.45 0.62 1" reflectance="0.18"/>
    <material name="oringmat" rgba="0.10 0.10 0.12 1" reflectance="0.05"/>
    <material name="elemmat"  rgba="0.93 0.93 0.90 1" reflectance="0.04"/>
    <material name="binmat"   rgba="0.55 0.58 0.62 1" reflectance="0.10"/>
    <material name="watermat" rgba="0.35 0.62 0.78 0.45" reflectance="0.30"/>
    <!-- BUBBLES. Emissive so they read against the water even at low light. Revealed only
         as a modelled consequence of under-tightening -- see the membrane station block. -->
    <material name="bubblemat" rgba="0.95 0.98 1.0 0.75" reflectance="0.5" emission="0.35"/>
    <material name="panelmat" rgba="0.80 0.81 0.83 1" reflectance="0.08"/>
    <!-- the three condition classes. Deliberately NOT flat recolours of the body: the
         classifier has to measure coverage and texture, not read back a value we set. -->
    <material name="soilmat"    rgba="0.42 0.36 0.28 1" reflectance="0.0"/>
    <!-- A scratch is modelled as a DARK GROOVE, not a bright specular line. Both occur
         on real plastic (fine scuffs scatter light and read pale; gouges shadow and read
         dark), so this is a stated modelling choice. It was made after measuring: a pale
         scratch renders at 0.846 against a body at 0.787 -- 1.6 body-sigma, and swamped
         by the cabinet's own edges and highlights. A groove separates cleanly.
         IT DOES NOT DECIDE THE CLASSIFIER. Scratches are told apart from dents by SHAPE
         (thin and elongated vs compact), which is what a human grader uses and is robust
         either way; the detector looks for two-sided anomalies, so a pale scratch would
         still be found. -->
    <material name="scratchmat" rgba="0.34 0.34 0.35 1" reflectance="0.05"/>
    <material name="dentmat"    rgba="0.30 0.30 0.32 1" reflectance="0.02"/>
    <material name="backdropmat" rgba="0.07 0.08 0.09 1" reflectance="0.0"/>
    <material name="padmat" rgba="0.95 0.85 0.30 1" reflectance="0.05"/>
    <material name="stemmat" rgba="0.25 0.27 0.30 1" reflectance="0.3"/>
    <material name="postmat" rgba="0.45 0.47 0.50 1" reflectance="0.1"/>
    <!-- detergent-and-warm-water mix (Stage 3). Translucent so the pad is visible
         through it while it is charging -- the dip has to be legible on camera, or
         nobody watching the demo can tell the station did anything. -->
    <material name="solmat"  rgba="0.62 0.78 0.86 0.55" reflectance="0.35"/>
    <material name="dampmat" rgba="0.55 0.65 0.78 1" reflectance="0.05"/>
    <material name="drymat"  rgba="0.82 0.82 0.80 1" reflectance="0.05"/>
  </asset>

  <worldbody>
    <light pos="0.5 -0.5 1.7" dir="-0.3 0.3 -1" diffuse="0.7 0.7 0.7"/>
    <light pos="0.3 0.6 1.5" dir="0 -0.4 -1" diffuse="0.45 0.45 0.45"/>

    <geom name="floor" type="plane" size="0 0 0.05" pos="0 0 -0.7" material="floormat"/>
    <geom name="bench" type="box" size="0.55 0.6 0.35" pos="0.35 0 -0.35" material="benchmat"/>

    <!-- ARM RISER. Holds the arm's flange 120 mm above the bench. Tops out 4 mm below
         the flange so it meets the base casting (which hangs 3 mm below the body origin)
         without interpenetrating. Modelled because it is an OBSTACLE, not decoration:
         link5 passes as low as z = 103 mm within 75 mm of the base axis. -->
    <geom name="arm_riser" type="cylinder" size="{RISER_DIA/2:.4f} 0.0580"
          pos="0 0 0.0580" material="postmat"/>

    <!-- Demo cameras, all computed by _cam(). They MUST sit on the -X side: the matte
         backdrop stands at x = {BACKDROP_X:.2f}, so anything viewing from +X sees a black
         wall and nothing else. The first draft did exactly that. -->
    <camera name="main" pos="{_cam((-0.20, -1.05, 0.90), (0.55, 0, 0.24))[0]}"
            xyaxes="{_cam((-0.20, -1.05, 0.90), (0.55, 0, 0.24))[1]}"/>
    <camera name="front" pos="{_cam((-0.32, -0.42, 0.42), (0.52, 0, 0.24))[0]}"
            xyaxes="{_cam((-0.32, -0.42, 0.42), (0.52, 0, 0.24))[1]}"/>
    <camera name="side" pos="{_cam((0.30, -1.10, 0.40), (0.58, 0, 0.24))[0]}"
            xyaxes="{_cam((0.30, -1.10, 0.40), (0.58, 0, 0.24))[1]}"/>
    <camera name="top" pos="{_cam((0.30, -0.02, 1.55), (0.56, 0, 0.30))[0]}"
            xyaxes="{_cam((0.30, -0.02, 1.55), (0.56, 0, 0.30))[1]}"/>

    <!-- ===================== TRIAGE STATION CAMERA (V5-B) =====================
         A FIXED camera, not the wrist camera. V5_PLAN originally called for the arm to
         orbit its wrist camera around the device -- correct when the device could not
         move. The rotary indexer changed that: with the part on a turntable, a fixed
         camera and a rotating device is both simpler and what real rotary vision cells
         actually do. It needs no hand-eye calibration (the single largest un-modelled
         risk in the wrist-camera plan), its geometry is fixed and surveyable, and it
         leaves the arm free during inspection instead of parking it in a pose.

         Placed on the -X side so the matte backdrop at x = {BACKDROP_X:.2f} fills the
         background: the sightline continues past the device and lands on the panel at
         roughly y = +0.26, well inside its +/-0.46 half-width. Offset in -Y to clear the
         arm, which sits at the origin. fovy 48 frames the {CAB_HEIGHT*1000:.0f} mm device
         at this range with margin. -->
    <!-- V5-D TOP-FACE VERIFICATION CAMERA. A hardware requirement discovered by the
         falsification test, not a nicety. The `inspect` camera sits at z = 0.400 and the
         device top face at z = 0.450 -- i.e. BELOW the plane of that face -- so it can
         never see the top. V5-C wipes five faces and counts five; without this camera the
         cleaning check saw four, and every unit that failed did so on the top face. The
         first falsification run scored a perfect 10/10 caught while quietly letting 9 of
         10 dirty units pass, because cleaning misses and camera blindness landed on the
         SAME face. Mounted on the -Y side, above the top plane and clear of the arm's
         working volume over the device. -->
    <camera name="verify_top" fovy="40"
            pos="{_cam((0.30, -0.30, 1.05), (0.58, 0, 0.46))[0]}"
            xyaxes="{_cam((0.30, -0.30, 1.05), (0.58, 0, 0.46))[1]}"/>

    <!-- V5-E DIP CAMERA. The bubble test is graded through this one. verify_top is aimed
         at the device's top face and the water bin is a third of a metre away, so grading
         the dip through it counted backdrop: the ROI was pixel-identical with bubbles on
         and off. A station that watches for bubbles needs a camera pointed at the water. -->
    <camera name="verify_dip" fovy="42"
            pos="{_cam((BIN_XY[0] - 0.26, BIN_XY[1] - 0.20, 0.34), (BIN_XY[0], BIN_XY[1], 0.13))[0]}"
            xyaxes="{_cam((BIN_XY[0] - 0.26, BIN_XY[1] - 0.20, 0.34), (BIN_XY[0], BIN_XY[1], 0.13))[1]}"/>

    <!-- DEMO camera for the V5-G video. SEPARATE FROM verify_dip ON PURPOSE.
         verify_dip is a MEASUREMENT fixture: the bubble threshold is frozen against its
         exact pose, and the ROI is projected from it. Re-aiming it for nicer framing
         moved bright water and bin edge into the ROI and turned a sealed unit
         (6.00 Nm, stalled) into 17835 bubble px and a FALSE FAIL -- against a station
         that had just published 0/10 false fails. "A vision result is only as valid as
         the fixture that presents the part" applies to the CAMERA too. Compose the demo
         shot here; never touch the one a number depends on. -->
    <camera name="demo_dip" fovy="34"
            pos="{_cam((BIN_XY[0] - 0.17, BIN_XY[1] - 0.19, 0.40), (BIN_XY[0], BIN_XY[1], 0.115))[0]}"
            xyaxes="{_cam((BIN_XY[0] - 0.17, BIN_XY[1] - 0.19, 0.40), (BIN_XY[0], BIN_XY[1], 0.115))[1]}"/>

    <!-- DEMO camera on the membrane station. VISUAL ONLY -- it has NO measurement role
         and nothing reads pixels from it, which is the whole reason it is a separate
         camera rather than a re-aim of verify_dip. Re-aiming a measurement fixture for
         nicer framing is exactly what broke V5-E once (17835 bubble px on a sealed unit).
         Added 2026-08-05 so the element insertion is actually VISIBLE in the reel. -->
    <camera name="demo_mem" fovy="40"
            pos="{_cam((MEM_XY[0] - 0.16, MEM_XY[1] - 0.20, 0.36), (MEM_XY[0], MEM_XY[1], 0.13))[0]}"
            xyaxes="{_cam((MEM_XY[0] - 0.16, MEM_XY[1] - 0.20, 0.36), (MEM_XY[0], MEM_XY[1], 0.13))[1]}"/>

    <camera name="inspect" fovy="48"
            pos="{_cam((0.10, -0.45, 0.40), (0.58, 0, 0.235))[0]}"
            xyaxes="{_cam((0.10, -0.45, 0.40), (0.58, 0, 0.235))[1]}"/>
    <site name="inspect_eye" pos="0.10 -0.45 0.40" size="0.006" rgba="0 0 0 0"/>

    <!-- Matte backdrop BEHIND the device as seen from the arm. A controlled background
         is what makes plant vision tractable and is what a real cell would have (v4
         used one for the same reason). Placed at +X because V5-0 found every reachable
         camera azimuth sits on the -X side.

         ONE PANEL, NOT TWO. The first draft added a second panel across +Y at y = 0.40.
         It looked harmless and it cost the entire right face: coverage went 89.6% on the
         bare probe scene to 0.0% here, because the arm has to swing its elbow out past
         y = 0.40 to press on a +Y surface. A backdrop is scenery to us and an obstacle to
         the robot. Widened to +/-0.46 so a single +X panel still fills the background at
         every framed azimuth (the extreme, 225 deg, needs coverage out to y = +0.28). -->
    <geom name="backdrop_x" type="box" size="0.006 0.46 0.36"
          pos="{BACKDROP_X:.3f} 0 0.36" material="backdropmat"/>

    <!-- Second panel, +Y, restored for the V5-B triage camera. It fills the rest of the
         background behind the device from the fixed inspect camera; a half-lit
         background makes segmentation a lighting problem instead of a geometry one.

         THIS PANEL WAS DELETED ONCE, because it cost the entire right face (89.6% -> 0%)
         when the arm had to reach around to press on a +Y surface. THE ROTARY INDEXER
         REMOVED THAT REQUIREMENT: every face now rotates to the FRONT working position,
         so the arm never works a +Y surface and the panel is no longer in its way.
         That is a claim, so `v5_reach.py --indexed` is re-run after adding it and the
         front/top numbers are unchanged. Do not restore it without re-checking. -->
    <geom name="backdrop_y" type="box" size="0.30 0.006 0.36"
          pos="0.66 0.42 0.36" material="backdropmat"/>
''')

    # ---------------------------------------------------------------- the cabinet
    hd, hw, hh = CAB_DEPTH / 2, CAB_WIDTH / 2, CAB_HEIGHT / 2
    add(f'''
    <!-- ======================= ROTARY INDEXER (TURNTABLE) =======================
         A low-profile rotary stage under the device, with its own commanded axis.

         WHY. V5-0 found two hard limits that no arm placement could fix: the BACK FACE
         is unreachable at every placement tested (0/48 raster points, 8 placements),
         and camera view separation trades directly against front-face coverage (5 views
         at 158 deg with 92% front, or 3 views at 90 deg with 100% front). Both are the
         same problem -- a fixed part can only be approached from the side the arm lives
         on. A rotary stage is the standard industrial answer, used in welding
         positioners, paint booths and vision inspection cells for exactly this reason,
         and it is cheap next to a second arm or a linear rail.

         WHAT IT BUYS. Every vertical face can be indexed into the FRONT working
         position, where coverage is 100%. Camera separation becomes arbitrary. The
         arm's job simplifies to one well-conditioned pose set instead of four
         badly-conditioned ones.

         It is a real commanded axis (position actuator `tt`), not scenery, because on
         the real cell it will be one -- and a demo that hides an axis is a demo that
         understates its own integration cost. The disc sits {TT_RISE*1000:.0f} mm proud of the
         bench, which V5-A re-verified does not change the reachability result. -->
    <body name="turntable" pos="{cab_x:.3f} {CAB_Y:.3f} 0">
      <joint name="tt_rot" type="hinge" axis="0 0 1" damping="12" armature="0.08"/>
      <!-- MATTE BLACK PLATTER, deliberately. In mid-grey it rendered at 0.580 value,
           above the 0.30 background threshold, so its elliptical rim sat inside the
           projected search region and read as a big compact dark anomaly -- i.e. as a
           DENT. Measured: 2374 false dent pixels against ~60 real ones. Finishing the
           fixture matte black is what a real vision cell does for exactly this reason,
           and it drops the platter below the background threshold for free. -->
      <geom name="tt_disc" type="cylinder" size="0.175 {TT_RISE/2:.4f}"
            pos="0 0 {TT_RISE/2:.4f}" material="backdropmat"/>
      <!-- index mark, so rotation is visible in a render and in a video -->
      <geom name="tt_mark" type="box" size="0.030 0.006 0.0012"
            pos="-0.140 0 {TT_RISE + 0.0012:.4f}" material="faciamat"
            contype="0" conaffinity="0"/>

    <!-- ============================ THE DEVICE ============================
         A field-returned purifier, standing ON the turntable. Dimensions are a
         PLACEHOLDER: no document in the set gives a cabinet envelope
         (dp_process.MISSING). V5-0 showed size is not on the critical path.
         depth(X)={CAB_DEPTH*1000:.0f} width(Y)={CAB_WIDTH*1000:.0f} height(Z)={CAB_HEIGHT*1000:.0f} mm,
         FRONT FACE (-X at index 0) toward the arm base. -->
    <body name="cabinet" pos="0 0 {TT_RISE:.4f}">
      <!-- Body + top cover are FLUSH: together they span exactly {CAB_HEIGHT:.3f} m.
           The first draft stacked a 12 mm cover ON TOP of a full-height body, which put
           the visible top surface 12 mm above the plane the raster and the reachability
           study both treat as "the top face". The renders and the numbers would have
           disagreed, silently. -->
      <!-- MASS IS AN EXPLICIT PLACEHOLDER, not a modelled value. Left to MuJoCo's
           default density this solid box came out at 21.3 kg, which is an artifact of
           filling it with water, not a purifier. NO SOURCE DOCUMENT GIVES A DEVICE MASS
           (dp_process.MISSING: "ANY mass or weight"), so {CAB_MASS} kg is a stated
           stand-in for a countertop RO purifier and nothing more. Nothing in V5-0/V5-A
           depends on it -- the reachability study is kinematics-only -- but the rotary
           indexer's sizing does, so it must not be an accident. -->
      <geom name="cab_body" type="box"
            size="{hd:.4f} {hw:.4f} {(CAB_HEIGHT - 0.010) / 2:.4f}"
            pos="0 0 {(CAB_HEIGHT - 0.010) / 2:.4f}" material="cabmat"
            mass="{CAB_MASS * 0.875:.3f}"/>
      <!-- top cover: stage 3's named part. Inset 8 mm so it reads as a separate part;
           the raster stays within the middle 76% of the face, so every raster point
           lands on the cover and not on the ledge. -->
      <geom name="cab_topcover" type="box"
            size="{hd - 0.008:.4f} {hw - 0.008:.4f} 0.005"
            pos="0 0 {CAB_HEIGHT - 0.005:.4f}" material="panelmat"
            mass="{CAB_MASS * 0.0625:.3f}"/>
      <!-- front facia accent, so renders read as a device and the front is identifiable -->
      <geom name="cab_facia" type="box" size="0.004 {hw:.4f} 0.030"
            pos="{-(hd + 0.004):.4f} 0 0.070" material="faciamat"
            contype="0" conaffinity="0" mass="{CAB_MASS * 0.0125:.3f}"/>
      <!-- back panel: stage 3's other named part. V5-0 measured this face as
           UNREACHABLE at every placement (0/48 points, 8 placements), and the source
           documents contradict each other on whether it is screwed (stage 6 lists 5
           back-panel screws) or taped (stage 7) -- i.e. whether it is even detached
           during refurb. Modelled COLLIDING so that if the arm ever does foul it we
           find out, rather than passing through it in a render. Carries NO pools. -->
      <geom name="cab_backpanel" type="box" size="0.005 {hw - 0.006:.4f} {hh - 0.020:.4f}"
            pos="{hd + 0.005:.4f} 0 {hh:.4f}" material="panelmat"
            mass="{CAB_MASS * 0.05:.3f}"/>
      <site name="cab_center" pos="0 0 {hh:.4f}" size="0.006" rgba="0 0 0 0"/>
      <site name="cab_front" pos="{-hd:.4f} 0 {hh:.4f}" size="0.006" rgba="0 0 0 0"/>
''')

    # ------------------------------------------------------------------ the pools
    # All three pools: visual only (contype/conaffinity 0, negligible mass), hidden by
    # default (alpha 0), revealed per trial by setting geom_rgba[...,3]. Same mechanism
    # v4 used, so cleaning can HIDE the same geoms the camera graded -- which is what
    # makes the verification observe the identical mechanism rather than assert success.
    # NOTE THE `rgb` COLUMN. In MuJoCo a geom's own rgba OVERRIDES its material colour.
    # The first draft wrote rgba="0 0 0 0" and toggled only alpha to reveal a patch --
    # which revealed it as BLACK, not as brown dirt or a bright scratch, silently
    # discarding the entire point of giving the three classes different appearances.
    # v4 avoids this by writing the material's own RGB into the geom and zeroing only
    # alpha; do the same. rgb here MUST match the material above.
    specs = [
        ("soil", N_SOIL, "soilmat", "0.42 0.36 0.28",
         (0.010, 0.020), (0.008, 0.016), 0.0010,
         "soil / stains -- come off with the CIF-cream wipe (stage 2)       -> EASY"),
        ("scr", N_SCRATCH, "scratchmat", "0.34 0.34 0.35",
         (0.018, 0.045), (0.0007, 0.0015), 0.0006,
         "scratches -- need the rubbing-component pass (stage 2)            -> MEDIUM"),
        ("dent", N_DENT, "dentmat", "0.30 0.30 0.32",
         (0.006, 0.013), (0.006, 0.013), 0.0022,
         "dents -- no cleaning step in any of the 10 stages addresses these -> HARD"),
    ]
    for prefix, n, mat, rgb, urange, vrange, thick, blurb in specs:
        add(f"\n      <!-- {blurb} -->")
        for i, (fname, n_hat, p, u, v) in enumerate(_sample(rng, faces, n)):
            su = rng.uniform(*urange)
            sv = rng.uniform(*vrange)
            if prefix == "scr":
                # scratches are directional: random in-plane angle
                th = rng.uniform(0, np.pi)
                uu = u * np.cos(th) + v * np.sin(th)
            else:
                uu = u
            # sit the patch proud of the surface along the outward normal
            pos = p + n_hat * (thick * 0.6)
            add(f'      <geom name="{prefix}{i:02d}" type="box" '
                f'size="{su/2:.5f} {sv/2:.5f} {thick:.5f}" '
                f'pos="{pos[0]:.5f} {pos[1]:.5f} {pos[2]:.5f}" '
                f'xyaxes="{_xyaxes(n_hat, uu)}" material="{mat}" '
                f'mass="0.00001" contype="0" conaffinity="0" '
                f'rgba="{rgb} 0"/>   <!-- {fname} -->')

    add("    </body>\n    </body>\n")     # close cabinet, then turntable

    # ------------------------------------------------------------- tool post + pad
    tx, ty = TOOLPOST_XY
    sx, sy = SOLUTION_XY
    dpx, dpy = TOOLPOST_DAMP_XY
    drx, dry_ = TOOLPOST_DRY_XY
    # VISIBLE THREAD on the cap: a helix of small visual-only ridges. 2.5 turns at
    # 12 segments per turn reads clearly as a screw at video scale without flooding the
    # renderer. contype/conaffinity 0 and mass 0 -> cannot collide, cannot change inertia.
    _TH = []
    _n_seg, _turns = 12, 2.5
    for _k in range(int(_n_seg * _turns)):
        _a = 2 * np.pi * _k / _n_seg
        _z = 0.002 + MEM_THREAD_PITCH * _k / _n_seg
        _TH.append(
            f'        <geom name="mem_cap_thread{_k}" type="box" '
            f'size="0.0035 0.0016 0.0011" '
            f'pos="{MEM_CAP_R * 0.995 * np.cos(_a):.5f} '
            f'{MEM_CAP_R * 0.995 * np.sin(_a):.5f} {_z:.5f}" '
            f'euler="0 0 {np.degrees(_a) + 90:.2f}" '
            f'material="stemmat" contype="0" conaffinity="0" mass="0"/>')
    THREAD = "\n".join(_TH)
    add(f'''
    <!-- ===================== WIPING TOOL + TOOL POST =====================
         The pad is a free body that the arm PICKS UP by a cylindrical stem. The stem is
         deliberately sized close to the cartridge body (radius 21.5 mm) that the whole
         grasp sequence in v2/v3/v4 was tuned and validated against, so the existing
         grasp constants transfer instead of needing a new grasp.
         The pad face itself is SOFT (high solref time constant, low solimp stiffness).
         That is the V5-C fallback made physical: if surface-following by control proves
         hard, a compliant pad keeps contact by geometry instead. Values are plausible,
         NOT yet validated under contact -- that is V5-C's job. -->
    <body name="padtool" pos="{tx:.3f} {ty:.3f} 0.040">
      <freejoint name="padtool_free"/>
      <!-- KEYED (rectangular) SHANK, not a cylinder. A cylinder in parallel jaws can
           PIVOT about the grip axis, and a 60 mm pad on a 90 mm stem has ample leverage
           to do it: measured, the pad's offset from the TCP went from (21.7, 0, 36.4) mm
           with the wrist pointing down to (87.6, 0, -16.1) mm with it horizontal -- the
           tool had rotated most of a right angle inside the grip, and cleaning coverage
           was 0%. A flatted or keyed shank is what a real robot tool has, for exactly
           this reason. 40 mm across the jaws (unchanged), 60 mm along them to resist the
           pivot. Same lesson as the v4 staging nest: shape the part so the problem
           cannot happen, rather than controlling around it. -->
      <geom name="pad_stem" type="box" size="0.030 0.020 0.045" pos="0 0 0.045"
            material="stemmat" mass="0.18"/>
      <!-- COMPLIANT PAD -- two corrections, both found by measuring the force/penetration
           curve rather than trusting the declared numbers:

           (a) solimp WIDTH must be smaller than the pad's own half-thickness. The first
               draft used width 0.012 on a 0.010 half-thickness pad, so the contact
               impedance never reached full stiffness before the pad was fully
               penetrated. Measured: 18.6 mm of penetration at 20 N on a 10 mm pad --
               it crushed clean through its own mount, and the stem would have contacted
               the surface directly. A wiping pass applies well within that range, so
               V5-C would have been built on a tool that does not exist.

           (b) priority="1". MuJoCo AVERAGES solref between the two geoms in a contact
               unless one has higher priority. The declared 0.045 was silently becoming
               0.0325 against the post -- the compliance was roughly halved, and would
               have varied per contacting surface. Priority makes the pad govern its own
               contacts, so the number in CELL_SPEC is the number in force.

           FRICTION 0.7, reduced from 1.4. A damp cloth or foam pad on plastic is
           around 0.6-0.8; 1.4 is dry rubber. At 1.4, dragging the pad across a face at
           20-40 N normal generated up to ~56 N of friction, which twisted the tool
           straight out of the jaws mid-raster.

           Values chosen by sweeping the force/penetration curve and requiring it to be
           MONOTONIC from 0 to 60 N. Two otherwise-reasonable settings had a solver
           instability that spiked penetration to 12-17 mm at 40 N and recovered at 60 --
           i.e. the pad passed through its own mount at one load and not at a higher one.
           Measured with these values: 1.4 / 2.0 / 2.4 / 2.6 / 3.0 / 4.6 mm at
           0 / 5 / 10 / 20 / 40 / 60 N. About 3 mm of give across the working range,
           never close to the 10 mm half-thickness. -->
      <site name="pad_grip" pos="0 0 0.045" size="0.004" rgba="0 0 0 0"/>

      <!-- ============== ACTIVE CONTACT FLANGE (compliance unit) ==============
           A sprung axis between the coupled shank and the pad, along the approach
           direction. This is a real product category -- the compliance unit that sits
           between a tool changer and a surface-finishing tool -- and this cell needs
           BOTH: the changer gives LOCATION, the flange gives FORCE.

           WHY. With the tool rigidly coupled, nothing absorbed path error and the arm's
           ~1.5 mm positioning error landed straight on contact force: median 58 N and a
           press depth that barely moved it (60.7 N at 2.5 mm, 61.1 N at 0.0 mm). Before
           the changer, a slipping parallel-jaw grip had been absorbing that error by
           FAILING -- an accidental and terrible compliance element. Removing it did not
           create the force problem, it revealed it.

           SIZING. {ACF_K:.0f} N/m over a {ACF_STROKE*1000:.0f} mm stroke, so the whole
           stroke spans about {ACF_K*ACF_STROKE:.0f} N. Commanding a nominal
           {ACF_NOMINAL*1000:.0f} mm of compression targets ~{ACF_K*ACF_NOMINAL:.0f} N,
           and a +/-3 mm path error then moves the force by only
           +/-{ACF_K*0.003:.1f} N instead of tens. That is the entire point: force becomes
           a property of the SPRING, not of the arm's accuracy. -->
      <body name="padhead" pos="0 0 0">
        <joint name="acf" type="slide" axis="0 0 1" range="-0.002 {ACF_STROKE:.4f}"
               stiffness="{ACF_K:.0f}" damping="{ACF_C:.0f}" springref="0"
               armature="0.002"/>
        <geom name="pad_face" type="box" size="0.030 0.030 0.010" pos="0 0 -0.010"
              material="padmat" mass="0.04" priority="1"
              solref="0.035 1" solimp="0.80 0.99 0.003 0.5 2" friction="0.7 0.02 0.001"/>
        <site name="pad_tip" pos="0 0 -0.020" size="0.004" rgba="0 0 0 0"/>
      </body>
    </body>

    <!-- Tool post. FLAT on purpose. The first draft gave it a locating ring of radius
         38 mm -- but the pad face is a 60 x 60 mm square whose half-diagonal is 42.4 mm,
         so the pad could not have sat inside its own holder. That is the same mistake as
         the v4 staging nest, which was sized to the cartridge's 21.5 mm body and fouled
         its 34 mm lugs by exactly 7 mm (PAIN_JOURNAL): A FIXTURE MUST CLEAR THE PART'S
         LARGEST FEATURE. Caught here by asking MuJoCo for the contact list instead of
         assuming. A proper locating feature is a V5-C refinement; flat and correct beats
         clever and interpenetrating.
         Post top is at z = 0.020 and the pad body origin sits 20 mm above its own pad
         face, so the body spawns at z = 0.040 and rests with zero penetration. -->
    <geom name="post_base" type="cylinder" size="0.055 0.010" pos="{tx:.3f} {ty:.3f} 0.010"
          material="postmat"/>
    <site name="post_pt" pos="{tx:.3f} {ty:.3f} 0.30" size="0.004" rgba="0 0 0 0"/>

    <!-- ============ V9 STAGE 3: THE OTHER TWO CLOTHS (damp / dry) ============
         Structural CLONES of the wash tool above -- same keyed shank, same compliant
         face, same ACF -- because the three cloths in Stage 3 are the same object in
         three roles, and a clone cannot drift from the original the way a re-typed
         copy can. Distinct materials so the camera (and a human watching the demo)
         can tell which cloth is working:
           wash = the existing pad, damp = blue-grey, dry = light grey.
         Each rests on its own flat post, gate-checked like the tray. -->
    <body name="damppad" pos="{dpx:.3f} {dpy:.3f} 0.040">
      <freejoint name="damppad_free"/>
      <geom name="damp_stem" type="box" size="0.030 0.020 0.045" pos="0 0 0.045"
            material="stemmat" mass="0.18"/>
      <site name="damp_grip" pos="0 0 0.045" size="0.004" rgba="0 0 0 0"/>
      <body name="damphead" pos="0 0 0">
        <joint name="damp_acf" type="slide" axis="0 0 1" range="-0.002 {ACF_STROKE:.4f}"
               stiffness="{ACF_K:.0f}" damping="{ACF_C:.0f}" springref="0"
               armature="0.002"/>
        <geom name="damp_face" type="box" size="0.030 0.030 0.010" pos="0 0 -0.010"
              material="dampmat" mass="0.04" priority="1"
              solref="0.035 1" solimp="0.80 0.99 0.003 0.5 2" friction="0.7 0.02 0.001"/>
        <site name="damp_tip" pos="0 0 -0.020" size="0.004" rgba="0 0 0 0"/>
      </body>
    </body>
    <geom name="post_damp" type="cylinder" size="0.055 0.010"
          pos="{dpx:.3f} {dpy:.3f} 0.010" material="postmat"/>

    <body name="drypad" pos="{drx:.3f} {dry_:.3f} 0.040">
      <freejoint name="drypad_free"/>
      <geom name="dry_stem" type="box" size="0.030 0.020 0.045" pos="0 0 0.045"
            material="stemmat" mass="0.18"/>
      <site name="dry_grip" pos="0 0 0.045" size="0.004" rgba="0 0 0 0"/>
      <body name="dryhead" pos="0 0 0">
        <joint name="dry_acf" type="slide" axis="0 0 1" range="-0.002 {ACF_STROKE:.4f}"
               stiffness="{ACF_K:.0f}" damping="{ACF_C:.0f}" springref="0"
               armature="0.002"/>
        <geom name="dry_face" type="box" size="0.030 0.030 0.010" pos="0 0 -0.010"
              material="drymat" mass="0.04" priority="1"
              solref="0.035 1" solimp="0.80 0.99 0.003 0.5 2" friction="0.7 0.02 0.001"/>
        <site name="dry_tip" pos="0 0 -0.020" size="0.004" rgba="0 0 0 0"/>
      </body>
    </body>
    <geom name="post_dry" type="cylinder" size="0.055 0.010"
          pos="{drx:.3f} {dry_:.3f} 0.010" material="postmat"/>

    <!-- =================== SOLUTION TRAY (Stage 3) ===================
         WHAT THE SOURCE DOCUMENT ACTUALLY SAYS, because this station exists only
         because of it. Stage 3 (0024DPCRO003, "Back Panel & Top Cover Cleaning"):

             "Mix a small amount of mild detergent with warm water"
             "DIP THE CLOTH IN THE SOLUTION and wring out excess water"
             "Gently wipe down the top cover and back panel"

         THE THING THAT IS DIPPED IS THE CLOTH, NOT THE DEVICE. Across all 13 source
         documents the word "solution" appears three times and every one of them is in
         that stage, applied to a cloth. The ONLY immersion of a part anywhere in the
         corpus is Stage 10's membrane assembly going into a water bin -- and that is a
         pressurised BUBBLE LEAK TEST, explicitly not a wash. So a bath that a device is
         lowered into would be OUR invention wearing their vocabulary, and the repo rule
         is not to add a process step no source document describes.

         Hence: a shallow tray the PAD is charged from, sited next to the tool post so
         charging costs almost no travel from the pad pickup.

         SIZING -- a fixture must clear the part's LARGEST feature. The pad is a 60 mm
         square, so its half-DIAGONAL is 42.4 mm, not 30. The inner basin is {SOL_INNER*1000:.0f} mm
         square, leaving {(SOL_INNER/2 - 0.0424)*1000:.0f} mm of clearance to a wall on the worst diagonal. This is the
         same mistake the v4 staging nest made (sized to a 21.5 mm body, fouled 34 mm
         lugs) and that the first draft of the tool post above made.

         THE LIQUID IS VISUAL ONLY -- contype/conaffinity 0 and mass 0, exactly like the
         cap's thread ridges. THERE IS NO FLUID SIMULATION ANYWHERE IN THIS REPO and
         adding a rendered slab does not create one. What is modelled is the LOGISTICS of
         solution -- carrying it, spending it, going back for more -- never its chemistry.
         The walls and floor ARE collidable: mis-position the pad and it strikes a wall,
         which is a real failure mode and should stay one. -->
    <body name="sol_tray" pos="{sx:.3f} {sy:.3f} 0">
      <geom name="sol_floor" type="box" size="{SOL_INNER/2 + SOL_WALL:.4f} {SOL_INNER/2 + SOL_WALL:.4f} 0.004"
            pos="0 0 0.004" material="postmat"/>
      <geom name="sol_w_xp" type="box" size="{SOL_WALL/2:.4f} {SOL_INNER/2 + SOL_WALL:.4f} {SOL_DEPTH/2:.4f}"
            pos="{SOL_INNER/2 + SOL_WALL/2:.4f} 0 {0.008 + SOL_DEPTH/2:.4f}" material="postmat"/>
      <geom name="sol_w_xn" type="box" size="{SOL_WALL/2:.4f} {SOL_INNER/2 + SOL_WALL:.4f} {SOL_DEPTH/2:.4f}"
            pos="-{SOL_INNER/2 + SOL_WALL/2:.4f} 0 {0.008 + SOL_DEPTH/2:.4f}" material="postmat"/>
      <geom name="sol_w_yp" type="box" size="{SOL_INNER/2:.4f} {SOL_WALL/2:.4f} {SOL_DEPTH/2:.4f}"
            pos="0 {SOL_INNER/2 + SOL_WALL/2:.4f} {0.008 + SOL_DEPTH/2:.4f}" material="postmat"/>
      <geom name="sol_w_yn" type="box" size="{SOL_INNER/2:.4f} {SOL_WALL/2:.4f} {SOL_DEPTH/2:.4f}"
            pos="0 -{SOL_INNER/2 + SOL_WALL/2:.4f} {0.008 + SOL_DEPTH/2:.4f}" material="postmat"/>
      <!-- the liquid. VISUAL ONLY: contype=0 conaffinity=0 mass=0, so it can neither
           touch anything nor shift any inertia. Surface sits at z = {SOL_SURF:.3f}. -->
      <geom name="sol_liquid" type="box" contype="0" conaffinity="0" mass="0"
            size="{SOL_INNER/2:.4f} {SOL_INNER/2:.4f} {(SOL_SURF - 0.008)/2:.4f}"
            pos="0 0 {0.008 + (SOL_SURF - 0.008)/2:.4f}" material="solmat"/>
    </body>
    <!-- dip target: directly above the basin centre. The pad face is driven down to
         SOL_SUBMERGE below the liquid surface; see v5_clean.charge_pad(). -->
    <site name="dip_pt" pos="{sx:.3f} {sy:.3f} 0.30" size="0.004" rgba="0 0 0 0"/>

    <!-- ===================== MEMBRANE STATION (Stage 10) =====================
         PLACEHOLDER GEOMETRY. See MEM_* at the top of this file for the swap-in point
         and the three part numbers the CAD ask names.

         WHAT IS MODELLED AND WHAT IS NOT, stated here so it cannot drift:
         * The cap is THREADED and multi-turn, terminated by a TORQUE criterion. It is a
           hinge + slide coupled by an equality into a screw of {MEM_THREAD_PITCH*1000:.0f} mm pitch,
           driven by a force-limited actuator that STALLS -- which is what a torque-limited
           driver does. It is NOT our v2/v3/v4 55-degree indexed bayonet, and the two must
           never be called equivalent: same task class, different motion.
         * The cap is presented ENGAGED ON THE FIRST THREAD, as a human would start it.
           Thread-starting is its own research problem and is de-scoped, like the elbows.
         * The O-ring is REAL: a soft geom the cap compresses. Stage 10's material table
           lists it, and a joint with no seal is not a seal test.
         * Plug, ball valve and 80-90 PSI are LOGGED STATE, not gas physics.
         * BUBBLES ARE A PROXY. They are revealed as a modelled consequence of
           under-tightening, NOT computed from fluid dynamics. There is no fluid
           simulation anywhere in this repo. The camera still has to SEE them, so the
           pass/fail is caused rather than asserted. -->
    <body name="mem_fixture" pos="{MEM_XY[0]:.3f} {MEM_XY[1]:.3f} 0">
      <geom name="mem_post" type="cylinder" size="0.045 0.020" pos="0 0 0.020"
            material="postmat"/>
    </body>

    <body name="mem_bowl" pos="{MEM_XY[0]:.3f} {MEM_XY[1]:.3f} 0.040">
      <freejoint name="bowl_free"/>
      <!-- bowl wall as a ring of segments: MuJoCo has no open cylinder primitive, and a
           solid one would leave nowhere to put the membrane -->
      <geom name="mem_bowl_base" type="cylinder" size="{MEM_BOWL_R:.4f} 0.006"
            pos="0 0 0.006" material="bowlmat" mass="0.18"/>
      {"".join(f"""<geom name="mem_wall{i}" type="box" size="0.005 0.0085 {MEM_BOWL_H/2:.4f}"
            pos="{MEM_BOWL_R*0.86*np.cos(i*np.pi/4):.4f} {MEM_BOWL_R*0.86*np.sin(i*np.pi/4):.4f} {MEM_BOWL_H/2:.4f}"
            euler="0 0 {i*np.pi/4:.5f}" material="bowlmat" mass="0.018"/>
      """ for i in range(8))}
      <!-- O-RING on the rim. Soft, and its own contact priority for the same reason the
           wiping pad has one: MuJoCo averages solref between geoms otherwise, and the
           compliance that sets the torque curve would silently become someone else's. -->
      {"".join(f"""<geom name="mem_oring{i}" type="sphere" size="0.0030"
            pos="{MEM_ORING_R*np.cos(i*np.pi/6):.4f} {MEM_ORING_R*np.sin(i*np.pi/6):.4f} {MEM_BOWL_H + 0.0030:.4f}"
            material="oringmat" mass="0.0004" priority="1" solref="0.02 1"
            solimp="0.85 0.93 0.0025" friction="0.9 0.02 0.001"/>
      """ for i in range(12))}
      {"".join(f"""<geom name="mem_rim{i}" type="sphere" size="0.0035"
            pos="{(MEM_BOWL_R-0.002)*np.cos(i*np.pi/4):.4f} {(MEM_BOWL_R-0.002)*np.sin(i*np.pi/4):.4f} {MEM_BOWL_H - 0.0005:.4f}"
            material="bowlmat" mass="0.001"/>
      """ for i in range(8))}
      <site name="mem_seal" pos="0 0 {MEM_BOWL_H:.4f}" size="0.004" rgba="0 0 0 0"/>
      <!-- BUBBLE GEOMS. Alpha 0 until revealed. THEY ARE A PROXY: revealed as a modelled
           consequence of an under-tightened cap, NOT computed from any fluid or gas
           simulation -- there is none anywhere in this repo. What stays real is that the
           camera has to SEE them, so the pass/fail is caused by the torque outcome rather
           than read from a variable. Every artifact showing this says so on the HUD. -->
      {"".join(f"""<geom name="bubble{i}" type="sphere" size="{0.0035 + 0.0016*((i*7)%5):.4f}"
            pos="{MEM_ORING_R*1.03*np.cos(i*np.pi/5):.4f} {MEM_ORING_R*1.03*np.sin(i*np.pi/5):.4f} {MEM_BOWL_H + 0.010 + 0.011*((i*3)%4):.4f}"
            material="bubblemat" rgba="0.95 0.98 1.0 0" mass="0.00002"
            contype="0" conaffinity="0"/>
      """ for i in range(10))}

      <body name="mem_cap" pos="0 0 {MEM_BOWL_H + 0.020:.4f}">
        <!-- THE SCREW. cap_z is tied to cap_rot by an equality below; together they are a
             single helical degree of freedom. Driven by `capdrv`, whose forcerange IS the
             torque limit -- the driver stalls instead of stripping the thread. -->
        <joint name="cap_rot" type="hinge" axis="0 0 1" damping="0.05" armature="0.002"/>
        <joint name="cap_z" type="slide" axis="0 0 1" damping="2.0" range="-0.030 0.001"/>
        <geom name="mem_cap_body" type="cylinder" size="{MEM_CAP_R:.4f} 0.010"
              pos="0 0 0.010" material="capmat" mass="0.09"/>
        <!-- flats for the spanner/driver head, and so the cap's rotation is VISIBLE -->
        <geom name="mem_cap_flat" type="box" size="{MEM_CAP_R*0.92:.4f} 0.006 0.007"
              pos="0 0 0.024" material="stemmat" mass="0.02"/>
        <!-- VISIBLE THREAD. The cap has ALWAYS been a screw mechanically -- cap_rot and
             cap_z are tied by the `capthread` equality, which is the one line that makes
             this a threaded fastener rather than a lid that happens to spin. But it
             rendered as a plain cylinder, so a viewer could not SEE a screw going in.
             These ridges are the thread made visible.
             STRICTLY VISUAL: contype/conaffinity 0 and mass 0, so they cannot touch
             anything and cannot shift the cap's inertia. The tightening physics -- turns
             to stall, torque, seal preload -- is byte-identical with them present, and
             that is asserted by re-running the membrane eval on the same seeds. -->
{THREAD}
        <site name="cap_top" pos="0 0 0.031" size="0.004" rgba="0 0 0 0"/>
      </body>
    </body>

    <!-- the membrane element the arm inserts into the bowl before capping -->
    <body name="mem_elem" pos="{MEM_XY[0] - 0.13:.3f} {MEM_XY[1]:.3f} 0.072">
      <freejoint name="elem_free"/>
      <geom name="mem_elem_body" type="cylinder" size="0.021 0.036" pos="0 0 0"
            material="elemmat" mass="0.10" friction="0.9 0.01 0.001"/>
    </body>
    <geom name="mem_elem_nest" type="cylinder" size="0.040 0.018"
          pos="{MEM_XY[0] - 0.13:.3f} {MEM_XY[1]:.3f} 0.018" material="postmat"/>

    <!-- V6-ARM: the cap the ARM places. A free "blank" on its own nest; when the arm
         delivers it onto the bowl mouth inside a thread-start capture envelope, the
         blank is exchanged for the threaded cap engaged on its first thread -- the same
         capture-envelope honesty as the tool changer: the ARM must achieve the pose,
         the ENGAGEMENT is modelled. Thread-STARTING physics stays a declared de-scope. -->
    <body name="cap_blank" pos="{MEM_XY[0] - 0.13:.3f} {MEM_XY[1] + 0.10:.3f} 0.046">
      <freejoint name="capblank_free"/>
      <geom name="cap_blank_body" type="cylinder" size="{MEM_CAP_R:.4f} 0.010"
            material="capmat" mass="0.09" friction="0.9 0.01 0.001"/>
      <geom name="cap_blank_flat" type="box" size="{MEM_CAP_R*0.92:.4f} 0.006 0.007"
            pos="0 0 0.014" material="stemmat" mass="0.02"/>
      <!-- PICK STEM: a design-for-automation feature so parallel jaws can hold the cap
           with BOTH pad rows and the CoM hanging well below the grip line. The cap
           cylinder itself is ungrippable by these jaws: 20 mm tall vs 18 mm between
           pad rows (any offset loses a row), and a cylinder in flat jaws is a pivot.
           The pad tool's shank is the same solution to the same problem. -->
      <geom name="cap_blank_stem" type="cylinder" size="0.012 0.014"
            pos="0 0 0.035" material="stemmat" mass="0.015"/>
    </body>
    <!-- nest is SLIMMER than the cap (r20 vs r34) so the jaws can close on the cap's
         cylinder with both pad rows without striking the nest wall -- the v4 lesson
         (a fixture must clear the part's largest feature) applied in reverse: here the
         FIXTURE must stay inside the GRIPPER's closing envelope. -->
    <geom name="cap_nest" type="cylinder" size="0.020 0.018"
          pos="{MEM_XY[0] - 0.13:.3f} {MEM_XY[1] + 0.10:.3f} 0.018" material="postmat"/>

    <!-- ===================== WATER BIN (Stage 10 dip) =====================
         The dip is a BUBBLE TEST on a pressurised subassembly (3.6 -> 3.7), not a wash.
         No fluid is simulated: the "water" geom has contype 0 and exists so the render
         reads as a dip. -->
    <body name="waterbin" pos="{BIN_XY[0]:.3f} {BIN_XY[1]:.3f} 0">
      {"".join(f"""<geom name="bin_w{i}" type="box" size="{0.006 if i < 2 else 0.085} {0.085 if i < 2 else 0.006} 0.105"
            pos="{(0.085 if i == 0 else -0.085 if i == 1 else 0):.3f} {(0 if i < 2 else 0.085 if i == 2 else -0.085):.3f} 0.105"
            material="binmat"/>
      """ for i in range(4))}
      <geom name="bin_floor" type="box" size="0.085 0.085 0.005" pos="0 0 0.005"
            material="binmat"/>
      <geom name="bin_water" type="box" size="0.080 0.080 0.088" pos="0 0 0.098"
            material="watermat" contype="0" conaffinity="0"/>
      <site name="bin_centre" pos="0 0 0.020" size="0.005" rgba="0 0 0 0"/>
    </body>
  </worldbody>

  <!-- THE CAP MUST BE TOLD TO TOUCH ITS OWN O-RING. `mem_cap` is a CHILD body of
       `mem_bowl` joined by the thread, and MuJoCo excludes contacts between bodies
       connected by a joint -- so the cap wound 49 mm down through the seal without ever
       loading it, and the driver never stalled. Explicit pairs override that filtering.
       This is the seal that makes the torque criterion mean anything. -->
  <contact>
    {"".join(f"""<pair geom1="mem_cap_body" geom2="mem_oring{i}" solref="0.02 1"
          solimp="0.85 0.93 0.0025" friction="0.9 0.9 0.02 0.001 0.001"/>
    """ for i in range(12))}
    {"".join(f"""<pair geom1="mem_cap_body" geom2="mem_rim{i}" solref="0.004 1"
          solimp="0.97 0.99 0.0005" friction="1.1 1.1 0.05 0.001 0.001"/>
    """ for i in range(8))}
  </contact>

  <equality>
    <!-- ================= POSITIVE TOOL COUPLING (V5-C) =================
         A robotic TOOL CHANGER, not a grip. When latched, the tool is mechanically
         locked to the wrist and cannot move relative to it.

         WHY THIS REPLACED THE GRIP. A parallel-jaw grip on a shank was measured to let
         the tool creep 60-70 mm across a single face's raster -- and that creep was
         INSENSITIVE to grip command (245 vs 255) and to press depth (3.0 vs 1.5 mm),
         which rules out friction and points at grip geometry. Keying the shank cut the
         wrist-rotation pivot from 87 mm to 9.6 mm but did not stop the creep. No
         production cell holds a process tool in a parallel-jaw grip for exactly this
         reason; it uses a changer or a positively-located holder.

         WHAT IS ASSUMED, AND WHAT IS STILL EARNED. The weld models the LATCHED state --
         i.e. it assumes the hardware coupling is rigid, which is what a changer sells.
         It does NOT assume the robot can find it: the latch only engages when the wrist
         is inside a stated capture envelope, and it welds at the ACTUAL relative pose
         achieved, so any residual misalignment is carried into the wipe rather than
         being quietly corrected. Alignment remains a real robot task and the latch can
         fail. A real changer would centre the tool as it pulls in, so this is the
         conservative direction. -->
    <weld name="toollock" body1="xarm_gripper_base_link" body2="padtool"
          active="false" solref="0.004 1" torquescale="1"/>
    <!-- V9: one latch per cloth. A weld binds two SPECIFIC bodies at model-compile
         time, so three tools need three welds; couple() activates exactly one. -->
    <weld name="toollock_damp" body1="xarm_gripper_base_link" body2="damppad"
          active="false" solref="0.004 1" torquescale="1"/>
    <weld name="toollock_dry" body1="xarm_gripper_base_link" body2="drypad"
          active="false" solref="0.004 1" torquescale="1"/>
    <!-- THE THREAD. MuJoCo has no screw joint, so one is built from a hinge and a slide
         tied together: cap_z = -(pitch / 2pi) * cap_rot. That single line is what makes
         the cap MULTI-TURN and axially advancing rather than our fixed-angle bayonet.
         pitch = {MEM_THREAD_PITCH*1000:.0f} mm/turn, so {MEM_TURNS_MAX:.0f} turns of driver stroke is
         {MEM_TURNS_MAX*MEM_THREAD_PITCH*1000:.0f} mm of travel. -->
    <joint name="capthread" joint1="cap_z" joint2="cap_rot"
           polycoef="0 {-MEM_THREAD_PITCH/(2*np.pi):.8f} 0 0 0"
           solref="0.001 1" solimp="0.99 0.999 0.0001"/>
    <weld name="partlock" body1="xarm_gripper_base_link" body2="mem_bowl"
          active="false" solref="0.004 1" torquescale="1"/>
  </equality>

  <actuator>
    <!-- The rotary indexer is a COMMANDED AXIS. On the real cell this is a stepper or
         servo indexer with its own controller; here it is one more setpoint. Modelled
         explicitly so the integration cost is visible rather than hidden in the scenery.

         CTRLRANGE IS A FULL REVOLUTION EACH WAY, and that is a hardware requirement, not
         a convenience. It was +-3.1416 (half a turn), an unexamined default: the joint
         itself is unlimited, so nothing failed loudly -- but MuJoCo CLAMPS ctrl, so
         v5_clean's `deg2rad(270)` = 4.712 rad silently became 3.1416 and the indexer
         stopped at 180 deg. The fourth face pass then re-wiped the back panel while one
         SIDE face was never presented at all, on every seed. A real indexer turns
         continuously; specify one that does. -->
    <position name="tt" joint="tt_rot" kp="120" kv="18" ctrlrange="-6.2832 6.2832"
              forcerange="-40 40"/>
    <!-- THE TORQUE-LIMITED DRIVER. A velocity actuator whose FORCERANGE IS THE TORQUE
         LIMIT: it winds the cap down until the O-ring load makes it stall, which is
         precisely how a real nutrunner terminates. Achieved turns and the torque at
         cutoff are what get reported -- never a commanded angle.
         {MEM_TORQUE_NM:.1f} N.m is OUR number. Stage 10 says only "Ensure the cap is tightened
         properly with the spanner"; no torque figure exists anywhere in the corpus. -->
    <velocity name="capdrv" joint="cap_rot" kv="3.0"
              ctrlrange="{-SPINDLE_FREE_RADS:g} {SPINDLE_FREE_RADS:g}"
              forcerange="{-MEM_TORQUE_NM:.2f} {MEM_TORQUE_NM:.2f}"/>
  </actuator>

  <keyframe>
    <!-- ****************************** READ THIS ******************************
         USE `v5home`. DO NOT USE THE INHERITED `home` (keyframe index 0).

         THE SAME BUG AS v4, AGAIN. CLAUDE.md already records it for the cartridge: "the
         keyframe `home` predates the cartridge free joint -- its qpos must be set
         explicitly after mj_resetDataKeyframe". `home` comes from xarm7.xml and declares
         only the 13 arm+gripper values; MuJoCo zero-fills the rest. In this scene that
         puts the pad tool's free joint at the WORLD ORIGIN -- 20 mm inside the bench,
         with a degenerate zero quaternion. Nothing in V5-A resets that way, which is
         exactly why it survived review: a landmine for the first controller that does.

         xarm7.xml is shared with the v2/v3/v4 scenes, so `home` cannot be fixed there
         without touching three validated cells. Hence a second, complete keyframe.
         `v5_check_scene.py` asserts this one is correct and that index 0 is NOT used.

         AND IT HAPPENED AGAIN IN V5-E. Adding the membrane bowl and element free joints
         plus the two cap joints silently extended nq from 22 to 38, and the old 22-value
         key zero-filled the rest -- putting the bowl AND the membrane element at the world
         origin, i.e. inside the arm riser: 174 contacts at spawn, and a screw that could
         not load because the parts it screws onto were somewhere else. If you add a joint
         to this scene, THIS STRING IS PART OF THE CHANGE.

         AND IT HAPPENED A FOURTH TIME IN V6-ARM (fixed 2026-08-09). `cap_blank`'s free
         joint took nq from 38 to 45; the 38-value key zero-filled the rest and put the
         cap blank at the world origin -- 20 contacts at spawn, buried in the arm riser
         and the bench, on EVERY reset. `v5_membrane` papered over it by re-setting that
         joint from `m.qpos0` after the reset, so the membrane numbers are unaffected;
         `v5_clean` does not, so every cleaning run since b388669 has carried a trapped
         body grinding through world geometry. `v5_check_scene` caught it and the failure
         was left unread -- run the gates.

         THE LESSON, AND WHY THE FIX IS HERE AND NOT IN THE CONSUMER: a per-consumer
         `qpos0` patch fixes one caller and leaves the landmine armed for the next. The
         keyframe is the single place every consumer already goes through.

         qpos layout (61): 7 arm | 6 gripper | 1 tt_rot | 7 padtool free (xyz + wxyz)
                         | 1 acf (compliance flange, 0 = fully extended)
                         | 7 damppad free | 1 damp_acf | 7 drypad free | 1 dry_acf
                         | 7 mem_bowl free | 1 cap_rot | 1 cap_z | 7 mem_elem free
                         | 7 cap_blank free
         (V9 added the damp/dry cloths -- FIFTH keyframe extension; every previous
          free-body addition that skipped this line spawned at the world origin
          inside the arm riser, four times running)
         ctrl layout (10): 7 arm | 1 gripper | 1 tt | 1 capdrv -->
    <key name="v5home"
         qpos="0 -.247 0 .909 0 1.15644 0  0 0 0 0 0 0  0  {tx:.3f} {ty:.3f} 0.040 1 0 0 0  0
               {dpx:.3f} {dpy:.3f} 0.040 1 0 0 0  0
               {drx:.3f} {dry_:.3f} 0.040 1 0 0 0  0
               {MEM_XY[0]:.3f} {MEM_XY[1]:.3f} 0.040 1 0 0 0  0 0
               {MEM_XY[0] - 0.13:.3f} {MEM_XY[1]:.3f} 0.072 1 0 0 0
               {MEM_XY[0] - 0.13:.3f} {MEM_XY[1] + 0.10:.3f} 0.046 1 0 0 0"
         ctrl="0 -.247 0 .909 0 1.15644 0 0 0 0"/>
  </keyframe>
</mujoco>
''')
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="ufactory_xarm7/refurb_scene_v5.xml")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--x", type=float, default=CAB_X)
    a = ap.parse_args()
    xml = build(a.seed, a.x)
    with open(a.out, "w") as f:
        f.write(xml)
    print(f"wrote {a.out}  (seed {a.seed}, cabinet at x={a.x})")
    print(f"  pools: {N_SOIL} soil, {N_SCRATCH} scratch, {N_DENT} dent "
          f"= {N_SOIL + N_SCRATCH + N_DENT} geoms on all 5 exposed faces")
