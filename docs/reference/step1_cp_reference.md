# Step 1 reference: Cp referenced to freestream static pressure

Build: OpenFOAM v2512, source `/usr/lib/openfoam/openfoam2512/src` (paths below are relative to it).
Line numbers read with `awk 'NR>=a && NR<=b'`.

## Decisions locked (grill, 20 Oct 2026)

| # | Question | Answer |
|---|---|---|
| Q1 | Method | Post-process now. `p_inf` = area-weighted mean of p over the `inlet` patch, taken from the inlet faces' owner cells (p is `zeroGradient` there, `case3d.py:246`, and v2512 writes no `value` entry for it). Subtracted from the voxel-grid p only; `body_forces` keeps the raw p, so every existing `forces.json` value stays identical. New keys: `forces.json` `p_inf_Pa`, `p_inf_Cp_vs_outlet`; `field.npz` `p_inf_Pa`. BCs revisited in step 4 |
| Q2 | Where `p_inf` comes from | Inlet patch mean. Its non-uniformity and the mean on a cell plane 1 L downstream of the inlet are measured in Stage 5 as a bound on the body's disturbance there |
| Q3 | Acceptance | (1) OpenFOAM `surfaceFieldValue` areaAverage of p on `inlet` equals our `p_inf` within 0.001 q; ours reproduces `baseline_v0.4.0.json` inlet offsets (cone +0.011, sphere +0.005, v1912 fields). (2) Inlet mean Cp after the shift = 0 within 0.002 (code-path check; zero by construction). (3) Our body-patch Cp equals the `pressure` function object (`staticCoeff`) within 0.001 on every face. (4) Cube front-face stagnation Cp = 1.00 within 2 %, face nearest the front-face centre; area-weighted front-face mean reported. A miss is recorded and attributed, never tuned, and does not block the commit if (1) and (3) pass. Cone tip and sphere stagnation reported, not gated. (5) Headless Blender reads the VDB `cp` at a point on the grid's upstream face and half a voxel ahead of the cube's front-face centre (the grid starts 0.75 L upstream, `export_field.py:291`, so 2 L upstream is outside it) |

## The `pressure` function object (`functionObjects/field/pressure/pressure.C`)

- Modes: `staticCoeff` is `STATIC | COEFF` (`:56`); result field name `static(p)_coeff` (`:81`, `:120`).
- Kinematic p is scaled by `rhoInf` (`rhoScale`, `:153`): `rhoInf * p`. Incompressible p needs
  `rhoInf` set; in a COEFF mode it is read with `pInf` and `UInf` (`:432-434`).
- `calcPressure` starts from `pRef` (default 0, `:236`, `:405`), adds the hydrostatic term only if
  `hydrostaticMode` is given (`:180-183`, `:407-424`; default none), then adds `rhoInf p` (`:244`).
- `coeff` (`:294`, `:300`):

```
Cp = (pRef + rhoInf * p - pInf) / (0.5 * rhoInf * |UInf|^2 + SMALL)
```

`pInf` has dimensions of pressure (Pa), not m2/s2. With kinematic p_inf from our helper, the
dictionary needs `pInf = rho * p_inf_kin`.

```
cpCheck { type pressure; libs (fieldFunctionObjects); mode staticCoeff;
          pInf <rho * p_inf_kin>; UInf (<U> 0 0); rhoInf <rho>; writeFields yes; }
inletP  { type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name inlet;
          operation areaAverage; fields (p); writeFields false; }
```

`areaAverage` without a weight field is `sum(|Sf| p_f) / sum(|Sf|)`
(`functionObjects/field/fieldValues/surfaceFieldValue/surfaceFieldValueTemplates.C:240-242`).

## Why the BCs are not the fix (`finiteVolume/fields/fvPatchFields/derived/`)

Both are `mixed` conditions; `nf` points out of the domain.

- `freestreamPressure` (`freestreamPressure/freestreamPressureFvPatchScalarField.C:115-119`):
  `valueFraction = 0.5 + 0.5 (U_p . n)/|U_p|`. Pure inflow gives 0, a zero gradient; pure outflow
  gives 1, fixed `freestreamValue`.
- `freestreamVelocity` (`freestreamVelocity/freestreamVelocityFvPatchVectorField.C:104-106`):
  `valueFraction = 0.5 - 0.5 (U_p . n)/|U_p|`. Inflow fixed, outflow zero gradient.

On our inlet (pure inflow) this pair reduces to what we already have: U fixed, p zero gradient.
The pressure level would still be fixed only where flow leaves the domain, where the wake has
lowered the static pressure. So the pair alone does not remove the offset; fixing the upstream
static level needs a different inflow condition, for example `totalPressure` with p0 = p_inf + q,
or a far-field domain, both of which mean new solves (step 4).

## Mapping onto the add-on

| Quantity | OpenFOAM | Add-on |
|---|---|---|
| `p_inf` (kinematic) | `surfaceFieldValue` areaAverage of p on `inlet` | `export_field.inlet_reference_pressure`: `sum(|Sf| p_P)/sum(|Sf|)` over the inlet faces' owner cells |
| Cp | `static(p)_coeff` above | `export_field.cp_from_p(p, p_inf, U)`: `(p - p_inf)/(0.5 U^2)`, kinematic p |
| Grid pressure | | `field.npz` `p` = `rho (p_IDW - p_inf)` in Pa (`export_field.py:303`); `p_inf_Pa` stored alongside |
| VDB `cp` | | `viz3d.write_vdb`: `p / (0.5 rho U^2)` (`viz3d.py:49`, `:61`), unchanged; it is now relative to `p_inf` because `field.npz` p is |
| `forces.json` | | all v0.4.1 keys unchanged; adds `p_inf_Pa = rho p_inf`, `p_inf_Cp_vs_outlet = p_inf/(0.5 U^2)` |

Forces do not change: a constant added to p integrates to zero over a closed surface.
