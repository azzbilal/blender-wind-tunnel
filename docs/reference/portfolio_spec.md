# PORTFOLIO slice: locked answers (2026-10-24)

Slice prompt: SESSION_LOG NEXT PROMPT of 2026-10-24 (archived in `docs/archive/session_log_2026-10.md` at the
handoff), extended by Bilal's request of the same day. No solver-side changes, no new runs.

## Added by Bilal's request (not grilled, decided by him)

- Hero GIF under 10 MB and 2 or 3 stills in `docs/media/`; a Mermaid pipeline diagram; an "Engineering highlights"
  section; a "What I learned about OpenFOAM" section drafted for Bilal to edit.
- The five personal paths, the v0.4.0 banner and the "Airfoil polars" tagline fixed.
- LICENSE added: GPL-3.0-or-later, the licence the manifest already declares (`SPDX:GPL-3.0-or-later`).
- CHANGELOG from 0.4.0 to 1.0.0; add-on version 1.0.0 (replaces the 0.7.1 the slice prompt planned).
- Cube and cone may cite Hoerner, Fluid-Dynamic Drag, via aerospaceweb.org q0231 as a secondary source, labelled
  as such; otherwise they are shown as mesh-quality checks only.

## Grill answers

| Q | Topic | Answer |
|---|---|---|
| Q1 | Repository | `blender-openfoam-wind-tunnel`, public. Creating the repo and pushing are Bilal's steps; Claude prepares the commands. |
| Q3a | Workflow record | CLAUDE.md, SESSION_LOG.md, `docs/archive/`, `docs/prompts/`, `docs/reviews/` stay public as evidence of method. The absolute Windows user paths are replaced with neutral wording. Git history is kept as is (no rewrite). |
| Q3b | CLAUDE.md owner section | Kept, reworded neutrally as "Working conventions": the style and evidence rules stay, the biography line goes; machine specs stay. |
| Q4a | Hero GIF | Cut from `renders/transient_t1_cube.mp4` (two-pass palette, about 640 px wide). |
| Q4b | Stills | The three existing transient stills (`renders/t1_still_030/060/120.png`, t = 0.5, 1.0, 2.0 s). No cone render. |
| Q5 | Cone reference | Context line, no percentage gap (see below). Cube: mesh-quality check only. |
| Q6 | CI | GitHub Actions, ubuntu-latest, `python -m unittest discover -s tests`, after checking the suite passes under Linux. |
| Q7 | WSL cleanup | Delete `~/wind_tunnel/_step3` and `~/wind_tunnel/_t1`; keep the six original solved cases. |

## Q5 detail: what the secondary source says (fetched 2026-10-24)

aerospaceweb.org/question/aerodynamics/q0231.shtml, J. Scott, "Drag of Cylinders & Cones", 5 June 2005:

- Cd 0.5 for a cone of 30 deg half-vertex angle, tip into the flow, from the page's table "Drag coefficients of
  several simple 3D and 2D shapes", which covers Re 1e4 to 1e6.
- The page credits its cone-drag-versus-angle graph to Hoerner, Fluid-Dynamic Drag, with no page or figure number;
  the table itself is not credited to Hoerner.
- The page has no cube value, so the cube has no reference in this slice.

The solved cone is not that cone: measured from `~/wind_tunnel/3d_Cone/constant/triSurface/body.stl` (the same file,
same md5, as the Stage B `run_Cone_d1`), tip at x = -1 m, base radius 1.0 m at x = +1 m, so 26.6 deg half angle, tip
upstream; Re about 2.7e6 on the 2 m length at 20 m/s, above the table's range. Both Cd values use the base area
pi r^2 (our frontal area for a tip-upstream cone). The README states the 0.50 with both mismatches in the same
sentence and gives no percentage. The README's earlier "cone (30 deg half angle)" was wrong and is corrected.
