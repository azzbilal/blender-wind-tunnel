# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-22 ANIMATION A+B
Q2 entry that this one supersedes, is kept verbatim in `docs/archive/session_log_2026-10.md`.

## 2026-10-22: ANIMATION A+B, Q3 and Q4 locked, stopped before Stage 3 (about 100k tokens)

### State
- FIX_PLAN steps 0 to 2 done and reviewed (step 2 review 11/11 PASS). Add-on version 0.4.4.
- ANIMATION A+B (slice prompt `docs/prompts/anim_ab.md`): Stage 1 done; Stage 2 Q1 to Q4 locked in
  `docs/reference/anim_ab_spec.md`. Grill finished. No add-on code changed, no version bump, nothing
  created in Bilal's Blender (Q3 measurements ran in a separate headless factory-startup Blender).
- Data: `~/wind_tunnel/_anim/Cube`, root `field.npz` and `forces.json` are t = 1831 (Cd 1.149141,
  window mean 1.149780), field.npz sha1 ab5348ab5db01a7d31428bd72ed9ba4c9b3d46a1.
- Q3 (commits 7966571 measurements, fc0367a lock), numbers in `validation/anim_ab_q3_measure.json`:
  Python twin of the midpoint step matches Blender to 2.4e-6 voxel; smoke vs RK4 drift over 1 L,
  slide off: max 0.062 voxel near body, 0.008 freestream; slide on (shipped): 23.5 and 24.7 voxels
  (edge bug d). Slide off with the still rule: 0 particles in the cube over 100 frames, 46 of 15000
  deleted, all within 0.35 voxel of the wall. Decision: solved mode has no slide and no push back;
  the still rule (speed < 0.02 U_inf) is the solid-entry rule; Stage 4 metric is inside the Test
  Object (cube box), mask count reported, not gated.
- Q4: fix the preview-mode slide in Stage 3 (band on Proximity Distance, slide along unit
  (P - nearest), push back unchanged), with the headless cube test in the spec.
- Scripts: `tools/audit/anim_q3_smoke.py` (headless Blender recorder), `tools/audit/anim_q3_drift.py`.

### Open issues carried
- a: Cp uses the speed ramp (Cp = 0 shows yellow). Fixed by the Q2 design in Stage 3.
- b: slice faces deleted where sampled speed < 0.01 leave a ring short of the outline at the grid
  edge. Fixed by Stage 3 slice clipping.
- c (step 1 review): inlet non-uniformity, stagnation line enters about 1.031 q; FIX_PLAN step 4.
- d: slide edge bug (band uses the projection on one face normal next to an edge). Fixed in Stage 3
  per Q4 (preview mode); concave-edge limit of the push back recorded, not solved.
- e: export_field solid mask is one node layer short on the -y and -z faces (64000 nodes vs 68921
  for the closed box). Solver-side, for FIX_PLAN; not in this slice.

### NEXT PROMPT (ANIMATION A+B, Stage 3 TDD)
Slice: ANIMATION A+B. Same structure as before: fresh session, bounded context, TDD red then green,
pure functions first, tracer on copies only (`_anim`, scene WT_ANIM), HIL visual QA, close, handoff
with REVIEWER and NEXT prompts, stop at about 100k tokens and never compact. The grill is finished
(Q1 to Q4 locked); ask Bilal only if the spec leaves a choice open (for example the Stage 3 choice of
two materials vs two ramps for the Cp branch: pick the simpler one and say which).

CONTEXT TO LOAD (nothing else):
- CLAUDE.md; this SESSION_LOG.md; `docs/reference/anim_ab_spec.md`.
- `docs/prompts/anim_ab.md` lines 25 to 42 only (STAGE 3 to STAGE 6): `sed -n 25,42p docs/prompts/anim_ab.md`.
- `wind_tunnel/viz3d.py`: `_smoke_tree` (line 274 to `get_input`), `build_smoke`, `tune_smoke`,
  `_slice_tree` (line 476 to `remove_all`), `build_slice`, and the helpers they call.
  `wind_tunnel/viz.py`: `SPEED_STOPS`, `_ramp`, `_emission_material` only.
- `tests/test_pure.py`: only the imports and one existing test class, to match the style.
- `tools/blender_smoke.py` (short) to extend; `wind_tunnel/__init__.py` only the panel draw for
  the 3D result section and the operator pattern of one existing 3D button (grep first).

Facts established, do not re-derive:
- Grid x -2.5 to 6.0 m, y and z plus/minus 2.5 m, h 0.05 m (171 x 101 x 101), node lattice
  origin + h (i, j, k) as write_vdb places it; cube -1 to 1 m, L = 2 m; Cp (fluid voxels) -0.700 to
  1.025. Steady solve; every frame shows only solved data.
- Smoke: 24 fps, Time Scale 0.08, step 0.0667 m = 1.33 voxels per frame, 150 particles per frame,
  Sample Grid interpolation Trilinear (an input socket "Interpolation" in Blender 5.2, not a node
  property). Distribute seed = frame, so runs are reproducible.
- In `_smoke_tree`: band factor is the Math node with 0.05, margin 0.004, still rule the Compare
  node with 0.02 (unique values, `tools/audit/anim_q3_smoke.py` finds them this way).
- Toggling the add-on in Preferences does not reload modules: restart Blender or reload via the MCP.
- Headless Blender in Git Bash: never leave a bare `cat > file` without a heredoc in a command (it
  waits on stdin and hangs). Windows Python reading `\\wsl.localhost` paths hung; copy files to the
  scratchpad with `wsl cp` to `/mnt/c/...` first.

Stage 3 work (spec is the contract):
1. Pure, red then green in tests/test_pure.py: `cp_to_ramp(cp, lo, hi)` (Cp 0 -> 0.5, two-sided,
   clamped), the 9 Moreland stops as data (linear column of the spec table), `sweep_keyframes(axis,
   centre, half_range, frames, pingpong)` (192 frames, ends exactly at the limits, constant speed),
   slice clipping to grid bounds and the solid mask on a synthetic grid, label text formatting
   (`Slice y = +0.85 m (+0.43 L) | Cp`).
2. Blender code: Cp branch with its own diverging ramp, WT Legend, WT Label, Animate slice and
   Clear buttons, smoke tree: slide and push back only when Use Field is off, Q4 fix for preview.
3. Headless checks in tools/blender_smoke.py: diverging ramp in Cp mode, keyframes at the expected
   positions, solved-mode smoke has no slide (read the node values / switch), the Q4 cube test.
Then Stage 4 tracer per the prompt (Bilal's live Blender through the MCP, new scene WT_ANIM).

RULES: at about 100k tokens stop, write SESSION_LOG.md and tell Bilal; never compact. No sudo. No
em dashes. Asterisk technical terms and add a glossary. Never call a result validated without a
cited reference value. Keep SESSION_LOG.md to current state plus NEXT prompt; move superseded
entries verbatim to `docs/archive/`.
