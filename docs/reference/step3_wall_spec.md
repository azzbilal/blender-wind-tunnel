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
