# Accuracy audit, add-on v0.4.0 (19 Oct 2026)

Question: are the numbers the add-on reports physically accurate, with the math OpenFOAM
solves as the reference? Short answer: **the post-processing math is correct; the reported
3D numbers are not yet reliable** because of convergence, wall treatment and domain set-up.

All numbers below come from the solved cases in WSL `~/wind_tunnel/` (coarse mesh, 20 m/s,
air nu = 1.5e-5 m2/s, rho = 1.225 kg/m3, 400 iterations, 24 cores, OpenFOAM v1912) and from
copies extended to 1200 iterations in `~/wind_tunnel/_audit`. Scripts: `tools/audit/`.

## What is correct

| Check | Method | Result |
|---|---|---|
| Force integration | Rebuilt face centres/areas and cell centres exactly as `primitiveMesh` does (area-weighted triangles, pyramid-volume cell centres); wall shear as `nuEff * |U_t| / y` with `nut` from `nutUSpaldingWallFunction` | Matches the add-on within 0.1 N on 128 to 1226 N. Cell-centre shortcut shifts wall cells by 3 to 5 % of h (median), no measurable force effect |
| Units and signs | Kinematic p times rho, `Sf` points out of the fluid | Correct |
| Exported field (field.npz) | Net mass flux through the grid box; rms divergence away from the body | Net flux 0.02 to 0.11 % of inflow; rms div 0.3 to 0.6 % of U0/h |
| Mesh | checkMesh | OK, no negative volumes, max non-orthogonality under 65 deg |
| Blockage | frontal area / inlet area | 2.2 % (sphere, cone), 2.8 % (cube) |

## What fails

### 1. Reported Cd is a snapshot of an unconverged solve (highest impact)

Initial residual of p after 400 iterations: about 0.018 (sphere, and rising), 0.024 (cube),
0.003 (cone). That is roughly 1.5 to 2.5 orders of magnitude.

Continued to 1200 iterations (`tools/audit/extend.sh`, forces every 50 iterations):

| Body | Cd at 400 (panel) | Cd at 1200 | Spread 750 to 1200 | Reference | Converged gap |
|---|---|---|---|---|---|
| Cube, face on | 1.251 | **1.151** | 1.151 to 1.173 | about 1.05 (common handbook value, not yet cited) | +10 % |
| Cone, 26.6 deg half angle, tip upstream | 0.579 | **0.583** | 0.583 flat | about 0.46 (Hoerner: 0.50 at 30 deg, roughly linear with half angle) | +27 % |
| Sphere | 0.167 | not extended | n/a | Achenbach 1972, Re = 2.7e6 here | no verdict, see #2 |

The cube's side force (250 N) and lift (156 N) at iteration 400 were transients: Cs and Cl
fall to about +/-0.02 by iteration 1000. At iteration 300 the cube showed Cd 1.05: matching
the reference was luck of timing.

Correction of an earlier statement: the cone Cd of 0.579 was described as "in the published
range". It is not; it is 27 % above Hoerner's data even when converged.

### 2. Wall treatment outside its range of validity

y+ of the first cell (area-weighted over the body, from `y * sqrt(nuEff |U|/y) / nu`):

| Body | min | mean | max | area with y+ > 300 |
|---|---|---|---|---|
| Sphere | 44 | 822 | 1269 | 82 % |
| Cone | 42 | 476 | 1467 | 69 % |
| Cube | 9 | 263 | 615 | 41 % |

snappyHexMesh added 2 layers with `relativeSizes true; finalLayerThickness 0.5`, total
thickness 0.04 to 0.07 m on a 2 m body. Spalding's law is formally continuous, but the k and
omega wall treatment and the log-law assumption degrade once the first cell sits in the outer
part of the boundary layer, so separation on smooth bodies is not predicted. The sphere is the
worst case (separation position decides Cd). Cube and cone are less sensitive because sharp
edges fix separation, which is consistent with their smaller errors.

### 3. Total pressure exceeds the freestream value (Bernoulli violated)

Steady incompressible flow cannot raise total pressure above the inlet value. Measured excess
(p + |U|^2/2 relative to inlet total, divided by q):

| Body | max excess | cells over +0.02 q |
|---|---|---|
| Sphere | 0.13 q (shoulder, |U| = 1.41 U0) | 6,010 |
| Cube | 0.19 q | 62,391 (17 % of the mesh) |

Numerical error from the coarse unconverged solution plus `linearUpwindV` on refinement
interfaces. Expected to shrink with convergence and finer mesh; it is a pass/fail check.

### 4. Cp reference point

`p = 0` is fixed at the outlet. The mean static pressure on the inlet is +0.5 % q (sphere),
+1.1 % (cone), +4.5 % (cube) above that, so every Cp shown in WT Slice is shifted by that
amount. Forces are not affected (a constant offset cancels on a closed surface).

### 5. OpenFOAM's own cross-checks are unavailable

v1912 from Ubuntu crashes in every function object (`forces`, `forceCoeffs`, `solverInfo`,
`yPlus`: `error in IOstream "sha1"`). The add-on's force math can therefore not be compared
against OpenFOAM's own output, and there is no in-run force history or averaging.

### 6. Visualisation alters the solved flow near walls

- The "slide along the surface" correction from preview mode also acts in solved mode, within
  5 % of L of the body, so near-wall pathlines are not the solved ones.
- It is needed because IDW resampling gives 10 to 12 % rms divergence (relative to U0/h) next to
  the wall, so particles leak inward.
- The voxel grid ends 2.5 L downstream, so the wake visualisation is truncated there.

### 7. 2D airfoil far field

Far field 20 chords away with a fixed freestream direction and no point-vortex correction.
At Cl around 1.1 the induced angle error is about Cl / (4 pi R) = 0.25 deg, roughly 2.5 % lift
deficit: consistent with the 2 to 4 % Cl gap to NASA TMR in the README.

## Reference sources

- Hoerner, Fluid-Dynamic Drag (cone vs half-vertex angle, disk 1.17, 60 deg cone 0.50), as
  summarised at https://aerospaceweb.org/question/aerodynamics/q0231.shtml
- Achenbach, E. (1972) Experiments on the flow past spheres at very high Reynolds numbers,
  J. Fluid Mech. 54(3), 565 to 575.
- NASA Turbulence Modeling Resource, NACA 0012 validation case (2D).
- Still to source properly: cube face-on Cd at Re about 1e6 (Hoerner / ESDU).
