# Wind Tunnel for Blender (OpenFOAM in WSL)

A Blender add-on that solves the air flow around a model with **OpenFOAM** running in
**WSL Ubuntu** and brings the results back into Blender.

> **Status (v0.4.0):** the pipeline works end to end, but the 3D numbers are not yet
> physically reliable. See `docs/ACCURACY_AUDIT.md` for the evidence and `docs/FIX_PLAN.md`
> for the ordered fixes.

```
Blender (Windows)                              WSL Ubuntu
  2D: NACA code ──► C-grid + case ───────────►  simpleFoam x N angles (parallel)
  3D: Test Object ──► STL + case ────────────►  snappyHexMesh, simpleFoam -parallel, export_field.py
  panel, Cp colours, VDB volume, GN smoke ◄───  ASCII results, forces.json, field.npz
```

## 2D airfoil

- Any 4-digit NACA section, structured C-grid written straight to polyMesh (y+ about 50,
  far field 20 chords), simpleFoam with k-omega SST and Spalding wall functions.
- One mesh for the whole angle sweep; forces summed face by face in Python.
- NACA 0012, Re 6e6 against NASA TMR (CFL3D, finest grid):

| alpha | Cl here | Cl NASA | Cd here | Cd NASA |
|---|---|---|---|---|
| 0 | 0.000 | 0 | 0.0085 | 0.0081 |
| 10 | 1.055 | 1.078 | 0.0139 | 0.0124 |
| 15 | 1.451 | 1.507 | 0.0263 | 0.0222 |

## 3D, any closed mesh

- The **WT Smoke** Geometry Nodes modifier has a **Test Object** field. Assigning a mesh
  starts a preview (particles slide around its surface), then an automatic OpenFOAM solve
  (snappyHexMesh, simpleFoam on up to 24 cores), cached per shape.
- The solved field comes back as an OpenVDB volume (**WT Flow**); particles are advected
  through it and **WT Slice** shows speed or Cp on a movable plane.

## Animating the result

The 3D solve is steady (simpleFoam): there is one flow field and it does not change in time. The
animation only moves the viewpoint through that field. **Animate slice** sweeps WT Slice over
plus/minus 1 L about the body along X, Y or Z (192 frames, ping-pong, one keyframe per frame);
every frame samples the same solved field at the plane's true position, nothing is interpolated
in the data. The label above the slice prints its position in metres and in L, and the legend
reads the same range inputs as the slice, so the two cannot disagree. Cp = (p - p_inf) / (0.5 rho
U_inf^2), with p_inf the area-weighted mean static pressure on the inlet patch; the diverging ramp
puts Cp = 0 on the neutral grey, -1 (blue) and +1 (red, the incompressible stagnation limit) at
the ends, clamped beyond. The slice stops about one voxel (5 cm) off the body, on purpose.

WT Smoke shows the same steady field as particles carried by its velocity (midpoint rule through
WT Flow). In solved mode there is no surface slide or push back; particles that stall at the wall
(sampled speed below 2 % of U_inf) are removed. On the 2 m cube (v0.5.0) no particle entered the
body over 192 frames and smoke paths stay within 0.06 voxel of an RK4 streamline over 1 L
(`validation/anim_ab_v2512.json`). Smoke paths are streamlines of a steady field, not a
time-resolved wake: vortex shedding is not in the data.

## Time-resolved flow

v0.6.0 adds a transient run (TRANSIENT T1, spec `docs/reference/transient_t1_spec.md`): pimpleFoam
with the same k-omega SST model and spatial schemes as the steady case, second-order backward time
stepping at a maximum Courant number of 1, started impulsively from the potential flow
(potentialFoam) on the mesh of the solved steady cube (2 m, 20 m/s, Re 2.7e6, 359618 cells). U and p
are written every 1/60 s for 2 s (20 flow-throughs L/U); every written time becomes one frame, an
OpenVDB file in a sequence, so scene frame k shows flow time k/60 s. WT Slice stays fixed at y = 0 in
Cp mode, the label prints t and t U/L, and the smoke (thin charcoal streaks released in a sheet within
0.05 L of the slice plane) advances exactly 1/60 s of flow per frame through the time-varying field.
Video `renders/transient_t1_cube.mp4`: 120 frames at 12 fps, so 10 s of video for 2 s of flow.

What the run shows, and what it does not (`validation/transient_t1_v2512.json`, 2026-10-24):

- The start-up: the starting vortex pair leaves the edges and the recirculation behind the cube
  grows and settles. Cp near the edges is far below the steady values at first (-4.24 at t = 1/60 s,
  the potential-flow start at sharp edges) and relaxes to -0.73 / +1.03 by t = 2 s (steady field:
  -0.68 / +1.02).
- No sustained vortex shedding. The side force oscillates between t = 1.0 and 1.6 s and then decays;
  after 1.7 s |Cs|, |Cl| < 0.008. No Strouhal number is reported. The only free-stream cube reference
  found (Klotz et al. 2014, St 0.125) is for Re <= 390, a different regime.
- Cd averaged over 1 to 2 s is 1.124, 2.2 % below the steady 1.150 on the same mesh. This compares two
  models, it is not a validation; neither number is checked against experiment yet (FIX_PLAN steps 3
  and 4).
- Mass conservation: the time step continuity error is at most 1.95e-12 at every frame (gate 1e-6).
  No smoke particle entered the cube in 130934 particle-frames.

Limits, plainly: this is URANS, so turbulence is modelled, not resolved; only unsteadiness much
slower than the turbulence can appear, and on this coarse mesh with wall functions the solution
settles toward the steady state. A finer mesh or a scale-resolving model (DES or LES) might shed;
that has not been tested. The frames are interpolated onto a 5 cm grid, so small vortices are
smoothed. The transient run is not yet in the panel: it is driven by `case3d.write_transient_case`,
`export_field.py --frames`, `viz3d.build_transient` and the scripts in `tools/audit/` (`t1_gates.py`,
`t1_scene.py`, `anim_inside.py`, `t1_frames_check.py`).

## Install

1. WSL: `wsl --install -d Ubuntu-24.04`, then in Ubuntu install OpenFOAM (see FIX_PLAN step 0
   for the openfoam.com build; Ubuntu's own `openfoam` package works but its function
   objects crash). Also `sudo apt install python3-numpy python3-scipy`.
2. Add-on: `py tools/deploy.py` from this folder (or install `dist/wind_tunnel.zip` from
   Blender's Preferences > Add-ons > Install from Disk).
3. Blender sidebar (N) > Wind Tunnel > refresh icon to find OpenFOAM.

Cases are written to `~/wind_tunnel/<run>` inside Ubuntu and read through
`\\wsl.localhost\Ubuntu-24.04\...`.

## Development

```bash
py -m unittest discover -s tests -v
py tools/deploy.py
"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/blender_smoke.py
```

Project context for Claude Code is in `CLAUDE.md`.
