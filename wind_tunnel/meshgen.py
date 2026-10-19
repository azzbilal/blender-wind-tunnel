"""A structured C-grid around any closed 2D profile, written straight to OpenFOAM's polyMesh format.

Grid lines leave the wall along its normals, so near-wall cells are orthogonal, then bend
smoothly towards a C-shaped far field: a half circle centred on the trailing edge, closed by a
straight wake box. No blockMesh, no OpenFOAM version dependence. Pure Python, no Blender import.

Index layout (i along the C, j away from the wall):
    i = 0 .. nw                  lower wake, outlet -> trailing edge
    i = nw .. nw + 2*ns          lower surface TE -> LE -> upper surface LE -> TE
    i = nw + 2*ns .. 2*(nw+ns)   upper wake, trailing edge -> outlet
At j = 0 the lower and upper wake lines coincide (the wake cut); their points are merged
and the faces between them are internal.
"""
from __future__ import annotations

import math
from pathlib import Path

HEADER = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    location    "constant/polyMesh";
    object      {obj};
}}
"""


# ---------------------------------------------------------------- 1D distributions
def two_sided(n: int, d0: float, d1: float):
    """n+1 points on [0, 1] with first spacing d0 and last d1 (Vinokur's tanh stretching)."""
    A = math.sqrt(d1 / d0)
    B = 1.0 / (n * math.sqrt(d0 * d1))
    if B <= 1.0:   # spacings too large to need stretching: fall back to uniform
        return [k / n for k in range(n + 1)]
    lo, hi = 1e-9, 60.0
    for _ in range(200):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if math.sinh(m) / m < B else (lo, m)
    dl = (lo + hi) / 2
    out = []
    for k in range(n + 1):
        u = 0.5 * (1 + math.tanh(dl * (k / n - 0.5)) / math.tanh(dl / 2))
        out.append(u / (A + (1 - A) * u))
    out[0], out[-1] = 0.0, 1.0
    return out


def geometric(n: int, length: float, first: float):
    """n+1 cumulative distances from 0 to length, first cell `first`, constant growth."""
    if abs(first * n - length) < 1e-12:
        return [length * k / n for k in range(n + 1)]
    lo, hi = -1.0, 1.0
    for _ in range(200):
        m = (lo + hi) / 2
        r = math.exp(m)
        f = length * (r - 1) / (r ** n - 1) if abs(m) > 1e-14 else length / n
        lo, hi = (m, hi) if f > first else (lo, m)
    r = math.exp((lo + hi) / 2)
    out, h = [0.0], 0.0
    cell = length * (r - 1) / (r ** n - 1) if abs(r - 1) > 1e-14 else length / n
    for _ in range(n):
        h += cell
        out.append(h)
        cell *= r
    out[-1] = length
    return out


# ---------------------------------------------------------------- polylines
def _cum(pts):
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + math.dist(a, b))
    return s


def resample(pts, fractions):
    """Points along a polyline at the given arc-length fractions (0..1)."""
    s = _cum(pts)
    L = s[-1]
    out, k = [], 0
    for f in fractions:
        t = f * L
        while k < len(s) - 2 and s[k + 1] < t:
            k += 1
        seg = s[k + 1] - s[k]
        w = 0.0 if seg == 0 else (t - s[k]) / seg
        a, b = pts[k], pts[k + 1]
        out.append((a[0] + w * (b[0] - a[0]), a[1] + w * (b[1] - a[1])))
    return out


def _unit(v):
    n = math.hypot(v[0], v[1])
    return (v[0] / n, v[1] / n)


# ---------------------------------------------------------------- the grid
def c_grid(upper, lower, *, ns=100, nw=60, nj=80, radius=20.0, wake=20.0,
           first_cell=2e-4, le_cell=0.002, te_cell=0.004, te_blend=0.25, outlet_cell=0.01):
    """Points of the C-grid, as rows grid[j][i] of (x, y).

    `upper` and `lower` run from the leading edge (0, 0) to the trailing edge (1, 0), dense enough
    to define the shape; they are resampled with clustering at both edges.
    """
    H, W = radius, wake
    fr = two_sided(ns, le_cell, te_cell)
    up = resample(upper, fr)
    lo = resample(lower, fr)
    te = up[-1]
    surf = list(reversed(lo)) + up[1:]                                 # TE lower -> LE -> TE upper
    te_len = math.dist(up[-1], up[-2])
    xw = [te[0] + d for d in geometric(nw, W, te_len)]                 # TE -> outlet
    inner = [(x, te[1]) for x in reversed(xw)] + surf[1:-1] + [(x, te[1]) for x in xw]
    NI = len(inner) - 1                                                # = 2 nw + 2 ns

    # Wall normals: central differences on the surface, straight up/down on the wake line.
    normals = []
    for i, p in enumerate(inner):
        if i < nw:
            normals.append((0.0, -1.0))
        elif i > NI - nw:
            normals.append((0.0, 1.0))
        else:
            a, b = inner[max(i - 1, 0)], inner[min(i + 1, NI)]
            t = _unit((b[0] - a[0], b[1] - a[1]))
            n = (-t[1], t[0])   # i runs clockwise round the body, so this points outward
            # Near the trailing edge, turn the normals towards the wake lines' vertical so that
            # neighbouring grid lines cannot cross; the blend fades out over te_blend chords.
            lower_side = i < nw + ns
            d = math.dist(inner[i], te)
            b = math.exp(-d / te_blend)
            v = (0.0, -1.0) if lower_side else (0.0, 1.0)
            n = _unit(((1 - b) * n[0] + b * v[0], (1 - b) * n[1] + b * v[1]))
            normals.append(n)

    # Far-field points: vertical lines over the wake, a half circle centred on the TE elsewhere.
    # Each surface point gets an angle that follows its normal, spread by its arc length so the
    # far field is not crowded where the normals are nearly parallel; kept strictly monotonic.
    surf_i = range(nw, NI - nw + 1)
    s = _cum([inner[i] for i in surf_i])
    outer = [None] * (NI + 1)
    prev = -math.pi / 2
    k_last = len(s) - 1
    for k, i in enumerate(surf_i):
        n = normals[i]
        phi = math.atan2(n[1], n[0])          # -pi/2 at TE lower ... pi at LE ... pi/2 at TE upper
        if phi < 0:
            phi += 2 * math.pi
        phi = min(max(phi, math.pi / 2), 3 * math.pi / 2)
        ang_n = 3 * math.pi / 2 - phi         # 0 at TE lower, pi at TE upper
        ang_s = math.pi * s[k] / s[-1]
        ang = 0.5 * ang_n + 0.5 * ang_s
        if k == 0:
            ang = 0.0
        elif k == k_last:
            ang = math.pi
        else:
            ang = max(ang, prev + 1e-4)
        prev = ang
        th = -math.pi / 2 - ang               # -pi/2 (bottom) -> -pi (front) -> -3pi/2 (top)
        outer[i] = (te[0] + H * math.cos(th), te[1] + H * math.sin(th))
    for i in range(nw):
        outer[i] = (inner[i][0], te[1] - H)
        outer[NI - i] = (inner[NI - i][0], te[1] + H)

    # Wall-normal distances. On the wake line the first cell grows from the wall value at the TE
    # to `outlet_cell` at the outlet, which keeps the wake cells from becoming needle-thin.
    dists = {}

    def dist(first):
        key = round(first, 12)
        if key not in dists:
            dists[key] = geometric(nj, H, first)
        return dists[key]

    firsts = []
    for i in range(NI + 1):
        if i < nw or i > NI - nw:
            f = (inner[i][0] - te[0]) / W
            firsts.append(first_cell * (outlet_cell / first_cell) ** f)
        else:
            firsts.append(first_cell)

    grid = [list(inner)]
    for j in range(1, nj + 1):
        row = []
        for i in range(NI + 1):
            hj = dist(firsts[i])[j]
            e = hj / H                            # 0 at the wall, 1 at the far field
            w = e ** 0.35                         # weight of the straight line to the far field
            p, n, q = inner[i], normals[i], outer[i]
            L = math.dist(p, q)
            h = hj + (L - H) * e * e              # absolute near the wall, ends exactly on the far field
            a = (p[0] + h * n[0], p[1] + h * n[1])
            b = (p[0] + (h / L) * (q[0] - p[0]), p[1] + (h / L) * (q[1] - p[1]))
            row.append(((1 - w) * a[0] + w * b[0], (1 - w) * a[1] + w * b[1]))
        grid.append(row)
    return grid, nw, ns


def cell_areas(grid):
    """Signed areas of every quad; all must have the same sign for a valid grid."""
    out = []
    for j in range(len(grid) - 1):
        for i in range(len(grid[0]) - 1):
            q = (grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i])
            out.append(0.5 * sum(q[k][0] * q[(k + 1) % 4][1] - q[(k + 1) % 4][0] * q[k][1] for k in range(4)))
    return out


# ---------------------------------------------------------------- polyMesh
def write_polymesh(case: Path, grid, nw: int, span: float = 0.1, farfield: str = "inletoutlet"):
    """Writes constant/polyMesh for the 2D grid, one cell thick in z, with patches
    airfoil (wall), inlet + outlet or farfield (patch), frontAndBack (empty)."""
    nj = len(grid) - 1
    NI = len(grid[0]) - 1
    npl = (NI + 1) * (nj + 1)

    def pid(i, j, k):
        if j == 0 and i >= NI - nw:            # upper wake line: same points as the lower wake line
            i = NI - i
        return k * npl + j * (NI + 1) + i

    def cid(i, j):
        return j * NI + i

    pts = [(x, y, 0.0) for row in grid for x, y in row] + [(x, y, span) for row in grid for x, y in row]
    cc = {}
    for j in range(nj):
        for i in range(NI):
            q = (grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i])
            cc[cid(i, j)] = (sum(p[0] for p in q) / 4, sum(p[1] for p in q) / 4, span / 2)

    def orient(face, toward):
        """Orders the face so its normal points toward `toward` (from the owner's side)."""
        P = [pts[v] for v in face]
        nx = ny = nz = 0.0
        for a, b in zip(P, P[1:] + P[:1]):
            nx += (a[1] - b[1]) * (a[2] + b[2])
            ny += (a[2] - b[2]) * (a[0] + b[0])
            nz += (a[0] - b[0]) * (a[1] + b[1])
        c = [sum(p[m] for p in P) / len(P) for m in range(3)]
        d = (toward[0] - c[0]) * nx + (toward[1] - c[1]) * ny + (toward[2] - c[2]) * nz
        return face if d > 0 else list(reversed(face))

    internal = []    # (owner, neighbour, face)
    for j in range(nj):
        for i in range(NI):
            c = cid(i, j)
            if i + 1 < NI:   # face on line i+1
                f = [pid(i + 1, j, 0), pid(i + 1, j + 1, 0), pid(i + 1, j + 1, 1), pid(i + 1, j, 1)]
                internal.append((c, cid(i + 1, j), f))
            if j + 1 < nj:   # face on line j+1
                f = [pid(i, j + 1, 0), pid(i + 1, j + 1, 0), pid(i + 1, j + 1, 1), pid(i, j + 1, 1)]
                internal.append((c, cid(i, j + 1), f))
    for i in range(nw):      # the wake cut
        f = [pid(i, 0, 0), pid(i + 1, 0, 0), pid(i + 1, 0, 1), pid(i, 0, 1)]
        internal.append((cid(i, 0), cid(NI - 1 - i, 0), f))
    internal.sort(key=lambda t: (t[0], t[1]))
    internal = [(o, n, orient(f, cc[n])) for o, n, f in internal]

    def outward(c, f):
        o = cc[c]
        P = [pts[v] for v in f]
        cf = [sum(p[m] for p in P) / len(P) for m in range(3)]
        return orient(f, (2 * cf[0] - o[0], 2 * cf[1] - o[1], 2 * cf[2] - o[2]))

    wall = [(cid(i, 0), [pid(i, 0, 0), pid(i + 1, 0, 0), pid(i + 1, 0, 1), pid(i, 0, 1)]) for i in range(nw, NI - nw)]
    far = [(cid(i, nj - 1), [pid(i, nj, 0), pid(i + 1, nj, 0), pid(i + 1, nj, 1), pid(i, nj, 1)]) for i in range(NI)]
    outl = [(cid(0, j), [pid(0, j, 0), pid(0, j + 1, 0), pid(0, j + 1, 1), pid(0, j, 1)]) for j in range(nj)]
    outl += [(cid(NI - 1, j), [pid(NI, j, 0), pid(NI, j + 1, 0), pid(NI, j + 1, 1), pid(NI, j, 1)]) for j in range(nj)]
    sides = []
    for j in range(nj):
        for i in range(NI):
            c = cid(i, j)
            sides.append((c, [pid(i, j, 0), pid(i + 1, j, 0), pid(i + 1, j + 1, 0), pid(i, j + 1, 0)]))
            sides.append((c, [pid(i, j, 1), pid(i + 1, j, 1), pid(i + 1, j + 1, 1), pid(i, j + 1, 1)]))

    patches = [("airfoil", "wall", wall)]
    if farfield == "freestream":
        patches.append(("farfield", "patch", far + outl))
    else:
        patches += [("inlet", "patch", far), ("outlet", "patch", outl)]
    patches.append(("frontAndBack", "empty", sides))

    faces = [f for _, _, f in internal]
    owner = [o for o, _, _ in internal]
    neigh = [n for _, n, _ in internal]
    bounds = []
    for name, typ, lst in patches:
        bounds.append((name, typ, len(faces), len(lst)))
        for c, f in lst:
            faces.append(outward(c, f))
            owner.append(c)

    # Drop the points the wake cut made unused, renumbering the rest.
    used = sorted({v for f in faces for v in f})
    remap = {v: k for k, v in enumerate(used)}
    pts = [pts[v] for v in used]
    faces = [[remap[v] for v in f] for f in faces]

    d = Path(case) / "constant" / "polyMesh"
    d.mkdir(parents=True, exist_ok=True)
    ncell = NI * nj
    note = f'note "nPoints:{len(pts)} nCells:{ncell} nFaces:{len(faces)} nInternalFaces:{len(internal)}";'

    def write(name, cls, body):
        hdr = HEADER.format(cls=cls, obj=name).replace("    object", f"    {note}\n    object") if name in ("owner", "neighbour") else HEADER.format(cls=cls, obj=name)
        (d / name).write_text(newline="\n", data=hdr + body)

    write("points", "vectorField", f"{len(pts)}\n(\n" + "\n".join(f"({x:.10g} {y:.10g} {z:.10g})" for x, y, z in pts) + "\n)\n")
    write("faces", "faceList", f"{len(faces)}\n(\n" + "\n".join(f"{len(f)}({' '.join(map(str, f))})" for f in faces) + "\n)\n")
    write("owner", "labelList", f"{len(owner)}\n(\n" + "\n".join(map(str, owner)) + "\n)\n")
    write("neighbour", "labelList", f"{len(neigh)}\n(\n" + "\n".join(map(str, neigh)) + "\n)\n")
    body = f"{len(bounds)}\n(\n"
    for name, typ, start, n in bounds:
        extra = "        inGroups        List<word> 1(wall);\n" if typ == "wall" else ""
        body += f"    {name}\n    {{\n        type            {typ};\n{extra}        nFaces          {n};\n        startFace       {start};\n    }}\n"
    write("boundary", "polyBoundaryMesh", body + ")\n")
    return {"cells": ncell, "points": len(pts), "faces": len(faces)}
