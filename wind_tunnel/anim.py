"""Pure rules for animating a steady 3D result (no bpy): the diverging Cp colour ramp, the slice
sweep keyframes, which slice vertices are shown, and the label and legend text.

viz3d builds the same rules in Geometry Nodes; tests/test_pure.py checks them here. Spec:
docs/reference/anim_ab_spec.md (Q1 sweep, Q2 colour).
"""
from __future__ import annotations

import numpy as np

# Cp range of the diverging ramp: Cp = +1 is the incompressible stagnation limit, Cp = -1 is
# |U| = sqrt(2) U_inf. Ends clamp.
CP_RANGE = (-1.0, 1.0)

# Moreland cool-warm, 9 stops (endpoints from Moreland 2009, intermediates from our Msh interpolation).
# ColorRamp elements take the linear column; the sRGB column is what a Standard-view render must show.
CP_STOPS_SRGB = [(59, 76, 192), (98, 130, 234), (141, 176, 254), (184, 208, 249), (221, 221, 221),
                 (245, 196, 173), (244, 154, 123), (222, 97, 76), (180, 4, 38)]
CP_STOPS = [(0.0, (0.0437, 0.0723, 0.5271)), (0.125, (0.1219, 0.2224, 0.8213)),
            (0.25, (0.2669, 0.4320, 0.9890)), (0.375, (0.4805, 0.6276, 0.9474)),
            (0.5, (0.7207, 0.7207, 0.7205)), (0.625, (0.9096, 0.5541, 0.4174)),
            (0.75, (0.9080, 0.3222, 0.1975)), (0.875, (0.7285, 0.1184, 0.0731)),
            (1.0, (0.4564, 0.0012, 0.0194))]

# A slice vertex is shown when the trilinear weight of fluid grid nodes around it is at least this
# (1 = all eight corners are fluid and inside the grid; float32 sampling in Blender gives 0.9999999).
KEEP_MIN = 0.999


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _clamp01(x):
    return min(max(x, 0.0), 1.0)


def cp_to_ramp(cp, lo=CP_RANGE[0], hi=CP_RANGE[1]):
    """Ramp coordinate 0..1: [lo, 0] -> [0, 0.5] and [0, hi] -> [0.5, 1], clamped outside, so Cp = 0
    is always the neutral stop. Same sum of two clamped Map Range nodes as the node tree."""
    a = 0.5 * _clamp01((cp - lo) / (0.0 - lo))
    b = 0.5 + 0.5 * _clamp01(cp / hi)
    return a + b - 0.5


def sweep_half_range(axis, centre, L, grid_lo, grid_hi, h, margin_voxels=10, factor=1.0):
    """Half range of the sweep: factor * L about the body centre, kept margin_voxels inside the grid."""
    i = "XYZ".index(axis)
    c = centre[i]
    return min(factor * L, c - (grid_lo[i] + margin_voxels * h), (grid_hi[i] - margin_voxels * h) - c)


def sweep_keyframes(axis, centre, half_range, frames=192, pingpong=True):
    """[(frame, location)] for frames 1..frames. Ping-pong: centre - R at frame 1, centre + R at frame
    frames / 2 + 1, then back at the same speed, so frame frames + 1 would be frame 1 again."""
    i = "XYZ".index(axis)
    R = half_range
    out = []
    for f in range(1, frames + 1):
        s = f - 1
        if pingpong:
            half = frames // 2
            d = -R + 2 * R * s / half if s <= half else R - 2 * R * (s - half) / half
        else:
            d = -R + 2 * R * s / (frames - 1)
        loc = list(centre)
        loc[i] = centre[i] + d
        out.append((f, tuple(loc)))
    return out


def slice_keep(points, origin, h, solid, keep_min=KEEP_MIN):
    """Which points (N x 3, world) a slice shows: the trilinear weight of the grid nodes that are fluid
    (inside the grid and not in the solid mask) is at least keep_min. Clips the slice to the grid
    bounds and the solid mask with one rule, the one the node tree samples from the 'fluid' grid."""
    P = (np.asarray(points, float) - np.asarray(origin, float)) / h
    n = np.array(solid.shape)
    inside = np.all((P >= -1e-9) & (P <= n - 1 + 1e-9), axis=1)
    i0 = np.clip(np.floor(P).astype(int), 0, n - 2)
    f = np.clip(P - i0, 0.0, 1.0)
    fluid = ~solid
    w = np.zeros(len(P))
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                wt = ((f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1])
                      * (f[:, 2] if dz else 1 - f[:, 2]))
                w += wt * fluid[i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz]
    return inside & (w >= keep_min)


def label_text(axis, offset, L, pressure):
    """'Slice y = +0.85 m (+0.43 L) | Cp'. offset is the slice position minus the body centre along
    the sweep axis. float32 arithmetic, as Geometry Nodes computes it."""
    off = np.float32(offset)
    r = np.float32(off / np.float32(L))
    what = "Cp" if pressure else "speed/U_inf"
    return f"Slice {axis.lower()} = {float(off):+.2f} m ({float(r):+.2f} L) | {what}"


def legend_ticks(pressure, lo=CP_RANGE[0], hi=CP_RANGE[1]):
    """[(ramp coordinate, text)] of the legend ticks: Cp lo, lo/2, 0, hi/2, hi (ends clamp, so they read
    '<=' and '>='), or speed/U_inf 0.3 to 1.9 in steps of 0.4."""
    if not pressure:
        return [(k / 4, f"{0.3 + 0.4 * k:.1f}") for k in range(5)]
    return [(cp_to_ramp(lo, lo, hi), f"<= {lo:.1f}"), (cp_to_ramp(lo / 2, lo, hi), f"{lo / 2:+.1f}"),
            (0.5, "0"), (cp_to_ramp(hi / 2, lo, hi), f"{hi / 2:+.1f}"), (cp_to_ramp(hi, lo, hi), f">= {hi:+.1f}")]
