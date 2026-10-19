#!/bin/bash
. /usr/share/openfoam/etc/bashrc >/dev/null 2>&1
export OMPI_MCA_btl_vader_single_copy_mechanism=none
cd ~/wind_tunnel/_audit
for c in Cube Cone; do
  cd $c
  rm -rf 300 400
  sed -i -E 's/^endTime .*/endTime         1200;/; s/^writeInterval .*/writeInterval   50;/; s/^purgeWrite .*/purgeWrite      0;/' system/controlDict
  for d in processor*; do rm -rf $d/300; done
  echo "running $c" > ../ext_status
  mpirun -np 24 --oversubscribe simpleFoam -parallel > log.ext 2>&1
  reconstructPar -newTimes > log.recext 2>&1
  cd ..
done
echo done > ext_status
