# Wind Tunnel for Blender (OpenFOAM in WSL)

> **In 30 seconds.**<br>
> **What:** a Blender add-on that puts any closed mesh, or a NACA 4-digit airfoil, in a virtual wind tunnel and brings forces, surface Cp and the 3D flow field back into Blender.<br>
> **Stack:** OpenFOAM v2512 in WSL Ubuntu (snappyHexMesh, simpleFoam, pimpleFoam, k-omega SST with wall functions), Python, Blender 5.2 (OpenVDB, Geometry Nodes).<br>
> **Checked:** NACA 0012 at Re 6e6 against NASA TMR (Cl -2.1 % / -3.7 % at alpha 10 / 15, Cd +5.1 % to +18.5 % over alpha 0 to 15); 3D body forces match OpenFOAM's own `forces` within 0.15 % of drag; cube and cone pass the convergence gate and both wall gates.<br>
> **Status:** 1.0.0, closed as a portfolio piece; no 3D result has been compared with experiment yet (FIX_PLAN step 5, documented, not started).

[![tests](https://github.com/azzbilal/blender-wind-tunnel/actions/workflows/tests.yml/badge.svg)](https://github.com/azzbilal/blender-wind-tunnel/actions/workflows/tests.yml)
![version](https://img.shields.io/badge/add--on-1.0.0-blue)
![licence](https://img.shields.io/badge/licence-GPL--3.0--or--later-green)

A Blender add-on that puts any closed mesh, or a NACA 4-digit airfoil, into a virtual wind tunnel: it
writes an OpenFOAM case, solves incompressible RANS (k-omega SST, wall functions) with **OpenFOAM v2512 in
WSL Ubuntu**, and brings forces, surface pressure and the 3D flow field back into Blender as an OpenVDB
volume, a Cp slice and Geometry Nodes smoke. The project was run as an accuracy exercise: an audit of the
first working version, then an ordered fix plan where every step has an acceptance check and every number
is recorded with its date, mesh and iteration count in `validation/`.

![Transient start-up flow around a 2 m cube at 20 m/s: Cp on the y = 0 slice and smoke streaks](docs/media/hero_transient_cube.gif)

*Start-up of the flow around a 2 m cube at 20 m/s (Re 2.7e6), pimpleFoam with k-omega SST, 2 s of flow time
(20 L/U) in 10 s of video. Colour: Cp on the y = 0 plane (blue -1, grey 0, red +1); streaks: smoke advected
through the time-varying field. The run shows the starting vortex pair and the recirculation settling, and no
sustained vortex shedding (see "Time-resolved flow" in [`docs/DETAILS.md`](docs/DETAILS.md)).*

| t = 0.5 s | t = 1.0 s | t = 2.0 s |
|---|---|---|
| ![t = 0.5 s](docs/media/cube_t0p5s.png) | ![t = 1.0 s](docs/media/cube_t1p0s.png) | ![t = 2.0 s](docs/media/cube_t2p0s.png) |

## Pipeline

```mermaid
flowchart LR
    subgraph B["Blender (Windows)"]
        A1["2D: NACA code"]
        A2["3D: any closed mesh<br/>(Test Object)"]
        V["Panel: Cd, Cl, gates<br/>WT Flow (OpenVDB)<br/>WT Slice (speed or Cp)<br/>WT Smoke (Geometry Nodes)"]
    end
    subgraph W["WSL Ubuntu, OpenFOAM v2512"]
        M2["meshgen.py: C-grid<br/>written to polyMesh"]
        S2["simpleFoam per angle<br/>(parallel sweep)"]
        M3["blockMesh + snappyHexMesh<br/>prism layers sized for y+"]
        S3["simpleFoam -parallel<br/>convergence gate, yPlus, forces"]
        E["export_field.py<br/>forces.json, field.npz"]
    end
    A1 --> M2 --> S2 -->|"ASCII fields, face-by-face forces"| V
    A2 -->|"STL"| M3 --> S3 --> E -->|"forces + voxel field"| V
```

## What is checked, and against what

Only one comparison in this repository is against a cited external reference: the 2D NACA 0012 case. The 3D
results are checked against OpenFOAM's own definitions and against internal gates, not against experiment;
the reference comparison is a documented next step (FIX_PLAN step 5).

**NACA 0012, Re 6e6, against the NASA Turbulence Modeling Resource** (2D NACA 0012 validation case, SST model,
CFL3D finest grid; reference values as stored in `wind_tunnel/results.py:331`). The sweep here was solved with
OpenFOAM v1912 before FIX_PLAN step 0 and has not been re-run since; it has no record in `validation/`.

| alpha (deg) | Cl here | Cl NASA | diff | Cd here | Cd NASA | diff |
|---|---|---|---|---|---|---|
| 0 | 0.000 | 0 | | 0.0085 | 0.00809 | +5.1 % |
| 10 | 1.055 | 1.0778 | -2.1 % | 0.0139 | 0.01236 | +12.5 % |
| 15 | 1.451 | 1.5068 | -3.7 % | 0.0263 | 0.02219 | +18.5 % |

At alpha 15 both the Cl gap and the Cd gap are outside the FIX_PLAN step 5 targets (Cl within 3 %, Cd within
15 %). Two known contributors are open in FIX_PLAN step 7: the far field at 20 chords has no point-vortex
correction (the audit estimates about 2.5 % lift deficit at Cl 1.1), and the C-grid's first cell runs at
about half its nominal y+.

**3D internal checks** (OpenFOAM v2512):

| Check | Result | Record |
|---|---|---|
| Body force vs OpenFOAM `forces` function object | agrees within 0.15 % of drag (cube, cone, sphere) | `validation/step0_v2512.json` |
| Cp reference | p_inf = area-weighted mean static p on the inlet patch; inlet mean Cp 0 to round-off. Cube front-face stagnation Cp 1.023, outside its 1.00 +/- 2 % target, recorded as a miss, not tuned | `validation/step1_cp_v2512.json` |
| Convergence gate | Cd band under 0.5 % over the last 200 iterations and p residual down 3 orders (cap 3000); a second STL triangulation of the cube gives the same gated Cd within 0.02 % | `validation/step2_gate_v2512.json` |
| Wall gates | y+ <= 300 on at least 90 % of the body area (OpenFOAM `yPlus`), layer coverage at least 90 % | `validation/step3_wall_v2512.json` |
| Mass conservation, transient | time-step continuity error at most 1.95e-12 at every written frame | `validation/transient_t1_v2512.json` |
| Smoke vs streamlines (steady) | no particle inside the body over 192 frames; paths within 0.06 voxel of an RK4 streamline over 1 L | `validation/anim_ab_v2512.json` |

**3D bodies on the default COARSE mesh** (2 m body, 20 m/s, Re 2.67e6, 24 ranks, 2026-10-24,
`validation/step3_wall_v2512.json` key `stageB_rerun_2026_10_24`). These are mesh-quality and convergence
checks, not a comparison with experiment:

| Body | Cells | Convergence gate | Cd (window mean) | y+ <= 300 | Layer coverage |
|---|---|---|---|---|---|
| Cube, face on | 437,192 | passed at 786 | 1.1448 | 99.8 % | 100 % |
| Cone, 26.6 deg half angle, tip upstream | 383,135 | passed at 716 | 0.5846 | 96.95 % | 98.4 % |
| Sphere | 388,788 | not passed at 3000 | none reported | 95.6 % | 99.2 % |

For context on the cone only, from a secondary source: aerospaceweb.org (J. Scott, "Drag of Cylinders &
Cones", 2005, [q0231](https://aerospaceweb.org/question/aerodynamics/q0231.shtml)) tabulates Cd 0.50 for a
cone of 30 deg half angle, tip first, for Re 1e4 to 1e6, and credits its cone-drag-versus-angle graph to
Hoerner, *Fluid-Dynamic Drag*. The cone here has a 26.6 deg half angle and runs at Re about 2.7e6, so this
is not a like-for-like comparison and no percentage is given. Both values use the base cross-section pi r^2
(the page states this reference area for cones; here it is the frontal area of a tip-upstream cone). No cube
reference is cited.

## Engineering highlights

- **Audit before features.** The first working version (0.4.0) was audited against the equations OpenFOAM
  solves; the audit found the reported 3D Cd to be a snapshot of an unconverged solve (the cube's
  400-iteration Cd differed by about 35 % between two triangulations of the same cube), first cells at
  y+ up to 1467, and Cp referenced to the outlet. Each finding became an ordered fix with an acceptance test
  (`docs/ACCURACY_AUDIT.md`, `docs/FIX_PLAN.md`).
- **Convergence gate inside the solver run.** OpenFOAM `forces` and `solverInfo` function objects feed a
  pure-Python gate; a `systemCall` / `abort` function object stops simpleFoam once Cd and the p residual
  pass, and the panel shows no Cd while the gate is open.
- **y+-driven prism layers.** The first layer is sized from a friction-velocity anchor at 2 y_c, because
  OpenFOAM's `yPlus` uses the cell-centre wall distance (about half the first layer). When the y+ gate
  fails the add-on says why: "cut layers" (snappyHexMesh dropped layers but kept the stack height) or
  "u_tau > sizing".
- **Independent force integration.** Forces are summed face by face in Python from rebuilt face areas and
  normals and checked against OpenFOAM's own `forces` (0.15 % of drag).
- **Own 2D mesher.** A structured C-grid for any NACA 4-digit section, written straight to `polyMesh`, one
  mesh for the whole angle sweep.
- **Flow field into Blender.** `field.npz` becomes an OpenVDB volume; a Geometry Nodes Simulation Zone
  advects smoke through it (midpoint rule) and a slice samples speed or Cp. A time-resolved pimpleFoam run
  becomes a VDB sequence with frame k at flow time k/60 s.
- **Tests and records.** 127 pure-module tests (no Blender, no WSL) run in CI; a headless Blender smoke
  check registers the add-on and builds the node trees; every validation number sits in a dated JSON
  record next to the script that produced it (`tools/audit/`).

## Known limits

- Steady RANS, k-omega SST with `nutUSpaldingWallFunction`: separation on smooth bodies is not reliably
  predicted; sharp-edged bodies (cube, cone) fix their separation lines and are less sensitive.
- The default mesh is COARSE (about 0.4 M cells for a 2 m body); no mesh-independence study yet.
- Domain and blockage have not been studied (the audit measured 2.2 to 2.8 % blockage).
- The sphere at Re 2.67e6 has no steady state on its gate-passing mesh, so no Cd is reported. This Re is
  above the smooth-sphere drag crisis, which Achenbach measured over Re 5e4 to 6e6 (Achenbach, E. 1972,
  J. Fluid Mech. 54(3), 565 to 575).
- The voxel field is interpolated (inverse distance, 4 nearest cell centres, 5 cm grid, ending 2.5 L
  downstream), and cell centres are approximated by face-centre means; forces do not use it.
- No 3D result has been compared with experiment yet; the step 3 work had no independent review session.
- 2D: far field without a point-vortex correction; the C-grid first cell sits at about half its nominal y+;
  the 2D numbers predate the OpenFOAM v2512 switch.
- Windows with WSL only.

## Next steps

Written up with acceptance checks in `docs/FIX_PLAN.md` (status block at the top), not started:

- **Step 4, domain:** inlet 5 L, outlet 15 L, blockage at most 1 %, a one-off domain study.
- **Step 5, validation set:** cube, cone and sphere against cited experimental values, NACA 0012 against NASA
  TMR within stated targets, a cube mesh study with Richardson extrapolation, the Bernoulli check.
- **Step 6, visualisation honesty:** `cellPoint` sampling instead of IDW, true cell centres (`C`), a longer
  voxel grid.
- **Step 7, 2D far field:** point-vortex correction and the C-grid half-y+ fix.
- Also logged: a time-averaged URANS fallback for bodies with no steady state (the sphere), and a guarded
  re-mesh from the measured friction velocity.

## Details

The 2D airfoil path, the 3D pipeline, the wall treatment, the steady-field animation and the time-resolved
run are described in [`docs/DETAILS.md`](docs/DETAILS.md).

## What I learned about OpenFOAM

> **Draft for Bilal to edit.** Written from the project records (audit, specs, reviews); rewrite in your own
> words and cut what you would not say in an interview.

- **Check that the build's own cross-checks run before trusting any post-processing.** Ubuntu's packaged
  OpenFOAM v1912 crashed in every function object (`forces`, `yPlus`, `solverInfo`), so for the first
  version nothing could be compared with OpenFOAM's own numbers. Moving to the openfoam.com v2512 build
  was step 0 of the fix plan, and the first thing it allowed was a check of my own force integration.
- **A fixed iteration count is not a result.** The cube's Cd at 400 iterations changed by about 35 %
  between two triangulations of the same cube; at iteration 300 it happened to match a commonly quoted
  figure (about 1.05) that this project never sourced.
  Gating on a force band plus a residual drop, and reporting the window mean, removed that path
  dependence (the gated values agree within 0.02 %).
- **Know what `yPlus` measures.** OpenFOAM's `yPlus` uses the wall distance of the first cell centre,
  about half the first layer height, so a layer sized for a y+ target at its full height lands at
  roughly half the target. The same mismatch sits in my 2D C-grid and is still open.
- **snappyHexMesh layers fail quietly.** When it cannot extrude all layers it keeps the smoothed stack
  height, leaving thick first cells; curvature refinement levels made this worse on the cone by stepping
  the surface cell size. Measuring layer coverage from the log and splitting the y+ failures by cause
  turned a vague "bad y+" into a fixable mesh setting.
- **`p` in incompressible solvers is kinematic and its level is arbitrary.** It is fixed at the outlet,
  so Cp needs an explicit free-stream reference; forces on a closed body are unaffected by the offset.
- **Convergence can come from a bad mesh.** An older sphere mesh converged only with a mean first-cell
  y+ of 822; on the mesh that passes the wall gates, steady simpleFoam no longer settles at Re 2.67e6.
  A converged run is not automatically a physical one.
- **URANS on a coarse wall-function mesh settles towards the steady answer.** The transient cube shows
  the start-up vortices and then no sustained shedding; resolving the wake needs a finer mesh or a
  scale-resolving model.
- **Practical WSL notes.** `set -e` or `set -u` before sourcing the OpenFOAM `bashrc` kills a script
  silently, and `mpirun` with 24 ranks in WSL needs `--oversubscribe`.

## Install

1. WSL: `wsl --install -d Ubuntu-24.04`, then in Ubuntu install the openfoam.com build (FIX_PLAN step 0 and
   `docs/reference/step0_openfoam_build.md`; Ubuntu's own `openfoam` package solves, but its function
   objects crash, and the convergence gate depends on them). Also `sudo apt install python3-numpy python3-scipy`.
2. Add-on: `py tools/deploy.py` from this folder (or install `dist/wind_tunnel.zip` from Blender's
   Preferences > Add-ons > Install from Disk). Tested with Blender 5.2 LTS.
3. Blender sidebar (N) > Wind Tunnel > refresh icon to find OpenFOAM.

Cases are written to `~/wind_tunnel/<run>` inside Ubuntu and read through
`\\wsl.localhost\Ubuntu-24.04\...`.

## Development

```bash
py -m unittest discover -s tests -v          # pure modules, no Blender or WSL needed (also run in CI)
py tools/deploy.py                           # install into Blender and build dist/wind_tunnel.zip
"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/blender_smoke.py
```

Layout, data flow and conventions (wind along +X, metres, kinematic p) are in `CLAUDE.md`; version history
in `CHANGELOG.md`.

## How it was built

The code was written with Claude Code (an AI coding agent) under a fixed method, and the record is kept
in the repository: an accuracy audit first, then one fix-plan step per session; each step opens with a
question-and-answer "grill" whose answers are locked in a spec (`docs/reference/`), proceeds test first,
runs live checks only on copies of solved cases, and closes with an independent review session
(`docs/reviews/`; every step except FIX_PLAN step 3, see "Known limits"). Session prompts are in
`docs/prompts/`, the running log in `SESSION_LOG.md` and its history in `docs/archive/`. I directed the
work: I chose at every decision point, approved each acceptance criterion and did the visual QA.

## Licence

GPL-3.0-or-later (`LICENSE`). OpenFOAM is GPL-3.0 licensed and is not distributed here.

OPENFOAM® is a registered trade mark of OpenCFD Limited, producer and distributor of the OpenFOAM software
via www.openfoam.com. This offering is not approved or endorsed by OpenCFD Limited.
