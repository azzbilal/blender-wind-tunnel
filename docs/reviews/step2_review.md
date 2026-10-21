# FIX_PLAN step 2 review: convergence gate

Date: 2026-10-21. Reviewer: Claude (fresh session), from the REVIEWER PROMPT in SESSION_LOG.md
(entry "stages 4 and 5 done", updated in 136293b).
Commits reviewed: 1a4d9e2 (gate code, 0.4.3), 382cc23 (Stage 5 tracer runs), dc56044 (Stage 6 QA
fixes, 0.4.4) and the session-log commits after them (a351b8b, fb68e95, 136293b).
Read: CLAUDE.md, docs/reference/step2_convergence_reference.md, SESSION_LOG.md last three entries,
validation/step2_gate_v2512.json, wind_tunnel/convergence.py, export_field.verdict_record,
case3d.write_system, results.progress / forces_converged / verdict_lines, the 3D panel and
field_state in `__init__.py`, OpenFOAM v2512 `abort.C` and `systemCall.C`.

**Result: 11 of 11 PASS, no FAIL open.** Two observations (items 6 and 7) and one note on item 11
(cell count) are listed; none needs a fix before the next slice.

| # | Item | Result |
|---|---|---|
| 1 | gate matches Q2 | PASS |
| 2 | parser | PASS |
| 3 | controlDict and fvSolution | PASS |
| 4 | independent recompute | PASS |
| 5 | Cd/Cl/Cs definition, FO vs face sum | PASS |
| 6 | panel | PASS |
| 7 | results.progress | PASS |
| 8 | tests, no bpy | PASS |
| 9 | em dashes, LF, version | PASS |
| 10 | path-dependence claim | PASS |
| 11 | gated path independence (Cube_tri2) | PASS |

## 1. `convergence.gate` against Q2: PASS

- Window: `sel = [i for i, t in enumerate(times) if t > n - WINDOW]` with integer times selects
  n-199..n, 200 values. No off-by-one. A gap in the history leaves fewer than 200 rows and adds the
  reason "only k of the 200 window iterations recorded", so a short window can never pass.
- Band: `(max - min) / abs(mean)` of Fx over the window, `inf` when the mean is 0. Q2 states the band
  on Cd; Cd = Fx / (q A) with constant q A, so the band is identical (scale free).
- Residual: `p_initial[-1]`, the value at n only. `p_initial` is the first p solve
  (`solverInfoTemplates.C:127`, per the reference doc).
- `n < 400` adds a reason. The cap reason is inserted only when `reasons` is non-empty and n >= cap,
  so a run converging exactly at the cap reports converged.
- Both criteria are tested with `not x < limit`, so a NaN band or residual fails the gate.

## 2. Parser: PASS

- `read_dat`: `names` is overwritten on every `#` line, so the last one wins. `lines.pop()` removes
  either the empty string after a final newline or the unfinished last line; rows shorter than the
  header are skipped as well.
- `_merged`: start-time directories parsed with `float()` and sorted numerically, later rows
  overwrite earlier ones at the same integer time. Non-numeric directory names are ignored.
- Columns by name: `Time`, `total_x/y/z` from `force.dat`, `p_initial` from `solverInfo.dat`. The
  string column `p_solver` (GAMG) is harmless because rows split on whitespace.
- `history` uses only iterations present in both files, so a forces row written before its
  solverInfo row is not gated.

## 3. controlDict and fvSolution: PASS

- `case3d.write_system`: `functions` order forces, solverInfo, gate, stop; gate `executeInterval 5`,
  `master yes`; `stop` with `file "wt_stop"` (relative). `abort.C:170-172` (v2512) turns a relative
  `file` into `time_.globalPath()/file_`, the case root also in parallel. `rhoInf {s.rho}`,
  `endTime {s.iterations}` (cap 3000 by default).
- No `residualControl` in the generated fvSolution, nor in `_step2/Cube/system/fvSolution` and
  `_step2/Cube_tri2/system/fvSolution` (grep exit 1).
- `systemCall.C:123` (fatal for an administrator) is matched by the Allrun root check.

## 4. Independent recompute from `_step2/{Cube,Cone}/postProcessing`: PASS

Own stdlib script (not convergence.py; scratchpad `recompute.py`), Cd = Fx / (0.5 x 1.225 x 20^2 x A):

| | Cube recompute | Cube record | Cone recompute | Cone record |
|---|---|---|---|---|
| first pass at a multiple of 5 (trigger) | 1830 | 1830 | 725 | 725 |
| first pass at any iteration | 1829 | 1829 | 724 | 724 |
| log.gated first "wt gate N: converged" | 1830 | | 725 | |
| written (trigger + 1) | 1831 | 1831 | 726 | 726 |
| band at written, % | 0.1706 | 0.1706 | 0.2072 | 0.2072 |
| p_initial at written | 9.819e-4 | 9.819e-4 | 9.606e-4 | 9.606e-4 |
| Cd window mean | 1.149780 | 1.149780 | 0.583268 | 0.583268 |
| Cd window min / max | 1.14902 / 1.15098 | same | 0.58257 / 0.58378 | same |
| Cd mean 1801-2000 | 1.148728 | 1.148728 | 0.582195 | 0.582195 |

All agree to more than 4 significant figures (identical to the printed precision).

## 5. Coefficient definitions and FO vs face sum: PASS

`export_field.verdict_record`: `qa = 0.5 rho U^2 A_frontal`; Cd from fx, Cs from fy, Cl from fz,
each mean/min/max over the window divided by qa; forces as window means in N. The forces FO uses
`rhoInf` = `Setup3D.rho` and export uses `--rho` from the same Setup3D, so N and Cd share one rho.

Last-iteration drag at the written time (forces_gated.json face sum vs `force.dat` total_x):

| | face sum (N) | forces FO (N) | difference |
|---|---|---|---|
| Cube, 1831 | 1126.158 | 1126.191 | -0.033 N (-0.003 %) |
| Cone, 726 | 447.183 | 447.158 | +0.025 N (+0.006 %) |

## 6. Panel: PASS

- `results.verdict_lines`: not converged gives "Not converged:" and the reasons only. A forces.json
  without a `converged` key gives "no convergence record (before 0.4.3):", "Solve 3D again".
- `__init__.py:742-748` still copies the last-iteration `Cd`, `drag_N` etc. into `p.cd3d`, `p.drag`
  when not converged, but no panel code draws `cd3d`, `cl3d`, `drag`, `lift` or `side` (grep over
  the add-on): only the verdict lines are drawn (`:1073-1076`). Observation, not a FAIL: the values
  are visible through the Python API only.
- `field_state` returns "solved" only when `p.converged3d`, otherwise "unconverged" (`:805`).

## 7. `results.progress`: PASS

It splits the 8 kB log tail on `Time = N` and returns the first `Solving for p, Initial residual`
of the last block that has one, i.e. the first p solve. 2D effect: the 2D panel's residual readout
now shows the first of the two p solves per iteration (the larger one with
`nNonOrthogonalCorrectors 1`) instead of the last; display only, no 2D gate depends on it.
Minor: the iteration comes from the last `Time =` line, the residual from the last block that
has a p solve, so for a moment while an iteration starts they are one iteration apart.

## 8. Tests: PASS

`py -m unittest discover -s tests`: 70 run, OK (expected failures=3). No `bpy` in case, case3d,
meshgen, results, flowfield, export_field, wsl, convergence.

## 9. Text hygiene and version: PASS

- Em dash (U+2014) in lines added since 572e999~1 (all step 2 commits): 0. Positive control: the
  same byte grep on a printed U+2014 counts 1. No tracked file under wind_tunnel, tools, docs,
  validation or SESSION_LOG.md contains one.
- `git ls-files --eol`: all 58 tracked files `i/lf`.
- `blender_manifest.toml` version "0.4.4", `bl_info` (0, 4, 4).

## 10. Path-dependence claim: PASS

SESSION_LOG.md (stages 4 and 5 entry) and `change_vs_400_iterations.note` in the json both say the
1.2624 value is from the other STL triangulation (359,240 cells), that the 400-iteration Cd differs
by about 35 % between the two meshes, that the commit headline "-8.9 %" compares across meshes
(+42 % against this run's own 400 value), and that the gated value's path independence was not
tested (one gated run per body). The 382cc23 headline itself cannot be changed; the log corrects it.

## 11. Gated path independence, Cube_tri2: PASS

Build (2026-10-21): `~/wind_tunnel/_step2/Cube_tri2` from `_step2/Cube`'s inputs only (Allrun,
convergence.py, export_field.py, 0.orig, system, constant/transportProperties and
turbulenceProperties; no polyMesh, no time directories), with the binary `body.stl` (12 triangles,
684 bytes) from `_step1/Cube/constant/triSurface`. `_step2/Cube/system/controlDict` had been edited
by the tracer's continuation (gate and stop removed, endTime 2000), so controlDict was regenerated
with `case3d.write_system` (0.4.4, iterations 3000, write_every 100, procs 24). The other generated
files (fvSchemes, fvSolution, decomposeParDict, transportProperties, turbulenceProperties) are
byte-identical to `_step2/Cube`'s; the controlDict differs from Cube's only in formatting, the
restored gate and stop FOs and endTime 3000. Run: `bash tools/audit/step2_tracer.sh Cube_tri2`
from WSL (24 ranks, COARSE), 23:29 to 23:37 gated, continued to 2000 by 23:40.

| | Cube (Stage 5) | Cube_tri2 (this review) |
|---|---|---|
| cells (checkMesh) | 359,618 | 359,597 |
| gate trigger / written | 1830 / 1831 | 1360 / 1361 |
| offline first pass, every 5 / any (step2_check.py and own recompute agree) | 1830 / 1829 | 1360 / 1358 |
| band at written, % | 0.171 | 0.152 |
| p residual at written | 9.82e-4 | 9.84e-4 |
| Cd window mean (min to max) | 1.14978 (1.14902 to 1.15098) | 1.14957 (1.14886 to 1.15061) |
| Cd mean 1801-2000 (ungated continuation) | 1.14873 | 1.14785 |
| forces FO Cd at 400 | 0.809 | 1.273 |
| gate open at 400 / 800 | yes / yes (band 33.6 %, 42.2 %) | yes / yes (band 49.1 %, 3.5 %) |

Difference of the gated Cd: (1.149570 - 1.149780) / 1.149780 = **-0.018 %**, inside the PASS band
1.1441 to 1.1555 (0.5 % of 1.1498). The late means differ by -0.076 %. At 400 iterations the two
meshes give 0.809 and 1.273 (a factor 1.57); through the gate they agree to 0.02 %, although the
stops are 470 iterations apart. So on these two meshes the gate removes the path dependence of the
reported Cd. Two gated runs on near-identical COARSE meshes test sensitivity to the triangulation,
not mesh convergence, and say nothing about agreement with experiment.

Note: the same STL gave 359,240 cells in step 1 and 359,597 here (same snappy settings; parallel
snappyHexMesh is not guaranteed to give the same mesh twice). So Cube_tri2 is a third mesh, not a
repeat of the step 1 mesh. That does not weaken the test: it is still a different mesh.

Recorded in `validation/step2_gate_v2512.json` under `cases.Cube_tri2` (step2_check.py output
plus `date`, `what`, `note_cells`, `vs_Cube`); one sentence appended to
`change_vs_400_iterations.note`, which said the gated value was untested. No other numbers changed.

## Glossary

- *Convergence gate*: the rule in `convergence.py` that declares a steady run converged at
  iteration n when the drag band, the p residual and n >= 400 all pass.
- *Window*: the 200 iterations n-199..n over which the band and the reported means are taken.
- *Band*: (max - min) / abs(mean) of the drag force over the window; must be below 0.5 %.
- *Initial residual*: OpenFOAM's normalised residual of the p equation before the linear solve of
  that iteration; the gate uses the first of the iteration's p solves.
- *Function object (FO)*: code OpenFOAM runs every time step inside the solver (`forces`,
  `solverInfo`, `systemCall`, `abort`).
- *Face sum*: export_field's own pressure plus viscous force integrated face by face over the body
  patch at the written time, independent of the forces FO.
- *Triangulation*: the set of triangles in the STL handed to snappyHexMesh; two triangulations of
  the same cube give slightly different meshes.
- *Path dependence*: the iteration history (and so a fixed-iteration snapshot) depending on small
  mesh differences rather than on the physics.
