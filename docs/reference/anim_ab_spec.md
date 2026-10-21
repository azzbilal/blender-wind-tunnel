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

## Q2 Colour (diverging Cp ramp, stops, range, legend): OPEN

## Q3 Smoke honesty (surface slide in solved mode, solid-mask deletion, RK4 drift): OPEN
