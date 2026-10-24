# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-24 "T1 polish, smoke
streaks visible, add-on 0.6.1" entry that this one supersedes, is kept verbatim in
`docs/archive/session_log_2026-10.md`.

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
