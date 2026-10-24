# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-24 "FIX_PLAN step 3, Stage A
bundle done, amendments D1 to D3 locked, stopped before Stage B" entry that this one supersedes, is kept verbatim in
`docs/archive/session_log_2026-10.md`.

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
5. FIX_PLAN step 3 acceptance text updated to the two gates (spec Q5), with the Stage B numbers.
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
