#!/usr/bin/env python3
"""FIX_PLAN step 3 probe (spec docs/reference/step3_wall_spec.md, Q2 and Q4): mesh only, no solve.

  python3 step3_probe.py edit CASE --feature-angle A     patch CASE/system/snappyHexMeshDict to the
                                                          locked layer and curvature settings
  python3 step3_probe.py report CASE                      layer table, checkMesh, cells, refinement
                                                          level of the body faces, STL tessellation

Locked settings (Q1 to Q4), COARSE mesh (cells_per_L 6, body level (2 3)):
  y_c = 100 nu / (0.0386 U (Re/2.67e6)^(-1/14)), h1 = 2 y_c, minThickness 0.5 h1 (metres),
  r = 1.3, n = ceil(1 + ln(Delta / (2 h1)) / ln r), Delta = (L/6) / 2^3, curvatureLevel (24 0 3 -1).
Runs inside WSL (numpy).
"""
import argparse
import json
import math
import re
import struct
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "wind_tunnel"))
import export_field as ef  # noqa: E402

CELLS_PER_L, LO, HI = 6, 2, 3


def read_stl(path: Path):
    data = path.read_bytes()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        v = [tuple(map(float, l.split()[1:4])) for l in data.decode(errors="replace").splitlines()
             if l.split()[:1] == ["vertex"]]
        return np.array(v).reshape(-1, 3, 3)
    n = struct.unpack("<I", data[80:84])[0]
    return np.array([struct.unpack("<12f", data[84 + 50 * k: 84 + 50 * k + 48])[3:] for k in range(n)]).reshape(n, 3, 3)


def settings(tris, U=20.0, nu=1.5e-5):
    lo, hi = tris.reshape(-1, 3).min(0), tris.reshape(-1, 3).max(0)
    L = float((hi - lo).max())
    Re = U * L / nu
    u_ref = 0.0386 * U * (Re / 2.67e6) ** (-1 / 14)
    y_c = 100 * nu / u_ref
    h1 = 2 * y_c
    level0 = L / CELLS_PER_L
    delta = level0 / 2 ** HI
    n = math.ceil(1 + math.log(delta / (2 * h1)) / math.log(1.3))
    return {"L": L, "Re": Re, "u_tau_ref": u_ref, "y_c": y_c, "h1": h1, "minThickness": 0.5 * h1,
            "level0": level0, "delta": delta, "n": n}


def edit(case: Path, angle: float, n=None, nc=24, lmax=HI):
    s = settings(read_stl(case / "constant/triSurface/body.stl"))
    s.update({"n": n or s["n"], "n_formula": s["n"], "curvature_cells_per_radius": nc, "curvature_lmax": lmax})
    p = case / "system/snappyHexMeshDict"
    t = p.read_text()
    subs = [
        (r"body \{ level \((\d+) (\d+)\); patchInfo", rf"body {{ level (\1 \2); curvatureLevel ({nc} 0 {lmax} -1); patchInfo"),
        (r"relativeSizes\s+true;", "relativeSizes false;"),
        (r"nSurfaceLayers\s+\d+;", f"nSurfaceLayers {s['n']};"),
        (r"finalLayerThickness\s+[\d.eE+-]+;", f"thicknessModel firstAndExpansion;\n    firstLayerThickness {s['h1']:.6g};"),
        (r"minThickness\s+[\d.eE+-]+;", f"minThickness {s['minThickness']:.6g};"),
        (r"featureAngle\s+[\d.]+;", f"featureAngle {angle:g};"),
    ]
    for pat, rep in subs:
        t, k = re.subn(pat, rep, t, count=1)
        if k != 1:
            sys.exit(f"pattern not found: {pat}")
    p.write_text(t)
    (case / "probe_settings.json").write_text(json.dumps({**s, "featureAngle": angle}, indent=1))
    print(json.dumps({**s, "featureAngle": angle}))


def layer_table(log: str):
    m = re.search(r"patch\s+faces\s+layers\s+overall thickness.*?-{3,}.*?\n(.*?)\n\s*\n", log, re.S)
    rows = {}
    for line in m.group(1).splitlines():
        f = line.split()
        if len(f) >= 6 and f[0] != "-----":            # v2512: patch faces target mesh thickness[m] [%]
            rows[f[0]] = {"faces": int(f[1]), "target": int(f[2]), "mesh_mean": float(f[3]),
                          "overall_thickness_m": float(f[4]), "thickness_pct_of_target": float(f[5])}
    ext = re.findall(r"Extruding (\d+) out of (\d+) faces", log)
    blocks = [b.split("Extruding")[0] for b in log.split("Checking mesh with layer")[1:]]

    def per_iter(pat):                         # a check line is printed only when it fails somewhere
        return [int(m.group(1)) if (m := re.search(pat + r"[^:\n]*:\s*(\d+)", b)) else 0 for b in blocks]

    tet = per_iter(r"tet quality < 1e-15")
    illegal = [int(m.group(1)) if (m := re.search(r"Detected (\d+) illegal faces", b)) else 0 for b in blocks]
    for r in rows.values():
        r["non_ortho_failures_per_iteration"] = per_iter(r"non-orthogonality >")
        r["pyramid_failures_per_iteration"] = per_iter(r"face pyramid volume <")
        r["faces_extruded_final"] = int(ext[-1][0])
        r["coverage_faces_extruded"] = int(ext[-1][0]) / int(ext[-1][1])
        r["layers_on_extruded_faces"] = r["mesh_mean"] / max(r["coverage_faces_extruded"], 1e-9)
        r["layer_iterations"] = len(tet)
        r["tet_quality_failures_per_iteration"] = tet
        r["illegal_faces_per_iteration"] = illegal
    return rows


def checkmesh(log: str):
    num = r"([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)"
    g = lambda pat: (float(re.search(pat, log).group(1)) if re.search(pat, log) else None)
    failed = re.search(r"Failed (\d+) mesh checks", log)
    return {"cells": int(g(r"cells:\s+(\d+)")), "failed_checks": int(failed.group(1)) if failed else 0,
            "mesh_ok": "Mesh OK." in log,
            "max_non_ortho": g(r"Mesh non-orthogonality Max: " + num),
            "max_skewness": g(r"Max skewness = " + num),
            "max_aspect": g(r"Max aspect ratio = " + num),
            "warnings": re.findall(r"\*\*\*.*", log)}


def tessellation(tris):
    v = np.unique(np.round(tris.reshape(-1, 3), 6), axis=0)
    c = v.mean(0)
    r = np.linalg.norm(v - c, axis=1)
    out = {"triangles": int(len(tris)), "vertices": int(len(v))}
    edge = np.linalg.norm(tris[:, 1] - tris[:, 0], axis=1)
    if len(v) > 50 and r.std() / r.mean() < 1e-3:
        out.update({"radius_m": float(r.mean()), "triangle_edge_m_median": float(np.median(edge))})
    zs = np.unique(np.round(v[:, 2] - c[2], 5))
    ico = len(tris) in [20 * 4 ** k for k in range(8)]
    if len(v) > 50 and r.std() / r.mean() < 1e-3 and not ico and len(zs) < 0.2 * len(v):   # UV sphere: rings along z
        z = np.unique(np.round(v[:, 2] - c[2], 5))
        rings = len(z) - 1                                             # ring bands between the poles
        segs = int(round((len(v) - 2) / (rings - 1)))
        out.update({"kind": "UV sphere", "rings": rings, "segments": segs,
                    "segment_angle_deg": 360 / segs})
    elif "radius_m" in out:
        out["kind"] = "icosphere" if ico else "sphere"
    return out


def report(case: Path):
    s = json.loads((case / "probe_settings.json").read_text())
    tris = read_stl(case / "constant/triSurface/body.stl")
    pm = case / "constant/polyMesh"
    pts = ef.read_points(pm)
    sizes, starts, toks = ef.read_faces(pm)
    owner = ef.read_labels(pm / "owner")
    s0, nf = ef.read_boundary(pm)["body"]
    faces = np.arange(s0, s0 + nf)
    fc, fa = ef.face_geometry(pts, sizes, starts, toks, faces)
    A = np.linalg.norm(fa, axis=1)
    lev_area = np.round(np.log2(s["level0"] / np.sqrt(A))).astype(int)  # level from the face size
    out = {"settings": s, "stl": tessellation(tris),
           "layers": layer_table((case / "log.snappyHexMesh").read_text()),
           "checkMesh": checkmesh((case / "log.checkMesh").read_text()),
           "body_faces": int(nf)}
    cl = pm / "cellLevel"
    if cl.exists():
        lev = ef.read_labels(cl)[owner[faces]]
        out["level_source"] = "cellLevel of the body-face owner cell"
    else:
        lev = lev_area
        out["level_source"] = "round(log2(level0 / sqrt(face area)))"
    out["level_area_fraction"] = {int(k): float(A[lev == k].sum() / A.sum()) for k in np.unique(lev)}
    out["level_from_face_area_fraction"] = {int(k): float(A[lev_area == k].sum() / A.sum()) for k in np.unique(lev_area)}
    c = tris.reshape(-1, 3).mean(0)
    if "radius_m" in out["stl"]:                                       # sphere: front, side, rear
        ux = (fc[:, 0] - c[0]) / np.linalg.norm(fc - c, axis=1)
        reg = {"front ux>0.5": ux > 0.5, "side |ux|<=0.5": np.abs(ux) <= 0.5, "rear ux<-0.5": ux < -0.5}
        out["level_by_region"] = {k: {int(l): float(A[m & (lev == l)].sum() / A[m].sum()) for l in np.unique(lev[m])}
                                  for k, m in reg.items()}
        eq = np.abs(fc[:, 2] - c[2]) < 0.5 * np.sqrt(np.median(A))     # one row of faces at the equator
        ang = np.arctan2(fc[eq, 1] - c[1], fc[eq, 0] - c[0])
        out["cells_around_equator"] = int(len(np.unique(np.round(ang, 3))))
        out["cells_around_from_level"] = {int(l): 2 * math.pi * out["stl"]["radius_m"] / (s["level0"] / 2 ** l)
                                          for l in np.unique(lev)}
    print(json.dumps(out, indent=1))
    (case / "probe_report.json").write_text(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["edit", "report"])
    ap.add_argument("case", type=Path)
    ap.add_argument("--feature-angle", type=float, default=120)
    ap.add_argument("--n", type=int, help="override nSurfaceLayers (default: the half-cell formula)")
    ap.add_argument("--nc", type=int, default=24, help="curvatureLevel cells per radius")
    ap.add_argument("--lmax", type=int, default=HI, help="curvatureLevel max level")
    a = ap.parse_args()
    edit(a.case, a.feature_angle, a.n, a.nc, a.lmax) if a.mode == "edit" else report(a.case)


if __name__ == "__main__":
    main()
