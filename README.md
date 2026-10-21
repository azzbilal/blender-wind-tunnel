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
