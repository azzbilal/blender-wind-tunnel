"""The solved OpenFOAM flow as something Blender can draw: a regular grid of velocity and pressure,
streamlines traced through it, and particle paths timed by the real velocities.

Everything is in the airfoil's own frame (chord along x from 0 to 1, thickness along y), where
OpenFOAM solved it with the freestream turned by the angle of attack. Blender shows the same frame
on the airfoil object, so the flow objects are simply parented to it. numpy only; the nearest-cell
search uses Blender's mathutils KD-tree when available and scipy otherwise.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from . import results


# ---------------------------------------------------------------- the cell data
def cell_centres(case: Path):
    """(x, y) of every cell centre: the mean of its face centres (exact enough for these hexes)."""
    pm = Path(case) / "constant" / "polyMesh"
    pts = np.array(results.read_points(pm / "points"))[:, :2]
    faces = results.read_faces(pm / "faces")
    owner = np.array(results.read_labels(pm / "owner"))
    neigh = np.array(results.read_labels(pm / "neighbour"))
    fc = np.array([pts[f].mean(axis=0) for f in faces])
    n = max(owner.max(), neigh.max()) + 1
    acc = np.zeros((n, 2))
    cnt = np.zeros(n)
    np.add.at(acc, owner, fc)
    np.add.at(cnt, owner, 1)
    np.add.at(acc, neigh, fc[: len(neigh)])
    np.add.at(cnt, neigh, 1)
    return acc / cnt[:, None]


def cell_fields(case: Path, time: str):
    U, U0 = results.read_internal(Path(case) / time / "U", 3)
    p, p0 = results.read_internal(Path(case) / time / "p", 1)
    U = np.array(U)[:, :2] if U is not None else None
    p = np.array(p) if p is not None else None
    return U, p


def _nearest(points, queries, k):
    """Indices and distances of the k nearest points for each query, shape (nq, k)."""
    try:
        from mathutils.kdtree import KDTree
        tree = KDTree(len(points))
        for i, (x, y) in enumerate(points):
            tree.insert((x, y, 0.0), i)
        tree.balance()
        idx = np.empty((len(queries), k), dtype=np.int64)
        dist = np.empty((len(queries), k))
        for q, (x, y) in enumerate(queries):
            found = tree.find_n((x, y, 0.0), k)
            for m, (_, i, d) in enumerate(found):
                idx[q, m], dist[q, m] = i, d
        return idx, dist
    except ImportError:
        from scipy.spatial import cKDTree
        dist, idx = cKDTree(points).query(queries, k=k)
        return idx, dist


def inside(poly, x, y):
    """Even-odd test of points (x, y arrays) against a closed polygon [(x, y), ...]."""
    poly = np.asarray(poly)
    res = np.zeros(x.shape, dtype=bool)
    xj, yj = poly[-1]
    for xi, yi in poly:
        cross = (yi > y) != (yj > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (xj - xi) * (y - yi) / (yj - yi) + xi
        res ^= cross & (x < xint)
        xj, yj = xi, yi
    return res


# ---------------------------------------------------------------- the grid
class Field:
    """Velocity (ux, uy) and pressure on a regular grid; solid nodes (inside the body) have zero velocity."""

    def __init__(self, x0, y0, h, ux, uy, p, solid):
        self.x0, self.y0, self.h = x0, y0, h
        self.ux, self.uy, self.p, self.solid = ux, uy, p, solid
        self.ny, self.nx = ux.shape

    @classmethod
    def from_case(cls, case: Path, time: str, polygon, box=(-1.0, 3.0, -1.2, 1.2), h=0.005, k=4):
        xc = cell_centres(case)
        U, p = cell_fields(case, time)
        x0, x1, y0, y1 = box
        nx, ny = int(round((x1 - x0) / h)) + 1, int(round((y1 - y0) / h)) + 1
        gx, gy = np.meshgrid(x0 + h * np.arange(nx), y0 + h * np.arange(ny))
        q = np.column_stack([gx.ravel(), gy.ravel()])
        idx, dist = _nearest(xc, q, k)
        w = 1.0 / np.maximum(dist, 1e-9) ** 2
        w /= w.sum(axis=1, keepdims=True)
        ux = (U[idx, 0] * w).sum(axis=1).reshape(ny, nx)
        uy = (U[idx, 1] * w).sum(axis=1).reshape(ny, nx)
        pp = (p[idx] * w).sum(axis=1).reshape(ny, nx)
        solid = inside(polygon, gx, gy)
        ux[solid] = uy[solid] = 0.0
        pp[solid] = np.nan
        return cls(x0, y0, h, ux, uy, pp, solid)

    def save(self, path: Path):
        np.savez_compressed(path, x0=self.x0, y0=self.y0, h=self.h, ux=self.ux, uy=self.uy, p=self.p, solid=self.solid)

    @classmethod
    def load(cls, path: Path):
        d = np.load(path)
        return cls(float(d["x0"]), float(d["y0"]), float(d["h"]), d["ux"], d["uy"], d["p"], d["solid"])

    def bounds(self):
        return self.x0, self.x0 + self.h * (self.nx - 1), self.y0, self.y0 + self.h * (self.ny - 1)

    def velocity(self, xy):
        """Bilinear velocity at points xy (n, 2); zero outside the grid."""
        fx = (xy[:, 0] - self.x0) / self.h
        fy = (xy[:, 1] - self.y0) / self.h
        ok = (fx >= 0) & (fy >= 0) & (fx < self.nx - 1) & (fy < self.ny - 1)
        i = np.clip(fx.astype(int), 0, self.nx - 2)
        j = np.clip(fy.astype(int), 0, self.ny - 2)
        tx, ty = fx - i, fy - j
        out = np.zeros_like(xy)
        for f, col in ((self.ux, 0), (self.uy, 1)):
            v = (f[j, i] * (1 - tx) * (1 - ty) + f[j, i + 1] * tx * (1 - ty)
                 + f[j + 1, i] * (1 - tx) * ty + f[j + 1, i + 1] * tx * ty)
            out[:, col] = np.where(ok, v, 0.0)
        return out, ok

    def pressure(self, xy):
        fx = np.clip(((xy[:, 0] - self.x0) / self.h).round().astype(int), 0, self.nx - 1)
        fy = np.clip(((xy[:, 1] - self.y0) / self.h).round().astype(int), 0, self.ny - 1)
        return self.p[fy, fx]


# ---------------------------------------------------------------- seeds and paths
def seed_line(alpha_deg: float, n: int, width: float = 0.9, upstream: float = 0.8, centre=(0.3, 0.0)):
    """n points on a line across the oncoming flow, `upstream` chords ahead of `centre`."""
    a = math.radians(alpha_deg)
    d = np.array([math.cos(a), math.sin(a)])
    nrm = np.array([-d[1], d[0]])
    c = np.array(centre) - upstream * d
    s = np.linspace(-width / 2, width / 2, n)
    return c + s[:, None] * nrm


def trace(field: Field, seeds, dt: float = 0.004, steps: int = 1200):
    """Paths of fluid particles released at `seeds`, one point every `dt` (midpoint rule).

    Because the flow is steady these are the streamlines, and equal time steps mean a particle
    moves one point per step: animating along them reproduces the real speeds. A path that leaves
    the grid or touches the body stops there (its remaining points repeat the last one).
    Returns positions (n, steps+1, 2) and speeds (n, steps+1).
    """
    pos = np.array(seeds, dtype=float)
    n = len(pos)
    out = np.empty((n, steps + 1, 2))
    spd = np.empty((n, steps + 1))
    alive = np.ones(n, dtype=bool)
    v, _ = field.velocity(pos)
    out[:, 0], spd[:, 0] = pos, np.hypot(v[:, 0], v[:, 1])
    for k in range(1, steps + 1):
        v1, ok1 = field.velocity(pos)
        mid = pos + 0.5 * dt * v1
        v2, ok2 = field.velocity(mid)
        new = pos + dt * v2
        alive &= ok1 & ok2 & (np.hypot(v2[:, 0], v2[:, 1]) > 1e-4)
        pos = np.where(alive[:, None], new, pos)
        out[:, k] = pos
        spd[:, k] = np.where(alive, np.hypot(v2[:, 0], v2[:, 1]), spd[:, k - 1])
    return out, spd
