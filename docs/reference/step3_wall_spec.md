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
