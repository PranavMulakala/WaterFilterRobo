"""V5-G -- render the v5 cell: triage, clean, verify, membrane, dip.

    ../venv/bin/python v5_video.py --render 1600           one unit, full cycle
    ../venv/bin/python v5_video.py --render 1600 --speed 4  labelled speed-up

WHY THIS FILE EXISTS AT ALL. Every v5 station was measured before any of them was ever
rendered -- `--render` existed nowhere in v5 until now. That ordering was deliberate and is
worth keeping: a video is a claim, and the numbers should exist before the claim does.

THE HUD IS PART OF THE DELIVERABLE, NOT DECORATION. This project's whole value is that it
does not overstate, and a video is where overstatement is easiest and hardest to catch. So
every frame carries the caveat that applies to what is on screen at that moment:

  * during the DIP:  BUBBLES = MODELLED FROM TORQUE, NOT FLUID SIM
  * during CLEAN:    no cream / detergent / chemistry is simulated
  * during TRIAGE:   the class NAMES are DrinkPrime's, the BOUNDARIES are ours
  * throughout:      membrane geometry is PLACEHOLDER pending CAD
  * any speed-up is stamped on the frame, as v4's 1.8x cut was

If a caption would need a verbal footnote in the room, it belongs on the frame instead.
"""
import argparse
import json
import sys

import numpy as np
import mujoco

import v5_route as RT
import v5_triage as TR
import dp_process as DP
from sim_poc4 import _font, FPS

W, H = 1280, 720

# Plain-English narration for every motion tag -- the HUD shows this line so a
# non-technical viewer can follow what the arm is doing at any moment.
FRIENDLY = {
    "APPROACH": "Reaching for the cleaning pad",
    "COUPLE": "Locking the pad onto the wrist (tool changer)",
    "LIFT": "Lifting the pad off its post",
    "SAFE": "Backing away to a safe position",
    "TO FACE": "Moving in front of the next surface",
    "SETTLE": "Letting the arm settle",
    "RETRACT": "Pulling back from the surface",
    "TO TOP": "Moving above the unit",
    "TOP CLEAR": "Backing away from the top",
    "RETURN": "Returning the pad to its post",
    "PLACE": "Setting the pad down",
    "UNLATCH": "Releasing the pad",
    "CLEAR": "Backing away, cleaning done",
    "ELEM_UP": "Rising to travel height",
    "ELEM_OVER": "Travelling over to the membrane element",
    "ELEM_DESCEND": "Descending to the element",
    "ELEM_GRIP": "Gripping the element",
    "ELEM_LIFT": "Lifting the element (slowly -- it can slip)",
    "ELEM_CARRY": "Carrying the element to the open housing",
    "ELEM_ALIGN": "Fine-correcting aim, watching the ELEMENT not the wrist",
    "ELEM_INSERT": "Lowering the element into the housing (1.5 mm to spare)",
    "ELEM_RELEASE": "Opening the jaws",
    "ELEM_RETRACT": "Withdrawing -- element seated",
    "ELEM_SETTLE": "Letting everything settle",
    "MEMBRANE_INSERT": "Starting the membrane insert",
    "CAP_UP": "Rising to travel height",
    "CAP_OVER": "Travelling to the cap",
    "CAP_DESCEND": "Descending to the cap",
    "CAP_GRIP": "Gripping the cap by its pick stem",
    "CAP_LIFT": "Lifting the cap",
    "CAP_CARRY": "Carrying the cap to the housing",
    "CAP_ALIGN": "Fine-correcting aim, watching the CAP not the wrist",
    "CAP_LOWER": "Lowering the cap onto the housing mouth",
    "CAP_RELEASE": "Opening the jaws -- cap engaged on its first thread",
    "CAP_RETRACT": "Withdrawing",
    "DRV_APPROACH": "Bringing the driver over the cap",
    "DRV_DOCK": "Holding the driver on the cap -- spindle spins only while held",
    "DRV_SPIN": "Driver spinning the cap down -- arm holds station (enforced)",
    "VERIFY PARK": "Moving clear of the inspection camera",
}


def friendly(tag):
    if tag.startswith("VERIFY INDEX"):
        return "Turntable presenting each face to the check camera"
    if tag.startswith("WIPE top"):
        return "Wiping the TOP surface"
    if tag.startswith("WIPE"):
        return f"Wiping a side surface (position {tag.split()[-1]} deg)"
    if tag.startswith("INDEX"):
        return "Turntable rotating the next surface into reach"
    return FRIENDLY.get(tag, tag)


CAVEAT = {
    "TRIAGE": "NO ARM MOTION HERE -- the arm parks clear, the turntable is stepped to each "
              "face and a FIXED camera grades pixels. NAMES + OUTCOME DEFINITIONS theirs "
              "(verbal); the VISUAL boundaries the camera applies are OURS.",
    "CLEAN": "No cream, detergent or chemistry is simulated. What is verified is that the "
             "soil the camera could see is gone.",
    "VERIFY": "The arm DRIVES clear of the camera and the indexer ROTATES each face past "
              "it -- both real motions, both counted. Re-inspected through a SECOND camera: "
              "the triage camera cannot see the top face, and that is the face cleaning misses.",
    "MEMBRANE": "The ARM inserts the element, PLACES the cap (thread-start capture 4mm/4deg "
                "is modelled) and HOLDS the driver -- the spindle spins only while the arm "
                "holds station. Geometry PLACEHOLDER.",
    "SOLUTION": "THE ARM CHARGES THE PAD from the tray -- DrinkPrime Stage 3 dips the "
                "CLOTH, never the device. The LIQUID IS A RENDERED SLAB: no fluid sim, no "
                "chemistry. What is real is the motion, the time, and that the charge RUNS "
                "OUT and has to be fetched again.",
    "DIP": "THE ARM DOES NOT CARRY THIS -- the assembly is TELEPORTED into the bin. "
           "BUBBLES = MODELLED FROM TORQUE, NOT FLUID SIM. The camera must still see them.",
    "SCRAP": "NO MOTION DELIVERS THE UNIT ANYWHERE -- this is a SOFTWARE decision only. "
             "HARD forks into RECTIFIABLE / NON-RECTIFIABLE on rectification cost. We have "
             "no cost model, so this goes to a HUMAN approval gate.",
}


class Recorder:
    def __init__(self, model, speed=1):
        from PIL import Image, ImageDraw
        self.Image, self.ImageDraw = Image, ImageDraw
        self.main = mujoco.Renderer(model, H, W)
        self.side = mujoco.Renderer(model, 216, 288)
        self.f_h = _font("mono_bold", 22)
        self.f = _font("mono", 20)
        self.f_s = _font("mono", 15)
        self.frames = []
        self.speed = speed
        self.info = {}
        self.marks = []          # (frame index, station) each time the station changes
        # TRUE simulated elapsed time. d.time is ZEROED by reset()/reset_mem() partway
        # through a cycle, so a naive read of it loses everything before the reset.
        self._t_base = 0.0
        self._t_last = 0.0

    def grab(self, d, station, cam="main", inset=None):
        now = float(d.time)
        if now < self._t_last:          # the clock was reset -- bank what came before
            self._t_base += self._t_last
        self._t_last = now
        if not self.marks or self.marks[-1][1] != station:
            # TRUE simulated clock, not frame index: frames are not grabbed at a uniform
            # sim cadence and some phases (TRIAGE, VERIFY) are pure rendering that costs
            # ZERO motion time but still occupies frames. A frame-derived split invents
            # seconds for them and steals seconds from CLEAN.
            self.marks.append((self._t_base + now, station))
        self.main.update_scene(d, camera=cam)
        img = self.Image.fromarray(self.main.render())
        draw = self.ImageDraw.Draw(img, "RGBA")
        if inset:
            self.side.update_scene(d, camera=inset)
            wr = self.Image.fromarray(self.side.render())
            px, py = W - 288 - 16, H - 216 - 16
            draw.rectangle([px - 3, py - 3, px + 291, py + 219], fill=(255, 255, 255, 220))
            img.paste(wr, (px, py))
            draw.text((px + 6, py + 4), inset.upper().replace("_", " "),
                      font=self.f_s, fill=(255, 255, 255, 230))

        # truncate to the panel width -- the route PLAN is 90+ chars and spilled straight
        # out of the dark box and off the frame
        lines = [(f"{k:<10}{v}")[:68] for k, v in self.info.items()]
        draw.rectangle([12, 12, 830, 46 + len(lines) * 26], fill=(10, 14, 20, 185))
        draw.text((24, 20), f"DrinkPrime REFURB CELL v5  --  {station}",
                  font=self.f_h, fill=(120, 200, 255, 255))
        for i, ln in enumerate(lines):
            draw.text((24, 52 + i * 26), ln, font=self.f, fill=(235, 240, 245, 255))

        # stage chips -- only the stations this route actually performs
        x0, y0 = 24, 60 + len(lines) * 26
        for st in self.chips:
            w = int(draw.textlength(st, font=self.f)) + 26
            on = st == station
            draw.rectangle([x0, y0, x0 + w, y0 + 32],
                           fill=(41, 121, 255, 235) if on else (255, 255, 255, 38))
            draw.text((x0 + 13, y0 + 6), st, font=self.f,
                      fill=(255, 255, 255, 255) if on else (170, 180, 195, 255))
            x0 += w + 8

        # THE CAVEAT FOR WHAT IS ON SCREEN RIGHT NOW
        cav = CAVEAT.get(station, "")
        if cav:
            draw.rectangle([12, H - 62, W - 12, H - 12], fill=(10, 14, 20, 190))
            for i, seg in enumerate(_wrap(cav, 108)):
                draw.text((24, H - 56 + i * 20), seg, font=self.f_s,
                          fill=(255, 214, 120, 245))
        if self.speed > 1:
            draw.text((W - 150, 24), f"{self.speed}x SPEED", font=self.f_h,
                      fill=(255, 214, 120, 255))
        self.frames.append(np.asarray(img).copy())

    def write(self, out):
        import imageio
        imageio.mimsave(out, self.frames, fps=FPS, codec="libx264", quality=8,
                        macro_block_size=None)
        print(f"wrote {out}  ({len(self.frames)} frames, {len(self.frames)/FPS:.1f} s)")


def _wrap(s, n):
    out, cur = [], ""
    for w in s.split():
        if len(cur) + len(w) + 1 > n:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out[:2]


def render_unit(seed, speed=1.0, out=None, v6=False, stroke=False,
                physical=False, solution=False):
    import dataclasses as _dc
    import v5_clean as _CL
    # V7: stroke composes with targeted -- they are independent switches. The render
    # path MUST construct the cell from the same CleanConfig the evaluation uses and
    # call the EVALUATED methods; v5_video has twice filmed a stale system by drifting
    # from that, and CLAUDE.md records both times.
    _over = {}
    if v6:
        _over["targeted"] = True
    if physical:
        # PUBLISHED ARM LIMITS. Our default setpoint rate is 0.02 rad per 2 ms step =
        # 10 rad/s, and UFACTORY publish 180 deg/s (3.14 rad/s) and 1 m/s at the TCP.
        # Measured consequence of the default: repositioning moves fling the pad at up
        # to 3.0 m/s. Contact motion is unaffected (the sweep runs at 93 mm/s median).
        _over["arm"] = _dc.replace(_CL.ARM, joint_rate=3.1416 * 0.002)
    if solution:
        CAVEAT["CLEAN"] = (
            "The pad is CHARGED FROM THE TRAY, but the CHEMISTRY is still not simulated: "
            "solution does not make soil easier to remove here, because removal is binary "
            "on contact. What is modelled is that solution is CARRIED, SPENT and REFETCHED "
            "-- and that a pad which runs dry keeps pressing and stops cleaning.")
        # V8: charge the pad from the solution tray (DrinkPrime Stage 3). Set through
        # the SAME CleanConfig the evaluation uses, for the same reason as everything
        # else here -- the render path has twice filmed a stale system by building its
        # own cell, and both times are recorded in CLAUDE.md.
        _over["solution"] = True
    if stroke:
        # FULL COVERAGE, deliberately. Stroke does NOT imply targeted: the two are
        # substitutes (both remove the same per-point stall cost) and stacking them
        # measured SLOWER than targeted alone, with one unit in 16 producing a 91.5 N
        # contact outside the model's validity. Full-coverage stroke is what ships.
        _over["stroke"] = True
    c = RT.RouteCell(_dc.replace(_CL.CFG, **_over)) if _over else RT.RouteCell()
    if stroke:
        CAVEAT["CLEAN"] = (
            "V7 CONTINUOUS STROKE, FULL COVERAGE: the pad is seated once per run and "
            "then SWEPT along the path under continuous flange compression instead of "
            "stopping at all 323 raster points. Every one of the five exposed faces is "
            "still swept in full -- nothing is skipped -- and the residue check that "
            "follows is a real camera.")
    elif v6:
        CAVEAT["CLEAN"] = (
            "V6 TARGETED: wipes only where dirt was seen, then a camera re-checks and "
            "re-cleans if anything is left. Dirt LOCATIONS are ground truth standing in "
            "for camera localisation; the FINAL residue check is a real camera.")
    rec = Recorder(c.m, speed)
    every = max(1, int(round(speed / (FPS * c.dt))))

    # ---------------- TRIAGE
    row = c.grade(seed)
    grade, truth = row["pred"], row["truth"]
    route = RT.GRADE_ROUTE[grade]
    plan = DP.V5_ROUTES[route].steps
    rec.chips = (["TRIAGE", "SCRAP"] if route == "hard_non_rectifiable"
                 else ["TRIAGE"] + (["SOLUTION"] if solution else []) +
                      ["CLEAN", "VERIFY"] +
                      (["MEMBRANE", "DIP"] if route != "easy" else []))
    rec.info = {"SEED": seed, "TRUTH": truth, "GRADED": grade.upper(),
                "ROUTE": route, "PLAN": " -> ".join(plan)}
    tt = c.m.jnt_qposadr[c.m.joint("tt_rot").id]
    for deg in TR.CFG.index_deg:                      # show the indexer presenting faces
        c.d.qpos[tt] = np.deg2rad(deg)
        mujoco.mj_forward(c.m, c.d)
        rec.info["INDEX"] = f"{deg:.0f} deg"
        for _ in range(6):
            rec.grab(c.d, "TRIAGE", inset="inspect")

    if route == "hard_non_rectifiable":
        rec.info["OUTCOME"] = "-> SCRAP APPROVAL (human decision gate)"
        for _ in range(int(FPS * 2.5)):
            rec.grab(c.d, "SCRAP", inset="inspect")
    else:
        # ---------------- CLEAN (the real V5-C cycle, frames plumbed through)
        rec.info.pop("INDEX", None)
        # THE STATION IS CHOSEN FROM THE MOTION TAG, not assumed. Charging the pad is a
        # different station from wiping with it -- different caveat, different chip -- and
        # billing its seconds to CLEAN would understate the dip exactly the way VERIFY was
        # understated when it teleported. One callback, two stations.
        _stn = lambda tag: ("SOLUTION" if tag.startswith(("DIP", "REDIP")) else "CLEAN")
        frames = {"f": rec.frames, "max": 10_000, "every": every,
                  "cb": lambda tag: (rec.info.__setitem__("STEP", friendly(tag)),
                                     rec.grab(c.d, _stn(tag), inset="verify_top"))}
        if v6:
            cr, v_bs, n_rc = _CL.run_with_backstop(c, seed, frames=frames)
            rec.info["COVERAGE"] = (f"{cr['coverage']*100:.1f}%  peak {cr['f_max']:.1f} N"
                                    f"  re-cleans {n_rc}")
        else:
            cr = super(RT.MB.MemCell, c).run(seed, frames=frames)
            rec.info["COVERAGE"] = f"{cr['coverage']*100:.1f}%  peak {cr['f_max']:.1f} N"
        rec.info.pop("STEP", None)

        # ---------------- VERIFY
        # DRIVEN, not teleported, and filmed. The arm moves itself out of the camera's
        # view and the indexer physically rotates each face past it -- which is what a
        # real cell must do and what makes this one continuous piece of footage instead
        # of a jump cut at the clean/verify boundary.
        vfr = {"f": rec.frames, "max": 10_000, "every": every,
               "cb": lambda tag: (rec.info.__setitem__("STEP", friendly(tag)),
                                  rec.grab(c.d, "VERIFY", inset="verify_top"))}
        v = c.verify(drive=True, frames=vfr)
        rec.info.pop("STEP", None)
        rec.info["VERIFY"] = (f"residue {v['soil_left_truth']} -> "
                              f"{'VERIFIED' if v['verified'] else 'FAILED'}")
        for _ in range(int(FPS * 2.0)):
            rec.grab(c.d, "VERIFY", inset="verify_top")

        if route != "easy":
            # ---------------- MEMBRANE INSERT (3.4), then multi-turn to torque
            # KEEP THE CELL. A bare reset_mem() here is a full keyframe reset, so the
            # arm snapped home and the unit re-initialised in the middle of the cycle --
            # the second half of the cut at ~1:52.
            c.reset_mem(seed, keep_cell=True)
            mc = c.mcfg
            # REGRESSION GUARD. reset_mem() leaves the bowl OPEN (cap absent) so the
            # element can be inserted. Between 11f9ea9 and this commit the video called
            # reset_mem() and then drove `capdrv` directly -- so it rendered a bowl with
            # no element and tightened a cap that was invisible AND non-colliding, while
            # the HUD printed STALLED unconditionally. A demo path that skips the
            # evaluated controller stops being a picture of the evaluated system, which
            # is the same lesson as V5-G's re-aimed camera. Use the real methods.
            rec.info["STEP"] = "MEMBRANE_INSERT"
            ins = c.insert_element(frames={
                "f": rec.frames, "max": 10_000, "every": every,
                "cb": lambda tag: (rec.info.__setitem__("STEP", friendly(tag)),
                                   rec.grab(c.d, "MEMBRANE", cam="main",
                                            inset="demo_mem"))})
            rec.info["INSERT"] = (
                f"aligned {ins['align_mm']:.2f} mm -> seated {ins['seat_xy_mm']:.2f} mm "
                f"off-axis, {'IN' if ins['inserted'] else 'NOT SEATED'}")
            rec.info.pop("STEP", None)
            # THE ARM places the cap and holds the driver -- the REAL methods, with
            # frame callbacks only. (This block was previously a copied drive loop plus
            # a cap_present teleport; it silently stopped filming the actual system the
            # moment cap_place existed -- the same render-path rot as the V5-G bug.)
            fr = {"f": rec.frames, "max": 10_000, "every": every,
                  "cb": lambda tag: (rec.info.__setitem__("STEP", friendly(tag)),
                                     rec.grab(c.d, "MEMBRANE", cam="main",
                                              inset="demo_mem"))}
            cp = c.cap_place(frames=fr)
            rec.info["CAP"] = (f"landed {cp['place_err_mm']:.2f} mm off-axis -> "
                               f"{'ENGAGED first thread' if cp['placed'] else 'MISSED'}")
            mc = c.mcfg
            tg = c.tighten(frames=fr)
            tq = tg["torque_nm"]
            rec.info["TIGHTEN"] = (
                f"{tg['turns']:5.2f} turns  {tq:4.2f} Nm  "
                f"{'STALLED' if tg['stalled'] else 'NO STALL'} "
                f"(driver limit {mc.torque_target_nm:.1f})")
            # ---------------- 3.6 charge, then 3.7 dip
            chg = c.pressurise(tq)
            rec.info["CHARGE"] = "end plug + ball valve + 85 PSI  [LOGGED STATE]"
            c.emit_bubbles(chg["seal_holds"])
            px, _ = c.dip_and_grade()
            rec.info["LEAK"] = (f"{px} bubble px -> "
                                f"{'PASS' if px <= mc.bubble_px_max else 'FAIL'}")
            # DEMO camera, not the measurement one -- see make_scene_v5's comment
            for _ in range(int(FPS * 3.0)):
                rec.grab(c.d, "DIP", cam="demo_dip")

    out = out or f"v5_cell_{seed}.mp4"
    sim_s = rec._t_base + rec._t_last
    rec.write(out)
    # Chapter times and duration are expressed against the TRUE simulated clock, not the
    # frame count. Frames are only grabbed inside motion loops, so a frame-count duration
    # understated this cycle by 15% -- fatal for a video whose whole point is "how long
    # does a unit take".
    return out, list(rec.marks), sim_s


# --------------------------------------------------------------- the full reel
#
# DEMO SEEDS ARE TAKEN FROM THE PUBLISHED EVAL SET ON PURPOSE. 1700, 1704 and 1702 are
# rows in stats_v5_route.json, so every figure the HUD shows can be cross-checked against
# the committed artifact. A separate "demo seed" would show a cycle whose result is in no
# artifact at all -- and would burn a fresh seed to do it. These are already spent.
REEL = [(1700, "EASY"), (1704, "MEDIUM"), (1702, "HARD")]


def _card(lines, fname, secs, accent=(41, 121, 255)):
    import imageio
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), (13, 17, 23))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 6], fill=accent)
    y = 90
    for txt, size, bold, col in lines:
        f = _font("sans_bold" if bold else "sans", size)
        d.text(((W - d.textlength(txt, font=f)) / 2, y), txt, font=f, fill=col)
        y += size + 20
    imageio.mimsave(fname, [np.asarray(img)] * int(FPS * secs), fps=FPS,
                    codec="libx264", quality=8, pixelformat="yuv420p")


def make_reel(speed=4.0, out="media/v5_cell_reel.mp4"):
    """Every route end to end, with the numbers and the caveats on the same reel.

    The end card carries FULLY BACKED (22/28), not end-to-end (26/28), because the HARD
    route's handoff is a software decision with no motion behind it. A reel that showed
    the flattering number while the repo published the honest one would be the exact
    failure this project keeps catching.
    """
    import subprocess, imageio_ffmpeg
    st = json.load(open("stats_v5_route.json"))
    mem = json.load(open("stats_v5_membrane.json"))
    W_, G, B = (235, 240, 245), (150, 160, 175), (120, 200, 255)
    A = (255, 180, 90)
    _card([("REFURBISHMENT CELL  --  v5", 54, True, W_),
           ("Modelled on DrinkPrime's own 13 process documents", 26, False, G),
           ("Simulated UFACTORY xArm7  |  MuJoCo 3.11 (pinned)  |  scripted controller", 22, False, G),
           ("", 12, False, (0, 0, 0)),
           ("TRIAGE  ->  CLEAN  ->  VERIFY  ->  MEMBRANE  ->  DIP", 30, True, B),
           ("one unit per route: EASY, MEDIUM, HARD", 24, False, B),
           ("", 12, False, (0, 0, 0)),
           ("Every clip is a unit from the PUBLISHED eval set --", 22, False, A),
           ("seeds 1700 / 1704 / 1702 are rows in stats_v5_route.json", 22, False, A)],
          "card_v5_title.mp4", 5.0)
    parts = ["card_v5_title.mp4"]
    chapters, clock = [(0.0, "TITLE CARD")], 5.0
    for seed, label in REEL:
        f = f"reel_{seed}.mp4"
        _, marks, dur = render_unit(seed, speed, f)
        chapters.append((clock, f"--- {label} route, seed {seed} ---"))
        chapters += [(clock + t, f"    {st}") for t, st in marks]
        clock += dur
        parts.append(f)
    _card([("WHAT THIS RUN MEASURED", 46, True, W_),
           ("", 10, False, (0, 0, 0)),
           (f"triage 97.5% on 120 fresh units   |   missed-hard 0.0%", 26, False, W_),
           (f"clean 100% coverage, 0 missed of 129   |   peak 34.5 N under a 45 N ceiling", 26, False, W_),
           (f"membrane element inserted {mem['elem_inserted']}/10 at 0.30 mm into 1.5 mm clearance", 26, False, W_),
           (f"cap stalls on torque   |   sabotage caught 10/10, false pass 0", 26, False, W_),
           ("", 14, False, (0, 0, 0)),
           (f"routing, {st['n']} held-out units:", 28, True, B),
           (f"right route {st['right_route_n']}/{st['n']}    "
            f"FULLY BACKED {st['fully_backed_n']}/{st['n']}    false-easy 0/{st['n']}", 30, True, B)],
          "card_v5_stats.mp4", 8.0)
    parts.append("card_v5_stats.mp4")
    _card([("WHAT IS NOT REAL, AND WE WILL SAY IT FIRST", 40, True, A),
           ("", 10, False, (0, 0, 0)),
           ("Easy / Medium / Hard: the NAMES are DrinkPrime's, the BOUNDARIES are ours.", 24, False, W_),
           ("CLEAN is a dry pad wipe of the cabinet. No cream, detergent or solution.", 24, False, W_),
           ("The membrane cap is PRESENTED BY A FIXTURE, not fitted by the robot.", 24, False, W_),
           ("Bubbles are MODELLED FROM TORQUE. There is no fluid simulation anywhere.", 24, False, W_),
           ("HARD stops at a human gate -- NO motion delivers the unit there. 0/6 built.", 24, False, W_),
           ("Membrane geometry is PLACEHOLDER until the CAD arrives.", 24, False, W_),
           ("", 12, False, (0, 0, 0)),
           ("This de-risks the approach. It does not de-risk the deployment.", 26, True, G)],
          "card_v5_caveats.mp4", 9.0)
    parts.append("card_v5_caveats.mp4")

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    with open("concat_v5.txt", "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", "concat_v5.txt",
                    "-c", "copy", out], check=True, capture_output=True)
    chapters.append((clock, "STATS CARD")); clock += 8.0
    chapters.append((clock, "CAVEATS CARD")); clock += 9.0
    print(f"wrote {out}  ({len(parts)} parts, {int(clock)//60}:{clock%60:04.1f})")
    print("\nCHAPTERS")
    for t, name in chapters:
        print(f"  {int(t)//60}:{t%60:04.1f}  {name}")
    with open("reel_chapters.txt", "w") as fh:
        for t, name in chapters:
            fh.write(f"{int(t)//60}:{t%60:04.1f}  {name}\n")
    return out


def make_realtime(seed=1704, out="../media/v5_cell_realtime.mp4", v6=False,
                  stroke=False, physical=False, solution=False):
    """ONE complete cycle at TRUE 1x. The runtime IS the cycle time.

    Deliberately not a reel and deliberately not sped up: the question this answers is
    "how long does a unit take", and any speed multiplier -- however honestly stamped --
    makes a viewer do arithmetic to find out.
    """
    import subprocess, imageio_ffmpeg
    W_, G, B, A = (235, 240, 245), (150, 160, 175), (120, 200, 255), (255, 180, 90)
    clip = f"rt_{seed}.mp4"
    raw = f"rt_raw_{seed}.mp4"
    _, marks, dur = render_unit(seed, 1.0, raw, v6=v6, stroke=stroke,
                                physical=physical, solution=solution)
    # RE-TIME so the clip's RUNTIME IS THE CYCLE TIME.
    #
    # Frames are not grabbed at a uniform simulated cadence -- some phases step the sim
    # without invoking the frame callback at all -- so playing the frames at a fixed 30 fps
    # ran 15% FAST (196 s of video for a 231 s cycle). That flatters us, on the one clip
    # whose entire purpose is duration.
    #
    # Stretch with setpts and re-emit at a UNIFORM 30 fps (ffmpeg duplicates frames to
    # fill). Uniform is the honest approximation available: the total is exact, and no
    # phase can be individually corrected without knowing where each dropped frame was.
    # Do NOT do this by setting an input -r and concatenating -- mismatched framerates
    # between the cards and the clip corrupt the timestamps (a 3:51 clip came out 55:23).
    import subprocess as _sp, imageio_ffmpeg as _iff, re as _re
    _ff = _iff.get_ffmpeg_exe()
    probe = _sp.run([_ff, "-i", raw], capture_output=True, text=True).stderr
    m_ = _re.search(r"Duration: (\d+):(\d+):([\d.]+)", probe)
    raw_s = int(m_.group(1)) * 3600 + int(m_.group(2)) * 60 + float(m_.group(3))
    k = dur / raw_s
    _sp.run([_ff, "-y", "-i", raw, "-vf", f"setpts={k:.6f}*PTS", "-r", "30",
             "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", clip], check=True, capture_output=True)
    print(f"  re-timed x{k:.3f}: {raw_s:.1f}s of frames -> {dur:.1f}s real cycle")
    # phase breakdown, from the station marks (already scaled to the true clock)
    seg = [(marks[i][1], (marks[i + 1][0] if i + 1 < len(marks) else dur) - marks[i][0])
           for i in range(len(marks))]
    merged = {}
    for name, d in seg:
        merged[name] = merged.get(name, 0.0) + d
    mm, ss = int(dur) // 60, dur % 60

    _card([(("ONE UNIT, START TO FINISH -- V6" if v6 else "ONE UNIT, START TO FINISH"),
            54, True, W_),
           ("", 12, False, (0, 0, 0)),
           ("REAL TIME  --  NOT SPED UP", 40, True, A),
           ("the length of this clip IS the cycle time", 26, False, G),
           ("", 14, False, (0, 0, 0)),
           ("MEDIUM route (the longest): clean + new membrane + leak test", 26, False, W_),
           (f"{mm} min {ss:04.1f} s per unit", 44, True, B)],
          "card_rt_a.mp4", 6.0)
    lines = [("WHERE THE TIME GOES", 46, True, W_), ("", 10, False, (0, 0, 0))]
    # Only stations that actually consume motion time get a row. TRIAGE and VERIFY are
    # pure camera work and cost ZERO; the dip's ~1.2 s lands inside MEMBRANE because its
    # station marker is set after dip_and_grade has already run. Printing them as
    # "0.0 s" would read as "the dip is free", which is not the same statement.
    shown = [(k, v) for k, v in sorted(merged.items(), key=lambda kv: -kv[1]) if v > 0.05]
    for name, d in shown:
        label = "MEMBRANE + DIP" if name == "MEMBRANE" else name
        lines.append((f"{label:<15} {d:6.1f} s   {d/dur*100:4.1f}%", 30, False, W_))
    lines.append(("", 8, False, (0, 0, 0)))
    lines.append(("TRIAGE and VERIFY cost NO motion time -- they are camera work.",
                  22, False, G))
    lines += [("", 14, False, (0, 0, 0)),
              (f"TOTAL  {mm} min {ss:04.1f} s", 34, True, B),
              ("", 10, False, (0, 0, 0)),
              ("HARD route stops at a person in about 3 seconds.", 22, False, G),
              ("How long this takes a person today: WE DO NOT KNOW -- it is not in the", 22, False, A),
              ("13 process documents, and we have asked. Without it there is no comparison.", 22, False, A)]
    _card(lines, "card_rt_b.mp4", 11.0)

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    with open("concat_rt.txt", "w") as f:
        for q in ("card_rt_a.mp4", clip, "card_rt_b.mp4"):
            f.write(f"file '{q}'\n")
    subprocess.run([ff, "-y", "-f", "concat", "-safe", "0", "-i", "concat_rt.txt",
                    "-c:v", "libx264", "-crf", "26", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                   check=True, capture_output=True)
    print(f"\nwrote {out}   cycle {mm}:{ss:04.1f} at TRUE 1x")
    for name, d in sorted(merged.items(), key=lambda kv: -kv[1]):
        print(f"    {name:<10} {d:7.1f} s  {d/dur*100:5.1f}%"
              if dur > 0 else f"    {name:<10} {d:7.1f} s")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", type=int, help="seed to render")
    ap.add_argument("--realtime", type=int, nargs="?", const=1704, metavar="SEED",
                    help="one full cycle at TRUE 1x + timing cards")
    ap.add_argument("--v6", action="store_true",
                    help="film the V6 targeted cell (fast clean + fast membrane)")
    ap.add_argument("--stroke", action="store_true",
                    help="film the V7 continuous-stroke cell (implies targeted)")
    ap.add_argument("--solution", action="store_true",
                    help="film the V8 solution station: the pad is charged from the "
                         "tray before cleaning (DrinkPrime Stage 3)")
    ap.add_argument("--physical", action="store_true",
                    help="clamp the setpoint rate to the arm's PUBLISHED 180 deg/s "
                         "instead of the 10 rad/s default")
    ap.add_argument("--reel", action="store_true",
                    help="title + one clip per route + stats + caveats -> one file")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="playback speed-up; stamped on frame. 1.5 = slow enough to dissect")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.realtime is not None:
        _dflt = ("../media/v7_cell_realtime.mp4" if a.stroke else
                 "../media/v6_cell_realtime.mp4" if a.v6 else
                 "../media/v5_cell_realtime.mp4")
        make_realtime(a.realtime, a.out or _dflt, v6=a.v6, stroke=a.stroke,
                      physical=a.physical, solution=a.solution)
    elif a.reel:
        make_reel(a.speed if a.speed > 1 else 4.0, a.out or "../media/v5_cell_reel.mp4")
    elif a.render is not None:
        render_unit(a.render, a.speed, a.out, v6=a.v6, stroke=a.stroke,
                    physical=a.physical, solution=a.solution)
    else:
        ap.print_help()
        sys.exit(1)
