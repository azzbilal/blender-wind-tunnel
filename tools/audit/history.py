#!/usr/bin/env python3
import sys, json
from pathlib import Path
import numpy as np
case = Path(sys.argv[1]); sys.path.insert(0, str(case))
import export_field as ef
nu, rho, U0 = 1.5e-5, 1.225, 20.0
pm = case/"constant"/"polyMesh"
pts = ef.read_points(pm); sizes, starts, toks = ef.read_faces(pm)
own = ef.read_labels(pm/"owner"); nei = ef.read_labels(pm/"neighbour")
nc = int(max(own.max(), nei.max())) + 1
cc = ef.cell_centres(pts, sizes, starts, toks, own, nei, nc)
s, nb = ef.read_boundary(pm)["body"]; bf = np.arange(s, s+nb); o = own[bf]
fc, fa = ef.face_geometry(pts, sizes, starts, toks, bf)
A = np.linalg.norm(fa, axis=1); n = fa/A[:, None]; y = np.abs(((fc-cc[o])*n).sum(1))
Af = json.loads((case/"forces.json").read_text())["frontal_area_m2"]
q = 0.5*rho*U0**2
times = sorted((d.name for d in case.iterdir() if d.is_dir() and d.name.replace(".","").isdigit() and float(d.name) > 0 and (d/"U").exists()), key=float)
rows = []
for t in times:
    U = ef.read_internal(case/t/"U", 3, nc); p = ef.read_internal(case/t/"p", 1, nc)
    nut = ef.read_patch_values(case/t/"nut", "body", nb)
    u = U[o]; ut = u - n*(u*n).sum(1)[:, None]
    F = rho*(p[o][:, None]*fa).sum(0) + rho*(ut*((nu+nut)*A/np.maximum(y,1e-12))[:, None]).sum(0)
    rows.append((int(float(t)), F[0]/(q*Af), F[1]/(q*Af), F[2]/(q*Af)))
for r in rows: print("%5d  Cd %.3f  Cs %+.3f  Cl %+.3f" % r)
last = np.array([r[1] for r in rows if r[0] > 700])
print("Cd over iterations 750-1200: mean %.3f  min %.3f  max %.3f  (n=%d)" % (last.mean(), last.min(), last.max(), len(last)))
