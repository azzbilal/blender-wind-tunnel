Slice: FIX_PLAN step 3, wall treatment and surface resolution (prism layers sized from a target y+, curvature
refinement, y+ reported). Solver-side (case3d, export_field), so every number is checked against OpenFOAM's
definitions and a cited reference, and recorded in `validation/` with date, mesh size and iteration count.

STAGE 0 GATE: satisfied 2026-10-24. T1 review item 10 fixed (commit 48216f2, closure line in
docs/reviews/transient_t1_review.md); no open FAIL. Pending on Bilal: fast-forward main to
worktree-t1-review (then to worktree-step3-wall) from the main checkout; a worktree session cannot.

CONTEXT TO LOAD (stay well under 100k tokens)
CLAUDE.md; SESSION_LOG.md current entry; docs/FIX_PLAN.md step 3; docs/ACCURACY_AUDIT.md section 2 (wall
treatment) only; docs/reference/step2_convergence_reference.md (the gate); in wind_tunnel/case3d.py
`Setup3D`, `tunnel`, `snappy_dict`, `write_fields`, `write_case` (Allrun lines); `case.Setup.first_cell`.
Facts already established, do not re-derive:
- v2512 function objects work (`yPlus`, `forces`, `forceCoeffs`; tools/audit/step0_check.py). A run is solved
  only when the step 2 gate passes. Cp uses the inlet p_inf.
- Re = U L / nu = 20 x 2 / 1.5e-5 = 2.67e6 for the 2 m bodies. `first_cell` uses Cf = 0.026 / Re^(1/7)
  (3.14e-3) and returns y = y+ / (sqrt(Cf/2) Re): 4.73e-4 m for y+ = 50. CORRECTED in Stage 1: that is
  y/L (2D case: chord 1, U 1, nu = 1/Re); for L = 2 m it is 0.95 mm (u_tau 0.79 m/s). The source of the 0.026 coefficient
  is NOT verified (White's local value is 0.027 / Re_x^(1/7) from memory, unconfirmed); cite it in Q1 or
  replace the correlation by one with a checked citation.
- OpenFOAM's `yPlus` uses `nearWallDist`: face centre to cell centre, about half the first prism height.
  snappy's `firstLayerThickness` is the full height. So layer height = 2 y for a target centre y+.
  `meshgen.c_grid` uses `first_cell` as the full first cell height, so the 2D grid runs at about half its
  nominal y+ (logged, not fixed in this slice unless Bilal says so).
- snappy layer sizing takes exactly two of firstLayerThickness, finalLayerThickness, thickness,
  expansionRatio; with `relativeSizes false`, minThickness is in metres.
- The solved 3d_Cube, 3d_Sphere, 3d_Cone (v1912 fields at 400) and the step 2 Cube (359,618 cells, gated Cd
  1.1498 at 1830) all used COARSE: body level (2 3), wake 2, background L/6 = 0.333 m. Smooth sphere cells at
  level 2 are 83 mm: about 75 around the circumference (FIX_PLAN wants about 100). MEDIUM is (3 4), 2, L/8.
- Current layers: 2, relativeSizes true, finalLayerThickness 0.5, expansion 1.3. Audit y+ (min/mean/max):
  sphere 44/822/1269, cone 42/476/1467, cube 9/263/615.
- A 0.95 mm first layer next to a 15.6 to 83 mm surface cell is a 16 to 87x jump; the last layer should reach
  about half the adjacent cell: n = 1 + ln(ratio) / ln(r) layers.
- CORRECTED in Stage 1: `_t1/Cube/0` and `processor*/0` are NOT a converged field (uniform 0.orig, then
  potentialFoam -writep). No converged steady cube field is left on disk; every Stage 4 run starts from
  scratch. Stage 1 used the T1 URANS field at t = 2 s. Keep `_t1/Cube` untouched; work on copies.
OUT OF SCOPE: domain size (step 4), validation against experiment (step 5), IDW and cell centres (step 6),
the 2D far field (step 7).

STAGE 1 MEASURE (AFK)
On copies in `~/wind_tunnel/_step3`: run `yPlus` and `wallShearStress` post-hoc on `_t1/Cube` time 0 (converged
cube) and on 3d_Sphere, 3d_Cone at 400 (unconverged v1912 fields: u_tau order of magnitude only, say so).
From the body faces, compute the area fraction with 30 < y+ < 300 as a function of the first cell-centre
distance, assuming u_tau unchanged (state it). This says whether 80 % in band is reachable for each body
and which y to aim for. Record in `validation/step3_wall_v2512.json`.

STAGE 2 GRILL (HIL): one question at a time, recommendation first, wait for Bilal's answer.
 Q1 Target y+ and first-layer formula: target centre y+ from the Stage 1 curves; the Cf correlation and its
    citation; layer height = 2 y. Also: is 30 the right lower bound for acceptance, given
    nutUSpaldingWallFunction is continuous in y+ and the cube's stagnation and separated faces have low u_tau?
 Q2 Layer count and expansion: n from the jump to about half the adjacent surface cell (for example 0.95 mm to
    15.6 mm at r = 1.3 gives about 12); nGrow, featureAngle, and what to do where snappy drops layers.
 Q3 relativeSizes false (absolute, needs a sane minThickness) vs true with snappy's fallback.
 Q4 Surface resolution: curvature refinement (v2512 `curvatureLevel` in refinementSurfaces, check the source)
    or a distance shell, to reach about 100 cells around the sphere; or switch the default to MEDIUM.
 Q5 Which cases to re-run (copies only), with cell counts and wall time from the step 2 runs (Cube 1830
    iterations at 360k cells), and whether the panel warning threshold is 80 %.
Lock the answers in `docs/reference/step3_wall_spec.md` (about one page) before any code.

STAGE 3 TDD (AFK), red then green, pure functions first
- `case3d` layer sizing: first layer height from target y+ (2 y), n and r from the adjacent cell, snappy dict
  text with exactly two sizing keys and metres when relativeSizes is false.
- Curvature or shell refinement text per Q4.
- Allrun runs the `yPlus` FO post-hoc after reconstructPar; `export_field` writes yplus min/mean/max and the
  area-weighted in-band fraction (face areas it already computes) into forces.json; layer coverage parsed from
  snappy's layer table in log.snappyHexMesh (`patch faces layers overall thickness`). Tests on synthetic text.
- Panel warning under the threshold (headless smoke check).

STAGE 4 TRACER (AFK)
Re-run the chosen bodies in `~/wind_tunnel/_step3` through the real Allrun to the step 2 gate. Record per body:
cells, layer coverage %, y+ min/mean/max and band fraction, gate iteration, Cd window mean and its change
against the step 2 value (cube 1.1498, cone 0.5833). Acceptance (FIX_PLAN): y+ band fraction >= 80 % and layer
coverage >= 90 % for sphere, cube and cone, or a recorded reason per Q1.

STAGE 5 CLOSE (AFK)
Tests green, py tools/deploy.py, headless smoke check, version bump in blender_manifest.toml and bl_info,
README note on wall treatment, commit with the physical quantity changed and by how much (y+ band fraction,
Cd change).

STAGE 6 HANDOFF (AFK)
SESSION_LOG.md entry (archive the previous one verbatim to docs/archive/), REVIEWER PROMPT to
`docs/reviews/step3_review.md` (push: layer height vs nearWallDist, Cf citation, band fraction recomputed
from the yPlus field independently, layer coverage from the log, gate passed on every re-run), NEXT PROMPT for
FIX_PLAN step 4 (domain).

Live Blender: any scene built by a script keeps Auto solve off and the handler paused while it exists
(pattern: tools/audit/t1_scene.py).
RULES: no sudo, no em dashes, asterisk terms plus glossary, never "validated" without a cited reference.
Stop at stage boundaries; no new heavy stage after about 150k tokens; hand off at about 200k; never compact.
