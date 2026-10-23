# Session log archive, 2026-10 (moved verbatim from SESSION_LOG.md on 2026-10-22)

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
one voxel (0.05 m) ahead of the front-face centre, 0.1481 at (-2.5, -1.25, -1.25) on the grid's upstream face;
VDB vs npz difference 0.0. Along the slice's upstream edge (x = -2.5, y = 0) Cp runs from 0.446 on
the axis to 0.046 at z = 2.5 m, because the grid starts only 0.75 L ahead of the body.

### Open issues
- Cube stagnation Cp 1.0232 > 1: present in OpenFOAM's own `pressure` FO, so it is in the solved
  field, not our interpolation. Attribution from the step 1 review (docs/reviews/step1_review.md
  3.4), reasoning on the stored t = 400 fields, not a validated result: U is fixed uniform on the
  inlet while p there is zero gradient and raised near the axis by the body, so the stagnation
  streamline enters with total pressure 1.031 q above the inlet mean p (sphere 1.0076 q); along
  the axis p0 only decreases (1.031 to 1.024 q at the wall cell), so no total pressure is created
  on the stagnation line. Cp 1.0232 = inlet centre excess +0.031 minus about 0.008 q loss. This is
  open issue (c), inlet non-uniformity (step 4); convergence (step 2) is not excluded but is not
  needed to account for the magnitude. Test of the attribution: after step 4, with inlet Cp
  spread below 0.002, cube stagnation Cp should fall within 1.00 +/- 2 %.
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

## 2026-10-21: step 1 review closed (docs/reviews/step1_review.md)

- 8 PASS, 0 FAIL. The 4 required fixes (probe point is one voxel, 0.05 m, ahead of the front face,
  not half a voxel; three stale citations in step1_cp_reference.md; cube stagnation attribution in
  the step 1 open issues) are applied. Recommended items (rho stored in field.npz, step1_check.py
  defaults read from the case, key renames) are not done; the rho coupling is noted for step 2+.

## 2026-10-21: FIX_PLAN step 2 (convergence gate), IN PROGRESS

### Decisions locked by the grill
| # | Answer |
|---|---|
| Q1 | AMENDED in Stage 3 (Bilal's go): `forces` + `solverInfo` FOs every iteration, `systemCall` (`master yes`) runs our stdlib-only gate every 5 iterations, which writes `<case>/wt_stop` on pass; `abort` FO (`action writeNow`) stops. Reason: `averageCondition` bounds abs(window mean - current) (valueAverageBaseTemplates.C:153-162), weaker than the band. `forces` (N), not `forceCoeffs`, because Aref (frontal area) is only known in export_field |
| Q2 | Converged at iteration n when (max - min)/abs(mean) of Cd over n-199..n < 0.5 %, the first p solve's normalised initial residual < 1e-3 (iteration 1 reads 1.0), and n >= 400; cap 3000 (panel Iterations becomes the cap); fvSolution residualControl removed. Report Cd, Cl, Cs mean/min/max over the window; only Cd gated |
| Q3 | Fresh v2512 Cube and Cone in ~/wind_tunnel/_step2: gated run, then continue ungated to 2000; offline gate on the full history must agree with the runTimeControl stop. Accept: (a) gate open at 400 and 800 on the cube; (b) mean of 1801-2000 within 1 % of the reported mean; (c) cone reported mean within 1 % of 0.583. Cube reported against 1.151 (and 1.151-1.173), not gated |
| Q4 | Converged: "Converged at iteration N: p residual r, Cd band b %" then window means (min to max), forces in N as window means. Not converged (cap or stopped): reasons only, no Cd/Cl/forces. Solving: iteration and p residual. field_state "solved" only with forces.json converged true; finished unconverged runs load the field as new state "unconverged"; _cached reads the same flag, so v0.4.x cases show as not converged |

### Done so far (stages 0 to 3)
- Stage 0: review report committed (8d36306), required fixes (4846d09). Stage 1: 26 run, 23 pass,
  3 expected failures; `_audit` present (3.2 GB).
- Stage 3: docs/reference/step2_convergence_reference.md (0724640). Probe on a copy of the v2512
  cube (`~/wind_tunnel/_step2/probe`, 130 MB, serial): forces/solverInfo/systemCall/abort chain
  works; abort writes one iteration after the trigger (gate passed at 402, `403/` written).
  Serial cost about 1.2 to 1.7 s per iteration on 359,240 cells.
- Audit Cd (50-iteration saves, history.py, v1912): cube 1.173 (750), 1.165 (800), 1.155 (1000),
  1.151 (1200); cone 0.583 from 650 on. p initial residual: cube 0.00164 at 1200 (2.79 orders),
  cone 0.00014 (3.85 orders). The cube will not pass the residual test by 1200; about 1450 by
  extrapolation of the 1000-1200 trend (not measured).

### Design constraints for Stage 4 (from the reference and the advisor review)
1. New pure stdlib module `wind_tunnel/convergence.py` (no numpy, no bpy): parse force.dat and
   solverInfo.dat (column names from the last `#` line, drop an incomplete last line, merge all
   `<startTime>` dirs sorted, later rows win), `gate(times, fx, fy, fz, p_initial) -> dict` with
   converged, reasons, iteration, band, residual, window Fx/Fy/Fz mean/min/max. CLI mode
   `python3 convergence.py <case> --trigger` writes `wt_stop` (content `action=writeNow`) on pass.
   case3d copies it next to export_field.py; export_field imports it.
2. controlDict: `functions { forces {...; patches (body); rho rhoInf; rhoInf <rho>; CofR (0 0 0);
   writeControl timeStep; writeInterval 1; log off;} solverInfo {fields (p); writeResidualFields no;}
   gate {type systemCall; master yes; executeControl timeStep; executeInterval 5; writeControl none;
   executeCalls ("python3 convergence.py . --trigger");} stop {type abort; file "<case>/wt_stop";
   action writeNow;} }` in that order; `endTime` = cap; residualControl removed from fvSolution.
3. Allrun: `rm -f wt_stop` before simpleFoam. Check the systemCall working directory is the case
   (probe used a relative `bash probe_gate.sh` and it worked from the case dir).
4. export_field: final verdict at the written time from the full history -> forces.json
   `converged`, `reasons`, `iterations`, `Cd_band`, `p_initial`, window `Cd/Cl/Cs` mean/min/max and
   `drag_N/lift_N/side_N` window means under new keys; existing snapshot keys unchanged.
5. __init__.py: `iterations3d` default 3000, min 400 (cap); panel per Q4; `field_state` "solved"
   only with `converged: true`, new "unconverged"; `_cached` reads the flag; status "stopped"
   never solved. Progress line shows iteration and p residual (results.progress).
6. Stage 5 continuation to 2000: delete `wt_stop`, drop gate and stop FOs from the copy's
   controlDict, set endTime 2000, run, then offline gate on the merged history.
7. Latent rho coupling from the step 1 review: forces FO `rhoInf` must come from Setup3D.rho.

### Open issues (added this session)
- `~/wind_tunnel/_review1` (118 MB, step 1 reviewer's Sphere copy) and `_step2/probe` (130 MB)
  can be deleted; ask Bilal.
- If a user's WSL default user is root, systemCall is fatal (systemCall.C:123); Allrun should
  check `id -u` and fail with a clear message.

### NEXT PROMPT (FIX_PLAN step 2, continue at Stage 4)
```
FRESH SESSION. Slice: FIX_PLAN step 2 (convergence gate), continue at Stage 4.
CONTEXT TO LOAD: CLAUDE.md, docs/reference/step2_convergence_reference.md, SESSION_LOG.md last
entry (decisions Q1 amended to Q4, design constraints 1 to 7). Do not redo the grill or Stage 3.
STAGE 4 TDD: red, then green: convergence.py parsers (header-driven, partial last line, merged
restart dirs), gate() on synthetic histories (band just under / over 0.5 %, residual just under /
over 1e-3, n < 400, cap reached), the --trigger CLI, case3d controlDict/Allrun text (FO order,
endTime = cap, no residualControl, rm -f wt_stop, convergence.py copied), export_field verdict keys,
and field_state/_cached logic where it can be tested without bpy.
STAGE 5 TRACER: fresh v2512 Cube and Cone from the new Allrun in ~/wind_tunnel/_step2 (8 procs
or more), gated; then continue each ungated to 2000 (constraint 6). Record stop iteration, lag,
Cd/Cl/Cs mean/min/max, band, residual, offline-gate agreement, and acceptance (a) to (c) plus the
cube vs 1.151 in validation/step2_gate_v2512.json.
STAGE 6: QA in Bilal's live Blender through the Blender MCP (new scene, never his own objects):
converged, not converged and solving wordings; wait for his OK.
STAGE 7: tests, deploy, smoke check, version 0.4.3 (manifest and bl_info), commit stating how Cd
changed and by how much versus the 400-iteration values (cube 1.2624 v2512, cone 0.5791).
STAGE 8: append to SESSION_LOG.md with REVIEWER and NEXT prompts.
RULES: stop at about 100k tokens and write SESSION_LOG.md; no sudo; no em dashes; asterisk the
terms and add a glossary; never call a result validated without a cited reference value.
```

## 2026-10-21: FIX_PLAN step 2, stages 4 and 5 done (commits 1a4d9e2, 382cc23), version 0.4.3, Stage 6 pending

### Decision added by the grill
| # | Answer |
|---|---|
| Q5 | Keep both criteria hard (band AND p residual < 1e-3 AND n >= 400, cap 3000). Reasons carry the p residual trend over the window (orders per 100 iterations). No "converged with residual plateau" state. Basis: in the v1912 `_audit` cube history the p residual is not plateaued at 1200 (2.40, 2.51, 2.61, 2.70, 2.79 orders at 800 to 1200, about 0.09 orders per 100 iterations; window max/min 1.57 down to 1.24), and the Cd band already passes at 1200 while Cd still drifts, so a force-first gate would stop on a moving Cd. Scored offline in Stage 5 (below): confirmed |

### Done
- Stage 4 (TDD, red then green; 67 tests, 3 expected failures): `wind_tunnel/convergence.py` (stdlib: header-driven `.dat` parser, unfinished last line dropped, restart dirs merged numerically with later rows winning, `gate()`, `--trigger` CLI that never fails the solver); case3d controlDict FOs (`forces`, `solverInfo`, `gate` systemCall every 5, `stop` abort with `file "wt_stop"`), `endTime` = cap, `Setup3D.iterations` 3000, `residualControl` removed, Allrun fails at once as root and runs `rm -f wt_stop` before simpleFoam, `convergence.py` copied into every case, `--cap` passed to export; `export_field.verdict_record` merged into forces.json; `results.forces_converged` and `results.verdict_lines` (Q4 wording); `__init__.py`: "Max iterations" default 3000, min 400, `converged3d`/`verdict3d`, new state "unconverged" (field loaded and flagged, no Cd or forces shown), progress line shows iteration and p residual.
- `results.progress` now returns the FIRST p solve of the last iteration (the gate's quantity), not the last p solve. This also changes the 2D panel's residual display (display only).
- Source facts read this session: abort resolves a relative `file` against the case (`abort.C:170-172`) and deletes the trigger file at construction and at `end()` (`:154`, `:253`), so `wt_stop` never survives the run; systemCall ignores the call's return code (`systemCall.C:68`).
- Deploy and headless smoke check pass (0.4.3 registered). Bilal has not reloaded the add-on yet.
- Stage 5 on v2512, 24 ranks, COARSE, `~/wind_tunnel/_step2/{Cube,Cone}`; scripts `tools/audit/step2_tracer.sh`, `tools/audit/step2_check.py`; record `validation/step2_gate_v2512.json`.

### Numbers (Stage 5)
| | Cube (359,618 cells) | Cone (355,379 cells) |
|---|---|---|
| gate trigger / written (lag) | 1830 / 1831 (1) | 725 / 726 (1) |
| offline first pass, every 5 / any | 1830 / 1829 | 725 / 724 |
| band, p residual, trend | 0.17 %, 9.82e-4, -0.087 orders/100 | 0.21 %, 9.61e-4, -0.185 orders/100 |
| Cd window mean (min to max) | 1.1498 (1.1490 to 1.1510) | 0.5833 (0.5826 to 0.5838) |
| Cl, Cs window means | 0.0010, -0.0021 | 0.0002, 0.0001 |
| Cd mean 1801-2000, vs reported | 1.1487, -0.09 % | 0.5822, -0.18 % |
| forces FO vs face sum at written time | 1.14917 vs 1.14914 | 0.58257 vs 0.58260 |
| Q5 force-first (band only): stop, Cd, vs 1801-2000 | 1570, 1.1539, +0.45 % | 675, 0.5831, +0.16 % |
| vs the project's own v1912 1200-iteration audit value (not experiment) | 1.151: -0.11 %, below the 1.151 to 1.173 spread by 0.0012 | 0.583: +0.05 % |
| Cd at 400 in this run (forces FO) | 0.809 | 0.576 |

Acceptance: (a) cube gate open at 400 (band 33.6 %) and 800 (band 42.2 %): pass. (b) both within 1 %: pass. (c) cone within 1 % of 0.583: pass. None of this is validation against experiment.

Cube trajectory (forces FO Cd every 100 iterations): 0.85, 0.77, 0.78, 0.81 (400), 0.86, 0.90, 1.18, 1.26 (800), 1.27, 1.20, 1.18, 1.17 (1200), 1.16, 1.155, 1.153, 1.151, 1.150, 1.149, 1.149, 1.148 (2000). The p residual reaches 1e-3 at about 1830, not the ~1450 extrapolated from the v1912 data.

Path dependence: the step 1 v2512 cube (`_step1/Cube`, 359,240 cells, Cd 1.2624 at 400) is the same cube [-1,1]^3 with a different STL triangulation (other face diagonals and triangle order); every other input is identical apart from residualControl. Residuals agree within about 2 % to iteration 200, then split (0.028 vs 0.047 at 400). The cube's 400-iteration Cd therefore varies by about 35 % between near-identical meshes. The Stage 5 commit headline "1.2624 -> 1.1498 (-8.9 %)" compares against that other mesh; against this run's own 400 value the change is 0.809 -> 1.150 (+42 %). Whether the gated value is equally path independent is not tested (one gated run per body).

### Open issues (added)
- Verdict flip: the gate passes at n, the run writes n+1 and export recomputes at n+1; in principle n+1 could fail the band and show "not converged". Not seen (both cases still pass at the written time).
- A scene saved with `iterations3d` below 400 keeps its stored value (Blender does not re-clamp on load); that run would end at the cap with "before 400" as a reason.
- `_step2/probe` (130 MB): delete after step 2 is committed (Bilal's go, given). `_step2/Cube` and `Cone` (about 400 MB each) are the Stage 5 evidence; keep until the step 2 review closes.
- Gate cost not measured separately; cube wall time 10 min to 1831 on 24 ranks (about 0.33 s per iteration).

### REVIEWER PROMPT
```
FRESH SESSION. Review FIX_PLAN step 2 (convergence gate): commits 1a4d9e2, 382cc23, dc56044
(Stage 6 QA fixes, 0.4.4) and the session-log commits after them. Read CLAUDE.md, docs/reference/step2_convergence_reference.md,
SESSION_LOG.md last three entries, validation/step2_gate_v2512.json. Check, PASS/FAIL each:
1. convergence.gate matches Q2 exactly: window n-199..n (200 values), band on Fx with abs(mean),
   p_initial at n only, n >= 400, cap reason only when not converged. Look for off-by-one.
2. Parser: header from the last # line; unfinished last line dropped; restart dirs sorted
   numerically, later wins; columns by name (force.dat total_x/y/z, solverInfo p_initial).
3. controlDict FO order forces, solverInfo, gate, stop; executeInterval 5; abort file relative
   (abort.C:170-172); rhoInf from Setup3D.rho; endTime = cap; no residualControl in fvSolution.
4. Recompute from ~/wind_tunnel/_step2/{Cube,Cone}/postProcessing with your own short script
   (not convergence.py): trigger iteration, window mean/min/max Cd, band, 1801-2000 mean. Must
   match validation/step2_gate_v2512.json to 4 significant figures.
5. Cd = Fx / (0.5 rho U^2 A_frontal), Cl = Fz, Cs = Fy in export_field.verdict_record; forces FO
   vs face sum at the written time agree (log the difference).
6. Panel: no Cd/Cl/forces shown when not converged; a v0.4.x forces.json (no converged key)
   shows "no convergence record"; field_state "solved" only with converged3d.
7. results.progress returns the first p solve of the last iteration; note the 2D display effect.
8. Tests: py -m unittest discover -s tests (70 run, 3 expected failures). No bpy in pure modules.
9. No em dashes in added text; LF endings (git ls-files --eol); version 0.4.4 in manifest and bl_info.
10. The path-dependence claim (step 1 vs step 2 cube STL triangulation) is stated with its limits.
11. Gated path independence (tests the Stage 5 caveat "one gated run per body"): rerun the cube
   through the gate with the OTHER STL triangulation, the 359,240-cell variant (binary STL in
   ~/wind_tunnel/_step1/Cube/constant/triSurface/body.stl). Build ~/wind_tunnel/_step2/Cube_tri2
   from _step2/Cube's inputs only (Allrun, convergence.py, export_field.py, 0.orig, system,
   constant without polyMesh), swap in that body.stl, then run `bash tools/audit/step2_tracer.sh
   Cube_tri2` from WSL (same COARSE settings and 24 ranks as Stage 5). PASS when the gated Cd window mean agrees with 1.1498 within
   0.5 % (1.1441 to 1.1555). Record stop iteration, cells, band, p residual, Cd mean/min/max and
   the difference in % in validation/step2_gate_v2512.json under a new key (cases.Cube_tri2), with
   the date. A FAIL means the gate does not remove the path dependence: report, do not tune.
Use MSYS_NO_PATHCONV=1 for every wsl call. No sudo. Write docs/reviews/step2_review.md. Mark
technical terms with an asterisk and add a short glossary.
```

### NEXT PROMPT (FIX_PLAN step 2, finish: stages 6 to 8)
```
FRESH SESSION. Slice: FIX_PLAN step 2, finish at Stage 6. Load CLAUDE.md and SESSION_LOG.md last
entry only. Stages 4 and 5 are done and committed; do not rerun them.
STAGE 6 (needs Bilal's OK first; he restarts Blender or toggles the add-on to load 0.4.3): QA in
his live Blender through the Blender MCP, in a NEW scene, never his objects. Three wordings:
 - not converged (old record): a fresh cube object named for an existing v0.4.x case, Load 3D:
   expect "Not converged: / no convergence record ...", no Cd or forces, field loaded and flagged.
 - converged: copy ~/wind_tunnel/_step2/Cube to ~/wind_tunnel/3d_<QAname> with forces_gated.json
   as forces.json (the current forces.json there is the 2000 export) and the matching field, then
   Load 3D on an object of that name: expect "Converged at iteration 1831: p residual 9.8e-04, Cd
   band 0.17 %", Cd 1.150 (1.149 to 1.151) and window-mean forces.
 - solving: a short live run shows "solving, iteration N, p residual r".
Remove the QA scene, every WT datablock it made and the 3d_<QAname> folder afterwards; never save
his file. Wait for his OK.
STAGE 7: tests, deploy, smoke; commit stating the Cd change (Stage 5 numbers and the
path-dependence note). Then delete ~/wind_tunnel/_step2/probe.
STAGE 8: append to SESSION_LOG.md (the REVIEWER prompt above stays valid), update the memory file.
RULES: no sudo; no em dashes; asterisk the terms and add a glossary; never call a result
validated without a cited reference value.
```

## 2026-10-21: FIX_PLAN step 2, stages 6 and 7 done (commit dc56044), version 0.4.4

### Done
- Stage 6 live QA in Bilal's Blender (new scene WT_QA, unsaved file, never saved), on copies so no
  solved case was touched: `3d_QAOld` (copy of the v0.4.x 3d_Sphere), `3d_QAGated` (copy of
  `_step2/Cube` without `2000/`, field re-exported at 1831, `forces_gated.json` as forces.json).
  - Old record: "Not converged:" plus the no-record lines, no Cd or forces, state `unconverged`. PASS.
  - Converged: "Converged at iteration 1831", "p residual 9.8e-04, Cd band 0.17 %", Cd 1.150
    (1.149 to 1.151), Cl 0.001, Cs -0.002, Drag 1126.78 N (window means), state `solved`. PASS.
  - Solving: "solving, iteration 53, p residual 7.5e-02, 0:38" on a live run, state `solving`. PASS.
- Two defects found and fixed (Bilal's go), 0.4.4:
  1. The default-width sidebar cut verdict lines longer than about 38 characters (the Cd line hid
     Cl and Cs). `results.verdict_lines` now gives one item per line and wraps reasons at
     `PANEL_CHARS = 38`; longest converged line 34 characters. Bilal checked the panel by eye: OK.
  2. Stop 3D: `pkill -f "<case>/Allrun"` matched the `sh -c` that ran it (pkill -f tests the whole
     command line), so the shell killed itself (exit 15) before `echo stopped`; status stayed
     `solving`. Now `wsl.stop3d_command` with `Allru[n]`. Live Solve then Stop: status `stopped`,
     no simpleFoam left, panel state `preview`.
- Tests 70 run, 3 expected failures; deploy and headless smoke pass (0.4.4). Cleanup: WT_QA scene,
  QA objects, every WT datablock, `3d_QA*` folders and `_step2/probe` (130 MB) deleted.

### Open issues (added)
- Toggling the add-on in Preferences did not reload its submodules (Blender kept 0.4.3 in
  `sys.modules`); the reload worked after removing the `wind_tunnel*` modules first. Restarting
  Blender is the reliable way to load new code.
- Blender MCP screenshots froze after the reload (data changed, image did not); the property
  strings were used as evidence and Bilal checked the panel himself.
- While another object solves, the last run's verdict stays visible under a red "(last solve, not
  the Test Object)" header; its own lines are only red when that run did not converge.
- The other installed add-on `physical-open-waters` throws in its depsgraph handler when a scene
  has no World (not ours; seen when WT_QA was created).

### NEXT PROMPT (FIX_PLAN step 2 review)
Use the REVIEWER PROMPT in the previous entry (items 1 to 11; item 11 is the gated rerun of the
other cube triangulation). After the review closes, delete `~/wind_tunnel/_step2/Cube`, `Cone`
(and `Cube_tri2`) only with Bilal's go, then FIX_PLAN step 3.

## 2026-10-21: step 2 review closed (docs/reviews/step2_review.md)

- 11 of 11 PASS, no FAIL. Items 1 to 10 from code, v2512 source (`abort.C:170-172`,
  `systemCall.C:123`) and an independent stdlib recompute of `_step2/{Cube,Cone}` (trigger, window
  Cd, band, 1801-2000 mean identical to the record). Tests 70 run, 3 expected failures.
- Item 11: `_step2/Cube_tri2` (step 1's STL triangulation, controlDict regenerated by case3d 0.4.4
  because the tracer had stripped the gate from `_step2/Cube`'s), 359,597 cells, gate at 1360,
  written 1361, Cd window mean 1.14957 vs 1.14978 (-0.018 %); 1801-2000 means -0.076 %. Cd at 400 is
  0.809 vs 1.273 on the two meshes. Recorded as `cases.Cube_tri2` in validation/step2_gate_v2512.json.
- Observations, no fix needed: unconverged Cd and forces are stored in scene properties but never
  drawn; `results.progress` can pair iteration N with the residual of N-1 for a moment.
- Pending on Bilal: delete `~/wind_tunnel/_step2/Cube`, `Cone`, `Cube_tri2` (about 1.2 GB). The
  animation slice uses `_step2/Cube` (converged at 1831): copy it to `~/wind_tunnel/_anim/Cube`
  first, or keep `_step2/Cube` until that slice is done.

### NEXT PROMPT
Bilal's ANIMATION A+B prompt (pressure slice sweep and smoke over the map), unchanged; its Stage 0
gate now passes with this review. Then FIX_PLAN step 3 (wall mesh and y+).

## 2026-10-21: WSL cleanup after the step 2 review (Bilal's go)

- `~/wind_tunnel/_step2/Cube` copied to `~/wind_tunnel/_anim/Cube` (`cp -a`; 1439 files, 405
  directories, 411,478,291 bytes in both, md5 of every file identical). The converged cube now
  lives in `_anim/Cube`. Its root `forces.json` and `field.npz` are the ungated continuation's
  export at 2000; the gated record is `forces_gated.json` (written 1831, Cd 1.1498) and the 1831
  fields are in `1831/`. Re-export at 1831 if the animation must show the gated time exactly.
- Deleted `~/wind_tunnel/_step2` (Cube, Cone, Cube_tri2, 1.2 GB) and `~/wind_tunnel/_audit` (3.2 GB).
- Every number reported from them is already in validation/*.json: `_step2` in
  `step2_gate_v2512.json` (the WSL `Cube_check.json` and `Cone_check.json` match `cases.Cube` and
  `cases.Cone` key for key; `cases.Cube_tri2` added by the review), `_audit` (v1912, 1200-iteration
  extension) in `baseline_v0.4.0.json` (Cd at 400 and 1200, 750-1200 spread, p residuals at 400, 800,
  1200). The raw per-iteration histories and logs are gone; the json keeps them only as
  every-100-iteration traces.
- Left in `~/wind_tunnel`: the solved `3d_*` cases, `naca0012_re6e06`, `_step1`, `_anim`.

## 2026-10-22: ANIMATION A+B, stages 1 and 2 (Q1), stopped at the token limit

- Prompt saved verbatim to `docs/prompts/anim_ab.md`; "Session workflow" section added to
  CLAUDE.md (commit a634901).
- Stage 1 done. Tests 70 run, OK, 3 expected failures. Blender MCP reachable (5.2.0 LTS, add-on
  0.4.4, one scene "Scene", unsaved file).
- Re-export at 1831 in `~/wind_tunnel/_anim/Cube`: `field.npz` and `forces.json` are now t = 1831;
  the 2000 export is kept as `field_2000.npz` and `forces_2000.json`; `log.export1831` is the log.
  Method: `export_field.py` takes the latest time directory and the full force history (to 2000),
  so it ran in a temporary view `_anim/_v1831` with symlinks to `constant`, `system`, `1831`, the two
  scripts and only `postProcessing/{forces,solverInfo}/0`, same arguments as Allrun
  (`--speed 20.0 --rho 1.225 --nu 1.5e-05 --voxel 0.05 --L 2 --cap 3000`); the view was deleted.
  All 35 keys of the new `forces.json` equal `forces_gated.json`: Cd 1.149141 at 1831, window
  [1632, 1831] mean 1.149780. Fields 1831 vs 2000 differ by up to 1.38 m/s in U and 7.2 Pa in p.
- Geometry facts (field.npz at 1831): grid x -2.5 to 6.0 m, y and z -2.5 to 2.5 m, h 0.05 m
  (171 x 101 x 101); cube -1 to 1 m, L = 2 m; Cp over fluid voxels -0.700 to 1.025.
- Q1 locked in `docs/reference/anim_ab_spec.md`: axis Y default (X/Y/Z choice), plus/minus 1.0 L
  clamped to grid minus a margin, 192 frames ping-pong at constant speed, one keyframe per frame,
  "Animate slice" replaces keys and sets the frame range, "Clear" removes them, "WT Label" built in
  Geometry Nodes (String to Curves from WT Slice's location and the Pressure toggle, no Python
  handler). Q2 and Q3 open.
- No code changed, no version bump. Nothing created in Blender.

### NEXT PROMPT (ANIMATION A+B, resume at Stage 2 Q2)
Full slice: `docs/prompts/anim_ab.md`; follow it from Stage 2 Q2, same structure: fresh session,
bounded context, grill one question at a time with recommendation first, TDD red then green,
tracer on copies only (`_anim`, new scene WT_ANIM), HIL visual QA, close, handoff with REVIEWER and
NEXT prompts, stop at about 100k tokens and never compact.

CONTEXT TO LOAD: CLAUDE.md; this SESSION_LOG entry only; `docs/reference/anim_ab_spec.md`;
`docs/prompts/anim_ab.md`; docs/ACCURACY_AUDIT.md section 6; wind_tunnel/viz3d.py (smoke tree,
slice tree, write_vdb, load_volume). Do not read the solver modules.

Facts established, do not re-derive:
- Stage 0 gate passed (step 2 review 11/11 PASS); Stage 1 done (above). Do not re-export.
- `_anim/Cube` root `field.npz` and `forces.json` are t = 1831 (Cd 1.149141, window mean 1.149780);
  2000 export kept as `*_2000.*`.
- Grid x -2.5 to 6.0 m, y and z plus/minus 2.5 m, h 0.05 m; cube -1 to 1 m, L = 2 m;
  Cp (fluid voxels) -0.700 to 1.025.
- The solve is steady; every frame shows only solved data.
- WT Slice: Pressure toggle switches speed / Cp, both through one MapRange (speed 0.3 to 1.9,
  Cp -2.5 to 1.0) and the speed ramp (open item a); faces deleted where sampled speed < 0.01 leave a
  ring short of the outline at the grid edge (open item b).
- WT Smoke: midpoint rule through the VDB; the surface slide acts within 0.05 L in both modes, plus a
  push back onto the surface within 0.004 L; particles are deleted when speed < 0.02, age >
  Lifetime, or farther than 6 L from the body centre.
- Q1 locked (see spec).
Next: Q2 (diverging Cp ramp: exact stops, range, legend), then Q3 (measure particles entering the
solid per 100 frames without the slide, and RK4 drift over 1 L, then recommend), lock both in the
spec, then Stage 3.

## 2026-10-22: ANIMATION A+B, Q2 locked, stopped before Q3 (Bilal's call at 122k tokens)

### State
- FIX_PLAN steps 0 to 2 done and reviewed (step 2 review 11/11 PASS). Add-on version 0.4.4.
- ANIMATION A+B (slice prompt `docs/prompts/anim_ab.md`): Stage 1 done, Stage 2 Q1 and Q2 locked in
  `docs/reference/anim_ab_spec.md`. Q3 open. No add-on code changed, no version bump, nothing
  created in Blender.
- Data: `~/wind_tunnel/_anim/Cube`, root `field.npz` and `forces.json` are t = 1831 (Cd 1.149141,
  window [1632, 1831] mean 1.149780, all 35 keys equal `forces_gated.json`); the 2000 export is kept
  as `field_2000.npz` and `forces_2000.json`.
- Q2 (this session): diverging Cp ramp, lo/hi = -1/+1 two-sided around Cp = 0, Moreland cool-warm
  9 stops (endpoints cited, intermediates computed by our own Msh implementation), WT Legend in
  Geometry Nodes, and a pixel colour test at the 9 stops (plus/minus 2/255) in the Stage 4 tracer.
  The Cp 1.025 peak clamps to red; its cause is the step 1 review's inlet explanation (open issue c,
  FIX_PLAN step 4), not a new item.
- Housekeeping: older SESSION_LOG entries moved verbatim to `docs/archive/session_log_2026-10.md`.

### Open issues carried
- a: Cp uses the speed ramp (Cp = 0 shows yellow). Fixed by the Q2 design in Stage 3.
- b: slice faces deleted where sampled speed < 0.01 leave a ring short of the outline at the grid
  edge. Fixed by Stage 3 slice clipping (grid bounds and solid mask from field.npz).
- c (step 1 review): inlet non-uniformity, stagnation line enters about 1.031 q; FIX_PLAN step 4.

### NEXT PROMPT (ANIMATION A+B, resume at Stage 2 Q3)
Slice: ANIMATION A+B. Same structure as before: fresh session, bounded context, grill one question
at a time with recommendation first, TDD red then green, tracer on copies only (`_anim`, new scene
WT_ANIM), HIL visual QA, close, handoff with REVIEWER and NEXT prompts, stop at about 100k tokens
and never compact.

CONTEXT TO LOAD (nothing else):
- CLAUDE.md; this SESSION_LOG.md; `docs/reference/anim_ab_spec.md`.
- `docs/prompts/anim_ab.md` lines 25 to 42 only (STAGE 3 to STAGE 6), for example
  `sed -n 25,42p docs/prompts/anim_ab.md`. The RULES of that file are repeated below.
- `wind_tunnel/viz3d.py`: `_smoke_tree` (starts at line 274, ends before `get_input`) and
  `build_smoke` (line 455) only, plus the node helpers `_sample`, `_vmath`, `_vsw`, `_bool` if a
  line in `_smoke_tree` needs them. Do not read the slice tree, the solver modules or the archive.

Facts established, do not re-derive:
- Stage 0 gate passed, Stage 1 done, Q1 and Q2 locked (see spec). Do not re-export the field.
- Grid x -2.5 to 6.0 m, y and z plus/minus 2.5 m, h 0.05 m (171 x 101 x 101); cube -1 to 1 m,
  L = 2 m; Cp (fluid voxels) -0.700 to 1.025. The solve is steady; every frame shows only solved data.
- field.npz holds U, p (Pa), the solid mask, origin, voxel, speed (export_field.py, IDW from 4
  nearest cell centres). The WT Flow VDB holds grids velocity, speed (|U|/U_inf) and cp.
- WT Smoke: midpoint rule through the VDB; the surface slide acts within 0.05 L in both modes, plus a
  push back onto the surface within 0.004 L; particles are deleted when speed < 0.02, age >
  Lifetime, or farther than 6 L from the body centre. Audit section 6: IDW resampling leaks 10 to
  12 % divergence next to the wall, which is why the slide exists in solved mode.
- Toggling the add-on in Preferences does not reload modules: restart Blender or reload via the MCP.

Q3 work, measure first, then ask:
1. Particles entering the solid per 100 frames with the slide off: on a copy in a new scene
   WT_ANIM (never File > New, never touch Bilal's scenes), build the cube result, set the slide off
   (and the push back off), run 100 frames, count particles whose position falls in the field.npz
   solid mask (and inside the cube box as a cross-check). Report the count per 100 frames and as a
   fraction of particles released.
2. Smoke vs reference streamline drift over 1 L: integrate reference streamlines in Python with RK4
   on the same VDB data (trilinear on the voxel grid, step at most 0.1 voxel) from the particles'
   release points; compare with the smoke paths (midpoint rule, the add-on's time step) over 1 L of
   path length. Report max and mean drift in voxels, for paths that pass near the body and for
   freestream paths separately.
3. Ask Q3 with a recommendation from those numbers: slide off, slide limited to the first voxel
   layer, or kept; and delete particles that enter the solid mask. Lock the answer in the spec.
Then Stage 3 (TDD) per the prompt's STAGE 3 section and the spec.

RULES: at about 100k tokens stop, write SESSION_LOG.md and tell Bilal; never compact. No sudo. No
em dashes. Asterisk technical terms and add a glossary. Never call a result validated without a
cited reference value. Keep SESSION_LOG.md to current state plus NEXT prompt; move superseded
entries verbatim to `docs/archive/`.

## 2026-10-22: ANIMATION A+B, Q3 and Q4 locked, stopped before Stage 3 (about 100k tokens)

### State
- FIX_PLAN steps 0 to 2 done and reviewed (step 2 review 11/11 PASS). Add-on version 0.4.4.
- ANIMATION A+B (slice prompt `docs/prompts/anim_ab.md`): Stage 1 done; Stage 2 Q1 to Q4 locked in
  `docs/reference/anim_ab_spec.md`. Grill finished. No add-on code changed, no version bump, nothing
  created in Bilal's Blender (Q3 measurements ran in a separate headless factory-startup Blender).
- Data: `~/wind_tunnel/_anim/Cube`, root `field.npz` and `forces.json` are t = 1831 (Cd 1.149141,
  window mean 1.149780), field.npz sha1 ab5348ab5db01a7d31428bd72ed9ba4c9b3d46a1.
- Q3 (commits 7966571 measurements, fc0367a lock), numbers in `validation/anim_ab_q3_measure.json`:
  Python twin of the midpoint step matches Blender to 2.4e-6 voxel; smoke vs RK4 drift over 1 L,
  slide off: max 0.062 voxel near body, 0.008 freestream; slide on (shipped): 23.5 and 24.7 voxels
  (edge bug d). Slide off with the still rule: 0 particles in the cube over 100 frames, 46 of 15000
  deleted, all within 0.35 voxel of the wall. Decision: solved mode has no slide and no push back;
  the still rule (speed < 0.02 U_inf) is the solid-entry rule; Stage 4 metric is inside the Test
  Object (cube box), mask count reported, not gated.
- Q4: fix the preview-mode slide in Stage 3 (band on Proximity Distance, slide along unit
  (P - nearest), push back unchanged), with the headless cube test in the spec.
- Scripts: `tools/audit/anim_q3_smoke.py` (headless Blender recorder), `tools/audit/anim_q3_drift.py`.

### Open issues carried
- a: Cp uses the speed ramp (Cp = 0 shows yellow). Fixed by the Q2 design in Stage 3.
- b: slice faces deleted where sampled speed < 0.01 leave a ring short of the outline at the grid
  edge. Fixed by Stage 3 slice clipping.
- c (step 1 review): inlet non-uniformity, stagnation line enters about 1.031 q; FIX_PLAN step 4.
- d: slide edge bug (band uses the projection on one face normal next to an edge). Fixed in Stage 3
  per Q4 (preview mode); concave-edge limit of the push back recorded, not solved.
- e: export_field solid mask is one node layer short on the -y and -z faces (64000 nodes vs 68921
  for the closed box). Solver-side, for FIX_PLAN; not in this slice.

### NEXT PROMPT (ANIMATION A+B, Stage 3 TDD)
Slice: ANIMATION A+B. Same structure as before: fresh session, bounded context, TDD red then green,
pure functions first, tracer on copies only (`_anim`, scene WT_ANIM), HIL visual QA, close, handoff
with REVIEWER and NEXT prompts, stop at about 100k tokens and never compact. The grill is finished
(Q1 to Q4 locked); ask Bilal only if the spec leaves a choice open (for example the Stage 3 choice of
two materials vs two ramps for the Cp branch: pick the simpler one and say which).

CONTEXT TO LOAD (nothing else):
- CLAUDE.md; this SESSION_LOG.md; `docs/reference/anim_ab_spec.md`.
- `docs/prompts/anim_ab.md` lines 25 to 42 only (STAGE 3 to STAGE 6): `sed -n 25,42p docs/prompts/anim_ab.md`.
- `wind_tunnel/viz3d.py`: `_smoke_tree` (line 274 to `get_input`), `build_smoke`, `tune_smoke`,
  `_slice_tree` (line 476 to `remove_all`), `build_slice`, and the helpers they call.
  `wind_tunnel/viz.py`: `SPEED_STOPS`, `_ramp`, `_emission_material` only.
- `tests/test_pure.py`: only the imports and one existing test class, to match the style.
- `tools/blender_smoke.py` (short) to extend; `wind_tunnel/__init__.py` only the panel draw for
  the 3D result section and the operator pattern of one existing 3D button (grep first).

Facts established, do not re-derive:
- Grid x -2.5 to 6.0 m, y and z plus/minus 2.5 m, h 0.05 m (171 x 101 x 101), node lattice
  origin + h (i, j, k) as write_vdb places it; cube -1 to 1 m, L = 2 m; Cp (fluid voxels) -0.700 to
  1.025. Steady solve; every frame shows only solved data.
- Smoke: 24 fps, Time Scale 0.08, step 0.0667 m = 1.33 voxels per frame, 150 particles per frame,
  Sample Grid interpolation Trilinear (an input socket "Interpolation" in Blender 5.2, not a node
  property). Distribute seed = frame, so runs are reproducible.
- In `_smoke_tree`: band factor is the Math node with 0.05, margin 0.004, still rule the Compare
  node with 0.02 (unique values, `tools/audit/anim_q3_smoke.py` finds them this way).
- Toggling the add-on in Preferences does not reload modules: restart Blender or reload via the MCP.
- Headless Blender in Git Bash: never leave a bare `cat > file` without a heredoc in a command (it
  waits on stdin and hangs). Windows Python reading `\\wsl.localhost` paths hung; copy files to the
  scratchpad with `wsl cp` to `/mnt/c/...` first.

Stage 3 work (spec is the contract):
1. Pure, red then green in tests/test_pure.py: `cp_to_ramp(cp, lo, hi)` (Cp 0 -> 0.5, two-sided,
   clamped), the 9 Moreland stops as data (linear column of the spec table), `sweep_keyframes(axis,
   centre, half_range, frames, pingpong)` (192 frames, ends exactly at the limits, constant speed),
   slice clipping to grid bounds and the solid mask on a synthetic grid, label text formatting
   (`Slice y = +0.85 m (+0.43 L) | Cp`).
2. Blender code: Cp branch with its own diverging ramp, WT Legend, WT Label, Animate slice and
   Clear buttons, smoke tree: slide and push back only when Use Field is off, Q4 fix for preview.
3. Headless checks in tools/blender_smoke.py: diverging ramp in Cp mode, keyframes at the expected
   positions, solved-mode smoke has no slide (read the node values / switch), the Q4 cube test.
Then Stage 4 tracer per the prompt (Bilal's live Blender through the MCP, new scene WT_ANIM).

RULES: at about 100k tokens stop, write SESSION_LOG.md and tell Bilal; never compact. No sudo. No
em dashes. Asterisk technical terms and add a glossary. Never call a result validated without a
cited reference value. Keep SESSION_LOG.md to current state plus NEXT prompt; move superseded
entries verbatim to `docs/archive/`.

## 2026-10-22: ANIMATION A+B, issue e fixed, Stage 3 done, stopped before Stage 4 (token budget)

### State
- FIX_PLAN steps 0 to 2 done and reviewed. Add-on version still 0.4.4 (0.5.0 at Stage 5 close).
  Deployed to Blender 5.2 after Stage 3: Bilal must restart Blender (or reload through the MCP) to load it.
- CLAUDE.md token rule now: end at stage boundaries, no new heavy stage after about 150k, hand off at
  about 200k (commit 6a8295f).
- Open issue e CLOSED (commit 6a8295f, record `validation/anim_ab_mask_e.json`). Cause, two ties:
  (1) column range rounding, dy = 0.04999999999999982 so (-1 - y0)/dy = 30.0000000000001 and ceil
  skipped the y = -1 and z = -1 columns; (2) a column on an x face's shared diagonal counted two
  crossings per face, so only the end nodes were filled. Fix: four offset rays per column
  (+-1e-3 dy, +-0.618e-3 dz) OR'ed, x span widened 1e-3 dx; surface nodes are solid on every face.
  Tests `SolidMask` (grid-aligned cube 41^3 = 68921 and mirror symmetric; cube at +-0.97 gives 39^3).
  `_anim/Cube` re-exported at t = 1831, no solve: mask 64000 -> 68921, spans -1.00..1.00 m on all
  axes, mirror symmetric in y and z; U and p unchanged except the 4921 added nodes (now 0, as every
  solid node). field.npz sha1 5868c18eb95212e0880898e04d211628a2771b29 (was ab5348ab).
  forces.json byte-identical (sha1 77061b3d, equal to forces_gated.json, Cd 1.1491410217993128).
  A fresh export rewrites the verdict block from the log history to 2000 (kept as
  `forces_1831e_verdict2000.json`); the gated record was put back, as in Stage 1. Backups in the case:
  `field_1831_pre_e.npz`, `forces_1831_pre_e.json`, `export_field_pre_e.py`.
  The Q3 figures (46 of 15000 deletions, drift) predate this mask; Stage 4 re-records them.
- Stage 3 pure (commit 1107faa): `wind_tunnel/anim.py` with `cp_to_ramp`, `CP_STOPS`
  (linear) and `CP_STOPS_SRGB`, `sweep_half_range`, `sweep_keyframes`, `slice_keep`, `label_text`
  (float32 like the nodes, so 0.85 / 2 prints +0.43), `legend_ticks`; tests `AnimPure`.
- Stage 3 Blender (commit 1e49285):
  - `write_vdb` adds grid `fluid` (1 fluid, 0 solid, background 0 outside the grid).
  - WT Slice: inputs Pressure, Cp Lo (-1), Cp Hi (+1). Ramp coordinate `show` = speed over
    0.3..1.9 or two clamped Map Range nodes summed (Cp 0 -> 0.5). Two materials, `WT Slice` (speed
    stops) and `WT Slice Cp` (9 Moreland stops), switched by Pressure (choice: two materials, the
    simpler one). Stores `show`, `cp`, `speed`. Clip: a vertex is kept only when the trilinear
    `fluid` value >= 0.999 (all 8 corners fluid and inside the grid). So the slice ends at the grid
    edge (closes open item b) and about one voxel (5 cm) off every body face, the same on all six
    faces; no colour is blended with the zeroed solid nodes. A loose vertex carries `cp_lo`,
    `cp_hi`, `pressure` for the overlays.
  - WT Legend (strip 2 L long, 257 x 2 vertices, at z = grid top + 0.2 L in the XZ plane through
    the body centre, facing -Y, ticks below) and WT Label (above it, "Slice y = +0.85 m (+0.43 L) |
    Cp") read those attributes through Object Info + Attribute Statistic, so they cannot disagree
    with the slice. Text: String to Curves + Format String (fmt syntax), material `WT Text`.
  - Panel (3D result box): Sweep X/Y/Z, "Animate slice", "Clear". `viz3d.animate_slice` writes one
    location key per frame (LINEAR), replaces old keys, rotates the plane for X / Z
    (`SWEEP_ROTATION`), sets frames 1..192 and the label's Axis.
  - Smoke: slide and push back only when Use Field is off (one Boolean NOT on Use Field). Preview
    slide band on Proximity Distance < 0.05 L, direction unit(P - nearest) (Q4). Push back unchanged.
    The audit script's unique values 0.05, 0.004, 0.02 are kept.
  - `_ramp` builds ColorRamp elements in order (Blender re-sorts); `_set_input` calls
    `mod.id_data.update_tag()` (without it a second input change was not re-evaluated).
  - Headless `tools/blender_smoke.py` (all pass): ramp read back = CP_STOPS; Cp mode materials
    slice [WT Slice Cp], legend [WT Slice Cp, WT Text]; kept vertices 39464 = `anim.slice_keep`;
    sampled Cp error 6.0e-8 on a linear Cp field (node placement exact); 17 label and tick strings
    equal the pure text; sweep y at frames 1/49/97/145/192 = -2.0/0/+2.0/0/-1.958333, 3 x 192 keys
    after a repeat, Clear restores rest; smoke one step: solved A, B, C all +0.0667 m in x (no slide,
    no push back); preview A (3 cm in front of the face) stops in x, B (-1.066, -1.467, -0.25) keeps
    +0.0667 (Q4), C (1 mm inside) ends at x = -1.008.

### Open issues carried
- a and b: fixed in Stage 3 (diverging Cp material; fluid-grid clip); confirm visually in Stage 4.
- c (step 1 review): inlet non-uniformity, stagnation line enters about 1.031 q; FIX_PLAN step 4.
- d: fixed for preview per Q4; concave-edge limit of the push back recorded, not solved.
- f (new, minor): the add-on's depsgraph handler hides WT Slice, WT Legend and WT Label unless the
  loaded field is the Test Object's solved one. Correct behaviour, but a tracer that calls viz3d
  directly sees nothing; use the load path below.
- g (new, minor): WT Legend and WT Label face -Y, placed for the default Y sweep camera; for X and Z
  sweeps they stay in place (not turned).

### NEXT PROMPT (ANIMATION A+B, Stage 4 tracer, then HIL stop)
Slice: ANIMATION A+B. Same structure: fresh session, bounded context, tracer on copies only, HIL
visual QA, then (after Bilal's rounds) Stage 5 close and Stage 6 handoff. Token budget per CLAUDE.md
(no new heavy stage after about 150k, hand off at about 200k, never compact). The grill is finished.

CONTEXT TO LOAD (nothing else):
- CLAUDE.md; this SESSION_LOG.md; `docs/reference/anim_ab_spec.md`.
- `sed -n 31,42p docs/prompts/anim_ab.md` (STAGE 4 to STAGE 6).
- `wind_tunnel/anim.py` (short). In `wind_tunnel/viz3d.py` only the names `build_slice`,
  `build_legend`, `animate_slice`, `build_smoke`, `tune_smoke`, `write_vdb`, `load_volume` (grep).
- `tools/blender_smoke.py` functions `_points` and `_smoke_steps` (how to read evaluated geometry).
- `tools/audit/anim_q3_drift.py` and `tools/audit/anim_q3_smoke.py` heads, to reuse for drift and
  the inside count.
- `wind_tunnel/__init__.py`: `WT_OT_load3d.execute` and `load_cached` only (grep).

Facts established, do not re-derive:
- Grid x -2.5 to 6.0 m, y and z +-2.5 m, h 0.05 m (171 x 101 x 101); cube -1 to 1 m, L = 2 m.
  `_anim/Cube` field.npz at t = 1831 with the fixed mask, sha1 5868c18e; forces.json sha1 77061b3d.
- Smoke: 24 fps, Time Scale 0.08, step 0.0667 m = 1.33 voxels per frame, about 150 particles per
  frame, Sample Grid Trilinear (default). Sweep Y: +-2.0 m, 192 frames, frame 97 at +2.0.
- Blender 5.2: read node-set materials from `ob.evaluated_get(dg).data`, not `to_mesh()`;
  Join Geometry puts the loose vertex last; modifier input changes need `update_tag()` (done in
  `_set_input`). Toggling the add-on does not reload modules: restart Blender or reload via the MCP.
- Windows Python reading `\\wsl.localhost` paths hung; copy with `wsl cp` to `/mnt/c/...` first.
  In Git Bash never leave a bare `cat > file` without a heredoc; long inline heredocs with nested
  quotes failed once, so write long patch scripts to the scratchpad first.

Stage 4 work (prompt lines 31 to 38 are the contract):
1. Load path: make a light copy `~/wind_tunnel/3d_AnimCube` with only `field.npz`, `forces.json`,
   `status` from `_anim/Cube` (no processor dirs). In Bilal's live Blender through the MCP: new scene
   "WT_ANIM" (`bpy.data.scenes.new`, never File > New, never touch his other scenes), a 2 m cube
   named "AnimCube" at the origin, then the add-on's load3d path so the handler shows the slice
   (open issue f). Scene colour settings per spec Q2: view transform Standard, look None, exposure 0,
   gamma 1, no bloom.
2. Press Animate slice (Y), play 1..192. Record in `validation/anim_ab_v2512.json` (date, mesh
   359618 cells, t = 1831): Cp at 3 probe points read from the slice's `cp` attribute vs trilinear
   field.npz within 1e-4; particles inside AnimCube (|x|, |y|, |z| < 1 m) over the whole animation,
   target 0, with the solid-mask count next to it (not gated); smoke vs RK4 drift over 1 L (max and
   mean, voxels) re-measured with the fixed mask; legend pixel colours at the 9 stops vs
   `anim.CP_STOPS_SRGB` within +-2/255 from a Standard-view render.
3. Render EEVEE, 1280 x 720, about 8 s, FFMPEG, to `renders/anim_ab_cube.mp4`; add `renders/` to
   `.gitignore`. Tell Bilal up front that the slice stops about one voxel (5 cm) off the body on
   every face, by design (no colour blended with solid nodes).
4. STOP (HIL): tell Bilal where the MP4 is and what to look at in the live viewport. Up to 3 rounds
   of small changes, re-render, stop again. Then Stage 5 and Stage 6 per the prompt; the Stage 6
   REVIEWER PROMPT must also check the issue e fix (`SolidMask`, `anim_ab_mask_e.json`).

RULES: no sudo. No em dashes. Asterisk technical terms and add a glossary. Never call a result
validated without a cited reference value. Keep SESSION_LOG.md to current state plus NEXT prompt;
move superseded entries verbatim to `docs/archive/`.

## 2026-10-22: ANIMATION A+B closed (Stage 4 tracer, HIL, Stage 5, Stage 6), add-on 0.5.0

### Done
- Stage 4 tracer (commit 30c0e9b, record `validation/anim_ab_v2512.json`). Light copy
  `~/wind_tunnel/3d_AnimCube` (field.npz sha1 5868c18e, forces.json, status); in Bilal's live Blender a
  new scene WT_ANIM (Standard view, look None, exposure 0, gamma 1), 2 m cube "AnimCube", loaded through
  `wind_tunnel.load3d` (issue f), Pressure on, Animate slice (Y): y = -2 / 0 / +2 / 0 / -1.958 m at
  frames 1 / 49 / 97 / 145 / 192.
- Numbers (mesh 359618 cells, t = 1831):

| Check | Result | Target |
|---|---|---|
| Slice cp vs trilinear field.npz p/q, 3 probes (frames 49, 61, 85) | max 1.9e-8 | 1e-4 |
| Particles inside the cube, frames 1..192, 2477893 particle-frames | 0 (closest 0.73 mm) | 0 |
| Solid-mask nearest-node hits (not gated) | 11518 particle-frames, all within 0.025 m outside the wall | reported |
| Smoke vs RK4 drift over 1 L, near body (2206 paths) | max 0.0558, mean 0.0024 voxel | recorded |
| Same, freestream (794 paths) | max 0.0077, mean 0.0011 voxel | recorded |
| Headless 100 frames, still rule off, 15000 released | 0 enter the cube box (old mask: 1) | recorded |
| Legend pixels at the 9 stops vs `anim.CP_STOPS_SRGB` | worst 1/255 | +-2/255 |

  The probe Cp 1.019 at the front stagnation point is open issue c, not a slice error.
- MP4 `renders/anim_ab_cube.mp4` (EEVEE, 1280 x 720, 192 frames, H264; `renders/` ignored).
- HIL (Bilal): no visual changes to the sweep. He wants a fixed plane with the flow developing in
  time, which needs a transient solve: new slice TRANSIENT T1 (prompt `docs/prompts/transient_t1.md`).
- Stage 5 (commit 8c3bebf): tests 80 run OK (3 expected failures), deployed, headless smoke check
  ok (version 0.5.0, cp_err_max 6.0e-8, kept 39464 = pure), version 0.5.0 in both places, README
  "Animating the result" (steady flow stated). Cp wording fixed: CLAUDE.md said the Cp reference was
  the outlet; it is p_inf = area-weighted mean static p on the inlet patch (FIX_PLAN step 1). The
  `p_inf_Cp_vs_outlet` key in forces.json is p_inf expressed against the outlet and is correct as named.
  WT_ANIM and every datablock it created (8 objects, 5 meshes, 5 materials, 4 node groups, volume,
  camera, light, world, font, action) removed through the MCP after checking Bilal's "Scene" (Camera,
  Cube, Light, transforms, AgX, frames 1..250) was unchanged; `~/wind_tunnel/3d_AnimCube` deleted.
  The live Blender has the 0.5.0 modules loaded (reloaded through the MCP).

### Grill decisions (locked, `docs/reference/anim_ab_spec.md`)
Q1 sweep Y default, +-1 L, 192 frames ping-pong, keyframes on location only; Q2 diverging Moreland
ramp, Cp -1..+1 two-sided around Cp 0, legend and label in Geometry Nodes; Q3 solved mode no slide,
still rule kept, inside count gated on the body box; Q4 preview slide on true distance.

### Open issues
- c (step 1 review): inlet non-uniformity, stagnation line enters about 1.031 q; FIX_PLAN step 4.
- d: concave-edge limit of the preview push back, recorded, not solved.
- f: handler hides slice, legend and label unless the field is the Test Object's (by design; tracers
  use the load path).
- g: WT Legend and WT Label face -Y; for X and Z sweeps they are not turned. Open, not fixed.
- h (new, Bilal): section view, hide the body and the smoke on the camera side of the slice.
- i (new, Bilal): smoke styling, plain white, fewer particles, short trails, so Cp is the only colour code.
- h and i are Q4 of the TRANSIENT T1 grill.
- `~/wind_tunnel/_anim` can be deleted once the ANIMATION A+B review passes.

### REVIEWER PROMPT (ANIMATION A+B review, fresh session)
Slice: review of ANIMATION A+B (commits 6a8295f, 1107faa, 1e49285, 30c0e9b, 8c3bebf). Read-only
except the report. Save the report to `docs/reviews/anim_ab_review.md` with one PASS / FAIL line per
item and the evidence (command, number, file:line).

CONTEXT TO LOAD: CLAUDE.md; this SESSION_LOG.md; `docs/reference/anim_ab_spec.md`;
`docs/prompts/anim_ab.md` lines 31 to 42; `wind_tunnel/anim.py`; in `wind_tunnel/viz3d.py` only
`write_vdb`, `build_slice`, `build_legend`, `animate_slice`, `build_smoke` (grep); `tests/test_pure.py`
classes `AnimPure` and `SolidMask`; `validation/anim_ab_v2512.json`, `validation/anim_ab_mask_e.json`.
Facts established, do not re-derive: the numbers table above; the solve is steady.

Push on:
1. Only solved data shown: no frame interpolates or invents field values (keyframes move the plane only).
2. Slice values equal field.npz: re-run one probe yourself headless (synthetic or the _anim/Cube
   field copied to /mnt/c first; Windows Python hangs on `\\wsl.localhost`).
3. Smoke never enters the solid: check the counting method (instance_transform, frames in order) and
   that solved mode has no slide (one NOT on Use Field).
4. Diverging ramp centred on Cp = 0 for asymmetric lo/hi too (`cp_to_ramp`), stops equal the spec table,
   Moreland 2009 endpoints cited.
5. Issue e fix: `SolidMask` tests (41^3 = 68921, mirror symmetric, cube at +-0.97 gives 39^3) and
   `anim_ab_mask_e.json` (forces.json byte-identical, only the 4921 added nodes changed).
6. Pure functions tested before Blender code; tests green (`py -m unittest discover -s tests -v`).
7. Cp wording: no file outside `docs/archive` and `docs/reviews` says the Cp reference is the outlet.
8. Version 0.5.0 in `blender_manifest.toml` and `bl_info`; README section honest that the flow is steady.
9. No em dashes in files changed by these commits; LF line endings; cited numbers only.
RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference.

### NEXT PROMPT (TRANSIENT T1)
Run `docs/prompts/transient_t1.md` (structure as `docs/prompts/anim_ab.md`). Stage 0 gate:
`docs/reviews/anim_ab_review.md` with no open FAIL. Load only what that prompt lists and take its
"facts already established" as given. Token budget per CLAUDE.md. One line: pimpleFoam time-resolved
solve of the cube, fixed WT Slice at y = 0 showing Cp per frame from a VDB sequence, smoke advected
through the time-varying field, label with physical time and t U/L.

### LATER PROMPT (FIX_PLAN step 3, wall mesh and y+; run after TRANSIENT T1 unless Bilal says otherwise)
Slice: FIX_PLAN step 3, wall treatment and surface resolution. Solver-side (case3d), so every
number is checked against OpenFOAM's definitions and a cited reference, and recorded in
`validation/` with date, mesh size and iteration count. Write the full prompt to
`docs/prompts/step3_wall.md` in the structure of `docs/prompts/anim_ab.md` as the first act.

STAGE 0 GATE: the previous slice's review in `docs/reviews/` has no open FAIL.
CONTEXT TO LOAD: CLAUDE.md; SESSION_LOG.md current entry; `docs/FIX_PLAN.md` step 3;
`docs/ACCURACY_AUDIT.md` (wall treatment and y+ findings only); `docs/reference/step2_convergence_reference.md`
(the gate); in `wind_tunnel/case3d.py` the snappyHexMeshDict writer (addLayersControls,
refinementSurfaces, features) and `case.Setup.first_cell` (grep).
Facts established, do not re-derive: v2512 function objects work (`yPlus`, `forces`, `forceCoeffs`;
`tools/audit/step0_check.py`); a run is solved only when the step 2 gate passes; Cp uses the inlet p_inf.
Acceptance (FIX_PLAN): y+ in 30 to 300 on at least 80 % of the area for sphere, cube and cone; layer
coverage at least 90 %; y+ min/mean/max and the in-band area fraction written to forces.json; panel
warning under 80 %.
GRILL (HIL, one question at a time, recommendation first): target y+ and first-layer formula
(flat-plate Cf on L, cite the correlation), layer count and expansion, `relativeSizes false` vs true
with snappy's fallback, curvature or distance refinement to reach about 100 cells around a sphere,
which of the solved cases to re-run (copies only) and the cost.
Then TDD (case text tests first), tracer on copies (`~/wind_tunnel/_step3`), Stage 5 close
(version bump, commit with the physical quantity changed and by how much), Stage 6 handoff with a
REVIEWER PROMPT to `docs/reviews/step3_review.md`.
RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference.

## 2026-10-23: TRANSIENT T1 Stages 0 to 2 done (gate, verify, grill), stopped before Stage 3 (token budget)

### Done
- Stage 0 (commit 661bbbd): `docs/reviews/anim_ab_review.md` has 9 PASS, 0 FAIL. Review O1 closed:
  the particles-inside-cube count is committed as `tools/audit/anim_inside.py` (headless Blender,
  `FIELD.npz FRAMES [OUT.json]`); recount on field.npz sha1 5868c18e reproduces 2477893
  particle-frames, 0 inside, 19571 alive max. `validation/anim_ab_v2512.json` now states that the
  recorded 0.73 mm is the per-axis (Chebyshev) gap, not the straight-line distance (0.98 mm).
- Stage 1: tests 80 run OK (3 expected failures); Blender MCP reachable (5.2.0 LTS, only "Scene");
  add-on 0.5.0 in the repo, the deployed copy and the live Blender.
- Stage 2 grill, locked in `docs/reference/transient_t1_spec.md` (commits af68d4c, 24c5ebb):

| Q | Decision |
|---|---|
| Q1 start | impulsive start from the potentialFoam field (exact t = 0+ solution), k 0.06, omega 400 uniform; mesh copied from `_anim/Cube` (359618 cells), no re-mesh |
| Q2 time | 2 s (20 L/U), 120 frames at 1/60 s, frame k at t = k/60 s, t U/L = k/6; 5 s video at 24 fps |
| Q2 St reference | none found for a free-stream cube near Re 2.7e6; nearest Klotz et al. 2014 JFM 750, St 0.125 at Re <= 390 (other regime) |
| Q3 solver | pimpleFoam SST, backward, maxCo 1, 1 outer / 2 correctors, steady spatial schemes, writeObjects U p every 1/60 s, full write every 0.5 s, forceCoeffs every step |
| Q3 cost (measured) | A (chosen) 0.48 s/step, dt 6.5e-4 s, about 3070 steps, about 25 min; B (Co 4, 3 outer) 0.94 s/step, about 13 min |
| Q4 gates | Cd mean 1.0 to 2.0 s vs steady 1.1498 (report); St vs Klotz or "not measurable" (report); continuity error <= 1e-6 every frame (FAIL); 0 particles inside (FAIL) |
| Q5 | issue i (white smoke, fewer particles, short trails) in T1; issue h deferred |

- Cost test cases: `~/wind_tunnel/_t1/cost_A`, `cost_B` (390 MB, 25 steps each, deletable).
  Script `tools/audit/t1_costtest.sh` holds the exact controlDict, fvSchemes edits and fvSolution
  used; the Stage 3 case writer should reproduce them. Early-transient numbers seen (not results):
  Cd 1.78 at t = 0.015 s (A), 1.45 at t = 0.058 s (B), the impulsive-start transient.

### Open issues
- c (step 1 review): inlet non-uniformity, stagnation line enters about 1.031 q; FIX_PLAN step 4.
- d: concave-edge limit of the preview push back, recorded, not solved.
- f: handler hides slice, legend and label unless the field is the Test Object's (by design).
- g: WT Legend and WT Label face -Y; for X and Z sweeps they are not turned.
- h: section view (hide body and smoke on the camera side of the slice), deferred by Q5.
- Review O2 (logged, open): the 7 intermediate Cp ramp stops are our Msh interpolation, not yet
  compared with Moreland's published CoolWarm table.
- Review O3 (logged, process): commit the red test separately from the fix when practical.
- `~/wind_tunnel/_anim` must stay until T1 closes (T1 copies its mesh; Cd compares on the same mesh).

### NEXT PROMPT (TRANSIENT T1, Stage 3 onward, fresh session)
Continue `docs/prompts/transient_t1.md` from STAGE 3. Stages 0 to 2 are done; do not redo them.
CONTEXT TO LOAD: CLAUDE.md; this SESSION_LOG.md entry; `docs/reference/transient_t1_spec.md` (the
locked answers, take as given); `tools/audit/t1_costtest.sh` (the dictionaries that ran);
`tools/audit/anim_inside.py`; then only the functions you change (grep): in `wind_tunnel/case3d.py`
the controlDict, fvSchemes, fvSolution writers and the Allrun builder; `wind_tunnel/export_field.py`
(frame export, solid mask once); `wind_tunnel/anim.py`; in `wind_tunnel/viz3d.py` `write_vdb`,
`load_volume`, `build_slice`, `build_smoke`, `build_label`/label tree.
Facts established: the table above; v2512 `postProcessing/forceCoeffs/0/coefficient.dat` columns are Time, Cd, Cd(f), Cd(r), Cl, Cl(f), Cl(r), CmPitch, CmRoll, CmYaw, Cs, Cs(f), Cs(r) (liftDir +Z, dragDir +X), so read the Q4 signals by header name, not position; v2512 function objects with adjustableRunTime shorten deltaT
to hit their write times; mpirun needs `--oversubscribe` for 24 ranks (as case3d does).
STAGE 3 TDD (red commit, then green): pure transient case writer per the spec; frame index to
physical time mapping (t = k/60 s, t U/L = k/6); VDB sequence naming and loading; issue i smoke
inputs; headless Blender check that the slice samples the frame-matching VDB.
STAGE 4: re-run the 20-step cost test with the Stage 3 writer and STOP with the estimate before the
full run (Bilal approves anything over 30 min); full run in `~/wind_tunnel/_t1/Cube`; parallel frame
export (16 to 24 processes, solid mask once); scene WT_T1 through the MCP (fixed WT Slice y = 0 in
Cp mode, smoke through the time-varying field, label with t and t U/L), render
`renders/transient_t1_cube.mp4`; one HIL round. Stages 5 and 6 as the prompt says (version 0.6.0,
README "Time-resolved flow", REVIEWER PROMPT to `docs/reviews/transient_t1_review.md`, NEXT PROMPT
= the LATER PROMPT below).
RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference.

### LATER PROMPT (FIX_PLAN step 3, wall mesh and y+; run after TRANSIENT T1 unless Bilal says otherwise)
Slice: FIX_PLAN step 3, wall treatment and surface resolution. Solver-side (case3d), so every
number is checked against OpenFOAM's definitions and a cited reference, and recorded in
`validation/` with date, mesh size and iteration count. Write the full prompt to
`docs/prompts/step3_wall.md` in the structure of `docs/prompts/anim_ab.md` as the first act.

STAGE 0 GATE: the previous slice's review in `docs/reviews/` has no open FAIL.
CONTEXT TO LOAD: CLAUDE.md; SESSION_LOG.md current entry; `docs/FIX_PLAN.md` step 3;
`docs/ACCURACY_AUDIT.md` (wall treatment and y+ findings only); `docs/reference/step2_convergence_reference.md`
(the gate); in `wind_tunnel/case3d.py` the snappyHexMeshDict writer (addLayersControls,
refinementSurfaces, features) and `case.Setup.first_cell` (grep).
Facts established, do not re-derive: v2512 function objects work (`yPlus`, `forces`, `forceCoeffs`;
`tools/audit/step0_check.py`); a run is solved only when the step 2 gate passes; Cp uses the inlet p_inf.
Acceptance (FIX_PLAN): y+ in 30 to 300 on at least 80 % of the area for sphere, cube and cone; layer
coverage at least 90 %; y+ min/mean/max and the in-band area fraction written to forces.json; panel
warning under 80 %.
GRILL (HIL, one question at a time, recommendation first): target y+ and first-layer formula
(flat-plate Cf on L, cite the correlation), layer count and expansion, `relativeSizes false` vs true
with snappy's fallback, curvature or distance refinement to reach about 100 cells around a sphere,
which of the solved cases to re-run (copies only) and the cost.
Then TDD (case text tests first), tracer on copies (`~/wind_tunnel/_step3`), Stage 5 close
(version bump, commit with the physical quantity changed and by how much), Stage 6 handoff with a
REVIEWER PROMPT to `docs/reviews/step3_review.md`.
RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference.
