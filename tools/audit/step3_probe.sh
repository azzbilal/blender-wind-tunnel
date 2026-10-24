#!/bin/bash
# FIX_PLAN step 3 probe: mesh Cube, Sphere, Suzanne at featureAngle 60 and 120 with the locked layer and
# curvature settings (docs/reference/step3_wall_spec.md), the same chain as Allrun up to checkMesh, then
# reconstructParMesh for the report. Copies only: ~/wind_tunnel/_step3/probe/<body>_fa<angle>.
# Usage (inside WSL): bash step3_probe.sh [bodies...]
. /usr/lib/openfoam/openfoam2512/etc/bashrc > /dev/null 2>&1
export OMPI_MCA_btl_vader_single_copy_mechanism=none
HERE="$(cd "$(dirname "$0")" && pwd)"
W=~/wind_tunnel; P=$W/_step3/probe; mkdir -p "$P"
for body in ${@:-Cube Sphere Suzanne}; do
  for fa in 60 120; do
    c=$P/${body}_fa$fa; rm -rf "$c"; mkdir -p "$c/constant"
    cp -r "$W/3d_$body/system" "$c/"; cp -r "$W/3d_$body/constant/triSurface" "$c/constant/"
    cd "$c" || exit 1
    python3 "$HERE/step3_probe.py" edit . --feature-angle $fa > log.edit 2>&1 || { echo "$body $fa edit FAIL"; cat log.edit; continue; }
    blockMesh > log.blockMesh 2>&1 && decomposePar -force > log.decomposePar 2>&1 \
      && mpirun -np 24 --oversubscribe snappyHexMesh -overwrite -parallel > log.snappyHexMesh 2>&1 \
      || { echo "$body $fa mesh FAIL"; tail -20 log.snappyHexMesh; continue; }
    mpirun -np 24 --oversubscribe checkMesh -parallel -constant > log.checkMesh 2>&1
    reconstructParMesh -constant > log.reconstructParMesh 2>&1 || echo "$body $fa reconstruct FAIL"
    rm -rf processor*
    echo "== $body fa $fa: $(grep 'Finished meshing in' log.snappyHexMesh)"
  done
done
