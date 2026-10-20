"""Headless Blender check for FIX_PLAN step 1: the VDB `cp` grid is referenced to p_inf.

    blender --background --factory-startup --python tools/blender_cp_probe.py -- FIELD_NPZ OUT_VDB X_FRONT

Builds flow.vdb with viz3d.write_vdb from FIELD_NPZ, reads the `cp` grid back with openvdb and
prints JSON: cp at a node on the grid's upstream face (off the stagnation line) and at the node
just upstream of the body face at x = X_FRONT on the grid's centre line, each beside the value
p / (0.5 rho U^2) computed from field.npz directly.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from wind_tunnel import viz3d  # noqa: E402

npz, vdb, x_front = sys.argv[sys.argv.index("--") + 1:][:3]
x_front, rho = float(x_front), 1.225
viz3d.write_vdb(Path(npz), Path(vdb), rho)

import openvdb  # noqa: E402

d = np.load(npz)
shape = d["p"].shape
h, o = float(d["voxel"]), d["origin"].astype(float)
cp = np.zeros(shape, np.float32)
openvdb.read(vdb, "cp").copyToArray(cp)
q = 0.5 * rho * float(d["speed"]) ** 2
direct = d["p"] / q
j, k = shape[1] // 2, shape[2] // 2
i_front = int(np.floor((x_front - o[0]) / h))
while d["solid"][i_front, j, k]:
    i_front -= 1
probes = {"upstream_face_off_axis": (0, shape[1] // 4, shape[2] // 4), "ahead_of_front_face_centre": (i_front, j, k)}
out = {"npz": npz, "voxel": h, "origin": o.tolist(), "shape": list(shape), "p_inf_Pa": float(d["p_inf_Pa"])}
for name, (a, b, c) in probes.items():
    out[name] = {"ijk": [a, b, c], "xyz": (o + h * np.array([a, b, c])).tolist(),
                 "vdb_cp": float(cp[a, b, c]), "npz_cp": float(direct[a, b, c])}
out["vdb_vs_npz_max_abs"] = float(np.abs(cp - direct).max())
print("CP_PROBE " + json.dumps(out))
