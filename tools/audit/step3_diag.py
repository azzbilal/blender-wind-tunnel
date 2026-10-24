#!/usr/bin/env python3
"""FIX_PLAN step 3 Stage A diagnostic bundle (SESSION_LOG NEXT PROMPT): copies only, in ~/wind_tunnel/_step3/diag.

  python3 step3_diag.py all          (inside WSL; about 20 min; writes _step3/diag/bundle.json)

1. Cone mesh-only variants (snappy up to checkMesh, then reconstructParMesh), each written by case3d.write_case
   from 3d_Cone's body.stl with the locked COARSE settings, then one addLayersControls value patched:
     V0_locked      none (calibration: run_Cone has 363,277 cells, 36 % of the area with d > 2 y_c)
     V1_nSmooth2    nSmoothThickness 10 -> 2
     V2_buffer_m1   nBufferCellsNoExtrude 0 -> -1 (snappyLayerDriver.C:2545-2582: no truncation buffer; a face
                    takes the minimum layer count of its extruded points)
     V3_h1x064_n5   h1 x 0.64 with n pinned at 5 (Setup3D u_tau = u_tau_ref / 0.64, layers 5); minThickness
                    follows (0.5 h1)
     V4_fa120       featureAngle 60 -> 120, judged by d rather than coverage
   Per variant: cells, coverage and layer table (snappy log), checkMesh, d per body face (normal distance from the
   owner cell centre to the face plane, as tools/audit/step3_yplus.py), area fraction with d > 2 y_c, and the
   predicted y+ <= 300 fraction: run_Cone's per-face u_tau (yPlus nu / d at 781) mapped onto the new faces by
   nearest face centre, y+ = d_new u_tau / nu.
   Predictor check: the same mapping onto run_Cone_remesh against its measured yPlus at 716 (75.5 %).
2. One cone solve of the best variant through the real Allrun (step3_tracer.run with a patch hook), no re-mesh.
3. Sphere attribution: 3d_Sphere (old mesh, v1912 fields at 400) continued with v2512 simpleFoam to 3000 under
   the step 2 gate FOs (run_Sphere's controlDict and fvSolution, which differ from 3d_Sphere's only by the
   removed residualControl); oscillation statistics by one function for both runs.
"""
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import step3_tracer as tr  # noqa: E402  (registers the wind_tunnel package)
import step3_probe as pr  # noqa: E402  (puts wind_tunnel/ on sys.path, imports export_field as ef)
from step3_yplus import wquantile  # noqa: E402
import convergence  # noqa: E402

ef, case3d = pr.ef, tr.case3d
W = Path.home() / "wind_tunnel"
S3 = W / "_step3"
D = S3 / "diag"
NU = 1.5e-5
BASH = ". /usr/lib/openfoam/openfoam2512/etc/bashrc > /dev/null 2>&1; " \
       "export OMPI_MCA_btl_vader_single_copy_mechanism=none; "
DEFAULTS = {"nSmoothThickness": 10, "nBufferCellsNoExtrude": 0, "featureAngle": 60}
VARIANTS = {
    "V0_locked": {},
    "V1_nSmooth2": {"nSmoothThickness": 2},
    "V2_buffer_m1": {"nBufferCellsNoExtrude": -1},
    "V3_h1x064_n5": {"h1_scale": 0.64, "layers": 5},
    "V4_fa120": {"featureAngle": 120},
}
# Added after the first pass (V0 layerFields map: the cut layers sit where curvatureLevel mixes level 2 and 3
# faces on the side, and next to the base rim, a 117 deg turn of the normals): uniform body level 3.
EXTRA = {
    "V5_level33": {"surface_levels": (3, 3)},
    "V6_level33_fa120": {"surface_levels": (3, 3), "featureAngle": 120},
}
CRITERION = ("best variant (pre-registered before the solve): the highest predicted y+ <= 300 fraction among "
             "V1 to V4 with coverage >= 90 %, checkMesh failed checks <= V0, max skewness <= 1.05 x V0 and "
             "max non-orthogonality <= V0 + 1 deg; tie-break the lower d > 2 y_c fraction. Solved only if its "
             "predicted fraction is above V0's.")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def cone_tris(body="Cone"):
    return case3d.read_stl(W / f"3d_{body}" / "constant/triSurface/body.stl")


def base_sizing():
    tris = cone_tris()
    lo, hi = case3d.bounds(tris)
    L = max(h - l for l, h in zip(lo, hi))
    s = case3d.Setup3D(surface_levels=(2, 3), wake_level=2, cells_per_L=6, procs=24)
    return L, case3d.layer_sizing(L, s)


def setup_kw(v):
    """u_tau and layers for tr.run / Setup3D: h1 scales as 1 / u_tau with n pinned."""
    if "h1_scale" not in v:
        return {"u_tau": None, "layers": None}
    return {"u_tau": base_sizing()[1]["u_tau_ref"] / v["h1_scale"], "layers": v["layers"]}


def patcher(v):
    def patch(root):
        p = Path(root) / "system/snappyHexMeshDict"
        t = p.read_text()
        a = t.index("addLayersControls")
        head, tail = t[:a], t[a:]
        if "curvature_nc" in v:
            head, n = re.subn(r"curvatureLevel \(24 ", f"curvatureLevel ({v['curvature_nc']} ", head, count=1)
            assert n == 1, "curvatureLevel (24 not found once"
        for k, d in DEFAULTS.items():
            if k in v:
                tail, n = re.subn(rf"(\n\s*{k}\s+){d};", rf"\g<1>{v[k]};", tail, count=1)
                assert n == 1, f"{k} {d} not found once in addLayersControls"
        p.write_text(head + tail, newline="\n")
    return patch


def mesh_variant(name, v):
    root = D / name
    kw = setup_kw(v)
    s = case3d.Setup3D(surface_levels=v.get("surface_levels", (2, 3)), wake_level=2, cells_per_L=6, iterations=3000,
                       procs=24, **kw)
    script, t = case3d.write_case(root, cone_tris(v.get("body", "Cone")), s, exporter=tr.REPO / "wind_tunnel/export_field.py")
    patcher(v)(root)
    lines = script.read_text().splitlines()
    k = next(i for i, l in enumerate(lines) if "checkMesh" in l)
    mesh = lines[:k + 1] + ["reconstructParMesh -constant > log.reconstructParMesh 2>&1 || fail reconstructParMesh",
                            "rm -rf processor*", "echo meshed > status"]
    (root / "Allmesh").write_text("\n".join(mesh) + "\n", newline="\n")
    t0 = time.time()
    subprocess.run(["bash", str(root / "Allmesh")], stdin=subprocess.DEVNULL, check=False)
    log(f"{name}: {(root / 'status').read_text().strip()} in {time.time() - t0:.0f} s")
    return root, case3d.layer_sizing(t["L"], s)


def body_geometry(case):
    pm = case / "constant/polyMesh"
    pts = ef.read_points(pm)
    sizes, starts, toks = ef.read_faces(pm)
    owner = ef.read_labels(pm / "owner")
    neigh = ef.read_labels(pm / "neighbour")
    ncells = int(max(owner.max(), neigh.max())) + 1
    s0, n = ef.read_boundary(pm)["body"]
    faces = np.arange(s0, s0 + n)
    fc, fa = ef.face_geometry(pts, sizes, starts, toks, faces)
    A = np.linalg.norm(fa, axis=1)
    cc = ef.cell_centres(pts, sizes, starts, toks, owner, neigh, ncells)
    d = np.abs(((cc[owner[faces]] - fc) * (fa / A[:, None])).sum(axis=1))
    return {"fc": fc, "A": A, "d": d, "cells": ncells, "faces": int(n)}


def reference(case=S3 / "run_Cone", t="781"):
    g = body_geometry(case)
    g["yplus"] = ef.read_patch_values(case / t / "yPlus", "body", g["faces"])
    g["u_tau"] = g["yplus"] * NU / g["d"]
    return g


def wall_metrics(g, y_c, ref=None, yplus=None):
    A, d = g["A"], g["d"]
    w = A / A.sum()
    out = {"cells": g["cells"], "body_faces": g["faces"],
           "d_gt_2yc_area": float(w[d > 2 * y_c].sum()),
           "d_mm_p10_p50_p90": [round(1e3 * wquantile(d, A, q), 3) for q in (0.1, 0.5, 0.9)],
           "d_mm_area_mean": round(1e3 * float((w * d).sum()), 3)}
    if ref is not None:
        dist, idx = cKDTree(ref["fc"]).query(g["fc"])
        yp = d * ref["u_tau"][idx] / NU
        out.update({"pred_yplus_le_300": float(w[yp <= 300].sum()),
                    "pred_band_30_300": float(w[(yp > 30) & (yp < 300)].sum()),
                    "pred_yplus_p50_p90": [round(wquantile(yp, A, q), 1) for q in (0.5, 0.9)],
                    "map_distance_mm_p50_max": [round(1e3 * float(np.median(dist)), 2), round(1e3 * float(dist.max()), 2)]})
    if yplus is not None:
        out.update({"meas_yplus_le_300": float(w[yplus <= 300].sum()),
                    "meas_band_30_300": float(w[(yplus > 30) & (yplus < 300)].sum()),
                    "meas_yplus_p50_p90": [round(wquantile(yplus, A, q), 1) for q in (0.5, 0.9)]})
    return out


def mesh_report(root):
    lt = pr.layer_table((root / "log.snappyHexMesh").read_text()).get("body", {})
    cm = pr.checkmesh((root / "log.checkMesh").read_text())
    keep = ("faces", "target", "mesh_mean", "overall_thickness_m", "thickness_pct_of_target",
            "faces_extruded_final", "coverage_faces_extruded", "layers_on_extruded_faces")
    return {"layers": {k: lt.get(k) for k in keep}, "checkMesh": {k: cm[k] for k in cm if k != "warnings"},
            "checkMesh_warnings": cm["warnings"][:6]}


def qualifies(r, base):
    c, b = r["checkMesh"], base["checkMesh"]
    return (r["layers"]["coverage_faces_extruded"] >= 0.90 and c["failed_checks"] <= b["failed_checks"]
            and c["max_skewness"] <= 1.05 * b["max_skewness"] and c["max_non_ortho"] <= b["max_non_ortho"] + 1.0)


def oscillation(case, Af, speed=20.0, rho=1.225, windows=((1001, 2000), (2001, 3000), (2801, 3000))):
    """Cd statistics per window from the forces FO history: mean, min, max, and the number of crossings of the
    window mean (sign changes of Cd - mean) per 1000 iterations; the gate verdict at the last iteration."""
    h = convergence.history(case)
    t = np.array(h["time"], dtype=float)
    cd = np.array(h["fx"]) / (0.5 * rho * speed ** 2 * Af)
    out = {"iterations": [int(t[0]), int(t[-1])], "p_initial_last": float(h["p_initial"][-1]), "windows": {}}
    for a, b in windows:
        m = (t >= a) & (t <= b)
        if m.sum() < 0.9 * (b - a + 1):
            continue
        c = cd[m]
        s = np.sign(c - c.mean())
        s = s[s != 0]
        out["windows"][f"{a}-{b}"] = {"Cd_mean": round(float(c.mean()), 4), "Cd_min": round(float(c.min()), 4),
                                      "Cd_max": round(float(c.max()), 4),
                                      "mean_crossings_per_1000": round(float((s[1:] != s[:-1]).sum()) * 1000 / m.sum(), 1)}
    v = convergence.gate(h["time"], h["fx"], h["fy"], h["fz"], h["p_initial"], cap=3000)
    out["gate"] = {"converged": v["converged"], "iteration": v["iteration"], "reasons": v["reasons"]}
    return out


def sphere_attribution():
    src, rs, c = W / "3d_Sphere", S3 / "run_Sphere", D / "sphere_attrib"
    if c.exists():
        shutil.rmtree(c)
    c.mkdir(parents=True)
    for item in ["0.orig", "constant", "system"] + sorted(p.name for p in src.glob("processor*")):
        shutil.copytree(src / item, c / item)
    for p in c.glob("processor*"):
        for tdir in ("0", "300"):
            shutil.rmtree(p / tdir, ignore_errors=True)
    for f in ("controlDict", "fvSolution"):
        shutil.copy(rs / "system" / f, c / "system" / f)
    shutil.copy(rs / "convergence.py", c / "convergence.py")
    t0 = time.time()
    subprocess.run(["bash", "-c", BASH + f"cd '{c}' && rm -f wt_stop && "
                    "mpirun -np 24 --oversubscribe simpleFoam -parallel > log.simpleFoam 2>&1"],
                   stdin=subprocess.DEVNULL, check=False)
    wall = time.time() - t0
    Af = json.loads((rs / "forces.json").read_text())["frontal_area_m2"]
    out = {"case": str(c), "mesh": "3d_Sphere (v1912-era snappy, 2 relative layers), 339,042 cells",
           "start": "3d_Sphere v1912 fields at 400", "wall_seconds": round(wall), "frontal_area_m2": Af,
           "old_mesh_continued": oscillation(c, Af), "run_Sphere_step3_mesh": oscillation(rs, Af)}
    log(f"sphere attribution done in {wall:.0f} s")
    return out


EXTRA2 = {
    "V7_curv48": {"curvature_nc": 48},
    "Cube_level33": {"body": "Cube", "surface_levels": (3, 3)},
}


def extra(variants=EXTRA):
    """Mesh-only extra variants into the existing bundle.json (same metrics as V0 to V4; a cube variant is
    predicted from run_Cube's u_tau at its gated time)."""
    L, sz = base_sizing()
    bundle = json.loads((D / "bundle.json").read_text())
    refs = {"Cone": reference(), "Cube": reference(S3 / "run_Cube", ef.latest_time(S3 / "run_Cube"))}
    for name, v in variants.items():
        ref = refs[v.get("body", "Cone")]
        root, vsz = mesh_variant(name, v)
        r = {"setting": {k: list(x) if isinstance(x, tuple) else x for k, x in v.items()},
             "sizing": {k: (round(x, 6) if isinstance(x, float) else x) for k, x in vsz.items()}}
        r.update(mesh_report(root))
        r.update(wall_metrics(body_geometry(root), sz["y_c"], ref=ref))
        bundle["variants"][name] = r
        log(f"{name}: " + json.dumps({k: r.get(k) for k in ("cells", "d_gt_2yc_area", "pred_yplus_le_300")}
                                       | {"coverage": r["layers"]["coverage_faces_extruded"]}))
    (D / "bundle.json").write_text(json.dumps(bundle, indent=1))


def main():
    D.mkdir(parents=True, exist_ok=True)
    L, sz = base_sizing()
    y_c = sz["y_c"]
    bundle = {"date": time.strftime("%Y-%m-%d"), "openfoam": "v2512", "body": "Cone, 3d_Cone body.stl, COARSE",
              "locked_sizing": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in sz.items()},
              "threshold_d_m": 2 * y_c, "criterion": CRITERION, "variants": {}}
    log("reference run_Cone at 781 and the predictor check on run_Cone_remesh at 716")
    ref = reference()
    bundle["check_run_Cone_781"] = wall_metrics(ref, y_c, ref=ref, yplus=ref["yplus"])
    rm = body_geometry(S3 / "run_Cone_remesh")
    rm_yp = ef.read_patch_values(S3 / "run_Cone_remesh/716/yPlus", "body", rm["faces"])
    bundle["check_predictor_run_Cone_remesh_716"] = wall_metrics(rm, y_c, ref=ref, yplus=rm_yp)
    log(json.dumps(bundle["check_predictor_run_Cone_remesh_716"]))
    for name, v in VARIANTS.items():
        root, vsz = mesh_variant(name, v)
        r = {"setting": v or "locked", "sizing": {k: (round(x, 6) if isinstance(x, float) else x) for k, x in vsz.items()}}
        try:
            r.update(mesh_report(root))
            r.update(wall_metrics(body_geometry(root), y_c, ref=ref))
        except Exception as e:                       # a failed mesh is a result, not a crash
            r["error"] = f"{type(e).__name__}: {e}"
        bundle["variants"][name] = r
        log(f"{name}: " + json.dumps({k: r.get(k) for k in ("cells", "d_gt_2yc_area", "pred_yplus_le_300")}
                                       | {"coverage": r.get("layers", {}).get("coverage_faces_extruded")}))
        (D / "bundle.json").write_text(json.dumps(bundle, indent=1))
    base = bundle["variants"]["V0_locked"]
    cand = [(n, r) for n, r in bundle["variants"].items() if n != "V0_locked" and "error" not in r and qualifies(r, base)]
    cand.sort(key=lambda nr: (-nr[1]["pred_yplus_le_300"], nr[1]["d_gt_2yc_area"]))
    best = cand[0][0] if cand and cand[0][1]["pred_yplus_le_300"] > base["pred_yplus_le_300"] else None
    bundle["qualifying"] = [n for n, _ in cand]
    bundle["best"] = best
    if best:
        log(f"solving {best}")
        v = VARIANTS[best]
        root = D / f"solve_{best}"
        f, summ = tr.run("Cone", root, patch=patcher(v), **setup_kw(v))
        g = body_geometry(root)
        t = ef.latest_time(root)
        yp = ef.read_patch_values(root / str(t) / "yPlus", "body", g["faces"])
        summ["wall_check"] = wall_metrics(g, y_c, ref=ref, yplus=yp)
        summ["Cd_vs_step2_0p5833_pct"] = (100 * (summ["Cd_mean"] / 0.5833 - 1)) if summ.get("Cd_mean") else None
        bundle["solve"] = summ
        (D / "bundle.json").write_text(json.dumps(bundle, indent=1))
    log("sphere attribution")
    bundle["sphere_attribution"] = sphere_attribution()
    (D / "bundle.json").write_text(json.dumps(bundle, indent=1))
    log("bundle written")


def solve(name):
    """One cone solve of a variant through the real Allrun (no re-mesh), into bundle.json["solve"]."""
    L, sz = base_sizing()
    bundle = json.loads((D / "bundle.json").read_text())
    v = {**VARIANTS, **EXTRA}[name]
    root = D / f"solve_{name}"
    log(f"solving {name}")
    f, summ = tr.run("Cone", root, patch=patcher(v), levels=v.get("surface_levels", (2, 3)), **setup_kw(v))
    g = body_geometry(root)
    t = ef.latest_time(root)
    yp = ef.read_patch_values(root / str(t) / "yPlus", "body", g["faces"])
    summ["wall_check"] = wall_metrics(g, sz["y_c"], ref=reference(), yplus=yp)
    summ["Cd_vs_step2_0p5833_pct"] = (100 * (summ["Cd_mean"] / 0.5833 - 1)) if summ.get("Cd_mean") else None
    bundle["solve"] = summ
    (D / "bundle.json").write_text(json.dumps(bundle, indent=1))
    log("solve recorded")


if __name__ == "__main__":
    a = sys.argv[1:]
    extra() if a == ["extra"] else extra(EXTRA2) if a == ["extra2"] else solve(a[1]) if a[:1] == ["solve"] else main()
