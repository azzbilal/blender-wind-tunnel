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

## 2026-10-24: TRANSIENT T1 closed (Stages 3 to 6), add-on 0.6.0

### Done
- Stage 3 TDD (red b2eea87, green 294d226 and 598c4e1): `case3d.write_transient_case` (pimpleFoam per
  the spec, potentialFoam start on a fresh copy only, ASCII writes); new pure `wind_tunnel/transient.py`
  (frame k at t = k/60 s matched by time with tolerance, VDB sequence, plain smoke inputs, continuity /
  Cd window / St maths); `export_field.py --frames` (U and p gathered from `processor*/<t>` through
  `cellProcAddressing`, no reconstructPar; mask and IDW weights once; forked pool); `viz3d`: VDB
  sequence load (the original volume is unloaded, a load on it looks for flow_0000), plain smoke with a
  Substeps repeat zone and streaks, label with t and t U/L, `build_transient`. Headless
  `tools/audit/t1_frames_check.py` passes. Bilal's addition 1: 50-step parallel potentialFoam start clean.
- Stage 4 (632e56f to 428767d): full run `~/wind_tunnel/_t1/Cube`, record `validation/transient_t1_v2512.json`:

| Quantity | Result |
|---|---|
| Run | 2564 steps, solve 1346 s (22.4 min), dt 6.3e-4 to 8.3e-4 s, Courant max 1.24 after step 1 |
| Gate 3 continuity, 120 frames | max 1.95e-12 (frame 45), limit 1e-6: PASS |
| Gate 4 particles (shipped render: sheet, 12 fps) | 130934 particle-frames, 0 inside, closest 1.15 mm: PASS |
| Gate 1 Cd mean 1 to 2 s / 0.5 to 1 s | 1.1243 / 0.9208; steady 1.1498 same mesh (-2.2 %); Cd(2 s) 1.127 |
| Gate 2 St | not measurable: Cs, Cl oscillate to 0.07 at 1.0 to 1.6 s then decay below 0.008 (no sustained shedding) |
| Cp min/max, frames 1 / 12 / 45 / 120 | -4.24/+1.159, -2.11/+1.023, -1.39/+1.016, -0.73/+1.026 (steady -0.68/+1.024) |

- HIL round (Bilal): thin charcoal streaks, release sheet |y| <= 0.05 L, 12 fps (10 s video, 1/60 s of
  flow per frame). MP4 `renders/transient_t1_cube.mp4`, frames and VDBs in `renders/t1_frames` (ignored).
- Stage 5 (aa121a3): 0.6.0 in both places, README "Time-resolved flow", tests 104 OK (3 expected
  failures), deployed, headless smoke check ok; WT_T1 and every WT datablock removed from the live
  Blender after checking Bilal's "Scene" unchanged; add-on handler restored, 0.6.0 loaded live.
- Steady export regression (CLAUDE.md rule for export_field changes): the refactored exporter on a scratch
  copy of `_anim/Cube` t = 1831 gives a bit-identical `field.npz` (all 7 keys) and a `forces.json` equal to
  `forces_1831e_verdict2000.json` on all 35 keys (same history to 2000); scratch deleted.

### Decisions and deviations (all in `docs/reference/transient_t1_spec.md`, Stage 3 and 4 notes)
- ASCII writes instead of binary (reuses the tested readers). Field held at frame k through the smoke
  step k-1 to k. The St gate needs a sustained oscillation (last 0.25 s spread >= 25 % of the window's);
  the period count alone said "measured" for a decaying transient. Early-frame Cp explained by the
  impulsive start and confirmed by its relaxation (Bilal's note).

### Open issues
- c, d, g, h as before (inlet non-uniformity; preview push back at concave edges; legend and label
  face -Y; section view).
- f, extended: the add-on has no load path for a time-resolved field; WT_T1 needs the Test Object
  handler suspended (`tools/audit/t1_scene.py`). Panel integration is a later slice.
- j (new): URANS on this mesh does not sustain shedding; whether a finer mesh or DES would is untested.
- Review O2 (Moreland intermediates) still open.
- Disk: `~/wind_tunnel/_t1/Cube` 5.4 GB and `~/wind_tunnel/_anim` stay until the T1 review passes;
  `renders/t1_frames` (2.7 GB plus VDBs) is local scratch, regenerable.

### REVIEWER PROMPT (fresh session; report to `docs/reviews/transient_t1_review.md`)
Review slice TRANSIENT T1 (commits b2eea87..aa121a3 plus the handoff). Read only CLAUDE.md, this entry,
`docs/reference/transient_t1_spec.md`, `docs/prompts/transient_t1.md` and the code you check.
Facts established, do not re-derive: the table above; v2512 forceCoeffs columns by header name; writeObjects
with adjustableRunTime lands writes on frame times; Blender volume sequence: scene frame k loads file k with
frame_start 1, offset 0.
Check, each PASS/FAIL with evidence:
1. The case text matches spec Q3 (`case3d.transient_*`; `~/wind_tunnel/_t1/Cube/system`), the only
   intended differences from the steady schemes are backward and no `bounded`.
2. Gate 3: re-parse `~/wind_tunnel/_t1/Cube/log.pimpleFoam` independently of `transient.py` and confirm
   120 frames, max 1.95e-12.
3. Gate 1: recompute the 1 to 2 s Cd mean from `postProcessing/forceCoeffs/0/coefficient.dat` with your own
   trapezoid code (expect 1.1243).
4. Gate 2: plot or tabulate Cs and Cl over 0.5 to 2 s and judge whether "no sustained shedding" is right;
   check the tail-spread rule in `tools/audit/t1_gates.py` is stated in the spec.
5. Frame export: for one frame, compare a few voxels of `frames/flow_0060.npz` with an IDW you compute from
   a `reconstructPar -time` of that frame (on a copy), within 1e-6 relative.
6. Gate 4: re-run `tools/audit/anim_inside.py -- renders/t1_frames 120` (12 fps): 0 inside.
7. `tools/audit/t1_frames_check.py` and `tools/blender_smoke.py` pass headless; tests 104 OK.
8. README "Time-resolved flow" claims nothing beyond the record (no "validated", no St).
9. Bilal's live Blender was left with only his own data (ask him; do not open his scenes).
RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference.

### NEXT PROMPT (FIX_PLAN step 3, wall mesh and y+; after the T1 review has no open FAIL)
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

## 2026-10-24: T1 polish, smoke streaks visible, add-on 0.6.1 (commit ed49139)

### Done
- Problem (Bilal): in `renders/transient_t1_cube.mp4` (0.6.0) the streaks showed only at the release.
- Root cause found by the red check, not the one in the brief: an unbaked Simulation Zone advances only
  when frames are played in order and a render only reads that cache. `t1_scene.render()` rendered
  without playing, so every frame showed only the particles born in it (gate 4 was unaffected: it plays
  frames in order). Fix: `t1_scene.play()` runs frames 1..120 before any render. Second, smaller cause
  (the brief's): radius L/600 drew 0.8 px wide streaks.
- Red: new `tools/audit/t1_visibility.py` (headless). Threshold over >= 400 px, wake >= 1000 px at
  frames 30, 60, 120 (about 2 and 5 full streaks). Classifier sRGB max <= 80, max - min <= 16.
- Green: `transient.plain_smoke_inputs` radius L/160 (12.5 mm, 3.0 px at 8.44 mm/px for the T1 camera:
  15 m, 50 mm lens, 36 mm sensor, 1280 px), trail 0.3 L at U_inf, 60 a frame. Sheet, integration,
  colour, Time Scale, Substeps, Lifetime unchanged.

| Visibility (over / wake px) | Frame 30 | Frame 60 | Frame 120 | Verdict |
|---|---|---|---|---|
| 0.6.0 as shipped | 0 / 0 | 0 / 0 | 0 / 0 | FAIL |
| 0.6.0 streaks, frames played | 0 / 2 | 3 / 0 | 0 / 0 | FAIL |
| trial 40 a frame | 11800 / 3751 | 12353 / 2523 | 10061 / 3798 | PASS, sparse |
| trial 120 a frame | 25692 / 12278 | 25527 / 7546 | 20879 / 9495 | PASS, rejected (bands hide Cp) |
| **0.6.1 shipped (60 a frame)** | 17033 / 5973 | 17479 / 3670 | 13376 / 5452 | **PASS** |
| no-smoke baseline, every run | 0 / 0 | 0 / 0 | 0 / 0 | |

- Gate 4 re-run (12 fps, shipped inputs): 196334 particle-frames, 0 inside, closest centre 1.15 mm
  (Chebyshev 0.99 mm), max alive 2064: PASS.
- Video re-rendered live (WT_T1 via `t1_scene.py`, handler paused, 46 s), stills
  `renders/t1_still_030/060/120.png`; Bilal's OK given. WT_T1 removed, his "Scene" compared identical to
  the snapshot (objects, transforms, frame, camera, render settings, every add-on property); no WT or
  T1 datablocks left; handler and timer on; 0.6.1 loaded live.
- Auto solve guard (Bilal): the add-on finds WT Smoke by global name but reads Auto solve from the
  current scene, so any scene with it on could solve T1Cube (this produced the unrequested
  `~/wind_tunnel/3d_T1Cube`, 2026-10-24 00:55 to 01:04, 298 MB, now deleted; its leftover WT_T1 was
  still in the live Blender at the start of this session and was removed). `t1_scene.build()` now
  switches Auto solve off on every scene (values kept in `bpy.app.driver_namespace`, never in the
  .blend) and `cleanup()` restores them before the handler. `tools/audit/t1_autosolve_check.py` passes.
- Records: `validation/transient_t1_v2512.json` (`gate4_particles` 0.6.1, old kept as
  `gate4_particles_0_6_0`, new `visibility_0_6_1`), spec "0.6.1 polish" note, README "Time-resolved
  flow", `tools/audit/README.md` (two new scripts). Tests 103 OK (3 expected failures; the 0.6.0 entry's
  "104" was a miscount, HEAD had 103), deployed, headless smoke check and `t1_frames_check.py` ok.
  Stale `renders/t1_still_012.png` (white-streak round) deleted.

### T1 results (unchanged by this polish, from the 0.6.0 entry)

| Quantity | Result |
|---|---|
| Run | 2564 steps, solve 1346 s (22.4 min), dt 6.3e-4 to 8.3e-4 s, Courant max 1.24 after step 1 |
| Gate 3 continuity, 120 frames | max 1.95e-12 (frame 45), limit 1e-6: PASS |
| Gate 4 particles (0.6.1 render: sheet, 12 fps, 60 a frame) | 196334 particle-frames, 0 inside, closest 1.15 mm: PASS |
| Gate 1 Cd mean 1 to 2 s / 0.5 to 1 s | 1.1243 / 0.9208; steady 1.1498 same mesh (-2.2 %); Cd(2 s) 1.127 |
| Gate 2 St | not measurable: Cs, Cl oscillate to 0.07 at 1.0 to 1.6 s then decay below 0.008 (no sustained shedding) |
| Cp min/max, frames 1 / 12 / 45 / 120 | -4.24/+1.159, -2.11/+1.023, -1.39/+1.016, -0.73/+1.026 (steady -0.68/+1.024) |

### Decisions
- 60 a frame chosen between the 40 and 120 trials by eye (Bilal OK on the stills and video).
- The visibility check renders through `t1_scene.build()` and `play()`, so it tests the real render path.
- "Over the cube" means above and below it in this view: with the +-0.05 L sheet no streak passes in
  front of the -Y face.

### Open issues
- k (new, known display limit): gate 4 tests particle centres; a 12.5 mm streak drawn 1.15 mm from the
  top face reaches up to about 11 mm into the cube (`streak_overlap_max_m` 0.01135 in the record). The
  -Y face hides it from the T1 camera; another view would show it.
- T1 review O1 (cell centres = mean of face centres, up to 1.2 % in |U|) moved to FIX_PLAN step 6.
- T1 review O2 (open): `visibility_0_6_1.red_0_6_0_streaks_with_play_through` stores the pixel counts
  but not the inputs; add OVERRIDES `{"Radius": 0.00333, "Trail": 0.01, "Rate": 71.43}` to that entry.
- T1 review O3 (open): "no sustained shedding" is shown for t <= 2 s only; the spec's "tends to the
  steady state" extrapolates beyond the run. The tail rule's "spread" is the unweighted sample standard
  deviation over time steps; the spec should name that statistic.
- The recirculation bubble behind the cube is nearly empty of streaks by t = 2 s: upstream particles
  follow the shear layers. That is the flow, not a rendering fault; seeding inside the bubble is a
  styling question for a later slice.
- c, d, g, h as before (inlet non-uniformity; preview push back at concave edges; legend and label
  face -Y; section view).
- f, extended: the add-on has no load path for a time-resolved field; WT_T1 needs the Test Object
  handler suspended and Auto solve off (`tools/audit/t1_scene.py`). Panel integration is a later slice.
- j: URANS on this mesh does not sustain shedding; whether a finer mesh or DES would is untested.
- ANIMATION A+B review O2 (Moreland intermediates) still open.
- Disk: T1 review closed (item 10 fixed 2026-10-24); `~/wind_tunnel/_review_t1` and `~/wind_tunnel/_anim`
  deleted, `~/wind_tunnel/_t1/Cube` (5.4 GB) kept. `renders/t1_frames` (2.7 GB plus VDBs) is local
  scratch, regenerable.

### REVIEWER PROMPT (fresh session; report to `docs/reviews/transient_t1_review.md`)
Review slice TRANSIENT T1 including the 0.6.1 polish (commits b2eea87..aa121a3, 7cf7d8f, ed49139 and
the handoffs). Read only CLAUDE.md, this entry, `docs/reference/transient_t1_spec.md`,
`docs/prompts/transient_t1.md` and the code you check.
STAGE 0 GATE: none (this is the review).
Facts established, do not re-derive: the two tables above; v2512 forceCoeffs columns by header name;
writeObjects with adjustableRunTime lands writes on frame times; Blender volume sequence: scene frame k
loads file k with frame_start 1, offset 0; an unbaked Simulation Zone must be played in order before a
render reads it.
Check, each PASS/FAIL with evidence:
1. The case text matches spec Q3 (`case3d.transient_*`; `~/wind_tunnel/_t1/Cube/system`), the only
   intended differences from the steady schemes are backward and no `bounded`.
2. Gate 3: re-parse `~/wind_tunnel/_t1/Cube/log.pimpleFoam` independently of `transient.py` and confirm
   120 frames, max 1.95e-12.
3. Gate 1: recompute the 1 to 2 s Cd mean from `postProcessing/forceCoeffs/0/coefficient.dat` with your own
   trapezoid code (expect 1.1243).
4. Gate 2: plot or tabulate Cs and Cl over 0.5 to 2 s and judge whether "no sustained shedding" is right;
   check the tail-spread rule in `tools/audit/t1_gates.py` is stated in the spec.
5. Frame export: for one frame, compare a few voxels of `frames/flow_0060.npz` with an IDW you compute from
   a `reconstructPar -time` of that frame (on a copy), within 1e-6 relative.
6. Gate 4: re-run `tools/audit/anim_inside.py -- renders/t1_frames 120` (12 fps): 0 inside, 196334
   particle-frames.
7. Visibility: re-run `tools/audit/t1_visibility.py -- renders/t1_frames <scratch>` headless; expect
   exit 0 and the 0.6.1 counts above (deterministic seed). Then judge the check itself: open one
   `vis_0060.png` and confirm the regions and classifier match its docstring, that the no-smoke baseline
   is 0, and that the red runs are recorded (`visibility_0_6_1.red_*` in the validation record). Reproduce
   one red: rerun with OVERRIDES `{"Radius": 0.00333, "Trail": 0.01, "Rate": 71.43}` (the 0.6.0 inputs)
   and expect FAIL.
8. Auto solve guard: `tools/audit/t1_autosolve_check.py` passes headless; read `t1_scene.cleanup()` and
   confirm the order (WT data removed, Auto solve restored, then handler).
9. `tools/audit/t1_frames_check.py` and `tools/blender_smoke.py` pass headless; tests 103 OK (3 expected
   failures).
10. README "Time-resolved flow" claims nothing beyond the record (no "validated", no St) and states
    the display limit (issue k).
11. Bilal's live Blender was left with only his own data (ask him; do not open his scenes).
RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference.

- New (2026-10-24, step 3 prep): `meshgen.c_grid` uses `case.Setup.first_cell` as the full first cell
  height, while y+ is measured at the cell centre (`nearWallDist`, half the height), so the 2D grid runs
  at about half its nominal y+. Not fixed; Bilal to decide in the step 3 grill or step 7.

### Step 3 started 2026-10-24 (branch worktree-step3-wall)
Stage 0 done (48216f2). The full slice prompt, with the facts established while loading context, is
`docs/prompts/step3_wall.md`; resume from it (Stage 1 measurement done 2026-10-24, commit 5a9ded9,
`validation/step3_wall_v2512.json`; next: grill Q1). Stage 1 corrected two prompt facts: `_t1/Cube/0` is the
potentialFoam start, not a converged field; `first_cell` returns y/L (0.95 mm for y+ 50 on L = 2 m). Work is
on main now (worktree removed). Measured: first layer = 2.00 x nearWallDist (sphere, 100 % coverage).

### NEXT PROMPT (FIX_PLAN step 3, wall mesh and y+; after the T1 review has no open FAIL)
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
Live Blender: any scene built by a script must keep Auto solve off and the handler paused while it
exists (pattern: `tools/audit/t1_scene.py`).
RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference.

## 2026-10-24: FIX_PLAN step 3, Stages 1 to 4 done, stopped at the Stage 4 decision (Bilal's call)

Work is on main (worktree `step3-wall` removed, branch deleted, `.claude/worktrees/` ignored). Code changed
but NOT deployed and NOT version-bumped: Blender still runs add-on 0.6.1; the repo's add-on code is the
step 3 code at version 0.6.1 until Stage 5.

### Done (commits 5a9ded9 .. 4fd8039, then this handoff)
- Stage 1 (5a9ded9, 6d9be29): v2512 `yPlus` and `wallShearStress` post-hoc on copies in `~/wind_tunnel/_step3`
  (`tools/audit/step3_yplus.py`). u_tau from yPlus nu / d agrees with sqrt(|wallShearStress|) (median ratio
  1.000 to 1.012); first layer = 2.00 x nearWallDist measured (sphere 0.03204 m vs d 0.01598 m).
  In-band 30 to 300 before step 3: sphere 0.18, cone 0.31, cube 0.61.
- Two prompt facts corrected: `_t1/Cube/0` and `processor*/0` are the potentialFoam start, not a converged
  field (no converged steady cube field is left on disk; Stage 1 used T1 URANS at t = 2 s); `case.Setup.first_cell`
  returns y/L (2D chord-1 case), so for L = 2 m and y+ 50 it is 0.95 mm, not 0.47 mm. 2D half-y+ finding moved
  to FIX_PLAN step 7.
- Grill Q1 to Q5 and probe amendments A1 to A4 locked in `docs/reference/step3_wall_spec.md` (final b76bad0,
  rules table at the top). Probes (mesh only): `tools/audit/step3_probe.sh`, `step3_probe2.sh`,
  `step3_probe.py`, `step3_icosphere.py`; results in `validation/step3_wall_v2512.json` (probe_2026_10_24,
  probe_round2, probe_round3).
- Stage 3 TDD (2e6a6d4): `case3d.layer_sizing` and the snappy text, `curvatureLevel (24 0 lo2 -1)`, Allrun
  `yPlus` FO after reconstructPar, `export_field.yplus_record / layer_record / wall_record` into
  `forces.json["wall"]`, `results.wall_lines / remesh_u_tau`, `__init__.apply_forces3d`, panel rows with
  warning, one automatic re-mesh (never on Load 3D). Tests 122 OK (2 expected failures, step 4); the step 3
  marker test passes; headless smoke check passes incl. the panel warning row (pass: CHECKMARK, fail: ERROR
  in alert).
- Stage 4 tracer (4fd8039, `tools/audit/step3_tracer.py`): real Allrun, COARSE, 24 ranks, cap 3000, fresh cases
  `~/wind_tunnel/_step3/run_<body>`.
- Housekeeping: `.claude/settings.json` (`worktree.bgIsolation none`) committed at Bilal's request. An empty
  `.claude/worktrees/step3-wall` folder could not be removed while this session's shell held it: delete it.

### Locked decisions (spec, short)

| Item | Locked |
|---|---|
| Q1 | y_c = 100 nu / u_tau_ref, u_tau_ref = 0.0386 U (Re_L / Re_a)^(-1/14), Re_a = 20 x 2 / 1.5e-5; h1 = 2 y_c in metres (3.89 mm for 2 m, 20 m/s). Gate y+ <= 300 on 90 % of area; band and y+ < 5 reported only. Re-mesh once from the run's own u_tau before FAIL (statistic now known to be wrong, D2) |
| Q2 + A1 | firstAndExpansion, r 1.3, n = min(n_half, n_depth) (stack <= one surface cell): 5 layers on COARSE 2 m bodies; nGrow 0 |
| A2 | coverage = faces extruded / body faces (final "Extruding" line), gate 90 %; mean layers and thickness % reported |
| A3 | featureAngle 60 (120 lowered cone coverage 97.0 -> 93.7 %, raised cube skewness 0.47 -> 2.45) |
| Q3 | relativeSizes false, minThickness 0.5 h1 (1.94 mm) |
| Q4 | curvatureLevel (24 0 lo2 -1), COARSE default: sphere at level 3 everywhere, 151 cells around (75 before) |
| Q5 | re-run Sphere, Cube, Cone; panel warns on the two 90 % gates; FIX_PLAN step 3 acceptance text amended (in this handoff commit) |
| A4 | Suzanne's 2 faces at skewness 4.70 pre-exist (castellation and snap); not gated |

### Stage 4 results

| Body | Converged (step 2 gate) | Cd window mean, vs step 2 | y+ <= 300 (gate 90 %) | Coverage (gate 90 %) | y+ min / mean / max | Band 30 to 300 | Cells |
|---|---|---|---|---|---|---|---|
| Cube | yes, at 801 (step 2: 1830) | 1.1431, -0.58 % (1.1498) | 99.8 %, pass | 100 %, pass (3.37 / 5) | 2.5 / 55 / 303 | 90.2 % | 369,664 |
| Cone | yes, at 781 | 0.5840, +0.12 % (0.5833) | 82.0 %, FAIL | 97.0 %, pass (3.07 / 5) | 9.8 / 203 / 1483 | 79.4 % | 363,277 |
| Cone, Q1 re-mesh (u_tau 0.698, h1 4.30 mm) | yes, at 716 | 0.5847, +0.24 % | 75.5 %, FAIL | 97.2 % | 10.5 / 221 / 1478 | 73.3 % | 363,307 |
| Sphere | no: cap 3000, Cd 0.20 to 0.26 (21 mean crossings per 1000 it), p residual 8.0e-3 | not reportable | 96.0 %, on an unconverged field | 99.2 % (4.56 / 5) | 6 / 119 / 1171 | 90.5 % | 388,963 |

Area-weighted y+ p50 / p90 / p95: cone 150 / 419 / 566, cone re-mesh 167 / 459 / 624, sphere 115 / 171 / 274,
cube 45 / 85 / 135. Wall time: sphere 1164 s, cube 306 s, cone 292 s, cone re-mesh 272 s.

Cone diagnosis: every face with y+ > 300 (18.0 % of area) has d > 2 y_c (d 5.2 / 6.7 / 14.7 mm at p10 / p50 / p90,
target 1.94 mm); with d = y_c everywhere the gate would pass on 100 %. They sit on the conical side from
x = -0.1 to 0.98 m (base at x = 1.0): layer stepping toward the base rim spreads the smoothed point thickness
over fewer layers. Their u_tau (median 0.85 m/s) is not unusual; the area-mean u_tau (0.698) is below the
anchor (0.772), so the Q1 re-mesh thickened h1 and made the gate worse.

### Open decisions (bring one at a time after the diagnostic bundle)
- D1 cone layer setting (nSmoothThickness, nBufferCellsNoExtrude, h1 scaling with n pinned, or featureAngle).
- D2 the Q1 re-mesh statistic: area-mean u_tau is wrong for stepped-layer failures; a p90-y+ scaling of h1
  under-delivers if n is allowed to rise (n_depth 6 at h1 2.5 mm) and cannot fix bare faces (about 3 %).
- D3 the sphere: recorded reason (steady RANS at Re 2.67e6 does not converge) or other treatment, after the
  attribution run.

### Open issues
- New, step 3: coarse-STL warning in the add-on (edge length or facet angle vs local cell, optional subdivide
  before export; icosphere 100 % vs UV sphere 62 % at n 8); UV sphere zero-layer faces at 67 and 79 deg from the
  poles, not the pole fans, cause not resolved; faces with fewer layers get a thicker first cell (now the cone's
  failure mechanism); Suzanne layers collapse at any depth (30 to 35 %) and curvatureLevel did not refine it;
  `forces.json["wall"]["yplus"]["u_tau_mean"]` is the wrong re-mesh statistic (D2).
- 2D: `meshgen.c_grid` uses `first_cell` as the full cell height (half the nominal y+): FIX_PLAN step 7.
- Carried from the T1 entry (archived): k (streak display limit, up to about 11 mm into the cube); T1 review O2
  (add OVERRIDES to `visibility_0_6_1.red_0_6_0_streaks_with_play_through`) and O3 (shedding shown for t <= 2 s
  only; name the tail-spread statistic in the spec); c, d, g, h (inlet non-uniformity; preview push back at
  concave edges; legend and label face -Y; section view); f (no add-on load path for a time-resolved field);
  j (URANS on this mesh does not sustain shedding); ANIMATION A+B review O2 (Moreland intermediates).
- Pending on Bilal: `sudo apt purge -y libopenfoam openfoam-examples` (orphaned 1912).
- Disk (WSL): `~/wind_tunnel/_step3` 2.6 GB (Stage 1 copies, probe, probe2, probe3, run_Sphere, run_Cube,
  run_Cone, run_Cone_remesh, tracer.json/log); keep the run_* cases until the diagnostic bundle is done.
  `~/wind_tunnel/_t1/Cube` 5.4 GB kept (T1 record).

### NEXT PROMPT (FIX_PLAN step 3, resume at the Stage 4 decision)
Slice: FIX_PLAN step 3, wall treatment and surface resolution, resumed after Stage 4. Solver-side, so every
number is checked against OpenFOAM's definitions and recorded in `validation/step3_wall_v2512.json` with date,
mesh size and iteration count. Work on main (no worktree).

STAGE 0 GATE: none new (the T1 review has no open FAIL; step 3 has no review yet).

CONTEXT TO LOAD (stay well under 100k tokens): CLAUDE.md; this entry; `docs/reference/step3_wall_spec.md`;
`docs/reference/step2_convergence_reference.md` (the gate); in `wind_tunnel/case3d.py` `layer_sizing` and the
addLayersControls part of `snappy_dict`; `tools/audit/step3_probe.py`, `step3_probe2.sh`, `step3_tracer.py`.
Facts established, do not re-derive: the Stage 4 table and the cone diagnosis above; the locked decisions
table; v2512 layer table columns (patch, faces, target, mesh, thickness m, %); snappy writes per-face
`nSurfaceLayers` and `thickness` with `writeFlags (layerFields)`; `cellLevel` does not survive
reconstructParMesh (levels from face size); mpirun eats a heredoc on stdin (case lists on fd 3);
`set -e` or `set -u` before sourcing the OpenFOAM bashrc kills the script.

STAGE A DIAGNOSTIC BUNDLE (AFK, copies only in `~/wind_tunnel/_step3`, about 20 min; nothing locked here)
1. Cone mesh-only variants, about 15 s each, from `~/wind_tunnel/3d_Cone` with the locked settings except:
   - `nSmoothThickness` 10 -> 2;
   - `nBufferCellsNoExtrude -1` (terminate in one go: faces full or bare, no stepping);
   - h1 x 0.64 with n pinned at 5 (the proportional route);
   - featureAngle 120, judged by d rather than coverage.
   Metric per variant: area fraction with d > 2 y_c (36 % now), coverage (faces extruded), mean layers,
   checkMesh, and the y+ <= 300 fraction predicted from `run_Cone`'s per-face u_tau (yPlus nu / d at 781)
   mapped onto the new body faces by nearest face centre (y+ = d_new u_tau / nu).
2. One cone solve (about 5 min) of the best variant through the real Allrun to the step 2 gate: y+ gate,
   coverage, Cd against 0.5833.
3. Sphere attribution, about 11 min: a copy of `~/wind_tunnel/3d_Sphere` (old mesh, 2 relative layers, v1912
   fields at 400) continued with v2512 simpleFoam from 400 to 3000 with the step 2 gate FOs. If it oscillates
   too, the cause is this body at this Re in steady RANS, not step 3.
Record all three in `validation/step3_wall_v2512.json`, commit.

STAGE B AMENDMENTS (HIL, one at a time, recommendation first, wait for Bilal): D1 cone layer setting;
D2 the Q1 re-mesh statistic (code change: forces.json must carry what the new rule needs); D3 the sphere
(recorded reason or treatment). Lock each in the spec. Then TDD for any code change (red, then green),
re-run the affected bodies (copies) to the gate.

STAGE 5 CLOSE (AFK): tests green, `py tools/deploy.py`, headless smoke check, version bump 0.6.1 -> 0.7.0 in
`wind_tunnel/blender_manifest.toml` and `bl_info`, README note on wall treatment (y+ target, layers, gates,
the panel rows; no "validated"), commit with the physical quantity changed and by how much (y+ <= 300
fraction and Cd change per body). Tell Bilal to restart Blender or toggle the add-on.

STAGE 6 HANDOFF (AFK): SESSION_LOG entry (archive this one verbatim to `docs/archive/`), REVIEWER PROMPT to
`docs/reviews/step3_review.md` (push: layer height vs nearWallDist, Cf citation status, band and y+ <= 300
fractions recomputed from the yPlus field independently, coverage from the log, gate passed on every re-run,
the cone diagnosis), NEXT PROMPT for FIX_PLAN step 4 (domain).

RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference;
Stop at stage boundaries; no new heavy stage after about 150k tokens; hand off at about 200k; never compact.

## 2026-10-24: FIX_PLAN step 3, Stage A bundle done, amendments D1 to D3 locked, stopped before Stage B

Work is on main. The empty `.claude/worktrees/step3-wall` folder is deleted. Add-on code is still the step 3
Stage 3 code at version 0.6.1, NOT deployed; D1 and D2 are locked in the spec but not yet coded.

### Done (commits 2e596f9 .. 040100b, then this handoff)
- Stage A diagnostic bundle (2e596f9, `tools/audit/step3_diag.py`, record `validation/step3_wall_v2512.json`
  key `stageA_diagnostic_2026_10_24`; every field in WSL `~/wind_tunnel/_step3/diag/bundle.json`). Modes:
  no argument = the pre-registered bundle (V0 to V4, best-variant solve, sphere attribution); `extra`, `extra2`,
  `extra3` = V5/V6, V7/Cube, Sphere mesh-only variants; `solve NAME`; `mapped` = the D3 discriminator.
  `step3_tracer.run` gained `layers`, `patch` and `levels` arguments.
- Calibration: the d metric on run_Cone reproduces 35.7 % of the area with d > 2 y_c and y+ <= 300 on 82.0 %;
  the predictor (run_Cone u_tau mapped by nearest face centre, y+ = d u_tau / nu) gives 74.8 % on run_Cone_remesh
  vs 75.5 % measured (-0.7 points), and 96.6 % vs 96.9 % on the D1 cone solve.
- Cut-layer mechanism, measured (V0 with `writeFlags (layerFields)`; fields land in `processor*/0`, which the
  Allrun `0.orig` copy deletes; reconstruct with `reconstructPar -withZero -time 0`): faces with 2 layers keep
  26.8 mm of the 35 mm stack, first layer 11.7 mm = 3 h1; every y+ > 300 face has 0 to 2 layers; source
  snappyLayerDriver.C:4171-4181. Cut layers sit on mixed level 2 and 3 faces (x -0.2 to 0.6 m) and next to
  the base rim; pure level 3 stretches keep 4.5 to 5 layers.
- D1, D2, D3 locked one at a time (c19f089, 2ea8f2f, 040100b) in `docs/reference/step3_wall_spec.md`
  (amendments D1, D2, D3; rules table and Q1, Q4 text updated); D3 discriminator run recorded (3b5366f).

### Stage A results

| Cone variant (mesh only) | Coverage | d > 2 y_c area | Predicted y+ <= 300 | Cells |
|---|---|---|---|---|
| V0 locked | 97.0 % | 35.7 % | 82.0 % | 363,291 |
| V1 nSmoothThickness 2 | 95.1 % | 43.7 % | 68.1 % | 362,659 |
| V2 nBufferCellsNoExtrude -1 | 0 % (every iteration removed more) | 100 % | 1.0 % | 352,177 |
| V3 h1 x 0.64, n 5 | 88.2 % | 29.8 % | 77.1 % | 360,899 |
| V4 featureAngle 120 | 93.7 % | 38.3 % | 79.4 % | 362,625 |
| V5 level (3 3) | 98.4 % | 9.9 % | 96.6 % | 383,254 |
| V6 level (3 3), featureAngle 120 | 96.0 % | 12.3 % | 94.1 % | 382,625 |
| V7 curvatureLevel (48 0 3 -1) | 96.9 % | 35.5 % | 82.4 % | 363,176 |

- V5 cone solved (real Allrun, no re-mesh, `_step3/diag/solve_V5_level33`): converged at 721, Cd 0.5849 (+0.27 %
  vs 0.5833), y+ <= 300 on 96.9 % (pass), band 94.3 %, coverage 98.4 % (4.26 / 5), checkMesh clean (max skewness
  0.82 vs 1.08), 383,044 cells, 275 s.
- Cube level (3 3), mesh only: 436,030 cells (+18 % vs 369,664), coverage 100 %, predicted 99.8 %, clean.
  Sphere level (3 3), mesh only: 388,914 cells (388,963), 100 % of the area at level 3 before and after.
- D2 split: on run_Cone, run_Cone_remesh, the V5 cone, run_Cube and run_Sphere, 0 % of the y+ > 300 area has
  d <= 1.5 y_c; on those full-stack faces the area-weighted y+ p90 is 54 to 163.
- Sphere: the old 3d_Sphere mesh continued from its v1912 field at 400 under the v2512 solver and gate converges
  at 1306, Cd 0.1622, band 0.25 %, p residual 9.8e-4 (256 s); its first cells sit at y+ mean 822 (17.8 % <= 300).
  The old converged field mapped onto the step 3 mesh (`_step3/diag/sphere_mapped`, 937 s) oscillates like the
  cold start: Cd 0.21 to 0.40, p residual 1.2e-2 at 3000.

### Locked decisions (spec, short; Stage 3 table in the archived entry still holds except where amended)

| Item | Locked |
|---|---|
| D1 | Body surface level (lo2 lo2) in every preset: COARSE (2 3) -> (3 3), MEDIUM (3 4) -> (4 4); `curvatureLevel` removed from `snappy_dict`; layer settings unchanged |
| D2 | No automatic re-mesh: `results.remesh_u_tau`, the `__init__` re-mesh step and `wall.yplus.u_tau_mean` go; `forces.json["wall"]["yplus"]` gains `y_c` (m) and `gt300_thick_first_cell` / `gt300_design_first_cell` (y+ > 300 area split at d = 2 y_c); the panel FAIL row names the larger cause |
| D3 | Sphere recorded, not treated: no steady state on the gate-passing step 3 mesh from either start; Stage B re-runs it unchanged, no Cd; sphere check stays in FIX_PLAN step 5; URANS time-averaged fallback is an open issue |

### Open issues
- New: URANS fallback with time-averaged forces for bodies whose steady run fails the gate on a gate-passing mesh
  (D3). Guarded u_tau re-mesh (p90 u_tau of design-first-cell faces at y+ 100) only if a body ever shows a
  u_tau-driven failure (D2). MEDIUM cost under D1 not measured. 9.9 % of the D1 cone area still has d > 2 y_c in
  the rim band (inside the gate). Wall versus surface resolution as the sphere's trigger not separated.
- Carried (see the archived entry): coarse-STL warning; UV sphere zero-layer faces; Suzanne layer collapse; 2D
  `meshgen.c_grid` half y+ (FIX_PLAN step 7); T1 items k, O2, O3, c, d, g, h, f, j; ANIMATION A+B review O2.
- Pending on Bilal: `sudo apt purge -y libopenfoam openfoam-examples` (orphaned 1912).
- Disk (WSL): `~/wind_tunnel/_step3` 4.1 GB (Stage 1 copies, probes, run_*, diag/*). Keep run_Cone (predictor
  reference) and diag/bundle.json until Stage 6; the rest can go after the Stage B re-runs.

### NEXT PROMPT (FIX_PLAN step 3, resume at Stage B TDD)
Slice: FIX_PLAN step 3, wall treatment and surface resolution, resumed after the amendments. Solver-side, so every
number is checked against OpenFOAM's definitions and recorded in `validation/step3_wall_v2512.json` with date,
mesh size and iteration count. Work on main (no worktree).

STAGE 0 GATE: none new (the T1 review has no open FAIL; step 3 has no review yet).

CONTEXT TO LOAD (stay well under 100k tokens): CLAUDE.md; this entry; `docs/reference/step3_wall_spec.md` (rules
table, amendments D1 to D3); in `wind_tunnel/case3d.py` `Setup3D`, `layer_sizing`, the refinementSurfaces line of
`snappy_dict`; `wind_tunnel/__init__.py` the presets (line ~541) and the re-mesh block in the 3D poll (~772-787);
`wind_tunnel/export_field.py` `yplus_record`, `wall_record`, the `--u-tau-ref` argument; `wind_tunnel/results.py`
`remesh_u_tau`, `wall_lines`; the step 3 tests in `tests/test_pure.py` (lines ~1040-1250);
`tools/audit/step3_tracer.py`. Facts established, do not re-derive: the Stage A table and results above; the
cut-layer mechanism; the locked decisions; mpirun eats a heredoc on stdin (case lists on fd 3, or stdin=DEVNULL);
`set -e` or `set -u` before sourcing the OpenFOAM bashrc kills the script.

STAGE B TDD (AFK; red, then green; pure modules first)
1. D1: tests first that COARSE writes `body { level (3 3); patchInfo` and MEDIUM `level (4 4)`, with no
   `curvatureLevel`; `__init__` presets (3, 3) and (4, 4); `Setup3D.surface_levels` default (4, 4); fix the old
   tests that assert `curvatureLevel` (~1097-1100) and (2, 3) sizing (layer_sizing only uses lo2, so h1 and n
   are unchanged: 3.89 mm, 5 layers).
2. D2: tests first for `yplus_record(yplus, A, d, nu, y_c)` returning `y_c`, `gt300_thick_first_cell`,
   `gt300_design_first_cell` (and no `u_tau_mean`); y_c into export_field from the Allrun (pass `--y-c` or the y+
   target with `--u-tau-ref`, test the Allrun text); `results.wall_lines` names the larger cause on a FAIL;
   delete `remesh_u_tau`, its tests (~1242-1250), the `--remeshed` export flag if nothing else needs it, the
   `__init__` re-mesh block and `start_run3d(u_tau=...)` only if unused elsewhere; `step3_tracer` without the
   re-mesh. Headless smoke check must still show the panel warning row.
3. Re-run Cube, Cone, Sphere on copies through `step3_tracer.py` (fresh `~/wind_tunnel/_step3/run_<body>_d1`), one
   at a time, 24 ranks, to the step 2 gate: record cells, coverage, mean layers, y+ min/mean/max, y+ <= 300 and
   band fractions, the new split, gate iteration, Cd window mean and change vs step 2 (cube 1.1498, cone 0.5833);
   sphere expected not converged (D3), recorded without Cd.

STAGE 5 CLOSE (AFK): tests green, `py tools/deploy.py`, headless smoke check, version bump 0.6.1 -> 0.7.0 in
`wind_tunnel/blender_manifest.toml` and `bl_info`, README note on wall treatment (y+ target, layers, uniform body
level, gates, the panel rows, the sphere's recorded state; no "validated"), commit with the physical quantity
changed and by how much (y+ <= 300 fraction and Cd change per body). Tell Bilal to restart Blender or toggle the
add-on.

STAGE 6 HANDOFF (AFK): SESSION_LOG entry (archive this one verbatim to `docs/archive/`), REVIEWER PROMPT to
`docs/reviews/step3_review.md` (push: layer height vs nearWallDist, Cf citation status, band and y+ <= 300 fractions
recomputed from the yPlus field independently, coverage from the log, gate passed on every re-run, the cut-layer
mechanism against snappyLayerDriver.C:4171-4181, the D2 split recomputed, the sphere attribution and mapped run),
NEXT PROMPT for FIX_PLAN step 4 (domain).

RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference;
stop at stage boundaries; no new heavy stage after about 150k tokens; hand off at about 200k; never compact.

## 2026-10-24: FIX_PLAN step 3, Stage B done (D1 and D2 coded, three re-runs recorded), stopped before Stage 5

Work is on main. Add-on code carries D1 and D2 but is still version 0.6.1 and NOT deployed (Stage 5 does both).
Stopped at the Stage B / Stage 5 boundary for the token budget.

### Done (commits 5499768, e7b538e, 4f8f097, then this handoff)
- D1 (5499768): `case3d.PRESETS = {"COARSE": ((3, 3), 2, 6), "MEDIUM": ((4, 4), 2, 8)}`, used by
  `__init__.start_run3d`; `snappy_dict` writes `body { level (lo2 lo2); patchInfo ...}` from `surface_levels[1]`
  whatever `surface_levels[0]` is, no `curvatureLevel`; `Setup3D.surface_levels` default (4, 4). h1 3.89 mm and
  5 layers (COARSE) unchanged. Tests: `test_uniform_body_level`, `test_presets`, old (2 3)/(3 4) tests moved.
- D2 (e7b538e): `export_field.yplus_record(yplus, A, d, y_c=None)` returns `y_c`, `gt300_thick_first_cell`
  (y+ > 300 and d > 2 y_c), `gt300_design_first_cell` (y+ > 300 and d <= 2 y_c), None for both without y_c; no
  `u_tau_mean`. `wall_record(..., y_c)`; Allrun passes `--y-c {y_c:.6g}` (1.94301 mm at L 2 m, 20 m/s); `--remeshed`
  and `forces["remeshed"]` gone; `forces["wall"]["u_tau_ref"]` kept. `results.wall_lines` adds a row under the
  y+ FAIL row, "Cause: cut layers (N % of area)" when thick >= design, else "Cause: u_tau > sizing (N % of area)",
  none when the split keys are missing (old forces.json). `results.remesh_u_tau`, the `__init__` re-mesh block and
  `start_run3d(u_tau=...)` deleted; `Setup3D.u_tau` kept as a plain sizing override (audit scripts).
  `tools/blender_smoke.py` fixture uses the new keys and checks the cause row; `step3_tracer.py` has no re-mesh,
  COARSE levels from `case3d.PRESETS`, `--suffix`, writes `_step3/tracer<suffix>.json` after every body.
- Tests: 127 run, OK (2 expected failures, pre-existing). Headless smoke check (repo source, before deploy):
  `ok: true`, FAIL row ERROR icon, cause row "Cause: cut layers (15 % of area)", none on the pass.
- Stage B re-runs (4f8f097, `validation/step3_wall_v2512.json` key `stageB_rerun_2026_10_24`, raw summaries
  in WSL `~/wind_tunnel/_step3/tracer_d1.json`, cases `_step3/run_<body>_d1`).

### Stage B results (COARSE, body level (3 3), 24 ranks, cap 3000, step 2 gate, 2026-10-24)

| | Cube | Cone | Sphere |
|---|---|---|---|
| Cells | 437,192 | 383,135 | 388,788 |
| Gate | converged at 786 | converged at 716 | not converged at 3000 (D3) |
| Cd window mean | 1.1448 (step 2 1.1498, -0.43 %) | 0.5846 (step 2 0.5833, +0.23 %) | none reported |
| Cd band | 0.33 % | 0.23 % | 17.7 %, p residual 1.0e-2 |
| Layer coverage | 100 % | 98.4 % | 99.2 % |
| Mean layers / 5, thickness % | 4.22, 90.9 % | 4.26, 91.2 % | 4.56, 96.2 % |
| y+ min / mean / max | 3.9 / 55 / 303 | 6.8 / 113 / 1491 | 7.7 / 129 / 1191 |
| y+ <= 300 (gate 90 %) | 99.8 % | 96.95 % (was 82.0 %) | 95.6 % (snapshot at 3000) |
| 30 < y+ < 300 band | 89.8 % | 94.3 % | 92.6 % |
| y+ > 300 split thick / design | 0.18 / 0 % | 3.05 / 0 % | 4.30 / 0.15 % |
| checkMesh | OK, skew 0.47, non-orth 41.5 | OK, skew 0.82, non-orth 56.8 | OK, skew 0.62, non-orth 51.6 |
| Wall time | 319 s | 234 s | 1039 s |

- Cone reproduces the Stage A V5 solve (383,044 cells, 721, Cd 0.5849, 96.9 %). Cube cells +18.3 % vs run_Cube
  (369,664), Cd 1.1431 -> 1.1448 between the two step 3 meshes.
- Sphere: the 0.15 % design-first-cell share is the first nonzero one (D2 stated 0 % at d <= 1.5 y_c); it is
  from an unconverged snapshot. No Cd reported (step 2 rule, D3).

### Locked decisions
Unchanged: D1, D2, D3 in `docs/reference/step3_wall_spec.md` (see the archived entry's table).

### Open issues
- Stage 5 and 6 not done: no deploy, no version bump, no README note, FIX_PLAN step 3 acceptance text not yet
  updated to the two gates (spec Q5), no review prompt.
- `tools/audit/step3_diag.py` variants that set `surface_levels (2, 3)` no longer reproduce the Stage A V0 mesh,
  because `snappy_dict` now writes (lo2 lo2); the Stage A record stands as measured with the earlier code.
- Carried: URANS fallback with time-averaged forces (D3); guarded u_tau re-mesh only on a u_tau-driven failure
  (D2); MEDIUM cost under D1 not measured; coarse-STL warning; UV sphere zero-layer faces; Suzanne layer collapse;
  2D `meshgen.c_grid` half y+ (FIX_PLAN step 7); T1 items k, O2, O3, c, d, g, h, f, j; ANIMATION A+B review O2.
- Pending on Bilal: `sudo apt purge -y libopenfoam openfoam-examples` (orphaned 1912).
- Disk (WSL): `~/wind_tunnel/_step3` grows by the three `run_*_d1` cases. Keep run_Cone (predictor reference),
  diag/bundle.json and the `run_*_d1` cases until the step 3 review; the rest can go.

### NEXT PROMPT (FIX_PLAN step 3, Stage 5 close and Stage 6 handoff)
Slice: FIX_PLAN step 3, wall treatment and surface resolution, close. Solver-side code is finished and recorded;
this session only closes and hands off. Work on main (no worktree).

STAGE 0 GATE: none new (the T1 review has no open FAIL; step 3 has no review yet).

CONTEXT TO LOAD (stay well under 60k tokens): CLAUDE.md; this entry; `docs/reference/step3_wall_spec.md` (rules
table, gates, amendments D1 to D3); the FIX_PLAN step 3 section of `docs/FIX_PLAN.md`; the README section on 3D
runs; `validation/step3_wall_v2512.json` key `stageB_rerun_2026_10_24` (summary only). Facts established, do not
re-derive: the Stage B table above; D1 and D2 as coded; tests 127 OK; smoke check ok before deploy.

STAGE 5 CLOSE (AFK):
1. `py -m unittest discover -s tests -v` green.
2. Version bump 0.6.1 -> 0.7.0 in `wind_tunnel/blender_manifest.toml` and `bl_info` in `wind_tunnel/__init__.py`.
3. `py tools/deploy.py`, then the headless smoke check (`report["version"]` must read [0, 7, 0]).
4. README note on wall treatment: y+ target 100 at the first cell centre, h1 = 2 y_c in metres, layers
   min(n_half, n_depth), uniform body level (3 3) COARSE / (4 4) MEDIUM, the two gates (y+ <= 300 on 90 % of the
   area, layer coverage 90 %), the panel rows including the cause row, no automatic re-mesh, the sphere's recorded
   state at Re 2.67e6 (no steady state on the gate-passing mesh, no Cd). No "validated".
5. FIX_PLAN step 3 acceptance text updated to the two gates (spec Q5), with the Stage B numbers; the
   `results.wall_lines` docstring mentions the D2 cause row.
6. Commit with the physical quantity changed and by how much (per body: y+ <= 300 fraction and Cd change, from
   the table above). Tell Bilal to restart Blender or toggle the add-on.

STAGE 6 HANDOFF (AFK): SESSION_LOG entry (archive this one verbatim to `docs/archive/`), REVIEWER PROMPT to
`docs/reviews/step3_review.md` (push: layer height vs nearWallDist, Cf citation status, band and y+ <= 300
fractions recomputed from the yPlus field of the `run_*_d1` cases independently, coverage from log.snappyHexMesh,
the gate passed on Cube and Cone and the sphere's failure recorded without Cd, the cut-layer mechanism against
snappyLayerDriver.C:4171-4181, the D2 split recomputed from d and y_c, the sphere attribution and mapped run, the
`level (lo2 lo2)` writer ignoring `surface_levels[0]`), NEXT PROMPT for FIX_PLAN step 4 (domain).

RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference;
stop at stage boundaries; no new heavy stage after about 150k tokens; hand off at about 200k; never compact.

## 2026-10-24: FIX_PLAN step 3 closed (Stage 5 and 6), add-on 0.7.0 deployed; project moves to the PORTFOLIO slice

Work is on main. Step 3 is closed without a separate review session (Bilal's decision, 2026-10-24, recorded in
FIX_PLAN step 3). The project is ending as a GitHub portfolio piece: FIX_PLAN steps 4 to 7 are documented next
steps, not scheduled work. The next and last slice is PORTFOLIO (NEXT PROMPT below).

### Done (commit 24ac156, then this handoff)
- Tests: 127 run, OK (2 expected failures, pre-existing).
- Version 0.6.1 -> 0.7.0 in `wind_tunnel/blender_manifest.toml` and `bl_info`; `py tools/deploy.py` (14 files,
  `dist/wind_tunnel.zip`); headless smoke check `ok: true`, `version` [0, 7, 0], wall panel pass row and FAIL row
  with "Cause: cut layers (15 % of area)". Deployed twice (the second after the docstring edit), same result.
- README: new subsection "Wall treatment (v0.7.0)" under "3D, any closed mesh": y+ target 100 at the first cell
  centre, h1 = 2 y_c in metres, n = min(n_half, n_depth), uniform body level (3 3) COARSE / (4 4) MEDIUM, the two
  gates, the cause row, no automatic re-mesh (the one tried took the cone 82.0 -> 75.5 %), cube and cone Stage B
  numbers stated as mesh-quality checks, not a comparison with experiment, the sphere's state at Re 2.67e6 (no
  steady state on the gate-passing mesh, no Cd). The drag-crisis Re (about 3e5 to 4e5) is from memory and says so.
- FIX_PLAN step 3: amendments D1 to D3 summarised, final acceptance (both gates on every body re-run) with the
  Stage B table, and the note that steps 4 to 7 are documented next steps.
- `docs/reference/step3_wall_spec.md` D2: note that the "0 %" design-height share held for the five runs listed;
  the Stage B sphere has 0.15 % (`gt300_design_first_cell` 0.0015, thick share 4.30 %), the first nonzero one,
  from the unconverged snapshot at 3000, so not evidence of a u_tau-driven failure; cube and cone Stage B 0 %.
- `results.wall_lines` docstring names the D2 cause row and the rule (thick >= design gives "cut layers").

### Numbers (Stage B, COARSE, body level (3 3), 24 ranks, cap 3000, step 2 gate, 2026-10-24)

| | Cube | Cone | Sphere |
|---|---|---|---|
| Cells | 437,192 | 383,135 | 388,788 |
| Gate | converged at 786 | converged at 716 | not converged at 3000 (D3) |
| Cd window mean | 1.1448 (step 2 1.1498, -0.43 %) | 0.5846 (step 2 0.5833, +0.23 %) | none reported |
| y+ <= 300 (gate 90 %) | 99.8 % | 96.95 % (Stage 4 82.0 %) | 95.6 % (snapshot) |
| Layer coverage (gate 90 %) | 100 % | 98.4 % | 99.2 % |
| y+ > 300 split thick / design | 0.18 / 0 % | 3.05 / 0 % | 4.30 / 0.15 % |

Full table: archived entry and `validation/step3_wall_v2512.json` key `stageB_rerun_2026_10_24`.

### No REVIEWER PROMPT
Skipped by Bilal's decision (2026-10-24). The review items that the previous NEXT PROMPT listed (layer height vs
nearWallDist, Cf citation status, band and y+ <= 300 fractions recomputed from the yPlus field, coverage from
log.snappyHexMesh, the cut-layer mechanism against snappyLayerDriver.C:4171-4181, the D2 split recomputed, the
sphere attribution, the `level (lo2 lo2)` writer ignoring `surface_levels[0]`) stay unchecked by an independent
session; the README and FIX_PLAN must not imply otherwise.

### Open issues
- Stale for a portfolio reader (PORTFOLIO item, not patched here): README banner "Status (v0.4.0): ... not yet
  physically reliable"; README transient section "(FIX_PLAN steps 3 and 4)" where the reference comparison is now
  step 5; FIX_PLAN title "work in this order" with no status line; `docs/ACCURACY_AUDIT.md` (v0.4.0) does not mark
  which findings steps 1 to 3 closed; manifest tagline "Airfoil polars from OpenFOAM running in WSL" (3D is the
  main feature now).
- Personal strings in tracked files (`git grep -i -E "bgare|gmail|azzbilal"`, archive excluded): `CLAUDE.md:40`
  (`C:\Users\bgare\Documents\WindTunnel`), `docs/reviews/anim_ab_review.md:13,14,169` and
  `docs/reviews/transient_t1_review.md:17` (local temp paths), `wind_tunnel/blender_manifest.toml:9` (website
  `https://github.com/azzbilal`). The archive has none. CLAUDE.md also holds the "Owner and how to talk to him"
  section, the WSL user name and machine details.
- No git remote, no LICENSE file (the manifest already says `SPDX:GPL-3.0-or-later`). `renders/` is gitignored:
  `anim_ab_cube.mp4` 4.8 MB, `transient_t1_cube.mp4` 4.5 MB, `t1_still_030/060/120.png` about 0.9 MB each,
  `t1_frames/`. `validation/` is 14 MB (largest `reference_case_3d_Cube/` 6.5 MB), inside GitHub limits.
- Carried as documented next steps (FIX_PLAN 4 to 7 and logged items): domain study and blockage (4); validation
  set against cited references, cube mesh study with Richardson extrapolation, Bernoulli check (5); cellPoint
  sampling, cell centres from `C` (T1 O1), longer voxel grid (6); 2D far-field correction and the `meshgen.c_grid`
  half-y+ bug (7); URANS fallback with time-averaged forces for bodies like the sphere (D3); guarded u_tau re-mesh
  (D2); MEDIUM cost under D1 not measured; coarse-STL warning; UV sphere zero-layer faces; Suzanne layer collapse
  and checkMesh skewness 4.70; T1 items k, O2, O3, c, d, g, h, f, j; ANIMATION A+B review O2;
  `tools/audit/step3_diag.py` variants with `surface_levels (2, 3)` no longer reproduce the Stage A V0 mesh.
- WSL disk: `~/wind_tunnel/_step3` (run_Cone, diag/bundle.json, `run_*_d1`) was kept for the step 3 review, which
  will not happen; it can go unless PORTFOLIO wants cone or sphere renders from it (each `run_*_d1` holds a
  `field.npz`). `~/wind_tunnel/_t1/Cube` likewise.
- Pending on Bilal: `sudo apt purge -y libopenfoam openfoam-examples` (orphaned 1912).

### NEXT PROMPT (PORTFOLIO: make the repository a GitHub portfolio piece, final slice)
Slice: PORTFOLIO. Turn this repository into a public GitHub portfolio piece that an aerospace or CFD reader can
judge in two minutes: what it does, a picture, what is checked against what, what is not, and what comes next.
No solver-side changes (case3d, case, meshgen, export_field, results logic) and no new runs. FIX_PLAN steps 4 to
7 are written up as documented next steps, not done. Work on main (no worktree).

STAGE 0 GATE: waived. Step 3 has no review by Bilal's decision (2026-10-24, recorded in FIX_PLAN step 3); every
earlier review in `docs/reviews/` has no open FAIL.

CONTEXT TO LOAD (stay under 60k tokens): CLAUDE.md; this entry; `README.md`; `docs/FIX_PLAN.md`; headings and
the "What fails" list of `docs/ACCURACY_AUDIT.md`; the file list of `docs/reviews/`, `docs/reference/`,
`validation/` (names only, open a JSON only for a number the README quotes); `wind_tunnel/blender_manifest.toml`.
Facts established, do not re-derive: everything in this entry (Done, Numbers, Open issues, including the personal
strings list and media sizes); the README's 2D table is against NASA TMR (CFL3D, finest grid) and is the only
experiment-or-reference comparison with a citation in the repo; the transient section's numbers stand.

GRILL (HIL, before any edit: one question at a time, recommendation first, wait for Bilal; lock the answers in
`docs/reference/portfolio_spec.md`):
- Q1 Repository name and visibility. Recommend public, a descriptive name such as `blender-openfoam-wind-tunnel`.
  Creating the GitHub repo and pushing are Bilal's steps (outward-facing; `gh` is installed at
  `/c/Program Files/GitHub CLI/gh` but needs his login and his go); Claude prepares the commands.
- Q2 Licence. Recommend a LICENSE file with GPL-3.0-or-later, matching the manifest's SPDX field and Blender's
  add-on licensing (OpenFOAM itself is GPL-3; both from memory, say so).
- Q3 The AI-assisted workflow record (CLAUDE.md, SESSION_LOG.md, `docs/archive/`, `docs/prompts/`,
  `docs/reviews/`). Recommend keeping them public as evidence of method (spec, grill, TDD, independent review),
  replacing the absolute Windows user paths in the five places listed with neutral wording, keeping git history
  as is (no rewrite). Ask separately whether the "Owner and how to talk to him" section stays.
- Q4 Media. Recommend `docs/media/` (not ignored) with two or three PNG stills under about 1 MB each (one Cp slice,
  one smoke still from `renders/`) and one short GIF cut from `renders/anim_ab_cube.mp4` under about 5 MB; an mp4
  in the repo does not play inline in a README, so the full videos go to a GitHub release or stay local. Offer
  a cone still only if Bilal wants it (needs `~/wind_tunnel/_step3/run_Cone_d1/field.npz` and a headless render,
  the one heavy task allowed in this slice).
- Q5 Results the README may show. Recommend: the NACA 0012 table against NASA TMR as the one cited comparison;
  cube and cone as "both wall gates and the convergence gate pass, Cd 1.1448 and 0.5846, reference comparison is
  FIX_PLAN step 5"; the sphere as "no steady state at Re 2.67e6, no Cd". No Hoerner, ESDU or Achenbach number
  unless Bilal supplies the source and page; never "validated" or "in range" without a cited value.
- Q6 Optional CI: a GitHub Actions job running `python -m unittest discover -s tests`. Recommend trying
  ubuntu-latest (the pure modules have no bpy), falling back to windows-latest if `wsl.py` path tests need it.
- Q7 WSL cleanup: delete `~/wind_tunnel/_step3` and `~/wind_tunnel/_t1` after Q4 is answered (recommend yes,
  Bilal's go; keep the six original solved cases).

STAGES (after the grill):
1. README rewrite: one-paragraph summary; a picture; the pipeline diagram; "What is checked" (convergence gate,
   wall gates, Cp reference, continuity, the NASA TMR table) with each number's source file in `validation/`;
   "Known limits" (steady RANS, wall functions, coarse default mesh, sphere, IDW sampling); "Next steps" (FIX_PLAN
   4 to 7 in one line each, plus the URANS fallback and the 2D y+ bug); Install; Development; a short "How it was
   built" paragraph if Q3 keeps the workflow record. Fix the two stale items (v0.4.0 banner, "steps 3 and 4").
2. `docs/FIX_PLAN.md`: a status block at the top (steps 0 to 3 closed with dates, versions and review files;
   step 3 without review; 4 to 7 documented next steps). `docs/ACCURACY_AUDIT.md`: a status line per "What fails"
   finding (closed by step N, or open, pointing at the FIX_PLAN step); do not change the audit's original text.
3. Repository hygiene per Q2 to Q4: LICENSE, `docs/media/` and a `.gitignore` exception, the path wording, the
   manifest tagline (and `website` once the repo URL is known). A manifest change is an add-on change: bump to
   0.7.1 in both places.
4. Optional CI per Q6.
5. HIL visual QA: Bilal reads the README rendered locally (VS Code preview or the GitHub preview after his push)
   and judges; small rounds.
6. Close: tests green; if the add-on changed, `py tools/deploy.py` and the headless smoke check; commit in small
   steps ("no physical quantity changed"); give Bilal the exact `gh repo create` / `git remote add` / `git push`
   commands and wait for his go. Claude does not push.
7. Handoff: final SESSION_LOG entry (archive this one verbatim first) stating the end state of the project and
   where each next step is documented; no NEXT PROMPT needed beyond "project closed, next steps in FIX_PLAN".

RULES: no sudo, no em dashes, asterisk terms plus glossary in chat replies, never "validated" without a cited
reference and say when a value is from memory; no solver-side changes; nothing pushed or published without
Bilal's explicit go; stop at stage boundaries; no new heavy stage after about 150k tokens; hand off at about
200k; never compact.
