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
BACKDROP_X = 0.86             # matte panel behind the device, from the arm's viewpoint
TT_RISE = 0.010               # rotary indexer disc height above the bench
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
  </worldbody>

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
  </equality>

  <actuator>
    <!-- The rotary indexer is a COMMANDED AXIS. On the real cell this is a stepper or
         servo indexer with its own controller; here it is one more setpoint. Modelled
         explicitly so the integration cost is visible rather than hidden in the scenery. -->
    <position name="tt" joint="tt_rot" kp="120" kv="18" ctrlrange="-3.1416 3.1416"
              forcerange="-40 40"/>
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

         qpos layout (22): 7 arm | 6 gripper | 1 tt_rot | 7 padtool free (xyz + wxyz)
                         | 1 acf (compliance flange, 0 = fully extended)
         ctrl layout  (9): 7 arm | 1 gripper | 1 tt -->
    <key name="v5home"
         qpos="0 -.247 0 .909 0 1.15644 0  0 0 0 0 0 0  0  {tx:.3f} {ty:.3f} 0.040 1 0 0 0  0"
         ctrl="0 -.247 0 .909 0 1.15644 0 0 0"/>
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
