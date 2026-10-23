FRESH SESSION. Slice: TRANSIENT T1 (time-resolved flow around the cube, shown on a fixed plane). First, overwrite docs/prompts/transient_t1.md with this prompt verbatim and commit it.
Read only CLAUDE.md, SESSION_LOG.md (last entry) and the functions you change.

STAGE 0 GATE (AFK): read docs/reviews/anim_ab_review.md. Close any FAIL in its own commit first (small fixes only); if a FAIL needs design work, stop and tell me.

FACTS: steady results come from simpleFoam (case3d.py) on the coarse cube mesh, about 359k cells, 20 m/s, L = 2 m, one flow-through L/U = 0.1 s. Steady gated Cd 1.1498 (not experiment-validated; FIX_PLAN steps 3 and 4 still open). The field export (export_field.py), the VDB writer (viz3d.write_vdb), the Cp diverging ramp, legend, label and the smoke tree from slice A+B exist and are tested. Cp uses p_inf = area-weighted mean static p on the inlet patch. Blender supports OpenVDB sequences (Volume datablock with is_sequence and a frame offset).

STAGE 1 VERIFY (AFK): tests green (80 run, 3 expected failures), MCP reachable, add-on 0.5.0.

STAGE 2 GRILL (HIL), one question at a time, recommendation first:
 Q1 Start: impulsive start from uniform flow (shows the wake forming), from the converged steady field (reaches shedding faster), or both in one run?
 Q2 Physical time and frames. Default for the first run: 2 s physical (20 flow-throughs), 120 frames, write interval to match; extend only if I ask after seeing it. Find and cite a Strouhal number reference for a cube in free stream before recommending, or say clearly that none was found.
 Q3 Solver settings: pimpleFoam with k-omega SST, time step from a stated Courant target, outer correctors, second-order time scheme (backward or CrankNicolson), write U and p only per frame. Include a measured cost estimate from a 20-step test.
 Q4 Honesty gates: time-averaged Cd over the settled window vs steady 1.1498 (report, no target claimed); if shedding appears, measured Strouhal number from the side-force signal vs the cited reference; mass conservation per written step; particles never inside the cube.
Lock the answers in docs/reference/transient_t1_spec.md.

STAGE 3 TDD (AFK), red then green: a pure transient case writer (pimpleFoam controlDict, fvSchemes, fvSolution per the spec); a frame index to physical time mapping; VDB sequence naming and loading; a headless Blender check that the slice samples the frame-matching VDB.

STAGE 4 TRACER (AFK, then HIL)
- Run the 20-step cost test, then STOP and show me the cost estimate before the full run (I approve anything over 30 minutes).
- Full run on a copy in ~/wind_tunnel/_t1/Cube.
- Speed: export frames in parallel across 16 to 24 processes; compute the solid mask once and reuse it for every frame.
- Scene WT_T1 through the MCP (never touch my other scenes): fixed WT Slice at y = 0 in Cp mode, smoke advected through the time-varying field, label with physical time and t U/L. Render to renders/transient_t1_cube.mp4.
- ONE HIL stop for my look: one round of changes, re-render once, then continue without stopping.

STAGE 5 CLOSE (AFK): tests, deploy, smoke check, version 0.6.0, README section "Time-resolved flow" (honest about URANS limits and the coarse mesh), clean up WT_T1 through the MCP after checking my original scene, commit.

STAGE 6 HANDOFF (AFK): SESSION_LOG.md entry with numbers, a REVIEWER PROMPT (report to docs/reviews/transient_t1_review.md), and the NEXT PROMPT = the kept FIX_PLAN step 3 "LATER PROMPT".

RULES: sessions end at stage boundaries; no new heavy stage after about 150k tokens; hand off at about 200k; never compact. No sudo. No em dashes. Asterisk technical terms with a glossary. Never call a result validated without a cited reference value.
