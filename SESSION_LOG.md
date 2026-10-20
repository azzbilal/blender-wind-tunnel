# Session log

## 2026-10-19: FIX_PLAN step 0 (working OpenFOAM build), commit 23f65e5, version 0.4.1

### Done
- Build: OpenFOAM v2512 (`openfoam2512-default` 2512.0-2, build bd2b6720-20260127). 2606.0~rc2 was
  installed first and then removed. Installing the openfoam.com `openfoam` package had already
  replaced Ubuntu's v1912 solver. Its orphaned `libopenfoam` and `openfoam-examples` 1912 are
  still installed.
- `wsl.pick_bashrc`: pure function that chooses the newest openfoam.com bashrc by version number,
  with Ubuntu's `/usr/share/openfoam` only as a fallback. The old probe sorted the two paths as
  text and reported v1912.
- `case3d`: `method scotch;` plus a `hierarchicalCoeffs` block. Allrun switches to hierarchical
  with `foamDictionary` when `$FOAM_LIBBIN/libscotchDecomp.so` is missing.
- `export_field.body_forces` extracted with no numerical change. `forces.json` gains the
  `pressure_N` and `viscous_N` vectors.
- `tools/audit/step0_check.py`, `docs/reference/step0_openfoam_build.md`, `validation/step0_v2512.json`.
- Fallback exercised live: with `FOAM_LIBBIN` pointed at a missing folder, the Allrun line set
  `hierarchical` and v2512 `decomposePar` reported `Decomposition method hierarchical [24]`, exit 0.
- Tests: 7 new, each shown failing before the fix. Suite: 21 run, 18 pass, 3 expected failures.
  Deploy done, and the Blender smoke check reports ok.

### Decisions locked by the grill
| # | Answer |
|---|---|
| Q0 | Use 2512 final as the reference build, not 2606 rc2 |
| Q1 | scotch, with a run-time fallback to hierarchical |
| Q2 | Cube, Cone, Sphere at t = 400. Gates: total within 0.5 % of Fx per component; pressure Fx within 0.1 % of Fx; viscous part reported, not gated |
| Q3 | Purge `libopenfoam openfoam-examples` (1912) once this slice passes |

### Numbers (OpenFOAM v2512 `forces` vs `export_field.body_forces`, same fields)
| Case | Cells | OpenFOAM Fx (N) | dFx total | dFp_x | viscous Fx gap (of itself) | Cd forceCoeffs / ours | y+ min / area mean / max | area 30 < y+ < 300 |
|---|---|---|---|---|---|---|---|---|
| Cube (v1912 field) | 358,176 | 1225.917 | -0.002 % | 6e-7 % | 1.3 % | 1.2509 / 1.2509 | 9.2 / 263 / 616 | 59 % |
| Cone (v1912 field) | 355,327 | 444.438 | +0.007 % | 4e-7 % | 0.6 % | 0.5790 / 0.5791 | 42 / 475 / 1470 | 31 % |
| Sphere (v1912 field) | 339,042 | 127.700 | +0.146 % | 4e-6 % | 2.0 % | 0.1670 / 0.1672 | 44 / 822 / 1269 | 18 % |
| Fresh cube (v2512 Allrun, 124 s) | 359,240 | 1237.237 | -0.004 % | 3e-6 % | 2.4 % | 1.2625 / 1.2624 | 10 / 261 / 787 | 63 % |

Acceptance: PASS on all four. The reference is OpenFOAM's own function objects; their source
lines are cited in the spec. None of these Cd values is a physical result: every run stopped at
400 iterations without converging (FIX_PLAN step 2).

### Open issues
- Viscous gap of 0.6 to 2.4 %: ours keeps only the tangential `snGrad` term of
  `devTwoSymm(gradU_b)`. This is a hypothesis taken from reading the source and has not yet been
  isolated numerically. It is worth at most 0.15 % of drag here, but will matter for streamlined
  bodies.
- y+ is far outside 30 to 300 (FIX_PLAN step 3).
- Purge the 1912 leftovers (Bilal, sudo): `sudo apt purge -y libopenfoam openfoam-examples`.
- `~/wind_tunnel/_step0` (copies plus the fresh cube, 695 MB) and `_install_check` (90 MB) can be
  deleted once Bilal agrees.
- A case written from Windows needs `wsl -u root chown` (as `wsl.launch` does) and `bash Allrun`;
  `./Allrun` is not executable over 9P.

### REVIEWER PROMPT
```
FRESH SESSION, REVIEW ONLY. Repo: D:\10_PROJECTS\aerodynamics blender openfoam (read CLAUDE.md).
Review the diff 83a661b..23f65e5 (FIX_PLAN step 0). Do not rewrite code; report PASS or FAIL per
standard with file:line evidence.
1. OpenFOAM definitions: export_field.body_forces and tools/audit/step0_check.py match
   docs/reference/step0_openfoam_build.md. Check against the installed source
   /usr/lib/openfoam/openfoam2512/src (forces.C 717-733, forceCoeffs.C 160/311-313,
   nutUSpaldingWallFunction 65/342, gaussGrad.C 228). Is the viscous-gap explanation right?
2. Pure modules (case.py, case3d.py, meshgen.py, results.py, flowfield.py, wsl.py, export_field.py)
   do not import bpy.
3. Tests assert behaviour (which bashrc path is chosen, which decomposition method is written and
   that the fallback runs before decomposePar), not that files exist. Run
   py -m unittest discover -s tests -v: expect 21 run, 18 pass, 3 expected failures.
4. No em dashes in any added text (git diff 83a661b..23f65e5 | grep the em dash character).
5. Every number in validation/step0_v2512.json, SESSION_LOG.md and the commit message names its
   source, and nothing is called validated without a cited reference value.
6. LF line endings: git ls-files --eol on all changed files.
7. Allrun fallback line in case3d.write_case: correct shell logic when the library exists and
   when it does not.
Use MSYS_NO_PATHCONV=1 for every wsl call. No sudo. Mark technical terms with an asterisk and add
a short glossary.
```

### NEXT PROMPT (FIX_PLAN step 1, Cp reference)
```
FRESH SESSION. Slice: FIX_PLAN step 1 (Cp reference to freestream static pressure).
CONTEXT TO LOAD: CLAUDE.md, docs/FIX_PLAN.md step 1 only, docs/ACCURACY_AUDIT.md section 4 only,
SESSION_LOG.md last entry. Facts already established: OpenFOAM v2512 at
/usr/lib/openfoam/openfoam2512 with source in src/, and function objects work. p = 0 is fixed at
the outlet. Inlet mean static Cp vs outlet (v1912, t = 400): cube +0.045, cone +0.011,
sphere +0.005 (baseline_v0.4.0.json).
STAGE 1 VERIFY: tests (21 run, 18 pass, 3 expected failures); ls /usr/lib/openfoam.
STAGE 2 GRILL, one question at a time with a recommendation:
 Q1 reference: subtract the mean inlet static p in export_field.py, or change the BCs
    (freestreamPressure/freestreamVelocity or totalPressure)? A BC change alters the solve,
    which means new runs.
 Q2 which plane or patch defines p_inf: the inlet patch mean, or a probe 2 L upstream?
 Q3 acceptance cases: cube front-face stagnation Cp = 1.00 within 2 %, and the inlet mean Cp = 0
    within 0.2 %. Which time and which copies?
STAGE 3 REFERENCE, read only: src/functionObjects/field/pressure (mode staticCoeff, pInf, UInf,
rhoInf, hydroStaticMode), and src/finiteVolume/fields/fvPatchFields/derived/freestreamPressure and
freestreamVelocity. Write docs/reference/step1_cp_reference.md (about one page).
STAGE 4 TDD: red, then green, on a pure helper (for example cp_from_p(p, p_inf, U_inf)) and on any
dictionary change in case3d.
STAGE 5 TRACER: copies only, in ~/wind_tunnel/_step1. Compare OpenFOAM's pressure function object
(staticCoeff) with our Cp. Record the numbers in validation/step1_*.json.
STAGE 6: tests, deploy, smoke check, version 0.4.2, commit stating the Cp shift in % of q.
STAGE 7: append to SESSION_LOG.md, with REVIEWER and NEXT prompts.
RULES: stop at about 100k tokens and write SESSION_LOG.md; no sudo; no em dashes; asterisk the
terms and add a glossary; never call a result validated without a cited reference value.
```

## 2026-10-20: step 0 review closed (docs/reviews/step0_review.md)

- Wording correction to commit 23f65e5, whose message calls the viscous gap "explained": the gap is a hypothesis, attributed by elimination to the wall terms `body_forces` drops; the split between those terms has not been measured.

## 2026-10-20: FIX_PLAN step 1 (Cp referenced to freestream static pressure), version 0.4.2

Status: all stages done. Code commit 0281002 (plus 67eb372, a formatting-only reflow of the step 0
reference doc). Stage 6 QA in live Blender (scene QA_Step1) passed with Bilal's OK on 2026-10-21.
Version 0.4.2. Tests: 26 run, 23 pass, 3 expected failures. Deploy and headless smoke check OK.

### Done
- Stage 0 committed as d3ea787 (step 0 review closed). `_step0` and `_install_check` deleted with
  Bilal's OK after copying Cube (v2512 fresh run), Cone, Sphere into `~/wind_tunnel/_step1`.
- numpy 2.5.4 and scipy 1.18.1 installed for `py` (which is Python 3.12.10, not 3.10 as CLAUDE.md says).
- Code: export_field.py `inlet_reference_pressure`, `cp_from_p`, `forces_record`, `write_field_npz`;
  4 new tests shown failing first. field.npz `p` is now `rho (p - p_inf)` in Pa, so the Blender VDB
  `cp` grid is relative to p_inf with no change in viz3d. Body forces still use the raw p, so every
  v0.4.1 `forces.json` value is unchanged; new keys `p_inf_Pa`, `p_inf_Cp_vs_outlet`.
- Tracer: tools/audit/step1_check.py, tools/blender_cp_probe.py; numbers in validation/step1_cp_v2512.json.
- Live QA: Load 3D result on a staged copy of the patched cube (`~/wind_tunnel/3d_CubeStep1`), Cd
  property 1.262434 (forces.json 1.2624345), WT Slice in Pressure mode, stagnation red ahead of the
  front face. Afterwards the QA scene and the objects and data it created were removed from Bilal's
  open Blender file (not saved), and `3d_CubeStep1` was deleted.

### Decisions locked by the grill
| # | Answer |
|---|---|
| Q1 | Post-process, no BC change: p_inf = area-weighted mean of p on the `inlet` patch from the inlet faces' owner cells; subtract it from the field.npz p only |
| Q2 | The inlet patch defines p_inf; its non-uniformity and a plane 1 L and 2 L downstream of the inlet are reported as a bound |
| Q3 | Gates: p_inf vs OpenFOAM `surfaceFieldValue` within 0.001 q; inlet mean Cp after the shift 0 within 0.002; body Cp vs `pressure` function object (`staticCoeff`) within 0.001 on every face. Cube stagnation Cp 1.00 within 2 % is recorded, not tuned, and does not block the commit. Cone tip and sphere stagnation reported only |

### Numbers (t = 400, 400 iterations, none converged; source validation/step1_cp_v2512.json)
| Case | Fields | Cells | p_inf as Cp vs outlet (shift) | inlet Cp max - min | plane 1 L / 2 L after inlet | body Cp vs `pressure` FO, max abs | stagnation face Cp (before) |
|---|---|---|---|---|---|---|---|
| Cube | v2512 fresh run | 359,240 | +0.0419 (-4.19 % of q) | 0.0504 | -0.0007 / -0.0039 | 3.9e-7 | 1.0232 (1.0651), gate 1.00 +/- 2 % FAIL by 0.3 % |
| Cone | v1912 | 355,327 | +0.0112 (-1.12 % of q) | 0.0100 | +0.0001 / -0.0004 | 2.7e-8 | 0.6197 (0.6309), tip face, reported only |
| Sphere | v1912 | 339,042 | +0.0047 (-0.47 % of q) | 0.0118 | +0.00003 / +0.0001 | 3.3e-7 | 0.9817 (0.9864), reported only |

p_inf matches `surfaceFieldValue` areaAverage on the inlet to 2e-10 q on all three; cone and sphere
reproduce the baseline_v0.4.0.json inlet offsets (+0.011, +0.005). Blender VDB probe (cube): Cp 1.0221
half a voxel ahead of the front-face centre, 0.1481 at (-2.5, -1.25, -1.25) on the grid's upstream face;
VDB vs npz difference 0.0. Along the slice's upstream edge (x = -2.5, y = 0) Cp runs from 0.446 on
the axis to 0.046 at z = 2.5 m, because the grid starts only 0.75 L ahead of the body.

### Open issues
- Cube stagnation Cp 1.0232 > 1: present in OpenFOAM's own `pressure` FO, so it is in the solved
  field, not our interpolation. Cause not determined; candidates are the unconverged solve (step 2)
  and the total-pressure excess in ACCURACY_AUDIT #3.
- (a) WT Slice colours Cp with the speed ramp (viz.SPEED_STOPS, mapped from Cp -2.5..1 in
  viz3d._slice_tree), so Cp = 0 shows as yellow (ramp position 0.714) and there is no grey stop.
  Needs a diverging ramp centred on Cp = 0 (FIX_PLAN step 6, visualisation honesty).
- (b) The coloured slice stops about 0.25 m short of its outline on the downstream and top sides:
  the edge of the field.npz grid, where the slice deletes faces with sampled speed < 0.01. Cause not
  chased (step 6).
- (c) Inlet non-uniformity: Cp spread 0.050 across the cube inlet (0.010 cone, 0.012 sphere), so the
  inlet is too close to the body for a uniform p_inf. For step 4 (domain).
- The sidebar prints Cd with 3 decimals (`__init__.py:1061`).
- Still pending (Bilal, sudo; checked installed 2026-10-21): `sudo apt purge -y libopenfoam openfoam-examples`.
- `~/wind_tunnel/_step1` (359 MB) and `_audit` (3.2 GB) can be deleted once no longer needed; step 2
  acceptance uses the `_audit` 1200-iteration values, so keep `_audit` until step 2 is closed.
- CLAUDE.md says `py` is 3.10; it is 3.12.10.
- Blender MCP: `get_screenshot_of_area_as_image` returned a stale frame twice even after a forced
  redraw; `bpy.ops.render.opengl(view_context=True)` gave a faithful viewport image.

### REVIEWER PROMPT
```
FRESH SESSION, REVIEW ONLY. Repo: D:\10_PROJECTS\aerodynamics blender openfoam (read CLAUDE.md).
Review the diff 67eb372..0281002 (FIX_PLAN step 1, Cp reference) and the session log commit after
it. Do not rewrite code; report PASS or FAIL per standard with file:line evidence. Save the report
to docs/reviews/step1_review.md.
1. OpenFOAM definitions: export_field.inlet_reference_pressure and cp_from_p match
   docs/reference/step1_cp_reference.md and the installed source
   /usr/lib/openfoam/openfoam2512/src: functionObjects/field/pressure (staticCoeff, pInf, UInf,
   rhoInf; pInf in Pa, not m2/s2) and surfaceFieldValue areaAverage. Is the owner-cell value the
   inlet face value (p zeroGradient on inlet, case3d.py:246)?
2. Units: field.npz p = rho (p - p_inf) in Pa; viz3d.write_vdb cp = p / (0.5 rho U^2). Check the
   chain end to end and that forces.json body forces still use the raw p (v0.4.1 values identical).
3. Numbers: every value in validation/step1_cp_v2512.json, SESSION_LOG.md and the 0281002 commit
   message traces to a log or file under ~/wind_tunnel/_step1 (cube, cone, sphere). Re-run
   tools/audit/step1_check.py on one case and compare. Nothing called validated without a cited
   reference value; the cube stagnation miss (1.0232 vs 1.00 +/- 2 %) is stated as a miss.
4. Tests assert behaviour (p_inf weighting by face area, Cp formula, forces.json keys, npz shift),
   not that files exist. Run py -m unittest discover -s tests -v: expect 26 run, 23 pass,
   3 expected failures.
5. Pure modules (case.py, case3d.py, meshgen.py, results.py, flowfield.py, wsl.py, export_field.py)
   do not import bpy.
6. No em dashes in any added text (git diff 67eb372..HEAD | grep the em dash character).
7. LF line endings: git ls-files --eol on all changed files.
8. Version 0.4.2 in both wind_tunnel/blender_manifest.toml and bl_info in __init__.py.
Use MSYS_NO_PATHCONV=1 for every wsl call. No sudo. Mark technical terms with an asterisk and add
a short glossary.
```

### NEXT PROMPT (FIX_PLAN step 2, convergence gate)
```
FRESH SESSION. Slice: FIX_PLAN step 2 (convergence gate).
CONTEXT TO LOAD: CLAUDE.md, docs/FIX_PLAN.md step 2 only, docs/ACCURACY_AUDIT.md section 1 only,
SESSION_LOG.md last entry. Facts already established: OpenFOAM v2512 with source in
/usr/lib/openfoam/openfoam2512/src; function objects (forces, forceCoeffs, yPlus, pressure,
surfaceFieldValue) work. Add-on 0.4.2: Cp is referenced to the inlet mean static p (step 1).
3D runs stop at a fixed endTime (case3d.py:284, Setup.iterations, panel iterations3d default 400,
__init__.py:87) with residualControl p 1e-5 (case3d.py:326) that 400 iterations never reach.
field_state() returns "solved" from the object signature only (__init__.py:779). Audit values at
1200 iterations (v1912 fields, ~/wind_tunnel/_audit, tools/audit/extend.sh): cube Cd 1.151
(spread 1.151 to 1.173 over 750 to 1200), cone 0.583 (flat). The v2512 fresh cube has 359,240
cells vs 358,176 for the v1912 cube and Cd 1.2624 vs 1.2509 at 400.
STAGE 1 VERIFY: tests (26 run, 23 pass, 3 expected failures); ls ~/wind_tunnel/_audit.
STAGE 2 GRILL, one question at a time with a recommendation:
 Q1 mechanism: forceCoeffs function object every N iterations plus a runTimeControl
    (averageCondition / equationInitialResidual conditions) inside OpenFOAM, or chunked runs
    with the gate in Python? Which N?
 Q2 gate: Cd change < 0.5 % over the last 200 iterations AND p initial residual down 3 orders
    (from which reference iteration?), cap 3000. Reported Cd = mean of the last 200 with min/max.
 Q3 acceptance: reproduce 1.151 and 0.583 within 1 %. Those are v1912 numbers on a slightly
    different cube mesh; rerun both on v2512 to 1200 first, or gate against the v1912 values?
 Q4 panel: exact wording for "converged" / "not converged: <reason>", and no Cd shown while the
    gate is open.
STAGE 3 REFERENCE, read only: src/functionObjects/utilities/runTimeControl (conditions
averageCondition, equationInitialResidualCondition, minMaxCondition), forceCoeffs output files,
solverPerformance / initial residual definition. Write docs/reference/step2_convergence_reference.md
(about one page).
STAGE 4 TDD: red, then green, on a pure gate function (for example gate(history) -> verdict,
reasons, Cd mean/min/max) and on the controlDict text case3d writes.
STAGE 5 TRACER: copies only, in ~/wind_tunnel/_step2. Run the gate on the cube and the cone; record
iterations to pass, Cd mean/min/max and residual drop in validation/step2_*.json.
STAGE 6: QA in Bilal's live Blender through the Blender MCP (new scene, never his own objects);
wait for his OK.
STAGE 7: tests, deploy, smoke check, version 0.4.3, commit stating how Cd changed and by how much.
STAGE 8: append to SESSION_LOG.md, with REVIEWER and NEXT prompts.
RULES: stop at about 100k tokens and write SESSION_LOG.md; no sudo; no em dashes; asterisk the
terms and add a glossary; never call a result validated without a cited reference value.
```
