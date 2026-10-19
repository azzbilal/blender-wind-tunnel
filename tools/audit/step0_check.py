"""FIX_PLAN step 0: OpenFOAM's forces / forceCoeffs / yPlus against export_field.py on a solved case.

Runs INSIDE WSL on a COPY of a solved case (it writes system/step0Check and postProcessing/):

    python3 step0_check.py ~/wind_tunnel/_step0/Cube --exporter /path/to/export_field.py

Definitions and gates: docs/reference/step0_openfoam_build.md. Prints one JSON object.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

import numpy as np

BASHRC = "/usr/lib/openfoam/openfoam2512/etc/bashrc"

DICT = """FoamFile {{ version 2.0; format ascii; class dictionary; object step0Check; }}
functions
{{
    forces1      {{ type forces; libs (forces); patches (body); rho rhoInf; rhoInf {rho}; CofR (0 0 0); }}
    forceCoeffs1 {{ type forceCoeffs; libs (forces); patches (body); rho rhoInf; rhoInf {rho}; CofR (0 0 0);
                   dragDir (1 0 0); liftDir (0 0 1); magUInf {speed}; lRef {L}; Aref {Aref}; }}
    yPlus1       {{ type yPlus; libs (fieldFunctionObjects); }}
}}
"""


def last_row(path: Path):
    """Header names (from the last '#' line) and the last data row of an OpenFOAM .dat file."""
    head, row = [], None
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            head = line[1:].split()
        elif line.strip():
            row = line.replace("(", " ").replace(")", " ").split()
    return head, [float(v) for v in row]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--exporter", required=True, help="export_field.py of the add-on under test")
    ap.add_argument("--bashrc", default=BASHRC)
    a = ap.parse_args()
    case = Path(a.case).expanduser().resolve()
    ref = json.loads((case / "forces.json").read_text())
    rho, speed, Aref = ref["rho"], ref["speed"], ref["frontal_area_m2"]
    nu = 1.5e-5

    spec = importlib.util.spec_from_file_location("export_field", a.exporter)
    ef = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ef)

    (case / "system" / "step0Check").write_text(DICT.format(rho=rho, speed=speed, L=2.0, Aref=Aref))
    cmd = (f". {a.bashrc} > /dev/null 2>&1 && cd '{case}' && echo $WM_PROJECT_VERSION && "
           "simpleFoam -postProcess -latestTime -dict system/step0Check > log.step0Check 2>&1")
    out = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"simpleFoam -postProcess failed, see {case}/log.step0Check")
    version = out.stdout.strip()

    t = ef.latest_time(case)
    head, row = last_row(next((case / "postProcessing" / "forces1").glob("*/force.dat")))
    col = {h: i for i, h in enumerate(head)}
    of = {k: np.array([row[col[f"{k}_{c}"]] for c in "xyz"]) for k in ("total", "pressure", "viscous")}
    chead, crow = last_row(next((case / "postProcessing" / "forceCoeffs1").glob("*/coefficient.dat")))
    of_cd = crow[chead.index("Cd")]

    pm = case / "constant" / "polyMesh"
    pts = ef.read_points(pm)
    sizes, starts, toks = ef.read_faces(pm)
    owner, neigh = ef.read_labels(pm / "owner"), ef.read_labels(pm / "neighbour")
    ncells = int(max(owner.max(), neigh.max())) + 1
    cc = ef.cell_centres(pts, sizes, starts, toks, owner, neigh, ncells)
    U = ef.read_internal(case / t / "U", 3, ncells)
    p = ef.read_internal(case / t / "p", 1, ncells)
    Fp, Fv = ef.body_forces(case, t, pts, sizes, starts, toks, owner, cc, U, p, rho, nu)
    ours = {"total": Fp + Fv, "pressure": Fp, "viscous": Fv}

    start, nb = ef.read_boundary(pm)["body"]
    _, farea = ef.face_geometry(pts, sizes, starts, toks, np.arange(start, start + nb))
    A = np.linalg.norm(farea, axis=1)
    yp = ef.read_patch_values(case / t / "yPlus", "body", nb)
    band = (yp >= 30) & (yp <= 300)

    fx = of["total"][0]
    diff = {k: ((ours[k] - of[k]) / abs(fx) * 100).tolist() for k in of}   # % of total OpenFOAM Fx
    res = {
        "case": case.name, "openfoam": version, "time": t, "cells": ncells,
        "openfoam_N": {k: v.tolist() for k, v in of.items()},
        "export_field_N": {k: v.tolist() for k, v in ours.items()},
        "diff_pct_of_Fx": diff,
        "viscous_x_diff_pct_of_viscous_x": float((ours["viscous"][0] - of["viscous"][0]) / of["viscous"][0] * 100),
        "Cd": {"forceCoeffs": of_cd, "export_field": float((Fp + Fv)[0] / (0.5 * rho * speed ** 2 * Aref))},
        "yplus": {"min": float(yp.min()), "area_mean": float((yp * A).sum() / A.sum()), "max": float(yp.max()),
                  "area_frac_30_300": float(A[band].sum() / A.sum())},
        "gate_total_0p5": bool(max(abs(v) for v in diff["total"]) <= 0.5),
        "gate_pressure_x_0p1": bool(abs(diff["pressure"][0]) <= 0.1),
    }
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
