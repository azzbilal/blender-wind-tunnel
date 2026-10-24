#!/usr/bin/env python3
"""Runs inside WSL after a 3D solve: turns the OpenFOAM result into what Blender needs.

  field.npz    velocity (m/s) and pressure (Pa, relative to the freestream static pressure p_inf)
               on a regular voxel grid around the body, plus a solid mask; Blender writes it to an
               OpenVDB volume that Geometry Nodes samples
  forces.json  drag, lift and side force on the body (pressure + wall shear, summed face by face),
               the frontal area, Cd, Cl and p_inf

p_inf is the area-weighted mean static p on the inlet patch (docs/reference/step1_cp_reference.md).

Reads the reconstructed case in ASCII (latest time). Needs numpy and scipy (python3-numpy,
python3-scipy). Usage: python3 export_field.py CASE --speed U --rho RHO --nu NU --voxel H --L L
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

try:
    from . import convergence, transient
except ImportError:                 # run as a script next to convergence.py and transient.py
    import convergence
    import transient

NUM = rb"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def body(raw: bytes) -> bytes:
    """The data after the FoamFile header, without comments."""
    raw = re.sub(rb"/\*.*?\*/", b"", raw, flags=re.S)
    raw = re.sub(rb"//[^\n]*", b"", raw)
    i = raw.find(b"FoamFile")
    if i >= 0:
        raw = raw[raw.index(b"}", i) + 1:]
    return raw


def list_block(raw: bytes, start=0):
    """`N ( ... )` from `start`: (N, inner bytes)."""
    m = re.compile(rb"(\d+)\s*\(").search(raw, start)
    n = int(m.group(1))
    depth, i = 1, m.end()
    j = i
    while depth:
        nxt_o = raw.find(b"(", j)
        nxt_c = raw.find(b")", j)
        if nxt_o != -1 and nxt_o < nxt_c:
            depth += 1
            j = nxt_o + 1
        else:
            depth -= 1
            j = nxt_c + 1
    return n, raw[i:j - 1]


def numbers(chunk: bytes):
    return np.array(chunk.replace(b"(", b" ").replace(b")", b" ").split(), dtype=float)


def read_points(pm: Path):
    n, inner = list_block(body(pm.joinpath("points").read_bytes()))
    return numbers(inner).reshape(n, 3)


def read_labels(path: Path):
    n, inner = list_block(body(path.read_bytes()))
    return np.array(inner.split(), dtype=np.int64)


def read_faces(pm: Path):
    """Faces as (sizes, flat vertex list)."""
    raw = body(pm.joinpath("faces").read_bytes())
    m = re.compile(rb"(\d+)\s*\(").search(raw)
    nf = int(m.group(1))
    toks = np.array(raw[m.end(): raw.rindex(b")")].replace(b"(", b" ").replace(b")", b" ").split(), dtype=np.int64)
    sizes = np.empty(nf, dtype=np.int64)
    starts = np.empty(nf, dtype=np.int64)
    k = 0
    for f in range(nf):
        s = toks[k]
        sizes[f], starts[f] = s, k + 1
        k += s + 1
    return sizes, starts, toks


def read_boundary(pm: Path):
    raw = body(pm.joinpath("boundary").read_bytes()).decode(errors="replace")
    out = {}
    for name, blk in re.findall(r"(\w+)\s*\{([^{}]*)\}", raw):
        sf = re.search(r"startFace\s+(\d+)", blk)
        nf = re.search(r"nFaces\s+(\d+)", blk)
        if sf and nf:
            out[name] = (int(sf.group(1)), int(nf.group(1)))
    return out


def read_internal(path: Path, width: int, ncells: int):
    raw = body(path.read_bytes())
    m = re.search(rb"internalField\s+uniform\s+(\([^)]*\)|" + NUM + rb")", raw)
    if m:
        v = numbers(m.group(1))
        return np.tile(v, (ncells, 1)) if width > 1 else np.full(ncells, v[0])
    i = raw.index(b"internalField")
    n, inner = list_block(raw, i)
    v = numbers(inner)
    return v.reshape(n, width) if width > 1 else v


def read_patch_values(path: Path, patch: str, n: int):
    raw = body(path.read_bytes())
    m = re.search(rb"\b" + patch.encode() + rb"\s*\{", raw)
    if not m:
        return np.zeros(n)
    depth, i = 1, m.end()
    while depth:
        depth += raw[i:i + 1] == b"{"
        depth -= raw[i:i + 1] == b"}"
        i += 1
    blk = raw[m.end():i - 1]
    if b"nonuniform" in blk:
        _, inner = list_block(blk, blk.index(b"nonuniform"))
        return numbers(inner)
    u = re.search(rb"value\s+uniform\s+(" + NUM + rb")", blk)
    return np.full(n, float(u.group(1)) if u else 0.0)


def latest_time(case: Path):
    times = []
    for d in case.iterdir():
        try:
            if d.is_dir() and float(d.name) > 0 and (d / "U").exists():
                times.append(d.name)
        except ValueError:
            pass
    return max(times, key=float)


def face_geometry(pts, sizes, starts, toks, faces):
    """Centres and area vectors of the given faces (triangle fan about the vertex mean)."""
    cen = np.empty((len(faces), 3))
    area = np.empty((len(faces), 3))
    for out_i, f in enumerate(faces):
        v = pts[toks[starts[f]:starts[f] + sizes[f]]]
        c = v.mean(axis=0)
        a = 0.5 * np.cross(v - c, np.roll(v, -1, axis=0) - c).sum(axis=0)
        cen[out_i], area[out_i] = c, a
    return cen, area


def cell_centres(pts, sizes, starts, toks, owner, neigh, ncells):
    """Mean of each cell's face centres (vectorised by face size)."""
    nf = len(sizes)
    fc = np.empty((nf, 3))
    for s in np.unique(sizes):
        idx = np.nonzero(sizes == s)[0]
        cols = starts[idx][:, None] + np.arange(s)[None, :]
        fc[idx] = pts[toks[cols]].mean(axis=1)
    acc = np.zeros((ncells, 3))
    cnt = np.zeros(ncells)
    np.add.at(acc, owner, fc)
    np.add.at(cnt, owner, 1)
    ni = len(neigh)
    np.add.at(acc, neigh, fc[:ni])
    np.add.at(cnt, neigh, 1)
    return acc / cnt[:, None]


def inside_mask(tris, grid_x, grid_y, grid_z):
    """Voxels inside the closed surface, by counting crossings of rays along +x for every (y, z) column.

    Nodes on the surface count as solid, the same on every face. A ray through a mesh edge or vertex
    is a tie (two crossings, or none), so each column is cast four times, offset by
    (+-1e-3 dy, +-0.618e-3 dz) (unequal, so no offset runs along a 45 degree diagonal), and the four
    results are OR'ed; the x span is widened by 1e-3 dx. A wall exactly on a grid plane then gives
    the same layer on both sides of the body (open issue e)."""
    ny, nz = len(grid_y), len(grid_z)
    y0, dy = grid_y[0], grid_y[1] - grid_y[0]
    z0, dz = grid_z[0], grid_z[1] - grid_z[0]
    ex = 1e-3 * (grid_x[1] - grid_x[0])
    solid = np.zeros((len(grid_x), ny, nz), dtype=bool)
    for oy, oz in ((sy * 1e-3 * dy, sz * 0.618e-3 * dz) for sy in (1, -1) for sz in (1, -1)):
        hits = [[[] for _ in range(nz)] for _ in range(ny)]
        for a, b, c in tris:
            ymin, ymax = min(a[1], b[1], c[1]), max(a[1], b[1], c[1])
            zmin, zmax = min(a[2], b[2], c[2]), max(a[2], b[2], c[2])
            j0, j1 = max(int(np.floor((ymin - y0) / dy)), 0), min(int(np.ceil((ymax - y0) / dy)), ny - 1)
            k0, k1 = max(int(np.floor((zmin - z0) / dz)), 0), min(int(np.ceil((zmax - z0) / dz)), nz - 1)
            if j0 > j1 or k0 > k1:
                continue
            d = (b[1] - a[1]) * (c[2] - a[2]) - (c[1] - a[1]) * (b[2] - a[2])
            if abs(d) < 1e-18:
                continue
            py, pz = np.meshgrid(y0 + oy + dy * np.arange(j0, j1 + 1), z0 + oz + dz * np.arange(k0, k1 + 1),
                                 indexing="ij")
            u = ((py - a[1]) * (c[2] - a[2]) - (c[1] - a[1]) * (pz - a[2])) / d
            v = ((b[1] - a[1]) * (pz - a[2]) - (py - a[1]) * (b[2] - a[2])) / d
            for j, k in zip(*np.nonzero((u >= 0) & (v >= 0) & (u + v <= 1))):
                hits[j0 + j][k0 + k].append(a[0] + u[j, k] * (b[0] - a[0]) + v[j, k] * (c[0] - a[0]))
        for j in range(ny):
            for k in range(nz):
                xs = sorted(hits[j][k])
                for m in range(0, len(xs) - 1, 2):
                    solid[(grid_x >= xs[m] - ex) & (grid_x <= xs[m + 1] + ex), j, k] = True
    return solid


def frontal_area(tris, n=400):
    """Area of the body's shadow on the y-z plane (rasterised)."""
    ys = np.array([[p[1] for p in t] for t in tris])
    zs = np.array([[p[2] for p in t] for t in tris])
    y0, y1, z0, z1 = ys.min(), ys.max(), zs.min(), zs.max()
    h = max(y1 - y0, z1 - z0) / n
    gy = y0 + h * (np.arange(int((y1 - y0) / h) + 1) + 0.5)
    gz = z0 + h * (np.arange(int((z1 - z0) / h) + 1) + 0.5)
    cover = np.zeros((len(gy), len(gz)), dtype=bool)
    for ty, tz in zip(ys, zs):
        j0, j1 = np.searchsorted(gy, ty.min()), np.searchsorted(gy, ty.max())
        k0, k1 = np.searchsorted(gz, tz.min()), np.searchsorted(gz, tz.max())
        if j0 >= j1 or k0 >= k1:
            continue
        Y, Z = np.meshgrid(gy[j0:j1], gz[k0:k1], indexing="ij")
        (ay, by, cy), (az, bz, cz) = ty, tz
        d = (by - ay) * (cz - az) - (cy - ay) * (bz - az)
        if abs(d) < 1e-18:
            continue
        u = ((Y - ay) * (cz - az) - (cy - ay) * (Z - az)) / d
        v = ((by - ay) * (Z - az) - (Y - ay) * (bz - az)) / d
        cover[j0:j1, k0:k1] |= (u >= 0) & (v >= 0) & (u + v <= 1)
    return cover.sum() * h * h


def body_forces(case, t, pts, sizes, starts, toks, owner, cc, U, p, rho, nu):
    """Pressure and viscous force vectors on the `body` patch, in newtons.

    Pressure: rho p_P Sf (p is zeroGradient on the wall, so p_P is the face value).
    Viscous: rho (nu + nut_w) |Sf| U_t,P / d_n, the tangential part of OpenFOAM's
    Sf & rho nuEff devTwoSymm(grad U) (docs/reference/step0_openfoam_build.md).
    """
    start, nb = read_boundary(case / "constant" / "polyMesh")["body"]
    bf = np.arange(start, start + nb)
    fcen, farea = face_geometry(pts, sizes, starts, toks, bf)
    own = owner[bf]
    A = np.linalg.norm(farea, axis=1)
    n = farea / A[:, None]                       # out of the air, into the body
    nut_w = read_patch_values(case / t / "nut", "body", nb)
    dn = np.abs(((fcen - cc[own]) * n).sum(axis=1))
    u = U[own]
    ut = u - n * (u * n).sum(axis=1)[:, None]
    f_p = p[own][:, None] * farea
    f_v = ut * ((nu + nut_w) * A / np.maximum(dn, 1e-12))[:, None]
    return rho * f_p.sum(axis=0), rho * f_v.sum(axis=0)


def inlet_reference_pressure(p, owner, Sf):
    """Freestream static pressure p_inf: area-weighted mean of p over a patch, from its faces' owner
    cells (p is zeroGradient on the inlet, so the owner value is the face value). Same units as p;
    OpenFOAM's surfaceFieldValue areaAverage of p on the inlet patch."""
    A = np.linalg.norm(Sf, axis=1)
    return float((p[owner] * A).sum() / A.sum())


def cp_from_p(p, p_inf, U_inf):
    """Pressure coefficient (p - p_inf) / (0.5 U_inf^2), p and p_inf kinematic (m2/s2)."""
    return (p - p_inf) / (0.5 * U_inf ** 2)


def forces_record(t, ncells, Fp, Fv, Af, speed, rho, p_inf):
    """forces.json content. Forces in N; p_inf (the Cp reference, inlet mean) is kinematic, reported in Pa
    and as its offset from the outlet p = 0 in units of q (p_inf_Cp_vs_outlet)."""
    F = Fp + Fv
    q = 0.5 * rho * speed ** 2
    return {"time": t, "cells": ncells, "drag_N": F[0], "side_N": F[1], "lift_N": F[2],
            "pressure_drag_N": Fp[0], "friction_drag_N": Fv[0], "frontal_area_m2": Af,
            "pressure_N": Fp.tolist(), "viscous_N": Fv.tolist(),
            "Cd": F[0] / (q * Af), "Cl": F[2] / (q * Af), "speed": speed, "rho": rho,
            "p_inf_Pa": rho * p_inf, "p_inf_Cp_vs_outlet": p_inf / (0.5 * speed ** 2)}


YPLUS_MAX, AREA_REQUIRED, COVERAGE_REQUIRED = 300.0, 0.9, 0.9      # docs/reference/step3_wall_spec.md


def yplus_record(yplus, A, d, y_c=None):
    """forces.json wall.yplus: OpenFOAM yPlus on the body faces (first cell centre, nearWallDist),
    area-weighted. Gate: y+ <= 300 on at least 90 % of the area. The y+ > 300 area is split at
    d = 2 y_c (spec amendment D2; d first cell-centre distance, y_c its design value, m):
    gt300_thick_first_cell (cut layers) and gt300_design_first_cell (u_tau above the sizing anchor)."""
    w = A / A.sum()
    le = float(w[yplus <= YPLUS_MAX].sum())
    high = yplus > YPLUS_MAX
    split = lambda m: None if y_c is None else float(w[high & m].sum())
    return {"min": float(yplus.min()), "mean": float((w * yplus).sum()), "max": float(yplus.max()),
            "le_300": le, "band_30_300": float(w[(yplus > 30) & (yplus < YPLUS_MAX)].sum()),
            "lt_5": float(w[yplus < 5].sum()), "gate": le >= AREA_REQUIRED, "required": AREA_REQUIRED,
            "y_c": y_c, "gt300_thick_first_cell": split(d > 2 * (y_c or 0)),
            "gt300_design_first_cell": split(d <= 2 * (y_c or 0))}


def layer_record(log: str):
    """forces.json wall.layers from log.snappyHexMesh: coverage = faces extruded / body faces from the
    final "Extruding X out of Y faces" line (gate: at least 90 %), and snappy's layer table for the body
    (v2512: patch faces target mesh thickness[m] [%]; v1912: patch faces layers thickness[m] [%])."""
    rec = {"coverage": None, "faces_extruded": None, "body_faces": None, "layers_target": None,
           "layers_mean": None, "thickness_m": None, "thickness_pct": None, "gate": None,
           "required": COVERAGE_REQUIRED}
    ext = re.findall(r"Extruding (\d+) out of (\d+) faces", log)
    if ext:
        done, total = map(int, ext[-1])
        rec.update(coverage=done / total, faces_extruded=done, body_faces=total,
                   gate=done / total >= COVERAGE_REQUIRED)
    tables = re.findall(r"patch\s+faces\s+layers\s+overall thickness[^\n]*\n(.*?)\n\s*\n", log, re.S)
    for line in (tables[-1].splitlines() if tables else []):
        f = line.split()
        if f[:1] == ["body"]:
            if len(f) >= 6:
                rec.update(layers_target=int(f[2]), layers_mean=float(f[3]), thickness_m=float(f[4]),
                           thickness_pct=float(f[5]))
            elif len(f) == 5:
                rec.update(layers_mean=float(f[2]), thickness_m=float(f[3]), thickness_pct=float(f[4]))
    return rec


def wall_record(case, t, pts, sizes, starts, toks, owner, cc, y_c=None):
    """y+ (the yPlus field Allrun writes after reconstructPar; None if it is missing) and layer coverage."""
    start, nb = read_boundary(case / "constant" / "polyMesh")["body"]
    bf = np.arange(start, start + nb)
    fcen, farea = face_geometry(pts, sizes, starts, toks, bf)
    A = np.linalg.norm(farea, axis=1)
    d = np.abs(((cc[owner[bf]] - fcen) * farea / A[:, None]).sum(axis=1))
    yp = case / t / "yPlus"
    log = case / "log.snappyHexMesh"
    return {"yplus": yplus_record(read_patch_values(yp, "body", nb), A, d, y_c) if yp.exists() else None,
            "layers": layer_record(log.read_text(errors="replace") if log.exists() else "")}


def verdict_record(case, cap, Af, speed, rho):
    """forces.json convergence keys (FIX_PLAN step 2): the gate verdict at the last recorded iteration
    of the full history, Cd/Cl/Cs as window mean/min/max and the forces (N) as window means, all from
    the forces function object. Cd = Fx, Cs = Fy, Cl = Fz, each over q A_frontal."""
    h = convergence.history(case)
    v = convergence.gate(h["time"], h["fx"], h["fy"], h["fz"], h["p_initial"], cap=cap)
    qa = 0.5 * rho * speed ** 2 * Af
    rec = {"converged": v["converged"], "reasons": v["reasons"], "iterations": v["iteration"],
           "window": list(v["window"]) if v["window"] else None, "Cd_band": v["band"],
           "p_initial": v["residual"], "p_trend": v["residual_trend"]}
    for c, k in (("Cd", "fx"), ("Cs", "fy"), ("Cl", "fz")):
        for s in ("mean", "min", "max"):
            rec[f"{c}_{s}"] = v[k][s] / qa if v[k] else None
    for name, k in (("drag_N", "fx"), ("side_N", "fy"), ("lift_N", "fz")):
        rec[f"{name}_mean"] = v[k]["mean"] if v[k] else None
    return rec


def voxel_grid(tris, pts, L, h, max_voxels):
    """The grid Blender samples: 0.75 L around the body, 2.5 L behind it, inside the mesh; the voxel h
    grows by 10 % steps until the grid has at most max_voxels nodes. Returns (origin, h, gx, gy, gz)."""
    lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
    blo = np.array([lo[0] - 0.75 * L, lo[1] - 0.75 * L, lo[2] - 0.75 * L])
    bhi = np.array([hi[0] + 2.5 * L, hi[1] + 0.75 * L, hi[2] + 0.75 * L])
    blo = np.maximum(blo, pts.min(axis=0))
    bhi = np.minimum(bhi, pts.max(axis=0))
    while np.prod(np.ceil((bhi - blo) / h) + 1) > max_voxels:
        h *= 1.1
    nx, ny, nz = (np.ceil((bhi - blo) / h).astype(int) + 1)
    return blo, h, blo[0] + h * np.arange(nx), blo[1] + h * np.arange(ny), blo[2] + h * np.arange(nz)


def idw_weights(cc, q_pts, dtype=np.float64):
    """Inverse-distance-squared weights of the 4 nearest cell centres for every query point:
    (idx int32, w dtype), rows of w sum to 1. Computed once and reused for every frame."""
    dist, idx = cKDTree(cc).query(q_pts, k=4, workers=-1)
    w = 1.0 / np.maximum(dist, 1e-9) ** 2
    w /= w.sum(axis=1, keepdims=True)
    return idx.astype(np.int32), w.astype(dtype)


def idw_apply(values, idx, w):
    """Cell values (n,) or (n, 3) interpolated with idw_weights."""
    v = values[idx]
    return (v * w[..., None]).sum(axis=1) if v.ndim == 3 else (v * w).sum(axis=1)


def gather_cells(parts, ncells):
    """Global cell array from per-processor (cellProcAddressing, values) pairs; every cell exactly once."""
    first = parts[0][1]
    out = np.empty((ncells,) + first.shape[1:], dtype=first.dtype)
    seen = np.zeros(ncells, dtype=bool)
    for addr, vals in parts:
        out[addr] = vals
        seen[addr] = True
    if not seen.all():
        raise ValueError(f"{int((~seen).sum())} cells missing from the processor fields")
    return out


def frame_dirs(case: Path, fps=transient.FPS_CFD):
    """{frame k: time directory name} of the decomposed case's written times that hold U."""
    out = {}
    for d in (Path(case) / "processor0").iterdir():
        k = transient.frame_from_time(d.name, fps)
        if k is not None and (d / "U").exists():
            out[k] = d.name
    return dict(sorted(out.items()))


def write_field_npz(path, origin, voxel, U, p, solid, speed, rho, p_inf):
    """field.npz: U (m/s) and p = rho (p - p_inf) in Pa on the voxel grid, both 0 inside the body.
    p and p_inf are kinematic; viz3d.write_vdb turns p into cp = p / (0.5 rho U^2)."""
    U = U.copy()
    pg = rho * (p - p_inf)
    U[solid] = 0.0
    pg[solid] = 0.0
    np.savez_compressed(path, origin=origin, voxel=voxel, U=U.astype(np.float32), p=pg.astype(np.float32),
                        solid=solid, speed=speed, p_inf_Pa=rho * p_inf)


# ---------------------------------------------------------------- time-resolved frames (TRANSIENT T1)
_CTX = {}


def _export_frame(item):
    """One frame: U and p gathered from the processor directories, interpolated with the cached weights,
    p referenced to this frame's inlet mean. Runs in a forked worker that shares _CTX."""
    k, tname = item
    c = _CTX
    U = gather_cells([(addr, read_internal(proc / tname / "U", 3, len(addr))) for proc, addr in c["procs"]],
                     c["ncells"])
    p = gather_cells([(addr, read_internal(proc / tname / "p", 1, len(addr))) for proc, addr in c["procs"]],
                     c["ncells"])
    p_inf = inlet_reference_pressure(p, c["inlet_owner"], c["inlet_Sf"])
    nx, ny, nz = c["shape"]
    Ug = idw_apply(U, c["idx"], c["w"]).reshape(nx, ny, nz, 3)
    pg = idw_apply(p, c["idx"], c["w"]).reshape(nx, ny, nz)
    write_field_npz(c["out"] / transient.frame_name(k, "npz"), c["origin"], c["h"], Ug, pg, c["solid"],
                    c["speed"], c["rho"], p_inf)
    return k, tname, c["rho"] * p_inf


def export_frames(case, a):
    """frames/flow_kkkk.npz for every written frame of the decomposed case, plus frames/index.json.
    The mesh, the solid mask and the interpolation weights are computed once; frames go in parallel."""
    import multiprocessing as mp
    pm = case / "constant" / "polyMesh"
    pts = read_points(pm)
    sizes, starts, toks = read_faces(pm)
    owner = read_labels(pm / "owner")
    neigh = read_labels(pm / "neighbour")
    ncells = int(max(owner.max(), neigh.max())) + 1
    cc = cell_centres(pts, sizes, starts, toks, owner, neigh, ncells)
    start, n = read_boundary(pm)["inlet"]
    inlet = np.arange(start, start + n)
    _, Sf_in = face_geometry(pts, sizes, starts, toks, inlet)
    tris_raw = Path(case / "constant" / "triSurface" / "body.stl").read_bytes()
    nt = int.from_bytes(tris_raw[80:84], "little")
    arr = np.frombuffer(tris_raw[84:84 + 50 * nt], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    tris = arr["v"].astype(float)
    blo, h, gx, gy, gz = voxel_grid(tris, pts, a.L, a.voxel, a.max_voxels)
    X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")
    idx, w = idw_weights(cc, np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]), dtype=np.float32)
    del X, Y, Z
    solid = inside_mask(tris, gx, gy, gz)
    procs = sorted((d for d in case.iterdir() if d.name.startswith("processor")), key=lambda d: int(d.name[9:]))
    frames = frame_dirs(case, a.fps)
    out = case / "frames"
    out.mkdir(exist_ok=True)
    _CTX.update(procs=[(d, read_labels(d / "constant" / "polyMesh" / "cellProcAddressing")) for d in procs],
                ncells=ncells, inlet_owner=owner[inlet], inlet_Sf=Sf_in, shape=(len(gx), len(gy), len(gz)),
                idx=idx, w=w, solid=solid, origin=blo, h=h, speed=a.speed, rho=a.rho, out=out)
    print("cells", ncells, "grid", len(gx), len(gy), len(gz), "voxel", h, "solid", int(solid.sum()),
          "frames", len(frames), flush=True)
    with mp.get_context("fork").Pool(a.jobs) as pool:
        done = sorted(pool.imap_unordered(_export_frame, frames.items()))
    index = {"fps": a.fps, "speed": a.speed, "L": a.L, "voxel": h, "origin": blo.tolist(),
             "frames": [{"k": k, "time": tn, "p_inf_Pa": pi} for k, tn, pi in done]}
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print("exported", len(done), "frames", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--speed", type=float, required=True)
    ap.add_argument("--rho", type=float, default=1.225)
    ap.add_argument("--nu", type=float, default=1.5e-5)
    ap.add_argument("--voxel", type=float, required=True)
    ap.add_argument("--L", type=float, required=True)
    ap.add_argument("--max-voxels", type=int, default=4_000_000)
    ap.add_argument("--cap", type=int, default=None, help="iteration cap (controlDict endTime)")
    ap.add_argument("--u-tau-ref", type=float, default=None, help="u_tau the layers were sized with, m/s")
    ap.add_argument("--y-c", type=float, default=None, help="design first cell-centre distance, m")
    ap.add_argument("--frames", action="store_true", help="time-resolved: one npz per written frame")
    ap.add_argument("--fps", type=int, default=transient.FPS_CFD, help="frames per second of flow time")
    ap.add_argument("--jobs", type=int, default=20, help="frames exported in parallel")
    a = ap.parse_args()
    case = Path(a.case)
    if a.frames:
        return export_frames(case, a)
    pm = case / "constant" / "polyMesh"
    t = latest_time(case)
    print("time", t, flush=True)

    pts = read_points(pm)
    sizes, starts, toks = read_faces(pm)
    owner = read_labels(pm / "owner")
    neigh = read_labels(pm / "neighbour")
    ncells = int(max(owner.max(), neigh.max())) + 1
    cc = cell_centres(pts, sizes, starts, toks, owner, neigh, ncells)
    U = read_internal(case / t / "U", 3, ncells)
    p = read_internal(case / t / "p", 1, ncells)
    print("cells", ncells, flush=True)

    # ---- forces on the body (pressure + wall shear), in newtons
    Fp, Fv = body_forces(case, t, pts, sizes, starts, toks, owner, cc, U, p, a.rho, a.nu)
    start, n = read_boundary(pm)["inlet"]
    inlet = np.arange(start, start + n)
    _, Sf_in = face_geometry(pts, sizes, starts, toks, inlet)
    p_inf = inlet_reference_pressure(p, owner[inlet], Sf_in)

    tris_raw = Path(case / "constant" / "triSurface" / "body.stl").read_bytes()
    nt = int.from_bytes(tris_raw[80:84], "little")
    arr = np.frombuffer(tris_raw[84:84 + 50 * nt], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))
    tris = arr["v"].astype(float)
    Af = frontal_area(tris)
    forces = forces_record(t, ncells, Fp, Fv, Af, a.speed, a.rho, p_inf)
    forces.update(verdict_record(case, a.cap, Af, a.speed, a.rho))
    forces["wall"] = wall_record(case, t, pts, sizes, starts, toks, owner, cc, a.y_c)
    forces["wall"]["u_tau_ref"] = a.u_tau_ref
    (case / "forces.json").write_text(json.dumps(forces, indent=2))
    print(json.dumps(forces), flush=True)

    # ---- the voxel grid Blender samples
    blo, h, gx, gy, gz = voxel_grid(tris, pts, a.L, a.voxel, a.max_voxels)
    nx, ny, nz = len(gx), len(gy), len(gz)
    X, Y, Z = np.meshgrid(gx, gy, gz, indexing="ij")
    idx, w = idw_weights(cc, np.column_stack([X.ravel(), Y.ravel(), Z.ravel()]))
    Ug = idw_apply(U, idx, w).reshape(nx, ny, nz, 3)
    pg = idw_apply(p, idx, w).reshape(nx, ny, nz)
    solid = inside_mask(tris, gx, gy, gz)
    write_field_npz(case / "field.npz", blo, h, Ug, pg, solid, a.speed, a.rho, p_inf)
    print("grid", nx, ny, nz, "voxel", h, flush=True)


if __name__ == "__main__":
    sys.exit(main())
