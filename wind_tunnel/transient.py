"""Pure rules for the time-resolved run (TRANSIENT T1, no bpy): which written time is which frame, the
VDB sequence, the plain smoke inputs, the time label, and the maths of the honesty gates (continuity
error per frame, time-averaged Cd, Strouhal number).

Spec: docs/reference/transient_t1_spec.md. Frame k (k = 1..N) is physical time t = k / fps_cfd
(fps_cfd = 60 written frames per second of flow), so t U/L = k U / (60 L); scene frame k shows it.
"""
from __future__ import annotations

import math
import re

import numpy as np

FPS_CFD = 60          # frames written per second of physical time
FRAME_TOL = 1e-3      # a written time is frame k when |t fps - k| < this (time names have 8 digits)
PLAIN_SRGB = (48, 48, 48)   # streak colour: charcoal, readable on every Cp colour of the slice


# ---------------------------------------------------------------- frames
def frame_time(k, fps=FPS_CFD):
    return k / fps


def frame_tUL(k, U, L, fps=FPS_CFD):
    """Flow-throughs at frame k: t U / L."""
    return k / fps * U / L


def frame_from_time(name, fps=FPS_CFD, tol=FRAME_TOL):
    """Frame index of a time directory name ('0.016666667' -> 1), or None for t = 0, a time step between
    frames, or a name that is not a number. Matched with a tolerance, never by string."""
    try:
        t = float(name)
    except (TypeError, ValueError):
        return None
    k = round(t * fps)
    return k if k >= 1 and abs(t * fps - k) < tol else None


def frame_name(k, ext):
    return f"flow_{k:04d}.{ext}"


def vdb_sequence(n_frames):
    """Volume settings so scene frame k loads flow_000k.vdb (Blender: file number = scene frame -
    frame_start + 1 + frame_offset); CLIP leaves the volume empty outside 1..n, it never repeats."""
    return {"is_sequence": True, "frame_start": 1, "frame_duration": n_frames, "frame_offset": 0,
            "sequence_mode": "CLIP"}


def time_label(k, U, L, fps=FPS_CFD):
    """'t = 0.500 s (t U/L = 5.00)'."""
    return f"t = {frame_time(k, fps):.3f} s (t U/L = {frame_tUL(k, U, L, fps):.2f})"


def plain_smoke_inputs(L, U, scene_fps, voxel, fps=FPS_CFD):
    """Smoke tree inputs for a time-resolved field (open issue i, as changed at the T1 HIL: thin charcoal
    streaks released in a sheet within +-0.05 L of the slice plane y = centre, 40 a frame). Particles
    move by exactly one CFD frame interval (1/fps s) per scene frame, so they keep pace with the field
    at any video frame rate; the step is split into substeps of at most one voxel at 1.5 U_inf."""
    sheet = 0.05 * L
    return {
        "Use Field": True,
        "Plain": True,
        "Time Scale": scene_fps / fps,                         # Delta Time (1 / scene_fps) * this = 1 / fps
        "Substeps": max(1, math.ceil(1.5 * U / fps / voxel - 1e-9)),
        "Sheet": sheet,                                          # half thickness of the release plane in y
        "Rate": 40.0 / (1.4 * L * 2 * sheet),                   # per m2 of the release plane: 40 a frame
        "Lifetime": float(math.ceil(1.5 * 4.25 * L * fps / U)),  # frames: the 4.25 L grid at 1 / 1.5 of U_inf
        "Trail": 0.1 * L / U,                                   # s: streak length |v| Trail, 0.1 L at U_inf
        "Radius": L / 600.0,
    }


# ---------------------------------------------------------------- gate 3: continuity error per frame
_TIME = re.compile(r"^Time = ([-+0-9.eE]+)s?\s*$")
_CONT = re.compile(r"^time step continuity errors : sum local = ([-+0-9.eE]+)")


def step_continuity(log_text):
    """[(time, sum local)] per time step of a pimpleFoam log: the last corrector's value (after pFinal).
    'sum local' = deltaT * volume-weighted mean of |div(phi)| (continuityErrs.H)."""
    out, t, last = [], None, None
    for line in log_text.splitlines():
        m = _TIME.match(line)
        if m:
            if t is not None and last is not None:
                out.append((t, last))
            t, last = float(m.group(1)), None
            continue
        m = _CONT.match(line)
        if m:
            last = float(m.group(1))
    if t is not None and last is not None:
        out.append((t, last))
    return out


def frame_continuity(log_text, fps=FPS_CFD):
    """{frame k: sum local of the time step that ends at frame k's time}."""
    out = {}
    for t, v in step_continuity(log_text):
        k = frame_from_time(repr(t), fps)
        if k is not None:
            out[k] = v
    return out


# ---------------------------------------------------------------- gates 1 and 2: Cd and St
def window_mean(t, y, t0, t1):
    """Time average of y over [t0, t1] by the trapezoid rule (time steps are not uniform)."""
    t, y = np.asarray(t, float), np.asarray(y, float)
    tt = np.concatenate([[t0], t[(t > t0) & (t < t1)], [t1]])
    yy = np.interp(tt, t, y)
    return float(np.sum(0.5 * (yy[1:] + yy[:-1]) * np.diff(tt)) / (t1 - t0))


def strouhal(t, s, U, L, t0, t1, min_periods=2):
    """Shedding frequency of a side-force signal over [t0, t1], as St = f L / U, two ways: zero
    crossings of s - mean (f = half periods / 2 / their span) and the peak of the zero-padded spectrum
    of the signal resampled uniformly. Fewer than min_periods full periods between the first and last
    crossing: 'not measurable', no number."""
    t, s = np.asarray(t, float), np.asarray(s, float)
    m = (t >= t0) & (t <= t1)
    tt, ss = t[m], s[m] - s[m].mean()
    i = np.nonzero(np.signbit(ss[:-1]) != np.signbit(ss[1:]))[0]
    tc = tt[i] - ss[i] * (tt[i + 1] - tt[i]) / (ss[i + 1] - ss[i])
    periods = (len(tc) - 1) / 2 if len(tc) > 1 else 0.0
    out = {"window": [t0, t1], "periods": periods, "St_crossings": None, "St_spectrum": None,
           "verdict": "not measurable"}
    if periods < min_periods:
        return out
    f_c = periods / (tc[-1] - tc[0])
    n = len(tt)
    tu = np.linspace(tt[0], tt[-1], n)
    su = np.interp(tu, tt, ss) * np.hanning(n)
    nfft = 8 * int(2 ** math.ceil(math.log2(n)))
    spec = np.abs(np.fft.rfft(su, nfft))
    freq = np.fft.rfftfreq(nfft, tu[1] - tu[0])
    spec[0] = 0.0
    f_s = float(freq[np.argmax(spec)])
    out.update(St_crossings=f_c * L / U, St_spectrum=f_s * L / U, verdict="measured")
    return out
