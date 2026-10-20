#!/usr/bin/env python3
"""Convergence gate of a steady 3D run (FIX_PLAN step 2, docs/reference/step2_convergence_reference.md).

Converged at iteration n when, over the window n-199..n:
  (max - min) / abs(mean) of the drag force Fx < 0.5 %   (the same band as Cd, which is Fx / (q A))
  the first p solve's normalised initial residual at n < 1e-3
  n >= 400
Both criteria are hard (grill Q2, kept in Q5). The reasons also give the p residual trend over the
window, in orders of magnitude per 100 iterations, so an open gate says whether the run is stalled
or only slow.

Reads postProcessing/forces/*/force.dat and postProcessing/solverInfo/*/solverInfo.dat. Standard
library only: the systemCall function object runs `python3 convergence.py . --trigger` every
5 iterations inside WSL, and on a pass it writes `wt_stop`, which the abort function object reads.
export_field.py imports it for the final verdict.
"""
import math
import sys
from pathlib import Path

WINDOW = 200          # iterations in the gate window
BAND = 0.005          # (max - min) / abs(mean) of Fx over the window
RESIDUAL = 1e-3       # p initial residual at the last iteration
MIN_ITER = 400        # never converged before this iteration
STOP_FILE = "wt_stop"


def read_dat(path):
    """(column names, rows of string fields) of a function object .dat file. The names come from the
    last `#` line; a last line without its newline may still be being written, so it is dropped."""
    text = Path(path).read_text(errors="replace")
    lines = text.split("\n")
    lines.pop()                     # "" after a final newline, or the unfinished last line
    names, rows = [], []
    for line in lines:
        if line.startswith("#"):
            names = line[1:].split()
        elif line.strip():
            rows.append(line.split())
    return names, rows


def _merged(case, fo, filename, columns):
    """{time: [values of `columns`]} over every postProcessing/<fo>/<startTime>/<filename>, the start
    times in numeric order so that a restart's rows replace the earlier run's at the same time."""
    base = Path(case) / "postProcessing" / fo
    starts = []
    if base.is_dir():
        for d in base.iterdir():
            try:
                starts.append((float(d.name), d))
            except ValueError:
                pass
    out = {}
    for _, d in sorted(starts):
        path = d / filename
        if not path.is_file():
            continue
        names, rows = read_dat(path)
        idx = [names.index(c) for c in ["Time"] + columns]
        for r in rows:
            if len(r) >= len(names):
                out[int(round(float(r[idx[0]])))] = [float(r[i]) for i in idx[1:]]
    return out


def history(case):
    """Per-iteration force (N) and p initial residual, on the iterations both files have."""
    f = _merged(case, "forces", "force.dat", ["total_x", "total_y", "total_z"])
    r = _merged(case, "solverInfo", "solverInfo.dat", ["p_initial"])
    times = sorted(set(f) & set(r))
    return {"time": times, "fx": [f[t][0] for t in times], "fy": [f[t][1] for t in times],
            "fz": [f[t][2] for t in times], "p_initial": [r[t][0] for t in times]}


def _stats(v):
    return {"mean": sum(v) / len(v), "min": min(v), "max": max(v)}


def _trend(times, res):
    """Least-squares slope of log10(residual) in orders of magnitude per 100 iterations."""
    pts = [(t, math.log10(r)) for t, r in zip(times, res) if r > 0]
    if len(pts) < 2:
        return None
    mt = sum(t for t, _ in pts) / len(pts)
    my = sum(y for _, y in pts) / len(pts)
    sxx = sum((t - mt) ** 2 for t, _ in pts)
    return 100 * sum((t - mt) * (y - my) for t, y in pts) / sxx if sxx else None


def gate(times, fx, fy, fz, p_initial, cap=None):
    """Verdict at the last iteration of the history: converged, reasons (empty when converged),
    iteration, window (first, last), band, residual, residual_trend, and fx/fy/fz mean/min/max over
    the window (N)."""
    if not times:
        return {"converged": False, "reasons": ["no force or residual history yet"], "iteration": 0,
                "window": None, "band": None, "residual": None, "residual_trend": None,
                "fx": None, "fy": None, "fz": None}
    n = times[-1]
    sel = [i for i, t in enumerate(times) if t > n - WINDOW]
    w = lambda v: [v[i] for i in sel]
    sx = _stats(w(fx))
    band = (sx["max"] - sx["min"]) / abs(sx["mean"]) if sx["mean"] else math.inf
    res = p_initial[-1]
    trend = _trend(w(times), w(p_initial))
    a = times[sel[0]]
    reasons = []
    if n < MIN_ITER:
        reasons.append(f"iteration {n} is before {MIN_ITER}")
    if len(sel) < WINDOW:
        reasons.append(f"only {len(sel)} of the {WINDOW} window iterations recorded")
    if not band < BAND:
        reasons.append(f"Cd band {100 * band:.2f} % >= {100 * BAND:g} % over iterations {a} to {n}")
    if not res < RESIDUAL:
        how = "" if trend is None else f" (trend {trend:+.2f} orders per 100 iterations)"
        reasons.append(f"p residual {res:.1e} >= {RESIDUAL:g}{how}")
    if reasons and cap is not None and n >= cap:
        reasons.insert(0, f"stopped at the cap of {cap} iterations")
    return {"converged": not reasons, "reasons": reasons, "iteration": n, "window": (a, n), "band": band,
            "residual": res, "residual_trend": trend,
            "fx": sx, "fy": _stats(w(fy)), "fz": _stats(w(fz))}


def main(argv=None):
    """`convergence.py CASE --trigger`: writes CASE/wt_stop when the gate passes. Never fails the
    solver: any error is printed and the gate stays open."""
    argv = sys.argv[1:] if argv is None else argv
    case = Path(argv[0]) if argv else Path(".")
    try:
        h = history(case)
        v = gate(h["time"], h["fx"], h["fy"], h["fz"], h["p_initial"])
    except Exception as e:
        print(f"wt gate: history not readable ({type(e).__name__}: {e})", flush=True)
        return 0
    if v["converged"]:
        print(f"wt gate {v['iteration']}: converged, band {100 * v['band']:.2f} %, "
              f"p residual {v['residual']:.2e}", flush=True)
        if "--trigger" in argv:
            (case / STOP_FILE).write_text("action=writeNow\n", newline="\n")
    else:
        print(f"wt gate {v['iteration']}: open; " + "; ".join(v["reasons"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
