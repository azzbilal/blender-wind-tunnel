# ANIMATION A+B spec (pressure slice sweep + smoke over the map)

Slice prompt: `docs/prompts/anim_ab.md`. Grill answers are locked here before any code.
Data: `~/wind_tunnel/_anim/Cube`, steady solution at t = 1831 (gated, window-mean Cd 1.14978).

## Geometry the decisions rest on (field.npz at 1831)

- Voxel grid: x -2.5 to 6.0 m, y and z -2.5 to 2.5 m, h = 0.05 m (171 x 101 x 101).
- Body (cube): -1 to 1 m on every axis, L = 2 m. The grid reaches only 1.25 L either side in y and z.
- Cp over fluid voxels: -0.700 to 1.025.

## Q1 Sweep design: LOCKED 2026-10-22

- Default axis Y (the XZ slice moves side to side through the body); the panel offers X / Y / Z.
  X and Z sweeps turn the plane to face the sweep axis.
- Range plus/minus 1.0 L (plus/minus 2.0 m) about the body centre, clamped to the field grid minus a
  margin (for Y the plane stays 10 voxels inside the grid edge; for X the grid is -2.5 to 6.0 m).
- 192 frames (8 s at 24 fps), ping-pong at constant speed: -range to +range in 96 frames and back.
- One keyframe per frame on WT Slice's location only. Each frame samples the solved field at the
  slice's true position; nothing is interpolated in the data.
- Panel button "Animate slice" writes the keyframes, replacing any earlier ones (never stacking),
  and sets the scene frame range to 1..192. Button "Clear" removes them.
- Label "WT Label" is built in Geometry Nodes (String to Curves), reading WT Slice's location
  through Object Info and the Pressure toggle, so it updates in viewport and render with no Python
  handler. Text: `Slice y = +0.85 m (+0.43 L) | Cp` or `| speed/U_inf` in speed mode.

## Q2 Colour (diverging Cp ramp, stops, range, legend): LOCKED 2026-10-22

- Range lo = -1.0, hi = +1.0, ends clamped; lo and hi are modifier inputs (other bodies may widen).
  Red end: Cp = 1 is the incompressible stagnation limit (Bernoulli). Blue end: Cp = -1 is
  |U| = sqrt(2) U_inf; the cube's deepest voxel suction (-0.70) lands near 0.15 on the ramp.
- The field's Cp peak 1.025 clamps to full red. Cause already explained in
  `docs/reviews/step1_review.md` (3.4 table): the inlet fixes U uniform while p is raised near the
  axis, so the stagnation streamline enters about 1.031 q above the inlet mean and loses about
  0.008 q on the way. That is open issue (c), inlet non-uniformity, for FIX_PLAN step 4; not a new item.
- Mapping is two-sided, `cp_to_ramp(cp, lo, hi)`: cp in [lo, 0] -> [0, 0.5], cp in [0, hi] -> [0.5, 1],
  clamped outside. Cp = 0 always hits the neutral stop, also for an asymmetric range.
- Stops: Moreland cool-warm, 9 stops. Endpoints cited from Moreland 2009, "Diverging Color Maps for
  Scientific Visualization"; the intermediates are computed with our own implementation of his Msh
  interpolation (not quoted). ColorRamp elements receive the linear column.

| t | Cp at lo/hi = -1/+1 | sRGB (0-255) | linear RGB |
|---|---|---|---|
| 0.000 | -1.00 | 59, 76, 192 | 0.0437, 0.0723, 0.5271 |
| 0.125 | -0.75 | 98, 130, 234 | 0.1219, 0.2224, 0.8213 |
| 0.250 | -0.50 | 141, 176, 254 | 0.2669, 0.4320, 0.9890 |
| 0.375 | -0.25 | 184, 208, 249 | 0.4805, 0.6276, 0.9474 |
| 0.500 | 0 | 221, 221, 221 | 0.7207, 0.7207, 0.7205 |
| 0.625 | +0.25 | 245, 196, 173 | 0.9096, 0.5541, 0.4174 |
| 0.750 | +0.50 | 244, 154, 123 | 0.9080, 0.3222, 0.1975 |
| 0.875 | +0.75 | 222, 97, 76 | 0.7285, 0.1184, 0.0731 |
| 1.000 | +1.00 | 180, 4, 38 | 0.4564, 0.0012, 0.0194 |

- Speed keeps SPEED_STOPS over 0.3 to 1.9 U_inf.
- Slice material: the Cp branch gets its own ColorRamp (second material via Switch + Set Material,
  or two ramps mixed in one material; decided in Stage 3). Closes open item a.
- Legend "WT Legend": Geometry Nodes strip at a fixed place by the grid edge (not parented to the
  slice), its own coordinate through the active ramp, String to Curves ticks: Cp -1.0, -0.5, 0,
  +0.5, +1.0 with end labels "<= -1.0" and ">= +1.0"; speed 0.3, 0.7, 1.1, 1.5, 1.9. It reads the
  same lo, hi and Pressure inputs as WT Slice, so the two cannot disagree.
- Colour fidelity is a test, not only a setting: WT_ANIM uses view transform Standard, look None,
  exposure 0, gamma 1; slice and legend emission strength exactly 1.0; no bloom. Stage 4 renders the
  legend strip and samples the pixel colour at the 9 stop positions; each must equal the sRGB column
  within plus/minus 2/255. Recorded in `validation/anim_ab_v2512.json`.

## Q3 Smoke honesty (surface slide in solved mode, solid-mask deletion, RK4 drift): LOCKED 2026-10-22

Measured first (`validation/anim_ab_q3_measure.json`, scripts `tools/audit/anim_q3_smoke.py` and
`tools/audit/anim_q3_drift.py`; headless Blender 5.2 factory startup, 24 fps, U_inf 20 m/s, 150
particles per frame, step 0.0667 m = 1.33 voxels per frame, Sample Grid Trilinear):
- Python twin of the midpoint step reproduces Blender frame 40 -> 41 for 6000 particles to 2.4e-6 voxel.
- Drift vs RK4 (step at most 0.07 voxel) at equal arc length over 1 L, 3000 release points:
  slide off max 0.062 voxel near body (2206 paths), 0.008 voxel freestream (794 paths);
  slide on (as shipped) max 23.5 and 24.7 voxels, caused by the edge bug (open issue d).
- Slide off, 100 frames, 15000 released: 1 particle enters the cube box (1.1 mm deep, frame 80); the
  RK4 streamline from its release point also enters (2.5 mm), so the resampled field carries it in
  (audit section 6), not the integrator. The still rule (speed < 0.02 U_inf) deletes 46 of 15000
  (0.31 %), all within 0.0176 m (0.35 voxel) of the surface, median 0.2 mm, and deletes the box
  entrant at frame 75, five frames before it enters: 0 particles inside the cube.

Decision:
- Solved mode (Use Field on): surface slide band and push back both OFF. Particles move by the
  midpoint rule through WT Flow only.
- Solid-entry rule: the existing still rule (sampled speed < 0.02 U_inf), kept as is. It is a speed
  proxy, not a geometric inside test; its deletions are near-wall stagnation particles.
- Not the solid mask: it spans x -1.00..1.00 but y, z -0.95..1.00 (64000 nodes; a closed box would
  have 68921), and at nearest node it flags fluid up to 0.67 voxel outside the wall (open issue e).
- Preview mode (Use Field off) keeps the slide; its edge bug is Q4.
- Stage 4 metric "particles inside the solid" = inside the Test Object (for the cube: |x|, |y|,
  |z| < 1 m) over the whole animation, target 0; the solid-mask count is reported next to it, not
  gated. Stage 3 headless check reads the band and margin values of the solved-mode smoke tree.

Open issues found here:
- d: slide band test uses gap = (P - nearest) . n with n of one face next to the nearest edge, so in
  a 0.1 m slab around each face plane, beyond the edges, the velocity along that normal is removed,
  and the push back can move a particle onto an edge (up to 0.42 m seen). Affects preview mode. Q4.
- e: export_field solid mask is asymmetric (one node layer short on the -y and -z faces). Solver-side
  (export_field.py), for FIX_PLAN; not fixed in this slice.

## Q4 Preview-mode slide (edge bug d): OPEN
