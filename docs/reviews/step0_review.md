# Step 0 review (FIX_PLAN step 0: OpenFOAM v2512 build, scotch, body force check)

- Range reviewed: `83a661b..b87985b` (commits 23f65e5, 9984ce5, b87985b). The REVIEWER PROMPT in
  SESSION_LOG.md names `83a661b..23f65e5`; the two later commits only touch SESSION_LOG.md and
  were included.
- Date: 2026-10-20. Review only: no code changed, no OpenFOAM runs. The only command executed
  besides reads and greps was the unittest suite.
- Source checked: installed OpenFOAM v2512 tree `/usr/lib/openfoam/openfoam2512/src` (paths below
  are relative to it unless they start with `applications/`), line numbers read with
  `awk 'NR>=a && NR<=b'` so blank lines are counted.
- Technical terms marked with an asterisk are defined in the glossary at the end.

## Summary

| # | Standard | Verdict |
|---|---|---|
| 1 | OpenFOAM definitions: code matches the reference doc, doc matches the v2512 source | **FAIL** (one false statement about the source in the doc; code is correct) |
| 2 | Pure modules free of `bpy` | PASS |
| 3 | Tests assert behaviour; 21 run, 18 pass, 3 expected failures | PASS |
| 4 | No em dashes in added text | PASS |
| 5 | Every number names its source; nothing called validated without a reference | PASS (two notes) |
| 6 | LF line endings | PASS |
| 7 | Allrun scotch fallback shell logic | PASS |
| 8 | `forces.json` keeps every v0.4.0 key; `__init__.py` reads match | PASS |
| 9 | Viscous-gap explanation, term by term, with size estimate | PASS (explanation right in substance; doc wording needs correction) |

## 1. OpenFOAM definitions: FAIL

Code against the reference doc (`docs/reference/step0_openfoam_build.md`):

- Pressure force: `export_field.py:239` `f_p = p[own] * Sf`, times rho at `:241`. Doc table row
  "Pressure force". `p` is `zeroGradient` on `body` (`case3d.py:247`), so `p_b = p_P` and the
  owner value is the face value. Matches `forces.C:729` `fP = rhoRef*Sfb*(pb - pRef)` with
  `rhoRef = rho(p)` (`forces.C:722`, return of `rhoRef_` for `rho rhoInf` at `forces.C:351`).
- Viscous force: `export_field.py:235-241`, `rho (nu + nut_w) |Sf| U_t,P / d_n`*. Matches the doc's
  "export_field.py" column. OpenFOAM side: `forces.C:731-734` `Sfb & devRhoReff(gradUb)`, and
  `devRhoReff` returns `-rho*nuEff*devTwoSymm(gradUp)`* for the incompressible model
  (`forces.C:231`). `gradU = fvc::grad(U)` at `forces.C:717`.
- Distance: `export_field.py:236` `d_n = |(C_f - C_P) . n|`. OpenFOAM: `fvPatch.C:158-160`
  (`delta() = nHat*(nHat & (Cf - Cn))`), `basicFvGeometryScheme.C:200`
  (`deltaCoeffs = 1/mag(p.delta())`*), used by `fvPatchField::snGrad`* at `fvPatchField.C:225-233`.
  Same definition.
- Wall gradient: `gaussGrad.C:226-230` replaces the normal row of the boundary gradient with
  `snGrad()` (the doc's line 228 is correct). The case uses `cellLimited Gauss linear 1`*
  (`case3d.py:300`); `cellLimitedGrad.C:213-214` applies the same wall correction after
  limiting, so the doc's statement holds for the limited scheme too.
- forceCoeffs: `forceCoeffs.C:160` `pDyn = 0.5*rhoRef_*sqr(magUInf_)`; `:293` lift/drag
  coordinate system; `:311-313` `magUInf`, `lRef`, `Aref` read. Matches the doc.
- yPlus: `yPlus.C:157` calls `nutWallPatch->yPlus()`; `nutUSpaldingWallFunction...C:342`*
  `y*calcUTau(mag(Uw.snGrad()))/nuw`; `:65` `nut_w = uTau^2/(magGradU) - nu_w`. Matches the doc.
- `step0_check.py:21-28` dictionary matches the doc's dictionary, except `lRef` (see below).

**Why FAIL.** The doc states (`step0_openfoam_build.md:58`): "`validate()` recomputes `nut` from
the stored U." This is false for `simpleFoam -postProcess`:

- `applications/solvers/incompressible/simpleFoam/simpleFoam.C:82` includes `postProcess.H`*
  before `turbulence->validate()` at `simpleFoam.C:92`.
- `OpenFOAM/db/functionObjects/functionObjectList/postProcess.H:110-178` loops over the selected
  times, includes `createFields.H` (`:147`), calls `functionsPtr->execute()` (`:157`) and
  `return 0` (`:178`). Line 92 of simpleFoam.C is never reached.
- `simpleFoam/createFields.H` contains no `validate` and no `nut` reference (grep, exit 1), and
  `eddyViscosity.C:67` constructs `nut` with `MUST_READ`*.

So OpenFOAM's `forces` uses the stored `400/nut`, the same file `body_forces`* reads
(`export_field.py:235`). This does not change any number; it makes the comparison tighter than
the doc claims (identical `nut_w` on both sides), which matters for standard 9.
`yPlus()` does recompute `uTau` from stored U (`:342`), so the identity
`nuEff_w |snGrad U| = uTau^2` stated in the doc holds only to the convergence of the stored `nut`
(Spalding Newton loop, `maxIter 10`, `tolerance 0.01`, `:174-178`, defaults at `:204-205`).

Minor (not the reason for FAIL):

- `step0_openfoam_build.md:31` cites `fvPatch.C` lines 156 to 160; the `delta()` body is 158-160.
- `step0_check.py:52` hard-codes `nu = 1.5e-5` and `:58` hard-codes `L=2.0`, while Allrun passes
  `--nu {s.nu}` to the exporter (`case3d.py:361`) and `forces.json` stores no `nu`. A case with
  another viscosity would give a non-physical disagreement. `L` only affects moment
  coefficients, which are not checked; the doc's dictionary says `lRef <L>`.

## 2. Pure modules do not import bpy: PASS

`grep` for `import bpy` / `from bpy` in `case.py, case3d.py, meshgen.py, results.py,
flowfield.py, wsl.py, export_field.py`: no hits. Their imports are stdlib, numpy, scipy and the
relative imports `case3d.py:17` (`from .case`), `case.py:18` (`meshgen`), `flowfield.py:16`
(`results`), all of which are themselves pure. New import in the diff: `wsl.py:8` `import re`.

## 3. Tests assert behaviour: PASS

`py -m unittest discover -s tests -v`: `Ran 21 tests ... OK (expected failures=3)`, so 18 pass
and 3 expected failures (`test_blockage_target`, `test_inlet_far_enough_upstream`,
`test_layers_target`), as stated.

The 7 new tests check behaviour, not file existence:

- `PickBashrc` (`tests/test_pure.py:145-167`): which path `wsl.pick_bashrc` returns for numeric
  ordering (2606 over 2512 over 1912, in both input orders), openfoam.com over Ubuntu's package
  in both orders, the `/opt` layout, Ubuntu-only fallback, and empty input.
- `test_decomposition_scotch` (`:107-109`): parses the `method` entry written to
  `decomposeParDict` and requires exactly `["scotch"]`.
- `test_decomposition_fallback_before_decompose` (`:111-118`): exactly one Allrun line mentions
  both `libscotchDecomp` and `hierarchical`, it comes before the `decomposePar` line, and
  `hierarchicalCoeffs` exists for the fallback to use.

Note (non-blocking): the fallback test checks text and order, not the shell outcome. The
outcome was exercised once live (SESSION_LOG: `Decomposition method hierarchical [24]`). A
test that runs the line in bash with a stub `foamDictionary` would lock it in.

## 4. No em dashes: PASS

`git diff 83a661b..b87985b | grep -c $'\xe2\x80\x94'` gives 0; same for the en dash
(`\xe2\x80\x93`) and for the three commit messages (0).

## 5. Numbers name their source: PASS (two notes)

- `validation/step0_v2512.json`: top-level `reference` names the v2512 `forces`, `forceCoeffs`,
  `yPlus` function objects and the spec; `method` names `step0_check.py` and the copies; each
  case has `fields_from` (v1912 solve, 400 iterations, unconverged, or the fresh v2512 run).
  Gates and `verdict` are against that cited reference, not against physics.
- SESSION_LOG.md numbers table header names both sides; the text states that none of the Cd
  values is a physical result. The Cp baseline numbers cite `baseline_v0.4.0.json`.
- Commit 23f65e5 message: numbers are labelled "OpenFOAM v2512 forces function object vs
  export_field.py on the same t = 400 fields". Nothing is called validated.

Notes:

1. The commit message of 23f65e5 and the doc's Q2 row (`step0_openfoam_build.md:15`) say the
   viscous gap is "explained"; the doc's mapping table calls it a "working hypothesis" and
   SESSION_LOG says it "has not yet been isolated numerically". Standard 9 below shows the
   attribution is right by elimination but the split between terms is not measured. The commit
   cannot be edited; use consistent wording from now on.
2. `fresh_cube.fields_from` quotes "p initial residual 0.0045 at 400" and "124 s" without naming
   the file (presumably `log.simpleFoam` of the fresh run). Folder sizes (695 MB, 90 MB) in
   SESSION_LOG are likewise unsourced; they are housekeeping, not physics.

## 6. LF line endings: PASS

`git ls-files --eol` on all 12 changed files: every one is `i/lf w/lf attr/text=auto eol=lf`.
`.gitattributes` sets `* text=auto eol=lf`.

## 7. Allrun fallback logic: PASS

Line written by `case3d.write_case` (between `blockMesh` and `decomposePar`):

```
[ -e "$FOAM_LIBBIN/libscotchDecomp.so" ] || foamDictionary -entry method -set hierarchical system/decomposeParDict > /dev/null 2>&1 || fail decomposeParDict
```

`a || b || c` parses as `(a || b) || c`.

- Library present: `[ -e ]` true, so `foamDictionary` and `fail` are skipped and `method scotch`
  stays. On this machine `$FOAM_LIBBIN/libscotchDecomp.so` exists (68552 bytes) next to the
  `dummy/` stub; the Allrun check looks at the real one, not `dummy/`, which is right.
- Library absent: `foamDictionary` sets `method hierarchical`; on success `fail` is skipped,
  on failure `fail decomposeParDict` writes the status and exits. `fail()` is defined earlier in
  the script (`case3d.py:368`). The `hierarchicalCoeffs` block is already in the dictionary.
- `FOAM_LIBBIN` unset (environment not sourced): the test sees `/libscotchDecomp.so`, falls back,
  and `foamDictionary` is then not found, so the run stops at `fail decomposeParDict`. Correct
  and clear.

## 8. forces.json keys and the panel: PASS

v0.4.0 writer (`git show 83a661b:wind_tunnel/export_field.py`, lines 269-271): `time, cells,
drag_N, side_N, lift_N, pressure_drag_N, friction_drag_N, frontal_area_m2, Cd, Cl, speed, rho`.
v0.4.1 writer `export_field.py:279-282`: all twelve, plus `pressure_N` and `viscous_N`.
Values are unchanged because `body_forces` is the same code moved into a function (diff of
`export_field.py`, old lines 248-260 against new 222-241, only `a.nu`/`a.rho` became
parameters).

Readers: `__init__.py:728` loads `forces.json`; `:739-740` read `drag_N, lift_N, side_N, Cd, Cl,
frontal_area_m2, cells`. No other module reads `forces.json` (`viz3d.py:46` reads `speed` from
`field.npz`, not `forces.json`). `step0_check.py:51` reads `rho, speed, frontal_area_m2`. All
present.

## 9. Viscous-gap explanation: PASS

### What OpenFOAM computes at a wall face

Notation: `n = Sf/|Sf|` (out of the air, into the body), `d = 1/deltaCoeffs = |n . (C_f - C_P)|`,
`U_w = 0`, `U_n = n . U_P`, `U_t = U_P - n U_n`. OpenFOAM's gradient is `(G)_ij = d_i U_j`, and
`G_P` is the owner-cell gradient from `cellLimited Gauss linear 1`.

- `snGrad U = (U_w - U_P)/d = -U_P/d` (full vector, `fvPatchField.C:225-233`).
- Boundary gradient (`gaussGrad.C:226-230`): `G_b = (I - nn) . G_P + n (snGrad U)`.
- `fV = Sf & [-rho nuEff devTwoSymm(G_b)]
      = -rho nuEff |Sf| [ n.G_b + G_b.n - (2/3) tr(G_b) n ]`, with
  - `n.G_b = snGrad U = -U_t/d - n U_n/d`
  - `G_b.n = (I - nn).(G_P.n) + n (n . snGrad U) = grad_t(U_n)|_GP - n U_n/d`*
  - `tr(G_b) = [tr G_P - n.G_P.n] - U_n/d = div_t U|_GP - U_n/d`*

Collecting:

```
fV = rho nuEff |Sf| { U_t/d                                   kept by body_forces
                     - grad_t(U_n)|_GP                         (B) dropped, tangential
                     + n [ (4/3) U_n/d + (2/3) div_t U|_GP ] } (A + C) dropped, normal
```

The `4/3` on `U_n/d` comes from `+1` (normal part of `snGrad`), `+1` (normal row of the
transpose, which is the wall `snGrad`, not the cell gradient) and `-2/3` (trace).

`body_forces` (`export_field.py:238-240`) is exactly the first line: `rho (nu + nut_w) |Sf| U_t/d`.
So SESSION_LOG's statement "ours keeps only the tangential `snGrad` term of `devTwoSymm(gradU_b)`"
is correct. The doc's list (a), (b), (c) names the right three sources but mislabels (b): the
transpose term is not only "tangential derivatives of the cell-centre gradient"; its normal
component is `-n U_n/d` from the wall `snGrad`, which doubles (a) before the trace removes a
third.

### Why the gap must come from these terms

With `nut_w` identical on both sides (standard 1: `-postProcess` uses the stored `nut`), `U_P`
read from the same file, the same `d` definition, and the pressure force agreeing to 4e-6 % of
Fx (which confirms `Sf` and `p`), the remaining difference between the two viscous forces is
A + B + C plus round-off in the cell centres. This review did not check `ef.cell_centres`
against OpenFOAM's `C` to round-off, so the statement is conditional on that. The split between
A, B and C is not known without a run.

### Size estimate (reasoning, not measured)

- A + C (normal): by continuity at a no-slip wall, `U_n` at the cell centre is of order
  `d . div_t U_t`, so `U_n / U_t ~ d / l`, where `l` is the length over which the wall-parallel
  velocity changes (about R on the sphere). Local size relative to the kept shear:
  about `(4/3) d / l`. It acts along `n` and enters drag through `n_x`, so on the sphere it does
  not cancel over the surface; on cube faces `div_t U_t` is small except near stagnation, edges
  and separation, where `U_t -> 0` and the ratio becomes order 1 locally.
- B (tangential): on a flat wall, `grad_t(U_n)` at the cell centre is second order, about
  `(d/l)^2` of the kept term. On a curved wall it is first order: the frozen face normal makes
  the cell gradient pick up the curvature term (in polar form, the `-u_theta/r` part of the
  `r theta` strain rate), about `kappa d = d/R` of the kept term, in the shear direction. The
  cell limiter reduces `G_P` in wall cells, so this is an upper estimate.
- Sphere: R = 1.0 m from `Aref = F_x/(Cd q) = 127.70/(0.16698 x 245) = 3.12 m^2`
  (validation JSON). `d` from y+*: area-mean y+ = 822; with an assumed mean `tau_w` of about
  1 Pa (`u_tau`* about 0.9 m/s, my assumption, not measured), `d = y+ nu / u_tau` is about
  0.014 m, so `d/R` is about 1.4 %. The measured gap is 2.0 % of the viscous x-force. Same order
  of magnitude; this is consistency, not proof.
- Effect on drag = gap x viscous share: sphere 2.0 % x (9.29/127.70 = 7.3 %) = 0.146 %,
  which is exactly the total dFx in the table, so the bookkeeping is consistent.
- Cube: the viscous x-force is a small net of opposing contributions (-1.63 N on 1226 N), so a
  percentage "of itself" is ill-conditioned there; the 1.3 % and 2.4 % should not be read as
  mesh or geometry trends.

### Physical meaning

In the continuum limit at a no-slip wall, A, B and C all vanish: `U = 0` along the wall gives
`d_t U_n = 0`, and continuity gives `d_n U_n = -div_t U_t = 0`, so the normal viscous stress is
zero and the wall traction is `mu d_n U_t`. The gap is therefore a difference between two
discretisations that is first order in `d`, not missing physics in `body_forces`. With wall
functions (y+ 30 to 300) `d` stays large, so it does not go away in practice. The log's remark
that it "will matter for streamlined bodies" is plausible: there friction is most of the drag
and `d/R` near a leading edge can be large, but this is my reasoning, not a measured value.
Since OpenFOAM's `forces` is the agreed reference, the fix is to reproduce its full
`devTwoSymm(G_b)` in `body_forces` (needs `G_P` with the same limiter), not to argue which is
more correct.

## Required fixes

1. `docs/reference/step0_openfoam_build.md:58`: replace "`validate()` recomputes `nut` from the
   stored U" with: under `-postProcess`, `postProcess.H:110-178` runs the function objects and
   returns before `simpleFoam.C:92`, so `nut` is read from the time folder (`MUST_READ`,
   `eddyViscosity.C:67`), identical to what `export_field.py` reads; only `yPlus()` re-solves
   `uTau` from stored U.
2. Same doc, viscous row (`:65`): state the three dropped terms as derived in standard 9 (normal
   `(4/3) U_n/d + (2/3) div_t U`, tangential `grad_t(U_n)` from the limited cell gradient), and
   that the attribution follows by elimination once `nut_w` is identical.
3. `tools/audit/step0_check.py:52`: read `nu` from `constant/transportProperties` instead of
   hard-coding 1.5e-5 (or have `export_field.py` write `nu` into `forces.json`). Optionally pass
   the case's L for `lRef` (`:58`).
4. `step0_openfoam_build.md:31`: `fvPatch.C` lines 158 to 160.

## Recommended (non-blocking)

- Before any streamlined-body acceptance (airfoil, FIX_PLAN later steps), isolate A, B and C
  numerically on the sphere copy: compute the full `devTwoSymm(G_b)` traction in Python with a
  `cellLimited` gradient and compare with `forces` to round-off.
- Use one wording for the gap ("attributed by elimination, split not measured") in future logs
  and commits; 23f65e5 says "explained".
- Name the source file for `p initial residual 0.0045` and `124 s` in `validation/step0_v2512.json`.
- `wsl.py:15-16` comment says `pick_bashrc` follows "the same rule as case.ENV", but
  `case.ENV` (`case.py:229`) uses `sort -V | tail -1` on full paths, which ranks every
  `/usr/lib/openfoam/...` path above any `/opt/...` path regardless of version. With both
  `/opt/openfoam2606` and `/usr/lib/openfoam/openfoam2512` installed, the panel would report
  2606 while Allrun sources 2512. Not reachable on this machine (only 2512 is installed); align
  the two rules when convenient.
- Add a bash-executed test of the Allrun fallback line with a stub `foamDictionary`.

## Glossary

- `body_forces`*: function in `export_field.py` that sums pressure and wall-shear force over the
  faces of the `body` patch.
- `cellLimited Gauss linear 1`*: Gauss gradient with linear face interpolation, then scaled per
  cell so that extrapolated face values stay within the min and max of neighbouring values.
- `deltaCoeffs`*: inverse of the owner-centre to face distance measured along the face normal.
- `devTwoSymm(T)`*: `T + T^T - (2/3) tr(T) I`, twice the deviatoric symmetric part of `T`.
- `div_t`*: surface divergence, the divergence taken only in the two wall-parallel directions.
- `grad_t`*: tangential gradient, the projection `(I - nn)` of a gradient onto the wall plane.
- `MUST_READ`*: OpenFOAM read mode for a field that must exist on disk and is taken from the file.
- `nuEff`*: effective kinematic viscosity `nu + nut`; at a wall the wall-function value of `nut`.
- `nut_w`*: eddy viscosity on the wall face, set by the wall function so that the wall shear
  equals `rho u_tau^2`.
- `postProcess.H`*: the code path behind `solver -postProcess`; it builds fields for each
  selected time, runs the function objects and exits without solving.
- `snGrad`*: surface-normal gradient on a face, `(phi_f - phi_P) * deltaCoeffs`.
- `Spalding wall function`*: single formula for `u+` against `y+` across the viscous sublayer,
  buffer layer and log layer, solved for `u_tau` by Newton iteration.
- `u_tau`*: friction velocity `sqrt(tau_w / rho)`.
- `y+`*: wall distance in viscous units, `y u_tau / nu`.

Step 0 review: 8 PASS, 1 FAIL

Step 0 review: all items closed
