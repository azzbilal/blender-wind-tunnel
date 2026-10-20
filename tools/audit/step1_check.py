"""FIX_PLAN step 1: Cp referenced to the inlet mean static pressure, checked against OpenFOAM.

Runs INSIDE WSL on a COPY of a solved case (it rewrites forces.json and field.npz, and writes
system/step1Cp, postProcessing/ and the static(p)_coeff field):

    python3 step1_check.py ~/wind_tunnel/_step1/Cube --exporter /path/to/export_field.py

Definitions and gates: docs/reference/step1_cp_reference.md. Prints one JSON object.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from step0_check import BASHRC, last_row

DICT = """FoamFile {{ version 2.0; format ascii; class dictionary; object step1Cp; }}
functions
{{
    cpCheck {{ type pressure; libs (fieldFunctionObjects); mode staticCoeff;
              pInf {pInf}; UInf ({U} 0 0); rhoInf {rho}; writeFields yes; }}
    inletP  {{ type surfaceFieldValue; libs (fieldFunctionObjects); regionType patch; name inlet;
              operation areaAverage; fields (p); writeFields false; }}
{planes}}}
"""
PLANE = """    {name} {{ type surfaceFieldValue; libs (fieldFunctionObjects); regionType sampledSurface; name {name};
              sampledSurfaceDict {{ type plane; point ({x} 0 0); normal (1 0 0); interpolate false; }}
              operation areaAverage; fields (p); writeFields false; }}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--exporter", required=True, help="export_field.py of the add-on under test")
    ap.add_argument("--speed", type=float, default=20.0)
    ap.add_argument("--rho", type=float, default=1.225)
    ap.add_argument("--nu", type=float, default=1.5e-5)
    ap.add_argument("--voxel", type=float, default=0.05)
    ap.add_argument("--L", type=float, default=2.0)
    ap.add_argument("--bashrc", default=BASHRC)
    a = ap.parse_args()
    case = Path(a.case).expanduser().resolve()
    U, rho, L = a.speed, a.rho, a.L
    qk = 0.5 * U ** 2                                    # kinematic dynamic pressure

    spec = importlib.util.spec_from_file_location("export_field", a.exporter)
    ef = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ef)

    # ---- patched exporter; the forces.json written before it is kept as forces_v041.json
    old_path = case / "forces_v041.json"
    if not old_path.exists():
        shutil.copy(case / "forces.json", old_path)
    old = json.loads(old_path.read_text())
    shutil.copy(a.exporter, case / "export_field.py")
    with open(case / "log.export_step1", "w") as log:
        subprocess.run(["python3", "export_field.py", ".", "--speed", str(U), "--rho", str(rho), "--nu", str(a.nu),
                        "--voxel", str(a.voxel), "--L", str(L)], cwd=case, stdout=log, stderr=subprocess.STDOUT, check=True)
    new = json.loads((case / "forces.json").read_text())
    p_inf = new["p_inf_Pa"] / rho

    # ---- mesh, fields, patches
    pm = case / "constant" / "polyMesh"
    t = ef.latest_time(case)
    pts = ef.read_points(pm)
    sizes, starts, toks = ef.read_faces(pm)
    owner, neigh = ef.read_labels(pm / "owner"), ef.read_labels(pm / "neighbour")
    ncells = int(max(owner.max(), neigh.max())) + 1
    p = ef.read_internal(case / t / "p", 1, ncells)
    bnd = ef.read_boundary(pm)

    def patch(name):
        s, n = bnd[name]
        f = np.arange(s, s + n)
        c, Sf = ef.face_geometry(pts, sizes, starts, toks, f)
        return owner[f], c, Sf, n

    own_in, c_in, Sf_in, _ = patch("inlet")
    own_b, c_b, Sf_b, nb = patch("body")
    x_in = float(pts[:, 0].min())

    # ---- OpenFOAM: pressure (staticCoeff) with the same pInf/UInf/rhoInf, inlet and plane averages
    planes = "".join(PLANE.format(name=f"plane{k}L", x=x_in + k * L) for k in (1, 2))
    (case / "system" / "step1Cp").write_text(DICT.format(pInf=repr(rho * p_inf), U=U, rho=rho, planes=planes))
    cmd = (f". {a.bashrc} > /dev/null 2>&1 && cd '{case}' && echo $WM_PROJECT_VERSION && "
           "simpleFoam -postProcess -latestTime -dict system/step1Cp > log.step1Cp 2>&1")
    out = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(f"simpleFoam -postProcess failed, see {case}/log.step1Cp")

    def fv(name):
        head, row = last_row(next((case / "postProcessing" / name).glob("*/surfaceFieldValue.dat")))
        return row[head.index("areaAverage(p)")]

    of_cp_body = ef.read_patch_values(case / t / "static(p)_coeff", "body", nb)
    ours_cp_body = ef.cp_from_p(p[own_b], p_inf, U)
    of_inlet = fv("inletP")

    # ---- inlet uniformity, stagnation
    A_in = np.linalg.norm(Sf_in, axis=1)
    cp_in = ef.cp_from_p(p[own_in], p_inf, U)
    centre_in = c_in.mean(axis=0)
    i_c = int(np.argmin(np.linalg.norm(c_in - centre_in, axis=1)))
    tris_raw = (case / "constant" / "triSurface" / "body.stl").read_bytes()
    nt = int.from_bytes(tris_raw[80:84], "little")
    v = np.frombuffer(tris_raw[84:84 + 50 * nt], dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]))["v"]
    lo, hi = v.reshape(-1, 3).min(axis=0).astype(float), v.reshape(-1, 3).max(axis=0).astype(float)
    nose = np.array([lo[0], (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2])
    i_s = int(np.argmin(np.linalg.norm(c_b - nose, axis=1)))
    A_b = np.linalg.norm(Sf_b, axis=1)
    front = (Sf_b[:, 0] / A_b > 0.99) & (c_b[:, 0] < lo[0] + 1e-3 * L)

    old_keys_equal = all(old[k] == new[k] for k in old)
    dcp = float(np.abs(ours_cp_body - of_cp_body).max())
    res = {
        "case": case.name, "openfoam": out.stdout.strip(), "time": t, "cells": ncells,
        "p_inf_kinematic": p_inf, "p_inf_Pa": new["p_inf_Pa"], "p_inf_Cp_vs_outlet": new["p_inf_Cp_vs_outlet"],
        "surfaceFieldValue_inlet_areaAverage_p": of_inlet,
        "p_inf_minus_surfaceFieldValue_over_q": (p_inf - of_inlet) / qk,
        "inlet_mean_Cp_after_shift": float((cp_in * A_in).sum() / A_in.sum()),
        "inlet_Cp_max_minus_min": float(cp_in.max() - cp_in.min()),
        "inlet_Cp_centre_face": float(cp_in[i_c]),
        "plane_1L_downstream_of_inlet_Cp": ef.cp_from_p(fv("plane1L"), p_inf, U),
        "plane_2L_downstream_of_inlet_Cp": ef.cp_from_p(fv("plane2L"), p_inf, U),
        "body_Cp_vs_pressure_FO_max_abs_diff": dcp,
        "stagnation_face": {"centre": c_b[i_s].tolist(), "target": nose.tolist(), "Cp": float(ours_cp_body[i_s]),
                            "Cp_pressure_FO": float(of_cp_body[i_s]), "Cp_vs_outlet_before": float(p[own_b][i_s] / qk)},
        "front_face_area_mean_Cp": float((ours_cp_body[front] * A_b[front]).sum() / A_b[front].sum()) if front.any() else None,
        "front_face_count": int(front.sum()),
        "body_face_Cp_max": float(ours_cp_body.max()),
        "forces_json_v041_values_identical": old_keys_equal,
        "forces_json_new_keys": sorted(set(new) - set(old)),
        "gate_surfaceFieldValue_0p001": bool(abs(p_inf - of_inlet) / qk <= 0.001),
        "gate_pressure_FO_0p001": bool(dcp <= 0.001),
        "gate_inlet_mean_0p002": bool(abs(float((cp_in * A_in).sum() / A_in.sum())) <= 0.002),
        "logs": ["log.export_step1", "log.step1Cp", "postProcessing/inletP", "postProcessing/plane1L",
                 "postProcessing/plane2L", f"{t}/static(p)_coeff"],
    }
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
