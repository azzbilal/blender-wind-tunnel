# TRANSIENT T1 review: time-resolved flow around the cube, including the 0.6.1 polish

Date: 2026-10-24. Reviewer: Claude (fresh session), from the REVIEWER PROMPT in SESSION_LOG.md
(entry "2026-10-24: T1 polish, smoke streaks visible, add-on 0.6.1").
Commits reviewed: b2eea87..aa121a3 (Stage 3 red to Stage 5 close), 73258ac and c929b10 (handoffs),
7cf7d8f (close-out), ed49139 (0.6.1 polish).
Read: CLAUDE.md, SESSION_LOG.md (current entry), docs/reference/transient_t1_spec.md,
docs/prompts/transient_t1.md; code checked: `wind_tunnel/case3d.py` (Transient, transient_control_dict,
transient_fv_schemes, transient_fv_solution, write_transient_case), `wind_tunnel/transient.py`
(window_mean, strouhal), `wind_tunnel/export_field.py` (cell_centres, idw_weights, idw_apply,
gather_cells, _export_frame, export_frames, voxel_grid, inlet_reference_pressure),
`tools/audit/t1_gates.py`, `tools/audit/t1_visibility.py`, `tools/audit/t1_scene.py` (cleanup),
`tools/audit/anim_inside.py` (header), README "Time-resolved flow",
`validation/transient_t1_v2512.json`. Read-only except this file.

Independent re-runs (reviewer scripts and scratch output in the job folder
`C:\Users\bgare\.claude\jobs\b1d12b8c\tmp\`, removed with the job; method stated per item so each
can be redone):
- `rev_gates.py` (WSL python3, imports neither `transient.py` nor `t1_gates.py`): raw parse of
  `log.pimpleFoam` and `coefficient.dat`, own trapezoid*, own zero-crossing count and 0.1 s bins.
- `rev_frame.py`, `rev_frame2.py`, `rev_frame3.py` (WSL): frame 60 against `reconstructPar -time 1`
  on a copy (`~/wind_tunnel/_review_t1`, 245 MB, safe to delete).
- Headless Blender 5.2 (factory startup, repo code): `anim_inside.py`, `t1_visibility.py` (shipped and
  red), `t1_autosolve_check.py`, `t1_frames_check.py`, `tools/blender_smoke.py`; `py -m unittest`.

**Result: 10 PASS, 1 FAIL (item 10, a one-phrase README fix).** Observations O1 to O4 need no fix
before FIX_PLAN step 3.

| # | Item | Result |
|---|---|---|
| 1 | case text matches spec Q3; only backward and no `bounded` differ from steady | PASS |
| 2 | gate 3 continuity re-parsed: 120 frames, max 1.95e-12 | PASS |
| 3 | gate 1 Cd 1 to 2 s mean by own trapezoid: 1.1243 | PASS |
| 4 | gate 2 "no sustained shedding" right; tail rule stated in the spec | PASS |
| 5 | frame export vs IDW* from reconstructPar, 1e-6 relative | PASS (O1) |
| 6 | gate 4 re-run: 0 inside, 196334 particle-frames | PASS |
| 7 | visibility re-run, check judged, red reproduced | PASS (O2) |
| 8 | Auto solve guard check passes; cleanup order | PASS |
| 9 | t1_frames_check, blender_smoke, tests 103 OK (3 expected failures) | PASS |
| 10 | README claims nothing beyond the record; states display limit k | **FAIL** |
| 11 | Bilal's live Blender has only his data | PASS (Bilal) |

## 1. Case text vs spec Q3: PASS

- `diff ~/wind_tunnel/_anim/Cube/system/fvSchemes ~/wind_tunnel/_t1/Cube/system/fvSchemes` shows
  exactly two hunks: `ddtSchemes { default steadyState; }` to `{ default backward; }`, and
  `div(phi,U)`, `div(phi,k)`, `div(phi,omega)` lose the `bounded` prefix (`Gauss linearUpwindV grad(U)`,
  `Gauss upwind`, `Gauss upwind`). Gradient, laplacian, interpolation and snGrad lines are identical.
  The writer produces this by construction: `transient_fv_schemes()` is `FV_SCHEMES` with those two
  replacements only (`wind_tunnel/case3d.py:492`).
- `_t1/Cube/system/controlDict`: `application pimpleFoam`, `endTime 2`, `deltaT 0.001`,
  `adjustTimeStep yes`, `maxCo 1`, `maxDeltaT 1`, `writeControl adjustableRunTime`, `writeInterval 0.5`
  (restart points), `writeObjects` of `(U p)` with `writeControl adjustableRunTime`,
  `writeInterval 0.01666666666667` (1/60 s), `forceCoeffs` on `body` every step with `magUInf 20`,
  `lRef 2`, `Aref 4`, `dragDir (1 0 0)`, `liftDir (0 0 1)`, rhoInf 1.225. All as Q3.
- `fvSolution`: p GAMG tol 1e-7 relTol 0.01, pFinal relTol 0; `(U|k|omega)` smoothSolver tol 1e-8
  relTol 0.1, Final relTol 0; PIMPLE `nOuterCorrectors 1`, `nCorrectors 2`,
  `nNonOrthogonalCorrectors 1`, `momentumPredictor yes`; relaxation factors 1 (no relaxation);
  `potentialFlow { nNonOrthogonalCorrectors 5; }`. All as Q3. The log confirms the `Final` solver
  entry resolved (`smoothSolver` on Ux, Uy, Uz, k, omega every step; 2 pressure correctors per step).
- `transportProperties` nu 1.5e-05, `RASModel kOmegaSST` in both cases.
- `writeFormat ascii` differs from Q3 "binary": recorded as a deliberate deviation in the spec's
  Stage 3 note (reuses the tested ASCII readers; physics unchanged). Not a scheme difference.

## 2. Gate 3 continuity, independent parse: PASS

`rev_gates.py` splits `log.pimpleFoam` at each `Time = ` line and keeps every
`time step continuity errors : sum local = ...` value of that step; a step is frame k when
|60 t - k| < 1e-4.

| Quantity | Re-parse | Record (`gate3_continuity`) |
|---|---|---|
| time steps | 2564 | 2564 |
| frames found / missing | 120 / none | 120 / [] |
| correctors per step | 2 (every step) | |
| max at frames, final corrector | 1.9486173e-12, frame 45 (t = 0.75) | 1.9486173e-12, frame 45 |
| max at any step, final corrector | 2.7758013e-12 | 2.7758013e-12 |
| max at frames, either corrector | 5.32e-10 (frame 1, first corrector) | not recorded |

All far below the 1e-6 limit. The gate's definition (final corrector) is the one stated in the
`t1_gates.py` docstring; even the first-corrector values pass by four orders of magnitude.
Frame times land exactly on k/60 (0.016666667, 0.75, 1, 2 for k = 1, 45, 60, 120), confirming the
established adjustableRunTime behaviour on this run.

## 3. Gate 1 Cd, own trapezoid: PASS

`rev_gates.py` reads `postProcessing/forceCoeffs/0/coefficient.dat` with columns by header name
(2564 rows, times strictly increasing, last t = 2.0), interpolates Cd linearly at the window ends and
sums trapezoids over the variable steps:

| Quantity | Re-computed | Record |
|---|---|---|
| Cd mean, t = 1.0 to 2.0 s | 1.1242609452056656 | 1.1242609452056653 |
| Cd mean, t = 0.5 to 1.0 s | 0.920831917972981 | 0.920831917972981 |
| Cd at t = 2 s | 1.12720727 | 1.127 (SESSION_LOG) |

Ratio to the steady gated 1.1498 on the same mesh: 0.978 (-2.2 %). As the spec says, this compares
two models on one mesh, with no experimental target.

## 4. Gate 2, "no sustained shedding": PASS

Cs and Cl per 0.1 s bin (min, max, range), own code on the raw coefficient file:

| Bin start (s) | Cs min | Cs max | Cs range | Cl min | Cl max | Cl range |
|---|---|---|---|---|---|---|
| 0.5 | 0.0030 | 0.0206 | 0.0175 | 0.0080 | 0.0283 | 0.0203 |
| 0.6 | -0.0148 | 0.0030 | 0.0178 | -0.0247 | 0.0075 | 0.0322 |
| 0.7 | -0.0084 | 0.0017 | 0.0101 | -0.0085 | 0.0149 | 0.0234 |
| 0.8 | 0.0000 | 0.0125 | 0.0124 | 0.0150 | 0.0420 | 0.0271 |
| 0.9 | -0.0187 | 0.0146 | 0.0333 | -0.0216 | 0.0460 | 0.0676 |
| 1.0 | -0.0194 | 0.0027 | 0.0221 | -0.0311 | -0.0162 | 0.0149 |
| 1.1 | 0.0020 | 0.0177 | 0.0157 | -0.0158 | 0.0068 | 0.0226 |
| 1.2 | -0.0166 | 0.0213 | 0.0379 | -0.0264 | 0.0377 | 0.0641 |
| 1.3 | 0.0224 | 0.0438 | 0.0214 | 0.0388 | 0.0731 | 0.0343 |
| 1.4 | -0.0131 | 0.0269 | 0.0400 | -0.0257 | 0.0415 | 0.0672 |
| 1.5 | -0.0172 | -0.0058 | 0.0115 | -0.0346 | -0.0229 | 0.0117 |
| 1.6 | -0.0056 | 0.0079 | 0.0135 | -0.0226 | -0.0039 | 0.0187 |
| 1.7 | -0.0026 | 0.0074 | 0.0100 | -0.0077 | -0.0040 | 0.0037 |
| 1.8 | -0.0031 | -0.0003 | 0.0028 | -0.0077 | -0.0016 | 0.0061 |
| 1.9 | -0.0010 | 0.0006 | 0.0016 | -0.0015 | 0.0038 | 0.0053 |

- Zero crossings of (signal minus window mean) over 1 to 2 s: Cs 6 at t = 1.099, 1.199, 1.280,
  1.452, 1.635, 1.744 s (2.5 periods, as recorded); Cl 5 at 1.128, 1.191, 1.273, 1.452, 1.895 s
  (2.0 periods). Half-period spacings are 0.099, 0.081, 0.172, 0.183, 0.109 s for Cs: no single
  period, and no crossing of Cs after 1.744 s.
- Amplitude: up to 0.044 (Cs) and 0.073 (Cl) at 1.3 s; after 1.7 s every |Cs|, |Cl| is below 0.008
  (largest 0.0077), as the spec and README say. Standard deviation over 1.75 to 2.0 s divided by that
  over 1.0 to 2.0 s: Cs 0.087, Cl 0.171 (record 0.08716, 0.17064; spec "9 % Cs, 17 % Cl").
- Judgement: what the window holds is a decaying start-up transient with irregular spacing, not a
  periodic signal; "no sustained shedding" is the right reading of these 2 s. A crossing count alone
  would have reported St 0.26 to 0.39, so the extra rule is needed. See O3 for the limits of the claim.
- The rule is stated in the spec, Stage 4 note "Full run results": "`t1_gates.py` now also requires
  the last 0.25 s spread to be at least 25 % of the window spread (measured 9 % Cs, 17 % Cl)", and the
  code does exactly that (`tools/audit/t1_gates.py:58` to `:66`: `sd_tail < 0.25 * sd` over
  1.75 to 2.0 s vs 1.0 to 2.0 s). The spec's "spread" is the sample standard deviation over time
  steps (not time-weighted); see O3.

## 5. Frame export vs IDW from reconstructPar: PASS (with O1)

Copy `~/wind_tunnel/_review_t1`: `system`, `constant` and `processor*/{constant,1}` of `_t1/Cube`,
then `reconstructPar -time 1 -fields '(U p)'` (frame 60, t = 1 s) and
`postProcess -func writeCellCentres -time 1`. p_inf from OpenFOAM itself,
`postProcess -func 'patchAverage(name=inlet,p)' -time 1`: areaAverage(inlet) of p = 5.8736711 m2/s2,
i.e. 7.195247 Pa; `flow_0060.npz` stores `p_inf_Pa` 7.195247 (relative difference 2.9e-9).
`renders/t1_frames/flow_0060.npz` and `_t1/Cube/frames/flow_0060.npz` have the same sha1 (bbebbc9c).

Three comparisons, U and p = rho (p_kin - p_inf) against the npz:

| IDW built from | Voxels | U max relative error | p max error / q | Within 1e-6 |
|---|---|---|---|---|
| (a) OpenFOAM `C` (volume centroid), own KD tree, 4 nearest, 1/d^2 | 60 (40 random, 20 next to the body) | 1.2e-2 | 1.2e-2 | 22 of 60 (O1) |
| (b) exporter's centre formula on the reconstructed mesh, own query (k = 5) | same 60 | 6.1e-8 (40 random); 3.4e-3 at 1 voxel | 1.0e-3 | 59 of 60 |
| (c) exporter's centre formula and query over the full grid (`idw_weights`, float32), reconstructPar values | all 1675450 fluid voxels | 5.9e-8 | 6.2e-8 | all |

- (c) is the check the item asks for: interpolation identical in definition, but the cell values
  come from `reconstructPar` (OpenFOAM's own reassembly) and p_inf from OpenFOAM's `patchAverage`,
  not from the exporter's processor gather. Every fluid voxel agrees to float32 rounding, so the
  processor gather through `cellProcAddressing`, the time-directory matching and the per-frame p_inf
  are exact. Solid voxels hold U = 0 and p = 0, as `write_field_npz` states.
- The single outlier in (b) is an exact distance tie: the 5th-nearest centre is as close as the 4th
  (d5 - d4 = 0), so a k = 5 query may keep a different 4 than the exporter's k = 4 query. It
  disappears in (c).
- (a) differs because the two centre definitions differ, not because of the frame export (O1).

## 6. Gate 4 re-run: PASS

`anim_inside.py -- renders/t1_frames 120` (12 fps, headless, 27 s): `particle_frames` 196334,
`inside_body_box_abs_lt_1m` 0, `particles_alive_max` 2064, `min_gap_euclidean_m` 0.0011540,
`min_gap_chebyshev_m` 0.0009911, `use_field_nots` 1. Identical to the record and SESSION_LOG
(196334, 0 inside, closest 1.15 mm, Chebyshev* 0.99 mm).

## 7. Visibility: PASS (with O2)

Re-run, shipped inputs (`t1_visibility.py -- renders/t1_frames <scratch>`, exit 0, 87 s):

| Frame | over (px) | wake (px) | no-smoke baseline | Record `green_0_6_1` |
|---|---|---|---|---|
| 30 | 17033 | 5973 | 0 / 0 | 17033 / 5973 |
| 60 | 17479 | 3670 | 0 / 0 | 17479 / 3670 |
| 120 | 13376 | 5452 | 0 / 0 | 13376 / 5452 |

Inputs read back from the modifier: Radius 0.0125 (L/160), Trail 0.03, Rate 107.14, Sheet 0.1,
Lifetime 39, Substeps 10; 8.438 mm per px at y = 0 (15 m, 50 mm lens, 36 mm sensor, 1280 px). The
counts are deterministic: bit-equal to the record.

Judging the check itself:
- `vis_0060.png` (t = 1.000 s, t U/L = 10.00) shows charcoal streaks on the Cp slice following the
  stagnation region and both shear layers above and below the cube, with sparse streaks in the near
  wake; the label, legend and grey cube face are where the docstring puts them.
- Regions in the code (`t1_visibility.py:80` to `:87`) are as the docstring and the record's
  `regions` string say: inside the slice rectangle shrunk by 4 px, outside the projected box of all 8
  cube corners grown by 4 px; over = x in [-1, 1] m with |z| from 1.1 m to the grid edge, wake = x from
  1.15 m to the grid end with |z| <= 1 m. Mask sizes 75840 and 135327 px.
- Classifier as documented: sRGB* max <= 80 and max - min <= 16 on the 8-bit PNG.
- No-smoke baseline 0 in every region and frame (re-run). This matters because the world background
  (sRGB 39, 39, 44) would pass the classifier; the regions stay inside the slice, and the baseline
  proves it.
- Red runs recorded: `visibility_0_6_1.red_0_6_0_as_shipped` (no play-through, 0 px everywhere,
  FAIL) and `red_0_6_0_streaks_with_play_through` (0/2, 3/0, 0/0, FAIL), plus the two trials.
- Red reproduced: OVERRIDES `{"Radius": 0.00333, "Trail": 0.01, "Rate": 71.43}` gives exit 1 and
  over/wake 0/2, 3/0, 0/0 at frames 30, 60, 120 (six threshold misses), baseline 0. Exactly the
  recorded `red_0_6_0_streaks_with_play_through`.

## 8. Auto solve guard: PASS

- `t1_autosolve_check.py` headless, exit 0: `AUTOCHK {"during": {"Other": false, "Scene": false,
  "WT_T1": false}, "saved": {"Other": false, "Scene": true, "WT_T1": true}, "after": {"Other": false,
  "Scene": true}, "ok": true}`. Every scene is off while WT_T1 exists, and each gets its own value back.
- `t1_scene.cleanup()` (`tools/audit/t1_scene.py:164` to `:191`) runs in the required order:
  WT data first (`viz3d.remove_all()`, objects T1Cube, T1Cam, T1Sun, the WT_T1 scene, their meshes,
  camera, light, materials and world, then orphan `WT ` meshes, node groups, volumes, materials), then
  `auto_solve_restore()` (line 190), then `restore_handler()` (line 191). The docstring says the same.
  Restoring Auto solve only after WT Smoke is gone closes the path that launched `3d_T1Cube`.

## 9. Headless checks and tests: PASS

- `t1_frames_check.py`: exit 0, `fails: []`; WT Slice cp = 0.1 k at scene frame k for k = 1..4 and
  0 kept vertices at frame 5 (CLIP*), time labels match at frames 1, 7, 30, 59, 120, streak length
  0.06 m in the synthetic setup.
- `tools/blender_smoke.py`: exit 0, `ok: true`, `version [0, 6, 1]`, no invalid links,
  `kept` 39464 = `kept_pure` 39464, `cp_err_max` 6.0e-8.
- `py -m unittest discover -s tests`: `Ran 103 tests`, `OK (expected failures=3)`.

## 10. README "Time-resolved flow": FAIL

What is right: no "validated" claim ("This compares two models, it is not a validation"); no St
("No Strouhal number is reported", Klotz 2014 given with its Re <= 390); every number matches the record
(Cd 1.124 vs 1.150, -2.2 %; Cp -4.24 at t = 1/60 s to -0.73 / +1.03 vs steady -0.68 / +1.02;
continuity 1.95e-12; 196334 particle-frames; |Cs|, |Cl| < 0.008 after 1.7 s; Re 2.7e6). URANS and
coarse-mesh limits are stated plainly, and so is the play-before-render rule.

The FAIL: the display limit (issue k) is stated with a size the record does not support and that is
too small. README: "a streak (radius L/160) drawn next to the top face can cut a few mm into the
cube". In the smoke tree `Radius` is the geometric radius of the streak's sphere and cylinder
(`viz3d.py:548`, `:554`), 12.5 mm, and the closest particle centre is 1.15 mm from the face (item 6),
so the drawn streak can reach 12.5 - 1.15 = about 11 mm into the cube, roughly four times "a few mm".
The record (`gate4_particles.note`) and SESSION_LOG issue k say only that it "cuts into the cube
surface geometrically", with no depth. Required fix (one phrase): replace "can cut a few mm into the
cube" with "can reach up to about 11 mm (radius 12.5 mm minus the 1.15 mm closest centre gap) into the
cube", or with no number at all.

## 11. Bilal's live Blender: PASS

Asked Bilal through the session (his scenes not opened): "Yes, only my data" (no WT_T1, no T1Cube,
T1Cam, T1Sun, no stray WT objects; Auto solve and the Test Object handler as he had them).

## Observations (no fix required before step 3)

- O1. Cell centres used by every IDW export (steady `field.npz` and T1 frames) are the mean of the
  face centres (`export_field.cell_centres`, `export_field.py:155`), not the volume centroid that
  OpenFOAM writes as `C`. On this mesh the two agree to 1e-7 m in the median cell, but differ by up to
  0.035 m at the 99th percentile and 0.070 m at most (1.4 voxels), in cells with uneven face counts
  such as coarse cells on a snappyHexMesh refinement interface. An IDW on OpenFOAM's `C` differs from
  the shipped frame by up to 1.2 % in |U| and 0.012 q in p at the voxels sampled (item 5 a). This was
  inherited from the steady export (T1 kept "the same IDW"), so it is not a T1 defect, but it is a
  physical-accuracy item for the display: suggest a later slice switch to `writeCellCentres` (or a
  volume-weighted centroid) and record the change in `field.npz`. Also, nodes of the uniform far-field
  grid often sit at exact distance ties between more than 4 centres, so which 4 are used depends on
  KD-tree tie order; harmless for display, worth knowing for any bit-level regression test.
- O2. The red record `red_0_6_0_streaks_with_play_through` stores the pixel counts but not the inputs
  that produced them; the reviewer prompt supplied them. Suggest adding the OVERRIDES dict to that
  entry, as `green_0_6_1` already lists its inputs.
- O3. Gate 2 limits of the claim: "no sustained shedding" is shown for t <= 2 s only; the spec's
  "tends to the steady state" extrapolates beyond the run (as the spec and README already say, untested
  on a finer mesh or with DES). The tail rule's "spread" is the unweighted sample standard deviation
  over time steps; with dt between 6.3e-4 and 8.3e-4 s this is close to a time-weighted value, but the
  spec could name the statistic.
- O4. Review O2 of ANIMATION A+B (Moreland intermediates) is still open, as SESSION_LOG lists.

Housekeeping: with item 10 fixed (README only, no code or physics), `~/wind_tunnel/_t1/Cube` (5.4 GB)
and `~/wind_tunnel/_anim` no longer need to stay for this review. The reviewer copy
`~/wind_tunnel/_review_t1` (245 MB) is still on disk and can be deleted any time.

## Glossary

- *trapezoid (rule)*: time integral approximated as the sum of (y_i + y_i+1) / 2 (t_i+1 - t_i); used
  because the adjustable time step makes samples non-uniform.
- *IDW (inverse distance weighting)*: value at a voxel node as the weighted mean of the 4 nearest cell
  values, weights 1/d^2 normalised to sum 1.
- *Chebyshev gap*: max over axes of (|x_i| - 1) for the 2 m box; for a point outside an axis-aligned box
  it is at most the Euclidean distance to the box.
- *sRGB*: display-encoded colour (0 to 255 here) after the Standard view transform, as stored in the PNG.
- *CLIP*: Blender volume-sequence mode that shows nothing outside the sequence's frame range.
- *URANS*: unsteady Reynolds-averaged Navier-Stokes; turbulence is modelled by k-omega SST and only
  unsteadiness much slower than the turbulence is resolved.
- *Strouhal number (St)*: f L / U, the non-dimensional shedding frequency.
- *continuity error (sum local)*: OpenFOAM's time-step measure of mass imbalance, dt times the
  volume-weighted mean of |div(phi)| after the pressure corrector.

## Closure

2026-10-24: item 10 fixed in commit 48216f2 (README: up to about 11 mm, radius 12.5 mm minus the 1.15 mm
closest centre gap; `gate4_particles.streak_overlap_max_m` 0.01135 in the validation record). No open
FAIL. O1 moved to FIX_PLAN step 6; O2 and O3 open in SESSION_LOG.md.
