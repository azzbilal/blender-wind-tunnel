#!/bin/bash
# FIX_PLAN step 3 probe round 2 (mesh only, diagnostics): layer stack depth vs refinement level vs STL
# faceting. Same chain as step3_probe.sh. Copies only: ~/wind_tunnel/_step3/probe2/<name>.
# Each case: name  source-case  featureAngle  n  curvature-cells-per-radius  curvature-lmax  [stl]
# Usage (inside WSL): bash step3_probe2.sh ICO_STL
. /usr/lib/openfoam/openfoam2512/etc/bashrc > /dev/null 2>&1
export OMPI_MCA_btl_vader_single_copy_mechanism=none
HERE="$(cd "$(dirname "$0")" && pwd)"
ICO="$1"
W=~/wind_tunnel; P=$W/_step3/probe2; mkdir -p "$P"
while read -r name src fa n nc lmax stl <&3; do
  [ -z "$name" ] && continue
  c=$P/$name; rm -rf "$c"; mkdir -p "$c/constant"
  cp -r "$W/$src/system" "$c/"; cp -r "$W/$src/constant/triSurface" "$c/constant/"
  cd "$c" || exit 1
  if [ -n "$stl" ]; then
    cp "$stl" constant/triSurface/body.stl; rm -f constant/triSurface/body.eMesh
    surfaceFeatureExtract > log.surfaceFeatureExtract 2>&1 || { echo "$name sFE FAIL"; continue; }
  fi
  python3 "$HERE/step3_probe.py" edit . --feature-angle $fa --n $n --nc $nc --lmax $lmax > log.edit 2>&1 \
    || { echo "$name edit FAIL"; cat log.edit; continue; }
  blockMesh > log.blockMesh 2>&1 && decomposePar -force > log.decomposePar 2>&1 \
    && mpirun -np 24 --oversubscribe snappyHexMesh -overwrite -parallel > log.snappyHexMesh 2>&1 \
    || { echo "$name mesh FAIL"; tail -20 log.snappyHexMesh; continue; }
  mpirun -np 24 --oversubscribe checkMesh -parallel -constant > log.checkMesh 2>&1
  reconstructParMesh -constant > log.reconstructParMesh 2>&1 || echo "$name reconstruct FAIL"
  rm -rf processor*
  python3 "$HERE/step3_probe.py" report . > /dev/null 2> log.report || echo "$name report FAIL"
  echo "== $name: $(grep 'Finished meshing in' log.snappyHexMesh)"
done 3<<EOF
Sphere_L3_n5   3d_Sphere  120 5 24 3
Sphere_L3_n3   3d_Sphere  120 3 24 3
Sphere_L4_n4   3d_Sphere  120 4 48 4
Ico_L3_n8      3d_Sphere  120 8 24 3 $ICO
Ico_L3_n5      3d_Sphere  120 5 24 3 $ICO
Suzanne_L3_n5  3d_Suzanne 120 5 24 3
Suzanne_L4_n4  3d_Suzanne 120 4 48 4
EOF
