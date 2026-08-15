"""
Export refurb-cell episodes as a LeRobot v2.1 dataset.

This is the bridge from the scripted controller to the learned-policy phase: the
scripted cell becomes a demonstration generator, and the demonstrations are written
in the format pi0.5 / OpenPi fine-tuning expects.

Layout produced (LeRobot v2.1):

    <out>/meta/info.json                 dataset + feature schema
    <out>/meta/tasks.jsonl               task_index -> natural-language task
    <out>/meta/episodes.jsonl            per-episode index, tasks, length
    <out>/meta/episodes_stats.jsonl      per-episode feature stats (this is what
                                         makes it v2.1 rather than v2.0, which used
                                         a single global meta/stats.json)
    <out>/data/chunk-000/episode_XXXXXX.parquet
    <out>/videos/chunk-000/observation.images.<cam>/episode_XXXXXX.mp4

Recorded per timestep:
    observation.state   8  measured joint positions (7 arm + gripper)
    action              8  COMMANDED joint positions (7 arm + gripper) -- these are
                           what the controller actually sent, read back from
                           data.ctrl, so the policy learns to imitate the command
                           stream rather than a post-hoc reconstruction.
    observation.images.wrist      wrist camera
    observation.images.overhead   fixed overhead camera
    timestamp / frame_index / episode_index / index / task_index

HONESTY: this writes the v2.1 layout and is validated structurally (parquet reads
back, frame counts match the videos, schemas parse, indices are contiguous). It has
NOT been round-tripped through the real `lerobot` library, which would pull in torch
and a large dependency tree. Treat "loads in LeRobot" as unverified until someone
runs `LeRobotDataset(...)` against it.

Usage:
    python3 lerobot_export.py --episodes 5 --out ../datasets/refurb_v1
    python3 lerobot_export.py --episodes 5 --out ... --validate-only
"""

import argparse, json, os, shutil
import numpy as np
import mujoco

import sim_poc4 as v4
from sim_poc4 import CFG

CODEBASE_VERSION = "v2.1"
ROBOT_TYPE = "ufactory_xarm7"
CHUNK_SIZE = 1000
TASK = ("Refurbish a water filter unit: remove the spent cartridge, inspect it, "
        "then clean and reinstall it or replace it with a fresh one.")

JOINT_NAMES = [f"joint{i}" for i in range(1, 8)] + ["gripper"]


# ------------------------------------------------------------------ recording
class EpisodeRecorder:
    """Hooks sim_poc4's frame_cb. The action is read from data.ctrl, which IS the
    controller's commanded joint position -- no reconstruction, no guessing."""

    def __init__(self, model, size=(256, 256), fps=30):
        self.h, self.w = size
        self.fps = fps
        self.model = model
        self.r = mujoco.Renderer(model, self.h, self.w)
        self.qpos_ids = np.array([model.joint(n).qposadr[0]
                                  for n in (f"joint{i}" for i in range(1, 8))])
        self.act_ids = np.array([model.actuator(f"act{i}").id for i in range(1, 8)])
        self.grip_id = model.actuator("gripper").id
        self.grip_qpos = model.joint("left_driver_joint").qposadr[0] \
            if mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "left_driver_joint") >= 0 else None
        self.steps_per_frame = max(1, int(round(1.0 / fps / model.opt.timestep)))
        self.n = 0
        self.state, self.action, self.tstamp = [], [], []
        self.frames = {"wrist": [], "overhead": []}

    def cb(self, m, d, phase, stage, seed, info):
        self.n += 1
        if self.n % self.steps_per_frame:
            return
        gq = float(d.qpos[self.grip_qpos]) if self.grip_qpos is not None else 0.0
        self.state.append(np.concatenate([d.qpos[self.qpos_ids], [gq]]).astype(np.float32))
        self.action.append(np.concatenate([d.ctrl[self.act_ids],
                                           [d.ctrl[self.grip_id]]]).astype(np.float32))
        self.tstamp.append(float(d.time))
        for key, cam in (("wrist", "wrist"), ("overhead", "top")):
            self.r.update_scene(d, camera=cam)
            self.frames[key].append(np.asarray(self.r.render()).copy())


# ------------------------------------------------------------------ writing
def _stats(arr):
    a = np.asarray(arr, dtype=np.float64)
    if a.ndim == 1:
        a = a[:, None]
    return {"min": a.min(0).tolist(), "max": a.max(0).tolist(),
            "mean": a.mean(0).tolist(), "std": a.std(0).tolist(), "count": [len(a)]}


def _image_stats(frames):
    """Per-channel stats over a subsample, normalised to [0,1] as LeRobot expects."""
    sub = np.stack(frames[:: max(1, len(frames) // 20)]).astype(np.float64) / 255.0
    return {"min": sub.min((0, 1, 2)).reshape(3, 1, 1).tolist(),
            "max": sub.max((0, 1, 2)).reshape(3, 1, 1).tolist(),
            "mean": sub.mean((0, 1, 2)).reshape(3, 1, 1).tolist(),
            "std": sub.std((0, 1, 2)).reshape(3, 1, 1).tolist(),
            "count": [len(frames)]}


def export(n_episodes, out, seed0=0, size=(256, 256), fps=30, dr=None):
    import pyarrow as pa
    import pyarrow.parquet as pq
    import imageio

    out = os.path.abspath(out)
    if os.path.exists(out):
        shutil.rmtree(out)
    for sub in ("meta", "data/chunk-000",
                "videos/chunk-000/observation.images.wrist",
                "videos/chunk-000/observation.images.overhead"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    cfg = CFG
    if dr is not None:
        from dataclasses import replace
        cfg = replace(cfg, dr=True, dr_scale=dr)

    model = mujoco.MjModel.from_xml_path(cfg.xml)
    episodes, ep_stats, total_frames, kept = [], [], 0, 0

    for k in range(n_episodes):
        seed = seed0 + k
        rec = EpisodeRecorder(model, size=size, fps=fps)
        res = v4.run_trial(seed, frame_cb=rec.cb, cfg=cfg)
        if not res["end_to_end"]:
            # Only successful demonstrations are exported. A policy trained on
            # failures learns the failures. This is stated in the dataset card;
            # the skipped seeds are recorded so the selection is not invisible.
            print(f"  ep seed {seed}: SKIPPED (end_to_end=False, route={res['route']})")
            continue
        ei = kept
        n = len(rec.state)
        state = np.stack(rec.state)
        action = np.stack(rec.action)
        # TIMESTAMPS ON THE FRAME GRID, NOT THE SIM CLOCK (fixed 2026-08-15, found by
        # round-tripping through the REAL lerobot library -- the structural validator
        # below passed 26/26 while the library rejected every frame pair). The recorder
        # samples every round((1/fps)/timestep) = 17 physics steps = 0.0340 s of sim
        # time, but fps declares 0.0333 s and the mp4s ARE encoded at exactly 30 fps --
        # so recorded sim time drifts off video time by 0.667 ms/frame, ~31 video frames
        # over a 1578-frame episode, and lerobot's check_timestamps_sync (tolerance
        # 1e-4 s) refuses the dataset. The frames' TRUE spacing in dataset-time is the
        # frame grid. The honest sim clock is not stored as an extra column (an
        # undeclared feature would trip the library's schema checks); it is exactly
        # recoverable as frame_index * steps_per_frame * timestep.
        ts = (np.arange(len(rec.tstamp), dtype=np.float32) / fps).astype(np.float32)
        tbl = pa.table({
            "observation.state": pa.array(state.tolist(), type=pa.list_(pa.float32())),
            "action": pa.array(action.tolist(), type=pa.list_(pa.float32())),
            "timestamp": pa.array(ts, type=pa.float32()),
            "frame_index": pa.array(np.arange(n), type=pa.int64()),
            "episode_index": pa.array(np.full(n, ei), type=pa.int64()),
            "index": pa.array(np.arange(total_frames, total_frames + n), type=pa.int64()),
            "task_index": pa.array(np.zeros(n), type=pa.int64()),
        })
        pq.write_table(tbl, os.path.join(out, f"data/chunk-000/episode_{ei:06d}.parquet"))
        for key in ("wrist", "overhead"):
            imageio.mimsave(
                os.path.join(out, f"videos/chunk-000/observation.images.{key}/episode_{ei:06d}.mp4"),
                rec.frames[key], fps=fps, codec="libx264", quality=8, pixelformat="yuv420p")
        episodes.append({"episode_index": ei, "tasks": [TASK], "length": n})
        ep_stats.append({"episode_index": ei, "stats": {
            "observation.state": _stats(state), "action": _stats(action),
            "timestamp": _stats(ts),
            "frame_index": _stats(np.arange(n)), "episode_index": _stats(np.full(n, ei)),
            "index": _stats(np.arange(total_frames, total_frames + n)),
            "task_index": _stats(np.zeros(n)),
            "observation.images.wrist": _image_stats(rec.frames["wrist"]),
            "observation.images.overhead": _image_stats(rec.frames["overhead"]),
        }})
        total_frames += n
        kept += 1
        print(f"  ep {ei:03d} seed {seed}: {n} frames, route={res['route']}, "
              f"{res['cycle_s']:.1f}s")

    h, w = size
    vinfo = {"video.fps": fps, "video.height": h, "video.width": w,
             "video.channels": 3, "video.codec": "h264", "video.pix_fmt": "yuv420p",
             "video.is_depth_map": False, "has_audio": False}
    info = {
        "codebase_version": CODEBASE_VERSION, "robot_type": ROBOT_TYPE,
        "total_episodes": kept, "total_frames": total_frames, "total_tasks": 1,
        "total_videos": kept * 2, "total_chunks": 1, "chunks_size": CHUNK_SIZE,
        "fps": fps, "splits": {"train": f"0:{kept}"},
        "data_path": "data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet",
        "video_path": "videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4",
        "features": {
            "observation.state": {"dtype": "float32", "shape": [8], "names": JOINT_NAMES},
            "action": {"dtype": "float32", "shape": [8], "names": JOINT_NAMES},
            "observation.images.wrist": {"dtype": "video", "shape": [h, w, 3],
                                         "names": ["height", "width", "channel"], "info": vinfo},
            "observation.images.overhead": {"dtype": "video", "shape": [h, w, 3],
                                            "names": ["height", "width", "channel"], "info": vinfo},
            "timestamp": {"dtype": "float32", "shape": [1], "names": None},
            "frame_index": {"dtype": "int64", "shape": [1], "names": None},
            "episode_index": {"dtype": "int64", "shape": [1], "names": None},
            "index": {"dtype": "int64", "shape": [1], "names": None},
            "task_index": {"dtype": "int64", "shape": [1], "names": None},
        },
    }
    with open(os.path.join(out, "meta/info.json"), "w") as f:
        json.dump(info, f, indent=2)
    with open(os.path.join(out, "meta/tasks.jsonl"), "w") as f:
        f.write(json.dumps({"task_index": 0, "task": TASK}) + "\n")
    with open(os.path.join(out, "meta/episodes.jsonl"), "w") as f:
        for e in episodes:
            f.write(json.dumps(e) + "\n")
    with open(os.path.join(out, "meta/episodes_stats.jsonl"), "w") as f:
        for e in ep_stats:
            f.write(json.dumps(e) + "\n")
    print(f"\nwrote {kept} episodes / {total_frames} frames to {out}")
    return out


# ------------------------------------------------------------------ validation
def validate(out):
    """Structural validation. This is NOT a LeRobot round-trip -- see module docstring."""
    import pyarrow.parquet as pq
    import imageio
    ok = True

    def chk(cond, msg):
        nonlocal ok
        print(("  PASS  " if cond else "  FAIL  ") + msg)
        ok = ok and cond

    info = json.load(open(os.path.join(out, "meta/info.json")))
    chk(info["codebase_version"] == "v2.1", "info.json codebase_version == v2.1")
    # THE CHECK THAT WAS MISSING (2026-08-15): 26/26 structural checks passed on a
    # dataset the real library rejected on every frame pair, because nothing here ever
    # compared the timestamp column against the declared fps. A validator that never
    # reads the quantity the consumer's first assertion reads is the blind-verifier
    # defect in a new costume.
    import numpy as _np
    _fps = float(info["fps"])
    for _f in sorted(os.listdir(os.path.join(out, "data/chunk-000")))[:1]:
        _t = pq.read_table(os.path.join(out, "data/chunk-000", _f))
        _tsc = _np.asarray(_t.column("timestamp"))
        _d = _np.diff(_tsc)
        chk(bool(_np.all(_np.abs(_d - 1.0 / _fps) < 1e-4)),
            f"timestamps advance on the declared frame grid (1/fps) -- worst "
            f"|dt-1/fps| {_np.max(_np.abs(_d - 1.0/_fps))*1e6:.0f} us "
            f"(lerobot tolerance 100 us)")
    eps = [json.loads(l) for l in open(os.path.join(out, "meta/episodes.jsonl"))]
    sts = [json.loads(l) for l in open(os.path.join(out, "meta/episodes_stats.jsonl"))]
    chk(len(eps) == info["total_episodes"], f"episodes.jsonl has {info['total_episodes']} rows")
    chk(len(sts) == len(eps), "episodes_stats.jsonl matches episode count (v2.1 requirement)")
    chk(os.path.exists(os.path.join(out, "meta/tasks.jsonl")), "tasks.jsonl present")

    total, running = 0, 0
    for e in eps:
        ei = e["episode_index"]
        t = pq.read_table(os.path.join(out, f"data/chunk-000/episode_{ei:06d}.parquet"))
        d = t.to_pydict()
        chk(t.num_rows == e["length"], f"ep{ei}: parquet rows == declared length ({e['length']})")
        chk(set(info["features"]) - {"observation.images.wrist", "observation.images.overhead"}
            <= set(t.column_names), f"ep{ei}: all non-video features present as columns")
        chk(len(d["observation.state"][0]) == 8 and len(d["action"][0]) == 8,
            f"ep{ei}: state and action are 8-dim")
        chk(d["frame_index"] == list(range(t.num_rows)), f"ep{ei}: frame_index contiguous from 0")
        chk(d["index"][0] == running, f"ep{ei}: global index continues from previous episode")
        running += t.num_rows
        for key in ("wrist", "overhead"):
            p = os.path.join(out, f"videos/chunk-000/observation.images.{key}/episode_{ei:06d}.mp4")
            rd = imageio.get_reader(p)
            nf = rd.count_frames()
            rd.close()
            chk(abs(nf - t.num_rows) <= 1, f"ep{ei}: {key} video frames ({nf}) match rows ({t.num_rows})")
        total += t.num_rows
    chk(total == info["total_frames"], f"total_frames ({info['total_frames']}) matches sum of episodes")
    print("\n  NOTE: structural validation only. Not round-tripped through the real")
    print("  `lerobot` library (that needs torch); 'loads in LeRobot' stays UNVERIFIED.")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--out", default="../datasets/refurb_v1")
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--dr", type=float, default=None)
    ap.add_argument("--validate-only", action="store_true")
    a = ap.parse_args()
    path = os.path.abspath(a.out)
    if not a.validate_only:
        path = export(a.episodes, a.out, seed0=a.seed0, size=(a.size, a.size), dr=a.dr)
    print("\nVALIDATING")
    raise SystemExit(0 if validate(path) else 1)
