# Accuracy audit scripts

These run **inside WSL Ubuntu** on a solved, reconstructed case. They import
`export_field.py` from the case folder (every case has its own copy).

| Script | What it checks |
|---|---|
| `audit.py CASE ORIG` | Recomputes face/cell geometry like OpenFOAM's `primitiveMesh`, compares forces with the add-on's method, y+ distribution, inlet static Cp, blockage, mass balance and divergence of `field.npz`. `CASE` must contain time folders `300` and `400`; `ORIG` is the solved run folder (for `forces.json`, `field.npz`). U0 = 20 m/s is hard-coded. |
| `history.py CASE` | Cd, Cs, Cl at every saved time of a case (frontal area from `forces.json`). |
| `step0_check.py CASE --exporter PATH` | FIX_PLAN step 0: runs OpenFOAM v2512 `forces`, `forceCoeffs` and `yPlus` (`simpleFoam -postProcess -latestTime`) on a copy of a solved case and compares total, pressure and viscous force with `export_field.body_forces`; y+ min, area mean, max and area fraction 30 to 300. Gates and definitions: `docs/reference/step0_openfoam_build.md`. |
| `step2_tracer.sh CASE...` | FIX_PLAN step 2 Stage 5: in `~/wind_tunnel/_step2/<CASE>` (written by `case3d.write_case`), the gated `Allrun`, then the same run continued without the gate to 2000 and exported again. Keeps `forces_gated.json`, `log.gated`, `forces_2000.json`. |
| `step2_check.py CASE [--ref CD]` | FIX_PLAN step 2: trigger iteration from `log.gated`, stop lag, offline gate on the merged history (must agree), gate verdict at 400 and 800, reported window means vs the 1801-2000 mean, and the force-first alternative (grill Q5) scored on the same history. Stdlib only, uses the case's `convergence.py`. |
| `anim_inside.py FIELD.npz FRAMES [OUT.json]` | Runs on **Windows** in headless Blender (`--background --factory-startup --python-exit-code 1 --python ... --`). Shipped WT Smoke in solved mode on a 2 m cube, frames played in order; particle-frames inside the body box (target 0) and the minimum gap outside it, Chebyshev (per-axis) and Euclidean. |
| `t1_costtest.sh NAME MAXCO NOUTER NCORR` | TRANSIENT T1 Q3: 25-step pimpleFoam cost test (potentialFoam start, backward, 24 ranks) on a copy of `~/wind_tunnel/_anim/Cube` in `~/wind_tunnel/_t1/cost_NAME`; prints steps, Courant, deltaT, ExecutionTime, continuity error, last forceCoeffs rows. Cost per step = (ExecutionTime at step 25 minus at step 5) / 20. |
| `t1_frames_check.py` (headless Blender) | TRANSIENT T1 Stage 3: synthetic 4-frame VDB sequence through `viz3d.build_transient`; checks WT Slice cp = 0.1 k at scene frame k and empty past the sequence (CLIP), plain smoke steps U/60 per scene frame with substeps, streak length 0.1 L along +X, and the node-built time text equals `transient.time_label`. Prints `T1CHECK {json}`, exit 1 on a failure. |
| `extend.sh` | Continues the `_audit` copies of Cube and Cone from 400 to 1200 iterations, writing every 50. |

Typical use from Git Bash on Windows:

```bash
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -e bash -lc "mkdir -p ~/wind_tunnel/_audit && cp /mnt/d/10_PROJECTS/'aerodynamics blender openfoam'/tools/audit/*.py ~/wind_tunnel/_audit/"
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -e bash -lc ". /usr/lib/openfoam/openfoam2512/etc/bashrc; cd ~/wind_tunnel/_audit && python3 history.py Cube"
```

Known limits: fixed speed, fixed time names, no CLI flags. Turning these into a proper
`validate` command that runs after every solve is part of FIX_PLAN step 5.
