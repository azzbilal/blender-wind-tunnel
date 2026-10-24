# ANIMATION A+B review: pressure slice sweep and smoke over the map

Date: 2026-10-23. Reviewer: Claude (fresh session), from the REVIEWER PROMPT in SESSION_LOG.md
(entry "2026-10-22: ANIMATION A+B closed").
Commits reviewed: 6a8295f (solid mask, issue e), 1107faa (anim.py pure rules), 1e49285 (Blender
side), 30c0e9b (Stage 4 tracer record), 8c3bebf (Stage 5 close, 0.5.0).
Read: CLAUDE.md, SESSION_LOG.md, docs/reference/anim_ab_spec.md, docs/prompts/anim_ab.md lines 31
to 42, wind_tunnel/anim.py, in wind_tunnel/viz3d.py `write_vdb`, `build_slice`, `build_legend`,
`animate_slice`, `build_smoke` (with `_smoke_tree`, `_slice_tree`, `_ramp_coord`, `_legend_tree`,
`_label_tree`), tests/test_pure.py classes `SolidMask` and `AnimPure`, validation/anim_ab_v2512.json,
validation/anim_ab_mask_e.json. Read-only except this file.

Independent re-runs (scripts outside the repo, in a local temp folder `wt_review_scripts\`,
on a copy of `~/wind_tunnel/_anim/Cube/field.npz` placed in a local temp folder `wt_review\`,
sha1 5868c18e as recorded):
- `probe.py`: headless Blender 5.2 factory startup, repo add-on code, real Cube field, WT Slice in Cp
  mode, `animate_slice("Y")`, evaluated slice at frames 13, 61, 100, 150 vs my own numpy trilinear*
  of p / q.
- `inside.py`: shipped WT Smoke tree in solved mode, real field, a 2 m cube, frames 1..192 in order,
  positions from depsgraph instance transforms.

**Result: 9 of 9 PASS, no FAIL open.** Three observations (O1 to O3) below; none needs a fix before
TRANSIENT T1.

| # | Item | Result |
|---|---|---|
| 1 | only solved data shown | PASS |
| 2 | slice values equal field.npz (re-run) | PASS |
| 3 | smoke never enters the solid; solved mode has no slide | PASS |
| 4 | diverging ramp centred on Cp = 0, stops, Moreland endpoints | PASS |
| 5 | issue e fix (SolidMask tests, anim_ab_mask_e.json) | PASS |
| 6 | pure functions tested first, tests green | PASS |
| 7 | Cp wording (no "outlet reference") | PASS |
| 8 | version 0.5.0, README honest about steady flow | PASS |
| 9 | no em dashes, LF endings, cited numbers | PASS |

## 1. Only solved data shown: PASS

- `animate_slice` writes keyframes on `location` only: `ob.keyframe_insert("location", frame=f)`
  (`wind_tunnel/viz3d.py:231`); the rotation for the sweep axis is set once without a key
  (`viz3d.py:224`). blender_smoke reads back 3 F-curves* of 192 keys each (`tools/blender_smoke.py`
  sweep_fcurves check).
- The slice tree samples `speed`, `cp`, `fluid` from WT Flow at the evaluated vertex position every
  evaluation (`viz3d.py:632`); Object Info in RELATIVE space puts the volume in the slice's object
  space, so a moved plane samples the field where it is. There is no time dimension in the data and
  no cache: a frame cannot carry values from another frame.
- Re-run (item 2) at frames 100 and 150, where the plane lies between voxel planes (y = 1.875 m,
  y = -0.2083 m), still matches the field to 7.2e-8 and 2.9e-7: the value is a spatial trilinear
  sample of the solved grid at the true position, nothing else.
- Smoke: velocity is `v2`, the field sampled at the midpoint (solved mode), `viz3d.py:473` switch;
  no invented velocity in solved mode (item 3).

## 2. Slice values equal field.npz: PASS (re-run)

`probe.py`, real Cube field (q = 0.5 x 1.225 x 20^2 = 245 Pa), comparison over every shown vertex
(not three probes):

| Frame | Slice y (m) | Key y (m) | Shown vertices | Pure `slice_keep` | max abs(cp_slice - cp_npz) |
|---|---|---|---|---|---|
| 13 | -1.5000 | -1.5000 | 43953 | 43953 | 8.1e-8 |
| 61 | +0.5000 | +0.5000 | 39464 | 39464 | 4.2e-7 |
| 100 | +1.8750 | +1.8750 | 43953 | 43953 | 7.2e-8 |
| 150 | -0.2083 | -0.2083 | 39464 | 39464 | 2.9e-7 |

Target 1e-4 (spec Q2, prompt Stage 4). Worst point (frame 61) at (-1.0, 0.5, -1.0625), next to the
body edge; the error is float32 rounding of the VDB grid. The shown-vertex count equals the pure
keep rule on the real mask at every frame, and 39464 equals the smoke-check figure in SESSION_LOG.
Cp range on the y = -0.2083 plane: -0.651 to 1.016; the value above 1 is open issue c (inlet
non-uniformity, `docs/reviews/step1_review.md`), not a slice error.

## 3. Smoke never enters the solid: PASS (re-run)

- Solved mode has no slide and no push back: one NOT on Use Field, `preview = NOT Use Field`
  (`viz3d.py:464`), ANDed into the slide gate (`viz3d.py:473`) and into the push-back selection
  (`viz3d.py:495`). blender_smoke counts exactly one such NOT (`use_field_nots == 1`) and my
  re-run counts 1 in the tree built by `build_smoke`.
- The still rule (`viz3d.py:505`) deletes particles where sampled speed < 0.02 U_inf, only with Use
  Field on, as locked in spec Q3.
- Counting method: positions from instance transforms of the evaluated WT Smoke instances, frames
  1..192 played in order with `scene.frame_set`, as recorded in `anim_ab_v2512.json`
  (`particles_inside.method`). Playing in order matters because the Simulation Zone* advances only
  frame to frame; the re-run does the same.
- Re-run (`inside.py`) result: 2477893 particle-frames, 0 inside |x|, |y|, |z| < 1 m, at most 19571
  alive. Both counts equal the record exactly (the release seed is the frame number, so the run is
  deterministic). Minimum gap outside the box 0.98 mm Euclidean, 0.734 mm as the largest per-axis
  gap (Chebyshev*); the record's 0.73 mm is the Chebyshev figure (O1).

## 4. Diverging ramp: PASS

- `cp_to_ramp` (`wind_tunnel/anim.py:42`) is two clamped maps summed: [lo, 0] to [0, 0.5] and
  [0, hi] to [0.5, 1]. Checked for (lo, hi) = (-1, 1), (-2, 1), (-1, 3), (-0.5, 2): Cp = lo, lo/2, 0,
  +-1e-9, hi/2, hi give 0, 0.25, 0.5, 0.5, 0.75, 1.0 every time; values beyond the ends clamp to 0
  and 1. The node tree builds the same sum of two clamped Map Range nodes (`viz3d.py:590`);
  blender_smoke checks node vs pure (`show_err_max < 1e-6`, `tools/blender_smoke.py:132`).
- Stops: `anim.CP_STOPS` (`anim.py:19`) equals the spec table, 9 stops at k/8, linear column; the
  linear column converted back to 8-bit sRGB* gives exactly `CP_STOPS_SRGB` (test
  `test_cp_stops_are_the_spec_table`, and my recompute). Stage 4 legend pixels: worst 1/255 against
  a tolerance of 2/255 (`anim_ab_v2512.json` `legend_pixels`).
- Moreland endpoints, cited: K. Moreland, "Diverging Color Maps for Scientific Visualization",
  Advances in Visual Computing (ISVC 2009), LNCS 5876, pp. 92 to 103. His page
  (https://www.kennethmoreland.com/color-maps/, fetched 2026-10-23) lists the cool/warm map as min
  (0.230, 0.299, 0.754), midpoint (0.865, 0.865, 0.865), max (0.706, 0.016, 0.150). Times 255:
  (58.65, 76.24, 192.27), 220.57, (180.03, 4.08, 38.25), which round to the spec's (59, 76, 192),
  (221, 221, 221), (180, 4, 38). The 7 intermediate stops are our own Msh* interpolation, as the
  spec says; I did not check them against Moreland's published 33-step table (O2).

## 5. Issue e fix: PASS

- `SolidMask` (`tests/test_pure.py:528`): grid-aligned cube gives spans (-1, 1) on all axes,
  41^3 = 68921 nodes, mirror symmetric in y and z (`:552`); cube at +-0.97 gives (-0.95, 0.95) and
  39^3 = 59319 (`:558`). Both pass.
- `anim_ab_mask_e.json` re-checked in WSL on `_anim/Cube` (`field_1831_pre_e.npz` vs `field.npz`):
  solid 64000 to 68921, 4921 added, 0 removed; U and p change at exactly 4921 nodes, 0 outside the
  added set, value 0 at all added nodes; origin, voxel, speed and p_inf_Pa identical.
- forces.json sha1 77061b3d equals `forces_1831_pre_e.json` (77061b3d): byte-identical, as recorded.

## 6. Pure functions first, tests green: PASS

- Order: 1107faa (anim.py and `AnimPure`, 00:56:42) before 1e49285 (Blender side, 01:06:49).
  `anim.py` imports only numpy. `AnimPure` covers ramp, stops, sweep keyframes (ends exactly at
  -1.9 and 2.1 for R = 2 about y = 0.1, constant step 4/96, mirror), half range clamp, keep rule
  (bounds, solid, symmetry), label and legend text.
- `py -m unittest discover -s tests -v`: "Ran 80 tests in 1.326s, OK (expected failures=3)".
- The red phase of `SolidMask` is not visible in history (O3).

## 7. Cp wording: PASS

`git grep -i outlet` outside docs/archive and docs/reviews: no file says the Cp reference is the
outlet. CLAUDE.md:76 says the solver fixes p = 0 at the outlet and Cp uses p_inf = inlet
area-weighted mean; README.md:45 to 46 the same. Remaining hits are boundary-condition text,
`p_inf_Cp_vs_outlet` (p_inf expressed against the outlet, correctly named, `export_field.py:273`),
and historical baseline keys (`validation/baseline_v0.4.0.json`), which describe the old
outlet-referenced value by name.

## 8. Version and README: PASS

- `wind_tunnel/blender_manifest.toml:4` `version = "0.5.0"`; `wind_tunnel/__init__.py:9`
  `"version": (0, 5, 0)`.
- README "Animating the result" (README.md:38 to 55): "The 3D solve is steady (simpleFoam): there is
  one flow field and it does not change in time. The animation only moves the viewpoint", and
  "Smoke paths are streamlines of a steady field, not a time-resolved wake: vortex shedding is not
  in the data." Its numbers (0 entries over 192 frames, within 0.06 voxel of RK4 over 1 L) match
  `anim_ab_v2512.json` (0, near-body max 0.0558).

## 9. Em dashes, LF, cited numbers: PASS

- Files changed by the five commits (15 files, `git diff --name-only 6a8295f~1 8c3bebf`) plus
  SESSION_LOG.md and the spec: 0 em dashes (U+2014), 0 en dashes; 0 em dashes on added lines of each
  commit diff.
- `git ls-files --eol`: i/lf w/lf for all 15; CR byte count 0 on anim.py, README.md,
  anim_ab_v2512.json. `.gitattributes` has `* text=auto eol=lf`.
- Numbers: every figure in the SESSION_LOG table appears in a committed record
  (`anim_ab_v2512.json`, `anim_ab_mask_e.json`); the Moreland reference is cited by paper and page.
  No "validated" claim found in the reviewed files.

## Observations (no fix required)

- O1. The Stage 4 inside-count script ran through the MCP and is not committed, and the record does
  not say the gap is the per-axis (Chebyshev) gap. The re-run reproduces every number, so this is a
  traceability point only. Suggest: commit such counting scripts under `tools/audit/` in T1 and
  name the gap metric in the JSON.
- O2. The 7 intermediate stops are our Msh implementation, not compared with Moreland's published
  CoolWarm 33 or 257-step table. A cheap check for a later slice.
- O3. `SolidMask` tests and the fix landed in one commit (6a8295f); the commit message states red
  then green, history cannot show it. Process note for TDD slices: commit the red test separately
  when practical.

Housekeeping: `~/wind_tunnel/_anim` can be deleted now that this review has no FAIL (SESSION_LOG
open issues). The reviewer's temp copy `wt_review\field.npz` (local temp folder) and
the two scripts can be deleted any time.

## Glossary

- *trilinear*: interpolation inside one voxel cell from its 8 corner nodes, weights linear in x, y, z.
- *F-curve*: Blender's animation curve for one property channel (here location x, y, z).
- *Simulation Zone*: Geometry Nodes construct that carries geometry from the previous frame to the
  next, so its state depends on playing frames in order.
- *Chebyshev gap*: max over axes of (|x_i| - 1); for a point outside an axis-aligned box it is at most
  the Euclidean distance to the box.
- *sRGB / linear*: display-encoded colour vs the linear-light values Blender's ColorRamp and
  emission use; the Standard view transform applies the sRGB curve.
- *Msh*: Moreland's polar form of CIELAB (magnitude, saturation, hue) used to interpolate a
  diverging map through a neutral midpoint.
