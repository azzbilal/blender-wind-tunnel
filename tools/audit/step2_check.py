#!/usr/bin/env python3
"""FIX_PLAN step 2 Stage 5: offline check of a gated run continued to 2000 (tools/audit/step2_tracer.sh).

Runs inside WSL on ~/wind_tunnel/_step2/<case>, standard library only, with the case's own
convergence.py. Prints one JSON record:
  trigger      iteration at which the systemCall gate wrote wt_stop (from log.gated)
  written      time the run wrote (forces_gated.json), lag = written - trigger
  offline      first gate pass on the merged history, at the systemCall iterations (every 5) and at
               any iteration; must equal the trigger
  open_at      gate verdict at given iterations (acceptance (a): open at 400 and 800 on the cube)
  reported     forces_gated.json window means (min to max)
  late_mean    Cd mean over 1801-2000 and its difference from the reported mean (acceptance (b))
  force_first  Q5 alternative scored on the same history: first n >= 400 with the band alone
Usage: python3 step2_check.py CASE [--ref CD] [--open-at 400 800]
"""
import argparse
import json
import re
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--ref", type=float, default=None, help="reference Cd for the reported mean")
    ap.add_argument("--open-at", type=int, nargs="*", default=[400, 800])
    a = ap.parse_args()
    case = Path(a.case).expanduser()
    sys.path.insert(0, str(case))
    import convergence as cv

    fg = json.loads((case / "forces_gated.json").read_text())
    qa = 0.5 * fg["rho"] * fg["speed"] ** 2 * fg["frontal_area_m2"]
    h = cv.history(case)
    T, fx, fy, fz, r = h["time"], h["fx"], h["fy"], h["fz"], h["p_initial"]
    at = lambda n: cv.gate(T[:T.index(n) + 1], fx[:T.index(n) + 1], fy[:T.index(n) + 1],
                           fz[:T.index(n) + 1], r[:T.index(n) + 1])
    trig = [int(m) for m in re.findall(r"wt gate (\d+): converged", (case / "log.gated").read_text())]
    first5 = next((n for n in T if n % 5 == 0 and at(n)["converged"]), None)
    first1 = next((n for n in T if at(n)["converged"]), None)

    # Q5 alternative: Cd band alone (n >= 400, full window), no residual test
    def band_only(n):
        v = at(n)
        return n >= cv.MIN_ITER and v["band"] < cv.BAND and len([t for t in T if n - cv.WINDOW < t <= n]) == cv.WINDOW
    ff = next((n for n in T if n % 5 == 0 and band_only(n)), None)

    late = [x / qa for t, x in zip(T, fx) if 1801 <= t <= 2000]
    late_mean = sum(late) / len(late) if late else None
    rec = {
        "case": case.name, "cells": fg["cells"], "frontal_area_m2": fg["frontal_area_m2"],
        "history": [T[0], T[-1]] if T else None,
        "trigger": trig[0] if trig else None, "written": int(float(fg["time"])),
        "lag": int(float(fg["time"])) - trig[0] if trig else None,
        "offline_first_pass_every5": first5, "offline_first_pass_any": first1,
        "offline_agrees": bool(trig) and first5 == trig[0],
        "converged": fg.get("converged"), "reasons": fg.get("reasons"),
        "Cd_band_pct": 100 * fg["Cd_band"] if fg.get("Cd_band") is not None else None,
        "p_initial": fg.get("p_initial"), "p_trend_orders_per_100": fg.get("p_trend"),
        "reported": {f"{k}_{s}": fg.get(f"{k}_{s}") for k in ("Cd", "Cl", "Cs") for s in ("mean", "min", "max")},
        "reported_N": {k: fg.get(f"{k}_mean") for k in ("drag_N", "lift_N", "side_N")},
        "snapshot_Cd_at_written": fg["Cd"],
        "fo_Cd_at_written": fx[T.index(int(float(fg["time"])))] / qa if int(float(fg["time"])) in T else None,
        "open_at": {n: {"converged": at(n)["converged"], "reasons": at(n)["reasons"]}
                    for n in a.open_at if n in T},
        "late_mean_Cd_1801_2000": late_mean,
        "late_vs_reported_pct": (100 * (late_mean - fg["Cd_mean"]) / fg["Cd_mean"]
                                 if late_mean and fg.get("Cd_mean") else None),
        "force_first_stop": ff,
        "force_first_Cd_mean": at(ff)["fx"]["mean"] / qa if ff else None,
        "force_first_vs_late_pct": (100 * (at(ff)["fx"]["mean"] / qa - late_mean) / late_mean
                                    if ff and late_mean else None),
        "gate_at_2000": at(2000) if 2000 in T else None,
        "trace_every_100": [[t, round(x / qa, 4), y] for t, x, y in zip(T, fx, r) if t % 100 == 0],
        "window_Cd_mean_every_100": [[n, round(at(n)["fx"]["mean"] / qa, 4), round(100 * at(n)["band"], 2)]
                                     for n in T if n % 100 == 0 and n >= 400],
    }
    if a.ref and fg.get("Cd_mean"):
        rec["ref_Cd"] = a.ref
        rec["reported_vs_ref_pct"] = 100 * (fg["Cd_mean"] - a.ref) / a.ref
    g = rec["gate_at_2000"]
    if g:
        g["fx"] = {k: v / qa for k, v in g["fx"].items()}       # as Cd
        rec["gate_at_2000"] = {k: g[k] for k in ("converged", "reasons", "band", "residual", "residual_trend", "fx")}
    print(json.dumps(rec, indent=2, default=list))


if __name__ == "__main__":
    main()
