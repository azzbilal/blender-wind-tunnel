# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-22 ANIMATION A+B
stage 1 / Q1 entry that this one supersedes, is kept verbatim in `docs/archive/session_log_2026-10.md`.

## 2026-10-22: ANIMATION A+B, Q2 locked, stopped before Q3 (Bilal's call at 122k tokens)

### State
- FIX_PLAN steps 0 to 2 done and reviewed (step 2 review 11/11 PASS). Add-on version 0.4.4.
- ANIMATION A+B (slice prompt `docs/prompts/anim_ab.md`): Stage 1 done, Stage 2 Q1 and Q2 locked in
  `docs/reference/anim_ab_spec.md`. Q3 open. No add-on code changed, no version bump, nothing
  created in Blender.
- Data: `~/wind_tunnel/_anim/Cube`, root `field.npz` and `forces.json` are t = 1831 (Cd 1.149141,
  window [1632, 1831] mean 1.149780, all 35 keys equal `forces_gated.json`); the 2000 export is kept
  as `field_2000.npz` and `forces_2000.json`.
- Q2 (this session): diverging Cp ramp, lo/hi = -1/+1 two-sided around Cp = 0, Moreland cool-warm
  9 stops (endpoints cited, intermediates computed by our own Msh implementation), WT Legend in
  Geometry Nodes, and a pixel colour test at the 9 stops (plus/minus 2/255) in the Stage 4 tracer.
  The Cp 1.025 peak clamps to red; its cause is the step 1 review's inlet explanation (open issue c,
  FIX_PLAN step 4), not a new item.
- Housekeeping: older SESSION_LOG entries moved verbatim to `docs/archive/session_log_2026-10.md`.

### Open issues carried
- a: Cp uses the speed ramp (Cp = 0 shows yellow). Fixed by the Q2 design in Stage 3.
- b: slice faces deleted where sampled speed < 0.01 leave a ring short of the outline at the grid
  edge. Fixed by Stage 3 slice clipping (grid bounds and solid mask from field.npz).
- c (step 1 review): inlet non-uniformity, stagnation line enters about 1.031 q; FIX_PLAN step 4.

### NEXT PROMPT (ANIMATION A+B, resume at Stage 2 Q3)
Slice: ANIMATION A+B. Same structure as before: fresh session, bounded context, grill one question
at a time with recommendation first, TDD red then green, tracer on copies only (`_anim`, new scene
WT_ANIM), HIL visual QA, close, handoff with REVIEWER and NEXT prompts, stop at about 100k tokens
and never compact.

CONTEXT TO LOAD (nothing else):
- CLAUDE.md; this SESSION_LOG.md; `docs/reference/anim_ab_spec.md`.
- `docs/prompts/anim_ab.md` lines 25 to 42 only (STAGE 3 to STAGE 6), for example
  `sed -n 25,42p docs/prompts/anim_ab.md`. The RULES of that file are repeated below.
- `wind_tunnel/viz3d.py`: `_smoke_tree` (starts at line 274, ends before `get_input`) and
  `build_smoke` (line 455) only, plus the node helpers `_sample`, `_vmath`, `_vsw`, `_bool` if a
  line in `_smoke_tree` needs them. Do not read the slice tree, the solver modules or the archive.

Facts established, do not re-derive:
- Stage 0 gate passed, Stage 1 done, Q1 and Q2 locked (see spec). Do not re-export the field.
- Grid x -2.5 to 6.0 m, y and z plus/minus 2.5 m, h 0.05 m (171 x 101 x 101); cube -1 to 1 m,
  L = 2 m; Cp (fluid voxels) -0.700 to 1.025. The solve is steady; every frame shows only solved data.
- field.npz holds U, p (Pa), the solid mask, origin, voxel, speed (export_field.py, IDW from 4
  nearest cell centres). The WT Flow VDB holds grids velocity, speed (|U|/U_inf) and cp.
- WT Smoke: midpoint rule through the VDB; the surface slide acts within 0.05 L in both modes, plus a
  push back onto the surface within 0.004 L; particles are deleted when speed < 0.02, age >
  Lifetime, or farther than 6 L from the body centre. Audit section 6: IDW resampling leaks 10 to
  12 % divergence next to the wall, which is why the slide exists in solved mode.
- Toggling the add-on in Preferences does not reload modules: restart Blender or reload via the MCP.

Q3 work, measure first, then ask:
1. Particles entering the solid per 100 frames with the slide off: on a copy in a new scene
   WT_ANIM (never File > New, never touch Bilal's scenes), build the cube result, set the slide off
   (and the push back off), run 100 frames, count particles whose position falls in the field.npz
   solid mask (and inside the cube box as a cross-check). Report the count per 100 frames and as a
   fraction of particles released.
2. Smoke vs reference streamline drift over 1 L: integrate reference streamlines in Python with RK4
   on the same VDB data (trilinear on the voxel grid, step at most 0.1 voxel) from the particles'
   release points; compare with the smoke paths (midpoint rule, the add-on's time step) over 1 L of
   path length. Report max and mean drift in voxels, for paths that pass near the body and for
   freestream paths separately.
3. Ask Q3 with a recommendation from those numbers: slide off, slide limited to the first voxel
   layer, or kept; and delete particles that enter the solid mask. Lock the answer in the spec.
Then Stage 3 (TDD) per the prompt's STAGE 3 section and the spec.

RULES: at about 100k tokens stop, write SESSION_LOG.md and tell Bilal; never compact. No sudo. No
em dashes. Asterisk technical terms and add a glossary. Never call a result validated without a
cited reference value. Keep SESSION_LOG.md to current state plus NEXT prompt; move superseded
entries verbatim to `docs/archive/`.
