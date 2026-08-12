"""V5-C -- Stage-2/3 cleaning: wipe the device's faces with a compliant pad.

    ../venv/bin/python v5_clean.py --run 3          one unit, verbose
    ../venv/bin/python v5_clean.py --eval 8          held-out; --seed0 defaults to 900

    ../venv/bin/python v5_clean.py --sabotage 8      V5-D falsification test

`--render` is still NOT implemented (that is V5-G): no v5 station writes video. The
`frames` dict is threaded through every motion method, so a renderer is wiring rather than
construction -- sim_poc4.py has a working template.

WHAT THIS IS. DrinkPrime Stage 2 (Cabinet Cleaning) and Stage 3 (Back Panel & Top Cover
Cleaning). Their own acceptance criterion is COVERAGE, in their words:

    Stage 2, activity : "Thoroughly clean the exterior of the device,
                         ENSURING ALL SURFACES ARE COVERED"
    Stage 3, QC check : "check for any MISSED SPOTS during cleaning"

So the metric is not one we picked for being easy to compute -- it is theirs.

HOW IT WORKS. The arm picks the wiping pad off its post by the stem, presses it against a
face, and rasters. The device is on the rotary indexer, so each face is rotated into the
front working position -- where V5-0 measured 100% reachability -- and wiped there. Soil
is removed where the pad actually makes contact, so cleaning and the camera observe the
IDENTICAL mechanism: the same geoms the classifier graded are the ones that disappear.

CONTACT IS THE WHOLE PROBLEM. A position-controlled arm cannot ask for a force; it can
only ask for a position. Press too little and the pad floats and misses patches; press too
much and you stall the arm or shove the device off the indexer. The pad is deliberately
compliant (measured force/penetration: 1.4 / 2.0 / 2.4 / 2.6 / 3.0 / 4.6 mm at
0 / 5 / 10 / 20 / 40 / 60 N, monotonic), so a commanded over-travel converts into a bounded
force rather than a collision. That is the cheap industrial answer -- let the tool absorb
the error instead of closing a force loop -- and it is what V5-0's 30-degree tilt cone
was already assuming.

WHAT IS NOT MODELLED. No cream, no detergent, no chemistry, no wear. What is verified is
that the soil the camera could see is gone, not that CIF cream would lift it.
"""
import argparse
import json
import sys
from dataclasses import dataclass

import numpy as np
import mujoco

import v5_triage as TR
import v5_reach as RE
from sim_poc2 import ik_step

XML = "ufactory_xarm7/refurb_scene_v5.xml"


# ============================================================================
# ARM-SPECIFIC CONSTANTS -- THE ONLY BLOCK AN ARM SWAP HAS TO TOUCH
# ============================================================================
# PORTABILITY RULE (2026-08-09). There is a live possibility we move off the xArm7
# (see TRADE_STUDY.md, option D). Everything else in this file is written in the
# CELL/PART frame -- faces, pad radius, press depth, feed rate, coverage criteria --
# and none of it mentions the arm. What genuinely depends on which arm is bolted to
# the bench lives here, so a swap is a profile + one re-validation run, not a rewrite.
#
# What is deliberately NOT here, because it is not ours to type: joint LIMITS and the
# mount pose are read from the model at load (`m.jnt_range`, `link_base`). A profile
# that restated them could drift from the arm it claims to describe -- the same class
# of bug as CELL_SPEC's numbers, which is why those are read from the model too.
#
# `reach_m` / `payload_kg` / `repeatability_mm` are NOT used by the controller. They
# are here so the trade study and this cell quote one set of numbers, and so that
# "YAM publishes no repeatability" is a visible None rather than a silent omission.
@dataclass(frozen=True)
class ArmProfile:
    name: str = "xArm7"
    joints: tuple = ("joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "joint7")
    acts: tuple = ("act1", "act2", "act3", "act4", "act5", "act6", "act7")
    # IK seed. A 7-DoF null space needs a cold start that is already in the branch we
    # want; a 6-DoF arm has no null space and this is just a starting guess.
    q_cold: tuple = (0.0, -0.3, 0.0, 0.9, 0.0, 1.1, 0.0)
    # Setpoint rate limit, rad per control step. **THE ARM'S PUBLISHED MAXIMUM**, adopted
    # 2026-08-10: UFACTORY publish 180 deg/s = 3.1416 rad/s, which at the model's 2 ms
    # timestep is 0.0062832 rad/step.
    #
    # It used to be 0.02 (= 10 rad/s, 3.2x the datasheet) and nothing caught it for three
    # phases of work, because EVERY METRIC THIS STATION REPORTS IS ABOUT CONTACT -- force,
    # coverage, tilt -- so free-space motion appeared in no number, no assertion and no
    # gate. It was found by a human watching the video and saying the arm flails.
    # Measured at 0.02: repositioning moves reached 3020 mm/s against a published 1 m/s
    # TCP limit; the sweep itself was always fine (93 mm/s median).
    #
    # Adopting it was not merely honest, it was BETTER: coverage unchanged at 100%, peak
    # contact force 32.15 -> 27.35 N (driving into a surface more slowly lands more
    # gently), and point mode got FASTER because fewer approaches overshoot into a stall.
    # `max_joint_rate_rad_s` and `max_tcp_speed` below are the datasheet figures the gates
    # assert against -- see v5_check_spec.py and Cell.report().
    joint_rate: float = 0.0062832
    # Branch-jump thresholds for the nearest-posture preference. A 7-DoF arm has a
    # continuum of solutions per pose and picks a bad one if you let it; these bound
    # how far the planner may travel between adjacent path knots. A 6-DoF arm has
    # discrete branches instead of a continuum and would want smaller numbers.
    max_joint_jump: float = 0.35
    hard_joint_jump: float = 0.60
    ik_damping: float = 0.08
    ik_gain: float = 0.55
    plan_iters: int = 220
    # --- DATASHEET LIMITS. These are ASSERTED against, not merely recorded:
    #     v5_check_spec.py checks joint_rate against max_joint_rate_rad_s, and
    #     Cell.report() checks the MEASURED peak tool speed against max_tcp_speed the
    #     same way it checks peak contact force against force_hi.
    max_joint_rate_rad_s: float = 3.1416   # [published] 180 deg/s
    max_tcp_speed: float = 1.0             # [published] 1 m/s at the TCP
    # The governor COMMANDS this fraction of the rating so the MEASURED peak lands under
    # it: a position servo overshoots its setpoint's velocity while closing an error, so
    # commanding exactly 1.00 m/s measured 1134 mm/s. This is the commissioning margin a
    # real cell is set up with, and it is deliberately a SEPARATE number from the rating
    # -- `max_tcp_speed` is what the arm is rated for and is what the gate asserts against;
    # this is what we choose to ask for.
    tcp_cmd_margin: float = 0.80
    # MAXIMUM FOLLOWING ERROR, rad per joint. NOT a datasheet figure -- a CONTROLLER
    # parameter, tuned so the servo's catch-up sprint stays inside the datasheet speed.
    # 0 disables the clamp (pre-2026-08-10 behaviour). See Cell._advance.
    # 0.25: satisfies the 180 deg/s joint limit with 21% margin AND gives the lowest
    # peak contact force of any value tried. Do NOT tighten it to chase the TCP figure --
    # the force cliff is at 0.14 (89.5 N). The tool speed is handled by the Cartesian
    # governor in _advance instead, which is where it belongs.
    max_follow_err: float = 0.25
    reach_m: float = 0.70
    payload_kg: float = 3.5
    repeatability_mm: float = 0.1


XARM7 = ArmProfile()
ARM = XARM7


@dataclass(frozen=True)
class CleanConfig:
    xml: str = XML
    # --- grasp. MEASURED, not inherited: the finger pads sit +38.9 mm ABOVE link_tcp on
    #     this gripper. The project's older note says ~25 mm, which is for the v2
    #     cartridge grasp; reusing it here would have missed the stem entirely.
    # --- tool changer. The wrist must reach this pose, pointing down, within the
    #     capture envelope, or the latch fails and the cycle aborts. A real changer's
    #     capture is a few mm; 4 mm / 4 deg is a realistic commodity figure.
    couple_tcp: tuple = (0.300, -0.340, 0.130)
    capture_mm: float = 4.0
    capture_deg: float = 4.0

    pad_offset: float = 0.0389
    stem_grasp_z: float = 0.105     # where on the stem the pads should close
    grip_open: float = 0.0
    grip_closed: float = 245.0

    # --- raster. Rows/cols are COMPUTED PER FACE from the pad size, not fixed: a fixed
    #     5 x 7 grid put 99 mm between rows while the pad only wipes a 68 mm swathe, so
    #     the raster stepped straight over the soil and cleaned 0 of 9 patches while
    #     reporting healthy contact forces the whole time. Step must be <= the wipe
    #     width or coverage is decided by luck.
    # step <= radius guarantees the worst-case in-plane gap (step/sqrt(2) for a square
    # grid) stays inside the wipe radius. At 1.30 it did not, and coverage depended on
    # where the soil happened to land between passes.
    # V6, 2026-08-05: 0.95 -> 1.20. THIS IS A DIAGNOSIS, NOT A TUNING KNOB.
    #
    # The budget showed STROKE is 91.3% of the cycle and all overhead is 7.2%, so the
    # cycle IS the raster and the only thing that matters is POINT COUNT. Per-point cost
    # is essentially FIXED (0.38-0.85 s, unchanged when the stride grows 37%) because each
    # wipe point is floored by two 0.20 s stall windows -- it is not travel-bound.
    #
    # On a square lattice the worst-case uncovered point is a cell CENTRE at step/sqrt(2),
    # so full coverage needs step <= R*sqrt(2) = 1.414 R. The old 0.95 R oversampled by
    # 2.2x in point count for no coverage benefit. Measured sweep (fresh 1810-1817,
    # confirmed held-out 1830-1837):
    #
    #   0.95  254.7 s  468 pts  100% cov  0 missed      <- was here
    #   1.20  186.8 s  323 pts  100% cov  0 missed      <- HERE. 18% geometric margin
    #   1.30  163.8 s  272 pts  100% cov  0 missed         8% margin -- available, not taken
    #   1.414 141.5 s  224 pts  97.4% cov 4 missed      <- the cliff, 0% margin
    #
    # 1.30 is faster and passed 16 units, but coverage failure is a RARE EVENT -- a spot is
    # only missed if soil lands in a cell-centre gap -- so 16 units x ~18 patches does not
    # prove a 2.4 mm gap band is closed, only that it is rarely hit. 1.414 is a cliff and
    # 1.30 sits 8% from it. Real surface variation, pad wear or fixture error would eat that.
    step_frac: float = 1.20         # raster step, in pad RADII
    # --- V7 CONTINUOUS STROKE (2026-08-09). DEFAULT OFF: point mode above is the
    #     published baseline and stays byte-identical while this is False.
    #
    # THE DIAGNOSIS THIS CORRECTS IS OUR OWN. V6 measured that the cycle IS the raster
    # and that per-point cost is FIXED rather than travel-proportional -- both true --
    # and then swept `speed`, which only moves the arm faster BETWEEN stops. It bought
    # 9.6% and destabilised the contact model, so we wrote down "feed rate is a dead
    # lever". The question never asked was whether to stop at all. Each point is floored
    # by TWO 0.20 s `wipe_stall_s` windows (the first sets the reference error, the
    # second compares against it), so ~0.40 s of a ~0.52 s point is the arm standing
    # still deciding it has arrived. A raster of 323 such points is ~168 s of a 187 s
    # cycle, and it is also exactly why the video looks like a bird pecking.
    #
    # WHAT CHANGES, PHYSICALLY. In point mode the pad is a stamp: approach, press,
    # confirm arrival, retreat, repeat. In stroke mode it is a wipe -- the pad is
    # seated once per contiguous run and then swept along the path under continuous
    # flange compression, which is what the ACTIVE CONTACT FLANGE was added for. The
    # flange is an 800 N/m spring over 30 mm, so normal force is set by commanded
    # compression, not by arrival tolerance; a path that wanders half a millimetre off
    # the surface costs 0.4 N instead of a stall.
    #
    # WHAT DOES *NOT* CHANGE, and this is the part that keeps the number honest: soil
    # removal still requires MEASURED CONTACT FORCE over the patch (`wipe()`), the
    # camera still decides acceptance, and the row pitch is unchanged. The speedup is
    # bought by not stopping -- NOT by sampling less. See row_frac.
    stroke: bool = False
    # Tangential sweep speed of the PAD ALONG THE SURFACE, m/s. This is a tool-frame
    # quantity on purpose: it is what a process engineer specifies for a wipe and it
    # ports across arms, whereas `speed` above is a joint-space setpoint rate that
    # means nothing off this arm. Swept on 1900-1907; see V5_PLAN "V7 STROKE SWEEP".
    # 0.20. THE FEED CLIFF THAT FORCED 0.10 IS GONE, AND IT WENT FOR A REASON.
    #
    # Pre-clamp (2026-08-09) there was a sharp coverage cliff between 0.10 and 0.15 m/s:
    # 0.15 missed 2 patches, 0.30 missed 3. The cause was TRACKING -- the pad's in-plane
    # departure from the commanded path grew with feed (worst 18 -> 21 mm), and a
    # displaced band leaves a gap the geometry says should not exist.
    #
    # Adopting the arm's published speed limits (2026-08-10) added a FOLLOWING-ERROR
    # CLAMP, and that made tracking FEED-INDEPENDENT. Re-swept on fresh 2100-2103:
    #
    #   feed   cycle    coverage  missed   peak N   tracking med/p99/worst
    #   0.05   235.5 s   100%     0/81     21.22    2.5 / 12.9 / 15.2 mm
    #   0.10   146.6 s   100%     0/81     22.04    2.6 / 13.5 / 15.2 mm
    #   0.15   121.6 s   100%     0/81     22.47    2.7 / 13.7 / 15.2 mm
    #   0.20   111.4 s   100%     0/81     22.62    2.8 / 14.0 / 15.2 mm   <- HERE
    #   0.30   104.1 s   100%     0/81     22.62    3.0 / 14.2 / 15.2 mm
    #
    # WORST-CASE TRACKING IS 15.2 mm AT EVERY FEED. That identity is the finding: the
    # error is no longer set by how fast the pad sweeps, it is set by the clamp. So the
    # mechanism that produced the old cliff no longer operates -- this is not "we tested
    # faster and nothing broke", it is "the thing that used to break is gone".
    #
    # 0.20 rather than 0.30, for two reasons. (1) MARGIN: 0.30 is measured clean above it,
    # so the shipped value has 1.5x headroom to the fastest verified setting, which is the
    # same discipline that shipped step_frac 1.20 under a 1.414 cliff. (2) DWELL: our model
    # removes soil on CONTACT, not on dwell, so the sim cannot see a rub getting too brief.
    # At 0.20 a surface point spends 0.30 s under the 60 mm pad; at 0.30 it is 0.20 s.
    # Real cream on real soil may care, and we cannot measure that here -- so we do not
    # spend margin the model is blind to.
    stroke_feed: float = 0.20
    # Trapezoidal ramp at each end of a run, m/s^2. Without it the first control step
    # of a stroke demands a step change in velocity, which the rate limiter turns into
    # a lag the pad drags through.
    stroke_accel: float = 0.60
    # A knot turning by more than this is a CORNER, not curvature: the spline gets a
    # one-sided tangent there and the velocity plan slows to meet it. 25 deg is well
    # below the 60-120 deg the serpentine's row reversals actually produce and well
    # above the 0-5 deg an ordinary along-row knot shows, so nothing sits near the line.
    stroke_corner_deg: float = 25.0
    # SEAT RATE. The stroke's force peak is NOT in the sweep -- measured, it is in the
    # SEAT, on face 180 (the back panel stands 10 mm proud, the geometry that has caused
    # every large contact in this station's history), with the flange at 22.6 of its
    # 30 mm. Driving into a surface and sliding along one are different motions with
    # different force budgets, and the V6 feed sweep's mistake was treating them as one
    # number. Approach contact at a fraction of the sweep rate; sweep at full rate.
    # 0.20 -- and it costs 0.6 s per unit (0.5%) while taking the peak from 34.66 N to
    # 32.15 N, BELOW the 32.94 N the point raster peaks at. Swept on seed 1900:
    #   1.00 -> 136.66 s / 34.66 N | 0.50 -> 136.69 / 34.35
    #   0.35 -> 136.95 s / 33.88 N | 0.20 -> 137.30 / 32.15
    stroke_seat_scale: float = 0.20
    # ROW PITCH, in pad radii. THIS IS THE ONLY COVERAGE-CRITICAL SPACING IN STROKE
    # MODE and it is why `step_frac` alone is not enough any more.
    #
    #   point mode : coverage is a LATTICE problem. Worst uncovered spot is a cell
    #                centre at step/sqrt(2), so the cliff is step <= 1.414 R.
    #   stroke mode: coverage along a row is CONTINUOUS -- the pad sweeps a band of
    #                half-width R -- so the only gap is BETWEEN rows, and the worst
    #                uncovered spot is midway between two rows at pitch/2. The cliff
    #                moves to pitch <= 2.000 R.
    #
    # We shipped 1.20 against a 1.414 cliff (18% margin) and explicitly declined 1.30
    # (8%) because coverage failure is a RARE EVENT that a 16-unit run cannot disprove.
    # The same reasoning applies here and the same margin is kept. 1.20 R is held as
    # the DEFAULT -- identical row geometry to the published raster -- so the stroke
    # result isolates one variable. The wider pitches the geometry allows are measured
    # (`--row-sweep`) and reported, not shipped.
    row_frac: float = 1.20
    # --- V6 TARGETED MODE (off by default; full coverage is the customer's criterion).
    # Visits only raster points within a pad radius of soil, and skips soil-free faces
    # entirely. HONESTY LABEL, printed every run it is used: soil locations are taken
    # from ground truth as a stand-in for camera localisation (perception assumed
    # perfect). The BACKSTOP is real: VERIFY re-inspects with the actual cameras and
    # triggers one spot re-clean round; the residue number is still camera-measured.
    targeted: bool = False
    target_margin: float = 0.0      # extra keep-radius around soil, m
    # 3 mm, not 6. The pad gives 1.4-4.6 mm over 0-60 N, so 6 mm of commanded
    # over-travel sat high on that curve and the resulting friction tore the tool out of
    # the grip. 3 mm lands around 10 N -- enough to wipe, not enough to strip.
    # THE PRESS AND THE TOLERANCE ARE COUPLED. With a positively-latched tool nothing
    # absorbs position error except the pad's own compliance (2.6 mm at 20 N), so an
    # arrival tolerance LARGER than the press depth lets the pad bury itself: at
    # tol 5 mm / press 3 mm the median contact force was 101 N and the peak 933 N, with
    # only 22% of samples in band. The compliant GRIP used to hide this by slipping --
    # that is the hidden cost of a rigid coupling, and it has to be paid in precision.
    # The pad is 20 mm thick and its geom ORIGIN is at its centre, so commanding the
    # centre onto the face plane buries it by half a thickness before any press at all.
    # Measured consequence: 12.5 mm of penetration, 101 N median / 795 N peak contact,
    # 22% of samples in band. Target the pad's CONTACT SURFACE, not its centre. Same
    # mistake as the gripper finger-pad offset, one object further out.
    pad_thick_half: float = 0.010   # m, half-thickness of the pad face geom
    # With the ACTIVE CONTACT FLANGE the press is no longer a knife-edge: it is the
    # commanded COMPRESSION of a 800 N/m spring, so it sets force directly (12 mm ->
    # ~9.6 N) and a few mm of path error costs a few newtons instead of tens. Before
    # the flange the press had to be smaller than the arrival tolerance to avoid burying
    # the tool, which is not a condition a real arm can hold.
    press: float = 0.012            # m of commanded flange compression
    wipe_tol: float = 0.004         # m, arrival tolerance -- now well inside the stroke
    standoff: float = 0.055         # m, tcp-to-face when clear
    # The generator scatters patches over +-0.41 of each face extent, so a raster that
    # only spans +-0.34 can never reach the outer ring no matter how well it presses.
    pad_half: float = 0.030         # m, half-width of the 60 mm pad
    floor_margin: float = 0.012     # m, extra clearance above the bench/platter
    faces_deg: tuple = (0.0, 90.0, 180.0, 270.0)

    # --- soil removal: the pad's contact patch
    pad_radius: float = 0.030       # m, in-plane wipe radius of the 60 mm square pad
    pad_reach: float = 0.022        # m, how far off the pad plane a patch still counts
    contact_min_n: float = 0.5      # N, below this the pad is not really touching
    # A WIPE IS DONE WHEN THE PAD HAS SWEPT THE POINT, not when the wrist hits a
    # positional tolerance it cannot hold while loaded. Waiting on 4 mm of TCP error was
    # unreachable under contact -- 0.8 deg of joint lag is 14 mm at that extension -- so
    # every top-face point and 60% of front-face points ran the full 2.5 s timeout
    # pressing at full command. Measured cost of that stall: peak 326 N and only 74.8%
    # of samples in band, beyond where the pad model is validated. Terminating on contact
    # is both the physical completion criterion for a wipe and the thing that bounds the
    # press duration. The COVERAGE criterion is untouched: a patch still only counts when
    # real contact force passes over it.
    # First attempt at this was "break once contact has lasted 0.1 s", which fired on the
    # first graze while the wrist was still 20-90 mm out: coverage fell 100% -> 88.9%.
    # A position-controlled arm pressing into a surface converges to a STEADY-STATE
    # error; the useful signal is that it has stopped closing, not that it has touched.
    # --- V5-D verification. The check re-inspects the unit we just cleaned through the
    #     SAME observation path the triage station uses -- same fixed camera, same index
    #     angles, same per-face regions, same feature extractor. That is not tidiness: v4's
    #     first sabotage test wrongly PASSED 2 of 5 dirty parts precisely because
    #     verification looked through one camera view while the inspection it was checking
    #     used two. A verifier that sees less than the process it verifies cannot fail.
    verify_soil_max: int = 0        # residual soil components tolerated, per unit
    # Joint-space continuity between adjacent raster points. 0.35 rad is comfortably
    # inside what the executor can cover in its 2.5 s budget at 0.02 rad/step, and well
    # above the 0.11-0.18 rad median step the geometry actually requires.
    # ARM-SPECIFIC: sourced from the profile, not typed here. Continuous strokes make a
    # branch jump MORE dangerous, not less -- in point mode a jump wastes a point, in
    # stroke mode it whips the pad across the device mid-wipe with the flange loaded.
    arm: ArmProfile = ARM
    max_joint_jump: float = ARM.max_joint_jump   # rad, per joint, between path knots
    # Above this, DECLINE the point instead of executing it. See plan_pad.
    hard_joint_jump: float = ARM.hard_joint_jump  # rad, per joint -- refuse rather than swing
    wipe_stall_s: float = 0.20      # window over which progress is judged
    wipe_stall_m: float = 0.0005    # less closing than this, while in contact, is a stall
    # ...and 'in contact' has to mean SEATED, not grazing. contact_min_n is 0.5 N, which
    # the pad reaches on the way in while the wrist is still tens of mm out; stalling on
    # that ended points before the pad had swept them and cost 11 points of coverage.
    wipe_seat_n: float = 5.0        # N the pad must carry before a stall counts as done

    # --- force band. Upper bound from the pad curve (60 N is still monotonic); lower
    #     bound is "actually touching".
    force_lo: float = 1.0
    # 45, NOT 60. "Monotonic to 60 N" was an artifact of a COARSE GRID: the sweep
    # sampled 0/5/10/20/40/60 and never tried 50, where the contact solver goes unstable
    # (12.1 mm of penetration on an 10 mm pad). Sampled finely the curve is clean and
    # repeatable to 45 N and intermittently unstable above -- 50 breaks, 55 is fine, 60
    # breaks, 65 is fine. That is solver behaviour, not a material property, and it was
    # present BEFORE the membrane station was added (verified against the committed
    # pre-V5-E scene), so it is a pre-existing mischaracterisation and not a regression.
    # Cleaning peaks at 34.5 N, comfortably inside the stable region.
    force_hi: float = 45.0

    speed: float = 1.0
    settle_s: float = 0.35


CFG = CleanConfig()


# ============================================================ helpers
def tool_mat_face(index_deg):
    """Tool frame pressing into the face currently at the FRONT (-X) position."""
    n = np.array([-1.0, 0.0, 0.0])
    z = -n
    x = np.cross(np.array([0.0, 0.0, 1.0]), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.column_stack([x, y, z])


def grasp_mat():
    """Gripper pointing straight down, jaws across the stem."""
    return np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]]).T


# --- the tilt cone. THIS IS NOT A RELAXATION WE INVENTED TO PASS. v5_reach's gate has
#     always reported coverage inside a 30-degree cone alongside the exact-normal
#     "strict" figure, because a 20 mm compliant pad genuinely conforms over about that
#     much. What went wrong is that the gate allowed the cone and the CLEANER did not
#     use it: tool_mat_face() returned one fixed exact-normal frame for every point, so
#     the station was living in the strict column -- front 83%, sides 27%, top 63% --
#     while a green gate reported the 100% one. Worse, re-running the placement sweep
#     with the tool's real 105 mm wrist-to-pad length shows NO placement presses
#     exact-normal on all five faces. The cone is load-bearing, not optional.
#
#     THE CONE IS IMPORTED FROM THE GATE, not restated here. That is fix 5, and it is the
#     one that stops this recurring: a gate is only a gate for the quantity it measures,
#     and a consumer that quietly uses a DIFFERENT quantity turns a green light into
#     decoration. v5_reach reports strict and relaxed side by side precisely so the
#     relaxation stays visible; the cleaner now spends that same allowance, from the same
#     constant, and reports the tilt it actually used against the limit.
TILT_TOL_DEG = RE.TILT_TOL_DEG
TILT_DIRS = RE.TILT_DIRS
COLD = np.array(ARM.q_cold)          # arm-specific; see ArmProfile
POS_TOL, ROT_TOL = 0.004, np.deg2rad(4)
PLAN_ITERS = ARM.plan_iters          # arm-specific


def tilted_mats(base):
    """(matrix, tilt_deg) pressing into the same face, smallest deviation first.

    Same construction as v5_reach.tilted_mats, but about a base frame handed in rather
    than rebuilt from a normal -- the tool changer cares about the in-plane orientation
    and re-deriving it here would quietly rotate the jaws.
    """
    for tilt in TILT_TOL_DEG:
        if tilt == 0.0:
            yield base, 0.0
            continue
        t = np.deg2rad(tilt)
        for k in range(TILT_DIRS):
            a = 2 * np.pi * k / TILT_DIRS
            axis = np.cos(a) * base[:, 0] + np.sin(a) * base[:, 1]
            quat, Rm = np.zeros(4), np.zeros(9)
            mujoco.mju_axisAngle2Quat(quat, axis, t)
            mujoco.mju_quat2Mat(Rm, quat)
            yield Rm.reshape(3, 3) @ base, tilt


class Cell:
    def __init__(self, cfg=CFG):
        self.cfg = cfg
        self.m = mujoco.MjModel.from_xml_path(cfg.xml)
        self.d = mujoco.MjData(self.m)
        self.ik = mujoco.MjData(self.m)
        m = self.m
        self.jnt = [m.joint(n).id for n in cfg.arm.joints]
        self.qadr = np.array([m.jnt_qposadr[j] for j in self.jnt])
        self.dof = np.array([m.jnt_dofadr[j] for j in self.jnt])
        self.rng_j = m.jnt_range[self.jnt].copy()
        self.act = [m.actuator(n).id for n in cfg.arm.acts]
        self.grip = m.actuator("gripper").id
        self.tt_act = m.actuator("tt").id
        self.tt_q = m.jnt_qposadr[m.joint("tt_rot").id]
        self.site = m.site("link_tcp").id
        self.pad_face = m.geom("pad_face").id
        self.stem = m.geom("pad_stem").id
        self.acf_q = m.jnt_qposadr[m.joint("acf").id]
        self.cab_bodyid = m.body("cabinet").id
        # the device's own COLLIDABLE geoms -- what surface_x rays against. Condition
        # patches are excluded by contype: they are 1 mm decals lying ON the surface, and
        # letting the probe hit one would put the raster plane a patch-thickness proud of
        # the face at exactly the points that matter most.
        self.cab_geoms = [g for g in range(m.ngeom)
                          if m.geom_bodyid[g] == self.cab_bodyid and m.geom_contype[g]]
        self.geomgroup = np.array([1, 1, 1, 1, 1, 1], np.uint8)
        self.pad_body = m.body("padtool").id
        name = lambda i: mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, i) or ""
        self.pools = {p: [i for i in range(m.ngeom) if name(i).startswith(p)]
                      for p in ("soil", "scr", "dent")}
        self.dt = m.opt.timestep
        self.q_des = None
        self.gb = m.body("xarm_gripper_base_link").id
        self.eq = next(k for k in range(m.neq)
                       if mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_EQUALITY, k) == "toollock")
        # a THIRD MjData, for planning only. mj_forward has to run to get contacts, and
        # running it on the live data would teleport the arm mid-cycle.
        self.plan = mujoco.MjData(m)
        base = m.body("link_base").id
        arm_bodies = set()
        for b in range(m.nbody):
            p = b
            while p != 0:
                if p == base:
                    arm_bodies.add(b)
                    break
                p = m.body_parentid[p]
        self.arm_geoms = {g for g in range(m.ngeom) if m.geom_bodyid[g] in arm_bodies}
        tool_bodies = {m.body("padtool").id, m.body("padhead").id}
        self.tool_geoms = {g for g in range(m.ngeom) if m.geom_bodyid[g] in tool_bodies}
        self.pad_jq = m.jnt_qposadr[m.body_jntadr[m.body("padtool").id]]
        self.tool_rel = None
        self.rend = None            # built lazily; rendering is the expensive part
        self.rend_top = None        # V5-D: the top face needs its own camera
        # V5-D: when True the pad still moves, still presses and still logs contact --
        # it simply stops REMOVING soil. Sabotaging the outcome rather than the motion is
        # what makes the falsification test about the verifier instead of about the arm.
        self.sabotage = False
        # PEAK TOOL SPEED -- initialised HERE, not only in reset(), because MemCell and
        # RouteCell override reset() and never call Cell.reset(). Anything a stepping
        # loop touches must exist from construction or a subclass crashes on the first
        # step; that is exactly how this bit on the first re-validation run.
        self.tcp_speed_max = 0.0
        self.joint_speed_max = 0.0
        # V6: opt-in cycle-time accounting. None = off, and OFF IS THE DEFAULT so the
        # published baselines cannot move. Set by `--budget`; see time_budget().
        self.budget = None

    # ------------------------------------------------------- tool changer
    def couple(self):
        """Latch the tool changer, if the wrist is inside the capture envelope.

        Returns (latched, position error, angle error). The latch welds at the pose
        ACTUALLY achieved, so residual misalignment is carried into the wipe rather than
        silently corrected -- a real changer would centre the tool as it pulls in, so
        this is the conservative direction.
        """
        m, d = self.m, self.d
        tcp = d.site_xpos[self.site]
        Rt = d.site_xmat[self.site].reshape(3, 3)
        want = np.array(self.cfg.couple_tcp)
        perr = float(np.linalg.norm(tcp - want))
        # wrist must also be pointing down, as the holder presents the tool
        aerr = float(np.degrees(np.arccos(np.clip(-Rt[2, 2], -1, 1))))
        if perr > self.cfg.capture_mm / 1000 or aerr > self.cfg.capture_deg:
            return False, perr, aerr
        p1, R1 = d.xpos[self.gb], d.xmat[self.gb].reshape(3, 3)
        p2, R2 = d.xpos[self.pad_body], d.xmat[self.pad_body].reshape(3, 3)
        relpos = R1.T @ (p2 - p1)
        q = np.zeros(4)
        mujoco.mju_mat2Quat(q, (R1.T @ R2).flatten())
        m.eq_data[self.eq][:3] = 0.0             # anchor, in body2 frame
        m.eq_data[self.eq][3:6] = relpos
        m.eq_data[self.eq][6:10] = q
        m.eq_data[self.eq][10] = 1.0             # torquescale
        d.eq_active[self.eq] = 1
        # keep the weld transform so the PLANNER can put the tool where the arm will
        # actually carry it. Without this the planner is blind to its own tool.
        self.tool_rel = (relpos.copy(), q.copy())
        mujoco.mj_forward(m, d)
        return True, perr, aerr

    def decouple(self):
        self.d.eq_active[self.eq] = 0
        mujoco.mj_forward(self.m, self.d)

    # ---------------------------------------------------------------- state
    def reset(self, seed):
        m, d = self.m, self.d
        mujoco.mj_resetDataKeyframe(m, d, m.key("v5home").id)
        rng = np.random.default_rng(seed)
        truth, nd, ns, no = TR.sample_condition(rng, TR.CFG)
        TR.set_pools(m, self.pools, nd, ns, no, rng)
        self.revealed_soil = [g for g in self.pools["soil"] if m.geom_rgba[g][3] > 0]
        self.raster_planned = self.raster_skipped = self.raster_infeasible = 0
        self.tilts = []
        self.q_warm = None
        self.face_unreachable = {}
        self.stroke_len = 0.0
        self.stroke_runs = 0
        self.stroke_path_err = 0.0
        self.stroke_lag = 0.0
        self.stroke_norm_err = 0.0
        self.stroke_corners = 0
        self.stroke_track = []
        # PEAK TOOL SPEED. Tracked on every run, asserted in report(). This exists
        # because free-space motion was invisible to every other metric for three
        # phases of work -- see ArmProfile.joint_rate.
        self.tcp_speed_max = 0.0
        self.joint_speed_max = 0.0
        self.device_shift = 0.0
        mujoco.mj_forward(m, d)
        self.q_des = d.qpos[self.qadr].copy()
        self.q_home = self.q_des.copy()
        return truth, nd, ns, no

    def _advance(self, q_new):
        """Set the commanded configuration, bounded by a MAXIMUM FOLLOWING ERROR.

        Rate-limiting the SETPOINT is not the same as limiting the ARM, and assuming it
        was is how the 2026-08-10 clamp initially failed: with the setpoint held to the
        published 3.14 rad/s the MEASURED joint speed still reached 5.71 rad/s and the
        tool 1871 mm/s. A position servo does not track the setpoint's velocity, it
        chases the setpoint's ERROR -- so whenever the planner hands over a configuration
        the arm is far from, the servo sprints. Measured: following error up to 0.787 rad
        (45 deg), and every over-speed step was inside a big repositioning move
        (TO FACE 464 steps, TO TOP 136, RETURN 79, APPROACH 39).

        Bounding the error bounds the sprint, which is what a real controller does -- and
        a real one FAULTS when the error grows past its limit rather than flooring it.
        """
        lo, hi = self.rng_j[:, 0], self.rng_j[:, 1]
        q_new = np.clip(q_new, lo, hi)
        # --- CARTESIAN SPEED GOVERNOR. The tool's speed is a CARTESIAN quantity and has
        # to be limited in Cartesian space. Trying to hold it down by squeezing the
        # following error instead was measured and REJECTED: it does reach 968 mm/s at
        # max_follow_err 0.15, but the force cliff sits at 0.14 (89.5 N, twice the model-
        # validity ceiling) -- a 7% margin on a catastrophic failure, where this project
        # already refused 8% on a merely-missed-spot failure. Throttling the servo also
        # throttles the press, which is why the two constraints fight.
        #
        # J maps joint rates to tool velocity, so the speed this step would command is
        # |J dq| / dt. Scaling dq is exact and costs one mj_jac per control step.
        # Bound the SETPOINT INCREMENT, not the following error. The first version
        # differenced against the MEASURED position -- that is the standing error, not a
        # step, so |J e|/dt read metres per second on every control step, the governor
        # scaled every command down by that factor, and the arm never reached the tool
        # changer at all (233 mm short of a 4 mm capture envelope). The commanded
        # Cartesian speed is how far the SETPOINT moves per step.
        vmax = self.cfg.arm.max_tcp_speed * self.cfg.arm.tcp_cmd_margin
        if vmax > 0 and self.q_des is not None:
            dq = q_new - self.q_des
            jacp = np.zeros((3, self.m.nv))
            mujoco.mj_jacSite(self.m, self.d, jacp, None, self.site)
            v = float(np.linalg.norm(jacp[:, self.dof] @ dq)) / self.dt
            if v > vmax:
                q_new = self.q_des + dq * (vmax / v)
        # --- FOLLOWING-ERROR CLAMP, which is what bounds the JOINT speed.
        e = self.cfg.arm.max_follow_err
        if e > 0:
            q_meas = self.d.qpos[self.qadr]
            q_new = np.clip(q_new, q_meas - e, q_meas + e)
        self.q_des = q_new
        return self.q_des

    def _tcp_tick(self):
        """Peak JOINT speed and peak TOOL speed, measured. Called after every mj_step.

        FROM VELOCITY STATE, NOT FROM POSITION DIFFERENCES. The first version of this
        differenced the pad's position between steps and read **51 m/s** on the very
        first re-validation run: this cell TELEPORTS several times per cycle -- verify()
        parks the arm by writing qpos, couple() snaps the tool in on a weld, the membrane
        station materialises the cap and teleports the assembly into the dip bin -- and a
        position difference across a teleport is a discontinuity, not a speed.
        `mj_objectVelocity` and `qvel` are derived from the velocity state, which a qpos
        teleport does not touch, so they measure motion and only motion.

        Joint speed is the primary figure because 180 deg/s is a JOINT limit on the
        datasheet; tool speed is reported beside it because that is what a person
        watching the cell actually sees.
        """
        qd = float(np.max(np.abs(self.d.qvel[self.dof])))
        if qd > self.joint_speed_max:
            self.joint_speed_max = qd
        v6 = np.zeros(6)
        mujoco.mj_objectVelocity(self.m, self.d, mujoco.mjtObj.mjOBJ_BODY,
                                 self.pad_body if self.tool_rel is not None else self.gb,
                                 v6, 0)
        v = float(np.linalg.norm(v6[3:]))
        if v > self.tcp_speed_max:
            self.tcp_speed_max = v

    def pad_contact_force(self):
        """Total normal force on the pad face this step."""
        tot = 0.0
        f6 = np.zeros(6)
        for c in range(self.d.ncon):
            con = self.d.contact[c]
            if self.pad_face in (con.geom1, con.geom2):
                mujoco.mj_contactForce(self.m, self.d, c, f6)
                tot += abs(f6[0])
        return tot

    # ------------------------------------------------------- V5-D verification
    def _sync_triage_globals(self):
        """Point v5_triage's face-projection globals at THIS model.

        face_regions() reads module-level constants that load_scene() normally fills in.
        v5_clean builds its own model and never calls load_scene, so those constants would
        silently describe whatever was loaded last -- and being right by default is not the
        same as being right on purpose.
        """
        m, d = self.m, self.d
        g = m.geom("cab_body").id
        TR.CFG_CAB_XY = (float(d.geom_xpos[g][0]), float(d.geom_xpos[g][1]))
        TR.CAB_HALF_XY = (float(m.geom_size[g][0]), float(m.geom_size[g][1]))
        zs = [(d.geom_xpos[i][2] - m.geom_size[i][2], d.geom_xpos[i][2] + m.geom_size[i][2])
              for i in range(m.ngeom)
              if m.geom_bodyid[i] == self.cab_bodyid and m.geom_contype[i]]
        TR.CAB_BASE = float(min(a for a, _ in zs))
        TR.CAB_TOP = float(max(b for _, b in zs))

    def soil_face(self, g):
        """Which face a soil geom sits on, in the cabinet's own frame."""
        cab = self.cab_bodyid
        p0 = self.d.xpos[cab]
        R0 = self.d.xmat[cab].reshape(3, 3)
        x, y, z = R0.T @ (self.d.geom_xpos[g] - p0)
        hd, hw = self.m.geom_size[self.m.geom("cab_body").id][:2]
        if z > 2 * self.m.geom_size[self.m.geom("cab_body").id][2] - 0.02:
            return "top"
        if x < -hd + 0.02:
            return "front"
        if x > hd + 0.01:
            return "back"
        return "left" if y < 0 else "right"

    def verify(self):
        """Re-inspect the unit THIS cycle just cleaned. Returns residual soil seen.

        Deliberately NOT a fresh spawn: it renders the live model, so the geoms it looks
        for are the same ones the wipe hid. And it reuses v5_triage's own `face_regions`
        and `image_features` rather than a second implementation, so the verifier and the
        grader cannot drift apart.

        WHAT IT CANNOT SEE, AND THIS IS THE V5-D RESULT: the station camera sits at
        z = 0.400 and the device's top face is at z = 0.450, so the camera is BELOW that
        plane -- cos(top normal, view) = +0.076 -- and `face_regions` returns the four
        VERTICAL faces only. The cleaning station wipes five faces and counts all five in
        its coverage number. So soil left on the TOP is structurally invisible here. That
        is reported per unit rather than hidden, and the sabotage test measures it.
        """
        m, d, cfg = self.m, self.d, self.cfg
        self._sync_triage_globals()
        if self.rend is None:
            self.rend = mujoco.Renderer(m, TR.CFG.cam_h, TR.CFG.cam_w)
        tt = m.jnt_qposadr[m.joint("tt_rot").id]
        # park the arm clear of frame -- v5_check_spec asserts this pose is 0.000% of the
        # inspect view, against 4.28% at the home pose
        d.qpos[self.qadr] = TR.PARK
        best = {}
        for deg in TR.CFG.index_deg:
            d.qpos[tt] = np.deg2rad(deg)
            mujoco.mj_forward(m, d)
            self.rend.update_scene(d, camera=TR.CFG.cam)
            rgb = self.rend.render()
            # grade each face ONCE, in the index position where it is most face-on --
            # the same rule triage uses, so a face seen twice is not counted twice
            for fid, cosang, roi in TR.face_regions(m, d, TR.CFG, deg):
                if fid in best and best[fid][0] <= cosang:
                    continue
                f = TR.image_features(rgb, roi, TR.CFG)
                if f is not None:
                    best[fid] = (cosang, f)
        # --- THE TOP FACE, from its own camera. Without this the check is blind exactly
        #     where the cleaning fails: the first falsification run caught 10/10 sabotaged
        #     units and still let 9 of 10 honestly-cleaned-but-dirty units pass, because
        #     100% of the residue sat on the one face `inspect` cannot see.
        top_f = None
        if self.rend_top is None:
            self.rend_top = mujoco.Renderer(m, TR.CFG.cam_h, TR.CFG.cam_w)
        d.qpos[tt] = 0.0
        mujoco.mj_forward(m, d)
        self.rend_top.update_scene(d, camera="verify_top")
        rgb = self.rend_top.render()
        roi = self.top_region()
        if roi is not None:
            top_f = TR.image_features(rgb, roi, TR.CFG)

        seen = sum(f["soil"] for _, f in best.values())
        seen_top = int(top_f["soil"]) if top_f else 0
        seen += seen_top
        left = [g for g in self.revealed_soil if m.geom_rgba[g][3] > 0]
        hidden_top = sum(1 for g in left if self.soil_face(g) == "top")
        return {"soil_seen": int(seen), "soil_seen_top": seen_top,
                "faces_graded": len(best) + (1 if top_f else 0),
                "top_graded": bool(top_f is not None),
                "soil_left_truth": len(left), "soil_left_top": int(hidden_top),
                "verified": bool(seen <= cfg.verify_soil_max)}

    def top_region(self):
        """Search region for the TOP face, projected from the verify_top camera.

        Same projection and same hull-mask format as v5_triage.face_regions, deliberately,
        so image_features can be reused unchanged -- one feature extractor for every face
        of both stations. Built here rather than inside face_regions because V5-B's triage
        result is frozen at 97.5% and must not move: the triage station grades the four
        vertical faces from `inspect`, and this is the CLEANING station's extra eye.
        """
        m, d = self.m, self.d
        cam = m.camera("verify_top").id
        p = d.cam_xpos[cam]
        R = d.cam_xmat[cam].reshape(3, 3)
        f = (TR.CFG.cam_h / 2) / np.tan(np.deg2rad(m.cam_fovy[cam]) / 2)
        cg = m.geom("cab_body").id
        cx, cy = float(d.geom_xpos[cg][0]), float(d.geom_xpos[cg][1])
        hd, hw = float(m.geom_size[cg][0]), float(m.geom_size[cg][1])
        z = TR.CAB_TOP
        ins = TR.CFG.face_inset
        quad = [(cx - hd + ins, cy - hw + ins), (cx + hd - ins, cy - hw + ins),
                (cx + hd - ins, cy + hw - ins), (cx - hd + ins, cy + hw - ins)]
        uv = []
        for X in [np.array([qx, qy, z]) for qx, qy in quad]:
            q = R.T @ (X - p)
            depth = -q[2]
            if depth < 1e-3:
                return None
            uv.append((TR.CFG.cam_w / 2 + f * q[0] / depth,
                       TR.CFG.cam_h / 2 - f * q[1] / depth))
        uv = np.array(uv)
        u0 = max(0, int(uv[:, 0].min()) - 2)
        u1 = min(TR.CFG.cam_w, int(uv[:, 0].max()) + 2)
        v0 = max(0, int(uv[:, 1].min()) - 2)
        v1 = min(TR.CFG.cam_h, int(uv[:, 1].max()) + 2)
        if u1 - u0 < 40 or v1 - v0 < 40:
            return None
        H = TR._hull(uv)
        gy, gx = np.mgrid[v0:v1, u0:u1]
        inside = np.ones(gx.shape, bool)
        for i in range(len(H)):
            a, b = H[i], H[(i + 1) % len(H)]
            inside &= ((b[0] - a[0]) * (gy - a[1])
                       - (b[1] - a[1]) * (gx - a[0])) >= 0
        return (v0, v1, u0, u1, inside)

    def wipe(self):
        """Hide soil geoms the pad's contact patch has passed over.

        Removal requires ACTUAL CONTACT, not proximity: if the pad is not pressing, it
        cleans nothing. That is what makes the coverage number a statement about the
        motion rather than about the trajectory we happened to command.
        """
        f = self.pad_contact_force()
        if f < self.cfg.contact_min_n:
            return 0
        if self.sabotage:
            return 0                # V5-D: contact happened, removal deliberately withheld
        centre = self.d.geom_xpos[self.pad_face]
        R = self.d.geom_xmat[self.pad_face].reshape(3, 3)
        n_hat = R[:, 2]                       # pad's own face normal
        n = 0
        for g in self.revealed_soil:
            if self.m.geom_rgba[g][3] <= 0:
                continue
            v = self.d.geom_xpos[g] - centre
            # IN-PLANE distance, not 3D. The pad is a flat 60 mm square and its geom
            # CENTRE sits half a thickness behind the contact surface, so a 3D distance
            # spends part of the wipe radius on that offset -- measured, the closest
            # approach came out 33.8 mm against a 34 mm radius, i.e. cleaning succeeded
            # or failed on rounding. Contact is already required separately by the force
            # test above, so the only question left is lateral reach.
            out = float(v @ n_hat)
            inplane = float(np.linalg.norm(v - out * n_hat))
            if inplane < self.cfg.pad_radius and abs(out) < self.cfg.pad_reach:
                self.m.geom_rgba[g][3] = 0.0
                n += 1
        return n

    # ------------------------------------------------------------- planning
    def plan_pose(self, tgt, base_mat, q_seed=None):
        """Smallest-tilt joint solution that is reachable, limit-clear and NOT colliding.

        WHY THIS EXISTS. The cleaner used to servo straight at a Cartesian target with a
        resolved-rate step and no notion of collision. Measured consequence: link1 jammed
        against link6 at 130-271 N with joint 4 pinned at its 30 Nm limit, and every
        setup waypoint missed by 100-400 mm -- the whole raster then ran from the wrong
        place. A local Jacobian step cannot climb out of a self-collision basin because
        nothing in it knows the basin is there. Solve first, reject the bad branches,
        then drive to a configuration already known to be good.

        Returns (q, mat, tilt_deg) or None.
        """
        for mat, tilt in tilted_mats(base_mat):
            q = self.solve_at(tgt, mat, q_seed)
            if q is not None:
                return q, mat, tilt
        return None

    def plan_pad(self, pad_pt, base_mat, pad_rel, q_seed=None):
        """Same, but for a raster point where PAD_PT is what must be hit, not the TCP.

        The tilt loop has to live out here: the pad hangs 105 mm off the wrist, so
        tilting the tool SWINGS THE TARGET. Solving a fixed TCP target and then tilting
        would land the pad somewhere else on the face -- which is the whole reason the
        tool's length matters to this station in the first place.

        AND IT PREFERS THE SOLUTION NEAREST THE PREVIOUS ONE. A 7-DoF arm has many
        configurations for the same pose, and taking the first one found let adjacent
        raster points 27 mm apart land in different branches: measured 5.78 rad of joint
        motion for a 37 mm step on the top face, 32 of 90 points above 0.5 rad on face 90.
        The executor interpolates at the arm's rate limit on a 2.5 s budget, so a jump
        cannot complete -- and on the way it sweeps the pad in a wide arc across the
        device, which is why the pad was measured 257 mm off target and 37 mm past the
        face edge. Face 180 had ZERO jumps and was the only pass that behaved.

        Smallest tilt still wins whenever continuity is acceptable, so the reported tilt
        stays honest; only when the nearest-in-tilt answer would tear the arm across its
        workspace does it keep looking for a closer one.
        """
        best = None
        for mat, tilt in tilted_mats(base_mat):
            tgt = pad_pt - mat @ pad_rel
            q = self.solve_at(tgt, mat, q_seed)
            if q is None:
                continue
            jump = 0.0 if q_seed is None else float(np.max(np.abs(q - q_seed)))
            if jump <= self.cfg.max_joint_jump:
                return q, mat, tilt, tgt
            if best is None or jump < best[0]:
                best = (jump, q, mat, tilt, tgt)
        if best is None:
            return None
        # REFUSE the point rather than execute a branch jump. The remaining >60 N contact
        # excursions were on exactly the two passes that still had jumps, and a jump drags
        # the pad across the device -- which is what generates them. Skipping is honest and
        # is counted; smashing the pad through a region where our own contact model is not
        # valid is not. The pad's force/penetration curve is monotonic to 60 N and blows up
        # above it (2.19 mm at 60 N, 20.25 mm at 80 N, non-monotonic thereafter), so 60 N
        # is a MODEL-VALIDITY ceiling and the cycle must stay under it by construction.
        if best[0] > self.cfg.hard_joint_jump:
            return None
        return best[1], best[2], best[3], best[4]

    def _carry_tool(self):
        """Put the welded tool where the arm would actually carry it, in the PLAN copy.

        The padtool is a free body held by an equality, so moving arm joints in a copy of
        the state leaves it behind -- its pose there is whatever the live sim last had.
        The first version of the planner therefore EXCLUDED the tool from its collision
        test, which made it blind to the one part of the machine that touches anything:
        it planned bottom-row poses whose 60 mm pad reached below the platter (measured
        pad z down to 1 mm against a platter top of 10 mm, with tt_disc and bench in the
        contact list), and top-face poses the pad could not physically reach. Result:
        0 of 48 top points and only 40% of front-face points ever arrived -- each one
        pressing at full command for the whole 2.5 s timeout, which is where the 326 N
        peak and the 74.8% in-band came from.

        Reconstructing the weld transform is exact and costs one quaternion multiply.
        The flange is set to its FREE extension, which is the conservative end: that is
        the longest the tool can be, so anything that clears here clears in practice.
        """
        if self.tool_rel is None:
            return
        relpos, relq = self.tool_rel
        mujoco.mj_kinematics(self.m, self.plan)
        p1 = self.plan.xpos[self.gb]
        R1 = self.plan.xmat[self.gb].reshape(3, 3)
        q1 = np.zeros(4)
        mujoco.mju_mat2Quat(q1, R1.flatten())
        qt = np.zeros(4)
        mujoco.mju_mulQuat(qt, q1, relq)
        self.plan.qpos[self.pad_jq:self.pad_jq + 3] = p1 + R1 @ relpos
        self.plan.qpos[self.pad_jq + 3:self.pad_jq + 7] = qt
        self.plan.qpos[self.acf_q] = self.m.jnt_range[self.m.joint("acf").id][0]

    def solve_at(self, tgt, mat, q_seed=None):
        """One pose, one orientation: reachable AND limit-clear AND collision-free."""
        m = self.m
        lo, hi = self.rng_j[:, 0], self.rng_j[:, 1]
        seeds = [q_seed, COLD] if q_seed is not None else [COLD]
        for q0 in seeds:
            q = np.array(q0, float)
            for _ in range(PLAN_ITERS):
                self.plan.qpos[:] = self.d.qpos
                self.plan.qpos[self.qadr] = q
                mujoco.mj_kinematics(m, self.plan)
                mujoco.mj_comPos(m, self.plan)
                dq, _ = ik_step(m, self.plan, self.site, tgt, mat, self.dof,
                                damping=self.cfg.arm.ik_damping,
                                gain=self.cfg.arm.ik_gain)
                step = np.max(np.abs(dq))
                if step > 0.12:
                    dq = dq * (0.12 / step)
                q = np.clip(q + dq, lo, hi)
                if step < 1e-5:
                    break
            self.plan.qpos[:] = self.d.qpos
            self.plan.qpos[self.qadr] = q
            self._carry_tool()
            mujoco.mj_forward(m, self.plan)
            if np.linalg.norm(tgt - self.plan.site_xpos[self.site]) > POS_TOL:
                continue
            R = self.plan.site_xmat[self.site].reshape(3, 3)
            quat, rv = np.zeros(4), np.zeros(3)
            mujoco.mju_mat2Quat(quat, (mat @ R.T).flatten())
            mujoco.mju_quat2Vel(rv, quat, 1.0)
            if np.linalg.norm(rv) > ROT_TOL:
                continue
            if np.min(np.minimum(q - lo, hi - q)) < np.deg2rad(1.0):
                continue
            # THE ARM may touch nothing. THE PAD may touch the device and nothing else --
            # pad-on-device IS the motion, pad-on-platter is the bug that made the
            # bottom rows stall. Anything else (bench, platter, riser, backdrop, post) is
            # a rejection for either.
            hit = False
            for k in range(self.plan.ncon):
                g1, g2 = self.plan.contact[k].geom1, self.plan.contact[k].geom2
                tool = (g1 in self.tool_geoms) or (g2 in self.tool_geoms)
                arm = (g1 in self.arm_geoms) or (g2 in self.arm_geoms)
                if tool and not arm:
                    other = g2 if g1 in self.tool_geoms else g1
                    if self.m.geom_bodyid[other] == self.cab_bodyid:
                        continue                 # the wipe itself
                    hit = True
                    break
                if arm:
                    hit = True
                    break
            if hit:
                continue
            return q
        return None

    # ---------------------------------------------------------------- motion
    def _charge(self, tag, secs):
        """Bill simulated seconds to a phase tag. No-op unless --budget is on."""
        if self.budget is not None:
            b = self.budget
            b["t"][tag] = b["t"].get(tag, 0.0) + secs
            b["n"][tag] = b["n"].get(tag, 0) + 1

    def step_to(self, tgt, mat, grip, index_deg=0.0, frames=None, tag=""):
        """One control step toward a Cartesian target. Returns TCP position error."""
        m, d = self.m, self.d
        self.ik.qpos[:] = d.qpos
        self.ik.qpos[self.qadr] = self.q_des
        mujoco.mj_kinematics(m, self.ik)
        mujoco.mj_comPos(m, self.ik)
        self._charge(tag, self.dt)
        dq, err = ik_step(m, self.ik, self.site, tgt, mat, self.dof)
        mx = np.max(np.abs(dq))
        lim = self.cfg.arm.joint_rate * self.cfg.speed
        if mx > lim:
            dq *= lim / mx
        self._advance(self.q_des + dq)
        d.ctrl[self.act] = self.q_des
        d.ctrl[self.grip] = grip
        d.ctrl[self.tt_act] = np.deg2rad(index_deg)
        d.qfrc_applied[self.dof] = d.qfrc_bias[self.dof]
        mujoco.mj_step(m, d)
        self._tcp_tick()
        return err

    def move(self, tgt, mat, grip, index_deg=0.0, tol=0.004, t_max=6.0,
             wipe=False, log=None, frames=None, tag=""):
        """Drive to a Cartesian target and WAIT FOR THE ARM TO ACTUALLY GET THERE.

        The completion test is on the MEASURED TCP, not on the commanded configuration.
        The first version broke as soon as the IK's own error went under tolerance --
        which happens in ~0.4 s, while the physical arm is still up to 0.9 rad behind and
        147 mm away from the target. Every downstream phase then started from the wrong
        place, and the pad was never picked up. This is the same class of mistake as
        v2's original oscillation, in reverse: there we listened to the measured state
        when we should have planned on the commanded one; here we judged completion on
        the commanded one when only the measured one means anything.
        """
        t = 0.0
        cleaned = 0
        settle = 0.0
        while t < t_max:
            self.step_to(tgt, mat, grip, index_deg, frames, tag)
            t += self.dt
            if wipe:
                cleaned += self.wipe()
                if log is not None:
                    log.append(self.pad_contact_force())
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    int(t / self.dt) % frames["every"] == 0:
                frames["cb"](tag)
            reached = float(np.linalg.norm(self.d.site_xpos[self.site] - tgt))
            if reached < tol:
                settle += self.dt
                if settle >= 0.06:
                    break
            else:
                settle = 0.0
        return cleaned

    def move_planned(self, q_goal, tgt, grip, index_deg=0.0, tol=0.004, t_max=6.0,
                     wipe=False, log=None, frames=None, tag="", rate_scale=1.0):
        """Drive to a PLANNED joint configuration, waiting for the MEASURED TCP.

        The setpoint is the planner's configuration, so the arm is not re-deriving a
        branch every control step and cannot wander into one the planner already
        rejected. Completion is still judged on the measured TCP -- the commanded
        configuration says nothing about whether the arm got there, which is exactly the
        distinction that took four bugs to untangle.
        """
        m, d = self.m, self.d
        t, cleaned, settle = 0.0, 0, 0.0
        stall_t, stall_err = 0.0, np.inf
        while t < t_max:
            dq = q_goal - self.q_des
            mx = np.max(np.abs(dq))
            # rate_scale defaults to 1.0, so every existing caller is unchanged. It
            # exists so a stroke can APPROACH CONTACT GENTLY AND SWEEP FAST -- see
            # stroke_seat_scale. Those are different motions and V6's feed sweep
            # conflated them.
            lim = self.cfg.arm.joint_rate * self.cfg.speed * rate_scale
            if mx > lim:
                dq = dq * (lim / mx)
            self._advance(self.q_des + dq)
            d.ctrl[self.act] = self.q_des
            d.ctrl[self.grip] = grip
            d.ctrl[self.tt_act] = np.deg2rad(index_deg)
            d.qfrc_applied[self.dof] = d.qfrc_bias[self.dof]
            mujoco.mj_step(m, d)
            self._tcp_tick()
            t += self.dt
            if wipe:
                cleaned += self.wipe()
                f = self.pad_contact_force()
                if log is not None:
                    log.append(f)
                stall_t += self.dt
                if stall_t >= self.cfg.wipe_stall_s:
                    e = float(np.linalg.norm(d.site_xpos[self.site] - tgt))
                    if f >= self.cfg.wipe_seat_n and \
                            stall_err - e < self.cfg.wipe_stall_m:
                        break
                    stall_err, stall_t = e, 0.0
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    int(t / self.dt) % frames["every"] == 0:
                frames["cb"](tag)
            if float(np.linalg.norm(d.site_xpos[self.site] - tgt)) < tol:
                settle += self.dt
                if settle >= 0.06:
                    break
            else:
                settle = 0.0
        if self.budget is not None:
            self._charge(tag, t)
            self.budget["dur"].setdefault(tag, []).append(t)
            if t >= t_max - 1e-9:
                self.budget["timeout"][tag] = self.budget["timeout"].get(tag, 0) + 1
        return cleaned

    # ------------------------------------------------- V7: continuous stroke
    def plan_runs(self, pad_pts, base_mat, pad_rel, q_seed, gap_m):
        """Plan a whole face's path up front; split it into CONTIGUOUS RUNS.

        Returns [[(q, tgt, mat, tilt), ...], ...]. A run is a stretch the pad can sweep
        without lifting: consecutive knots that are both feasible AND adjacent on the
        path. A knot the planner refuses (branch jump, collision, limit) ENDS the run
        rather than being bridged, because bridging it is precisely the swing that
        `plan_pad` refuses to execute in point mode -- and doing it while the flange is
        loaded drags the pad across the device instead of merely wasting a point.

        PLANNING THE FACE BEFORE TOUCHING IT is the one real behavioural difference
        from point mode, and it has a cost worth naming: point mode re-probes the
        surface after every point, so it tracks a device that shifts under the pad,
        while a stroke commits to a surface measured before the run started. That is
        why `device_shift_mm` is measured and reported -- if the device moved more than
        the flange can absorb, this assumption is the first thing to suspect.
        """
        runs, cur, q = [], [], q_seed
        prev_pt = None
        for pt, contiguous in pad_pts:
            self.raster_planned += 1
            got = self.plan_pad(pt, base_mat, pad_rel, q)
            if got is None:
                self.raster_infeasible += 1
                if cur:
                    runs.append(cur)
                cur, prev_pt = [], None
                continue
            q_pt, mat_pt, tilt_pt, tgt = got
            far = prev_pt is not None and float(np.linalg.norm(pt - prev_pt)) > gap_m
            if cur and (not contiguous or far):
                runs.append(cur)
                cur = []
            q = q_pt
            self.q_warm = q_pt
            self.tilts.append(tilt_pt)
            cur.append((q_pt, tgt, mat_pt, tilt_pt, pt))
            prev_pt = pt
        if cur:
            runs.append(cur)
        return runs

    @staticmethod
    def _corners(P, sharp_deg=25.0):
        """Per-knot turn angle, and which knots are CORNERS rather than path curvature.

        MEASURED, not assumed. A serpentine's row reversal is not a gentle bend: on the
        front face 17 of 58 knots turn by more than 60 degrees and the worst is 120.5.
        Treating those as ordinary interpolation points is what produced an 8-10 mm bow
        in PURE GEOMETRY, before any dynamics -- the spline rounds the corner off the
        face and the pad never sweeps it.
        """
        n = len(P)
        turn = np.zeros(n)
        for i in range(1, n - 1):
            a, b = P[i] - P[i - 1], P[i + 1] - P[i]
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            if na < 1e-9 or nb < 1e-9:
                turn[i] = 180.0
                continue
            turn[i] = float(np.degrees(np.arccos(np.clip(a @ b / (na * nb), -1.0, 1.0))))
        return turn, turn > sharp_deg

    @staticmethod
    def _vel_plan(s_knot, P, sharp, feed, accel):
        """Per-knot speed caps, then a two-pass look-ahead. Standard CNC, for the
        standard reason.

        A single trapezoid over the whole run ramps in and out at the ENDS and then
        drives every interior corner at full feed. The arm cannot turn 120 degrees at
        150 mm/s, so it cuts the corner -- and a cut corner on a wiping path is an
        uncleaned corner. The cap is the component of velocity that SURVIVES the turn,
        cos(phi): straight ahead keeps all of it, a right angle keeps none.

        The two passes make the caps reachable: backward asks "can I still slow to that
        cap in the distance remaining", forward asks "can I have sped up that much by
        then". Without them the profile is a wish rather than a plan.
        """
        n = len(P)
        seg = np.diff(s_knot)
        v = np.full(n, float(feed))
        v[0] = v[-1] = 0.0
        for i in range(1, n - 1):
            a, b = P[i] - P[i - 1], P[i + 1] - P[i]
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            if na < 1e-9 or nb < 1e-9:
                v[i] = 0.0
                continue
            c = float(np.clip(a @ b / (na * nb), -1.0, 1.0))
            # Floor at 8% rather than 0. A true stop at every row reversal is both slow
            # and unnecessary -- the corner only has to be slow enough that the arm's
            # lag through it stays inside what the flange absorbs.
            v[i] = feed * max(0.08, c) if sharp[i] else feed * max(0.5, c)
        for i in range(n - 2, -1, -1):
            v[i] = min(v[i], float(np.sqrt(v[i + 1] ** 2 + 2 * accel * seg[i])))
        for i in range(n - 1):
            v[i + 1] = min(v[i + 1], float(np.sqrt(v[i] ** 2 + 2 * accel * seg[i])))
        return v

    @staticmethod
    def _catmull(Q, s_knot, s, sharp=None):
        """Joint vector at arc length S, Catmull-Rom through the planned knots.

        WHY A SPLINE AND NOT A POLYLINE. Linear interpolation between knots is C0: the
        commanded joint VELOCITY steps discontinuously at every knot, which is the same
        pecking signature one level down -- the rate limiter turns each step into a
        lag the loaded pad drags through. Catmull-Rom is C1 and, crucially, INTERPOLATES
        its control points, so the path still passes exactly through every configuration
        the planner checked for collisions and limits. A B-spline would smooth better
        and pass through none of them; that trade is not available here, because a
        posture that was never collision-checked is a posture that may be inside the
        cabinet.

        Between knots the curve can bow slightly off the straight Cartesian row. That
        bow is measured, not assumed -- see stroke_path_error_mm in the run row -- and
        it is absorbed by the flange, which is a spring, at 800 N/m per mm.
        """
        n = len(Q)
        i = int(np.searchsorted(s_knot, s, side="right") - 1)
        i = max(0, min(i, n - 2))
        span = s_knot[i + 1] - s_knot[i]
        t = 0.0 if span <= 1e-12 else float((s - s_knot[i]) / span)
        t = min(max(t, 0.0), 1.0)
        p1, p2 = Q[i], Q[i + 1]
        # ONE-SIDED TANGENTS AT A CORNER. Collapsing the outside control point onto the
        # corner knot zeroes the tangent there, so the curve arrives and leaves along
        # the actual path instead of blending across the turn. This is what removes the
        # geometric bow; the velocity plan then removes the dynamic one.
        p0 = p1 if (sharp is not None and sharp[i]) else Q[max(i - 1, 0)]
        p3 = p2 if (sharp is not None and sharp[i + 1]) else Q[min(i + 2, n - 1)]
        t2, t3 = t * t, t * t * t
        return 0.5 * ((2 * p1) + (-p0 + p2) * t
                      + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                      + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)

    def stroke_run(self, run, grip, index_deg=0.0, frames=None, tag="", log=None):
        """Seat once, then SWEEP the whole run without stopping.

        The feed rate is specified on the PAD ALONG THE SURFACE and converted to a path
        parameter here, so it is an arm-independent statement about the process. The
        actuator rate limit is still honoured exactly: when a step would demand more
        joint travel than the arm may command, the ARC ADVANCE is scaled back rather
        than the setpoint being clipped. Clipping the setpoint instead would let the
        commanded path fall progressively behind the parameter -- the executor would
        believe it had swept ground it never reached, which is the failure mode that
        makes a coverage number a fiction.
        """
        cfg = self.cfg
        m, d = self.m, self.d
        if len(run) == 1:
            return self.move_planned(run[0][0], run[0][1], grip, index_deg=index_deg,
                                     tol=cfg.wipe_tol, t_max=3.5, wipe=True, log=log,
                                     tag=tag, frames=frames,
                                     rate_scale=cfg.stroke_seat_scale)
        # 1) SEAT. Entering contact is unchanged from point mode -- same planned pose,
        #    same stall criterion -- so the press that starts a stroke is the press this
        #    station has always measured. Only what happens AFTER contact is new.
        cleaned = self.move_planned(run[0][0], run[0][1], grip, index_deg=index_deg,
                                    tol=cfg.wipe_tol, t_max=3.5, wipe=True, log=log,
                                    tag=tag, frames=frames,
                                    rate_scale=cfg.stroke_seat_scale)
        Q = np.array([k[0] for k in run], float)
        T = np.array([k[1] for k in run], float)          # TCP targets (what IK solved)
        # THE TOOLPATH IS THE PAD'S, NOT THE WRIST'S. Every knot picks its own tilt out
        # of a DISCRETE set, and the pad hangs 105 mm off the wrist, so a one-step change
        # of tilt swings the TCP by centimetres while the pad slides smoothly along the
        # face. Measured on the front face: parametrising by TCP arc length flagged 195
        # of 304 knots as >25 deg "corners" and reported 20 mm of path error, all of it
        # an artefact of reading the wrong frame. Feed rate, corner detection and path
        # error are all statements about the PAD ON THE SURFACE.
        P = np.array([k[4] for k in run], float)          # pad points -- the real path
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        s_knot = np.concatenate([[0.0], np.cumsum(seg)])
        L = float(s_knot[-1])
        if L < 1e-6:
            return cleaned
        lim = cfg.arm.joint_rate * cfg.speed
        a = cfg.stroke_accel
        turn, sharp = self._corners(P, cfg.stroke_corner_deg)
        v_knot = self._vel_plan(s_knot, P, sharp, cfg.stroke_feed, a)
        N = np.array([k[2][:, 2] for k in run], float)   # surface normal at each knot
        v_min = 0.02 * cfg.stroke_feed
        s, t = 0.0, 0.0
        t_max = 3.0 + 4.0 * L / max(cfg.stroke_feed, 1e-6)
        err_max, lag_max, nrm_max = 0.0, 0.0, 0.0
        while s < L and t < t_max:
            # LOOK-AHEAD profile: accelerate away from the last knot's cap, and stay
            # slow enough to still meet the next one's. sqrt(v^2 + 2 a d) is the fastest
            # speed reachable over d, and equally the fastest that can be given back.
            i_v = int(np.searchsorted(s_knot, s, side="right") - 1)
            i_v = max(0, min(i_v, len(P) - 2))
            v = min(cfg.stroke_feed,
                    np.sqrt(v_knot[i_v] ** 2 + 2 * a * max(s - s_knot[i_v], 0.0)),
                    np.sqrt(v_knot[i_v + 1] ** 2 + 2 * a * max(s_knot[i_v + 1] - s, 0.0)))
            v = max(v, v_min)
            ds = v * self.dt
            q_try = self._catmull(Q, s_knot, s + ds, sharp)
            dq = q_try - self.q_des
            mx = float(np.max(np.abs(dq)))
            if mx > lim:
                # back the ARC off, not the setpoint: the path stays exact and only the
                # speed gives way. One proportional pass is enough -- the map from arc
                # length to joint travel is locally linear at these spacings.
                ds *= lim / mx
                q_try = self._catmull(Q, s_knot, s + ds, sharp)
                dq = q_try - self.q_des
                mx = float(np.max(np.abs(dq)))
                if mx > lim:
                    dq *= lim / mx
                    q_try = self.q_des + dq
            s += ds
            self._advance(q_try)
            d.ctrl[self.act] = self.q_des
            d.ctrl[self.grip] = grip
            d.ctrl[self.tt_act] = np.deg2rad(index_deg)
            d.qfrc_applied[self.dof] = d.qfrc_bias[self.dof]
            mujoco.mj_step(m, d)
            self._tcp_tick()
            t += self.dt
            cleaned += self.wipe()
            if log is not None:
                log.append(self.pad_contact_force())
            # PERPENDICULAR deviation from the commanded path, not distance to the
            # nearest knot. The first version measured the latter and read 40 mm, almost
            # all of which was the 36 mm segment length plus the arm's along-path lag --
            # neither of which is an error. Lag ALONG the path costs nothing (the pad
            # sweeps the same ground, later); departure ACROSS it is what lifts the pad
            # off the surface, and it is the only one the flange has to absorb.
            k = int(np.searchsorted(s_knot, s, side="right") - 1)
            k = max(0, min(k, len(P) - 2))
            # DECOMPOSE ABOUT THE SEGMENT THE PAD IS ACTUALLY ON, not the one the
            # setpoint has reached. The flange compresses along the TOOL axis, and the
            # tool tilts by up to 30 deg and changes tilt at ~30% of knots, so using the
            # setpoint knot's normal leaks up to `flange x sin(delta tilt)` of pure
            # flange travel into the "in-plane" number. That is what made this metric
            # read 20.5 mm while the pad was in fact tracking the path to 0.01 mm.
            # +-8 segments covers far more lag than the arm ever shows and still cannot
            # snap to a neighbouring row, which sits a full row pitch away.
            tcp_now = d.geom_xpos[self.pad_face]
            dev, dvec, kbest = np.inf, None, k
            for kk in range(max(k - 8, 0), min(k + 9, len(P) - 1)):
                ab = P[kk + 1] - P[kk]
                den = float(ab @ ab)
                u_ = 0.0 if den < 1e-12 else float(np.clip((tcp_now - P[kk]) @ ab / den,
                                                           0.0, 1.0))
                w = tcp_now - (P[kk] + u_ * ab)
                if float(np.linalg.norm(w)) < dev:
                    dev, dvec, kbest = float(np.linalg.norm(w)), w, kk
            # SPLIT IT, AND ONLY ONE HALF IS AN ERROR.
            #   IN-PLANE  -- did the pad sweep the ground it claims to? This is the
            #                coverage number, and distance to the POLYLINE (not to a
            #                knot) already excludes along-path lag, which costs nothing.
            #   NORMAL    -- this is the ACTIVE CONTACT FLANGE COMPRESSING. It is
            #                supposed to be about `press` (12 mm) and reporting it as
            #                "path error" made a working spring look like a defect --
            #                exactly the mistake the coupling-drift metric already
            #                documents one object further in. The normal direction is
            #                spoken for by the FORCE band, which is measured.
            if dvec is not None:
                nof = float(dvec @ N[kbest])
                ipl = float(np.linalg.norm(dvec - nof * N[kbest]))
            else:
                nof, ipl = 0.0, dev
            err_max = max(err_max, ipl)
            nrm_max = max(nrm_max, abs(nof))
            lag_max = max(lag_max, dev)
            self.stroke_track.append(ipl)
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    int(t / self.dt) % frames["every"] == 0:
                frames["cb"](tag)
        # 2) CATCH-UP at the far end. The setpoint reaches the last knot before the
        #    physical arm does; without this the final knot of every run is swept by a
        #    pad that is still tens of mm behind it. Bounded, ONCE PER RUN rather than
        #    once per point -- which is the whole saving -- and it still wipes.
        hold = 0.0
        while hold < 0.30:
            dq = Q[-1] - self.q_des
            mx = float(np.max(np.abs(dq)))
            if mx > lim:
                dq *= lim / mx
            self._advance(self.q_des + dq)
            d.ctrl[self.act] = self.q_des
            d.ctrl[self.grip] = grip
            d.ctrl[self.tt_act] = np.deg2rad(index_deg)
            d.qfrc_applied[self.dof] = d.qfrc_bias[self.dof]
            mujoco.mj_step(m, d)
            self._tcp_tick()
            hold += self.dt
            t += self.dt
            cleaned += self.wipe()
            if log is not None:
                log.append(self.pad_contact_force())
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    int(t / self.dt) % frames["every"] == 0:
                frames["cb"](tag)
            if float(np.linalg.norm(d.site_xpos[self.site] - T[-1])) < cfg.wipe_tol:
                break
        self.stroke_path_err = max(self.stroke_path_err, err_max)
        self.stroke_lag = max(self.stroke_lag, lag_max)
        self.stroke_norm_err = max(self.stroke_norm_err, nrm_max)
        self.stroke_corners += int(sharp.sum())
        self.stroke_len += L
        self.stroke_runs += 1
        if self.budget is not None:
            self._charge(tag, t)
            self.budget["dur"].setdefault(tag, []).append(t)
        return cleaned

    def dwell(self, s, mat, tgt, grip, index_deg=0.0, frames=None, tag=""):
        """Hold station for S seconds -- AND KEEP FILMING.

        `step_to` takes a `frames` argument and has never used it, so every dwell stepped
        the simulation while capturing nothing: the 1.2 s indexer settles x4, the 1.4 s
        top index, the 0.3 s settles and the unlatch -- 8.45 s of simulated time with
        ZERO frames on a 137 s cycle. `make_realtime` then stretches the footage
        uniformly to match the true clock, so those gaps come back as ~9% duplicated
        frames smeared across the WHOLE clip. That is the judder: the arm appears to
        stutter during motion because time that elapsed while it was standing still was
        redistributed into the parts where it was moving.
        """
        t = 0.0
        while t < s:
            self.step_to(tgt, mat, grip, index_deg, frames, tag)
            t += self.dt
            if frames is not None and len(frames["f"]) < frames["max"] and \
                    int(t / self.dt) % frames["every"] == 0:
                frames["cb"](tag)

    def surface_x(self, y, z):
        """X of the device surface at (y, z), by casting a ray from in front of it.

        Exact where a plane fit is not: it sees whatever geom is actually presented at
        this point -- body, proud back panel, top cover ledge -- with no assumption about
        which face the indexer has brought round.

        RAYS ONLY THE CABINET'S OWN GEOMS, one at a time, and takes the nearest hit.
        The scene-wide `mj_ray` returns the FIRST geom along the beam, and the beam starts
        at x = 0.20 and travels +X -- straight through the space the arm and the pad
        occupy while wiping. Whenever a link was in the way the hit belonged to the arm,
        this returned None, and the raster loop silently `continue`d: no wipe, no force
        sample, no entry in the contact statistics. Measured on seed 800: 154 of 450
        raster points skipped (34.2%), the beam landing on xarm_gripper_base_link x61,
        link7 x33, link4 x26 and the pad itself x14. Because skipped points log nothing,
        the reported "contact during raster" was a fraction of the points that RAN --
        74.4% where the true figure over the planned raster was about 49%.

        Per-geom rays cannot be occluded by anything that is not the device, so the
        answer no longer depends on where the arm happens to be standing.
        """
        pnt = np.array([0.20, y, z])
        vec = np.array([1.0, 0.0, 0.0])
        best = -1.0
        for g in self.cab_geoms:
            d = mujoco.mju_rayGeom(self.d.geom_xpos[g], self.d.geom_xmat[g],
                                   self.m.geom_size[g], pnt, vec,
                                   int(self.m.geom_type[g]))
            if d >= 0 and (best < 0 or d < best):
                best = d
        if best < 0:
            return None
        return float(pnt[0] + best)

    # ---------------------------------------------------------------- geometry
    def front_face_plane(self, index_deg):
        """(x of the face now at the FRONT position, half-width in Y, z range).

        Read from the model at the commanded index angle, so it follows the device
        rather than assuming which face is presented.
        """
        m, d = self.m, self.d
        cab = m.body("cabinet").id
        cg = m.geom("cab_body").id
        cy = d.geom_xpos[cg][1]
        # THE PRESENTED SURFACE IS THE OUTERMOST GEOM, not the body's own face. The back
        # panel stands 10 mm proud of the body, so at index 180 a plane taken from
        # cab_body sits 10 mm INSIDE the panel -- and the raster then drove the pad 10 mm
        # into it. Measured: 1.2 M pad/back-panel contacts, 153 k of them above 100 N,
        # and a median force that did not respond to press depth at all because the press
        # was not what was causing it.
        xs, ys, zs = [], [], []
        for i in range(m.ngeom):
            if m.geom_bodyid[i] != cab or not m.geom_contype[i]:
                continue
            e = np.abs(d.geom_xmat[i].reshape(3, 3)) @ m.geom_size[i]
            p = d.geom_xpos[i]
            xs.append(p[0] - e[0])
            ys.append(e[1])
            zs.append((p[2] - e[2], p[2] + e[2]))
        z0, z1 = min(a for a, _ in zs), max(b for _, b in zs)
        return min(xs), cy, max(ys), z0, z1

    # ---------------------------------------------------------------- the cycle
    def run(self, seed, verbose=False, frames=None, reclean=False):  # noqa: C901
        cfg = self.cfg
        if reclean:
            # RE-CLEAN ROUND: keep the unit exactly as the last pass left it -- same
            # soil state, no respawn -- and sweep only what is still dirty. Entered via
            # run_with_backstop() when VERIFY still sees residue. A fresh entry gives
            # the planner a fresh branch, which is precisely what the stuck patches
            # need: their failure mode is a tilt the previous approach was locked into.
            truth, nd, ns, no = self._last_reset
            self.raster_planned = self.raster_skipped = self.raster_infeasible = 0
            self.tilts = []
            self.q_warm = None
            self.face_unreachable = {}
            self.stroke_len = 0.0
            self.stroke_runs = 0
            self.stroke_path_err = 0.0
            self.stroke_lag = 0.0
            self.stroke_norm_err = 0.0
            self.stroke_corners = 0
            self.stroke_track = []
            self.tcp_speed_max = 0.0
            self.joint_speed_max = 0.0
            self.device_shift = 0.0
            # DRIVE HOME FIRST. verify() parks the arm (teleport, camera clearance), and
            # entering the plan chain from PARK put the first face's corner points into
            # a tilt branch that presses edge-first -- the same patch failed every
            # reclean round while a fresh run cleaned it. Entry state is part of the
            # plan; make it the same one every fresh run has.
            mujoco.mj_forward(self.m, self.d)
            self.q_des = self.d.qpos[self.qadr].copy()
            t_h = 0.0
            while t_h < 3.0:
                dq = self.q_home - self.q_des
                mx = np.max(np.abs(dq))
                # was a hard-coded 0.02: an arm-specific literal the ArmProfile refactor
                # missed, so this one loop would have kept running at 10 rad/s after the
                # 2026-08-10 clamp. Grep for bare rate literals when changing the profile.
                _lim = self.cfg.arm.joint_rate
                if mx > _lim:
                    dq = dq * (_lim / mx)
                self._advance(self.q_des + dq)
                self.d.ctrl[self.act] = self.q_des
                self.d.qfrc_applied[self.dof] = self.d.qfrc_bias[self.dof]
                mujoco.mj_step(self.m, self.d)
                self._tcp_tick()
                t_h += self.dt
                if np.max(np.abs(self.d.qpos[self.qadr] - self.q_home)) < 0.02:
                    break
        else:
            truth, nd, ns, no = self.reset(seed)
            self._last_reset = (truth, nd, ns, no)
        n0 = len(self.revealed_soil)
        gm = grasp_mat()
        want = np.array(cfg.couple_tcp)

        # --- couple the tool changer
        self.move(want + np.array([0, 0, 0.12]), gm, cfg.grip_open, tag="APPROACH",
                  frames=frames)
        self.move(want, gm, cfg.grip_open, tol=0.003, t_max=8.0, tag="COUPLE",
                  frames=frames)
        latched, perr, aerr = self.couple()
        self.move(want + np.array([0, 0, 0.14]), gm, cfg.grip_open, t_max=8.0,
                  tag="LIFT", frames=frames)

        # MEASURE the coupled tool offset. Even with a positive coupling this is
        # measured rather than assumed -- the latch welds at the pose ACTUALLY achieved,
        # so whatever misalignment was inside the capture envelope is carried here.
        tcp = self.d.site_xpos[self.site]
        Rt = self.d.site_xmat[self.site].reshape(3, 3)
        self.pad_rel = Rt.T @ (self.d.geom_xpos[self.pad_face] - tcp)
        self.stem_rel = Rt.T @ (self.d.geom_xpos[self.stem] - tcp)

        if not latched:
            return {"seed": seed, "truth": truth, "picked": False, "coverage": 0.0,
                    "soil0": n0, "cleaned": 0, "missed": n0, "f_med": 0.0, "f_max": 0.0,
                    "in_band": 0.0, "contact_frac": 0.0,
                    "couple_mm": perr * 1000, "couple_deg": aerr}

        # --- wipe each face at the front working position
        forces, cleaned = [], 0
        # A SAFE WAYPOINT well clear of the device, in front of it and above the bench.
        # Everything indexes from here.
        safe = np.array([0.26, 0.0, 0.42])
        prev_deg = 0.0
        if cfg.targeted:
            self.targeted_skipped_faces = []
        for deg in cfg.faces_deg:
            # RETRACT CLEAR, THEN INDEX, THEN APPROACH -- in that order. Rotating the
            # device while the arm was still swinging back across it swept the tool
            # through the cabinet and knocked it out of the jaws: face 0 wiped correctly
            # and every face after it was "wiped" with an empty gripper, while the force
            # log kept reporting healthy contact. A real cell sequences it the same way,
            # for the same reason.
            pl = self.plan_pose(safe, tool_mat_face(deg), self.q_des)
            if pl is not None:
                self.move_planned(pl[0], safe, cfg.grip_open, index_deg=prev_deg,
                                  tol=0.006, t_max=8.0, tag="SAFE", frames=frames)
            # The fixed 1.2 s indexer dwell STAYS. An early-exit on measured angle
            # (|tt - deg| < 0.005 rad, min 0.15 s) saved ~4 s per unit and BROKE
            # COVERAGE: angle-arrived is not settled -- the device still carries a small
            # oscillation, and a corner patch (geom 33, front top-right) survived a FULL
            # raster that cleans it when the dwell is respected. 4 s is not worth a
            # missed patch; if this is ever revisited it needs an angular-VELOCITY
            # settle criterion, not an angle threshold.
            self.dwell(1.2, tool_mat_face(deg), safe, cfg.grip_open,
                       index_deg=deg, frames=frames, tag=f"INDEX {deg:.0f}")
            prev_deg = deg
            fx, cy, hw, z0, z1 = self.front_face_plane(deg)
            # GEOMETRIC soil selection: a patch is on the PRESENTED face iff, after this
            # rotation, it sits on the presented plane. Face names were tried first and
            # mis-mapped left/right, which filtered against the wrong list and missed
            # 1-4 patches per unit -- geometry cannot be wrong that way.
            if cfg.targeted:
                mujoco.mj_forward(self.m, self.d)
                _face_soil = [self.d.geom_xpos[g].copy() for g in self.revealed_soil
                              if self.m.geom_rgba[g][3] > 0
                              and abs(self.d.geom_xpos[g][0] - fx) < 0.03
                              and self.d.geom_xpos[g][2] < z1 - 0.005]
                if not _face_soil:
                    if __import__("os").environ.get("V6DBG"):
                        import numpy as _np
                        _tt = float(_np.rad2deg(self.d.qpos[self.tt_q]))
                        print(f"    [dbg] deg {deg}: SKIP, tt={_tt:.1f}, fx={fx:.4f}, "
                              f"z1={z1:.3f}; nearest dx of revealed:")
                        for g in self.revealed_soil:
                            if self.m.geom_rgba[g][3] > 0:
                                d_ = self.d.geom_xpos[g]
                                if abs(d_[0] - fx) < 0.1:
                                    print(f"          g{g} x{d_[0]:.4f} "
                                          f"dx{abs(d_[0]-fx)*1000:5.1f}mm z{d_[2]:.3f}")
                    self.targeted_skipped_faces.append(deg)
                    prev_deg = deg
                    continue
            tm = tool_mat_face(deg)
            zc, zh = (z0 + z1) / 2, (z1 - z0)
            # approach the face centre from clear
            # Approach on the LIFT-frame estimate, then RE-MEASURE once the wrist is
            # actually in the working orientation. The pad shifts in the jaws when the
            # tool rotates from pointing-down to pointing-horizontal -- gravity now pulls
            # it sideways across the grip instead of along it -- so an offset measured at
            # the lift is not the offset during the wipe. Measuring at the lift and using
            # it here put coverage at 0%.
            approach = np.array([fx - cfg.standoff, cy, zc]) - tm @ self.pad_rel
            pl = self.plan_pose(approach, tm, self.q_des)
            if pl is None:
                # RETRY, best seed first. The DEVICE rotates between faces, not the arm,
                # so every face's approach is nearly the same arm pose -- the previous
                # face's approach solution is the natural seed. Then home. In targeted
                # mode a sparse visit can end where no continuation exists, and without
                # a retry the WHOLE FACE was silently dropped with its patches.
                for _sq in ([getattr(self, "_last_q_ap")] if getattr(self, "_last_q_ap",
                            None) is not None else []) + [self.q_home]:
                    pl = self.plan_pose(approach, tm, _sq)
                    if pl is not None:
                        break
            if pl is None:
                self.face_unreachable[deg] = "approach"
                continue
            q_ap, mat_ap, _ = pl
            self._last_q_ap = q_ap.copy()
            # start each face from its OWN approach pose, not from wherever the previous
            # face's last raster point left the arm on the other side of the device
            self.q_warm = q_ap
            self.move_planned(q_ap, approach, cfg.grip_open, index_deg=deg,
                              tol=0.006, t_max=10.0, tag="TO FACE", frames=frames)
            self.dwell(0.3, mat_ap, approach, cfg.grip_open, index_deg=deg,
                       frames=frames, tag="SETTLE")
            tcp_n = self.d.site_xpos[self.site]
            Rn = self.d.site_xmat[self.site].reshape(3, 3)
            pad_rel = Rn.T @ (self.d.geom_xpos[self.pad_face] - tcp_n)
            # RASTER BOUNDS FROM THE FACE AND THE PAD, not a fixed fraction. The pad
            # CENTRE must stay inside the face by its own half-width, or the pad hangs
            # over the edge -- and at the bottom it hangs into the BENCH. Measured: with
            # a fixed +-0.44 span the bottom row drove the pad into the bench at raster
            # point 9 of 135, knocked the tool out of the jaws, and every later face was
            # "wiped" with an empty gripper while the metrics still logged contact.
            ph = cfg.pad_half
            v_lo = (z0 + ph + cfg.floor_margin) - zc
            v_hi = (z1 - ph) - zc
            u_lim = hw - ph
            step = cfg.step_frac * cfg.pad_radius
            # ROW pitch is a separate knob in stroke mode and the SAME one in point
            # mode: `row_frac` defaults to `step_frac`, so the shipped stroke config
            # rasters exactly the row geometry the published number was measured on.
            row_step = (cfg.row_frac * cfg.pad_radius) if cfg.stroke else step
            rows = max(int(np.ceil((v_hi - v_lo) / row_step)) + 1, 2)
            cols = max(int(np.ceil(2 * u_lim / step)) + 1, 2)
            # targeted: keep only points with soil within a pad radius (in-plane).
            # Grid spacing <= R*sqrt(2) guarantees every soil location is within R of
            # at least one grid point, so every patch keeps at least one visit.
            keep = None
            if cfg.targeted and not getattr(self, "_reclean_full", False):
                sp = _face_soil
                keep = set()
                # CONTIGUOUS ROW SEGMENTS, not scattered points. Scattered keeps broke
                # the serpentine's joint-space continuity -- the planner chained through
                # IK branches it never sees in full mode, one face became unplannable
                # and its patches were missed. Within a kept row, everything from the
                # first to the last soil-adjacent column is visited, so every executed
                # stroke is a pattern the full raster also executes.
                # +-1 ROW BAND around soil rows, columns widened by 1. Measured need,
                # not caution: at some face locations the smallest FEASIBLE tilt still
                # presses edge-first with the pad face ~30 mm off the patch (reach 22),
                # so the visit that actually cleans such a patch is a NEIGHBOURING one
                # whose tilted face sweeps it. Full coverage carries that diversity for
                # free; a sparse pass must keep the one-row band that provides it.
                _hits = {}
                for r_ in range(rows):
                    v_ = v_lo + (v_hi - v_lo) * r_ / (rows - 1)
                    for c_ in range(cols):
                        u_ = -u_lim + 2 * u_lim * c_ / (cols - 1)
                        for p_ in sp:
                            if np.hypot(p_[1] - (cy + u_), p_[2] - (zc + v_)) \
                                    <= cfg.pad_radius + cfg.target_margin:
                                _hits.setdefault(r_, []).append(c_); break
                for r_, cl_ in _hits.items():
                    lo_, hi_ = max(min(cl_) - 1, 0), min(max(cl_) + 1, cols - 1)
                    for rb in (r_ - 1, r_, r_ + 1):
                        if 0 <= rb < rows:
                            for c_ in range(lo_, hi_ + 1):
                                keep.add((rb, c_))
            if cfg.targeted and __import__("os").environ.get("V6DBG"):
                print(f"    [dbg] deg {deg}: soil_on_face {len(_face_soil)} "
                      f"kept {len(keep)}/{rows*cols} fx {fx:.4f} "
                      f"cy {cy:.3f} zc {zc:.3f} u_lim {u_lim:.3f} "
                      f"v [{v_lo:.3f},{v_hi:.3f}]")
                for p_ in _face_soil:
                    print(f"          soil {np.round(p_,3)}")
            if cfg.stroke:
                # ONE CONTINUOUS SERPENTINE PER FACE. The row-to-row transition is part
                # of the PATH, not a separate move: the pad stays seated and sweeps the
                # row step in v, which is coverage rather than dead time. Everything the
                # point raster does per point -- probe the surface, plan a tilt, refuse a
                # branch jump -- still happens per KNOT; the only thing removed is the
                # arm standing still at each one waiting to agree it has arrived.
                pad_pts, contiguous = [], False
                for r in range(rows):
                    v = v_lo + (v_hi - v_lo) * r / (rows - 1)
                    order = range(cols) if r % 2 == 0 else reversed(range(cols))
                    for c in order:
                        if keep is not None and (r, c) not in keep:
                            contiguous = False
                            continue
                        u = -u_lim + 2 * u_lim * c / (cols - 1)
                        self.raster_planned += 1
                        hit = self.surface_x(cy + u, zc + v)
                        if hit is None:
                            self.raster_skipped += 1
                            contiguous = False
                            continue
                        pad_pts.append((np.array([hit - cfg.pad_thick_half + cfg.press,
                                                  cy + u, zc + v]), contiguous))
                        contiguous = True
                # the probe above is charged to raster_planned; plan_runs must not
                # double-count it
                self.raster_planned -= len(pad_pts)
                dev0 = self.d.xpos[self.cab_bodyid].copy()
                warm = self.q_warm if self.q_warm is not None else self.q_des
                for rn in self.plan_runs(pad_pts, tm, pad_rel, warm,
                                         1.8 * max(step, row_step)):
                    cleaned += self.stroke_run(rn, cfg.grip_open, index_deg=deg,
                                               frames=frames, tag=f"WIPE {deg:.0f}",
                                               log=forces)
                # A STROKE COMMITS TO A SURFACE MEASURED BEFORE IT STARTED. Point mode
                # re-probes after every point and so tracks a device that shifts; this
                # does not. Measure the shift so the assumption is falsifiable rather
                # than merely stated -- the flange absorbs 0.8 N per mm, so a shift of a
                # millimetre is nothing and a shift of ten is the first suspect.
                self.device_shift = max(self.device_shift, float(np.linalg.norm(
                    self.d.xpos[self.cab_bodyid] - dev0)) * 1000)
            else:
                for r in range(rows):
                    v = v_lo + (v_hi - v_lo) * r / (rows - 1)
                    order = range(cols) if r % 2 == 0 else reversed(range(cols))
                    for c in order:
                        if keep is not None and (r, c) not in keep:
                            continue
                        u = -u_lim + 2 * u_lim * c / (cols - 1)
                        # PROBE THE SURFACE PER POINT with a ray, instead of assuming one
                        # plane for the whole face. A single plane from the geom extents was
                        # inconsistent between mirror-symmetric orientations (0.4536 at index
                        # 90 vs 0.4800 at 270), because a rotated box's X-extent is not its
                        # presented face -- so the pad was commanded short of the surface and
                        # did not touch for 29% of the raster. A ray gives the ACTUAL surface
                        # at this point, and handles the proud back panel for free.
                        # COUNT what gets skipped. A `continue` here used to be invisible:
                        # the point contributed no wipe and no force sample, so a raster that
                        # never ran a third of its points still reported healthy contact.
                        # Anything the station declines to attempt has to show up in the
                        # numbers, or the metric is measuring the subset that succeeded.
                        self.raster_planned += 1
                        hit = self.surface_x(cy + u, zc + v)
                        if hit is None:
                            self.raster_skipped += 1
                            continue
                        pad_pt = np.array([hit - cfg.pad_thick_half + cfg.press,
                                           cy + u, zc + v])
                        # PLAN the point before driving at it, and let it TILT. The target
                        # moves with the tilt, because the pad is offset from the wrist: the
                        # pad face has to land on pad_pt whatever angle the tool arrives at.
                        warm = self.q_warm if self.q_warm is not None else self.q_des
                        got = self.plan_pad(pad_pt, tm, pad_rel, warm)
                        if got is None:
                            self.raster_infeasible += 1
                            continue
                        q_pt, mat_pt, tilt_pt, tgt = got
                        self.q_warm = q_pt
                        self.tilts.append(tilt_pt)
                        cleaned += self.move_planned(q_pt, tgt, cfg.grip_open, index_deg=deg,
                                                     tol=cfg.wipe_tol, t_max=2.5, wipe=True,
                                                     log=forces, tag=f"WIPE {deg:.0f}",
                                                     frames=frames)
            # SPOT PASS: any patch on this face the lattice pass left dirty gets a
            # visit aimed AT THE PATCH, not at the nearest lattice point. Measured cause:
            # at high tilt the pad presses with an edge, its face plane 29.5 mm off the
            # patch (reach is 22), so a single lattice visit can carry force straight
            # over a patch without touching it. Full coverage survives this through
            # neighbouring visits with different tilts; a sparse pass must aim directly.
            if cfg.targeted:
                mujoco.mj_forward(self.m, self.d)
                for p_ in _face_soil:
                    g_alive = [g for g in self.revealed_soil
                               if self.m.geom_rgba[g][3] > 0
                               and np.linalg.norm(self.d.geom_xpos[g] - p_) < 0.005]
                    if not g_alive:
                        continue
                    u_s = float(np.clip(p_[1] - cy, -u_lim, u_lim))
                    v_s = float(np.clip(p_[2] - zc, v_lo, v_hi))
                    self.raster_planned += 1
                    hit = self.surface_x(cy + u_s, zc + v_s)
                    if hit is None:
                        self.raster_skipped += 1
                        continue
                    pad_pt = np.array([hit - cfg.pad_thick_half + cfg.press,
                                       cy + u_s, zc + v_s])
                    warm = self.q_warm if self.q_warm is not None else self.q_des
                    got = self.plan_pad(pad_pt, tm, pad_rel, warm)
                    if got is None:
                        self.raster_infeasible += 1
                        continue
                    q_pt, mat_pt, tilt_pt, tgt = got
                    self.q_warm = q_pt
                    self.tilts.append(tilt_pt)
                    cleaned += self.move_planned(q_pt, tgt, cfg.grip_open,
                                                 index_deg=deg, tol=cfg.wipe_tol,
                                                 t_max=2.5, wipe=True, log=forces,
                                                 tag=f"WIPE {deg:.0f}", frames=frames)
            retract = np.array([fx - cfg.standoff - 0.05, cy, zc]) - tm @ pad_rel
            pl = self.plan_pose(retract, tm, self.q_des)
            if pl is not None:
                self.move_planned(pl[0], retract, cfg.grip_open, index_deg=deg,
                                  tol=0.006, t_max=8.0, tag="RETRACT", frames=frames)
            if verbose:
                on_face = sum(1 for g in self.revealed_soil
                              if self.m.geom_rgba[g][3] > 0)
                print(f"    face {deg:>5.0f} deg: {rows}x{cols} raster, "
                      f"pad_rel {np.round(pad_rel,4)}, fx={fx:.4f}, "
                      f"cleaned so far {n0 - on_face}/{n0}")

        pl = self.plan_pose(safe, tool_mat_face(0.0), self.q_des)
        if pl is not None:
            self.move_planned(pl[0], safe, cfg.grip_open, index_deg=prev_deg,
                              tol=0.006, t_max=8.0, tag="SAFE", frames=frames)

        # --- the TOP face. Stage 3 names the top cover explicitly, and the vertical
        #     loop above never touches it -- soil there would have been permanently
        #     uncleanable while the coverage number quietly ignored it.
        #
        # INDEX FORWARD TO 360, NOT BACK TO 0. The top raster spans the cabinet's LOCAL
        # half-extents (180 x 250 mm) along world X and Y, so it is only correct with the
        # device square-on. It used to get there by accident: every top-pass move left
        # index_deg at its 0.0 default, so the indexer was commanded to unwind 270 deg
        # WHILE the arm was already travelling over the device -- the exact sequencing
        # error the vertical loop documents above. 360 deg keeps every step of the cycle
        # a +90 deg move in one direction, which is also how a real indexer is driven.
        top_deg = 360.0
        skip_top = False
        if cfg.targeted:
            # decide from LOCAL z (rotation-invariant); capture world positions only
            # AFTER the 360-deg index below, because the device is still at 270 here and
            # top-soil x,y rotate with it -- capturing now filtered against a world that
            # no longer existed and missed every top patch.
            cab = self.cab_bodyid
            _p0 = self.d.xpos[cab]; _R0 = self.d.xmat[cab].reshape(3, 3)
            _n_top = sum(1 for g in self.revealed_soil
                         if self.m.geom_rgba[g][3] > 0
                         and (_R0.T @ (self.d.geom_xpos[g] - _p0))[2] > 0.44)
            if _n_top == 0:
                self.targeted_skipped_faces.append(top_deg)
                skip_top = True
        if not skip_top:
            self.dwell(1.4, tool_mat_face(0.0), safe, cfg.grip_open, index_deg=top_deg,
                       frames=frames, tag=f"INDEX {top_deg:.0f}")
            if cfg.targeted:
                mujoco.mj_forward(self.m, self.d)
                cg0 = self.m.geom("cab_body").id
                _ztop = float(self.d.geom_xpos[cg0][2] + self.m.geom_size[cg0][2])
                _top_soil = [self.d.geom_xpos[g].copy() for g in self.revealed_soil
                             if self.m.geom_rgba[g][3] > 0
                             and self.d.geom_xpos[g][2] > _ztop - 0.03]
            tmt = np.array([[1.0, 0, 0], [0, -1.0, 0], [0, 0, -1.0]]).T
            cg = self.m.geom("cab_body").id
            cx, cyy = self.d.geom_xpos[cg][0], self.d.geom_xpos[cg][1]
            _, _, _, _, ztop = self.front_face_plane(top_deg)
            appr = np.array([cx, cyy, ztop + 0.10])
            pl = self.plan_pose(appr, tmt, self.q_des)
            if pl is not None:
                self.q_warm = pl[0]
                self.move_planned(pl[0], appr, cfg.grip_open, index_deg=top_deg,
                                  tol=0.006, t_max=10.0, tag="TO TOP", frames=frames)
            self.dwell(0.3, tmt, appr, cfg.grip_open, index_deg=top_deg,
                       frames=frames, tag="SETTLE")
            tcp_n = self.d.site_xpos[self.site]
            Rn = self.d.site_xmat[self.site].reshape(3, 3)
            prel = Rn.T @ (self.d.geom_xpos[self.pad_face] - tcp_n)
            hx, hy = self.m.geom_size[cg][0], self.m.geom_size[cg][1]
            step = cfg.step_frac * cfg.pad_radius
            row_step = (cfg.row_frac * cfg.pad_radius) if cfg.stroke else step
            ux, uy = hx - cfg.pad_half, hy - cfg.pad_half
            rows = max(int(np.ceil(2 * ux / row_step)) + 1, 2)
            cols = max(int(np.ceil(2 * uy / step)) + 1, 2)
            keep_top = None
            if cfg.targeted and not getattr(self, "_reclean_full", False):
                sp = _top_soil
                keep_top = set()
                _hits = {}
                for r_ in range(rows):
                    du_ = -ux + 2 * ux * r_ / (rows - 1)
                    for c_ in range(cols):
                        dv_ = -uy + 2 * uy * c_ / (cols - 1)
                        for p_ in sp:
                            if np.hypot(p_[0] - (cx + du_), p_[1] - (cyy + dv_)) \
                                    <= cfg.pad_radius + cfg.target_margin:
                                _hits.setdefault(r_, []).append(c_); break
                for r_, cl_ in _hits.items():
                    lo_, hi_ = max(min(cl_) - 1, 0), min(max(cl_) + 1, cols - 1)
                    for rb in (r_ - 1, r_, r_ + 1):
                        if 0 <= rb < rows:
                            for c_ in range(lo_, hi_ + 1):
                                keep_top.add((rb, c_))
            if cfg.stroke:
                # The top face needs no surface probe -- it is a single flat plane at
                # ztop, already read from the model -- so its path is the serpentine
                # lattice directly.
                pad_pts, contiguous = [], False
                for r in range(rows):
                    du = -ux + 2 * ux * r / (rows - 1)
                    order = range(cols) if r % 2 == 0 else reversed(range(cols))
                    for cc in order:
                        if keep_top is not None and (r, cc) not in keep_top:
                            contiguous = False
                            continue
                        dv = -uy + 2 * uy * cc / (cols - 1)
                        pad_pts.append((np.array([cx + du, cyy + dv,
                                                  ztop + cfg.pad_thick_half - cfg.press]),
                                        contiguous))
                        contiguous = True
                dev0 = self.d.xpos[self.cab_bodyid].copy()
                warm = self.q_warm if self.q_warm is not None else self.q_des
                for rn in self.plan_runs(pad_pts, tmt, prel, warm,
                                         1.8 * max(step, row_step)):
                    cleaned += self.stroke_run(rn, cfg.grip_open, index_deg=top_deg,
                                               frames=frames, tag="WIPE top", log=forces)
                self.device_shift = max(self.device_shift, float(np.linalg.norm(
                    self.d.xpos[self.cab_bodyid] - dev0)) * 1000)
            else:
                for r in range(rows):
                    du = -ux + 2 * ux * r / (rows - 1)
                    order = range(cols) if r % 2 == 0 else reversed(range(cols))
                    for cc in order:
                        if keep_top is not None and (r, cc) not in keep_top:
                            continue
                        dv = -uy + 2 * uy * cc / (cols - 1)
                        pad_pt = np.array([cx + du, cyy + dv,
                                           ztop + cfg.pad_thick_half - cfg.press])
                        self.raster_planned += 1
                        warm = self.q_warm if self.q_warm is not None else self.q_des
                        got = self.plan_pad(pad_pt, tmt, prel, warm)
                        if got is None:
                            self.raster_infeasible += 1
                            continue
                        q_pt, mat_pt, tilt_pt, tgt = got
                        self.q_warm = q_pt
                        self.tilts.append(tilt_pt)
                        cleaned += self.move_planned(q_pt, tgt, cfg.grip_open,
                                                     index_deg=top_deg, tol=cfg.wipe_tol,
                                                     t_max=2.5, wipe=True, log=forces,
                                                     tag="WIPE top", frames=frames)
            # spot pass -- same reason as the side faces
            if cfg.targeted:
                mujoco.mj_forward(self.m, self.d)
                for p_ in _top_soil:
                    g_alive = [g for g in self.revealed_soil
                               if self.m.geom_rgba[g][3] > 0
                               and np.linalg.norm(self.d.geom_xpos[g] - p_) < 0.005]
                    if not g_alive:
                        continue
                    du_s = float(np.clip(p_[0] - cx, -ux, ux))
                    dv_s = float(np.clip(p_[1] - cyy, -uy, uy))
                    pad_pt = np.array([cx + du_s, cyy + dv_s,
                                       ztop + cfg.pad_thick_half - cfg.press])
                    self.raster_planned += 1
                    warm = self.q_warm if self.q_warm is not None else self.q_des
                    got = self.plan_pad(pad_pt, tmt, prel, warm)
                    if got is None:
                        self.raster_infeasible += 1
                        continue
                    q_pt, mat_pt, tilt_pt, tgt = got
                    self.q_warm = q_pt
                    self.tilts.append(tilt_pt)
                    cleaned += self.move_planned(q_pt, tgt, cfg.grip_open,
                                                 index_deg=top_deg, tol=cfg.wipe_tol,
                                                 t_max=2.5, wipe=True, log=forces,
                                                 tag="WIPE top", frames=frames)
            clear = np.array([cx, cyy, ztop + 0.12])
            pl = self.plan_pose(clear, tmt, self.q_des)
            if pl is not None:
                self.move_planned(pl[0], clear, cfg.grip_open, index_deg=top_deg,
                                  tol=0.006, t_max=8.0, tag="TOP CLEAR", frames=frames)

        # measure how far the tool moved relative to the wrist across the whole job,
        # while it is STILL LATCHED -- measuring after unlatch just reports the holder
        # COUPLING integrity is measured on the SHANK, not the pad. The pad now rides
        # on the compliance flange, so its offset from the wrist SHOULD change -- that
        # movement is the flange doing its job, and reporting it as "tool drift" would
        # make a working spring look like a slipping grip.
        tcp_e = self.d.site_xpos[self.site]
        Re = self.d.site_xmat[self.site].reshape(3, 3)
        drift_mm = float(np.linalg.norm(
            Re.T @ (self.d.geom_xpos[self.stem] - tcp_e) - self.stem_rel) * 1000)
        acf_mm = float(self.d.qpos[self.acf_q] * 1000)

        # --- return the tool to its holder and unlatch
        # HOLD the indexer where the job left it for the tool return. Letting index_deg
        # fall back to its 0.0 default here commands a 360 deg unwind while the arm is
        # crossing the cell to the holder -- same class of sequencing error as the top
        # pass, and free to avoid.
        self.move(want + np.array([0, 0, 0.14]), gm, cfg.grip_open, index_deg=top_deg,
                  t_max=12.0, tag="RETURN", frames=frames)
        self.move(want, gm, cfg.grip_open, index_deg=top_deg, tol=0.004, t_max=8.0,
                  tag="PLACE", frames=frames)
        self.decouple()
        self.dwell(0.3, gm, want, cfg.grip_open, index_deg=top_deg,
                   frames=frames, tag="UNLATCH")
        self.move(want + np.array([0, 0, 0.14]), gm, cfg.grip_open, index_deg=top_deg,
                  t_max=8.0, tag="CLEAR", frames=frames)

        left = sum(1 for g in self.revealed_soil if self.m.geom_rgba[g][3] > 0)
        f = np.array(forces) if forces else np.array([0.0])
        touching = f[f >= self.cfg.contact_min_n]
        return {"seed": seed, "truth": truth, "picked": True,
                "couple_mm": perr * 1000, "couple_deg": aerr,
                "coupling_drift_mm": drift_mm, "acf_mm": acf_mm,
                "soil0": n0, "cleaned": n0 - left, "missed": left,
                "coverage": (n0 - left) / n0 if n0 else 1.0,
                "f_med": float(np.median(touching)) if len(touching) else 0.0,
                "f_max": float(f.max()),
                "in_band": float(((touching >= cfg.force_lo) &
                                  (touching <= cfg.force_hi)).mean()) if len(touching) else 0.0,
                "contact_frac": float((f >= cfg.contact_min_n).mean()),
                "raster_planned": self.raster_planned,
                "raster_skipped": self.raster_skipped,
                "raster_infeasible": self.raster_infeasible,
                "tilt_mean": float(np.mean(self.tilts)) if self.tilts else 0.0,
                "tilt_max": float(np.max(self.tilts)) if self.tilts else 0.0,
                "tilt_zero_frac": float(np.mean([t == 0.0 for t in self.tilts]))
                                  if self.tilts else 0.0,
                # V7 stroke. Zero in point mode, which is how a stroke row is told apart
                # from a point row in the stats file without a separate schema.
                "stroke": bool(cfg.stroke),
                "stroke_runs": int(self.stroke_runs),
                "stroke_len_m": float(self.stroke_len),
                "stroke_inplane_err_mm": float(self.stroke_path_err * 1000),
                "stroke_track_med_mm": float(np.median(self.stroke_track) * 1000)
                                       if self.stroke_track else 0.0,
                "stroke_track_p99_mm": float(np.percentile(self.stroke_track, 99)
                                             * 1000) if self.stroke_track else 0.0,
                "stroke_total_dev_mm": float(self.stroke_lag * 1000),
                "stroke_flange_mm": float(self.stroke_norm_err * 1000),
                "stroke_corners": int(self.stroke_corners),
                "device_shift_mm": float(self.device_shift),
                "tcp_speed_max": float(self.tcp_speed_max),
                "joint_speed_max": float(self.joint_speed_max)}


def run_with_backstop(cell, seed, max_recleans=2, frames=None):
    """Targeted clean with the VERIFY backstop: re-clean while the camera sees residue.

    THE ACCEPTANCE IS THE CAMERA'S, not the plan's: each round ends with verify(), and
    the loop re-enters only on what VERIFY reports. Returns the final run row, the final
    verify row, and how many re-cleans were needed.
    """
    # Cell.run EXPLICITLY: on a RouteCell, `cell.run` dispatches to the MEMBRANE cycle
    # (MemCell.run overrides it), which is a different machine entirely.
    r = Cell.run(cell, seed, frames=frames)
    v = cell.verify()
    rounds = 0
    while v["soil_left_truth"] > 0 and rounds < max_recleans:
        rounds += 1
        # LAST ROUND ESCALATES to a full sweep of the still-dirty faces. The sparse
        # pass's one failure mode is a patch whose location admits no face contact from
        # any nearby approach; the full raster provably cleans those (100% at this
        # stride), so the guarantee of full-coverage mode is recovered exactly where it
        # is needed, at the cost of one face's sweep on the rare unit that needs it.
        cell._reclean_full = (rounds == max_recleans)
        r2 = Cell.run(cell, seed, reclean=True)
        cell._reclean_full = False
        # accumulate the honest totals: planned/skipped/infeasible add up across rounds
        for k in ("raster_planned", "raster_skipped", "raster_infeasible"):
            r[k] += r2[k]
        r["f_max"] = max(r["f_max"], r2["f_max"])
        r["coverage"] = r2["coverage"]
        r["missed"] = r2["missed"]
        v = cell.verify()
    return r, v, rounds


def report(rows):
    cfg_force_hi = CFG.force_hi
    n = len(rows)
    ok = [r for r in rows if r["picked"]]
    cov = np.array([r["coverage"] for r in ok]) if ok else np.array([0.0])
    print(f"\nCLEANING: {n} units | pad picked {len(ok)}/{n}")
    print(f"  COVERAGE        : mean {cov.mean()*100:.1f}%  median "
          f"{np.median(cov)*100:.1f}%  worst {cov.min()*100:.1f}%")
    print(f"  units at 100%   : {sum(1 for c in cov if c >= 0.999)}/{len(ok)}")
    tot0 = sum(r["soil0"] for r in ok)
    totm = sum(r["missed"] for r in ok)
    print(f"  MISSED SPOTS    : {totm} of {tot0} soil patches "
          f"({totm/max(tot0,1)*100:.1f}%)   <- Stage 3's own QC check")
    fm = np.array([r["f_med"] for r in ok]) if ok else np.array([0.0])
    fx = np.array([r["f_max"] for r in ok]) if ok else np.array([0.0])
    ib = np.array([r["in_band"] for r in ok]) if ok else np.array([0.0])
    cf = np.array([r["contact_frac"] for r in ok]) if ok else np.array([0.0])
    peak = fx.max()
    # NOT `ok` -- that name already holds the list of successful rows, and shadowing it
    # made report() die three lines later without writing stats.
    force_ok = peak <= cfg_force_hi
    print(f"  contact force   : median {fm.mean():.1f} N, peak {peak:.1f} N   "
          f"[{'OK' if force_ok else '*** OUTSIDE MODEL VALIDITY ***'} -- our pad's "
          f"force/penetration curve is measured monotonic to {cfg_force_hi:.0f} N and")
    print(f"                    goes INTERMITTENTLY unstable above it -- 50 N breaks "
          f"(11.6 mm on a 10 mm pad), 55 N is fine,")
    print(f"                    60 N breaks. That is the contact solver, not the pad, and "
          f"it is a MODEL-validity")
    print(f"                    ceiling rather than a component rating.]")
    rp = sum(r.get("raster_planned", 0) for r in ok)
    rs = sum(r.get("raster_skipped", 0) for r in ok)
    # Contact is reported over the PLANNED raster, not the executed subset. Skipped
    # points log no force sample, so averaging only what ran quietly excused every point
    # the station declined to attempt.
    cf_planned = cf.mean() * (1 - rs / max(rp, 1))
    print(f"  in force band   : {ib.mean()*100:.1f}%   contact during raster: "
          f"{cf.mean()*100:.1f}% of points RUN, {cf_planned*100:.1f}% of points PLANNED")
    ri = sum(r.get("raster_infeasible", 0) for r in ok)
    print(f"  raster skipped  : {rs} probe-miss + {ri} no-feasible-pose of {rp} "
          f"planned points ({(rs+ri)/max(rp,1)*100:.1f}%)")
    tz = np.array([r.get("tilt_zero_frac", 0.0) for r in ok]) if ok else np.array([0.0])
    tm_ = np.array([r.get("tilt_mean", 0.0) for r in ok]) if ok else np.array([0.0])
    tx = np.array([r.get("tilt_max", 0.0) for r in ok]) if ok else np.array([0.0])
    print(f"  press angle     : {tz.mean()*100:.1f}% at exact normal, mean tilt "
          f"{tm_.mean():.1f} deg, max {tx.max():.0f} deg (cone limit "
          f"{max(TILT_TOL_DEG):.0f} deg)")
    cd = np.array([r.get("coupling_drift_mm", 0.0) for r in ok]) if ok else np.array([0.0])
    print(f"  coupling drift  : {cd.mean():.2f} mm mean, {cd.max():.2f} mm worst "
          f"(tool changer; the flange stroke is separate and expected)")
    if ok and any(r.get("stroke") for r in ok):
        sr = int(np.mean([r.get("stroke_runs", 0) for r in ok]))
        sl = float(np.mean([r.get("stroke_len_m", 0.0) for r in ok]))
        pe = max(r.get("stroke_inplane_err_mm", 0.0) for r in ok)
        ds = max(r.get("device_shift_mm", 0.0) for r in ok)
        fl = max(r.get("stroke_flange_mm", 0.0) for r in ok)
        cn = int(np.mean([r.get("stroke_corners", 0) for r in ok]))
        print(f"  CONTINUOUS STROKE: {sr} runs/unit, {sl:.2f} m of swept pad path, "
              f"{cn} corners slowed, device shift {ds:.2f} mm")
        tmd = float(np.mean([r.get("stroke_track_med_mm", 0.0) for r in ok]))
        t99 = max(r.get("stroke_track_p99_mm", 0.0) for r in ok)
        print(f"                    IN-PLANE departure from the commanded path: median "
              f"{tmd:.1f} mm, p99 {t99:.1f} mm, worst {pe:.1f} mm")
        print(f"                    <- the coverage-relevant one, on a {CFG.pad_radius*1000:.0f} mm "
              f"pad radius. A max alone hides this distribution.")
        print(f"                    worst NORMAL offset {fl:.1f} mm -- this is the "
              f"ACTIVE CONTACT FLANGE compressing,")
        print(f"                    which is what it is for (press is "
              f"{CFG.press*1000:.0f} mm). The normal direction is judged by the FORCE")
        print("                    band above, not by this number.")
        print(f"                    dwell per surface point under the 60 mm pad at "
              f"{CFG.stroke_feed*1000:.0f} mm/s = {0.060/CFG.stroke_feed:.2f} s")
        print("                    (point mode gives ~2 visits x ~0.5 s ~ 1.0 s. Our model")
        print("                     removes soil on CONTACT, not on dwell, so a shorter")
        print("                     rub is free here and would NOT be free with real cream.")
        print("                     That is a modelling limit, not a result -- flag it.)")
    vmax = max(r.get("tcp_speed_max", 0.0) for r in ok) if ok else 0.0
    jmax = max(r.get("joint_speed_max", 0.0) for r in ok) if ok else 0.0
    vlim, jlim = CFG.arm.max_tcp_speed, CFG.arm.max_joint_rate_rad_s
    # JOINT speed is the arm's MECHANICAL limit and is asserted hard. TOOL speed is
    # asserted with 10% because the governor bounds the COMMANDED Cartesian rate (at 80%
    # of the rating) while a position servo overshoots its setpoint while closing an
    # error: measured peak lands ~6% over on 0.16% of steps, all in free-space moves.
    # Tightening it further is NOT available -- the following-error clamp is what bounds
    # the overshoot, and its force cliff is at 0.14 rad (89.5 N). This still catches the
    # defect it was written for by a factor of three (that was 3020 mm/s).
    v_ok, j_ok = vmax <= vlim * 1.10, jmax <= jlim
    print(f"  peak JOINT speed : {jmax:.2f} rad/s ({np.degrees(jmax):.0f} deg/s) vs the "
          f"arm's PUBLISHED {jlim:.2f} rad/s ({np.degrees(jlim):.0f} deg/s)   "
          f"[{'OK' if j_ok else '*** OVER THE ARM RATING ***'}]")
    print(f"  peak TOOL speed  : {vmax*1000:.0f} mm/s   vs the arm's PUBLISHED "
          f"{vlim*1000:.0f} mm/s TCP limit   [{'OK' if v_ok else '*** OVER THE ARM RATING ***'}]")
    print("                    THIS ASSERTION EXISTS BECAUSE NOTHING ELSE HERE MEASURES")
    print("                    FREE-SPACE MOTION. Every other number is about contact, so")
    print("                    the arm ran at 3x its rating for three phases of work and")
    print("                    was caught by a person watching a video, not by a metric.")
    assert j_ok, (f"peak joint speed {jmax:.2f} rad/s exceeds the arm's published "
                  f"{jlim:.2f} rad/s -- see ArmProfile")
    assert v_ok, (f"peak tool speed {vmax*1000:.0f} mm/s exceeds the arm's published "
                  f"{vlim*1000:.0f} mm/s -- see ArmProfile")
    print("\n  Coverage is of ALL FIVE faces -- the back panel carries soil too, since the")
    print("  indexer reaches it. No fluid or chemistry is simulated: what is verified is")
    print("  that the soil the camera could see is gone.")
    print("\n  THE TRAJECTORY IS OPEN-LOOP AND SEED-INDEPENDENT. The raster, the planned")
    print("  poses and the contact are identical for every unit; the seed only moves the")
    print("  soil. So force, tilt and raster figures above have NO seed variance -- they")
    print("  are effectively n = 1 and must not be quoted as an n-unit spread. Only the")
    print("  coverage and missed-spot figures actually vary across units.")
    return {"n": n, "picked": len(ok), "coverage_mean": float(cov.mean()),
            "coverage_worst": float(cov.min()), "missed": int(totm), "soil": int(tot0),
            "f_max": float(fx.max()), "in_band": float(ib.mean()),
            "contact_run": float(cf.mean()), "contact_planned": float(cf_planned),
            "raster_planned": int(rp), "raster_skipped": int(rs),
            "raster_infeasible": int(ri), "tilt_mean_deg": float(tm_.mean()),
            "tilt_max_deg": float(tx.max()),
            "exact_normal_frac": float(tz.mean()),
            "tcp_speed_max_mms": float(vmax * 1000),
            "joint_speed_max_rad_s": float(jmax),
            "tcp_speed_limit_mms": float(vlim * 1000),
            **({"stroke_runs": int(np.mean([r.get("stroke_runs", 0) for r in ok])),
                "stroke_len_m": float(np.mean([r.get("stroke_len_m", 0.0) for r in ok])),
                "stroke_track_med_mm": float(np.mean([r.get("stroke_track_med_mm", 0.0)
                                                      for r in ok])),
                "stroke_track_p99_mm": float(max(r.get("stroke_track_p99_mm", 0.0)
                                                 for r in ok)),
                "stroke_inplane_worst_mm": float(max(r.get("stroke_inplane_err_mm", 0.0)
                                                     for r in ok)),
                "stroke_flange_mm": float(max(r.get("stroke_flange_mm", 0.0) for r in ok)),
                "device_shift_mm": float(max(r.get("device_shift_mm", 0.0) for r in ok))}
               if ok and any(r.get("stroke") for r in ok) else {})}


def falsify(n, seed0, cfg=CFG):
    """V5-D: the same unit cleaned honestly and cleaned NOT AT ALL, verified both ways.

    PAIRED, deliberately. Each seed is run twice -- once with the wipe working and once
    with removal withheld -- so the two arms differ in exactly one thing. An unpaired test
    can be passed by a verifier that is merely lucky about which units it saw.

    The exit criterion from V5_PLAN is n/n both ways: every honest cleaning verified, every
    sabotaged cleaning caught. Anything less means the check cannot fail, and a check that
    cannot fail is not evidence.
    """
    rows = []
    for k in range(n):
        seed = seed0 + k
        rec = {"seed": seed}
        for sab in (False, True):
            c = Cell(cfg)
            c.sabotage = sab
            r = c.run(seed)
            v = c.verify()
            tag = "sab" if sab else "hon"
            rec[f"{tag}_cov"] = r["coverage"]
            rec[f"{tag}_seen"] = v["soil_seen"]
            rec[f"{tag}_left"] = v["soil_left_truth"]
            rec[f"{tag}_top"] = v["soil_left_top"]
            rec[f"{tag}_pass"] = v["verified"]
        rows.append(rec)
        # print the honest side's RESIDUE too. A unit can be verified while still
        # carrying soil -- that is a FALSE VERIFY, and it is the error this station's
        # customer would care about most. Hiding it behind "seen 0" would repeat exactly
        # the mistake v4's sabotage test was built to catch.
        rec["hon_false"] = bool(rec["hon_pass"] and rec["hon_left"] > 0)
        print(f"  seed {seed}: honest cov {rec['hon_cov']*100:5.1f}% "
              f"left {rec['hon_left']:2d} (top {rec['hon_top']:2d}) seen {rec['hon_seen']:2d}"
              f" -> {'VERIFIED' if rec['hon_pass'] else 'failed'}"
              f"{' **FALSE VERIFY**' if rec['hon_false'] else ''}"
              f" | sabotaged left {rec['sab_left']:2d} (top {rec['sab_top']:2d}) "
              f"seen {rec['sab_seen']:2d} -> {'ESCAPED' if rec['sab_pass'] else 'caught'}")

    hon_ok = sum(r["hon_pass"] for r in rows)
    false_verify = sum(r["hon_false"] for r in rows)
    hon_left_tot = sum(r["hon_left"] for r in rows)
    hon_top_tot = sum(r["hon_top"] for r in rows)
    sab_caught = sum(not r["sab_pass"] for r in rows)
    # the sharp question: could a filthy unit pass because all its residue is on the face
    # the camera cannot see?
    blind = [r for r in rows if r["sab_left"] > 0 and r["sab_left"] == r["sab_top"]]
    top_left = sum(r["sab_top"] for r in rows)
    all_left = sum(r["sab_left"] for r in rows)

    print(f"\nV5-D FALSIFICATION: {n} units, each run twice")
    print(f"  honest cleanings VERIFIED   : {hon_ok}/{n}")
    print(f"  FALSE VERIFIES              : {false_verify}/{n}   <- passed while still "
          f"carrying soil ({hon_left_tot} patches left, {hon_top_tot} of them on the "
          f"unseeable top face)")
    print(f"  sabotaged cleanings CAUGHT  : {sab_caught}/{n}   <- the one that matters")
    print(f"  residue on the TOP face     : {top_left} of {all_left} patches "
          f"({top_left/max(all_left,1)*100:.1f}%) -- the face V5-C cleans worst")
    print(f"  units that could ESCAPE      : {len(blind)}/{n} "
          f"(all residue on one face)")
    print("\n  WHY THERE ARE TWO CAMERAS. The triage camera sits at z = 0.400 and the")
    print("  device top face at z = 0.450 -- below the plane of that face, so it can never")
    print("  see the top, and `face_regions` returns the four VERTICAL faces only. V5-C")
    print("  wipes five faces and counts five. Verified through that camera alone, this")
    print("  test scored a perfect 10/10 sabotage-caught while letting 9 of 10 honestly-")
    print("  cleaned-but-still-dirty units PASS, because the face cleaning misses and the")
    print("  face the camera cannot see are the SAME face. `verify_top` was added for that")
    print("  reason and is a hardware requirement, not a rendering convenience.")
    print("\n  A CHECK THAT CANNOT FAIL IS NOT EVIDENCE -- and n/n on the sabotage arm")
    print("  alone would have been exactly that. Read the FALSE VERIFY line first.")
    st = {"n": n, "honest_verified": hon_ok, "false_verify": false_verify,
          "honest_residual": hon_left_tot, "honest_residual_on_top": hon_top_tot,
          "sabotage_caught": sab_caught,
          "residual_total": all_left, "residual_on_top": top_left,
          "would_escape": len(blind), "rows": rows}
    # PROTECT THE PUBLISHED BASELINE, same reason as stats_v5_clean.json: the committed
    # stats_v5_verify.json is V5-D's recorded 10/10 on the point-mode station.
    _tag = ("_stroke" if cfg.stroke else "") + ("_targeted" if cfg.targeted else "")
    out = f"stats_v5_verify{_tag}.json"
    st["mode"] = ("stroke" if cfg.stroke else "point") + \
                 ("+targeted" if cfg.targeted else "+full")
    st["seed0"] = seed0
    with open(out, "w") as f:
        json.dump(st, f, indent=2)
    print(f"\nwrote {out}")
    return st


# ============================================================ V6: cycle time
#
# WHY THIS EXISTS. "Make cleaning faster" is a tuning instruction, and this project's own
# rule is diagnose first. The budget answered it in one run: STROKE is 91.3% of the cycle
# and ALL the overhead -- tool changer, five turntable rotations, every retract and
# approach -- is 7.2%. Optimising the sequencing that took four bugs to get right would
# have bought nothing. The cycle IS the raster.
#
# The cleaning trajectory is open-loop and seed-independent, so ONE unit gives the exact
# budget rather than a sample of it. Only coverage and missed spots vary with the seed.
STROKE_TAGS = ("WIPE",)
OVERHEAD_TAGS = ("SAFE", "TO FACE", "TO TOP", "SETTLE", "RETRACT", "TOP CLEAR", "INDEX")
LATCH_TAGS = ("APPROACH", "COUPLE", "LIFT", "RETURN", "PLACE", "UNLATCH", "CLEAR")


def time_budget(seed, cfg=CFG):
    """Where the clean cycle's seconds go. Measures; changes nothing."""
    c = Cell(cfg)
    c.budget = {"t": {}, "n": {}, "dur": {}, "timeout": {}}
    r = c.run(seed)
    T = c.budget["t"]
    total = sum(T.values())
    pick = lambda pres: {k: v for k, v in T.items() if any(k.startswith(p) for p in pres)}
    stroke, over, latch = pick(STROKE_TAGS), pick(OVERHEAD_TAGS), pick(LATCH_TAGS)
    pts = [d for k, v in c.budget["dur"].items() if k.startswith("WIPE") for d in v]
    tmo = sum(v for k, v in c.budget["timeout"].items() if k.startswith("WIPE"))
    print(f"\nCLEAN CYCLE TIME BUDGET -- seed {seed}, step_frac {cfg.step_frac}, "
          f"speed {cfg.speed}")
    print(f"  simulated cycle {total:.2f} s | coverage {r['coverage']*100:.1f}% | "
          f"raster {r['raster_planned']} planned, {r['raster_skipped']} skipped")
    for name, grp in (("STROKE (pad on surface)", stroke),
                      ("retract/rotate/approach", over),
                      ("tool latch/unlatch", latch)):
        t = sum(grp.values())
        print(f"    {name:<26} {t:8.2f} s  {t/total*100:5.1f}%")
    unit = "stroke runs" if cfg.stroke else "raster points"
    print(f"  {unit} executed {len(pts)}  median {np.median(pts):.3f} s  "
          f"mean {np.mean(pts):.3f} s  hit t_max {tmo}/{len(pts)}")
    if cfg.stroke:
        print(f"  swept path {r['stroke_len_m']:.2f} m in {r['stroke_runs']} runs at "
              f"{cfg.stroke_feed*1000:.0f} mm/s | worst path error "
              f"{r['stroke_inplane_err_mm']:.1f} mm | device shift "
              f"{r['device_shift_mm']:.2f} mm")
    print(f"  per face: " + "  ".join(f"{k.split()[-1]}={v:.1f}s"
                                      for k, v in sorted(stroke.items())))
    # per-point cost per face -- if one face is dearer PER POINT, the cause is pose, not
    # distance, and a bigger stride will not help it as much as the geometry predicts
    print(f"  s/point : " + "  ".join(
        f"{k.split()[-1]}={np.mean(c.budget['dur'][k]):.3f}"
        for k in sorted(c.budget["dur"]) if k.startswith("WIPE")))
    return {"seed": seed, "total_s": total, "stroke_s": sum(stroke.values()),
            "overhead_s": sum(over.values()), "latch_s": sum(latch.values()),
            "points": len(pts), "point_median_s": float(np.median(pts)),
            "timeouts": tmo, "coverage": r["coverage"],
            "per_face_s": stroke, "tilt_max": r["tilt_max"], "f_max": r["f_max"],
            "in_band": r["in_band"]}


def sweep(param, values, n, seed0, out, base=None):
    """Vary ONE parameter and report cycle time against every quality metric it could cost.

    A speedup that quietly drops coverage, leaves the force band, or exceeds the tilt cone
    is not a speedup -- it is the same trade this project already refused once.
    """
    import dataclasses
    base = base if base is not None else CFG
    rows = []
    for v in values:
        cfg = dataclasses.replace(base, **{param: v})
        c = Cell(cfg)
        c.budget = {"t": {}, "n": {}, "dur": {}, "timeout": {}}
        rs = [c.run(seed0 + k) for k in range(n)]
        # budget accumulates across the n units; divide to get per-unit
        total = sum(c.budget["t"].values()) / n
        cov = np.array([r["coverage"] for r in rs])
        row = {param: v, "cycle_s": total, "n": n,
               "step_frac": cfg.step_frac, "speed": cfg.speed,
               "cov_mean": float(cov.mean()), "cov_worst": float(cov.min()),
               "missed": int(sum(r["missed"] for r in rs)),
               "soil": int(sum(r["soil0"] for r in rs)),
               "f_max": float(max(r["f_max"] for r in rs)),
               "in_band_worst": float(min(r["in_band"] for r in rs)),
               "tilt_max": float(max(r["tilt_max"] for r in rs)),
               "raster": int(rs[0]["raster_planned"]),
               "skipped": int(sum(r["raster_skipped"] for r in rs)),
               "track_med_mm": float(np.mean([r.get("stroke_track_med_mm", 0.0)
                                              for r in rs])),
               "track_p99_mm": float(max(r.get("stroke_track_p99_mm", 0.0) for r in rs)),
               "track_max_mm": float(max(r.get("stroke_inplane_err_mm", 0.0) for r in rs)),
               "flange_mm": float(max(r.get("stroke_flange_mm", 0.0) for r in rs)),
               "runs": int(rs[0].get("stroke_runs", 0))}
        rows.append(row)
        print(f"  {param}={v:<6} cycle {total:7.2f}s  raster {row['raster']:4d}  "
              f"cov {row['cov_mean']*100:5.1f}% (worst {row['cov_worst']*100:5.1f}%)  "
              f"missed {row['missed']:3d}/{row['soil']:3d}  "
              f"fmax {row['f_max']:5.2f}N  in-band {row['in_band_worst']*100:5.1f}%  "
              f"tilt {row['tilt_max']:4.1f}deg"
              + (f"  track {row['track_med_mm']:4.1f}/{row['track_p99_mm']:5.1f}/"
                 f"{row['track_max_mm']:5.1f}mm" if cfg.stroke else ""))
    with open(out, "w") as f:
        json.dump({"param": param, "n": n, "seed0": seed0, "rows": rows}, f, indent=2)
    print(f"\nwrote {out}")
    print("  A row is only usable if coverage holds at 100%, missed = 0, peak force is")
    print(f"  under the {CFG.force_hi:.0f} N model-validity ceiling and tilt is inside 30 deg.")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int)
    ap.add_argument("--eval", type=int)
    ap.add_argument("--sabotage", type=int,
                    help="V5-D paired falsification test: N units, honest and sabotaged")
    # 900, not 800: a bare --eval should reproduce the PUBLISHED number, not a seed range
    # the ledger records as spent on development. 800-807 were used to diagnose against
    # the old 64.7%, so defaulting there quietly reproduced a development figure.
    ap.add_argument("--seed0", type=int, default=900)
    ap.add_argument("--budget", type=int, metavar="SEED",
                    help="V6: where the cycle's seconds go. One unit; writes nothing.")
    ap.add_argument("--stride-sweep", type=int, metavar="N", dest="stride_sweep",
                    help="V6: sweep step_frac over N units each")
    ap.add_argument("--feed-sweep", type=int, metavar="N", dest="feed_sweep",
                    help="V6: sweep speed over N units each")
    ap.add_argument("--at-stride", type=float, default=1.20, dest="at_stride",
                    help="step_frac to hold fixed during --feed-sweep")
    ap.add_argument("--validate", type=int, metavar="N", dest="validate",
                    help="V6: run N units at each candidate stride on held-out seeds")
    # --- V7 continuous stroke
    ap.add_argument("--stroke", action="store_true",
                    help="V7: sweep each face as continuous strokes instead of "
                         "stopping at every raster point")
    ap.add_argument("--targeted", action="store_true",
                    help="V6 targeted cleaning (soil-adjacent bands only)")
    ap.add_argument("--feed", type=float, default=None,
                    help="V7: stroke_feed in m/s (default %.2f)" % CleanConfig.stroke_feed)
    ap.add_argument("--stroke-sweep", type=int, metavar="N", dest="stroke_sweep",
                    help="V7: sweep stroke_feed over N units each")
    ap.add_argument("--row-sweep", type=int, metavar="N", dest="row_sweep",
                    help="V7: sweep row_frac (the only coverage-critical spacing in "
                         "stroke mode) over N units each -- finds the 2.0 R cliff")
    a = ap.parse_args()
    import dataclasses as _dc
    _over = {}
    if a.stroke:
        _over["stroke"] = True
    if a.targeted:
        _over["targeted"] = True
    if a.feed is not None:
        _over["stroke_feed"] = a.feed
    CFGX = _dc.replace(CFG, **_over) if _over else CFG
    # PROTECT THE PUBLISHED BASELINE. `stats_v5_clean.json` is the recorded
    # full-coverage point-mode number the whole station is measured against; a stroke
    # or targeted run must never land in it.
    _tag = ("_stroke" if CFGX.stroke else "") + ("_targeted" if CFGX.targeted else "")
    STATS = f"stats_v5_clean{_tag}.json"
    if a.validate:
        import dataclasses as _dc
        for sf in (1.20, 1.30):
            print(f"\n--- HELD-OUT VALIDATION, step_frac {sf}, seeds "
                  f"{a.seed0}-{a.seed0+a.validate-1} ---")
            sweep("step_frac", [sf], a.validate, a.seed0, f"validate_{sf}.json")
    elif a.stroke_sweep:
        sweep("stroke_feed", [0.05, 0.10, 0.15, 0.20, 0.30], a.stroke_sweep, a.seed0,
              "sweep_stroke_feed.json", base=_dc.replace(CFGX, stroke=True))
    elif a.row_sweep:
        # The geometric cliff for a swept band is pitch <= 2.000 R, not the lattice's
        # 1.414 R. Measure where it actually falls before believing the geometry.
        sweep("row_frac", [1.20, 1.50, 1.70, 1.85, 2.00, 2.20], a.row_sweep, a.seed0,
              "sweep_row.json", base=_dc.replace(CFGX, stroke=True))
    elif a.budget is not None:
        time_budget(a.budget, CFGX)
    elif a.stride_sweep:
        sweep("step_frac", [0.95, 1.10, 1.20, 1.30, 1.414], a.stride_sweep,
              a.seed0, "sweep_stride.json")
    elif a.feed_sweep:
        # swept at the CHOSEN stride, not the old one: the two interact, and what we want
        # to know is the feed curve of the config we would actually ship
        import dataclasses as _dc
        sweep("speed", [1.0, 1.5, 2.0, 3.0, 4.0], a.feed_sweep, a.seed0,
              "sweep_feed.json", base=_dc.replace(CFG, step_frac=a.at_stride))
    elif a.sabotage:
        falsify(a.sabotage, a.seed0, CFGX)
    elif a.run is not None:
        c = Cell(CFGX)
        r = c.run(a.run, verbose=True)
        print(r)
    elif a.eval:
        c = Cell(CFGX)
        rows = []
        for k in range(a.eval):
            rows.append(c.run(a.seed0 + k))
            print(f"  seed {a.seed0+k}: cov {rows[-1]['coverage']*100:5.1f}%  "
                  f"picked={rows[-1]['picked']}  fmax {rows[-1]['f_max']:.1f} N")
        st = report(rows)
        st["mode"] = ("stroke" if CFGX.stroke else "point") + \
                     ("+targeted" if CFGX.targeted else "+full")
        st["stroke_feed"] = CFGX.stroke_feed if CFGX.stroke else None
        st["row_frac"] = CFGX.row_frac if CFGX.stroke else CFGX.step_frac
        st["seed0"] = a.seed0
        with open(STATS, "w") as f:
            json.dump(st, f, indent=2)
        print(f"\nwrote {STATS}")
    else:
        ap.print_help()
        sys.exit(1)
