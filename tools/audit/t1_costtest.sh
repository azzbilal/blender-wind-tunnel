#!/bin/bash
# TRANSIENT T1 Stage 2 Q3: 25-step pimpleFoam cost test on a copy of ~/wind_tunnel/_anim/Cube
# (potentialFoam start, backward, steady spatial schemes, 24 ranks). Runs inside WSL:
#   bash t1_costtest.sh NAME MAXCO NOUTER NCORR   -> ~/wind_tunnel/_t1/cost_NAME
# Cost per step = (ExecutionTime at step 25 - at step 5) / 20.
. /usr/lib/openfoam/openfoam2512/etc/bashrc
NAME=$1; CO=$2; NOUT=$3; NCOR=$4
SRC=~/wind_tunnel/_anim/Cube
D=~/wind_tunnel/_t1/cost_$NAME
rm -rf $D; mkdir -p $D; cd $D
cp -r $SRC/constant $SRC/system .
rm -rf constant/extendedFeatureEdgeMesh constant/triSurface
for p in $SRC/processor*; do b=$(basename $p); mkdir -p $b; cp -r $p/0 $p/constant $b/; done
cat > system/controlDict <<CD
FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }
application     pimpleFoam;
startFrom       startTime;
startTime       0;
stopAt          nextWrite;
endTime         2;
deltaT          1e-3;
writeControl    timeStep;
writeInterval   25;
writeFormat     binary;
writePrecision  8;
timeFormat      general;
timePrecision   8;
runTimeModifiable false;
adjustTimeStep  yes;
maxCo           $CO;
maxDeltaT       1;
functions
{
    forceCoeffs
    {
        type forceCoeffs; libs (forces); patches (body); rho rhoInf; rhoInf 1.225;
        CofR (0 0 0); liftDir (0 0 1); dragDir (1 0 0); pitchAxis (0 1 0);
        magUInf 20; lRef 2; Aref 4; writeControl timeStep; writeInterval 1; log off;
    }
}
CD
sed -i 's/default steadyState;/default backward;/; s/bounded Gauss/Gauss/g' system/fvSchemes
cat > system/fvSolution <<FS
FoamFile { version 2.0; format ascii; class dictionary; object fvSolution; }
solvers
{
    p      { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.01; }
    pFinal { \$p; relTol 0; }
    Phi    { \$p; relTol 0.01; }
    "(U|k|omega)"      { solver smoothSolver; smoother GaussSeidel; tolerance 1e-8; relTol 0.1; nSweeps 1; }
    "(U|k|omega)Final" { \$U; relTol 0; }
}
PIMPLE
{
    momentumPredictor yes;
    nOuterCorrectors $NOUT;
    nCorrectors $NCOR;
    nNonOrthogonalCorrectors 1;
}
potentialFlow { nNonOrthogonalCorrectors 5; }
relaxationFactors { equations { ".*" 1; } }
FS
mpirun -np 24 --oversubscribe potentialFoam -parallel -writep > log.potentialFoam 2>&1 || { echo POTFAIL; tail -20 log.potentialFoam; exit 1; }
/usr/bin/time -f "WALL %e" mpirun -np 24 --oversubscribe pimpleFoam -parallel > log.pimpleFoam 2>&1 || { echo PIMPLEFAIL; tail -30 log.pimpleFoam; exit 1; }
echo "== $NAME maxCo $CO nOuter $NOUT nCorr $NCOR"
grep -c '^Time =' log.pimpleFoam
grep '^Courant' log.pimpleFoam | sed -n '1p;$p'
grep '^deltaT' log.pimpleFoam | sed -n '1p;$p'
grep ExecutionTime log.pimpleFoam | sed -n '5p;$p'
grep 'continuity errors' log.pimpleFoam | tail -1
tail -2 postProcessing/forceCoeffs/0/coefficient.dat
