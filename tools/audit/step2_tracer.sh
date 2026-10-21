#!/bin/bash
# FIX_PLAN step 2 Stage 5 (SESSION_LOG.md, design constraint 6). For each case in ~/wind_tunnel/_step2:
# the gated Allrun, then the same run continued without the gate (gate and stop FOs removed,
# endTime 2000) and exported again. Keeps forces_gated.json, log.gated, forces_2000.json.
# Usage (inside WSL): bash step2_tracer.sh Cube Cone
for f in /usr/lib/openfoam/openfoam*/etc/bashrc; do . "$f" > /dev/null 2>&1; done
export OMPI_MCA_btl_vader_single_copy_mechanism=none
for c in "$@"; do
    cd ~/wind_tunnel/_step2/"$c" || continue
    np=$(foamDictionary -entry numberOfSubdomains -value system/decomposeParDict)
    exp=$(grep -o 'export_field.py .*--cap [0-9]*' Allrun | sed 's/--cap [0-9]*$//')
    echo "$c: gated run, $(date +%T)"
    bash Allrun
    echo "$c: gated status $(cat status), latest $(foamListTimes -latestTime -processor 2>/dev/null | tail -1), $(date +%T)"
    [ "$(cat status)" = done ] || continue
    cp forces.json forces_gated.json
    cp log.simpleFoam log.gated
    rm -f wt_stop
    foamDictionary -entry functions/gate -remove system/controlDict > /dev/null
    foamDictionary -entry functions/stop -remove system/controlDict > /dev/null
    foamDictionary -entry endTime -set 2000 system/controlDict > /dev/null
    mpirun -np "$np" --oversubscribe simpleFoam -parallel > log.cont 2>&1 || { echo "$c: continuation failed"; continue; }
    reconstructPar -latestTime > log.reconstructPar2 2>&1
    python3 $exp --cap 2000 > log.export2 2>&1 || { echo "$c: export failed"; continue; }
    cp forces.json forces_2000.json
    echo "$c: continued to $(python3 -c 'import json; print(json.load(open("forces.json"))["time"])'), $(date +%T)"
done
