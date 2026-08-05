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

CAVEAT = {
    "TRIAGE": "NO ARM MOTION HERE -- the arm parks clear, the turntable is stepped to each "
              "face and a FIXED camera grades pixels. NAMES theirs, BOUNDARIES ours.",
    "CLEAN": "No cream, detergent or chemistry is simulated. What is verified is that the "
             "soil the camera could see is gone.",
    "VERIFY": "NO ARM MOTION -- cameras only. Re-inspected through a SECOND camera: the "
              "triage camera cannot see the top face, and that is the face cleaning misses.",
    "MEMBRANE": "The ARM really inserts the element. The CAP IS NOT TURNED BY THE ARM -- a "
                "station driver spins it, and the fixture presents it. Geometry PLACEHOLDER.",
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

    def grab(self, d, station, cam="main", inset=None):
        if not self.marks or self.marks[-1][1] != station:
            self.marks.append((len(self.frames), station))
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


def render_unit(seed, speed=1.0, out=None):
    c = RT.RouteCell()
    rec = Recorder(c.m, speed)
    every = max(1, int(round(speed / (FPS * c.dt))))

    # ---------------- TRIAGE
    row = c.grade(seed)
    grade, truth = row["pred"], row["truth"]
    route = RT.GRADE_ROUTE[grade]
    plan = DP.V5_ROUTES[route].steps
    rec.chips = (["TRIAGE", "SCRAP"] if route == "hard_non_rectifiable"
                 else ["TRIAGE", "CLEAN", "VERIFY"] +
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
        frames = {"f": rec.frames, "max": 10_000, "every": every,
                  "cb": lambda tag: (rec.info.__setitem__("STEP", tag),
                                     rec.grab(c.d, "CLEAN", inset="verify_top"))}
        cr = super(RT.MB.MemCell, c).run(seed, frames=frames)
        rec.info["COVERAGE"] = f"{cr['coverage']*100:.1f}%  peak {cr['f_max']:.1f} N"
        rec.info.pop("STEP", None)

        # ---------------- VERIFY
        v = c.verify()
        rec.info["VERIFY"] = (f"residue {v['soil_left_truth']} -> "
                              f"{'VERIFIED' if v['verified'] else 'FAILED'}")
        for _ in range(int(FPS * 2.0)):
            rec.grab(c.d, "VERIFY", inset="verify_top")

        if route != "easy":
            # ---------------- MEMBRANE INSERT (3.4), then multi-turn to torque
            c.reset_mem(seed)
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
                "cb": lambda tag: (rec.info.__setitem__("STEP", tag),
                                   rec.grab(c.d, "MEMBRANE", cam="main",
                                            inset="demo_mem"))})
            rec.info["INSERT"] = (
                f"aligned {ins['align_mm']:.2f} mm -> seated {ins['seat_xy_mm']:.2f} mm "
                f"off-axis, {'IN' if ins['inserted'] else 'NOT SEATED'}")
            rec.info.pop("STEP", None)
            # the cap is PRESENTED by the fixture, engaged on the first thread -- a
            # declared de-scope, NOT a robot motion, and the frame says so
            c.cap_present(True)
            mujoco.mj_forward(c.m, c.d)
            for _ in range(int(FPS * 1.2)):
                rec.grab(c.d, "MEMBRANE", cam="main", inset="demo_mem")
            t, held, hist = 0.0, 0.0, []
            win = max(int(0.1 / c.dt), 1)
            k = 0
            while t < mc.drive_t_max:
                c.d.ctrl[c.capdrv] = mc.drive_rate
                c.d.qfrc_applied[c.dof] = c.d.qfrc_bias[c.dof]
                mujoco.mj_step(c.m, c.d)
                t += c.dt
                k += 1
                if k % every == 0:
                    rec.info["TIGHTEN"] = (f"{c.turns():5.2f} turns  {c.torque():4.2f} Nm  "
                                           f"seal {c.seal_load():4.0f} N")
                    rec.grab(c.d, "MEMBRANE", cam="main", inset="demo_mem")
                hist.append(float(c.d.qpos[c.cap_z_q]))
                if len(hist) > win:
                    hist.pop(0)
                    dz = abs(hist[-1] - hist[0]) / (win * c.dt) * 1e6
                    if c.torque() >= 0.98 * mc.torque_target_nm and dz < mc.stall_dz_um_s:
                        held += c.dt
                        if held >= mc.stall_hold_s:
                            break
                    else:
                        held = 0.0
            c.d.ctrl[c.capdrv] = 0.0
            tq = c.torque()
            stalled = bool(held >= mc.stall_hold_s)
            rec.info["TIGHTEN"] = (
                f"{c.turns():5.2f} turns  {tq:4.2f} Nm  "
                f"{'STALLED' if stalled else 'NO STALL'} "
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
    rec.write(out)
    return out, [(i / FPS, st) for i, st in rec.marks], len(rec.frames) / FPS


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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--render", type=int, help="seed to render")
    ap.add_argument("--reel", action="store_true",
                    help="title + one clip per route + stats + caveats -> one file")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="playback speed-up; stamped on frame. 1.5 = slow enough to dissect")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.reel:
        make_reel(a.speed if a.speed > 1 else 4.0, a.out or "../media/v5_cell_reel.mp4")
    elif a.render is not None:
        render_unit(a.render, a.speed, a.out)
    else:
        ap.print_help()
        sys.exit(1)
