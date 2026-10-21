# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-22 "issue e fixed,
Stage 3 done" entry that this one supersedes, is kept verbatim in `docs/archive/session_log_2026-10.md`.

## 2026-10-22: ANIMATION A+B closed (Stage 4 tracer, HIL, Stage 5, Stage 6), add-on 0.5.0

### Done
- Stage 4 tracer (commit 30c0e9b, record `validation/anim_ab_v2512.json`). Light copy
  `~/wind_tunnel/3d_AnimCube` (field.npz sha1 5868c18e, forces.json, status); in Bilal's live Blender a
  new scene WT_ANIM (Standard view, look None, exposure 0, gamma 1), 2 m cube "AnimCube", loaded through
  `wind_tunnel.load3d` (issue f), Pressure on, Animate slice (Y): y = -2 / 0 / +2 / 0 / -1.958 m at
  frames 1 / 49 / 97 / 145 / 192.
- Numbers (mesh 359618 cells, t = 1831):

| Check | Result | Target |
|---|---|---|
| Slice cp vs trilinear field.npz p/q, 3 probes (frames 49, 61, 85) | max 1.9e-8 | 1e-4 |
| Particles inside the cube, frames 1..192, 2477893 particle-frames | 0 (closest 0.73 mm) | 0 |
| Solid-mask nearest-node hits (not gated) | 11518 particle-frames, all within 0.025 m outside the wall | reported |
| Smoke vs RK4 drift over 1 L, near body (2206 paths) | max 0.0558, mean 0.0024 voxel | recorded |
| Same, freestream (794 paths) | max 0.0077, mean 0.0011 voxel | recorded |
| Headless 100 frames, still rule off, 15000 released | 0 enter the cube box (old mask: 1) | recorded |
| Legend pixels at the 9 stops vs `anim.CP_STOPS_SRGB` | worst 1/255 | +-2/255 |

  The probe Cp 1.019 at the front stagnation point is open issue c, not a slice error.
- MP4 `renders/anim_ab_cube.mp4` (EEVEE, 1280 x 720, 192 frames, H264; `renders/` ignored).
- HIL (Bilal): no visual changes to the sweep. He wants a fixed plane with the flow developing in
  time, which needs a transient solve: new slice TRANSIENT T1 (prompt `docs/prompts/transient_t1.md`).
- Stage 5 (commit 8c3bebf): tests 80 run OK (3 expected failures), deployed, headless smoke check
  ok (version 0.5.0, cp_err_max 6.0e-8, kept 39464 = pure), version 0.5.0 in both places, README
  "Animating the result" (steady flow stated). Cp wording fixed: CLAUDE.md said the Cp reference was
  the outlet; it is p_inf = area-weighted mean static p on the inlet patch (FIX_PLAN step 1). The
  `p_inf_Cp_vs_outlet` key in forces.json is p_inf expressed against the outlet and is correct as named.
  WT_ANIM and every datablock it created (8 objects, 5 meshes, 5 materials, 4 node groups, volume,
  camera, light, world, font, action) removed through the MCP after checking Bilal's "Scene" (Camera,
  Cube, Light, transforms, AgX, frames 1..250) was unchanged; `~/wind_tunnel/3d_AnimCube` deleted.
  The live Blender has the 0.5.0 modules loaded (reloaded through the MCP).

### Grill decisions (locked, `docs/reference/anim_ab_spec.md`)
Q1 sweep Y default, +-1 L, 192 frames ping-pong, keyframes on location only; Q2 diverging Moreland
ramp, Cp -1..+1 two-sided around Cp 0, legend and label in Geometry Nodes; Q3 solved mode no slide,
still rule kept, inside count gated on the body box; Q4 preview slide on true distance.

### Open issues
- c (step 1 review): inlet non-uniformity, stagnation line enters about 1.031 q; FIX_PLAN step 4.
- d: concave-edge limit of the preview push back, recorded, not solved.
- f: handler hides slice, legend and label unless the field is the Test Object's (by design; tracers
  use the load path).
- g: WT Legend and WT Label face -Y; for X and Z sweeps they are not turned. Open, not fixed.
- h (new, Bilal): section view, hide the body and the smoke on the camera side of the slice.
- i (new, Bilal): smoke styling, plain white, fewer particles, short trails, so Cp is the only colour code.
- h and i are Q4 of the TRANSIENT T1 grill.
- `~/wind_tunnel/_anim` can be deleted once the ANIMATION A+B review passes.

### REVIEWER PROMPT (ANIMATION A+B review, fresh session)
Slice: review of ANIMATION A+B (commits 6a8295f, 1107faa, 1e49285, 30c0e9b, 8c3bebf). Read-only
except the report. Save the report to `docs/reviews/anim_ab_review.md` with one PASS / FAIL line per
item and the evidence (command, number, file:line).

CONTEXT TO LOAD: CLAUDE.md; this SESSION_LOG.md; `docs/reference/anim_ab_spec.md`;
`docs/prompts/anim_ab.md` lines 31 to 42; `wind_tunnel/anim.py`; in `wind_tunnel/viz3d.py` only
`write_vdb`, `build_slice`, `build_legend`, `animate_slice`, `build_smoke` (grep); `tests/test_pure.py`
classes `AnimPure` and `SolidMask`; `validation/anim_ab_v2512.json`, `validation/anim_ab_mask_e.json`.
Facts established, do not re-derive: the numbers table above; the solve is steady.

Push on:
1. Only solved data shown: no frame interpolates or invents field values (keyframes move the plane only).
2. Slice values equal field.npz: re-run one probe yourself headless (synthetic or the _anim/Cube
   field copied to /mnt/c first; Windows Python hangs on `\\wsl.localhost`).
3. Smoke never enters the solid: check the counting method (instance_transform, frames in order) and
   that solved mode has no slide (one NOT on Use Field).
4. Diverging ramp centred on Cp = 0 for asymmetric lo/hi too (`cp_to_ramp`), stops equal the spec table,
   Moreland 2009 endpoints cited.
5. Issue e fix: `SolidMask` tests (41^3 = 68921, mirror symmetric, cube at +-0.97 gives 39^3) and
   `anim_ab_mask_e.json` (forces.json byte-identical, only the 4921 added nodes changed).
6. Pure functions tested before Blender code; tests green (`py -m unittest discover -s tests -v`).
7. Cp wording: no file outside `docs/archive` and `docs/reviews` says the Cp reference is the outlet.
8. Version 0.5.0 in `blender_manifest.toml` and `bl_info`; README section honest that the flow is steady.
9. No em dashes in files changed by these commits; LF line endings; cited numbers only.
RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference.

### NEXT PROMPT (TRANSIENT T1)
Run `docs/prompts/transient_t1.md` (structure as `docs/prompts/anim_ab.md`). Stage 0 gate:
`docs/reviews/anim_ab_review.md` with no open FAIL. Load only what that prompt lists and take its
"facts already established" as given. Token budget per CLAUDE.md. One line: pimpleFoam time-resolved
solve of the cube, fixed WT Slice at y = 0 showing Cp per frame from a VDB sequence, smoke advected
through the time-varying field, label with physical time and t U/L.

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
