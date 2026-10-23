# TRANSIENT T1 spec: time-resolved flow around the cube on a fixed plane

Locked in the Stage 2 grill (HIL, Bilal), 2026-10-23. Prompt: `docs/prompts/transient_t1.md`.

## Case facts (from the prompt and the case, not re-derived)

- Body: cube, edge L = 2 m, centred at the origin, wind +X, U = 20 m/s, one flow-through L/U = 0.1 s.
- nu = 1.5e-5 m2/s (`~/wind_tunnel/_anim/Cube/constant/transportProperties`), so
  Re = U L / nu = 2.67e6.
- Mesh: the gated steady mesh, 359618 cells, copied from `~/wind_tunnel/_anim/Cube` (no re-meshing).
  Cube Cd is path dependent by about 35 % between two triangulations of the same cube (memory note),
  so the comparison with steady Cd 1.1498 is like-for-like only on this identical mesh.
  `~/wind_tunnel/_anim` must stay until T1 is closed.

## Q1 Start condition: impulsive start, potentialFoam initial field

- t = 0 field: `potentialFoam` on the copied mesh (U and p, irrotational). For incompressible flow
  past an impulsively started body the t = 0+ solution is the potential flow, so this is the exact
  initial condition of the impulsive-start problem, and it avoids the first-step Courant spike of a
  uniform field near the body.
- k and omega uniform at the inlet values of the steady case; nut computed from them.
- The steady-field start and the two-run option were declined. The run shows the wake forming; the
  first flow-throughs are start-up and are excluded from averages (window in Q4).

## Q2 Physical time and frames: 2 s, 120 frames

- End time 2 s (20 flow-throughs L/U), 120 written frames, one every 1/60 s (adjustableRunTime so
  writes land on the frame times). Frame k (k = 1..120) is physical time t_k = k / 60 s,
  t U/L = k / 6. The t = 0 potential field is not a frame. Video at 24 fps: 5 s (0.4x real time).
- Extend only on Bilal's request after he has seen it (pimpleFoam continues from the last time).
- Strouhal reference: none found for a cube in free stream at Re near 1e6 (searches 2026-10-23;
  every high-Re cube St found was for a wall-mounted cube in a boundary layer, a different flow,
  not used). Nearest free-stream cube value, a different regime:
  L. Klotz, S. Goujon-Durand, J. Rokicki, J. E. Wesfreid, "Experimental investigation of flow
  behind a cube for moderate Reynolds numbers", J. Fluid Mech. 750 (2014) 73 to 98,
  doi:10.1017/jfm.2014.236: St = f d / U = 0.125, almost constant up to Re = 390 (d = cube edge,
  blockage 1.44 %, hairpin-vortex shedding, frequency from PIV vorticity maxima); 0.109 and 0.104 at
  blockage 0.96 % and 0.43 %; Saha (Phys. Fluids 16, 2004, numerical) 0.094.
- Consequence: at St 0.1 to 0.125, f = St U / L = 1 to 1.25 Hz, so 2 s holds about 2 periods in
  total and fewer in the settled window. Any St measured from this run is a rough number, reported
  next to Klotz 2014 with its Re stated, never called a match.

## Q3 Solver settings: pimpleFoam, max Co 1, PISO mode, backward

- pimpleFoam, k-omega SST (as the steady case), nu 1.5e-5.
- Time: `ddtSchemes default backward` (second order). `adjustTimeStep yes`, `maxCo 1`,
  `maxDeltaT 1`, initial deltaT 1e-3 (reduced on step 1 to the Courant target).
- Space: the steady case's schemes, so the Cd comparison is like-for-like: `div(phi,U) Gauss
  linearUpwindV grad(U)`, `div(phi,k|omega) Gauss upwind` (the `bounded` prefix dropped, it is
  for steady runs), gradients, laplacian and snGrad as in the steady case.
- PIMPLE: `nOuterCorrectors 1`, `nCorrectors 2`, `nNonOrthogonalCorrectors 1`,
  `momentumPredictor yes`, no relaxation. Solvers: p GAMG tol 1e-7 relTol 0.01, pFinal relTol 0;
  U, k, omega smoothSolver tol 1e-8 relTol 0.1, Final relTol 0. potentialFlow 5 non-orthogonal
  correctors (potentialFoam -writep).
- Output: `writeObjects` (U, p) with `writeControl adjustableRunTime`, `writeInterval 1/60`;
  in v2512 a function object with adjustableRunTime shortens deltaT to land on its write times
  (`src/OpenFOAM/db/functionObjects/timeControl/timeControlFunctionObject.C:560`). Full write of all
  fields every 0.5 s (restart points), binary. `forceCoeffs` on patch body every step
  (magUInf 20, lRef 2, Aref 4, dragDir +X, liftDir +Z): the side-force and drag signals for Q4.
- Measured cost (2026-10-23, `tools/audit/t1_costtest.sh`, 24 ranks oversubscribed as case3d does,
  359618 cells, 25 steps from the potentialFoam field, cost = steps 5 to 25):

| Variant | maxCo | outer / correctors | s per step | dt at target Co (s) | steps for 2 s | estimate |
|---|---|---|---|---|---|---|
| A (chosen) | 1 | 1 / 2 | 0.48 | 6.5e-4 | about 3070 | about 25 min |
| B | 4 | 3 / 1 | 0.94 | 2.4e-3 | about 820 | about 13 min |

  Continuity error (sum local) at step 25: A 1.2e-12, B 9.4e-12. The estimate assumes dt stays at
  its step-25 value; Co max can move as the wake develops. Stage 4 re-measures before the full run.
- Declined: B (3 fixed outer iterations are not converged per step, a splitting error not bounded
  without a second run) and CrankNicolson 0.9.

## Q4 Honesty gates (record: `validation/transient_t1_v2512.json`)

1. Cd: time average over the settled window t = 1.0 to 2.0 s (t U/L 10 to 20) from forceCoeffs,
   reported next to steady gated Cd 1.1498 (same mesh). No target: two models compared, not a
   validation. The 0.5 to 1.0 s mean is reported beside it as a settling indicator.
2. Strouhal number: from the side-force coefficients (Cs about y and Cl about z) over the same window,
   spectrum peak plus zero-crossing count, St = f L / U. Reported next to Klotz 2014 (0.125,
   Re <= 390, a different regime, see Q2). Fewer than 2 full periods in the window: reported as
   "not measurable", no number.
3. Mass conservation: the time step continuity error (sum local) logged at every written frame
   step; FAIL if any exceeds 1e-6 (cost test: about 1e-12).
4. Particles: `tools/audit/anim_inside.py` extended to the VDB sequence; 0 particle-frames inside
   the body box |x|, |y|, |z| < 1 m over all frames (target 0, FAIL otherwise). Gap reported as
   Chebyshev and Euclidean.

Only 3 and 4 can FAIL; 1 and 2 are reports.

## Q5 Open issues h and i

- i (smoke styling) is in T1: plain white smoke, fewer particles, short trails, so Cp on the slice is
  the only colour code. Built as smoke tree inputs with tests in Stage 3, judged at the Stage 4 HIL.
- h (section view, hide body and smoke on the camera side of the slice) stays open for a later slice
  (needs a clipping design).

## Stage 3 and 4 notes (2026-10-24, not grill decisions; recorded so the reviewer sees them)

- **Write format ASCII, not binary** (deviation from Q3 "binary"): the frame export reuses the tested
  ASCII readers of `export_field.py` instead of a new binary parser. Physics unchanged; disk is
  larger (about 20 MB per frame over 24 processors, 948 GB free).
- **No reconstructPar per frame**: `export_field.py --frames` gathers U and p straight from
  `processor*/<t>/` through each processor's `cellProcAddressing` (written with the source mesh), so
  frames come out in the reconstructed mesh's cell order. The solid mask and the IDW weights
  (int32 index, float32 weight, 4 nearest cell centres, as the steady export) are computed once.
  p_inf (inlet-patch area mean) is taken per frame, since it moves with the transient.
- **Frame directories are matched by time with a tolerance** (`transient.frame_from_time`,
  |t 60 - k| < 1e-3), never by name: time names have 8 significant digits (0.016666667).
- **Smoke time**: one CFD frame interval (1/60 s) per scene frame (Time Scale = 24/60 = 0.4), split
  into substeps of at most one voxel at 1.5 U_inf (10 substeps for h = 0.05 m). The field is held at
  scene frame k's VDB through the step from k-1 to k (piecewise constant in time).
- **Stage 4 re-measure** with the Stage 3 writer (`~/wind_tunnel/_t1/cost50`, 50 steps, same
  dictionaries as the full run except stopAt/writeControl): potentialFoam in parallel ran 6 Phi
  solves and ended normally (continuity error 1.5e-4, interpolated velocity error 3.6e-5, its own
  measures); no FATAL, warning or NaN in either log. Courant max 1.80 at step 1, 1.00 +- 0.005 after.
  Final-corrector sum local max 2.8e-12 over 50 steps, frame 1 1.4e-12. Cost 0.522 s/step (steps 10
  to 50), dt about 6.3e-4 s, so about 3200 steps and about 28 min of solve for 2 s. Cd 1.62 at
  t = 0.031 s (impulsive-start transient, not a result).
- **Early-frame Cp (Bilal, 2026-10-24)**: frame 1 (t = 1/60 s, t U/L = 0.17) has Cp -4.24 to +1.16
  against -0.68 to +1.02 for the steady field on the same mesh and grid. Expected from the impulsive
  start: the potential-flow start has very high speed (strong suction) at the cube's sharp edges, and
  while the flow accelerates the unsteady Bernoulli term -rho dphi/dt adds to the stagnation pressure,
  so Cp > 1 is possible. To be confirmed, not assumed: Cp must relax toward the steady range in the
  1 to 2 s window; the frame Cp min/max over time go into `validation/transient_t1_v2512.json`.
