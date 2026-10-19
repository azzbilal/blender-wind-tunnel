#!/usr/bin/env python3
"""Audit of a wind-tunnel case against OpenFOAM's own definitions (geometry, wall functions, forces)."""
import sys, json, re
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(sys.argv[1])))
import export_field as ef

case = Path(sys.argv[1]); orig = Path(sys.argv[2])
nu, rho, U0 = 1.5e-5, 1.225, 20.0
pm = case / "constant" / "polyMesh"
pts = ef.read_points(pm)
sizes, starts, toks = ef.read_faces(pm)
owner = ef.read_labels(pm / "owner"); neigh = ef.read_labels(pm / "neighbour")
nc = int(max(owner.max(), neigh.max())) + 1
nf, ni = len(sizes), len(neigh)

# OpenFOAM primitiveMesh face centres/areas (triangles about the vertex mean, area-weighted)
fC = np.empty((nf, 3)); fA = np.empty((nf, 3)); fmean = np.empty((nf, 3))
for s in np.unique(sizes):
    idx = np.nonzero(sizes == s)[0]
    P = pts[toks[starts[idx][:, None] + np.arange(s)[None, :]]]        # (m, s, 3)
    pav = P.mean(axis=1); fmean[idx] = pav
    if s == 3:
        fC[idx] = pav; fA[idx] = 0.5 * np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]); continue
    Pn = np.roll(P, -1, axis=1)
    c = P + Pn + pav[:, None, :]
    n = np.cross(Pn - P, pav[:, None, :] - P)
    a = np.linalg.norm(n, axis=2)
    fC[idx] = (a[..., None] * c).sum(1) / (3 * a.sum(1)[:, None])
    fA[idx] = 0.5 * n.sum(1)
# OpenFOAM cell centres (pyramid decomposition about the face-centre mean)
acc = np.zeros((nc, 3)); cnt = np.zeros(nc)
np.add.at(acc, owner, fC); np.add.at(cnt, owner, 1); np.add.at(acc, neigh, fC[:ni]); np.add.at(cnt, neigh, 1)
cEst = acc / cnt[:, None]
v_o = (fA * (fC - cEst[owner])).sum(1)
v_n = (fA[:ni] * (cEst[neigh] - fC[:ni])).sum(1)
cc = np.zeros((nc, 3)); vol = np.zeros(nc)
np.add.at(cc, owner, v_o[:, None] * (0.75 * fC + 0.25 * cEst[owner])); np.add.at(vol, owner, v_o)
np.add.at(cc, neigh, v_n[:, None] * (0.75 * fC[:ni] + 0.25 * cEst[neigh])); np.add.at(vol, neigh, v_n)
cOF = cc / vol[:, None]; vol /= 3.0
# the add-on's cell centres: plain mean of the vertex-mean face centres
acc = np.zeros((nc, 3)); np.add.at(acc, owner, fmean); np.add.at(acc, neigh, fmean[:ni])
cAddon = acc / cnt[:, None]

bnd = ef.read_boundary(pm)
start, nb = bnd["body"]; bf = np.arange(start, start + nb); own = owner[bf]
h_cell = np.cbrt(vol[own])
dev = np.linalg.norm(cAddon[own] - cOF[own], axis=1) / h_cell
out = {"cells": nc, "neg_vol": int((vol <= 0).sum()),
       "centre_shift_wall_cells_rel_h": {"median": float(np.median(dev)), "p95": float(np.percentile(dev, 95)), "max": float(dev.max())}}

def forces(t, geo):
    U = ef.read_internal(case / t / "U", 3, nc); p = ef.read_internal(case / t / "p", 1, nc)
    nutw = ef.read_patch_values(case / t / "nut", "body", nb)
    if geo == "addon":
        Cf, Sf, C = fmean[bf], fA[bf], cAddon
    else:
        Cf, Sf, C = fC[bf], fA[bf], cOF
    A = np.linalg.norm(Sf, axis=1); n = Sf / A[:, None]
    y = np.abs(((Cf - C[own]) * n).sum(1))
    u = U[own]; ut = u - n * (u * n).sum(1)[:, None]
    Fp = rho * (p[own][:, None] * Sf).sum(0)
    Fv = rho * (ut * ((nu + nutw) * A / np.maximum(y, 1e-12))[:, None]).sum(0)
    # y+ as OpenFOAM's nutUSpaldingWallFunction defines it: y * u_tau / nu, u_tau = sqrt(nuEff |snGrad U|)
    utau = np.sqrt((nu + nutw) * np.linalg.norm(u, axis=1) / np.maximum(y, 1e-12))
    yp = y * utau / nu
    return Fp, Fv, yp, A, p, U

res = {}
for t in ("300", "400"):
    for geo in ("addon", "openfoam"):
        Fp, Fv, yp, A, p, U = forces(t, geo)
        F = Fp + Fv
        res[f"{t}_{geo}"] = {"drag": round(F[0], 2), "side": round(F[1], 2), "lift": round(F[2], 2),
                             "fric_drag": round(Fv[0], 2)}
        if geo == "openfoam" and t == "400":
            w = A / A.sum()
            out["yplus"] = {"min": float(yp.min()), "area_mean": float((yp * w).sum()), "max": float(yp.max()),
                            "frac_below_30": float(w[yp < 30].sum()), "frac_above_300": float(w[yp > 300].sum())}
            pin = ef.read_patch_values(case / t / "p", "inlet", 1)
            si, ni_ = bnd["inlet"]
            pin_cells = p[owner[np.arange(si, si + ni_)]]
            q = 0.5 * U0 ** 2
            out["inlet_static_Cp"] = float(pin_cells.mean() / q)
out["forces"] = res

# blockage
s_, n_ = bnd["inlet"]; inlet_area = np.linalg.norm(fA[s_:s_ + n_], axis=1).sum()
F = json.loads((orig / "forces.json").read_text())
out["blockage"] = F["frontal_area_m2"] / inlet_area
out["Cd_reported"] = F["Cd"]

# the resampled grid Blender uses: net mass flux through the grid box (should be ~0 for incompressible flow)
d = np.load(orig / "field.npz"); G = d["U"].astype(float); h = float(d["voxel"]); solid = d["solid"]
inflow = (G[0, :, :, 0]).sum() * h * h
flux = (G[-1, :, :, 0].sum() - G[0, :, :, 0].sum() + G[:, -1, :, 1].sum() - G[:, 0, :, 1].sum()
        + G[:, :, -1, 2].sum() - G[:, :, 0, 2].sum()) * h * h
out["grid_box_net_flux_vs_inflow"] = float(flux / inflow)
# local divergence in fluid voxels at least 2 voxels from the solid, relative to U0/h
from scipy.ndimage import binary_dilation
near = binary_dilation(solid, iterations=2)
div = (np.gradient(G[..., 0], h, axis=0) + np.gradient(G[..., 1], h, axis=1) + np.gradient(G[..., 2], h, axis=2)) * h / U0
m = ~near
m[[0, -1], :, :] = m[:, [0, -1], :] = m[:, :, [0, -1]] = False
out["grid_divergence_rms_far_from_body"] = float(np.sqrt((div[m] ** 2).mean()))
ring = binary_dilation(solid, iterations=2) & ~solid
out["grid_divergence_rms_next_to_body"] = float(np.sqrt((div[ring] ** 2).mean()))
spd = np.linalg.norm(G, axis=-1) / U0
out["fluid_voxels_below_0.02U_(particles deleted)"] = float(((spd < 0.02) & ~solid).sum() / (~solid).sum())
out["voxel_over_L"] = h / max(np.ptp(pts[:, i]) for i in range(3)) * 10  # L = domain/10 along x
print(json.dumps(out, indent=1, default=float))
