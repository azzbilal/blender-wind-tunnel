#!/usr/bin/env python3
"""FIX_PLAN step 3 Stage 4 tracer (docs/reference/step3_wall_spec.md Q5): re-run bodies through the real
Allrun with the step 3 case writer, one at a time, on copies.

  python3 step3_tracer.py [--suffix _d1] Sphere Cube Cone          (inside WSL)

For each body: case3d.write_case from ~/wind_tunnel/3d_<body>/constant/triSurface/body.stl into
~/wind_tunnel/_step3/run_<body><suffix> (COARSE preset, case3d.PRESETS: body level (3 3) since amendment D1,
wake 2, L/6; 24 ranks; cap 3000), bash Allrun. No re-mesh (amendment D2). Prints one JSON summary per run and
writes them all to _step3/tracer<suffix>.json.
"""
import json
import subprocess
import sys
import time
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
pkg = types.ModuleType("wind_tunnel")
pkg.__path__ = [str(REPO / "wind_tunnel")]
sys.modules["wind_tunnel"] = pkg
import importlib  # noqa: E402

case3d = importlib.import_module("wind_tunnel.case3d")

W = Path.home() / "wind_tunnel"


def run(body, root, u_tau=None, layers=None, patch=None, levels=case3d.PRESETS["COARSE"][0]):
    """patch: optional callable(root) applied after write_case and before Allrun (step3_diag.py variants)."""
    tris = case3d.read_stl(W / f"3d_{body}" / "constant/triSurface/body.stl")
    s = case3d.Setup3D(surface_levels=levels, wake_level=2, cells_per_L=6, iterations=3000, procs=24, u_tau=u_tau,
                       layers=layers)
    script, t = case3d.write_case(root, tris, s, exporter=REPO / "wind_tunnel/export_field.py")
    if patch:
        patch(root)
    t0 = time.time()
    subprocess.run(["bash", str(script)], check=False)
    wall_s = time.time() - t0
    status = (root / "status").read_text().strip() if (root / "status").exists() else "?"
    f = json.loads((root / "forces.json").read_text()) if (root / "forces.json").exists() else {}
    summary = {"body": body, "root": str(root), "status": status, "wall_seconds": round(wall_s),
               "sizing": case3d.layer_sizing(t["L"], s), "cells": f.get("cells"),
               "converged": f.get("converged"), "iterations": f.get("iterations"), "reasons": f.get("reasons"),
               "Cd_mean": f.get("Cd_mean"), "Cd_band": f.get("Cd_band"), "wall": f.get("wall")}
    print("TRACER " + json.dumps(summary), flush=True)
    return f, summary


def main(bodies, suffix=""):
    out = []
    for body in bodies:
        out.append(run(body, W / "_step3" / f"run_{body}{suffix}")[1])
        (W / "_step3" / f"tracer{suffix}.json").write_text(json.dumps(out, indent=1))   # after every body


if __name__ == "__main__":
    args = sys.argv[1:]
    suffix = ""
    if args[:1] == ["--suffix"]:
        suffix, args = args[1], args[2:]
    main(args or ["Sphere", "Cube", "Cone"], suffix)
