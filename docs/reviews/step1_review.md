# Step 1 review (FIX_PLAN step 1: Cp referenced to the inlet static pressure)

- Range reviewed: `67eb372..0281002` (code commit 0281002) plus the session log commit 572e999,
  which only touches SESSION_LOG.md. `git diff 0281002..572e999 -- wind_tunnel tests tools` is
  empty, so the code under review is the same at HEAD.
- Date: 2026-10-21. Review only: no repository file changed except this report.
- Executed: the unittest suite; `tools/audit/step1_check.py` on a fresh copy of the Sphere
  (`~/wind_tunnel/_review1/Sphere`, 118 MB, copied from `_step1/Sphere` with `postProcessing/`,
  `400/static(p)_coeff`, `field.npz` and the step 1 logs removed and the v0.4.0 `forces.json`
  restored; `_step1` itself untouched); the headless Blender probe `tools/blender_cp_probe.py` on a
  copy of the Cube `field.npz`; one read-only numpy script (total pressure along the stagnation
  line, Cube and Sphere). No sudo, no solves.
- Source checked: installed OpenFOAM v2512 tree `/usr/lib/openfoam/openfoam2512/src` (paths below
  are relative to it), line numbers read with `awk 'NR>=a && NR<=b'`.
- Technical terms marked with an asterisk are defined in the glossary at the end.

## Summary

| # | Standard | Verdict |
|---|---|---|
| 1 | OpenFOAM definitions: `inlet_reference_pressure`, `cp_from_p` match the reference doc and the v2512 source; owner value = inlet face value | PASS (two stale line citations in the doc) |
| 2 | Units end to end; body forces still use the raw p | PASS (one latent coupling on rho) |
| 3 | Every number traces to a file; nothing called validated; cube stagnation stated as a miss | PASS (one wording error; attribution of the miss can be sharpened, see 3.4) |
| 4 | Tests assert behaviour; 26 run, 23 pass, 3 expected failures | PASS (two notes) |
| 5 | Pure modules free of `bpy` | PASS |
| 6 | No em dashes in added text | PASS |
| 7 | LF line endings | PASS |
| 8 | Version 0.4.2 in manifest and `bl_info` | PASS |

## 1. OpenFOAM definitions: PASS

### 1.1 `inlet_reference_pressure` against `surfaceFieldValue` areaAverage*

- Ours (`export_field.py:247-252`): `A = |Sf|`, `p_inf = sum(p[owner] A) / sum(A)`. Called at
  `:309-312` with the `inlet` patch's face range from `read_boundary`, `owner[inlet]` and the
  inlet `Sf` from `face_geometry`.
- OpenFOAM, unweighted areaAverage (`functionObjects/field/fieldValues/surfaceFieldValue/surfaceFieldValueTemplates.C:224-243`):
  no `weightField` is given, so the branch at `:237-242` runs, `factor = mag(Sf)` (`:240`),
  `result = gSum(factor*values)/gSum(factor + ROOTVSMALL)` (`:242`). The `ROOTVSMALL`* per face is
  negligible. Same formula as ours.
- Where `values` come from for `regionType patch`: `getFieldValues` (`:88-134`) finds the
  `volScalarField` p, `sampledPtr_` is null, so `filterField(fld)` (`:122`), which takes
  `field.boundaryField()[patchi][facei]` (`:561`), the patch face value.
- Owner value = face value: p on `inlet` is `zeroGradient` (`case3d.py:246`; confirmed in
  `_step1/Cube/400/p:359269-359272`, a v2512 file, which has no `value` entry, as the doc states).
  `zeroGradientFvPatchField<Type>::evaluate` (`finiteVolume/fields/fvPatchFields/basic/zeroGradient/zeroGradientFvPatchField.C:96-105`)
  calls `extrapolateInternal()` (`:103`), and `fvPatchField<Type>::extrapolateInternal`
  (`finiteVolume/fields/fvPatchFields/fvPatchField/fvPatchField.C:69-74`) is
  `patch.patchInternalField(internalField_, *this)` (`:73`), i.e. the owner-cell values. So
  `p[owner]` is exactly what `surfaceFieldValue` averages. **Yes, the owner-cell value is the inlet
  face value.**
- Face area: ours is a triangle fan about the vertex mean (`export_field.py:137-146`); for the
  planar blockMesh inlet faces this equals OpenFOAM's face area. The measured agreement (3.2 below,
  2e-10 q) confirms it.

### 1.2 `cp_from_p` against the `pressure` function object (`staticCoeff`)

File `functionObjects/field/pressure/pressure.C`:

- `staticCoeff` name `:56`; result name `static(` + p + `)` (`:79-81`) + `_coeff` (`:118-120`).
  The bit composition `STATIC_COEFF = (STATIC | COEFF)` is in `pressure.H:200` (the doc cites
  `:56` for it, see minor 1 below).
- `rhoScale(p)` (`:127-154`): p with `dimPressure` is returned as is (`:132-141`); kinematic p
  needs `rhoInf` set (fatal otherwise, `:143-151`) and returns `rhoInf*p` (`:153`).
- `calcPressure` (`:224-246`): result initialised to `pRef` (`:236`, default 0 at `:405`),
  hydrostatic part skipped when `hydrostaticMode` is NONE (`:180-183`, read only if present
  `:407-427`), `result += tp` for STATIC (`:242-245`), with `tp = rhoScale(p)` (`:323`).
- `coeff` (`:289-302`): `pCoeff -= pInf` with `dimPressure` (`:294`), divided by
  `0.5*rho*magSqr(U) + pSmall` with `pSmall = SMALL` (`:296`, `:300`). `pInf`, `UInf`, `rhoInf`
  are read at `:432-434`.

So `Cp_OF = (0 + rhoInf p - pInf) / (0.5 rhoInf |UInf|^2 + SMALL)`. With `pInf = rho p_inf_kin`
and `rhoInf = rho`, this equals `(p - p_inf)/(0.5 U^2)` in kinematic units, which is
`cp_from_p` (`export_field.py:255-257`). **pInf is in Pa** (`dimPressure`, `:294`), and
`step1_check.py:91` writes `pInf = rho * p_inf` (`repr(rho * p_inf)`), `rhoInf = rho`,
`UInf = (U 0 0)`. Correct.

On the body patch, p is `zeroGradient` (`case3d.py:247`), and `rhoInf*p` keeps the patch values
`rhoInf*p_b = rhoInf*p_P`, so comparing `cp_from_p(p[own_b])` (`step1_check.py:103`) with the
`body` patch values of `static(p)_coeff` (`:102`) compares like with like.

### 1.3 Freestream BC paragraph in the doc

`freestreamPressureFvPatchScalarField.C:119` `valueFraction = 0.5 + 0.5*(Up & nf)/mag(Up)` and
`freestreamVelocityFvPatchVectorField.C:106` `valueFraction = 0.5 - 0.5*(Up & nf)/mag(Up)`
(the doc cites `:115-119` and `:104-106`; the assignment lines are 119 and 106). With `nf` out of
the domain, pure inflow gives 0 (zero gradient p) and 1 (fixed U). The doc's conclusion holds.

### Minor (not a FAIL)

1. `step1_cp_reference.md:16` attributes `STATIC | COEFF` to `pressure.C:56`; `:56` is the name
   table, the composition is `pressure.H:200`.
2. Stale add-on line citations (pre-change numbering): `step1_cp_reference.md:12` cites
   `export_field.py:291` for the 0.75 L grid start, now `:326` (`git show 67eb372:` puts the
   grid block at 289-291); `:62` cites `export_field.py:303` for the grid p, now `:340` (IDW
   p, kinematic) and `:275` (shift and rho in `write_field_npz`). `viz3d.py:49, :61` and
   `case3d.py:246` are correct.

## 2. Units end to end: PASS

| Step | Code | Quantity | Units |
|---|---|---|---|
| Read | `export_field.py:304` `read_internal(.../p)` | p, `[0 2 -2]` (`case3d.py:245`) | m2/s2 |
| Reference | `:312` | `p_inf`, same units as p | m2/s2 |
| Grid | `:340` IDW of p, weights sum to 1 (`:338`) | kinematic p on voxels; IDW(p) - p_inf = IDW(p - p_inf) | m2/s2 |
| field.npz | `:275` `pg = rho * (p - p_inf)`; solid set 0 at `:277` | `p` in Pa relative to p_inf; `p_inf_Pa = rho p_inf` (`:279`) | Pa |
| VDB | `viz3d.py:49` `q = 0.5 rho U^2`, `:61` `cp = p / q` | Cp relative to p_inf | 1 |
| Slice | `viz3d.py:489` samples grid `cp` | as above | 1 |

- Body forces use the raw p: `export_field.py:308` passes `p` straight from `:304` to
  `body_forces`, and `:242` `f_p = p[own] * farea`. `forces_record` (`:260-268`) reproduces the
  old dictionary key for key and only appends `p_inf_Pa`, `p_inf_Cp_vs_outlet`. Measured:
  `forces_json_v041_values_identical: true` on all three cases, which is exact float equality
  `old[k] == new[k]` over every old key (`step1_check.py:120`). Cube Cd 1.2624344573924446 in both
  `_step1/Cube/forces_v041.json` and `forces.json`; Cone 0.5790654614775652; Sphere
  0.16722171382361664.
- Note on the label "v041": for Cone and Sphere the saved old file is v0.4.0 output (no
  `pressure_N`, `viscous_N`), which is why those two keys appear in `forces_json_new_keys`. The
  identity check iterates the old keys only, so it is valid; it shows v0.4.0 = v0.4.2 on those
  keys, and the step 0 review showed v0.4.1 = v0.4.0 plus two keys.

Latent coupling (non-blocking, pre-existing): `field.npz` p is scaled by the exporter's rho
(`Setup.rho`, `case3d.py:24`, passed at `:361`), but `__init__.py:727` calls
`viz3d.write_vdb(...)` without `rho`, so the VDB divides by the default 1.225 (`viz3d.py:42`).
Nothing in `__init__.py` sets `Setup.rho`, so both are 1.225 today. If rho ever becomes a panel
input, the VDB Cp would be off by `rho_case/1.225`. The comment "forces only" at `case3d.py:24`
is now wrong: rho also enters `field.npz` p. Storing `rho` (or Cp itself) in `field.npz` removes
the coupling.

## 3. Numbers trace to files: PASS

### 3.1 Re-run (Sphere, fresh copy)

`python3 step1_check.py ~/wind_tunnel/_review1/Sphere --exporter <repo>/wind_tunnel/export_field.py`,
exit 0. Every one of the 29 output values, including nested ones, equals `_step1/Sphere.json`
and `validation/step1_cp_v2512.json` `cases.Sphere` exactly (float equality, not rounding). Fresh
`log.step1Cp`: `Version: 2512`, `Operating mode: staticCoeff`, `areaAverage(inlet) of p =
0.9346655`, `plane1L 0.9409079`, `plane2L 0.9608069`.

### 3.2 Trace of the other two cases and of the prose

- `_step1/Cube.json`, `Cone.json`, `Sphere.json` against the validation JSON: 29 keys each, 0
  differences. The validation JSON adds hand-written keys `fields_from`,
  `gate_stagnation_1p00_within_2pct` (Cube) and `baseline_v0.4.0_inlet_static_Cp_vs_outlet`,
  `gate_baseline_reproduced_to_3_decimals` (Cone, Sphere); each traces:
  - `fields_from`: `Cube/log.simpleFoam` `Build : ... OPENFOAM=2512`, `Cone` and `Sphere`
    `Build : OPENFOAM=1912 patch=200626`; 400 `Time =` lines in each.
  - Baseline: `validation/baseline_v0.4.0.json:22` 0.011 (cone), `:31` 0.005 (sphere); ours
    0.01120, 0.00467.
  - Stagnation gate false: 1.0232 is outside 0.98 to 1.02.
- `Cube/log.step1Cp`: `areaAverage(inlet) of p = 8.380877`, `plane1L 8.241773`, so plane 1 L Cp
  = (8.241773 - 8.380877)/200 = -0.000696, matching -0.0007.
- SESSION_LOG.md table (`:142-144`) and the 0281002 commit message: every value (shifts -4.19,
  -1.12, -0.47 % of q; inlet spreads; plane values; 3.9e-7, 2.7e-8, 3.3e-7; stagnation 1.0232
  (1.0651), 0.6197 (0.6309), 0.9817 (0.9864); 359,240 / 355,327 / 339,042 cells; "2e-10 q",
  "4e-7") is a rounding of a JSON value above.
- Blender probe, re-run headless on a copy of `_step1/Cube/field.npz`: `upstream_face_off_axis`
  (-2.5, -1.25, -1.25) `vdb_cp 0.14809949696063995`, `ahead_of_front_face_centre` (-1.05, 0, 0)
  `vdb_cp 1.022086501121521`, `vdb_vs_npz_max_abs 0.0`. Identical to the validation JSON.
- Slice edge (SESSION_LOG:149-150), from `field.npz` directly: Cp 0.4461 at (-2.5, 0, 0) and
  0.0463 at (-2.5, 0, 2.5). Traces.
- Not traceable to a file: the live-QA "Cd property 1.262434" (SESSION_LOG:128) was read in a
  Blender scene that was deleted afterwards. It agrees with `forces.json` Cd to 6 digits.

### 3.3 Wording

- Nothing is called validated: `git diff 67eb372..HEAD | grep -i "validated\|in range"` finds
  only the rule text inside the two prompts. The validation JSON `reference` names the OpenFOAM
  function objects for gates (1) and (3) and calls Bernoulli stagnation "a physical target; a
  miss is recorded, not tuned".
- The cube miss is stated as a miss in all three places: commit 0281002 ("misses the Bernoulli
  target 1.00 +/- 2 % by 0.3 %; recorded, not tuned"), SESSION_LOG:142 ("FAIL by 0.3 %"), and
  `gate_stagnation_1p00_within_2pct: false`.
- **Error:** SESSION_LOG:148 and `step1_cp_reference.md:12` (Q3 item 5) say the probe point is
  "half a voxel ahead of the front-face centre". The probe node is i = 29 at x = -1.05 with
  h = 0.05 m and the face at x = -1.0 (`blender_cp_probe.py:34-36`), so it is one voxel (0.05 m,
  0.025 L) ahead. The value is right; the description is not.
- Precision note: "p_inf matches `surfaceFieldValue` to 2e-10 q" is agreement to the 8
  significant digits that `surfaceFieldValue.dat` writes (8.3808771); the true agreement may be
  better. Not wrong, just bounded by output precision. Same for 3.9e-7 on the body (Cp written to
  7 digits).

### 3.4 The cube stagnation miss: reviewer attribution (measured, from stored fields)

SESSION_LOG:153-155 lists the cause as "not determined; candidates are the unconverged solve
(step 2) and the total-pressure excess in ACCURACY_AUDIT #3". The stored fields point to a more
specific cause. Total pressure `p0 = p + |U|^2/2`* on the cell nearest the x axis, with p_inf the
inlet area mean, from `_step1/Cube` (t = 400, v2512) and the Sphere copy:

| x (m) | Cube Cp | Cube (p0 - p_inf)/q | Sphere Cp | Sphere (p0 - p_inf)/q |
|---|---|---|---|---|
| -7.0 (inlet centre face) | +0.0311 | 1.0311 (U fixed at 20 m/s) | +0.0076 | 1.0076 |
| -6.84 | 0.0311 | 1.0309 | 0.0077 | 1.0076 |
| -4.20 | 0.0983 | 1.0297 | 0.0260 | 1.0072 |
| -2.31 | 0.4463 | 1.0239 | 0.1560 | 1.0051 |
| -1.52 | 0.8605 | 1.0252 | 0.4890 | 1.0035 |
| -1.19 / -1.18 | 1.0018 | 1.0255 | 0.8303 | 1.0012 |
| -1.02 / -1.01 (wall cell) | 1.0232 | 1.0241 | 0.9817 | 0.9943 |

Reading (reasoning on the measured numbers, not a validated result):

- The inlet fixes U uniform (`case3d.py:243`) while p is zero gradient and raised near the axis by
  the body's upstream influence (inlet 3 L ahead of the cube front face). So the stagnation
  streamline enters with total pressure 1.031 q above p_inf (mean) on the cube, not 1.000 q.
- Along the axis p0 only falls (1.031 to 1.024 at the wall cell, a 0.0013 q wiggle at x -1.5 to
  -1.2): no total pressure is created on the stagnation line, so ACCURACY_AUDIT #3's excess
  (shoulders and refinement interfaces) is not what lifts the stagnation Cp.
- Stagnation Cp 1.0232 = inlet centre excess (+0.031) minus about 0.008 q loss on the way.
  Relative to the local inlet total pressure on that streamline it would be about 0.992. The
  sphere is consistent: +0.0076 at the inlet centre, 0.9817 on the face nearest the nose
  (that face sits about 0.058 rad off the axis, which by potential flow* alone lowers Cp by about
  0.0075; textbook formula from memory, not checked here).
- So the 2 % gate is missed because p_inf is the inlet *mean* while the 1.00 target assumes a
  uniform upstream static pressure. This is open issue (c) (inlet non-uniformity, step 4 domain).
  Convergence (step 2) is not excluded, but it is not needed to account for the magnitude.
  Implication for grill Q2/Q3: on the present domain, the choice of p_inf inside the inlet patch
  moves stagnation Cp by up to the inlet spread (0.050 q on the cube).

## 4. Tests assert behaviour: PASS

`py -m unittest discover -s tests -v`: `Ran 26 tests ... OK (expected failures=3)`, so 23 pass
and 3 expected failures (`test_blockage_target`, `test_inlet_far_enough_upstream`,
`test_layers_target`), as stated.

The 4 new tests (`tests/test_pure.py:189-245`, class `CpReference`) check behaviour:

- `test_inlet_mean_is_area_weighted` (`:201-205`): areas 1 and 3 with values 0 and 4 give 3.0,
  where the unweighted mean would be 2; cell 2 (value 99) is not on the patch and must not
  enter. Tests both area weighting (from `|Sf|`) and owner indexing.
- `test_cp_zero_at_inlet_one_at_stagnation` (`:207-212`): Cp 0 at p_inf and 1 at p_inf + U^2/2,
  on an offset field, so the subtraction of p_inf is exercised.
- `test_field_npz_pressure_shifted_by_p_inf` (`:214-231`): writes `field.npz` with
  `write_field_npz` and checks the stored p is `rho (p - p_inf)` (Cp 1 at stagnation, 0 in the
  freestream), solid voxels 0, and `p_inf_Pa = rho p_inf`.
- `test_forces_json_keeps_v041_keys_and_adds_p_inf` (`:232-244`): exact key set (v0.4.1 keys plus
  the two new), drag, pressure and friction drag, Cd, Cl, both new values, and JSON
  serialisability.

Notes (non-blocking):

1. The npz test re-implements `viz3d.write_vdb`'s formula (`:226`) instead of calling it (it
   needs openvdb). If viz3d changes, this test will not see it; the headless probe does.
2. `main()`'s wiring (that the `inlet` patch and raw p reach the helpers, and that `body_forces`
   gets the unshifted p) is covered by the tracer (exact force equality on three cases), not by a
   unit test. "Shown failing first" (SESSION_LOG:123) cannot be checked from git, since tests and
   code are in one commit.

## 5. Pure modules do not import bpy: PASS

`grep -nE "import bpy|from bpy"` over `case.py, case3d.py, meshgen.py, results.py, flowfield.py,
wsl.py, export_field.py`: no hits (exit 1). `export_field.py` imports are stdlib, numpy and
`scipy.spatial.cKDTree` (`:15-22`); the diff adds no import to any pure module.

## 6. No em dashes: PASS

`git diff 67eb372..HEAD | grep -c $'\xe2\x80\x94'` gives 0; en dash (`\xe2\x80\x93`) 0; commit
messages of `67eb372..HEAD` 0.

## 7. LF line endings: PASS

`git ls-files --eol` on all 9 changed files (SESSION_LOG.md, step1_cp_reference.md,
test_pure.py, step1_check.py, blender_cp_probe.py, step1_cp_v2512.json, `__init__.py`,
blender_manifest.toml, export_field.py): every one `i/lf w/lf attr/text=auto eol=lf`.

## 8. Version 0.4.2: PASS

`wind_tunnel/blender_manifest.toml:4` `version = "0.4.2"`; `wind_tunnel/__init__.py:9`
`"version": (0, 4, 2)`.

## Required fixes

1. SESSION_LOG.md:148 and `step1_cp_reference.md:12`: "half a voxel ahead" becomes "one voxel
   (0.05 m) ahead" of the front-face centre.
2. `step1_cp_reference.md:12`: `export_field.py:291` becomes `:326`; `:62`: `export_field.py:303`
   becomes `:340` (IDW) and `:275` (shift in `write_field_npz`).
3. `step1_cp_reference.md:16`: cite `pressure.H:200` for `STATIC_COEFF = (STATIC | COEFF)`;
   `:56` is the name table.
4. SESSION_LOG.md open issue on the cube stagnation Cp (`:153-155`): replace "cause not
   determined" with the measured attribution of 3.4 (inlet centre-line total pressure 1.031 q
   above the inlet mean because U is fixed uniform while p is raised near the axis; p0 only
   decreases along the stagnation line; consistent with open issue (c), step 4), and state that
   this is reasoning on stored fields, not a validated result.

## Recommended (non-blocking)

- Store `rho` (or Cp) in `field.npz` and pass it to `viz3d.write_vdb` from `__init__.py:727`; fix
  the "forces only" comment at `case3d.py:24`.
- `tools/audit/step1_check.py:42-46` hard-codes `--speed 20 --rho 1.225 --nu 1.5e-5 --L 2.0`
  defaults; the step 0 review had `step0_check.py` read `nu` from the case. Read them from the
  case's `forces_v041.json` / `transportProperties` instead. Harmless here: exact force equality
  on all three cases shows the values matched.
- In `validation/step1_cp_v2512.json`, per-case `"openfoam": "v2512"` is the post-processing
  build, while `fields_from` says v1912 for Cone and Sphere. Rename the key (for example
  `postprocess_openfoam`) so the two cannot be confused.
- Rename `forces_v041.json` to `forces_before_step1.json` in `step1_check.py:58`, since for Cone
  and Sphere it is v0.4.0 output.
- When step 4 moves the inlet, re-run the 3.4 table: on a domain where inlet Cp spread is below
  0.002, cube stagnation Cp against the inlet mean should fall within the 2 % gate if this
  attribution is right. That is the test of the attribution.
- `~/wind_tunnel/_review1` (118 MB, this review's Sphere copy) can be deleted.
- This report is saved, not committed; step 0's review was committed on its own.

## Glossary

- `areaAverage`*: `surfaceFieldValue` operation `sum(|Sf| phi_f) / sum(|Sf|)` over the faces of a
  patch or sampled surface.
- `p0 = p + |U|^2/2`*: kinematic total pressure; constant along a streamline in steady, inviscid,
  incompressible flow (Bernoulli), and it can only fall where there are losses.
- `potential flow`*: inviscid, irrotational flow; for a sphere the surface Cp is
  `1 - (9/4) sin^2(theta)`, theta measured from the stagnation point.
- `ROOTVSMALL`*: OpenFOAM constant, the square root of the smallest double it uses (about
  1e-150), added to avoid division by zero.
- `rhoInf`*: reference density the `pressure` function object uses to convert kinematic p to Pa.
- `staticCoeff`*: `pressure` function object mode that writes `(pRef + rho p - pInf)/(0.5 rho
  |UInf|^2)`.
- `surfaceFieldValue`*: OpenFOAM function object that reduces a field over a patch, face zone or
  sampled surface (sum, average, area average, and so on).
- `zeroGradient`*: boundary condition with zero normal gradient; the face value equals the
  owner-cell value.

Step 1 review: 8 PASS, 0 FAIL, 4 required fixes (wording and citations), 1 attribution to record
