"""Writes OpenFOAM cases for a 2D NACA 4-digit airfoil (simpleFoam, k-omega SST).

Pure Python, no Blender import: the add-on calls it, and it runs on its own for tests.
Tested with OpenFOAM v1912 (Ubuntu package `openfoam`); any openfoam.com version should do.

Layout of a sweep folder:
    <root>/mesh/              the C-grid (written by meshgen, checked by checkMesh)
    <root>/a+05.00/           one simpleFoam case per angle, sharing the mesh
The angle of attack turns the freestream, not the airfoil, so one mesh serves the sweep.
"""
from __future__ import annotations

import math
import shutil
from dataclasses import dataclass
from pathlib import Path

from . import meshgen

HEADER = """FoamFile
{{
    version     2.0;
    format      ascii;
    class       {cls};
    object      {obj};
}}
"""


@dataclass
class Setup:
    naca: str = "0012"        # 4-digit code
    reynolds: float = 6.0e6   # based on chord, U = 1, c = 1
    radius: float = 20.0      # far-field radius in chords, centred on the trailing edge
    wake: float = 20.0        # wake length behind the trailing edge, in chords
    n_surface: int = 100      # cells per side of the profile, leading edge to trailing edge
    n_wake: int = 60          # cells along the wake
    n_normal: int = 80        # cells, wall to far field
    y_plus: float = 50.0      # target y+ of the first wall cell (wall-function range)
    le_cell: float = 0.002    # surface cell length at the leading edge, in chords
    te_cell: float = 0.004    # surface cell length at the trailing edge, in chords
    iterations: int = 3000
    span: float = 0.1         # thickness of the 2D slab (one cell)
    write_every: int = 250    # iterations between saved results (the lift history is rebuilt from them)
    farfield: str = "inletoutlet"  # "inletoutlet": fixed velocity in, fixed pressure out; "freestream": OpenFOAM's switching pair

    @property
    def nu(self) -> float:
        return 1.0 / self.reynolds

    @property
    def first_cell(self) -> float:
        """Wall-normal height of the first cell for the target y+ (flat-plate skin friction estimate)."""
        cf = 0.026 / self.reynolds ** (1 / 7)
        return self.y_plus / (math.sqrt(cf / 2) * self.reynolds)


# ---------------------------------------------------------------- geometry
def naca4(code: str, n: int = 120):
    """Upper and lower surface points, leading edge to trailing edge, closed trailing edge."""
    m, p, t = int(code[0]) / 100, int(code[1]) / 10, int(code[2:]) / 100
    up, lo = [], []
    for k in range(n + 1):
        x = (1 - math.cos(math.pi * k / n)) / 2
        yt = 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
        if m == 0 or p == 0:
            yc, dyc = 0.0, 0.0
        elif x < p:
            yc, dyc = m / p**2 * (2 * p * x - x * x), 2 * m / p**2 * (p - x)
        else:
            yc, dyc = m / (1 - p) ** 2 * ((1 - 2 * p) + 2 * p * x - x * x), 2 * m / (1 - p) ** 2 * (p - x)
        th = math.atan(dyc)
        up.append((x - yt * math.sin(th), yc + yt * math.cos(th)))
        lo.append((x + yt * math.sin(th), yc - yt * math.cos(th)))
    up[0] = lo[0] = (0.0, 0.0)
    up[-1] = lo[-1] = (1.0, 0.0)
    return up, lo


def _fmt(v):
    return "(" + " ".join(f"{c:.8g}" for c in v) + ")"


def write_mesh(case: Path, s: Setup, profile=None):
    """Builds the C-grid round the profile (default: the NACA section) into case/constant/polyMesh."""
    up, lo = profile or naca4(s.naca, 400)
    grid, nw, _ = meshgen.c_grid(up, lo, ns=s.n_surface, nw=s.n_wake, nj=s.n_normal, radius=s.radius,
                                 wake=s.wake, first_cell=s.first_cell, le_cell=s.le_cell, te_cell=s.te_cell)
    bad = sum(a <= 0 for a in meshgen.cell_areas(grid))
    if bad:
        raise ValueError(f"{bad} folded cells in the grid; try fewer surface cells or a smoother profile")
    return meshgen.write_polymesh(case, grid, nw, s.span, s.farfield)


# ---------------------------------------------------------------- case files
def _field(name, dims, internal, farfield, wall, cls="volScalarField"):
    return (HEADER.format(cls=cls, obj=name) +
            f"dimensions      {dims};\ninternalField   {internal};\n\nboundaryField\n{{\n"
            + "".join(f"    {n}\n    {{\n{bc}\n    }}\n" for n, bc in farfield.items())
            + f"    airfoil\n    {{\n{wall}\n    }}\n"
            f"    frontAndBack\n    {{\n        type empty;\n    }}\n}}\n")


def turbulence_inlet(s: Setup):
    """Freestream k and omega: 0.08 % turbulence intensity and omega = 5 U/c (Menter's far-field range, 1 to 10)."""
    k = 1.5 * (0.0008 * 1.0) ** 2
    om = 5.0
    return k, om, k / om


def write_fields(case: Path, s: Setup, alpha_deg: float):
    a = math.radians(alpha_deg)
    U = (math.cos(a), math.sin(a), 0.0)
    k, om, nut = turbulence_inlet(s)
    zero = case / "0"
    zero.mkdir(parents=True, exist_ok=True)
    io = "        type            inletOutlet;\n        inletValue      $internalField;\n        value           $internalField;"
    calc = "        type            calculated;\n        value           $internalField;"
    if s.farfield == "freestream":
        fs = "        type            freestream{kind};\n        freestreamValue $internalField;"
        bU, bp = {"farfield": fs.format(kind="Velocity")}, {"farfield": fs.format(kind="Pressure")}
        bt, bnut = {"farfield": io}, {"farfield": calc}
    else:
        bU = {"inlet": "        type            fixedValue;\n        value           $internalField;",
              "outlet": "        type            pressureInletOutletVelocity;\n        value           $internalField;"}
        bp = {"inlet": "        type            zeroGradient;",
              "outlet": "        type            fixedValue;\n        value           $internalField;"}
        bt = {"inlet": "        type            fixedValue;\n        value           $internalField;", "outlet": io}
        bnut = {"inlet": calc, "outlet": calc}

    def put(name, text):
        (zero / name).write_text(newline="\n", data=text)

    put("U", _field("U", "[0 1 -1 0 0 0 0]", f"uniform {_fmt(U)}", bU, "        type            noSlip;", "volVectorField"))
    put("p", _field("p", "[0 2 -2 0 0 0 0]", "uniform 0", bp, "        type            zeroGradient;"))
    put("k", _field("k", "[0 2 -2 0 0 0 0]", f"uniform {k:.6g}", bt,
                    "        type            kqRWallFunction;\n        value           $internalField;"))
    put("omega", _field("omega", "[0 0 -1 0 0 0 0]", f"uniform {om:.6g}", bt,
                        "        type            omegaWallFunction;\n        value           $internalField;"))
    put("nut", _field("nut", "[0 2 -1 0 0 0 0]", f"uniform {nut:.6g}", bnut,
                      "        type            nutUSpaldingWallFunction;\n        value           uniform 0;"))


def write_system(case: Path, s: Setup, alpha_deg: float):
    sysd, con = case / "system", case / "constant"
    sysd.mkdir(parents=True, exist_ok=True)
    con.mkdir(parents=True, exist_ok=True)
    (con / "transportProperties").write_text(newline="\n", data=HEADER.format(cls="dictionary", obj="transportProperties") +
                                             f"transportModel  Newtonian;\nnu              {s.nu:.8g};\n")
    (con / "turbulenceProperties").write_text(newline="\n", data=HEADER.format(cls="dictionary", obj="turbulenceProperties") +
                                              "simulationType  RAS;\nRAS\n{\n    RASModel        kOmegaSST;\n    turbulence      on;\n    printCoeffs     on;\n}\n")
    (sysd / "controlDict").write_text(newline="\n", data=HEADER.format(cls="dictionary", obj="controlDict") + f"""application     simpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {s.iterations};
deltaT          1;
writeControl    timeStep;
writeInterval   {s.write_every};
purgeWrite      0;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

""")
    (sysd / "fvSchemes").write_text(newline="\n", data=HEADER.format(cls="dictionary", obj="fvSchemes") + """ddtSchemes      { default steadyState; }
gradSchemes     { default cellLimited Gauss linear 1; }
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,omega)  bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear limited corrected 0.5; }
interpolationSchemes { default linear; }
snGradSchemes   { default limited corrected 0.5; }
wallDist        { method meshWave; }
""")
    (sysd / "fvSolution").write_text(newline="\n", data=HEADER.format(cls="dictionary", obj="fvSolution") + """solvers
{
    p
    {
        solver          GAMG;
        tolerance       1e-07;
        relTol          0.05;
        smoother        GaussSeidel;
    }
    "(U|k|omega)"
    {
        solver          smoothSolver;
        smoother        GaussSeidel;
        nSweeps         2;
        tolerance       1e-08;
        relTol          0.1;
    }
}
SIMPLE
{
    nNonOrthogonalCorrectors 1;
    consistent      no;
    residualControl
    {
        p               1e-6;
        U               1e-7;
        "(k|omega)"     1e-7;
    }
}
relaxationFactors
{
    fields
    {
        p               0.3;
    }
    equations
    {
        U               0.7;
        "(k|omega)"     0.5;
    }
}
""")


# Finds OpenFOAM's environment script: the newest openfoam.com build first, then other layouts.
ENV = ('for f in $(ls -d /usr/lib/openfoam/openfoam*/etc/bashrc /opt/openfoam*/etc/bashrc 2>/dev/null | sort -V | tail -1) '
       '/usr/share/openfoam/etc/bashrc; do [ -f "$f" ] && . "$f" > /dev/null 2>&1 && break; done')


def write_sweep(root: Path, s: Setup, alphas, parallel: bool = True, profile=None):
    """Writes the mesh and one case per angle, plus the `Allrun` script that checks the mesh and runs them.

    Progress is left in plain files the caller can poll: `status` at the root (checking, running, done,
    failed), and `exit` in each case once its solver has stopped.
    """
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    mesh = root / "mesh"
    write_system(mesh, s, 0.0)
    stats = write_mesh(mesh, s, profile)
    names = []
    for a in alphas:
        name = case_name(a)
        write_system(root / name, s, a)
        write_fields(root / name, s, a)
        names.append(name)
    amp = " &" if parallel else ""
    lines = ["#!/bin/bash", ENV, "cd \"$(dirname \"$0\")\"",
             "echo checking > status",
             "(cd mesh && checkMesh > log.checkMesh 2>&1) || true",
             "echo running > status"]
    for n in names:
        lines += [f"mkdir -p {n}/constant && cp -r mesh/constant/polyMesh {n}/constant/",
                  f"(cd {n} && simpleFoam > log.simpleFoam 2>&1; echo $? > exit){amp}"]
    lines += ["wait", "echo done > status"]
    script = root / "Allrun"
    script.write_text(newline="\n", data="\n".join(lines) + "\n")
    try:
        script.chmod(0o755)
    except OSError:
        pass
    return script, stats


def case_name(alpha: float) -> str:
    return f"a{alpha:+06.2f}"
