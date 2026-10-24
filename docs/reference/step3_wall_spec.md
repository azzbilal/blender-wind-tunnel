# Step 3 spec: wall treatment and surface resolution

Grill answers and probe amendments (Bilal, 2026-10-24), locked before any code. Measurements and probes:
`validation/step3_wall_v2512.json` (Stage 1 `tools/audit/step3_yplus.py`; probes `tools/audit/step3_probe*.sh`,
`step3_probe.py`, `step3_icosphere.py`). OpenFOAM v2512; source paths relative to
`/usr/lib/openfoam/openfoam2512/src` unless they start with `applications/` or `etc/`.

## Rules the code implements (final)

L = the body's largest dimension (`case3d.tunnel`), level0 = L / cells_per_L, (lo1, lo2) = body surface levels
(COARSE (2 3), L/6; MEDIUM (3 4), L/8), Delta = level0 / 2^lo2, r = 1.3.

| Quantity | Rule | L 2 m, U 20 m/s, COARSE |
|---|---|---|
| u_tau_ref | 0.0386 U (Re_L / Re_a)^(-1/14), Re_L = U L / nu, Re_a = 20 x 2 / 1.5e-5 = 2.67e6 | 0.772 m/s |
| y_c (first cell centre) | 100 nu / u_tau_ref | 1.94 mm |
| h1 = firstLayerThickness | 2 y_c, metres | 3.89 mm |
| n_half | ceil(1 + ln(Delta / (2 h1)) / ln r) | 8 |
| n_depth | floor(ln(1 + Delta (r - 1) / h1) / ln r) | 5 |
| nSurfaceLayers | min(n_half, n_depth), at least 1 | 5 (stack 35 mm) |
| minThickness | 0.5 h1, metres | 1.94 mm |

snappyHexMeshDict: `relativeSizes false; thicknessModel firstAndExpansion; firstLayerThickness h1;
expansionRatio 1.3; minThickness 0.5 h1; nSurfaceLayers n; featureAngle 60; nGrow 0` (no
finalLayerThickness); body in refinementSurfaces gets `curvatureLevel (24 0 lo2 -1)`.

Gates (reported in forces.json and the panel; the panel warns on either):
- y+ <= 300 on at least 90 % of the body area (OpenFOAM `yPlus` FO, area-weighted).
- Layer coverage = faces extruded / body faces, from snappy's final "Extruding X out of Y faces" line in
  log.snappyHexMesh, at least 90 %.
Information only: y+ min/mean/max, area fraction 30 < y+ < 300, area fraction y+ < 5, mean layers / target
and overall thickness % of target (snappy's layer table: patch, faces, target, mesh, thickness m, %).
If a converged run fails the y+ gate: re-derive u_tau from that run (area-weighted mean of
y+ nu / nearWallDist), re-mesh and re-solve once, then report.

## Q1. Target y+ and first-layer height

- Target y+ 100 at the anchor u_tau/U = 0.0386: the area-weighted mean on the sphere (3d_Sphere, v1912 field
  at 400, unconverged, so approximate). The Re^(-1/14) factor is the flat-plate shape (Cf ~ Re^(-1/7)) and only
  transfers the anchor to other U and L.
- Layer height = 2 y_c: `yPlus` uses `nearWallDist` (functionObjects/field/yPlus/yPlus.C:136-157;
  nutUSpaldingWallFunctionFvPatchScalarField.C:322-343); measured d / first layer = 0.499 on the sphere.
- Stage 1 extrapolation (u_tau unchanged) at y_c 1.94 mm: y+ <= 300 on 100 % of sphere, cone, cube; mean y+
  98 / 85 / 43. Sphere 90 % limit y_c 3.9 mm, so u_tau may double before the gate fails.
- Cross-check only: flat-plate sqrt(Cf/2) with Cf = 0.026 Re^(-1/7) (Cadence y+ calculator, attributed to
  White, Fluid Mechanics 5th ed. p. 467; not read) gives 0.0396, with 0.027 Re_x^(-1/7) (course notes citing
  White) 0.0404: 3 to 5 % above the anchor.
- Why 100, not 130: exceeding 300 costs a re-mesh and re-solve, y+ < 30 is harmless with
  nutUSpaldingWallFunction (continuous in y+), and the anchor is from an unconverged field.

## Q2. Layers (amended by A1 and A3)

- firstAndExpansion, h1 = 2 y_c, r = 1.3, nGrow 0, layerTerminationAngle default.
- A1, stack cap: n = min(n_half, n_depth). Evidence (round 2): 960-triangle UV sphere 62 % coverage at n 8
  (93 mm, 2.2 Delta) but 99.2 % at n 5; 5120-triangle icosphere 100 % at n 8 and n 5. Faceting, not stack
  depth alone, breaks deep stacks; the cap keeps coarse STLs meshable. Last-layer jump 3.7x (v2512's annotated
  snappyHexMeshDict example uses finalLayerThickness 0.3, about 3.3x).
- A3, featureAngle 60 (Q2 had 120). Criterion (unchanged): 120 only if coverage rises AND checkMesh is clean
  AND max non-orthogonality and skewness are no worse. Round 3 at n 5: cone coverage 97.0 % (60) vs 93.7 % (120),
  cube 100 % at both with max skewness 0.47 vs 2.45. 120 fails on both.
- A2, coverage definition as in the gates above. Faces with fewer layers get a thicker first cell (sphere n 5:
  2.6 % of area, d up to 9.9 mm); the y+ gate catches them, not the face count.
- Dropped layers: no extra fallback; below 90 % coverage the run reports FAIL with snappy's table.

## Q3. Absolute sizes

- relativeSizes false: with true, snappy multiplies firstLayerThickness by the local undistorted cell edge
  (mesh/snappyHexMesh/snappyHexMeshDriver/snappyLayerDriver.C:1618-1625, edgeLen from the point level at
  :1563-1566), so y+ would halve per refinement level.
- minThickness 0.5 h1: points whose stack falls below it get no layers (truncateDisplacement, :2274), first
  cell centre about Delta/2 (y+ about 1000 at sphere u_tau); above it a squeezed stack keeps thinner layers.
  Judgement value, close to the old 0.1 relative on 20.8 mm cells.

## Q4. Surface resolution

- curvatureLevel (24 0 lo2 -1): per triangle level = round(log2(nCurvCells level0 / r)) up to lo2
  (mesh/snappyHexMesh/refinementSurfaces/refinementSurfaces.C:1240-1250; level0 from
  applications/utilities/mesh/generation/snappyHexMesh/snappyHexMesh.C:1384-1388; curvature reset on sharp
  edges :1043-1131). COARSE: level = round(log2(4 L / r)). COARSE stays the default.
- Probe: the whole UV sphere (32 segments x 16 rings, 960 triangles, 11.25 deg facets, median edge 0.196 m)
  goes to level 3 at front, side and rear: 151 cells around by level (75 before), 136 faces counted in one
  equator row. Cube flat faces unchanged; cone at level 3.

## Q5. Re-runs and panel

- Stage 4 re-runs Sphere, Cube, Cone one at a time on 24 ranks, fresh cases from their body.stl in
  `~/wind_tunnel/_step3/run_<body>`, real Allrun to the step 2 gate. Probe cell counts at the final settings:
  cube 368,124, cone 363,123 (round 3), sphere about 389k (round 2 at featureAngle 120; smooth surface, same
  at 60). Estimate (0.24 / 0.32 / 0.25 s per iteration at about 350k cells): cube about 7.5 min, cone about
  4 min, sphere up to 13 min.
- Record per body: cells, coverage, mean layers, y+ min/mean/max, y+ <= 300 fraction, band and y+ < 5
  fractions, gate iteration, Cd window mean; Cd change against step 2 (cube 1.1498, cone 0.5833); the sphere's
  gated v2512 Cd becomes its baseline.
- Panel warns on the two gates; FIX_PLAN step 3 acceptance text is updated to them at close.

## Notes

- A4: Suzanne fails checkMesh by 2 faces at skewness 4.70 at featureAngle 60 and 120, and the current solved
  3d_Suzanne mesh has the same failure (4.700331): it predates this slice (castellation and snap). Not gated.

## Open issues (logged, not in this slice)

- Coarse-STL warning in the add-on: compare STL edge length or facet angle with the local surface cell, offer
  an optional subdivide before export. Evidence: icosphere (median edge 0.076 m) 100 % vs UV sphere (0.196 m)
  62 % at n 8 (probe_round2).
- UV sphere zero-layer faces are not at the poles: 48 faces at 67 and 79 deg from the poles, next to the ring
  edges at 22.5 and 11.25 deg latitude; pole caps (< 15 deg) carry all layers; cause not resolved.
- Suzanne: layers collapse at any depth (30 to 35 % faces extruded, tet quality failures at iteration 1);
  curvatureLevel (48 0 4 -1) raised no face to level 4.
