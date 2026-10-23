#!/usr/bin/env python3
"""TRANSIENT T1 Q4 honesty gates 1 to 3 on the solved case (runs inside WSL, next to transient.py).

    python3 t1_gates.py CASE [OUT.json]

Gate 1 (report): Cd time average over t = 1.0 to 2.0 s, and 0.5 to 1.0 s as a settling indicator, from
  postProcessing/forceCoeffs/0/coefficient.dat (columns read by header name), next to the steady gated
  Cd 1.1498 on the same mesh. No target.
Gate 2 (report): Strouhal number from Cs and Cl over 1.0 to 2.0 s (transient.strouhal), next to
  Klotz et al. 2014 (St 0.125, Re <= 390, a different regime); fewer than 2 periods: "not measurable".
Gate 3 (FAIL): time step continuity error (sum local, last corrector) at every written frame <= 1e-6.
Also: Cp min/max on the fluid nodes of every frames/flow_kkkk.npz (the early-frame Cp check of the spec).
Prints T1GATES {json}; exit 1 when gate 3 fails or a frame is missing.
"""
import json
import sys
from pathlib import Path

import numpy as np

import transient as tr

CD_STEADY = 1.1498           # gated steady Cd, same mesh (validation/, step 2)
KLOTZ = {"St": 0.125, "Re_max": 390, "ref": "Klotz et al. 2014, J. Fluid Mech. 750, 73-98, doi:10.1017/jfm.2014.236"}
CONT_MAX = 1e-6
U, L, RHO = 20.0, 2.0, 1.225


def read_coefficients(path):
    names, rows = [], []
    for line in Path(path).read_text().splitlines():
        if line.startswith("#"):
            names = line[1:].split()
        elif line.strip():
            rows.append(line.split())
    rows = [r for r in rows if len(r) == len(names)]
    return {n: np.array([float(r[i]) for r in rows]) for i, n in enumerate(names)}


def main():
    case = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else case / "t1_gates.json"
    log = (case / "log.pimpleFoam").read_text(errors="replace")
    cont = tr.frame_continuity(log)
    n_frames = round(2.0 * tr.FPS_CFD)
    missing = [k for k in range(1, n_frames + 1) if k not in cont]
    worst = max(cont.items(), key=lambda kv: kv[1]) if cont else (None, None)
    over = {k: v for k, v in cont.items() if v > CONT_MAX}
    steps = tr.step_continuity(log)

    c = read_coefficients(case / "postProcessing/forceCoeffs/0/coefficient.dat")
    t = c["Time"]
    cd = {"window_1_2s": tr.window_mean(t, c["Cd"], 1.0, 2.0), "window_0p5_1s": tr.window_mean(t, c["Cd"], 0.5, 1.0)}
    w = (t >= 1.0) & (t <= 2.0)
    cd.update(min_1_2s=float(c["Cd"][w].min()), max_1_2s=float(c["Cd"][w].max()), steady_gated=CD_STEADY,
              ratio_to_steady=cd["window_1_2s"] / CD_STEADY)
    st = {name: tr.strouhal(t, c[name], U, L, 1.0, 2.0) for name in ("Cs", "Cl")}
    tail = (t >= 1.75) & (t <= 2.0)
    for name in ("Cs", "Cl"):
        sd, sd_tail = float(c[name][w].std()), float(c[name][tail].std())
        st[name].update(mean=tr.window_mean(t, c[name], 1.0, 2.0), std=sd, std_last_0p25s=sd_tail,
                        tail_to_window=sd_tail / sd if sd else None)
        # Counting periods only works for a sustained oscillation: a start-up transient that dies out
        # inside the window has periods but no shedding frequency (spec Stage 4 note).
        if st[name]["verdict"] == "measured" and sd_tail < 0.25 * sd:
            st[name]["verdict"] = "not measurable: oscillation decays inside the window (no sustained shedding)"

    q = 0.5 * RHO * U ** 2
    cp = {}
    for k in range(1, n_frames + 1):
        f = case / "frames" / tr.frame_name(k, "npz")
        if f.exists():
            d = np.load(f)
            v = d["p"][~d["solid"]] / q
            cp[k] = [round(float(v.min()), 4), round(float(v.max()), 4)]
    late = [cp[k] for k in cp if k >= 60]

    rep = {
        "date": "2026-10-24", "solver": "pimpleFoam v2512, k-omega SST, backward, maxCo 1, PISO 1/2",
        "case": str(case), "cells": 359618, "steps": len(steps), "end_time": float(t[-1]),
        "gate1_Cd": cd,
        "gate2_St": {**st, "reference": KLOTZ},
        "gate3_continuity": {"limit": CONT_MAX, "frames": len(cont), "missing": missing,
                             "max": worst[1], "max_frame": worst[0], "over_limit": over,
                             "max_any_step": max(v for _, v in steps) if steps else None,
                             "per_frame": {str(k): v for k, v in sorted(cont.items())},
                             "verdict": "PASS" if cont and not over and not missing else "FAIL"},
        "frame_cp_range": {str(k): v for k, v in cp.items()},
        "cp_range_1_2s": [min(a for a, _ in late), max(b for _, b in late)] if late else None,
        "cp_range_last_frame": cp.get(n_frames),
        "cp_range_steady_same_grid": [-0.6772, 1.0245],
    }
    out.write_text(json.dumps(rep, indent=1) + "\n")
    print("T1GATES " + json.dumps({k: v for k, v in rep.items() if k not in ("frame_cp_range",)}
                                 | {"gate3_continuity": {k: v for k, v in rep["gate3_continuity"].items()
                                                         if k != "per_frame"}}))
    return 0 if rep["gate3_continuity"]["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
