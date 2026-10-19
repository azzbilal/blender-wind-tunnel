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
- `~/wind_tunnel/_step0` (copies plus the fresh cube, about 1.2 GB) and `_install_check` can be
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
