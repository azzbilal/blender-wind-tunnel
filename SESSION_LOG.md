# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-22 "ANIMATION A+B
closed" entry that this one supersedes, is kept verbatim in `docs/archive/session_log_2026-10.md`.

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
