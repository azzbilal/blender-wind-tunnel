# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-24 "FIX_PLAN step 3, Stages 1
to 4 done, stopped at the Stage 4 decision" entry that this one supersedes, is kept verbatim in
`docs/archive/session_log_2026-10.md`.

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
