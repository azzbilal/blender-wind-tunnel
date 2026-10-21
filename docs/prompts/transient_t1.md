Slice: TRANSIENT T1 (time-resolved cube flow shown on a fixed slice). A new solver path (pimpleFoam) plus the Blender side to play it. Steady simpleFoam stays the default and is not changed.

One line: pimpleFoam time-resolved solve of the cube, fixed WT Slice at y = 0 showing Cp per frame from a VDB sequence, smoke advected through the time-varying field, label with physical time and t U/L.

STAGE 0 GATE: `docs/reviews/anim_ab_review.md` exists and has no open FAIL. If it is missing, stop and tell Bilal.

CONTEXT TO LOAD (stay well under 100k tokens)
CLAUDE.md; SESSION_LOG.md current entry only; docs/reference/anim_ab_spec.md (Q1 to Q4, for what the slice, legend, label and smoke already do); docs/ACCURACY_AUDIT.md section 6 only. In code, grep only: `case3d.write_case` and its controlDict/fvSchemes/fvSolution writers, `export_field.py` main and `inlet_reference_pressure`, `viz3d.write_vdb`, `load_volume`, `build_slice`, `build_smoke`, `anim.label_text`. Do not read the 2D modules.
Facts already established, do not re-derive:
- Cube case `~/wind_tunnel/_anim/Cube`: 359618 cells, steady simpleFoam k-omega SST, gated at t = 1831 (window-mean Cd 1.14978), U_inf 20 m/s, L = 2 m, so L / U_inf = 0.1 s.
- field.npz grid x -2.5 to 6.0 m, y and z +-2.5 m, h 0.05 m (171 x 101 x 101), about 24 MB per export; solid mask closed on all six faces (issue e fixed, `validation/anim_ab_mask_e.json`).
- Cp = (p - p_inf) / (0.5 rho U_inf^2), p_inf = area-weighted mean static p on the inlet patch (FIX_PLAN step 1), subtracted in field.npz; forces use the raw p.
- v0.5.0: WT Slice samples Cp or speed from WT Flow at its vertices (equal to field.npz to 2e-8, `validation/anim_ab_v2512.json`); legend and label read the slice's inputs; smoke uses the midpoint rule through WT Flow, no slide in solved mode, still rule (speed < 0.02 U_inf) deletes stalled particles; 0 particles entered the cube over 192 frames.
- Blender 5.2: smoke positions are in the evaluated instances' `instance_transform` (the `position` attribute is not filled); keep the GeometrySet referenced while reading. Read node-set materials from `ob.evaluated_get(dg).data`. A modal render started through the MCP stops; a blocking `render.render(animation=True)` of 192 frames at 1280 x 720 took 34 s. FFMPEG output gets `0001-0192` appended; rename after.
- The add-on's depsgraph handler hides the slice, legend and label unless the loaded field belongs to the Test Object (issue f): tracers must use the add-on's load path.
OUT OF SCOPE: any change to the steady path's numbers (Cd, forces, gate, mesh), FIX_PLAN step 3 to 6, issue g.

STAGE 1 VERIFY (AFK)
Tests green, Blender MCP reachable, add-on 0.5.0, `pimpleFoam -help` runs in v2512. Measure and report (no decisions): smallest cell size and max Courant number at U_inf on the _anim/Cube mesh (checkMesh plus a one-step estimate), disk free in WSL, wall time of one simpleFoam iteration on 24 cores as a cost proxy.

STAGE 2 GRILL (HIL): one question at a time, your recommendation first, wait for my answer.
 Q1 Physics and solver: URANS k-omega SST from the steady 1831 field, or a scale-resolving model (DES / DDES), given the mesh is RANS-sized; time step by max Courant (number?) or fixed; start-up time discarded (how many L / U_inf) and the run length; a statistical-stationarity gate for a transient run (replacing the steady convergence gate), with a cited Strouhal number for a cube face on as the reference (find it, do not quote from memory).
 Q2 Output and storage: frames per convective time, total frames, field.npz per written time vs a slimmer per-frame export (Cp on the slice plane only, or U and Cp on the full grid), and a VDB sequence on disk vs regenerating; the disk budget.
 Q3 Blender side: a fixed WT Slice at y = 0 driven by the VDB sequence frame offset; smoke through the time-varying field (sample the current frame's grid, step size vs written time step); label "t = 0.123 s (1.23 L/U)"; the mapping scene frame -> physical time (real time slowed down by a stated factor).
 Q4 Visual items logged in ANIMATION A+B: section view (hide the body and smoke on the camera side of the slice) and smoke styling (plain white, fewer particles, short trails, so Cp is the only colour code). In this slice or later?
Lock the answers in docs/reference/transient_t1_spec.md (about one page) before any code.

STAGE 3 TDD (AFK), red then green, pure functions first
- Case writer for the transient run (controlDict with adjustTimeStep / maxCo or fixed deltaT, writeInterval, PIMPLE dict), tested as text like the steady case.
- frame -> time mapping and label text with t and t U/L (float32 like the nodes).
- Export per written time (names, units, p_inf per time step), tested on a synthetic case.
- Stationarity gate as a pure function on a Cd(t) history (synthetic sine plus noise).
- Headless Blender checks (extend tools/blender_smoke.py): a 3-frame synthetic VDB sequence, the slice shows frame k's Cp at frame k, smoke steps with the current frame's field.

STAGE 4 TRACER (AFK, then HIL)
Run the transient solve on a copy (`~/wind_tunnel/_t1/Cube`, never the original cases), gate it, export the frames. In a new scene "WT_T1" through the MCP (never File > New, never touch my other scenes), through the add-on's load path: record in `validation/t1_v2512.json` (date, mesh, time step, run length, Strouhal vs the cited reference, mean Cd vs the steady 1.1498, slice Cp vs that frame's field.npz at 3 probes within 1e-4 at 2 frames, particles inside the cube over the whole animation, target 0). Render 1280 x 720 EEVEE MP4 to `renders/t1_cube.mp4`. Then STOP (HIL): MP4 path and 3 things to look at. One round of changes, re-render, continue.

STAGE 5 CLOSE (AFK)
Tests green, py tools/deploy.py, smoke check, version 0.6.0 in blender_manifest.toml and bl_info, README section "Time-resolved flow" (honest about URANS vs resolved turbulence and the cost), commit. Through the MCP, remove WT_T1 and every datablock it created after checking my original scene is untouched. Keep `_t1` until the review passes.

STAGE 6 HANDOFF (AFK)
SESSION_LOG.md: done, grill decisions, numbers, open issues, a REVIEWER PROMPT (only solved data shown, frame k shows time k, Strouhal and Cd against cited values, slice equals field.npz, smoke never enters the solid, pure functions tested, no em dashes, LF endings; report to docs/reviews/t1_review.md) and the NEXT PROMPT (FIX_PLAN step 3 unless Bilal says otherwise).

RULES
Token budget per CLAUDE.md (end at stage boundaries, no new heavy stage after about 150k, hand off at about 200k, never compact). No sudo. No em dashes. Asterisk technical terms and add a glossary. Never call a result validated without a cited reference value; if a number is from memory, say so.
