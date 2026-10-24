# Changelog

Add-on versions as set in `wind_tunnel/blender_manifest.toml` and `bl_info`. Every number below has its
record in `validation/`; dates are commit dates. Format loosely follows Keep a Changelog.

## 1.0.0 (2026-10-24): portfolio release

No solver or add-on behaviour change; documentation and repository only.

- README rewritten for a reader new to the project: hero GIF and stills (`docs/media/`), Mermaid pipeline
  diagram, "What is checked" with each number's record, known limits, next steps, engineering highlights.
- Corrected the README's description of the solved cone: 26.6 deg half angle, tip upstream (it said 30 deg).
- FIX_PLAN status block; one status line per ACCURACY_AUDIT finding (original audit text unchanged).
- LICENSE (GPL-3.0-or-later, as the manifest already declared), this changelog, GitHub Actions job for the
  pure-module unittest suite.
- Manifest tagline and `bl_info` description now describe the 3D wind tunnel (they still said "airfoil
  polars"); manifest `website` points at the repository.
- Absolute local user paths in CLAUDE.md and two review reports replaced with neutral wording.

## 0.7.0 (2026-10-24): wall treatment (FIX_PLAN step 3)

- Prism layers sized from a y+ target of 100 at the first cell centre: first layer 2 y_c in metres
  (`relativeSizes false`), expansion 1.3, n = min(n_half, n_depth), featureAngle 60.
- One uniform body refinement level, (3 3) COARSE and (4 4) MEDIUM, curvature levels removed.
- Two wall gates in `forces.json` and the panel: y+ <= 300 on at least 90 % of the body area and layer
  coverage at least 90 %; a cause row ("cut layers" or "u_tau > sizing") when the y+ gate fails.
- Re-runs (COARSE, 24 ranks): cube Cd 1.1498 -> 1.1448 (-0.43 %), y+ <= 300 99.8 %; cone Cd 0.5833 ->
  0.5846 (+0.23 %), y+ <= 300 82.0 -> 96.95 %; sphere passes both wall gates but reaches no steady state,
  so no Cd is reported.

## 0.6.1 (2026-10-24): transient smoke visibility

- Smoke streak radius L/600 -> L/160, trail 0.1 L -> 0.3 L, release 40 -> 60 particles a frame, so the
  streaks read in the T1 video. No physical quantity changed.

## 0.6.0 (2026-10-24): time-resolved run (TRANSIENT T1)

- pimpleFoam on the solved cube mesh, started from potentialFoam, written every 1/60 s for 2 s; one OpenVDB
  frame per written time, so scene frame k is flow time k/60 s; WT Slice fixed in Cp mode with a time label.
- Cd averaged over 1 to 2 s 1.124 against the steady 1.150 on the same mesh (a model-to-model comparison);
  time-step continuity error at most 1.95e-12; no sustained vortex shedding, so no Strouhal number.

## 0.5.0 (2026-10-22): animating the steady result (ANIMATION A+B)

- Animate slice: WT Slice sweeps plus/minus 1 L through the solved field, 192 frames, labelled position.
- Diverging Cp ramp (Cp 0 neutral grey, -1 blue, +1 red) with a legend read from the same inputs.
- Solved-mode smoke: no surface slide or push back; particles that stall at the wall are removed. On the 2 m
  cube no particle entered the body over 192 frames; paths within 0.06 voxel of an RK4 streamline over 1 L.

## 0.4.4 (2026-10-21): convergence gate, Blender QA fixes (FIX_PLAN step 2)

- Panel wording and QA fixes for the gate introduced in 0.4.3. No physical quantity changed.

## 0.4.3 (2026-10-21): convergence gate (FIX_PLAN step 2)

- The fixed 400 iterations replaced by a gate: Cd band under 0.5 % over the last 200 iterations and the p
  residual down 3 orders, cap 3000, using OpenFOAM `forces` and `solverInfo` function objects. Cd is the
  window mean; the panel shows no number while the gate is open.
- Cube converged at 1830 (Cd 1.150), cone at 725 (Cd 0.583), matching the 1200-iteration audit values.

## 0.4.2 (2026-10-21): Cp reference (FIX_PLAN step 1)

- Cp referenced to the area-weighted mean static pressure on the inlet patch instead of the outlet's p = 0
  (the offset was +0.5 % q sphere, +1.1 % cone, +4.5 % cube); `p_inf_Pa` written to `field.npz`.

## 0.4.1 (2026-10-19): OpenFOAM v2512 (FIX_PLAN step 0)

- openfoam.com v2512 with scotch replaces Ubuntu's v1912, whose function objects crashed. The add-on's body
  force agrees with OpenFOAM's `forces` within 0.15 % of drag.

## 0.4.0 (2026-10-19): starting point of this repository

- 2D NACA 4-digit C-grid sweeps and the 3D any-mesh pipeline (snappyHexMesh, simpleFoam, VDB volume, Geometry
  Nodes smoke) as imported, together with the accuracy audit (`docs/ACCURACY_AUDIT.md`) that found the 3D
  numbers not yet reliable and the ordered fix plan (`docs/FIX_PLAN.md`).
