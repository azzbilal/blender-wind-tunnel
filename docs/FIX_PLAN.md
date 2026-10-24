# Fix plan (work in this order)

## Status (v1.0.0, 2026-10-24)

| Step | State | Closed | Add-on | Record | Review |
|---|---|---|---|---|---|
| 0. OpenFOAM build | closed | 2026-10-19 | 0.4.1 | `validation/step0_v2512.json` | `docs/reviews/step0_review.md` |
| 1. Cp reference | closed | 2026-10-21 | 0.4.2 | `validation/step1_cp_v2512.json` | `docs/reviews/step1_review.md` |
| 2. Convergence gate | closed | 2026-10-21 | 0.4.3, 0.4.4 | `validation/step2_gate_v2512.json` | `docs/reviews/step2_review.md` |
| 3. Wall treatment | closed | 2026-10-24 | 0.7.0 | `validation/step3_wall_v2512.json` | none (Bilal's decision, see step 3) |
| 4. Domain | documented next step | | | | |
| 5. Validation set | documented next step | | | | |
| 6. Visualisation honesty | documented next step (solved-mode slide already off since 0.5.0) | | | | |
| 7. 2D far field | documented next step | | | | |

The project closed as a portfolio piece at add-on 1.0.0. Steps 4 to 7 are written up below with their
acceptance checks but were not started. Further next steps logged outside this plan: a time-averaged URANS
fallback for bodies with no steady state (the sphere, step 3 amendment D3) and a guarded u_tau re-mesh (D2).

Each step has an acceptance check. Record every validation number in `validation/` with date,
cell count, iterations and mesh setting. Audit references: `docs/ACCURACY_AUDIT.md`.

## Step 0. A working OpenFOAM build (Bilal runs this, needs sudo)

In the Ubuntu window:

```bash
curl -s https://dl.openfoam.com/add-debian-repo.sh | sudo bash
sudo apt update
apt search openfoam2 2>/dev/null | grep -- -default     # pick the highest version
sudo apt install -y openfoam2512-default                # replace with that version
```

Then make `case.ENV` prefer `/usr/lib/openfoam/openfoam*/etc/bashrc` over
`/usr/share/openfoam` (check the current ENV string first). Re-enable scotch decomposition if
available.

Accept: `forceCoeffs` and `yPlus` run on an existing case without the sha1 crash, and
OpenFOAM's `forces` agree with `export_field.py` within 0.5 %.

## Step 1. Cp reference

Reference Cp to freestream static pressure: either fix `p` at the inlet side
(`totalPressure`/`freestreamPressure` pair) or subtract the mean inlet static pressure in
`export_field.py` before writing `cp`. Also expose it in `forces.json`.

Accept: mean Cp on the inlet plane is 0 within 0.2 %; stagnation Cp on the cube front face is
1.00 within 2 %.

## Step 2. Convergence gate (biggest win)

- Replace the fixed 400 iterations with: run in chunks, integrate forces every N iterations
  (OpenFOAM `forces` once step 0 is done, otherwise write every 50 and integrate in Python),
  stop when Cd changes less than 0.5 % over the last 200 iterations and the p residual has
  dropped 3 orders, or at a cap (3000).
- Report Cd as the mean over the last 200 iterations with min/max; panel shows "converged" or
  "not converged" with the reason.
- `field_state() == "solved"` only when the gate passed.

Accept: cube and cone reproduce the 1200-iteration values (1.151, 0.583) within 1 %, and the
panel never shows a number while the gate is open.

## Step 3. Wall treatment and surface resolution

- Layers: `relativeSizes false`, first layer height from a target y+ of about 50 using a
  flat-plate Cf estimate on L (same formula as `case.Setup.first_cell`), 5 layers, expansion
  1.2. Fall back gracefully where snappy drops layers and report layer coverage %.
- Surface refinement: curvature-based levels (or `resolveFeatureAngle` plus a distance
  refinement shell) so a sphere gets at least about 100 cells around its circumference.
- Compute y+ (OpenFOAM `yPlus` after step 0) and write min/mean/max and the area fraction
  with 30 < y+ < 300 into `forces.json`; warn in the panel when under 80 %.

Accept: y+ in 30 to 300 on at least 80 % of the area for sphere, cube and cone; layer
coverage at least 90 %.

Amended 2026-10-24 by the step 3 grill (docs/reference/step3_wall_spec.md, which supersedes the plan
above where they differ): first cell-centre y+ 100 on a measured u_tau anchor, first layer 2 y_c in
metres, n = min(half-cell rule, one-cell stack cap), expansion 1.3, featureAngle 60, curvatureLevel
(24 0 lo2 -1). Accept (as locked): y+ <= 300 on at least 90 % of the area and layer coverage (faces
extruded / body faces) at least 90 % for sphere, cube and cone; the 30 to 300 band and y+ < 5 fractions
are reported, not gated (y+ < 30 is valid with nutUSpaldingWallFunction). The panel warns on the two gates.
Amendments D1 to D3 (same spec): uniform body level (lo2 lo2), COARSE (3 3), MEDIUM (4 4), curvatureLevel
removed; no automatic re-mesh, a failing y+ gate reports its cause (cut layers or u_tau above the sizing anchor);
the sphere at Re 2.67e6 is recorded, not treated.

Accept (final, as closed 2026-10-24, add-on 0.7.0): both gates, y+ <= 300 on at least 90 % of the body area and
layer coverage at least 90 %, on every body re-run. Stage B re-runs (COARSE, OpenFOAM v2512, 24 ranks, step 2
convergence gate, `validation/step3_wall_v2512.json` key `stageB_rerun_2026_10_24`):

| Body | Cells | Gate iteration | y+ <= 300 | Coverage | Cd window mean |
|---|---|---|---|---|---|
| Cube | 437,192 | 786 | 99.8 % | 100 % | 1.1448 (step 2 1.1498, -0.43 %) |
| Cone | 383,135 | 716 | 96.95 % (step 3 Stage 4 82.0 %) | 98.4 % | 0.5846 (step 2 0.5833, +0.23 %) |
| Sphere | 388,788 | not converged at 3000 | 95.6 % (snapshot) | 99.2 % | none (amendment D3) |

Both wall gates pass on all three meshes; the sphere has no steady state on its gate-passing mesh, so no Cd.
Step 3 closed without a separate review session (Bilal, 2026-10-24): the project is ending as a portfolio
piece and steps 4 to 7 below are documented next steps, not scheduled work.

## Step 4. Domain

- Inlet 5 L upstream, outlet 15 L downstream, sides so that blockage is at most 1 %.
- Keep the wake refinement box but extend it to 5 L.

Accept: blockage at most 1 % printed in `forces.json`; Cd changes less than 1 % when the
domain is enlarged by a further 50 % (one-off domain study, recorded).

## Step 5. Validation set (gate before any release)

| Case | Reference | Target |
|---|---|---|
| Cube face on, 1 m, 20 m/s | Hoerner / ESDU (find and cite) | within 10 % |
| Cone 30 deg half angle, tip upstream | Hoerner 0.50 | within 10 % |
| Sphere, subcritical Re (lower speed or smaller) | Achenbach 1972 | within 15 % |
| NACA 0012 2D, Re 6e6, alpha 0/10/15 | NASA TMR | Cl within 3 %, Cd within 15 % |

Also a mesh study (coarse / medium / fine) on the cube with Richardson extrapolation, and the
Bernoulli check from `tools/audit/audit.py` (max total pressure excess under 0.02 q outside
the first cell layer).

## Step 6. Visualisation honesty

- In solved mode, switch off the surface-slide correction, or limit it to the first voxel.
- Sample the field with OpenFOAM's `cellPoint` interpolation (`postProcess -func
  "internalProbes"` or a VTK export) instead of IDW, or at least use a divergence-cleaning step.
- Cell centres (T1 review O1, 2026-10-24): every IDW export (steady `field.npz` and the T1 frames)
  places cell values at the mean of the face centres (`export_field.cell_centres`), not at the
  volume centroid OpenFOAM writes as `C`. On the cube mesh they differ by up to 0.070 m (1.4 voxels)
  in cells with uneven face counts (snappyHexMesh refinement interfaces), which moves |U| by up to
  1.2 % at the voxels sampled. Forces are unaffected (face-by-face sum). Use `writeCellCentres` or a
  volume-weighted centroid and record the change in `field.npz`. Note for bit-level regression
  tests: far-field voxel nodes often sit at exact distance ties between more than 4 centres.
- Extend the voxel grid to at least 5 L downstream.

Accept: rms divergence next to the body under 2 % of U0/h; particles stay out of the solid
without the correction.

## Step 7. 2D far field

Add a point-vortex far-field correction (or move the boundary to 100 chords).

Also (found 2026-10-24, step 3 prep): `meshgen.c_grid` uses `case.Setup.first_cell` as the full
first cell height, while OpenFOAM's `yPlus` uses `nearWallDist` (cell centre, about half the
height), so the 2D grid runs at about half its nominal y+ (about 25 for the target 50). Fix: use
2 x `first_cell` as the cell height, and check y+ with the `yPlus` FO.

Accept: Cl at alpha 10 within 1.5 % of NASA TMR.
