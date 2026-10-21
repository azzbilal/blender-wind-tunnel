# Wind Tunnel: Blender add-on + OpenFOAM (WSL)

A Blender add-on that builds or takes a model in Blender, solves the air flow around it with
OpenFOAM running in WSL Ubuntu, and brings forces and the flow field back into Blender
(sidebar panel, surface pressure colours, Geometry Nodes smoke that samples the solved field).

**The goal of the current phase is physical accuracy, not features.** The reference for every
number is the math OpenFOAM solves (incompressible RANS, k-omega SST, wall functions) plus
published experimental data. Read `docs/ACCURACY_AUDIT.md` before changing solver-side code,
and work through `docs/FIX_PLAN.md` in order.

## Owner and how to talk to him

- Bilal, aerospace structures engineer (MSc), CFD coursework (Ansys CFX, Altair, own OpenFOAM
  cases). Knows the physics; explain CFD terms precisely, not simply.
- Never use em dashes in anything you write for him (code comments, docs, chat).
- When a reply uses technical terms, mark each with an asterisk and define them in a short
  glossary at the end of the reply.
- Never claim a result is "validated" or "in range" without a cited reference value. If a
  number is from memory, say so. A wrong confidence claim already happened once (cone Cd).

## Machine and toolchain (Windows)

- Windows, Claude Code runs commands in **Git Bash**. Python is `py` (3.10) or `py -3.12`.
  Bare `python` is the Windows Store stub and fails.
- **Git Bash mangles Linux paths passed to Windows programs.** Every `wsl ...` call that
  contains a `/path` must be prefixed with `MSYS_NO_PATHCONV=1`, for example:
  `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -e bash -lc ". /usr/lib/openfoam/openfoam2512/etc/bashrc && simpleFoam -help | head -3"`
- WSL distro: `Ubuntu-24.04`, Linux user `bilal`, 32 cores, about 15 GB RAM. Do not use the
  default `docker-desktop` distro.
- OpenFOAM: **v2512** (openfoam.com package `openfoam2512-default` 2512.0-2) at
  `/usr/lib/openfoam/openfoam2512/etc/bashrc`, with scotch and its own source tree under `src/`.
  Function objects work (`forces`, `forceCoeffs`, `yPlus`); `tools/audit/step0_check.py` compares
  them with `export_field.py`. The old Ubuntu v1912 (sha1 crash in every function object) is gone;
  the solved cases' t = 400 fields were produced by it. Installs need sudo: Bilal runs them.
- Blender 5.2 LTS: `"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"`.
  The add-on is installed as a legacy add-on in
  `%APPDATA%\Blender Foundation\Blender\5.2\scripts\addons\wind_tunnel`.
- Older working copy (do not edit, it is the previous source of truth):
  `C:\Users\bgare\Documents\WindTunnel`. **This folder is now the source of truth.**

## Layout

```
wind_tunnel/            the add-on (Blender package)
  __init__.py           properties, operators, timers, panel, 3D run orchestration (needs bpy)
  case.py               2D airfoil case: dictionaries, BCs, Allrun (pure Python)
  meshgen.py            2D structured C-grid written straight to polyMesh (pure Python)
  results.py            2D: ASCII readers, face-by-face force sum, Cp, convergence verdict (pure)
  flowfield.py          2D: resampled field + streamline tracing (numpy, optional scipy)
  case3d.py             3D: blockMesh box + snappyHexMesh + simpleFoam case for any STL (pure)
  export_field.py       3D: runs INSIDE WSL after the solve; forces.json + field.npz (numpy, scipy)
  viz.py, viz3d.py      Blender objects, OpenVDB volume, Geometry Nodes trees (needs bpy)
  wsl.py                find distro and OpenFOAM, map paths, launch/stop runs (pure)
tests/test_pure.py      unittest suite for the pure modules, no Blender needed
tools/deploy.py         copy the add-on into Blender's add-ons folder and build dist/wind_tunnel.zip
tools/blender_smoke.py  headless Blender check: register add-on, build airfoil, build node trees
tools/audit/            accuracy audit scripts (run inside WSL, see tools/audit/README.md)
validation/             baseline numbers, reference case dictionaries, solved-run forces
docs/                   ACCURACY_AUDIT.md (findings), FIX_PLAN.md (ordered work with acceptance)
```

## Data flow (3D)

1. `__init__.start_run3d` exports the evaluated mesh to triangles, `case3d.write_case` writes
   the case to `~/wind_tunnel/3d_<name>` in WSL (accessed from Windows as
   `\\wsl.localhost\Ubuntu-24.04\home\bilal\wind_tunnel\...`).
2. `Allrun`: surfaceFeatureExtract, blockMesh, decomposePar (scotch; hierarchical if libscotchDecomp is missing),
   snappyHexMesh -parallel, simpleFoam -parallel, reconstructPar, `python3 export_field.py`.
3. `export_field.py` writes `forces.json` (Newtons, Cd/Cl on frontal area) and `field.npz`
   (U, p in Pa on a voxel grid, IDW from 4 nearest cell centres, solid mask).
4. Blender converts `field.npz` to `flow.vdb`, loads it as `WT Flow`; `WT Smoke` (Simulation
   Zone) advects particles through it; `WT Slice` samples speed or Cp.

Conventions: wind along +X, metres, m/s. OpenFOAM `p` is kinematic (m2/s2); multiply by rho
(1.225) for Pa. Pressure reference is the outlet (`p = 0`), which is wrong for Cp (audit #4).

## Commands

```bash
py -m unittest discover -s tests -v          # pure-module tests (no Blender, no WSL)
py tools/deploy.py                           # install into Blender + build dist/wind_tunnel.zip
"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup --python tools/blender_smoke.py
```

WSL (always with `MSYS_NO_PATHCONV=1` from Git Bash):

```bash
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -e bash -lc "ls ~/wind_tunnel"
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -e bash -lc "cd ~/wind_tunnel/3d_Cube && tail -5 log.simpleFoam"
```

Solved cases live in WSL `~/wind_tunnel/`: `3d_Cube`, `3d_Cone`, `3d_Sphere`, `3d_Suzanne`,
`3d_Torus`, `naca0012_re6e06`. Audit copies (extended to 1200 iterations for Cube and Cone)
are in `~/wind_tunnel/_audit` (about 3 GB, safe to delete once no longer needed).

## Rules for changes

- Solver-side changes (case3d, case, meshgen, export_field, results) must be checked against
  OpenFOAM's definitions and a reference value, and the result recorded in
  `validation/` with the date, mesh size and iteration count.
- A run is "solved" only when the convergence gate passes (FIX_PLAN step 2), never on a fixed
  iteration count.
- Keep the pure modules free of `bpy` so the tests run without Blender.
- After changing the add-on: run the tests, `py tools/deploy.py`, then the headless smoke
  check. Tell Bilal to restart Blender or toggle the add-on to load the new code.
- Bump `version` in both `wind_tunnel/blender_manifest.toml` and `bl_info` in `__init__.py`.
- Commit in small steps with a message that says what physical quantity changed and by how much.

## Session workflow

Every slice (a FIX_PLAN step or a feature) runs the same way. The prompt for each slice is written
in this structure and saved under `docs/prompts/` (example: `docs/prompts/anim_ab.md`).

1. **Fresh session, bounded context.** Load only the files the prompt names and take its
   "facts already established" as given; do not re-derive them.
2. **Stage 0 gate:** the previous slice's review in `docs/reviews/` has no open FAIL.
3. **Grill (HIL)** before any code: one question at a time, recommendation first, wait for Bilal's
   answer. Lock the answers in a short spec under `docs/reference/`.
4. **TDD:** a failing test first (red), then the code that makes it pass (green), pure functions
   before Blender code.
5. **Tracer on copies only:** live runs use copies of solved cases (for example `~/wind_tunnel/_anim`)
   and a new Blender scene, never Bilal's own scenes or the original cases.
6. **HIL visual QA** wherever appearance matters: render, stop, Bilal judges, small rounds.
7. **Close:** tests green, `py tools/deploy.py`, headless smoke check, version bump in both places,
   commit.
8. **Handoff:** append to `SESSION_LOG.md` what was done, decisions, numbers, open issues, a
   REVIEWER PROMPT and a NEXT PROMPT, both written in this same structure.
9. **Review** runs in its own fresh session and saves its report to `docs/reviews/`.
10. **Token budget** (Claude cannot see its own count; Bilal watches it): end work at stage
    boundaries, start no new heavy stage after about 150k tokens, hand off at about 200k (write
    `SESSION_LOG.md`, tell Bilal); never compact.
