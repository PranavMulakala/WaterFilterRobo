"""V5-C diagnostic -- WHERE are the cleaning misses, before changing anything.

    ../venv/bin/python v5_clean_diag.py --run 800
    ../venv/bin/python v5_clean_diag.py --eval 4 --seed0 800

This does NOT reimplement the cleaning cycle. It SUBCLASSES it and overrides two
methods, so every number below comes out of the controller that actually runs in
v5_clean.py. Reimplementing the loop to measure it is how you end up measuring the
measuring equipment -- which this project has now done about twenty times.

What it answers, in order of how much it would change the fix:

  1. Which FACE are the missed patches on?  A whole missing face and a uniformly leaky
     raster need completely different fixes.
  2. Did the INDEXER actually go where it was told?  Commanded angle != achieved angle
     is invisible from the coverage number alone.
  3. For each missed patch: did the pad ever get NEAR it (a contact problem) or never
     come close (a raster-geometry problem)?
  4. Where on the face do misses cluster -- edges, the facia band, the bottom?
"""
import argparse
from collections import defaultdict

import numpy as np
import mujoco

import v5_clean as CL


def face_of(local, depth=0.18, width=0.25, height=0.45, tol=0.02):
    """Name the face a patch sits on, from its position in the CABINET's own frame."""
    x, y, z = local
    if z > height - tol:
        return "top"
    if x < -depth / 2 + tol:
        return "front"
    if x > depth / 2 + tol / 2:
        return "back"
    if y < -width / 2 + tol:
        return "left"
    if y > width / 2 - tol:
        return "right"
    return "?"


class DiagCell(CL.Cell):
    def reset(self, seed):
        out = super().reset(seed)
        m, d = self.m, self.d
        cab = m.body("cabinet").id
        p0, R0 = d.xpos[cab], d.xmat[cab].reshape(3, 3)
        self.local = {g: R0.T @ (d.geom_xpos[g] - p0) for g in self.revealed_soil}
        self.face = {g: face_of(self.local[g]) for g in self.revealed_soil}
        # closest the PAD CONTACT SURFACE ever came to each patch, in-plane and normal
        self.best = {g: (9.9, 9.9, 0.0) for g in self.revealed_soil}
        self.tag = ""
        self.index_log = defaultdict(list)
        self.pts = []            # one row per raster point
        self.moves = []          # one row per move() call, wipes included
        self.probe_n = self.probe_none = 0
        self.probe_hit = {}
        self._pt = None
        return out

    # ---- the surface probe. It fires from x = 0.20 toward +X, which is straight
    #      THROUGH the space the arm and the pad occupy while wiping. Any raster point
    #      whose ray lands on a link instead of the device returns None and the
    #      controller silently `continue`s -- no wipe, no force sample, no count.
    def surface_x(self, y, z):
        out = super().surface_x(y, z)
        self.probe_n += 1
        if out is None:
            self.probe_none += 1
            pnt = np.array([0.20, y, z])
            gid = np.zeros(1, np.int32)
            dist = mujoco.mj_ray(self.m, self.d, pnt, np.array([1.0, 0.0, 0.0]),
                                 self.geomgroup, 1, -1, gid)
            b = (mujoco.mj_id2name(self.m, mujoco.mjtObj.mjOBJ_BODY,
                                   self.m.geom_bodyid[gid[0]]) or "?") \
                if (dist >= 0 and gid[0] >= 0) else "nothing"
            self.probe_hit[b] = self.probe_hit.get(b, 0) + 1
        return out

    # ---- record every wipe step, whether or not the pad is in contact
    def wipe(self):
        f = self.pad_contact_force()
        centre = self.d.geom_xpos[self.pad_face]
        R = self.d.geom_xmat[self.pad_face].reshape(3, 3)
        n_hat = R[:, 2]
        for g in self.revealed_soil:
            if self.m.geom_rgba[g][3] <= 0:
                continue
            v = self.d.geom_xpos[g] - centre
            out = float(v @ n_hat)
            inplane = float(np.linalg.norm(v - out * n_hat))
            if inplane < self.best[g][0]:
                self.best[g] = (inplane, abs(out), f)
        if self._pt is not None:
            self._pt["fmax"] = max(self._pt["fmax"], f)
            self._pt["n"] += 1
            if f >= self.cfg.contact_min_n:
                self._pt["touch"] += 1
        return super().wipe()

    # ---- record the indexer's ACHIEVED angle, and per-raster-point contact
    def move(self, tgt, mat, grip, index_deg=0.0, tol=0.004, t_max=6.0,
             wipe=False, log=None, frames=None, tag=""):
        if wipe:
            self._pt = {"tag": tag, "tgt": np.array(tgt, float), "fmax": 0.0,
                        "n": 0, "touch": 0, "t_max": t_max}
        out = super().move(tgt, mat, grip, index_deg, tol, t_max, wipe, log, frames, tag)
        if wipe:
            err = float(np.linalg.norm(self.d.site_xpos[self.site] - tgt))
            self._pt["arrived"] = err < tol
            self._pt["err_mm"] = err * 1000
            self._pt["cleaned"] = out
            self._pt["tcp"] = self.d.site_xpos[self.site].copy()
            self._pt["pad"] = self.d.geom_xpos[self.pad_face].copy()
            self._pt["acf"] = float(self.d.qpos[self.acf_q])
            self.pts.append(self._pt)
            self._pt = None
        self.index_log[tag].append(
            (index_deg, float(np.degrees(self.d.qpos[self.tt_q]))))
        # every move, not just the wipes -- a face pass that starts from a bad approach
        # is doomed before the first raster point, and the raster stats cannot show that
        q = self.q_des
        sat = int(np.sum((q - self.rng_j[:, 0] < 1e-3) | (self.rng_j[:, 1] - q < 1e-3)))
        # THE DECISIVE SPLIT. Where the COMMANDED configuration puts the TCP tells you
        # whether the IK converged; the gap between commanded and measured joints tells
        # you whether the arm tracked it. They are different bugs with different fixes.
        self.ik.qpos[:] = self.d.qpos
        self.ik.qpos[self.qadr] = self.q_des
        mujoco.mj_kinematics(self.m, self.ik)
        cmd_tcp = self.ik.site_xpos[self.site].copy()
        self.moves.append({
            "tag": tag, "tgt": np.array(tgt, float),
            "tcp": self.d.site_xpos[self.site].copy(),
            "err_mm": float(np.linalg.norm(self.d.site_xpos[self.site] - tgt)) * 1000,
            "ik_mm": float(np.linalg.norm(cmd_tcp - tgt)) * 1000,
            "lag_rad": float(np.max(np.abs(self.q_des - self.d.qpos[self.qadr]))),
            "tol_mm": tol * 1000, "sat": sat, "wipe": wipe,
        })
        return out

    # ---- record the geometry each face pass actually planned against
    def front_face_plane(self, index_deg):
        out = super().front_face_plane(index_deg)
        cab = self.m.body("cabinet").id
        R = self.d.xmat[cab].reshape(3, 3)
        tcp = self.d.site_xpos[self.site]
        Rn = self.d.site_xmat[self.site].reshape(3, 3)
        if not hasattr(self, "planes"):
            self.planes = []
        self.planes.append({
            "cmd": index_deg, "plane": out,
            "tt": float(np.degrees(self.d.qpos[self.tt_q])),
            "cab_xpos": self.d.xpos[cab].copy(),
            "cab_tilt": float(np.degrees(np.arccos(np.clip(R[2, 2], -1, 1)))),
            "pad_rel": Rn.T @ (self.d.geom_xpos[self.pad_face] - tcp),
            "acf": float(self.d.qpos[self.acf_q]),
        })
        return out


def diagnose(seed, quiet=False):
    c = DiagCell()
    r = c.run(seed)
    m = c.m

    # ---------- 1. indexer: commanded vs achieved
    print(f"\n=== seed {seed}  coverage {r['coverage']*100:.1f}% "
          f"({r['cleaned']}/{r['soil0']}) ===")
    print("\n  INDEXER  commanded -> achieved (last sample of each phase)")
    for tag, rows in c.index_log.items():
        if not tag.startswith(("WIPE", "INDEX")):
            continue
        cmd = rows[-1][0]
        ach = [a for _, a in rows]
        print(f"    {tag:<12} cmd {cmd:>6.1f} deg   achieved "
              f"{ach[0]:>7.1f} .. {ach[-1]:>7.1f} deg"
              f"{'   <-- MISMATCH' if abs(((ach[-1]-cmd+180)%360)-180) > 3 else ''}")

    # ---------- 2. misses by face
    print("\n  MISSES BY FACE")
    tot = defaultdict(int)
    miss = defaultdict(int)
    for g in c.revealed_soil:
        f = c.face[g]
        tot[f] += 1
        if m.geom_rgba[g][3] > 0:
            miss[f] += 1
    for f in ("front", "right", "back", "left", "top"):
        if not tot[f]:
            continue
        print(f"    {f:<7} {tot[f]-miss[f]:>3}/{tot[f]:<3} cleaned "
              f"({(tot[f]-miss[f])/tot[f]*100:5.1f}%)"
              f"{'   <-- ENTIRE FACE MISSED' if miss[f] == tot[f] else ''}")

    # ---------- 3. why each miss was missed
    print("\n  WHY MISSED (closest pad approach, in-plane / normal / force there)")
    R = c.cfg.pad_radius * 1000
    reach = c.cfg.pad_reach * 1000
    buckets = defaultdict(int)
    for g in c.revealed_soil:
        if m.geom_rgba[g][3] <= 0:
            continue
        ip, out, f = c.best[g]
        ip, out = ip * 1000, out * 1000
        if ip > 200:
            why = "pad NEVER on this face"
        elif ip > R:
            why = f"raster gap: closest {ip:.0f} mm > {R:.0f} mm radius"
        elif out > reach:
            why = f"pad too far off plane: {out:.0f} mm > {reach:.0f} mm"
        else:
            why = f"in reach but NO CONTACT (f={f:.1f} N)"
        buckets[(c.face[g], why)] += 1
    for (f, why), n in sorted(buckets.items(), key=lambda kv: -kv[1]):
        print(f"    {n:>3}  {f:<7} {why}")

    # ---------- 4. where on the face
    print("\n  MISSED PATCH POSITIONS (cabinet-local, mm)")
    for f in ("front", "right", "back", "left", "top"):
        ms = [c.local[g] * 1000 for g in c.revealed_soil
              if m.geom_rgba[g][3] > 0 and c.face[g] == f]
        if not ms:
            continue
        a = np.array(ms)
        print(f"    {f:<7} n={len(ms):<3} x {a[:,0].min():7.1f}..{a[:,0].max():7.1f}  "
              f"y {a[:,1].min():7.1f}..{a[:,1].max():7.1f}  "
              f"z {a[:,2].min():7.1f}..{a[:,2].max():7.1f}")

    # ---------- 3b. the non-raster moves, in order -- did the arm ever get set up?
    print("\n  SETUP MOVES (non-raster), in order")
    for mv in c.moves:
        if mv["wipe"]:
            continue
        blame = ("IK never solved it" if mv["ik_mm"] > mv["tol_mm"] * 3
                 else "arm did not track" if mv["err_mm"] > mv["tol_mm"] * 3 else "")
        print(f"    {mv['tag']:<10} want {np.round(mv['tgt'],3)} got "
              f"{np.round(mv['tcp'],3)}  err {mv['err_mm']:7.1f} mm | IK-cmd off by "
              f"{mv['ik_mm']:7.1f} mm | joint lag {mv['lag_rad']:.3f} rad | "
              f"at limit {mv['sat']}  {blame}")

    # ---------- 3c. per-face raster error trace: fails at once, or drifts in?
    print("\n  RASTER ERROR TRACE (first 8 points of each face pass)")
    seen = set()
    for mv in c.moves:
        if not mv["wipe"] or mv["tag"] in seen:
            continue
        rows = [x for x in c.moves if x["wipe"] and x["tag"] == mv["tag"]]
        seen.add(mv["tag"])
        head = "  ".join(f"{x['err_mm']:.0f}" for x in rows[:8])
        print(f"    {mv['tag']:<12} err mm: {head} ...  "
              f"(max jnts at limit {max(x['sat'] for x in rows)})")

    # ---------- 4b. what geometry each pass planned against
    print("\n  PER-PASS PLAN (front_face_plane, as the controller saw it)")
    for p in getattr(c, "planes", []):
        fx, cy, hw, z0, z1 = p["plane"]
        print(f"    cmd {p['cmd']:>6.1f} tt {p['tt']:>7.1f} | fx {fx:.4f} cy {cy:+.4f} "
              f"hw {hw:.4f} z {z0:.4f}..{z1:.4f} | cab xyz "
              f"{np.round(p['cab_xpos'],4)} tilt {p['cab_tilt']:.1f} deg | "
              f"pad_rel {np.round(p['pad_rel'],4)} acf {p['acf']*1000:+.1f} mm")

    # ---------- 4c. the surface probe: how many raster points were never attempted
    print("\n  SURFACE PROBE (rays that never found the device -> point silently skipped)")
    print(f"    {c.probe_none} of {c.probe_n} raster points skipped "
          f"({c.probe_none/max(c.probe_n,1)*100:.1f}%) -- these are commanded by the")
    print("    raster, never executed, and never appear in the force or contact stats.")
    for b, n in sorted(c.probe_hit.items(), key=lambda kv: -kv[1])[:6]:
        print(f"      ray landed on {b:<22} x{n}")

    # ---------- 5. the raster itself
    print("\n  RASTER POINTS (contact + arrival, per face pass)")
    byface = defaultdict(list)
    for p in c.pts:
        byface[p["tag"]].append(p)
    for tag, ps in byface.items():
        touch = sum(p["touch"] for p in ps)
        nn = sum(p["n"] for p in ps)
        never = sum(1 for p in ps if p["touch"] == 0)
        arr = sum(1 for p in ps if p["arrived"])
        errs = np.array([p["err_mm"] for p in ps])
        print(f"    {tag:<12} {len(ps):>3} pts | contact {touch/max(nn,1)*100:5.1f}% of "
              f"steps | {never:>3} pts NEVER touched | arrived {arr}/{len(ps)} | "
              f"err med {np.median(errs):5.1f} mm max {errs.max():5.1f} mm")
        w = max(ps, key=lambda p: p["err_mm"])
        print(f"        worst pt: want tcp {np.round(w['tgt'],3)} got "
              f"{np.round(w['tcp'],3)} | pad at {np.round(w['pad'],3)} "
              f"acf {w['acf']*1000:+.1f} mm")
    return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int)
    ap.add_argument("--eval", type=int)
    ap.add_argument("--seed0", type=int, default=800)
    a = ap.parse_args()
    if a.run is not None:
        diagnose(a.run)
    else:
        for k in range(a.eval or 1):
            diagnose(a.seed0 + k)
