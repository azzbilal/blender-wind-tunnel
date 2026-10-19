"""Reads an OpenFOAM case's ASCII results and integrates the airfoil forces itself.

No function objects are needed, so this works with any OpenFOAM version: it sums
pressure and wall shear over the `airfoil` patch, face by face, as OpenFOAM's own
`forces` function object does. Pure Python (numpy optional), no Blender import.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

_NUM = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"


def _body(text: str) -> str:
    """Drops the FoamFile header and comments."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    i = text.find("FoamFile")
    if i >= 0:
        text = text[text.index("}", i) + 1:]
    return text


def _list_block(text: str, start: int = 0):
    """Finds `N ( ... )` from `start`; returns (N, inner text, end index)."""
    m = re.compile(r"(\d+)\s*\(").search(text, start)
    n, depth, i = int(m.group(1)), 1, m.end()
    while depth:
        c = text[i]
        depth += c == "("
        depth -= c == ")"
        i += 1
    return n, text[m.end():i - 1], i


def read_points(path: Path):
    n, inner, _ = _list_block(_body(path.read_text()))
    vals = [float(v) for v in re.findall(_NUM, inner)]
    return [tuple(vals[3 * k:3 * k + 3]) for k in range(n)]


def read_faces(path: Path):
    _, inner, _ = _list_block(_body(path.read_text()))
    return [[int(v) for v in grp.split()] for grp in re.findall(r"\d+\s*\(([^)]*)\)", inner)]


def read_labels(path: Path):
    _, inner, _ = _list_block(_body(path.read_text()))
    return [int(v) for v in inner.split()]


def read_boundary(path: Path):
    text = _body(path.read_text())
    out = {}
    for name, block in re.findall(r"(\w+)\s*\{([^{}]*)\}", text):
        sf = re.search(r"startFace\s+(\d+)", block)
        nf = re.search(r"nFaces\s+(\d+)", block)
        if sf and nf:
            out[name] = (int(sf.group(1)), int(nf.group(1)))
    return out


def _values(chunk: str, width: int):
    vals = [float(v) for v in re.findall(_NUM, chunk)]
    return vals if width == 1 else [tuple(vals[width * k:width * k + width]) for k in range(len(vals) // width)]


def read_internal(path: Path, width: int):
    """The internal field: a list of values, or a single uniform value repeated on demand (None, value)."""
    text = _body(path.read_text())
    m = re.search(r"internalField\s+uniform\s+(\([^)]*\)|" + _NUM + ")", text)
    if m:
        v = _values(m.group(1), width)
        return None, (v[0] if width > 1 else v[0])
    i = text.index("internalField")
    _, inner, _ = _list_block(text, i)
    return _values(inner, width), None


def read_patch_value(path: Path, patch: str, width: int):
    """A patch's `value` entry, or None when the patch writes none (zeroGradient)."""
    text = _body(path.read_text())
    m = re.search(patch + r"\s*\{", text)
    if not m:
        return None
    depth, i = 1, m.end()
    while depth:
        depth += text[i] == "{"
        depth -= text[i] == "}"
        i += 1
    block = text[m.end():i - 1]
    if "nonuniform" in block:
        _, inner, _ = _list_block(block, block.index("nonuniform"))
        return _values(inner, width)
    u = re.search(r"value\s+uniform\s+(\([^)]*\)|" + _NUM + ")", block)
    return ("uniform", _values(u.group(1), width)[0]) if u else None


# ---------------------------------------------------------------- vectors
def _sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def _dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _norm(a): return math.sqrt(_dot(a, a))


def _face_geom(face, pts):
    """Area vector (Newell) and centroid of a planar polygon."""
    c = (0.0, 0.0, 0.0)
    for k in face:
        c = _add(c, pts[k])
    c = _mul(c, 1.0 / len(face))
    s = (0.0, 0.0, 0.0)
    for i in range(len(face)):
        s = _add(s, _cross(pts[face[i]], pts[face[(i + 1) % len(face)]]))
    return _mul(s, 0.5), c


class Mesh:
    """The parts of the mesh the force sum needs: the patch faces and their owner cells' centres."""

    def __init__(self, case: Path, patch: str = "airfoil"):
        pm = Path(case) / "constant" / "polyMesh"
        self.pts = read_points(pm / "points")
        faces = read_faces(pm / "faces")
        owner = read_labels(pm / "owner")
        neigh = read_labels(pm / "neighbour")
        start, n = read_boundary(pm / "boundary")[patch]
        self.patch_faces = [faces[f] for f in range(start, start + n)]
        self.cells = [owner[f] for f in range(start, start + n)]
        wanted = set(self.cells)
        cell_faces = {c: [] for c in wanted}
        for f, c in enumerate(owner):
            if c in wanted:
                cell_faces[c].append(f)
        for f, c in enumerate(neigh):
            if c in wanted:
                cell_faces[c].append(f)
        self.cc = {}
        for c, fl in cell_faces.items():
            acc = (0.0, 0.0, 0.0)
            for f in fl:
                acc = _add(acc, _face_geom(faces[f], self.pts)[1])
            self.cc[c] = _mul(acc, 1.0 / len(fl))
        self.geom = [_face_geom(f, self.pts) for f in self.patch_faces]


def _cell_values(internal, uniform, cells):
    return [internal[c] for c in cells] if internal is not None else [uniform] * len(cells)


def coefficients(case: Path, time: str, mesh: Mesh, nu: float, alpha_deg: float,
                 span: float = 0.1, chord: float = 1.0, cofr=(0.25, 0.0, 0.0)):
    """Cl, Cd, Cm of the airfoil patch at one saved time (U = 1, rho = 1)."""
    d = Path(case) / time
    p_int, p_uni = read_internal(d / "p", 1)
    U_int, U_uni = read_internal(d / "U", 3)
    nut_w = read_patch_value(d / "nut", "airfoil", 1)
    p_c = _cell_values(p_int, p_uni, mesh.cells)
    U_c = _cell_values(U_int, U_uni, mesh.cells)
    if nut_w is None:
        nut_w = [0.0] * len(mesh.cells)
    elif isinstance(nut_w, tuple):
        nut_w = [nut_w[1]] * len(mesh.cells)

    F, M = (0.0, 0.0, 0.0), 0.0
    for i, (Sf, Cf) in enumerate(mesh.geom):
        A = _norm(Sf)
        n = _mul(Sf, 1.0 / A)
        f_p = _mul(Sf, p_c[i])                       # pressure: Sf points out of the fluid, into the body
        dn = abs(_dot(n, _sub(Cf, mesh.cc[mesh.cells[i]])))
        u = U_c[i]
        u_t = _sub(u, _mul(n, _dot(u, n)))           # tangential velocity of the wall cell (wall at rest)
        f_v = _mul(u_t, (nu + nut_w[i]) * A / dn)    # wall shear drags the body along the flow
        f = _add(f_p, f_v)
        F = _add(F, f)
        r = _sub(Cf, cofr)
        M += r[0] * f[1] - r[1] * f[0]
    a = math.radians(alpha_deg)
    lift, drag = (-math.sin(a), math.cos(a), 0.0), (math.cos(a), math.sin(a), 0.0)
    q = 0.5 * span * chord
    return {"Cl": _dot(F, lift) / q, "Cd": _dot(F, drag) / q, "Cm": -M / (q * chord)}


def wall_cp(case: Path, time: str, mesh: Mesh):
    """Pressure coefficient on every airfoil face, as (x, y, Cp) at the face centres (U = 1, rho = 1)."""
    p_int, p_uni = read_internal(Path(case) / time / "p", 1)
    p_c = _cell_values(p_int, p_uni, mesh.cells)
    return [(Cf[0], Cf[1], 2.0 * p) for (_, Cf), p in zip(mesh.geom, p_c)]


def saved_times(case: Path):
    out = []
    for p in Path(case).iterdir():
        try:
            if p.is_dir() and float(p.name) > 0 and (p / "U").exists():
                out.append(p.name)
        except ValueError:
            pass
    return sorted(out, key=float)


def residuals(log: Path):
    """Initial residual of p (first corrector) per iteration, and whether SIMPLE reported convergence."""
    text = Path(log).read_text(errors="replace")
    hist = []
    for block in re.split(r"\nTime = ", text)[1:]:
        m = re.search(r"Solving for p, Initial residual = (" + _NUM + ")", block)
        if m:
            hist.append(float(m.group(1)))
    finished = re.search(r"\nEnd\s*$", text) is not None
    return hist, "SIMPLE solution converged" in text, "FOAM FATAL" in text or not finished


def analyse(case: Path, nu: float, alpha_deg: float, mesh: Mesh | None = None, last: int | None = None):
    """Coefficients at the saved times (all, or the `last` few), the residual drop, and a convergence
    verdict with its reasons."""
    mesh = mesh or Mesh(case)
    times = saved_times(case)
    if last:
        times = times[-last:]
    hist = [(float(t), coefficients(case, t, mesh, nu, alpha_deg)) for t in times]
    res, simple_conv, crashed = residuals(Path(case) / "log.simpleFoam") if (Path(case) / "log.simpleFoam").exists() else ([], False, False)
    drop = math.log10(max(res[:20]) / res[-1]) if len(res) > 20 and res[-1] > 0 else 0.0
    reasons = []
    if crashed:
        reasons.append("solver stopped with an error, or has not finished")
    if drop < 2 and not simple_conv:
        reasons.append(f"pressure residual fell only {drop:.1f} orders (want 2)")
    if len(hist) >= 2:
        (_, c0), (_, c1) = hist[-2], hist[-1]
        dcl, dcd = abs(c1["Cl"] - c0["Cl"]), abs(c1["Cd"] - c0["Cd"])
        if dcl > max(0.002 * abs(c1["Cl"]), 0.001):
            reasons.append(f"lift still moving ({dcl:.4f} between the last two saves)")
        if dcd > 0.01 * abs(c1["Cd"]):
            reasons.append(f"drag still moving ({dcd:.5f} between the last two saves)")
    else:
        reasons.append("fewer than two saved results")
    final = hist[-1][1] if hist else None
    return {"alpha": alpha_deg, "final": final, "history": hist, "residual_drop": drop,
            "converged": not reasons, "reasons": reasons}


def progress(case: Path):
    """(iteration, latest pressure residual) from the end of a running solver's log, or (0, None)."""
    log = Path(case) / "log.simpleFoam"
    if not log.exists():
        return 0, None
    with open(log, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 8000))
        tail = f.read().decode("utf-8", "replace")
    its = re.findall(r"\nTime = (\d+)", tail)
    res = re.findall(r"Solving for p, Initial residual = (" + _NUM + ")", tail)
    return (int(its[-1]) if its else 0), (float(res[-1]) if res else None)


# NASA Turbulence Modeling Resource, NACA 0012 at Re 6e6, SST model (CFL3D, finest grid).
NASA_0012_SST = {0.0: (0.0, 0.00809), 10.0: (1.0778, 0.01236), 15.0: (1.5068, 0.02219)}
