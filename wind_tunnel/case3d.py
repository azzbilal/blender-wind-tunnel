"""A 3D virtual wind tunnel around any closed surface (an STL exported from Blender).

snappyHexMesh cuts the body out of a box of air and refines around it; simpleFoam (k-omega SST)
solves the steady flow in parallel; export_field.py (run inside WSL right after) turns the result
into a regular velocity/pressure grid and the forces. Pure Python, no Blender import.

Units: metres, m/s. The wind blows along +X. Sizes scale with L, the body's largest dimension.
"""
from __future__ import annotations

import math
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

from .case import ENV, HEADER


@dataclass
class Setup3D:
    speed: float = 20.0           # wind speed, m/s, along +X
    nu: float = 1.5e-5            # air kinematic viscosity, m2/s
    rho: float = 1.225            # air density, kg/m3 (forces only)
    ground: bool = False          # True: a moving road under the body (cars); False: free air
    cells_per_L: int = 6          # background cells across L
    surface_levels: tuple = (4, 4)  # refinement on the body: each level halves the cell; the body gets lo2
    wake_level: int = 2           # refinement in the box around and behind the body
    layers: int | None = None     # prism layers on the body; None: from the y+ target (layer_sizing), 0: none
    y_plus: float = 100.0         # target y+ of the first cell centre (docs/reference/step3_wall_spec.md)
    u_tau: float | None = None    # friction velocity for the sizing, m/s; None: the measured anchor
    iterations: int = 3000        # cap; the convergence gate (convergence.py) normally stops earlier
    write_every: int = 100
    procs: int = 8
    voxels_per_L: int = 40        # resolution of the grid handed to Blender


# Add-on mesh presets: (body surface levels, wake level, background cells across L). The body is refined
# uniformly to lo2 (docs/reference/step3_wall_spec.md amendment D1, was (2 3) and (3 4)).
PRESETS = {"COARSE": ((3, 3), 2, 6), "MEDIUM": ((4, 4), 2, 8)}


# ---------------------------------------------------------------- STL
def read_stl(path: Path):
    """Triangles of an ASCII or binary STL: list of ((x,y,z),(x,y,z),(x,y,z))."""
    data = Path(path).read_bytes()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        tris, cur = [], []
        for line in data.decode(errors="replace").splitlines():
            parts = line.split()
            if parts[:1] == ["vertex"]:
                cur.append(tuple(float(v) for v in parts[1:4]))
                if len(cur) == 3:
                    tris.append(tuple(cur))
                    cur = []
        return tris
    n = struct.unpack("<I", data[80:84])[0]
    tris = []
    for k in range(n):
        v = struct.unpack("<12f", data[84 + 50 * k: 84 + 50 * k + 48])
        tris.append((v[3:6], v[6:9], v[9:12]))
    return tris


def write_stl(path: Path, tris, name="body"):
    """Binary STL."""
    out = bytearray(name.encode()[:80].ljust(80, b" "))
    out += struct.pack("<I", len(tris))
    for a, b, c in tris:
        u = [b[i] - a[i] for i in range(3)]
        v = [c[i] - a[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        out += struct.pack("<12fH", *n, *a, *b, *c, 0)
    Path(path).write_bytes(bytes(out))


def bounds(tris):
    xs = [p[0] for t in tris for p in t]
    ys = [p[1] for t in tris for p in t]
    zs = [p[2] for t in tris for p in t]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


# ---------------------------------------------------------------- geometry of the tunnel
def tunnel(lo, hi, s: Setup3D):
    """Domain box, wake box and the background cell counts, all from the body's bounding box."""
    L = max(hi[i] - lo[i] for i in range(3))
    h = L / s.cells_per_L
    cy, cz = (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2
    x0, x1 = lo[0] - 3 * L, hi[0] + 7 * L
    y0, y1 = cy - 3 * L, cy + 3 * L
    z0 = min(lo[2], 0.0) if s.ground else cz - 3 * L      # the road is Blender's ground (z = 0)
    z1 = (hi[2] + 4 * L) if s.ground else cz + 3 * L
    n = [max(4, round((b - a) / h)) for a, b in ((x0, x1), (y0, y1), (z0, z1))]
    m = 0.5 * L
    wake = ((lo[0] - m, lo[1] - m, max(lo[2] - m, z0)), (hi[0] + 3 * L, hi[1] + m, hi[2] + m))
    return {"L": L, "box": ((x0, y0, z0), (x1, y1, z1)), "n": n, "wake": wake}


def _v(p):
    return "(" + " ".join(f"{c:.8g}" for c in p) + ")"


def block_mesh_dict(t, ground: bool):
    (x0, y0, z0), (x1, y1, z1) = t["box"]
    nx, ny, nz = t["n"]
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    return HEADER.format(cls="dictionary", obj="blockMeshDict") + f"""convertToMeters 1;
vertices
(
{chr(10).join('    ' + _v(p) for p in v)}
);
blocks ( hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1) );
edges ();
boundary
(
    inlet  {{ type patch; faces ((0 4 7 3)); }}
    outlet {{ type patch; faces ((1 2 6 5)); }}
    sides  {{ type patch; faces ((0 1 5 4) (3 7 6 2)); }}
    top    {{ type patch; faces ((4 5 6 7)); }}
    ground {{ type {"wall" if ground else "patch"}; faces ((0 3 2 1)); }}
);
mergePatchPairs ();
"""


# Area-weighted mean u_tau / U on the sphere (Re_L 2.67e6), FIX_PLAN step 3 Stage 1
# (validation/step3_wall_v2512.json); the Re^(-1/14) flat-plate shape carries it to other U and L.
U_TAU_ANCHOR, RE_ANCHOR, EXPANSION = 0.0386, 20.0 * 2.0 / 1.5e-5, 1.3     # Re of that run, 2.67e6


def layer_sizing(L: float, s: Setup3D):
    """Prism layers from a target y+ (docs/reference/step3_wall_spec.md), all lengths in metres.

    y_c is the first cell-centre distance: OpenFOAM's yPlus uses nearWallDist (half the first layer),
    so the first layer is h1 = 2 y_c. n is the smaller of the half-cell rule (last layer about half the
    surface cell Delta) and the one-cell stack cap (total thickness <= Delta)."""
    re_L = s.speed * L / s.nu
    u_tau = s.u_tau or U_TAU_ANCHOR * s.speed * (re_L / RE_ANCHOR) ** (-1 / 14)
    y_c = s.y_plus * s.nu / u_tau
    h1 = 2 * y_c
    delta = L / s.cells_per_L / 2 ** s.surface_levels[1]
    r = EXPANSION
    n_half = math.ceil(1 + math.log(delta / (2 * h1)) / math.log(r))
    n_depth = math.floor(math.log(1 + delta * (r - 1) / h1) / math.log(r))
    n = max(1, min(n_half, n_depth)) if s.layers is None else s.layers
    return {"u_tau_ref": u_tau, "y_c": y_c, "h1": h1, "delta": delta, "n_half": n_half, "n_depth": n_depth,
            "n": n, "min_thickness": 0.5 * h1, "expansion": r}


def snappy_dict(t, s: Setup3D):
    (w0, w1), L = t["wake"], t["L"]
    (x0, y0, z0), _ = t["box"]
    # A point in the air, well upstream, off every background face.
    loc = (x0 + 1.37 * L + 0.0123 * L, (t["box"][0][1] + t["box"][1][1]) / 2 + 0.0137 * L,
           (z0 + t["box"][1][2]) / 2 + 0.0111 * L if not s.ground else z0 + 2.21 * L + 0.0111 * L)
    lo2 = s.surface_levels[1]       # uniform body level (spec amendment D1): mixed levels cut layers
    w = layer_sizing(L, s)
    return HEADER.format(cls="dictionary", obj="snappyHexMeshDict") + f"""castellatedMesh true;
snap            true;
addLayers       {'true' if w['n'] else 'false'};

geometry
{{
    body.stl {{ type triSurfaceMesh; name body; }}
    wakeBox  {{ type searchableBox; min {_v(w0)}; max {_v(w1)}; }}
}}

castellatedMeshControls
{{
    maxLocalCells       1000000;
    maxGlobalCells      4000000;
    minRefinementCells  10;
    maxLoadUnbalance    0.10;
    nCellsBetweenLevels 3;
    features ( {{ file "body.eMesh"; level {lo2}; }} );
    refinementSurfaces
    {{
        body {{ level ({lo2} {lo2}); patchInfo {{ type wall; }} }}
    }}
    resolveFeatureAngle 30;
    refinementRegions
    {{
        wakeBox {{ mode inside; levels ((1e15 {s.wake_level})); }}
    }}
    locationInMesh {_v(loc)};
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch 3;
    tolerance 2.0;
    nSolveIter 30;
    nRelaxIter 5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes false;
    layers {{ body {{ nSurfaceLayers {w['n']}; }} }}
    thicknessModel firstAndExpansion;
    firstLayerThickness {w['h1']:.6g};
    expansionRatio {w['expansion']:g};
    minThickness {w['min_thickness']:.6g};
    nGrow 0;
    featureAngle 60;
    slipFeatureAngle 30;
    nRelaxIter 3;
    nSmoothSurfaceNormals 1;
    nSmoothNormals 3;
    nSmoothThickness 10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedialAxisAngle 90;
    nBufferCellsNoExtrude 0;
    nLayerIter 50;
}}

meshQualityControls
{{
    maxNonOrtho 65;
    maxBoundarySkewness 20;
    maxInternalSkewness 4;
    maxConcave 80;
    minVol 1e-13;
    minTetQuality 1e-15;
    minArea -1;
    minTwist 0.02;
    minDeterminant 0.001;
    minFaceWeight 0.05;
    minVolRatio 0.01;
    minTriangleTwist -1;
    nSmoothScale 4;
    errorReduction 0.75;
}}

mergeTolerance 1e-6;
"""


FEATURES = HEADER.format(cls="dictionary", obj="surfaceFeatureExtractDict") + """body.stl
{
    extractionMethod    extractFromSurface;
    includedAngle       150;
    subsetFeatures { nonManifoldEdges no; openEdges yes; }
    writeObj            no;
}
"""


def _field(name, cls, dims, internal, bcs):
    body = "".join(f"    {p}\n    {{\n{bc}\n    }}\n" for p, bc in bcs.items())
    return (HEADER.format(cls=cls, obj=name) + f"dimensions      {dims};\ninternalField   {internal};\n\n"
            "boundaryField\n{\n    #includeEtc \"caseDicts/setConstraintTypes\"\n" + body + "}\n")


def write_fields(zero: Path, s: Setup3D, L: float):
    zero.mkdir(parents=True, exist_ok=True)
    U = (s.speed, 0.0, 0.0)
    k = 1.5 * (0.01 * s.speed) ** 2                 # 1 % turbulence intensity
    om = k / (10 * s.nu)                            # eddy viscosity ratio 10
    fixed = "        type            fixedValue;\n        value           $internalField;"
    io = "        type            inletOutlet;\n        inletValue      $internalField;\n        value           $internalField;"
    slip = "        type            slip;"
    zg = "        type            zeroGradient;"
    road = (f"        type            fixedValue;\n        value           uniform {_v(U)};" if s.ground
            else slip)
    bottom = lambda wall, free: wall if s.ground else free
    put = lambda n, txt: (zero / n).write_text(newline="\n", data=txt)
    put("U", _field("U", "volVectorField", "[0 1 -1 0 0 0 0]", f"uniform {_v(U)}", {
        "inlet": fixed, "outlet": io.replace("inletValue      $internalField", "inletValue      uniform (0 0 0)"),
        "sides": slip, "top": slip, "ground": road, "body": "        type            noSlip;"}))
    put("p", _field("p", "volScalarField", "[0 2 -2 0 0 0 0]", "uniform 0", {
        "inlet": zg, "outlet": "        type            fixedValue;\n        value           uniform 0;",
        "sides": slip, "top": slip, "ground": bottom(zg, slip), "body": zg}))
    kw = "        type            kqRWallFunction;\n        value           $internalField;"
    ow = "        type            omegaWallFunction;\n        value           $internalField;"
    nw = "        type            nutUSpaldingWallFunction;\n        value           uniform 0;"
    calc = "        type            calculated;\n        value           $internalField;"
    put("k", _field("k", "volScalarField", "[0 2 -2 0 0 0 0]", f"uniform {k:.6g}", {
        "inlet": fixed, "outlet": io, "sides": slip, "top": slip, "ground": bottom(kw, slip), "body": kw}))
    put("omega", _field("omega", "volScalarField", "[0 0 -1 0 0 0 0]", f"uniform {om:.6g}", {
        "inlet": fixed, "outlet": io, "sides": slip, "top": slip, "ground": bottom(ow, slip), "body": ow}))
    put("nut", _field("nut", "volScalarField", "[0 2 -1 0 0 0 0]", "uniform 0", {
        "inlet": calc, "outlet": calc, "sides": calc, "top": calc, "ground": bottom(nw, calc), "body": nw}))


def split3(n: int):
    """n = a * b * c with a >= b >= c, as even as possible (a along the wind)."""
    best = (n, 1, 1)
    for b in range(1, n + 1):
        for c in range(1, b + 1):
            if n % (b * c) == 0 and n // (b * c) >= b:
                a = n // (b * c)
                if a / c < best[0] / best[2]:
                    best = (a, b, c)
    return best


# Spatial schemes of the steady solve. The transient case (write_transient_case) uses the same text with
# a backward time derivative and without the steady-only `bounded` prefix (spec Q3), so Cd compares
# like-for-like.
FV_SCHEMES = """ddtSchemes { default steadyState; }
gradSchemes
{
    default         Gauss linear;
    grad(U)         cellLimited Gauss linear 1;
}
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwindV grad(U);
    div(phi,k)      bounded Gauss upwind;
    div(phi,omega)  bounded Gauss upwind;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
    div(div(phi,U)) Gauss linear;
}
laplacianSchemes { default Gauss linear limited corrected 0.5; }
interpolationSchemes { default linear; }
snGradSchemes { default limited corrected 0.5; }
wallDist { method meshWave; }
"""


def write_system(case: Path, s: Setup3D):
    sysd, con = case / "system", case / "constant"
    sysd.mkdir(parents=True, exist_ok=True)
    con.mkdir(parents=True, exist_ok=True)
    w = lambda p, cls, obj, body: p.write_text(newline="\n", data=HEADER.format(cls=cls, obj=obj) + body)
    w(con / "transportProperties", "dictionary", "transportProperties", f"transportModel Newtonian;\nnu {s.nu:.8g};\n")
    w(con / "turbulenceProperties", "dictionary", "turbulenceProperties",
      "simulationType RAS;\nRAS\n{\n    RASModel kOmegaSST;\n    turbulence on;\n    printCoeffs on;\n}\n")
    w(sysd / "controlDict", "dictionary", "controlDict", f"""application     simpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {s.iterations};
deltaT          1;
writeControl    timeStep;
writeInterval   {s.write_every};
purgeWrite      2;
writeFormat     ascii;
writePrecision  7;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

// Convergence gate (FIX_PLAN step 2, docs/reference/step2_convergence_reference.md): forces and the
// p residual every iteration; convergence.py checks them every 5 and writes wt_stop on a pass.
functions
{{
    forces {{ type forces; libs (forces); patches (body); rho rhoInf; rhoInf {s.rho:.8g}; CofR (0 0 0);
             writeControl timeStep; writeInterval 1; log off; }}
    solverInfo {{ type solverInfo; libs (utilityFunctionObjects); fields (p); writeResidualFields no;
                 writeControl timeStep; writeInterval 1; }}
    gate {{ type systemCall; libs (utilityFunctionObjects); master yes; executeControl timeStep;
           executeInterval 5; writeControl none; executeCalls ("python3 convergence.py . --trigger"); }}
    stop {{ type abort; libs (utilityFunctionObjects); file "wt_stop"; action writeNow; }}
}}
""")
    w(sysd / "fvSchemes", "dictionary", "fvSchemes", FV_SCHEMES)
    w(sysd / "fvSolution", "dictionary", "fvSolution", """solvers
{
    p     { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.05; }
    Phi   { $p; relTol 0.01; }
    "(U|k|omega)" { solver smoothSolver; smoother GaussSeidel; tolerance 1e-8; relTol 0.1; nSweeps 1; }
}
SIMPLE
{
    nNonOrthogonalCorrectors 1;
    consistent yes;
}
potentialFlow { nNonOrthogonalCorrectors 5; }
relaxationFactors
{
    fields { p 0.5; }
    equations { U 0.7; "(k|omega)" 0.6; }
}
""")
    nx, ny, nz = split3(s.procs)
    # scotch balances the pieces on the mesh graph. Allrun falls back to the geometric split (most
    # pieces along the wind) on a build without libscotchDecomp, such as Ubuntu's own package.
    w(sysd / "decomposeParDict", "dictionary", "decomposeParDict",
      f"numberOfSubdomains {s.procs};\nmethod scotch;\n"
      f"hierarchicalCoeffs {{ n ({nx} {ny} {nz}); order xyz; }}\n")


def write_case(root: Path, stl_tris, s: Setup3D, exporter: Path | None = None):
    """Writes the whole case into `root` and returns (Allrun path, tunnel info)."""
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    lo, hi = bounds(stl_tris)
    t = tunnel(lo, hi, s)
    write_system(root, s)
    tri = root / "constant" / "triSurface"
    tri.mkdir(parents=True, exist_ok=True)
    write_stl(tri / "body.stl", stl_tris)
    (root / "system" / "blockMeshDict").write_text(newline="\n", data=block_mesh_dict(t, s.ground))
    (root / "system" / "snappyHexMeshDict").write_text(newline="\n", data=snappy_dict(t, s))
    (root / "system" / "surfaceFeatureExtractDict").write_text(newline="\n", data=FEATURES)
    write_fields(root / "0.orig", s, t["L"])
    if exporter:
        shutil.copy(exporter, root / "export_field.py")
    for helper in ("convergence.py", "transient.py"):      # export_field.py imports both
        shutil.copy(Path(__file__).with_name(helper), root / helper)
    vox = t["L"] / s.voxels_per_L
    w = layer_sizing(t["L"], s)
    exp_args = (f"--speed {s.speed} --rho {s.rho} --nu {s.nu} --voxel {vox:.6g} --L {t['L']:.6g} "
                f"--cap {s.iterations} --u-tau-ref {w['u_tau_ref']:.6g} --y-c {w['y_c']:.6g}")
    np_ = s.procs
    mpi = f"mpirun -np {np_} --oversubscribe"
    lines = [
        "#!/bin/bash", ENV,
        "export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 OMPI_MCA_btl_vader_single_copy_mechanism=none",
        "cd \"$(dirname \"$0\")\"",
        "fail() { echo \"failed $1\" > status; exit 1; }",
        # systemCall (the convergence gate) is fatal as root (systemCall.C:123)
        "[ \"$(id -u)\" != 0 ] || fail \"as root: the convergence gate cannot run as root; set a normal default user in WSL\"",
        "echo meshing > status",
        "surfaceFeatureExtract > log.surfaceFeatureExtract 2>&1 || fail surfaceFeatureExtract",
        "blockMesh > log.blockMesh 2>&1 || fail blockMesh",
        "[ -e \"$FOAM_LIBBIN/libscotchDecomp.so\" ] || foamDictionary -entry method -set hierarchical "
        "system/decomposeParDict > /dev/null 2>&1 || fail decomposeParDict",
        "decomposePar -force > log.decomposePar 2>&1 || fail decomposePar",
        f"{mpi} snappyHexMesh -overwrite -parallel > log.snappyHexMesh 2>&1 || fail snappyHexMesh",
        "for d in processor*; do rm -rf \"${d:?}/0\"; cp -r 0.orig \"$d/0\"; done",
        f"{mpi} checkMesh -parallel -constant > log.checkMesh 2>&1 || true",
        "echo solving > status",
        "rm -f wt_stop",
        f"{mpi} simpleFoam -parallel > log.simpleFoam 2>&1 || fail simpleFoam",
        "echo exporting > status",
        "reconstructParMesh -constant > log.reconstructParMesh 2>&1 || fail reconstructParMesh",
        "reconstructPar -latestTime > log.reconstructPar 2>&1 || fail reconstructPar",
        # y+ of the first cell centres (yPlus FO, nearWallDist); export_field reports it, a failure only
        # leaves y+ unmeasured
        "simpleFoam -postProcess -func yPlus -latestTime > log.yPlus 2>&1 || true",
        f"python3 export_field.py . {exp_args} > log.export 2>&1 || fail export",
        "echo done > status",
    ]
    script = root / "Allrun"
    script.write_text(newline="\n", data="\n".join(lines) + "\n")
    try:
        script.chmod(0o755)
    except OSError:
        pass
    return script, t


# ---------------------------------------------------------------- transient (TRANSIENT T1)
@dataclass
class Transient:
    """pimpleFoam on the mesh of a solved steady case (docs/reference/transient_t1_spec.md)."""
    end_time: float = 2.0         # s, 20 flow-throughs L/U for the 2 m cube at 20 m/s
    frames_per_s: int = 60        # U and p written every 1/60 s: frame k at t = k / 60 s
    max_co: float = 1.0           # Courant target of the adjustable time step
    n_outer: int = 1              # PIMPLE outer correctors (1 = PISO mode)
    n_corr: int = 2               # pressure correctors per outer corrector
    full_write: float = 0.5       # s between full writes of every field (restart points)
    procs: int = 24               # must match the decomposition of the source case
    steps: int | None = None      # cost test: stop after this many time steps and do not export


def transient_control_dict(s: Setup3D, tr: Transient, L: float, Aref: float) -> str:
    if tr.steps:
        stop, wctl, wint = "nextWrite", "timeStep", f"{tr.steps}"
    else:
        stop, wctl, wint = "endTime", "adjustableRunTime", f"{tr.full_write:g}"
    # writeObjects with adjustableRunTime shortens deltaT to land on its write times (v2512,
    # timeControlFunctionObject.C:560), so every frame is written at exactly k / frames_per_s.
    return f"""application     pimpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          {stop};
endTime         {tr.end_time:g};
deltaT          0.001;
writeControl    {wctl};
writeInterval   {wint};
purgeWrite      0;
writeFormat     ascii;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   8;
runTimeModifiable false;
adjustTimeStep  yes;
maxCo           {tr.max_co:g};
maxDeltaT       1;

functions
{{
    frames
    {{
        type writeObjects;
        libs (utilityFunctionObjects);
        objects (U p);
        writeOption anyWrite;
        writeControl adjustableRunTime;
        writeInterval {1.0 / tr.frames_per_s:.13g};
    }}
    forceCoeffs
    {{
        type forceCoeffs;
        libs (forces);
        patches (body);
        rho rhoInf;
        rhoInf {s.rho:.8g};
        CofR (0 0 0);
        liftDir (0 0 1);
        dragDir (1 0 0);
        pitchAxis (0 1 0);
        magUInf {s.speed:g};
        lRef {L:g};
        Aref {Aref:g};
        writeControl timeStep;
        writeInterval 1;
        log off;
    }}
}}
"""


def transient_fv_schemes() -> str:
    return FV_SCHEMES.replace("default steadyState;", "default backward;").replace("bounded Gauss", "Gauss")


def transient_fv_solution(tr: Transient) -> str:
    return f"""solvers
{{
    p      {{ solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.01; }}
    pFinal {{ $p; relTol 0; }}
    Phi    {{ $p; relTol 0.01; }}
    "(U|k|omega)" {{ solver smoothSolver; smoother GaussSeidel; tolerance 1e-8; relTol 0.1; nSweeps 1; }}
    "(U|k|omega)Final" {{ $U; relTol 0; }}
}}
PIMPLE
{{
    momentumPredictor yes;
    nOuterCorrectors {tr.n_outer};
    nCorrectors {tr.n_corr};
    nNonOrthogonalCorrectors 1;
}}
potentialFlow {{ nNonOrthogonalCorrectors 5; }}
relaxationFactors {{ equations {{ ".*" 1; }} }}
"""


def write_transient_case(root: Path, src: str, s: Setup3D, tr: Transient, L: float, Aref: float,
                         exporter: Path | None = None):
    """Writes system/, constant/ properties and an Allrun into `root`; the Allrun copies the decomposed
    mesh and the initial fields of the solved steady case `src` (a WSL path), starts from potentialFoam,
    runs pimpleFoam and exports one field frame per written time. Returns the Allrun path."""
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    sysd, con = root / "system", root / "constant"
    sysd.mkdir(parents=True)
    con.mkdir(parents=True)
    w = lambda p, obj, body: p.write_text(newline="\n", data=HEADER.format(cls="dictionary", obj=obj) + body)
    w(con / "transportProperties", "transportProperties", f"transportModel Newtonian;\nnu {s.nu:.8g};\n")
    w(con / "turbulenceProperties", "turbulenceProperties",
      "simulationType RAS;\nRAS\n{\n    RASModel kOmegaSST;\n    turbulence on;\n    printCoeffs on;\n}\n")
    w(sysd / "controlDict", "controlDict", transient_control_dict(s, tr, L, Aref))
    w(sysd / "fvSchemes", "fvSchemes", transient_fv_schemes())
    w(sysd / "fvSolution", "fvSolution", transient_fv_solution(tr))
    if exporter:
        shutil.copy(exporter, root / "export_field.py")
        for helper in ("convergence.py", "transient.py"):
            shutil.copy(Path(__file__).with_name(helper), root / helper)
    mpi = f"mpirun -np {tr.procs} --oversubscribe"
    vox = L / s.voxels_per_L
    lines = [
        "#!/bin/bash", ENV,
        "export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 OMPI_MCA_btl_vader_single_copy_mechanism=none",
        "cd \"$(dirname \"$0\")\"",
        "fail() { echo \"failed $1\" > status; exit 1; }",
        f"SRC=\"{src}\"",
        # potentialFoam overwrites processor*/0; a second start over a run would mix two runs.
        "ls -d processor0/[0-9]* 2>/dev/null | grep -qv '/0$' && fail \"the case already has time steps: "
        "the potential start runs only on a fresh copy\"",
        "echo copying > status",
        "[ -d \"$SRC/processor0/constant/polyMesh\" ] || fail \"no decomposed mesh in $SRC\"",
        "cp -r \"$SRC/constant/polyMesh\" \"$SRC/constant/triSurface\" constant/ || fail copy",
        "cp \"$SRC/system/decomposeParDict\" system/ || fail copy",
        "cp -r \"$SRC/0.orig\" 0 || fail copy",
        "(cd \"$SRC\" && cp -r --parents processor*/constant \"$OLDPWD\"/) || fail copy",
        f"[ \"$(ls -d processor* | wc -l)\" = {tr.procs} ] || fail \"source is not decomposed into {tr.procs}\"",
        "for d in processor*; do rm -rf \"${d:?}/0\"; cp -r 0 \"$d/0\"; done",
        "echo potential > status",
        f"{mpi} potentialFoam -parallel -writep > log.potentialFoam 2>&1 || fail potentialFoam",
        "echo solving > status",
        f"{mpi} pimpleFoam -parallel > log.pimpleFoam 2>&1 || fail pimpleFoam",
    ]
    if not tr.steps:
        lines += [
            "echo exporting > status",
            f"python3 export_field.py . --frames --speed {s.speed} --rho {s.rho} --nu {s.nu} "
            f"--voxel {vox:.6g} --L {L:.6g} --fps {tr.frames_per_s} --jobs 20 > log.export 2>&1 || fail export",
        ]
    lines.append("echo done > status")
    script = root / "Allrun"
    script.write_text(newline="\n", data="\n".join(lines) + "\n")
    try:
        script.chmod(0o755)
    except OSError:
        pass
    return script
