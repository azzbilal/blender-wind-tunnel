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
