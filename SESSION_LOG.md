# Session log

Current state only. Every earlier entry, including the 2026-10-24 "FIX_PLAN step 3 closed (Stage 5 and 6), add-on
0.7.0 deployed" entry that held the PORTFOLIO NEXT PROMPT, is kept verbatim in `docs/archive/session_log_2026-10.md`.

## 2026-10-24: PORTFOLIO slice, add-on 1.0.0; project closed

Work on main. Spec: `docs/reference/portfolio_spec.md` (grill Q1 to Q7 plus Bilal's additions of the same day:
hero GIF under 10 MB, Mermaid diagram, highlights, "What I learned about OpenFOAM" draft, CHANGELOG, LICENSE,
version 1.0.0, cone secondary source). No solver-side change, no new run.

### Done (commits c074f09..8b1832f, then this handoff)
- c074f09 spec locked. 141369c `docs/media/`: `hero_transient_cube.gif` (cut from `renders/transient_t1_cube.mp4`,
  720 x 405, 120 frames at 83 ms, 128-colour global palette, no dither, 7.9 MB; built with Pillow via
  `uv run --with pillow` because the only ffmpeg on the machine is a 2013 build without `palettegen`) and three
  stills `cube_t0p5s/t1p0s/t2p0s.png` (copies of `renders/t1_still_030/060/120.png`). Not gitignored.
- e84a47d LICENSE (GPL-3.0 full text from gnu.org, md5 1ebbd3e3...) and `.github/workflows/tests.yml`
  (ubuntu-latest, Python 3.12, numpy + scipy, `python -m unittest discover -s tests -v`). Checked first under WSL
  python 3.12 on a `git archive` copy: 127 tests OK, 2 expected failures.
- d91e3c1 personal paths: CLAUDE.md, `docs/reviews/anim_ab_review.md` (3 places), `docs/reviews/transient_t1_review.md`
  now neutral. CLAUDE.md "Owner and how to talk to him" became "Working conventions" (biography line removed, rules
  kept), status line for 1.0.0, stale `_audit` note replaced.
- 2042c78 FIX_PLAN status block (steps 0 to 3 closed with date, version, record, review; 4 to 7 documented next
  steps). ACCURACY_AUDIT: a preamble and one status line per "What fails" finding, original text unchanged.
- 8b1832f version 0.7.0 -> 1.0.0 in manifest and `bl_info`; manifest tagline "Wind tunnel: OpenFOAM in WSL, flow
  field back in Blender", `bl_info` description updated, `website` = https://github.com/azzbilal/blender-wind-tunnel (repo renamed in README round 1).
  README rewritten; CHANGELOG.md 0.4.0 to 1.0.0 (version/date pairs from `git log -G'^version = '` on the manifest).
  Tests 127 OK (2 expected failures), `py tools/deploy.py` (14 files), headless smoke `ok: true`, version [1, 0, 0].
- WSL: `~/wind_tunnel/_step3` (5.0 GB) and `~/wind_tunnel/_t1` (5.4 GB) deleted (Q7).

### Findings and decisions
- The solved cone is 26.6 deg half angle, tip upstream (STL x -1 to +1 m, base radius 1.0 m; `3d_Cone` and the
  Stage B `run_Cone_d1` body.stl had the same md5). The 0.7.0 README said "30 deg"; corrected. FIX_PLAN step 5's
  "Cone 30 deg" is a planned case and stays.
- The aerospaceweb q0231 page (J. Scott, 2005) gives Cd 0.5 for a 30 deg cone from a table for Re 1e4 to 1e6 that it
  does not credit to Hoerner (only its cone-vs-angle graph is credited), and has no cube value. README shows it as
  a labelled context line for the cone with both mismatches and no percentage (Q5); the cube has no reference.
- README NACA 0012 table now shows the gaps: Cl -2.1 / -3.7 % at alpha 10 / 15, Cd +5.1 / +12.5 / +18.5 % at 0 / 10 / 15
  against `results.NASA_0012_SST`; alpha 15 misses both FIX_PLAN step 5 targets. The 2D sweep was solved with
  OpenFOAM v1912 (log header `OPENFOAM=1912 patch=200626`) and has no `validation/` record.
- The README's "What I learned about OpenFOAM" section and the last sentence of "How it was built" ("The
  engineering decisions, acceptance criteria and visual QA were mine.") are drafts in Bilal's voice for him to edit.

### Open issues
- HIL visual QA (Stage 5) of the rendered README: round 1 applied (30-second summary, Details moved to
  `docs/DETAILS.md`, OpenFOAM trade mark notice, Achenbach 1972 citation, repo renamed `blender-wind-tunnel`,
  method sentence); further rounds pending on Bilal. The Mermaid block is not render-tested locally.
- Push: Bilal's step (commands in the chat reply of this session). The CI badge and the manifest `website` assume
  the GitHub account `azzbilal`; change both if the repo lives elsewhere.
- The archived 0.7.0 entry (verbatim, `docs/archive/session_log_2026-10.md`) quotes the old user paths and the
  `azzbilal` website string; git history also keeps them (no rewrite, Q3a).
- `~/wind_tunnel/_step1` still exists in WSL (not in the Q7 list); can be deleted.
- Pending on Bilal: `sudo apt purge -y libopenfoam openfoam-examples` (orphaned 1912). Note the NACA sweep's
  only solve is a v1912 one; purging does not delete it.
- Next steps: `docs/FIX_PLAN.md` status block and steps 4 to 7; README "Next steps".

### NEXT PROMPT
Project closed at add-on 1.0.0. Next steps are documented in `docs/FIX_PLAN.md` (steps 4 to 7, status block at the
top) and the README "Next steps"; a future slice starts from FIX_PLAN step 4 with a new prompt in `docs/prompts/`.
