# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-24 "TRANSIENT T1
closed (Stages 3 to 6), add-on 0.6.0" entry that this one supersedes, is kept verbatim in
`docs/archive/session_log_2026-10.md`.

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
  top face cuts into the cube geometrically. The -Y face hides it from the T1 camera; another view
  would show it.
- The recirculation bubble behind the cube is nearly empty of streaks by t = 2 s: upstream particles
  follow the shear layers. That is the flow, not a rendering fault; seeding inside the bubble is a
  styling question for a later slice.
- c, d, g, h as before (inlet non-uniformity; preview push back at concave edges; legend and label
  face -Y; section view).
- f, extended: the add-on has no load path for a time-resolved field; WT_T1 needs the Test Object
  handler suspended and Auto solve off (`tools/audit/t1_scene.py`). Panel integration is a later slice.
- j: URANS on this mesh does not sustain shedding; whether a finer mesh or DES would is untested.
- Review O2 (Moreland intermediates) still open.
- Disk: `~/wind_tunnel/_t1/Cube` 5.4 GB and `~/wind_tunnel/_anim` stay until the T1 review passes;
  `renders/t1_frames` (2.7 GB plus VDBs) is local scratch, regenerable.

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
