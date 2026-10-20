# Step 2 reference: convergence gate

Build: OpenFOAM v2512, source `/usr/lib/openfoam/openfoam2512/src` (paths below are relative to it).
Line numbers read with `grep -n` and `sed -n`.

## Decisions locked (grill, 21 Oct 2026)

| # | Question | Answer |
|---|---|---|
| Q1 (amended) | Mechanism | `forces` and `solverInfo` function objects write every iteration; a `systemCall` FO (`master yes`) runs our stdlib-only Python gate every 5 iterations; when it passes, the gate writes `<case>/wt_stop` and an `abort` FO (`action writeNow`) stops the run. Our gate is the only decider. `export_field.py` recomputes the verdict at the written time from the full history and stores it in `forces.json` |
| Q2 | Gate | Converged at iteration n when (max - min)/abs(mean) of Cd over n-199..n < 0.5 %, the first p solve's initial residual at n < 1e-3, and n >= 400. Cap 3000 (= `endTime`). `residualControl` removed from fvSolution. Report Cd, Cl, Cs mean/min/max over the window; only Cd gated |
| Q3 | Acceptance | Fresh v2512 Cube and Cone in `~/wind_tunnel/_step2`: gated run, then continued ungated to 2000; the offline gate on the full history agrees with the stop. (a) gate open at 400 and 800 on the cube; (b) mean of 1801-2000 within 1 % of the reported mean; (c) cone reported mean within 1 % of 0.583 (v1912, 1200-iteration audit value). Cube reported against 1.151 (spread 1.151 to 1.173), not gated |
| Q4 | Panel | Converged: "Converged at iteration N: p residual r, Cd band b %", then window means (min to max). Not converged: reasons only, no Cd/Cl/forces. Solving: iteration and p residual. `field_state` "solved" only when `forces.json` has `converged: true`; a finished unconverged run loads as "unconverged" |

## Why not `runTimeControl` (`functionObjects/utilities/runTimeControl`)

`averageCondition` uses `valueAverageBase` (`OpenFOAM/db/functionObjects/valueAverageBase/valueAverageBaseTemplates.C`).
With `windowType exact` (`:85`) the mean is the time-weighted average over the window (`:117-143`),
then `delta = mag(meanValue - currentValue)` (`:153`) and the condition fails while
`delta > tolerance` (`:162`). That is an absolute bound on the distance of the current value from
the window mean. Our band (max - min)/abs(mean) < 0.5 % implies it, but it does not imply our band, so
OpenFOAM would stop earlier than our gate. No stock condition computes max - min over a window.
The END action itself is usable (`runTimeControl.C:289`, `time.writeAndEnd()`); only the
conditions are the problem.

## Residual definition

- `solverInfo` writes `p_initial` from `sp.first().initialResidual()`
  (`functionObjects/utilities/solverInfo/solverInfoTemplates.C:127`, column name `:61`), i.e. the
  first p solve of the iteration. `equationInitialResidualCondition` uses the same
  (`.../equationInitialResidualConditionTemplates.C:47`).
- With `nNonOrthogonalCorrectors 1` there are two p solves per iteration; the first is the larger.
- OpenFOAM normalises the residual, and iteration 1 reads 1.0 in the cube and cone logs, so
  "3 orders down" is the same as `p_initial < 1e-3`.
- Audit history (v1912, `~/wind_tunnel/_audit/*/log.simpleFoam` + `log.ext`): cube 0.0236 (400),
  0.0040 (800), 0.00164 (1200); cone 0.0030 (400), 0.00069 (800), 0.00014 (1200).

## Stop chain

- `systemCall` (`functionObjects/utilities/systemCall/systemCall.C`): `master yes` runs the calls
  on the master rank only (`:64`, key read at `:115`) and broadcasts afterwards. It is fatal as
  root (`:123`) and when `allowSystemOperations` is 0 (`:131`). `etc/controlDict:75` sets it to 1.
  Allrun runs as the distro's default user (`wsl.py:98`).
- `abort` (`functionObjects/utilities/abort/abort.C`): the master checks for the file, broadcasts
  the action (`:223`) and calls `time_.stopAt(action)` on every rank (`:228`). The trigger is
  sticky: once seen, it is never rechecked. Allrun must delete `wt_stop` before `simpleFoam`.
- Function objects run in the order they are listed: `forces`, `solverInfo`, `gate`
  (systemCall), `stop` (abort).

## Probe (copy of `_step1/Cube` (v2512 fields) in `~/wind_tunnel/_step2/probe`, serial, 21 Oct 2026)

The four FOs above with a stub gate that writes `wt_stop` once the latest `solverInfo` time is
>= 402. Result: the gate ran at 401, 402, 403. The log shows `USER REQUESTED ABORT (timeIndex=402):
stop and write data`, then `Time = 403`, `End`; time directory `403/` written. **Stop lag: the run
writes one iteration after the gate passes.** The final verdict is therefore recomputed at the
written time, and the lag is recorded in Stage 5.

File formats (v2512):

```
postProcessing/forces/<startTime>/force.dat
# Time  total_x total_y total_z  pressure_x pressure_y pressure_z  viscous_x viscous_y viscous_z
401     1.2285683e+03 -9.9752657e+00 ...        (plain numbers, no parentheses)
postProcessing/solverInfo/<startTime>/solverInfo.dat
# Time  p_solver p_initial p_final p_iters p_converged
401     GAMG 2.7955010e-02 6.6939590e-04 3 true
```

Parse the column names from the last `#` line; ignore an incomplete last line, because the gate
can read while the FO is writing. A restart writes a new `<startTime>` directory: merge all of
them, sorted by start time, with later rows replacing earlier ones at the same time.

## Forces and Cd

`forces` with `rho rhoInf; rhoInf 1.225` gives N. `forceCoeffs` is not used because `Aref` is the
frontal area, which `export_field.frontal_area` computes after meshing (numpy), not `case3d`. The
band is scale free, so the gate uses Fx directly. Reported Cd = mean Fx over the window /
(0.5 rho U^2 A_frontal).
