# Step 3 spec: wall treatment and surface resolution

Grill answers (Bilal, 2026-10-24), locked before any code. Measurements: `validation/step3_wall_v2512.json`
(Stage 1, `tools/audit/step3_yplus.py`). OpenFOAM v2512; source paths relative to
`/usr/lib/openfoam/openfoam2512/src`.

## Q1. Target y+ and first-layer height (locked)

- First cell-centre distance y_c = 100 nu / u_tau_ref, with
  u_tau_ref = 0.0386 U (Re_L / 2.67e6)^(-1/14), Re_L = U L / nu.
  0.0386 is the area-weighted mean u_tau/U measured on the sphere (3d_Sphere, v1912 field at 400,
  unconverged: the anchor is approximate). The Re^(-1/14) factor is the flat-plate shape
  (Cf ~ Re^(-1/7), u_tau ~ sqrt(Cf)) and only transfers the anchor to other U and L.
- First layer height = 2 y_c. Basis: `yPlus` uses `nearWallDist` (functionObjects/field/yPlus/yPlus.C:136-157;
  nutUSpaldingWallFunctionFvPatchScalarField.C:322-343); measured d / first layer = 0.499 on the sphere.
- For L = 2 m, U = 20 m/s: y_c = 1.94 mm, first layer 3.89 mm. Stage 1 extrapolation (u_tau unchanged):
  y+ <= 300 on 100 % of sphere, cone and cube; mean y+ 98 / 85 / 43.
- Cross-check only: flat-plate u_tau/U = sqrt(Cf/2) with Cf = 0.026 Re^(-1/7) (Cadence y+ calculator,
  attributed to White, Fluid Mechanics 5th ed. p. 467; not read) gives 0.0396, with 0.027 Re_x^(-1/7)
  (course notes citing White) 0.0404: 3 to 5 % above the anchor.
- Why 100 and not 130: exceeding 300 costs a re-mesh and re-solve, y+ < 30 is harmless with
  nutUSpaldingWallFunction (continuous in y+), and the anchor comes from an unconverged field, so the
  larger margin (u_tau may double before the sphere's 90 % limit of 3.9 mm) is taken.
- Gate: y+ <= 300 on at least 90 % of the body area. Reported, not gated: area fraction with
  30 < y+ < 300, area fraction with y+ < 5, y+ min/mean/max.
- Rule: if a converged run fails the gate, re-derive u_tau from that run (area-weighted mean of
  y+ nu / nearWallDist) and re-mesh and re-solve once before reporting a FAIL.

## Q2. Layer count, expansion, featureAngle (locked)

- `thicknessModel firstAndExpansion`: firstLayerThickness h1 = 2 y_c (Q1), expansionRatio r = 1.3.
- nSurfaceLayers n = ceil(1 + ln(Delta / (2 h1)) / ln r), Delta = cell size at the body's finer surface
  level (Q4), so the last layer is about half the adjacent cell (0.5 to 0.6 Delta after rounding up).
  h1 = 3.89 mm: n = 5 (stack 35 mm) on 20.8 mm cells, 4 (24 mm) on 15.6 mm cells.
- `featureAngle 120` (was 60), `nGrow 0`, `layerTerminationAngle` default (0.5 featureAngle).
  featureAngle is "when not to extrude surface; 90 is when two faces are perpendicular"
  (etc/caseDicts/annotated/snappyHexMeshDict, v2512 example value 120). Hypothesis: 60 stops extrusion
  at the cube's 90 degree edges and the cone's base rim (coverage now 77.9 % and 83.6 %).
- Probe after Q4, before Stage 3: snappy only, on a copy of the cube, featureAngle 60 vs 120 with the
  chosen layer settings. 120 passes only if layer coverage rises AND checkMesh reports no failed
  checks AND max non-orthogonality and max skewness are no worse than at 60. Both results recorded in
  `validation/step3_wall_v2512.json`.
- Dropped layers: no extra fallback logic. snappy's layer table (patch, faces, layers, overall
  thickness m and %) is parsed from log.snappyHexMesh into forces.json; gate layer coverage >= 90 %.
  Below that: FAIL reported with the table (re-meshing from u_tau does not address edge or quality drops).

## Q3. Absolute sizes (locked)

- `relativeSizes false`: with true, snappy multiplies firstLayerThickness by the local undistorted cell
  edge (mesh/snappyHexMesh/snappyHexMeshDriver/snappyLayerDriver.C:1618-1625, edgeLen from the point
  level at :1563-1566), so the first layer and y+ would halve per refinement level.
- `minThickness = 0.5 h1` in metres (1.94 mm for L 2 m, U 20 m/s). Points whose stack falls below it get
  no layers (truncateDisplacement, :2274), leaving a first cell centre about Delta/2 from the wall
  (y+ about 530 on the sphere); above it a squeezed stack keeps n thinner layers (lower y+, harmless).
  0.5 h1 is a judgement value, close to the current 0.1 relative on 20.8 mm cells (2.1 mm).

## Q4. Surface resolution (locked)

- Body entry in refinementSurfaces gets `curvatureLevel (24 0 lmax -1)`, lmax = the body's max surface
  level (3 on COARSE, 4 on MEDIUM). COARSE stays the default.
- v2512 per triangle: level = round(log2(nCurvCells level0EdgeLength / r)), raised up to lmax only
  (mesh/snappyHexMesh/refinementSurfaces/refinementSurfaces.C:1240-1250); level0EdgeLength is the
  background cell (applications/utilities/mesh/generation/snappyHexMesh/snappyHexMesh.C:1384-1388);
  curvature is reset on sharp edges (:1043-1131). With level0 = L/6: level = round(log2(4 L / r)).
- Expected: sphere (r = L/2) level 3 everywhere, 151 cells around (75 now); cone circumferential radius
  at the base r/cos(26.6 deg) = 1.12 m, level 3; cube flat faces unchanged (features stay level 3).
- Probe (with the Q2 probe): snappy only on copies of the cube and the sphere. Record cell count,
  cells around the sphere, layer coverage, checkMesh, the sphere STL tessellation (segments and rings)
  and the resulting refinement level per region (snappy measures curvature from the triangles).
  If sphere layer coverage is under 90 % (8 layers, 93 mm stack on 41.7 mm cells): stop and show Bilal
  the table; no fallback chosen without him.

## Q5. Re-runs and panel (locked)

- Stage 4 re-runs Sphere, Cube, Cone (the acceptance bodies), one at a time on 24 ranks, each a fresh case
  written by the new case3d from its existing body.stl into `~/wind_tunnel/_step3/run_<body>`, through the
  real Allrun to the step 2 gate. Estimate from v2512 _step1 logs (0.24 / 0.25 / 0.32 s per iteration at
  about 350k cells): cube about 7.5 min (1830 it), cone about 4 min (725 it), sphere up to 13 min (cap),
  times the cell growth the probe measures; plus one Q1 re-mesh per body that fails the y+ gate.
- Record per body: cells, layer coverage, y+ min/mean/max, y+ <= 300 fraction, band fraction, y+ < 5
  fraction, gate iteration, Cd window mean; Cd change against step 2 for cube (1.1498) and cone (0.5833);
  the sphere's gated v2512 Cd becomes its baseline (no comparison claimed).
- Panel: warning when y+ <= 300 covers under 90 % of the area or layer coverage is under 90 %; band
  fraction (30 < y+ < 300) and y+ < 5 fraction shown as information. FIX_PLAN step 3 acceptance text is
  updated to these gates at close.
- Probe also meshes Suzanne (mesh only, no solve): cell count, layer coverage, checkMesh at featureAngle
  60 vs 120, to check irregular and concave shapes. If Suzanne fails checkMesh at 120: stop and show Bilal.

## Amendments after the probes (2026-10-24)

A1 (Q2 layer count, locked): n = min(n_half, n_depth), n_depth = floor(ln(1 + Delta (r - 1) / h1) / ln r), the
largest n whose stack stays at or under one surface cell Delta. h1 3.89 mm, Delta 41.7 mm: n = min(8, 5) = 5,
stack 35 mm, last-layer jump 3.7x (v2512's annotated example uses finalLayerThickness 0.3, about 3.3x).
Evidence (round 2): 960-triangle UV sphere 62 % coverage at n 8 (93 mm, 2.2 Delta) but 99.2 % at n 5; 5120-triangle
icosphere 100 % at n 8 and n 5. Faceting, not stack depth alone, breaks deep stacks.

## Open issues (logged, not in this slice)

- Coarse-STL warning in the add-on: compare STL edge length or facet angle with the local surface cell, offer
  an optional subdivide before export. Evidence: icosphere (median edge 0.076 m) 100 % vs UV sphere 32 x 16
  (0.196 m) 62 % at n 8 (validation/step3_wall_v2512.json, probe_round2).
- UV sphere zero-layer faces are not at the poles: 48 faces at 67 and 79 deg from the poles, next to the ring
  edges at 22.5 and 11.25 deg latitude; cause not resolved.
- Faces where snappy reduces the layer count get a thicker first cell (sphere n 5: 2.6 % of area, d up to
  9.9 mm vs 1.94 mm, y+ up to about 5x target); caught by the y+ gate, not by face coverage.
- Suzanne: layers collapse at any depth (30 to 35 % faces extruded, tet quality failures at iteration 1);
  curvatureLevel (48 0 4 -1) raised no face to level 4; checkMesh fails by 2 pre-existing skew faces (4.70).
