Slice: ANIMATION A+B (pressure slice sweep + smoke over the map). A visualisation feature, not a FIX_PLAN step. No solver or mesh changes.

STAGE 0 GATE: already satisfied (step 2 review 11/11 PASS, docs/reviews/step2_review.md). Skip.

CONTEXT TO LOAD (stay well under 100k tokens)
CLAUDE.md; SESSION_LOG.md last entry only; docs/ACCURACY_AUDIT.md section 6 only; wind_tunnel/viz3d.py (smoke tree, slice tree, write_vdb, load_volume). Do not read the solver modules.
Facts already established, do not re-derive:
- The solve is steady: the field does not change with time. Every animation must show only solved data; nothing may be invented between frames.
- WT Slice samples speed or Cp from the WT Flow VDB at its vertices; the Pressure toggle switches the two. It uses the speed colour ramp for Cp, so Cp = 0 shows as yellow (logged open item a).
- The coloured slice stops about 0.25 m short of its outline on the downstream and top sides because faces are deleted where sampled speed < 0.01 at the field.npz grid edge (open item b).
- WT Smoke advects particles through the VDB (midpoint rule). In solved mode the preview "surface slide" still bends velocities within 5 % of L of the body (audit section 6), because IDW resampling leaks 10 to 12 % divergence next to the wall.
- Data: the converged cube in ~/wind_tunnel/_anim/Cube (gated at 1831, window-mean Cd 1.1498; time dirs 1831 and 2000). Work only in _anim.
- Toggling the add-on in Preferences does not reload modules: restart Blender or reload through the MCP.
OUT OF SCOPE: unsteady flow (pimpleFoam), any change to forces, Cd, the gate or the mesh; FIX_PLAN step 6's cellPoint resampling (log anything relevant for it).

STAGE 1 VERIFY (AFK)
Tests green (70 run, 3 expected failures), Blender MCP reachable, add-on 0.4.4. Re-export field.npz and forces.json from time 1831 in _anim/Cube (keep the 2000 export as forces_2000.json / field_2000.npz) and confirm Cd matches forces_gated.json.

STAGE 2 GRILL (HIL): one question at a time, your recommendation first, wait for my answer.
 Q1 Sweep design: default axis (side to side along Y through the body, or front to back along X), range (for example plus/minus 1.5 L), duration in frames, ping-pong or one pass, and a panel button "Animate slice" that writes keyframes on WT Slice's transform (the slice samples at world positions, so moving the object is enough). Also: a small on-screen label with the slice position in metres and the quantity shown?
 Q2 Colour: a diverging ramp for Cp centred on 0 (blue suction, neutral freestream, red stagnation) with a stated range (for example -1.5 to 1.0); speed keeps its ramp; a legend object with tick values in the scene. Recommend the exact ramp stops.
 Q3 Smoke honesty: in solved mode, switch the surface slide off (or limit it to the first voxel layer) and delete particles that enter the solid mask instead. Measure first on the converged cube: particles entering the body per 100 frames without the slide, and drift of smoke paths from a reference streamline integrated in Python (RK4 on the same VDB data, small step) over 1 L. Recommend from those numbers.
Lock the answers in docs/reference/anim_ab_spec.md (about one page) before any code.

STAGE 3 TDD (AFK), red then green, pure functions first
- cp_to_ramp(cp, lo, hi) or equivalent: Cp = 0 maps to the neutral stop, ends clamp.
- sweep_keyframes(axis, centre, half_range, frames, pingpong): positions per frame, symmetric, ends exactly at the range limits.
- Slice clipping: trim the slice to the field grid bounds and the solid mask from field.npz, not by a speed threshold, so no ring of missing faces at the grid edge (fixes open item b). Test on a synthetic grid.
- Headless Blender checks (extend tools/blender_smoke.py): slice tree uses the diverging ramp in Cp mode, sweep keyframes exist at the expected positions, smoke tree in solved mode has the slide set per Q3.

STAGE 4 TRACER (AFK, then HIL)
On _anim/Cube, through the MCP, in a new scene "WT_ANIM" (never File > New, never touch my other scenes):
- Load the result, press the new Animate button, play frames 1 to the end.
- Record in validation/anim_ab_v2512.json: Cp at 3 probe points sampled from the slice equals field.npz within 1e-4; particle count inside the solid over the whole animation (target 0); smoke vs RK4 streamline drift over 1 L (max and mean, in voxels).
- Render a short EEVEE preview to D:\10_PROJECTS\aerodynamics blender openfoam\renders\anim_ab_cube.mp4 (FFMPEG from Blender, about 8 s, 1280x720); add renders/ to .gitignore.
Then STOP (HIL): tell me where the MP4 is and what to look at in the live viewport. I judge the look. Up to 3 rounds of my visual feedback; each round is a small change, re-render, stop again.

STAGE 5 CLOSE (AFK)
Tests green, py tools/deploy.py, smoke check, version 0.5.0 in blender_manifest.toml and bl_info, README section "Animating the result" (two short paragraphs, honest that the flow is steady), commit. Through the MCP, remove WT_ANIM and every datablock it created, after checking my original scene is untouched.

STAGE 6 HANDOFF (AFK)
Append to SESSION_LOG.md: done, grill decisions, numbers, open issues, a REVIEWER PROMPT (push: only solved data shown, slice values equal field.npz, smoke never enters the solid, diverging ramp centred on Cp = 0, pure functions tested, no em dashes, cited numbers, LF endings; report to docs/reviews/anim_ab_review.md), and a NEXT PROMPT for FIX_PLAN step 3 (wall mesh and y+).

RULES
At about 100k tokens stop, write SESSION_LOG.md and tell me; never compact. No sudo. No em dashes. Asterisk technical terms and add a glossary. Never call a result validated without a cited reference value.

Also add a section "Session workflow" to CLAUDE.md: every slice follows fresh session with bounded context and established facts, Stage 0 gate on the previous review, grill (one question at a time, recommendation first) before code, TDD red then green, tracer on copies only, HIL visual QA where appearance matters, close (tests, deploy, smoke, version bump, commit), handoff in SESSION_LOG.md with REVIEWER and NEXT prompts written in this same structure, reviewer in its own fresh session saving to docs/reviews/, stop at about 100k tokens and never compact. Commit it with the slice.
