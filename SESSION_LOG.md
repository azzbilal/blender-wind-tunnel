# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-22 "Q3 and Q4
locked" entry that this one supersedes, is kept verbatim in `docs/archive/session_log_2026-10.md`.

## 2026-10-22: ANIMATION A+B, issue e fixed, Stage 3 done, stopped before Stage 4 (token budget)

### State
- FIX_PLAN steps 0 to 2 done and reviewed. Add-on version still 0.4.4 (0.5.0 at Stage 5 close).
  Deployed to Blender 5.2 after Stage 3: Bilal must restart Blender (or reload through the MCP) to load it.
- CLAUDE.md token rule now: end at stage boundaries, no new heavy stage after about 150k, hand off at
  about 200k (commit 6a8295f).
- Open issue e CLOSED (commit 6a8295f, record `validation/anim_ab_mask_e.json`). Cause, two ties:
  (1) column range rounding, dy = 0.04999999999999982 so (-1 - y0)/dy = 30.0000000000001 and ceil
  skipped the y = -1 and z = -1 columns; (2) a column on an x face's shared diagonal counted two
  crossings per face, so only the end nodes were filled. Fix: four offset rays per column
  (+-1e-3 dy, +-0.618e-3 dz) OR'ed, x span widened 1e-3 dx; surface nodes are solid on every face.
  Tests `SolidMask` (grid-aligned cube 41^3 = 68921 and mirror symmetric; cube at +-0.97 gives 39^3).
  `_anim/Cube` re-exported at t = 1831, no solve: mask 64000 -> 68921, spans -1.00..1.00 m on all
  axes, mirror symmetric in y and z; U and p unchanged except the 4921 added nodes (now 0, as every
  solid node). field.npz sha1 5868c18eb95212e0880898e04d211628a2771b29 (was ab5348ab).
  forces.json byte-identical (sha1 77061b3d, equal to forces_gated.json, Cd 1.1491410217993128).
  A fresh export rewrites the verdict block from the log history to 2000 (kept as
  `forces_1831e_verdict2000.json`); the gated record was put back, as in Stage 1. Backups in the case:
  `field_1831_pre_e.npz`, `forces_1831_pre_e.json`, `export_field_pre_e.py`.
  The Q3 figures (46 of 15000 deletions, drift) predate this mask; Stage 4 re-records them.
- Stage 3 pure (commit 1107faa): `wind_tunnel/anim.py` with `cp_to_ramp`, `CP_STOPS`
  (linear) and `CP_STOPS_SRGB`, `sweep_half_range`, `sweep_keyframes`, `slice_keep`, `label_text`
  (float32 like the nodes, so 0.85 / 2 prints +0.43), `legend_ticks`; tests `AnimPure`.
- Stage 3 Blender (commit 1e49285):
  - `write_vdb` adds grid `fluid` (1 fluid, 0 solid, background 0 outside the grid).
  - WT Slice: inputs Pressure, Cp Lo (-1), Cp Hi (+1). Ramp coordinate `show` = speed over
    0.3..1.9 or two clamped Map Range nodes summed (Cp 0 -> 0.5). Two materials, `WT Slice` (speed
    stops) and `WT Slice Cp` (9 Moreland stops), switched by Pressure (choice: two materials, the
    simpler one). Stores `show`, `cp`, `speed`. Clip: a vertex is kept only when the trilinear
    `fluid` value >= 0.999 (all 8 corners fluid and inside the grid). So the slice ends at the grid
    edge (closes open item b) and about one voxel (5 cm) off every body face, the same on all six
    faces; no colour is blended with the zeroed solid nodes. A loose vertex carries `cp_lo`,
    `cp_hi`, `pressure` for the overlays.
  - WT Legend (strip 2 L long, 257 x 2 vertices, at z = grid top + 0.2 L in the XZ plane through
    the body centre, facing -Y, ticks below) and WT Label (above it, "Slice y = +0.85 m (+0.43 L) |
    Cp") read those attributes through Object Info + Attribute Statistic, so they cannot disagree
    with the slice. Text: String to Curves + Format String (fmt syntax), material `WT Text`.
  - Panel (3D result box): Sweep X/Y/Z, "Animate slice", "Clear". `viz3d.animate_slice` writes one
    location key per frame (LINEAR), replaces old keys, rotates the plane for X / Z
    (`SWEEP_ROTATION`), sets frames 1..192 and the label's Axis.
  - Smoke: slide and push back only when Use Field is off (one Boolean NOT on Use Field). Preview
    slide band on Proximity Distance < 0.05 L, direction unit(P - nearest) (Q4). Push back unchanged.
    The audit script's unique values 0.05, 0.004, 0.02 are kept.
  - `_ramp` builds ColorRamp elements in order (Blender re-sorts); `_set_input` calls
    `mod.id_data.update_tag()` (without it a second input change was not re-evaluated).
  - Headless `tools/blender_smoke.py` (all pass): ramp read back = CP_STOPS; Cp mode materials
    slice [WT Slice Cp], legend [WT Slice Cp, WT Text]; kept vertices 39464 = `anim.slice_keep`;
    sampled Cp error 6.0e-8 on a linear Cp field (node placement exact); 17 label and tick strings
    equal the pure text; sweep y at frames 1/49/97/145/192 = -2.0/0/+2.0/0/-1.958333, 3 x 192 keys
    after a repeat, Clear restores rest; smoke one step: solved A, B, C all +0.0667 m in x (no slide,
    no push back); preview A (3 cm in front of the face) stops in x, B (-1.066, -1.467, -0.25) keeps
    +0.0667 (Q4), C (1 mm inside) ends at x = -1.008.

### Open issues carried
- a and b: fixed in Stage 3 (diverging Cp material; fluid-grid clip); confirm visually in Stage 4.
- c (step 1 review): inlet non-uniformity, stagnation line enters about 1.031 q; FIX_PLAN step 4.
- d: fixed for preview per Q4; concave-edge limit of the push back recorded, not solved.
- f (new, minor): the add-on's depsgraph handler hides WT Slice, WT Legend and WT Label unless the
  loaded field is the Test Object's solved one. Correct behaviour, but a tracer that calls viz3d
  directly sees nothing; use the load path below.
- g (new, minor): WT Legend and WT Label face -Y, placed for the default Y sweep camera; for X and Z
  sweeps they stay in place (not turned).

### NEXT PROMPT (ANIMATION A+B, Stage 4 tracer, then HIL stop)
Slice: ANIMATION A+B. Same structure: fresh session, bounded context, tracer on copies only, HIL
visual QA, then (after Bilal's rounds) Stage 5 close and Stage 6 handoff. Token budget per CLAUDE.md
(no new heavy stage after about 150k, hand off at about 200k, never compact). The grill is finished.

CONTEXT TO LOAD (nothing else):
- CLAUDE.md; this SESSION_LOG.md; `docs/reference/anim_ab_spec.md`.
- `sed -n 31,42p docs/prompts/anim_ab.md` (STAGE 4 to STAGE 6).
- `wind_tunnel/anim.py` (short). In `wind_tunnel/viz3d.py` only the names `build_slice`,
  `build_legend`, `animate_slice`, `build_smoke`, `tune_smoke`, `write_vdb`, `load_volume` (grep).
- `tools/blender_smoke.py` functions `_points` and `_smoke_steps` (how to read evaluated geometry).
- `tools/audit/anim_q3_drift.py` and `tools/audit/anim_q3_smoke.py` heads, to reuse for drift and
  the inside count.
- `wind_tunnel/__init__.py`: `WT_OT_load3d.execute` and `load_cached` only (grep).

Facts established, do not re-derive:
- Grid x -2.5 to 6.0 m, y and z +-2.5 m, h 0.05 m (171 x 101 x 101); cube -1 to 1 m, L = 2 m.
  `_anim/Cube` field.npz at t = 1831 with the fixed mask, sha1 5868c18e; forces.json sha1 77061b3d.
- Smoke: 24 fps, Time Scale 0.08, step 0.0667 m = 1.33 voxels per frame, about 150 particles per
  frame, Sample Grid Trilinear (default). Sweep Y: +-2.0 m, 192 frames, frame 97 at +2.0.
- Blender 5.2: read node-set materials from `ob.evaluated_get(dg).data`, not `to_mesh()`;
  Join Geometry puts the loose vertex last; modifier input changes need `update_tag()` (done in
  `_set_input`). Toggling the add-on does not reload modules: restart Blender or reload via the MCP.
- Windows Python reading `\\wsl.localhost` paths hung; copy with `wsl cp` to `/mnt/c/...` first.
  In Git Bash never leave a bare `cat > file` without a heredoc; long inline heredocs with nested
  quotes failed once, so write long patch scripts to the scratchpad first.

Stage 4 work (prompt lines 31 to 38 are the contract):
1. Load path: make a light copy `~/wind_tunnel/3d_AnimCube` with only `field.npz`, `forces.json`,
   `status` from `_anim/Cube` (no processor dirs). In Bilal's live Blender through the MCP: new scene
   "WT_ANIM" (`bpy.data.scenes.new`, never File > New, never touch his other scenes), a 2 m cube
   named "AnimCube" at the origin, then the add-on's load3d path so the handler shows the slice
   (open issue f). Scene colour settings per spec Q2: view transform Standard, look None, exposure 0,
   gamma 1, no bloom.
2. Press Animate slice (Y), play 1..192. Record in `validation/anim_ab_v2512.json` (date, mesh
   359618 cells, t = 1831): Cp at 3 probe points read from the slice's `cp` attribute vs trilinear
   field.npz within 1e-4; particles inside AnimCube (|x|, |y|, |z| < 1 m) over the whole animation,
   target 0, with the solid-mask count next to it (not gated); smoke vs RK4 drift over 1 L (max and
   mean, voxels) re-measured with the fixed mask; legend pixel colours at the 9 stops vs
   `anim.CP_STOPS_SRGB` within +-2/255 from a Standard-view render.
3. Render EEVEE, 1280 x 720, about 8 s, FFMPEG, to `renders/anim_ab_cube.mp4`; add `renders/` to
   `.gitignore`. Tell Bilal up front that the slice stops about one voxel (5 cm) off the body on
   every face, by design (no colour blended with solid nodes).
4. STOP (HIL): tell Bilal where the MP4 is and what to look at in the live viewport. Up to 3 rounds
   of small changes, re-render, stop again. Then Stage 5 and Stage 6 per the prompt; the Stage 6
   REVIEWER PROMPT must also check the issue e fix (`SolidMask`, `anim_ab_mask_e.json`).

RULES: no sudo. No em dashes. Asterisk technical terms and add a glossary. Never call a result
validated without a cited reference value. Keep SESSION_LOG.md to current state plus NEXT prompt;
move superseded entries verbatim to `docs/archive/`.
