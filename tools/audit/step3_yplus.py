#!/usr/bin/env python3
"""FIX_PLAN step 3, Stage 1: y+ and u_tau on the body faces of a solved case, and the y+ band fraction
as a function of the first cell-centre distance, assuming u_tau unchanged.

Runs inside WSL (numpy) on a case where OpenFOAM's yPlus and wallShearStress function objects have
been run post-hoc, for example
    simpleFoam -postProcess -funcs '(yPlus wallShearStress)' -time 400
Usage: python3 step3_yplus.py CASE TIME [--nu 1.5e-5] [--speed 20] [--L 2] [--json out.json]

Per body face:
  A       face area (export_field.face_geometry)
  d       normal distance from the owner cell centre (mean of its face centres, export_field) to
          the face plane: our estimate of OpenFOAM's nearWallDist y
  yplus   OpenFOAM yPlus FO; for nutUSpaldingWallFunction it is y calcUTau(|snGrad U|) / nu with
          y = nearWallDist (yPlus.C:136-157, nutUSpaldingWallFunctionFvPatchScalarField.C:322-343)
  u_tau   yplus nu / d (the Spalding u_tau the FO used); cross-check sqrt(|wallShearStress|)
Moving every first cell centre to a common distance y with u_tau unchanged gives y+ = y u_tau / nu.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "wind_tunnel"))
import export_field as ef  # noqa: E402

BAND = (30.0, 300.0)


def wquantile(v, w, q):
    """Area-weighted quantile: the smallest v with cumulative weight fraction >= q."""
    o = np.argsort(v)
    c = np.cumsum(w[o]) / w.sum()
    return float(v[o][min(np.searchsorted(c, q), len(v) - 1)])


def fractions(yplus, A):
    """Area fractions in the band, at or under 300, under 30, under 5."""
    lo, hi = BAND
    return {"band_30_300": float(A[(yplus > lo) & (yplus < hi)].sum() / A.sum()),
            "le_300": float(A[yplus <= hi].sum() / A.sum()),
            "lt_30": float(A[yplus < lo].sum() / A.sum()),
            "lt_5": float(A[yplus < 5].sum() / A.sum())}


def analyse(case: Path, t: str, nu: float, speed: float, L: float):
    pm = case / "constant" / "polyMesh"
    pts = ef.read_points(pm)
    sizes, starts, toks = ef.read_faces(pm)
    owner = ef.read_labels(pm / "owner")
    neigh = ef.read_labels(pm / "neighbour")
    ncells = int(max(owner.max(), neigh.max())) + 1
    s0, n = ef.read_boundary(pm)["body"]
    faces = np.arange(s0, s0 + n)
    fc, fa = ef.face_geometry(pts, sizes, starts, toks, faces)
    A = np.linalg.norm(fa, axis=1)
    nhat = fa / A[:, None]
    cc = ef.cell_centres(pts, sizes, starts, toks, owner, neigh, ncells)
    d = np.abs(((cc[owner[faces]] - fc) * nhat).sum(axis=1))
    yp = ef.read_patch_values(case / t / "yPlus", "body", n)
    tau = ef.read_patch_values(case / t / "wallShearStress", "body", n).reshape(n, 3)
    u_tau = yp * nu / d
    u_tau_wss = np.sqrt(np.linalg.norm(tau, axis=1))
    ok = u_tau_wss > 1e-9
    ratio = u_tau[ok] / u_tau_wss[ok]

    def wstats(v):
        return {"min": float(v.min()), "mean": float((v * A).sum() / A.sum()), "max": float(v.max()),
                "p10": wquantile(v, A, 0.10), "p50": wquantile(v, A, 0.50), "p90": wquantile(v, A, 0.90)}

    ys = np.logspace(-5, -2, 61)                        # common first cell-centre distance, m
    curve = []
    for y in ys:
        f = fractions(y * u_tau / nu, A)
        curve.append({"y_m": float(y), **f, "yplus_mean": float((y * u_tau / nu * A).sum() / A.sum())})
    fine = np.logspace(-5, -2, 3001)
    band = np.array([fractions(y * u_tau / nu, A)["band_30_300"] for y in fine])
    i = int(band.argmax())
    ut_p90, ut_p50 = wquantile(u_tau, A, 0.90), wquantile(u_tau, A, 0.50)
    ut_mean = float((u_tau * A).sum() / A.sum())
    Re = speed * L / nu
    return {
        "case": str(case), "time": t, "body_faces": int(n), "area_m2": float(A.sum()),
        "now": {"yplus": wstats(yp), **fractions(yp, A), "d_m": wstats(d)},
        "u_tau_m_s": wstats(u_tau),
        "u_tau_check_wallShearStress": {"ratio_p10": float(np.quantile(ratio, 0.1)),
                                        "ratio_median": float(np.median(ratio)),
                                        "ratio_p90": float(np.quantile(ratio, 0.9)),
                                        "faces_with_tau": int(ok.sum())},
        "best_band": {"y_m": float(fine[i]), "band_30_300": float(band[i]),
                      "layer_height_m": float(2 * fine[i])},
        "y_for_le300_on_90pct_m": 300 * nu / ut_p90,
        "y_for_yplus100_at_median_u_tau_m": 100 * nu / ut_p50,
        "y_for_mean_yplus100_m": 100 * nu / ut_mean,
        "at_target": {str(tgt): {"y_m": tgt * nu / ut_p50, **fractions(tgt * u_tau / ut_p50, A)}
                      for tgt in (50, 100, 150)},
        "flat_plate_u_tau_m_s": {str(c): float(speed * np.sqrt(c / Re ** (1 / 7) / 2)) for c in (0.026, 0.027)},
        "u_tau_over_U": {k: v / speed for k, v in wstats(u_tau).items()},
        "table": [{"y_mm": y, **fractions(y * 1e-3 * u_tau / nu, A),
                   "yplus_mean": float((y * 1e-3 * u_tau / nu * A).sum() / A.sum()),
                   "yplus_max": float(y * 1e-3 * u_tau.max() / nu)}
                  for y in (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)],
        "curve": curve,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case", type=Path)
    ap.add_argument("time")
    ap.add_argument("--nu", type=float, default=1.5e-5)
    ap.add_argument("--speed", type=float, default=20.0)
    ap.add_argument("--L", type=float, default=2.0)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    r = analyse(a.case, a.time, a.nu, a.speed, a.L)
    if a.json:
        a.json.write_text(json.dumps(r, indent=1))
    print(json.dumps({k: v for k, v in r.items() if k != "curve"}, indent=1))


if __name__ == "__main__":
    main()
