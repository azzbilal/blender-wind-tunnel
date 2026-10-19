# Step 0 reference: OpenFOAM build, forces, forceCoeffs, yPlus

Build: **OpenFOAM v2512** (openfoam.com), Ubuntu package `openfoam2512-default` 2512.0-2, build
`bd2b6720-20260127` (`META-INFO/build-info`). Source is
the shipped `openfoam2512-source` tree under `/usr/lib/openfoam/openfoam2512/src`, which is the code
the installed libraries were built from (upstream tag `OpenFOAM-v2512`,
develop.openfoam.com/Development/openfoam). Paths below are relative to that `src`.

## Decisions locked (grill, 19 Oct 2026)

| # | Question | Answer |
|---|---|---|
| Q0 | Build | 2512 final release; 2606.0~rc2 removed (a pre-release is not a citable reference) |
| Q1 | Decomposition | `method scotch`; Allrun switches to `hierarchical` with `foamDictionary` only when `$FOAM_LIBBIN/libscotchDecomp.so` is missing |
| Q2 | Force check | Cube, Cone, Sphere copies at t = 400. Gates: total dFx, dFy, dFz each at most 0.5 % of total Fx; pressure dFx at most 0.1 % of Fx. Viscous part reported and explained, not gated |
| Q3 | Ubuntu 1912 leftovers | The 1912 solver was already replaced by the openfoam.com `openfoam` package. Purge the orphaned `libopenfoam` and `openfoam-examples` after this slice passes |

## forces (`functionObjects/forces/forces/forces.C`: lines 717 to 733, `devRhoReff` line 231, `rho(p)` line 351)

Per boundary face f of the listed patches, with `Sf` pointing out of the fluid:

- Pressure: `fP = rhoRef * Sf * (p_b - pRef/rhoRef)`. For kinematic p (incompressible),
  `rho(p)` returns `rhoInf`, which is mandatory with `rho rhoInf;`. `pRef` defaults to 0.
- Viscous: `fV = Sf & devRhoReff`, with `devRhoReff = -rhoInf * nuEff_b * devTwoSymm(gradU_b)`,
  `devTwoSymm(T) = T + T^T - (2/3) tr(T) I`, and `nuEff_b = nu + nut_b`, where `nut_b` is the
  wall-function value.
- `gradU = fvc::grad(U)` (our `gradSchemes`). On a wall patch, the Gauss gradient's boundary value
  is the owner-cell gradient with its normal part replaced by `snGrad(U) = (U_w - U_P) * deltaCoeffs`
  (`finiteVolume/finiteVolume/gradSchemes/gaussGrad/gaussGrad.C` line 228). On a non-coupled patch
  `deltaCoeffs = 1/|n . (C_f - C_P)|` (`fvMesh/fvGeometryScheme/basic/basicFvGeometryScheme.C` line 200,
  `fvMesh/fvPatches/fvPatch/fvPatch.C` lines 156 to 160).

## forceCoeffs (`functionObjects/forces/forceCoeffs/forceCoeffs.C`: lines 160, 293, 311 to 313)

`pDyn = 0.5 * rhoInf * magUInf^2`; `Cd = F . dragDir / (Aref * pDyn)`; `Cl` uses `liftDir`; moment
coefficients also divide by `lRef`. `CofR` only moves the moment centre, not the forces.

## yPlus with nutUSpaldingWallFunction (`functionObjects/field/yPlus/yPlus.C` line 157; `TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutUSpaldingWallFunction/nutUSpaldingWallFunctionFvPatchScalarField.C` lines 65, 342)

`yPlus = y * uTau / nu_w`. Here `y = turbModel.y()` (nearWallDist: normal distance from the cell
centre to the wall face), and `uTau` is from Newton iteration of Spalding's law on
`|snGrad(U)| = |U_w - U_P| * deltaCoeffs`. `calcNut` sets `nut_w = uTau^2 / |snGrad U| - nu`, so
by construction `nuEff_w * |snGrad U| = uTau^2`.

## Dictionary used for the check (run with `simpleFoam -postProcess -latestTime -dict system/step0Check`)

```
functions
{
    forces1      { type forces;      libs (forces); patches (body); rho rhoInf; rhoInf 1.225; CofR (0 0 0); }
    forceCoeffs1 { type forceCoeffs; libs (forces); patches (body); rho rhoInf; rhoInf 1.225; CofR (0 0 0);
                   dragDir (1 0 0); liftDir (0 0 1); magUInf 20; lRef <L>; Aref <frontal_area_m2 from forces.json>; }
    yPlus1       { type yPlus;       libs (fieldFunctionObjects); }
}
```

`simpleFoam -postProcess` builds the turbulence model, so `nuEff` and the wall-function `nut` are
available. `validate()` recomputes `nut` from the stored U.

## Mapping onto `wind_tunnel/export_field.py`

| Quantity | OpenFOAM | export_field.py | Expected agreement |
|---|---|---|---|
| Pressure force | `rhoInf * Sf * p_b` | `rho * p[owner] * Sf` | Identical: p is `zeroGradient` on the body, so `p_b = p_P`; pRef 0 in both |
| Viscous force | `-Sf & rho nuEff_b devTwoSymm(gradU_b)` | `rho (nu + nut_b) |Sf| U_t,P / d_n` | Same leading term `|Sf| rho nuEff (U_P - U_w) deltaCoeffs` (tangential part). Ours drops (a) the normal part of `U_P`, (b) the transpose term `gradU_b . n` (tangential derivatives of the cell-centre gradient), (c) the `-(2/3) tr(gradU)` term. On coarse curved wall cells these are not zero, which is the working hypothesis for the 2 % viscous gap on the sphere |
| Distance | `1/deltaCoeffs` (owner-centre to face, along n) | `d_n = |(C_f - C_P) . n|` | Same definition |
| Cd | `F . dragDir / (Aref pDyn)` | `F_x / (q * A_f)` | Same once `Aref = A_f` |
| y+ | `y uTau / nu`, Spalding | Not exported yet (FIX_PLAN step 3) | Audit used `y sqrt(nuEff |U_P| / y) / nu`, which equals Spalding's uTau by the `calcNut` identity |
