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
