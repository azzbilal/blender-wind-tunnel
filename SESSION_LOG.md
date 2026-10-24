# Session log

Current state and the NEXT prompt only. Every earlier entry, including the 2026-10-24 "FIX_PLAN step 3, Stage B
done (D1 and D2 coded, three re-runs recorded), stopped before Stage 5" entry that this one supersedes, is kept
verbatim in `docs/archive/session_log_2026-10.md`.

## 2026-10-24: FIX_PLAN step 3 closed (Stage 5 and 6), add-on 0.7.0 deployed; project moves to the PORTFOLIO slice

Work is on main. Step 3 is closed without a separate review session (Bilal's decision, 2026-10-24, recorded in
FIX_PLAN step 3). The project is ending as a GitHub portfolio piece: FIX_PLAN steps 4 to 7 are documented next
steps, not scheduled work. The next and last slice is PORTFOLIO (NEXT PROMPT below).

### Done (commit 24ac156, then this handoff)
- Tests: 127 run, OK (2 expected failures, pre-existing).
- Version 0.6.1 -> 0.7.0 in `wind_tunnel/blender_manifest.toml` and `bl_info`; `py tools/deploy.py` (14 files,
  `dist/wind_tunnel.zip`); headless smoke check `ok: true`, `version` [0, 7, 0], wall panel pass row and FAIL row
  with "Cause: cut layers (15 % of area)". Deployed twice (the second after the docstring edit), same result.
- README: new subsection "Wall treatment (v0.7.0)" under "3D, any closed mesh": y+ target 100 at the first cell
  centre, h1 = 2 y_c in metres, n = min(n_half, n_depth), uniform body level (3 3) COARSE / (4 4) MEDIUM, the two
  gates, the cause row, no automatic re-mesh (the one tried took the cone 82.0 -> 75.5 %), cube and cone Stage B
  numbers stated as mesh-quality checks, not a comparison with experiment, the sphere's state at Re 2.67e6 (no
  steady state on the gate-passing mesh, no Cd). The drag-crisis Re (about 3e5 to 4e5) is from memory and says so.
- FIX_PLAN step 3: amendments D1 to D3 summarised, final acceptance (both gates on every body re-run) with the
  Stage B table, and the note that steps 4 to 7 are documented next steps.
- `docs/reference/step3_wall_spec.md` D2: note that the "0 %" design-height share held for the five runs listed;
  the Stage B sphere has 0.15 % (`gt300_design_first_cell` 0.0015, thick share 4.30 %), the first nonzero one,
  from the unconverged snapshot at 3000, so not evidence of a u_tau-driven failure; cube and cone Stage B 0 %.
- `results.wall_lines` docstring names the D2 cause row and the rule (thick >= design gives "cut layers").

### Numbers (Stage B, COARSE, body level (3 3), 24 ranks, cap 3000, step 2 gate, 2026-10-24)

| | Cube | Cone | Sphere |
|---|---|---|---|
| Cells | 437,192 | 383,135 | 388,788 |
| Gate | converged at 786 | converged at 716 | not converged at 3000 (D3) |
| Cd window mean | 1.1448 (step 2 1.1498, -0.43 %) | 0.5846 (step 2 0.5833, +0.23 %) | none reported |
| y+ <= 300 (gate 90 %) | 99.8 % | 96.95 % (Stage 4 82.0 %) | 95.6 % (snapshot) |
| Layer coverage (gate 90 %) | 100 % | 98.4 % | 99.2 % |
| y+ > 300 split thick / design | 0.18 / 0 % | 3.05 / 0 % | 4.30 / 0.15 % |

Full table: archived entry and `validation/step3_wall_v2512.json` key `stageB_rerun_2026_10_24`.

### No REVIEWER PROMPT
Skipped by Bilal's decision (2026-10-24). The review items that the previous NEXT PROMPT listed (layer height vs
nearWallDist, Cf citation status, band and y+ <= 300 fractions recomputed from the yPlus field, coverage from
log.snappyHexMesh, the cut-layer mechanism against snappyLayerDriver.C:4171-4181, the D2 split recomputed, the
sphere attribution, the `level (lo2 lo2)` writer ignoring `surface_levels[0]`) stay unchecked by an independent
session; the README and FIX_PLAN must not imply otherwise.

### Open issues
- Stale for a portfolio reader (PORTFOLIO item, not patched here): README banner "Status (v0.4.0): ... not yet
  physically reliable"; README transient section "(FIX_PLAN steps 3 and 4)" where the reference comparison is now
  step 5; FIX_PLAN title "work in this order" with no status line; `docs/ACCURACY_AUDIT.md` (v0.4.0) does not mark
  which findings steps 1 to 3 closed; manifest tagline "Airfoil polars from OpenFOAM running in WSL" (3D is the
  main feature now).
- Personal strings in tracked files (`git grep -i -E "bgare|gmail|azzbilal"`, archive excluded): `CLAUDE.md:40`
  (`C:\Users\bgare\Documents\WindTunnel`), `docs/reviews/anim_ab_review.md:13,14,169` and
  `docs/reviews/transient_t1_review.md:17` (local temp paths), `wind_tunnel/blender_manifest.toml:9` (website
  `https://github.com/azzbilal`). The archive has none. CLAUDE.md also holds the "Owner and how to talk to him"
  section, the WSL user name and machine details.
- No git remote, no LICENSE file (the manifest already says `SPDX:GPL-3.0-or-later`). `renders/` is gitignored:
  `anim_ab_cube.mp4` 4.8 MB, `transient_t1_cube.mp4` 4.5 MB, `t1_still_030/060/120.png` about 0.9 MB each,
  `t1_frames/`. `validation/` is 14 MB (largest `reference_case_3d_Cube/` 6.5 MB), inside GitHub limits.
- Carried as documented next steps (FIX_PLAN 4 to 7 and logged items): domain study and blockage (4); validation
  set against cited references, cube mesh study with Richardson extrapolation, Bernoulli check (5); cellPoint
  sampling, cell centres from `C` (T1 O1), longer voxel grid (6); 2D far-field correction and the `meshgen.c_grid`
  half-y+ bug (7); URANS fallback with time-averaged forces for bodies like the sphere (D3); guarded u_tau re-mesh
  (D2); MEDIUM cost under D1 not measured; coarse-STL warning; UV sphere zero-layer faces; Suzanne layer collapse
  and checkMesh skewness 4.70; T1 items k, O2, O3, c, d, g, h, f, j; ANIMATION A+B review O2;
  `tools/audit/step3_diag.py` variants with `surface_levels (2, 3)` no longer reproduce the Stage A V0 mesh.
- WSL disk: `~/wind_tunnel/_step3` (run_Cone, diag/bundle.json, `run_*_d1`) was kept for the step 3 review, which
  will not happen; it can go unless PORTFOLIO wants cone or sphere renders from it (each `run_*_d1` holds a
  `field.npz`). `~/wind_tunnel/_t1/Cube` likewise.
- Pending on Bilal: `sudo apt purge -y libopenfoam openfoam-examples` (orphaned 1912).

### NEXT PROMPT (PORTFOLIO: make the repository a GitHub portfolio piece, final slice)
Slice: PORTFOLIO. Turn this repository into a public GitHub portfolio piece that an aerospace or CFD reader can
judge in two minutes: what it does, a picture, what is checked against what, what is not, and what comes next.
No solver-side changes (case3d, case, meshgen, export_field, results logic) and no new runs. FIX_PLAN steps 4 to
7 are written up as documented next steps, not done. Work on main (no worktree).

STAGE 0 GATE: waived. Step 3 has no review by Bilal's decision (2026-10-24, recorded in FIX_PLAN step 3); every
earlier review in `docs/reviews/` has no open FAIL.

CONTEXT TO LOAD (stay under 60k tokens): CLAUDE.md; this entry; `README.md`; `docs/FIX_PLAN.md`; headings and
the "What fails" list of `docs/ACCURACY_AUDIT.md`; the file list of `docs/reviews/`, `docs/reference/`,
`validation/` (names only, open a JSON only for a number the README quotes); `wind_tunnel/blender_manifest.toml`.
Facts established, do not re-derive: everything in this entry (Done, Numbers, Open issues, including the personal
strings list and media sizes); the README's 2D table is against NASA TMR (CFL3D, finest grid) and is the only
experiment-or-reference comparison with a citation in the repo; the transient section's numbers stand.

GRILL (HIL, before any edit: one question at a time, recommendation first, wait for Bilal; lock the answers in
`docs/reference/portfolio_spec.md`):
- Q1 Repository name and visibility. Recommend public, a descriptive name such as `blender-openfoam-wind-tunnel`.
  Creating the GitHub repo and pushing are Bilal's steps (outward-facing; `gh` is installed at
  `/c/Program Files/GitHub CLI/gh` but needs his login and his go); Claude prepares the commands.
- Q2 Licence. Recommend a LICENSE file with GPL-3.0-or-later, matching the manifest's SPDX field and Blender's
  add-on licensing (OpenFOAM itself is GPL-3; both from memory, say so).
- Q3 The AI-assisted workflow record (CLAUDE.md, SESSION_LOG.md, `docs/archive/`, `docs/prompts/`,
  `docs/reviews/`). Recommend keeping them public as evidence of method (spec, grill, TDD, independent review),
  replacing the absolute Windows user paths in the five places listed with neutral wording, keeping git history
  as is (no rewrite). Ask separately whether the "Owner and how to talk to him" section stays.
- Q4 Media. Recommend `docs/media/` (not ignored) with two or three PNG stills under about 1 MB each (one Cp slice,
  one smoke still from `renders/`) and one short GIF cut from `renders/anim_ab_cube.mp4` under about 5 MB; an mp4
  in the repo does not play inline in a README, so the full videos go to a GitHub release or stay local. Offer
  a cone still only if Bilal wants it (needs `~/wind_tunnel/_step3/run_Cone_d1/field.npz` and a headless render,
  the one heavy task allowed in this slice).
- Q5 Results the README may show. Recommend: the NACA 0012 table against NASA TMR as the one cited comparison;
  cube and cone as "both wall gates and the convergence gate pass, Cd 1.1448 and 0.5846, reference comparison is
  FIX_PLAN step 5"; the sphere as "no steady state at Re 2.67e6, no Cd". No Hoerner, ESDU or Achenbach number
  unless Bilal supplies the source and page; never "validated" or "in range" without a cited value.
- Q6 Optional CI: a GitHub Actions job running `python -m unittest discover -s tests`. Recommend trying
  ubuntu-latest (the pure modules have no bpy), falling back to windows-latest if `wsl.py` path tests need it.
- Q7 WSL cleanup: delete `~/wind_tunnel/_step3` and `~/wind_tunnel/_t1` after Q4 is answered (recommend yes,
  Bilal's go; keep the six original solved cases).

STAGES (after the grill):
1. README rewrite: one-paragraph summary; a picture; the pipeline diagram; "What is checked" (convergence gate,
   wall gates, Cp reference, continuity, the NASA TMR table) with each number's source file in `validation/`;
   "Known limits" (steady RANS, wall functions, coarse default mesh, sphere, IDW sampling); "Next steps" (FIX_PLAN
   4 to 7 in one line each, plus the URANS fallback and the 2D y+ bug); Install; Development; a short "How it was
   built" paragraph if Q3 keeps the workflow record. Fix the two stale items (v0.4.0 banner, "steps 3 and 4").
2. `docs/FIX_PLAN.md`: a status block at the top (steps 0 to 3 closed with dates, versions and review files;
   step 3 without review; 4 to 7 documented next steps). `docs/ACCURACY_AUDIT.md`: a status line per "What fails"
   finding (closed by step N, or open, pointing at the FIX_PLAN step); do not change the audit's original text.
3. Repository hygiene per Q2 to Q4: LICENSE, `docs/media/` and a `.gitignore` exception, the path wording, the
   manifest tagline (and `website` once the repo URL is known). A manifest change is an add-on change: bump to
   0.7.1 in both places.
4. Optional CI per Q6.
5. HIL visual QA: Bilal reads the README rendered locally (VS Code preview or the GitHub preview after his push)
   and judges; small rounds.
6. Close: tests green; if the add-on changed, `py tools/deploy.py` and the headless smoke check; commit in small
   steps ("no physical quantity changed"); give Bilal the exact `gh repo create` / `git remote add` / `git push`
   commands and wait for his go. Claude does not push.
7. Handoff: final SESSION_LOG entry (archive this one verbatim first) stating the end state of the project and
   where each next step is documented; no NEXT PROMPT needed beyond "project closed, next steps in FIX_PLAN".

RULES: no sudo, no em dashes, asterisk terms plus glossary in chat replies, never "validated" without a cited
reference and say when a value is from memory; no solver-side changes; nothing pushed or published without
Bilal's explicit go; stop at stage boundaries; no new heavy stage after about 150k tokens; hand off at about
200k; never compact.
