# Architecture

Technical reference for `sim_poc/sim_poc2.py`. For the non-technical version see
[HOW_IT_WORKS.md](HOW_IT_WORKS.md); for measured outcomes see [RESULTS.md](RESULTS.md).

## Shape of the program

One file, no framework. `run_trial(seed)` executes a complete attempt and returns a
result dict; `evaluate(n)` runs `n` of them and writes `stats.json`. Rendering is an
optional callback (`frame_cb`) invoked once per simulation step — which makes it a
convenient tracing seam for debugging, since it needs no fonts or video encoding.

```
run_trial(seed)
  ├─ reset to keyframe, place cartridge at a random pose
  ├─ simulated perception (true pose + gaussian noise)
  ├─ phase state machine  ── per step ──▶ target pose
  │                                       └─▶ damped-least-squares IK
  │                                            └─▶ joint position actuators
  └─ verification → {seated, locked, xy_offset, twist, ...}
```

## Scene geometry

Defined in `ufactory_xarm7/cartridge_scene_v2.xml`. The controller constants in
`sim_poc2.py` are derived from these numbers and **must be kept consistent with them.**

| Feature | Value |
|---|---|
| Cartridge body | cylinder r = 21.5 mm, half-length 55 mm (110 mm tall), 0.28 kg |
| Bayonet lugs | 2 boxes at local z = −49 mm, outer radius 34 mm |
| Collar bore | inner radius 24.5 mm → **3.0 mm radial clearance**, spans z 58–100 mm |
| Chamfer funnel | 45°, spans z 98.5–126.1 mm; **mouth at z = 126.1 mm** |
| Entry slots | two gaps in the collar centred on ±90° (world y) |
| Pedestal seat | top at z = 45 mm → seated cartridge centre at z = 100 mm (`SEAT_Z`) |
| Socket centre | world (0.46, 0.26); tray spawn centre (0.46, −0.26) |

Derived: the cartridge's bottom face is at `cart_centre_z − 55 mm`, so it first
contacts the funnel mouth when its centre is at **≈181 mm**. That number drives the
insertion logic.

## Control loop

Per simulation step (`dt` = model timestep, `base_step = 2·dt`):

1. **Yaw command.** During servo phases, a closed loop drives the *measured cartridge*
   yaw onto the slot axis (π/2, mod π — the lugs are 2-fold symmetric). Note the sign
   flip: commanded wrist yaw maps to **negative** physical yaw via `down_mat`.
2. **Lateral command.** Phase-dependent (see below).
3. **IK.** Damped least squares on the 6-DOF site error, `damping = 0.1`, `gain = 0.3`.
   Planned on the **commanded** configuration (`ik_data`), not measured state — this is
   deliberate; servoing on measured state oscillates.
4. **Rate limit.** `dq` is scaled to `max|dq| ≤ base_step · speed_scale`,
   **direction-preserving**. The original clipped element-wise, which distorts the
   joint-space direction whenever any joint saturates — so a large commanded step made
   the tool travel somewhere other than straight down.
5. **Gravity compensation.** `qfrc_applied = qfrc_bias`; the position actuators sag
   otherwise.

### Phase table

`P` is a list of `(name, tcp_xyz, grip, dwell_s, tol_m, speed_scale, servo, max_s)`.
A phase advances when its completion condition has held for `dwell_s`; exceeding
`max_s` triggers retry or abort.

```
PERCEPTION → APPROACH → DESCEND → GRASP → LIFT → TRANSIT
    → [RECOVER GRIP → RECOVER LIFT]   (skipped on the normal path)
    → ORIENT LUGS → PRE-INSERT → INSERT → DROP-SEAT
    → REGRIP ALIGN → REGRIP CAP → TWIST-LOCK → RELEASE → RETREAT
```

Completion conditions are judged on **the part** wherever the part is what matters:

| Phase | Completes when |
|---|---|
| ORIENT LUGS, PRE-INSERT | part within `ENTRY_TOL` of the socket axis, tilt < 3°, yaw aligned < 4° |
| INSERT | wrist below 129 mm **and** part upright (> `INSERT_UPRIGHT`) **and** part below `INSERT_DEPTH_Z` |
| DROP-SEAT | part has fallen to within 8 mm of `SEAT_Z` |
| TWIST-LOCK | elapsed > 1.2 s (open-loop ramp) |
| others | TCP within `tol` of target |

### The insertion law

This is where all the difficulty lives. Three regimes:

```python
if servo and name == "INSERT":
    tip = cart_centre + R_cart @ [0, 0, -CART_HALF]      # the bottom face
    if hold_e is None:                                   # latch once, at entry
        hold_e = clip(tcp_xy - tip[:2], ±GRIP_ECC_MAX)   # in-jaw eccentricity
    tgt[:2] = tip[:2] + hold_e                           # hang plumb over the tip
    tgt[2]  = max(tgt[2], tcp_z - Z_LAG)                 # bounded feed lead
elif servo:
    tgt[:2] = tcp_xy + (SOCK - cart_xy)                  # coarse centering
elif name in FOLLOW:
    tgt[:2] = cart_xy                                    # track the part
```

Two properties matter:

- **Tip, not centre.** A tilting part swings its centre sideways; following the centre
  chases and amplifies the tilt. The tip is what's inside the funnel.
- **Bounded feed lead.** `tgt[2]` is never more than `Z_LAG` below the *measured* wrist
  height, so the IK residual stays small and the rate limiter never saturates. The
  original commanded the full 64 mm drop as one absolute step.

The coarse-centering law `tcp + (SOCK − cart)` is retained for the approach phases,
where the part hangs free. It is **only** unsafe once the part is in contact, because
then it becomes an unbounded integrator against a constraint — see RESULTS.md.

### Recovery

`RECOVER GRIP` and `RECOVER LIFT` sit in `P` between TRANSIT and ORIENT LUGS but are
skipped during normal forward progress:

```python
while wp < len(P) and P[wp][0].startswith("RECOVER"):
    wp += 1
```

They are entered only by the retry jump, which fires on an INSERT **or** DROP-SEAT
timeout (up to 2 retries). `RECOVER GRIP` is in `FOLLOW`, so it closes the jaws where
the part *actually is* — a wedged part sits 20–35 mm off-axis — then `RECOVER LIFT`
raises to 300 mm to clear the collar before re-approaching.

## Verification

A trial is `seated` if `xy_offset < 6 mm`, `height < SEAT_Z + 8 mm`, and
`upright > 0.95`; `locked` additionally requires `rel_twist > 30°`, measured against
the part's yaw at the end of insertion. These thresholds are unchanged from the
original and **should not be relaxed** — they are the definition of success.

## Known constraints

- Grasp: the finger **pads** sit ~25 mm above the `link_tcp` site. `GRASP_OFF` is tuned
  so they land mid-body; changing it blindly breaks the grasp (and it is already at its
  practical optimum — lower and the gripper palm fouls the cartridge cap).
- The `home` keyframe predates the cartridge free joint, so its qpos must be set
  explicitly after `mj_resetDataKeyframe`.
- Single fixed set of physical parameters — no domain randomization yet. Mass,
  friction and table height are all exactly known, which is not true on real hardware.
- Perception is simulated by reading ground truth and adding noise. There is no actual
  vision pipeline; a real one is a substantial separate problem.
