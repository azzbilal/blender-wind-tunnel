# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-22 "ANIMATION A+B
closed" entry that this one supersedes, is kept verbatim in `docs/archive/session_log_2026-10.md`.

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
