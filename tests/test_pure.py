"""Tests for the add-on's pure-Python modules (no Blender, no WSL, no OpenFOAM).

Run from the repo root:   py -m unittest discover -s tests -v

The package __init__ imports bpy, so the modules are loaded through a stub package that
skips it. Tests marked expectedFailure encode accuracy targets from docs/FIX_PLAN.md that the
current code does not meet yet: when a fix lands they start "unexpectedly succeeding", which
is the signal to remove the marker.
"""
from __future__ import annotations

import contextlib
import importlib
import io
import importlib.util
import json
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if "wind_tunnel" not in sys.modules:
    pkg = types.ModuleType("wind_tunnel")
    pkg.__path__ = [str(REPO / "wind_tunnel")]
    sys.modules["wind_tunnel"] = pkg

case = importlib.import_module("wind_tunnel.case")
case3d = importlib.import_module("wind_tunnel.case3d")
results = importlib.import_module("wind_tunnel.results")
wsl = importlib.import_module("wind_tunnel.wsl")


def cube_triangles(L=2.0):
    """A closed cube of side L centred on the origin, outward-facing triangles."""
    h = L / 2
    v = [(x, y, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = []
    for a, b, c, d in quads:
        tris += [(v[a], v[b], v[c]), (v[a], v[c], v[d])]
    return tris


class Naca(unittest.TestCase):
    def test_0012_max_thickness(self):
        up, lo = case.naca4("0012", 200)
        t = max(u[1] - l[1] for u, l in zip(up, lo))
        self.assertAlmostEqual(t, 0.12, delta=0.002)

    def test_closed_ends(self):
        up, lo = case.naca4("2412")
        self.assertEqual(up[0], lo[0])
        self.assertEqual(up[-1], lo[-1])

    def test_camber_upper_above_lower(self):
        up, lo = case.naca4("4412", 100)
        mid = len(up) // 2
        self.assertGreater(up[mid][1], lo[mid][1])
        self.assertGreater(up[mid][1] + lo[mid][1], 0.0)   # positive camber


class Decompose(unittest.TestCase):
    def test_split3(self):
        for n in range(1, 33):
            a, b, c = case3d.split3(n)
            self.assertEqual(a * b * c, n)
            self.assertTrue(a >= b >= c >= 1)


class Case3D(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "3d_Cube"
        self.s = case3d.Setup3D()
        self.script, self.t = case3d.write_case(self.root, cube_triangles(), self.s)

    def tearDown(self):
        self.tmp.cleanup()

    def test_files(self):
        for rel in ("Allrun", "system/blockMeshDict", "system/snappyHexMeshDict", "system/fvSchemes",
                    "system/fvSolution", "system/controlDict", "system/decomposeParDict",
                    "0.orig/U", "0.orig/p", "0.orig/k", "0.orig/omega", "0.orig/nut",
                    "constant/triSurface/body.stl"):
            self.assertTrue((self.root / rel).exists(), rel)

    def test_stl_roundtrip(self):
        tris = case3d.read_stl(self.root / "constant/triSurface/body.stl")
        self.assertEqual(len(tris), 12)
        lo, hi = case3d.bounds(tris)
        self.assertAlmostEqual(hi[0] - lo[0], 2.0, places=5)

    def test_body_is_noslip_wall(self):
        U = (self.root / "0.orig/U").read_text()
        self.assertIn("noSlip", U)
        self.assertIn("type wall", (self.root / "system/snappyHexMeshDict").read_text().replace("  ", " "))

    def test_allrun_order(self):
        text = self.script.read_text()
        order = ["blockMesh", "snappyHexMesh", "simpleFoam", "reconstructPar", "export_field.py"]
        pos = [text.index(k) for k in order]
        self.assertEqual(pos, sorted(pos))

    def _decompose_method(self):
        text = (self.root / "system/decomposeParDict").read_text()
        return [ln.split()[1].rstrip(";") for ln in text.splitlines() if ln.split()[:1] == ["method"]]

    def test_decomposition_scotch(self):
        """FIX_PLAN step 0: scotch partitioning, as the openfoam.com builds ship it."""
        self.assertEqual(self._decompose_method(), ["scotch"])

    def test_decomposition_fallback_before_decompose(self):
        """Without libscotchDecomp the Allrun switches to hierarchical before decomposePar runs."""
        lines = self.script.read_text().splitlines()
        fb = [i for i, ln in enumerate(lines) if "libscotchDecomp" in ln and "hierarchical" in ln]
        dp = [i for i, ln in enumerate(lines) if ln.startswith("decomposePar")]
        self.assertEqual(len(fb), 1)
        self.assertLess(fb[0], dp[0])
        self.assertIn("hierarchicalCoeffs", (self.root / "system/decomposeParDict").read_text())

    def _blockage(self):
        (x0, y0, z0), (x1, y1, z1) = self.t["box"]
        return self.t["L"] ** 2 / ((y1 - y0) * (z1 - z0))   # cube frontal area = L^2

    def test_blockage_current(self):
        self.assertLess(self._blockage(), 0.03)

    @unittest.expectedFailure
    def test_blockage_target(self):
        """FIX_PLAN step 4: blockage at most 1 %."""
        self.assertLessEqual(self._blockage(), 0.01)

    @unittest.expectedFailure
    def test_inlet_far_enough_upstream(self):
        """FIX_PLAN step 4: inlet at least 5 L upstream of the body."""
        (x0, _, _), _ = self.t["box"]
        self.assertGreaterEqual(-1.0 - x0, 5 * self.t["L"])

    @unittest.expectedFailure
    def test_layers_target(self):
        """FIX_PLAN step 3: at least 5 prism layers sized from a target y+."""
        self.assertGreaterEqual(self.s.layers, 5)
        self.assertIn("relativeSizes false", (self.root / "system/snappyHexMeshDict").read_text())


class PickBashrc(unittest.TestCase):
    """Which OpenFOAM environment script the add-on sources (wsl.pick_bashrc)."""
    UBUNTU = "/usr/share/openfoam/etc/bashrc"
    COM = "/usr/lib/openfoam/openfoam{}/etc/bashrc"

    def test_newest_openfoam_com_wins(self):
        paths = [self.COM.format(2606), self.COM.format(2512), self.COM.format(1912)]
        self.assertEqual(wsl.pick_bashrc(paths), self.COM.format(2606))
        self.assertEqual(wsl.pick_bashrc(paths[::-1]), self.COM.format(2606))

    def test_openfoam_com_beats_ubuntu_package(self):
        self.assertEqual(wsl.pick_bashrc([self.COM.format(2512), self.UBUNTU]), self.COM.format(2512))
        self.assertEqual(wsl.pick_bashrc([self.UBUNTU, self.COM.format(2512)]), self.COM.format(2512))

    def test_opt_layout_counts_as_openfoam_com(self):
        self.assertEqual(wsl.pick_bashrc([self.UBUNTU, "/opt/openfoam2412/etc/bashrc"]),
                         "/opt/openfoam2412/etc/bashrc")

    def test_ubuntu_package_only_as_fallback(self):
        self.assertEqual(wsl.pick_bashrc([self.UBUNTU]), self.UBUNTU)

    def test_nothing_found(self):
        self.assertIsNone(wsl.pick_bashrc([]))


class Readers(unittest.TestCase):
    def test_uniform_vector(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "U"
            p.write_text("FoamFile\n{\n    version 2.0;\n}\ndimensions [0 1 -1 0 0 0 0];\n"
                         "internalField   uniform (20 0 0);\nboundaryField {}\n")
            values, uniform = results.read_internal(p, 3)
            self.assertIsNone(values)
            self.assertEqual(tuple(uniform), (20.0, 0.0, 0.0))

    def test_face_area_unit_square(self):
        pts = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
        area, centre = results._face_geom([0, 1, 2, 3], pts)
        self.assertAlmostEqual(area[2], 1.0)
        self.assertAlmostEqual(centre[0], 0.5)


class CpReference(unittest.TestCase):
    """FIX_PLAN step 1: Cp referenced to the inlet mean static pressure (docs/reference/step1_cp_reference.md)."""

    V041_KEYS = {"time", "cells", "drag_N", "side_N", "lift_N", "pressure_drag_N", "friction_drag_N",
                 "frontal_area_m2", "pressure_N", "viscous_N", "Cd", "Cl", "speed", "rho"}

    @classmethod
    def setUpClass(cls):
        global np
        import numpy as np
        cls.ef = importlib.import_module("wind_tunnel.export_field")

    def test_inlet_mean_is_area_weighted(self):
        p = np.array([0.0, 4.0, 99.0])                      # cell 2 is not on the patch
        owner = np.array([0, 1])
        Sf = np.array([[-1.0, 0, 0], [-3.0, 0, 0]])         # areas 1 and 3; unweighted mean would be 2
        self.assertAlmostEqual(self.ef.inlet_reference_pressure(p, owner, Sf), 3.0)

    def test_cp_zero_at_inlet_one_at_stagnation(self):
        U, off = 20.0, 7.3                                  # uniform offset field, kinematic p
        p_cells = np.full(4, off)
        p_inf = self.ef.inlet_reference_pressure(p_cells, np.array([0, 1]), np.array([[-2.0, 0, 0], [-5.0, 0, 0]]))
        self.assertEqual(self.ef.cp_from_p(off, p_inf, U), 0.0)
        self.assertEqual(self.ef.cp_from_p(off + 0.5 * U ** 2, p_inf, U), 1.0)

    def test_field_npz_pressure_shifted_by_p_inf(self):
        """p in field.npz is rho (p - p_inf) in Pa, so viz3d.write_vdb's cp = p / (0.5 rho U^2) is
        referenced to p_inf. The VDB grid itself needs Blender (openvdb); Stage 5 checks it headless."""
        U, rho, p_inf = 20.0, 1.225, 9.0
        pk = np.full((3, 2, 2), p_inf, dtype=float)
        pk[0, 0, 0] = p_inf + 0.5 * U ** 2                 # stagnation
        solid = np.zeros((3, 2, 2), bool)
        solid[2, 1, 1] = True
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "field.npz"
            self.ef.write_field_npz(path, np.zeros(3), 0.5, np.zeros((3, 2, 2, 3)), pk, solid, U, rho, p_inf)
            with np.load(path) as f:
                cp = f["p"] / (0.5 * rho * float(f["speed"]) ** 2)     # viz3d.write_vdb's formula
                self.assertAlmostEqual(float(cp[0, 0, 0]), 1.0, places=6)
                self.assertAlmostEqual(float(cp[1, 1, 0]), 0.0, places=6)
                self.assertEqual(float(f["p"][2, 1, 1]), 0.0)          # solid voxels stay 0
                self.assertAlmostEqual(float(f["p_inf_Pa"]), rho * p_inf, places=5)

    def test_forces_json_keeps_v041_keys_and_adds_p_inf(self):
        Fp, Fv = np.array([100.0, 1.0, 2.0]), np.array([3.0, 0.5, 0.25])
        rec = self.ef.forces_record("400", 1000, Fp, Fv, 4.0, 20.0, 1.225, 9.8)
        self.assertEqual(set(rec), self.V041_KEYS | {"p_inf_Pa", "p_inf_Cp_vs_outlet"})
        q = 0.5 * 1.225 * 20.0 ** 2
        self.assertEqual(rec["drag_N"], 103.0)
        self.assertEqual(rec["pressure_drag_N"], 100.0)
        self.assertEqual(rec["friction_drag_N"], 3.0)
        self.assertAlmostEqual(rec["Cd"], 103.0 / (q * 4.0))
        self.assertAlmostEqual(rec["Cl"], 2.25 / (q * 4.0))
        self.assertAlmostEqual(rec["p_inf_Pa"], 1.225 * 9.8)
        self.assertAlmostEqual(rec["p_inf_Cp_vs_outlet"], 9.8 / (0.5 * 20.0 ** 2))
        json.dumps(rec)                                     # must stay serialisable


FORCE_HEAD = ("# Force        \n# CofR         : (0.0000000e+00 0.0000000e+00 0.0000000e+00)\n#\n"
              "# Time         \ttotal_x total_y total_z\tpressure_x pressure_y pressure_z\tviscous_x viscous_y viscous_z\n")
RES_HEAD = ("# Solver information\n# Time         \tp_solver       \tp_initial      \tp_final        "
            "\tp_iters        \tp_converged    \n")


def write_history(case: Path, start, times, fx, fy, fz, p_initial):
    """postProcessing/forces/<start>/force.dat and solverInfo/<start>/solverInfo.dat as v2512 writes them."""
    fd = case / "postProcessing" / "forces" / str(start)
    sd = case / "postProcessing" / "solverInfo" / str(start)
    fd.mkdir(parents=True, exist_ok=True)
    sd.mkdir(parents=True, exist_ok=True)
    f_rows = "".join(f"{t:<15} {x:.7e} {y:.7e} {z:.7e} {x:.7e} {y:.7e} {z:.7e} 0 0 0\n"
                     for t, x, y, z in zip(times, fx, fy, fz))
    r_rows = "".join(f"{t:<15}\tGAMG\t{r:.7e}\t1e-5\t3\ttrue\n" for t, r in zip(times, p_initial))
    (fd / "force.dat").write_text(FORCE_HEAD + f_rows, newline="\n")
    (sd / "solverInfo.dat").write_text(RES_HEAD + r_rows, newline="\n")


def steady(n, fx=1000.0, rel=0.0, res=5e-4, first=1):
    """n iterations from `first`: Fx alternating between fx and fx (1 + rel), constant residual."""
    times = list(range(first, first + n))
    return (times, [fx * (1 + rel * (t % 2)) for t in times], [3.0] * n, [-2.0] * n, [res] * n)


class ConvergenceParsers(unittest.TestCase):
    """FIX_PLAN step 2: postProcessing readers (docs/reference/step2_convergence_reference.md, file formats)."""

    @classmethod
    def setUpClass(cls):
        cls.cv = importlib.import_module("wind_tunnel.convergence")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_columns_from_last_header_line(self):
        path = self.case / "x.dat"
        path.write_text("# Solver information\n# Time\tp_initial\tp_solver\n5\t1e-3\tGAMG\n", newline="\n")
        names, rows = self.cv.read_dat(path)
        self.assertEqual(names, ["Time", "p_initial", "p_solver"])
        self.assertEqual(rows, [["5", "1e-3", "GAMG"]])

    def test_incomplete_last_line_dropped(self):
        path = self.case / "x.dat"
        path.write_text(RES_HEAD + "1\tGAMG\t1e-2\t1e-5\t3\ttrue\n2\tGAMG\t9.5e-3\t1e-5\t3\ttr", newline="\n")
        self.assertEqual(len(self.cv.read_dat(path)[1]), 1)
        # all the fields there, but the number may be cut short: still no trailing newline, still dropped
        path.write_text(RES_HEAD + "1\tGAMG\t1e-2\t1e-5\t3\ttrue\n2\tGAMG\t9.5e-3\t1e-5\t3\ttrue", newline="\n")
        self.assertEqual(len(self.cv.read_dat(path)[1]), 1)

    def test_history_aligns_forces_and_residuals(self):
        times, fx, fy, fz, res = steady(5)
        write_history(self.case, 0, times, fx, fy, fz, res)
        h = self.cv.history(self.case)
        self.assertEqual(h["time"], [1, 2, 3, 4, 5])
        self.assertEqual(h["fx"], fx)
        self.assertEqual(h["fy"], fy)
        self.assertEqual(h["fz"], fz)
        self.assertEqual(h["p_initial"], res)

    def test_restart_dirs_merged_numerically_later_wins(self):
        write_history(self.case, 900, *steady(150, fx=1.0, first=901))        # 901..1050
        write_history(self.case, 1000, *steady(100, fx=2.0, first=1001))      # 1001..1100 (lexically first)
        h = self.cv.history(self.case)
        self.assertEqual(h["time"], list(range(901, 1101)))
        self.assertEqual(h["fx"][h["time"].index(1000)], 1.0)
        self.assertEqual(h["fx"][h["time"].index(1001)], 2.0)
        self.assertEqual(h["fx"][-1], 2.0)

    def test_no_history(self):
        h = self.cv.history(self.case)
        self.assertEqual(h["time"], [])


class ConvergenceGate(unittest.TestCase):
    """FIX_PLAN step 2, decision Q2 (and Q5: both criteria hard, residual trend reported)."""

    @classmethod
    def setUpClass(cls):
        cls.cv = importlib.import_module("wind_tunnel.convergence")

    def test_constants(self):
        self.assertEqual((self.cv.WINDOW, self.cv.BAND, self.cv.RESIDUAL, self.cv.MIN_ITER), (200, 0.005, 1e-3, 400))

    def test_band_just_under_passes(self):
        v = self.cv.gate(*steady(600, rel=0.0049))
        self.assertTrue(v["converged"], v["reasons"])
        self.assertEqual(v["reasons"], [])
        self.assertAlmostEqual(v["band"], 0.0049 / 1.00245, places=9)
        self.assertEqual(v["iteration"], 600)
        self.assertEqual(v["window"], (401, 600))

    def test_band_just_over_fails(self):
        v = self.cv.gate(*steady(600, rel=0.0051))
        self.assertFalse(v["converged"])
        self.assertEqual(len(v["reasons"]), 1)
        self.assertIn("Cd band", v["reasons"][0])

    def test_band_uses_only_the_window(self):
        times, fx, fy, fz, res = steady(600)
        fx[400] = 5000.0                       # iteration 401: inside the window
        self.assertFalse(self.cv.gate(times, fx, fy, fz, res)["converged"])
        fx[400], fx[399] = 1000.0, 5000.0      # iteration 400: just outside it
        self.assertTrue(self.cv.gate(times, fx, fy, fz, res)["converged"])

    def test_residual_just_under_passes(self):
        self.assertTrue(self.cv.gate(*steady(600, res=9.9e-4))["converged"])

    def test_residual_just_over_fails(self):
        v = self.cv.gate(*steady(600, res=1.01e-3))
        self.assertFalse(v["converged"])
        self.assertEqual(len(v["reasons"]), 1)
        self.assertIn("p residual", v["reasons"][0])
        self.assertAlmostEqual(v["residual"], 1.01e-3)

    def test_residual_is_the_last_iteration(self):
        times, fx, fy, fz, res = steady(600, res=2e-3)
        res[-1] = 9e-4
        self.assertTrue(self.cv.gate(times, fx, fy, fz, res)["converged"])

    def test_before_400_never_converged(self):
        v = self.cv.gate(*steady(399))
        self.assertFalse(v["converged"])
        self.assertTrue(any("400" in r for r in v["reasons"]))

    def test_window_must_be_full(self):
        """A history that starts late (restart) cannot pass on fewer than 200 iterations."""
        v = self.cv.gate(*steady(150, first=451))     # 451..600
        self.assertFalse(v["converged"])
        self.assertTrue(any("200" in r for r in v["reasons"]))

    def test_cap_reached(self):
        v = self.cv.gate(*steady(3000, res=2e-3), cap=3000)
        self.assertFalse(v["converged"])
        self.assertIn("3000", v["reasons"][0])
        self.assertTrue(any("p residual" in r for r in v["reasons"]))

    def test_cap_not_a_reason_when_converged(self):
        self.assertTrue(self.cv.gate(*steady(3000), cap=3000)["converged"])

    def test_residual_trend_orders_per_100(self):
        """Q5: the reasons say whether the p residual is still falling (orders of magnitude per 100 iterations)."""
        times, fx, fy, fz, _ = steady(1200)
        res = [10 ** (-1.7 - 0.0009 * t) for t in times]     # cube-like: -0.09 orders per 100 iterations
        v = self.cv.gate(times, fx, fy, fz, res)
        self.assertAlmostEqual(v["residual_trend"], -0.09, places=6)
        self.assertFalse(v["converged"])
        self.assertTrue(any("-0.09 orders per 100 iterations" in r for r in v["reasons"]))

    def test_window_statistics(self):
        times, fx, fy, fz, res = steady(600, rel=0.004)
        fy = [float(t % 3) for t in times]
        v = self.cv.gate(times, fx, fy, fz, res)
        self.assertAlmostEqual(v["fx"]["mean"], 1002.0)
        self.assertEqual((v["fx"]["min"], v["fx"]["max"]), (1000.0, 1004.0))
        self.assertEqual((v["fy"]["min"], v["fy"]["max"]), (0.0, 2.0))
        self.assertEqual(v["fz"]["mean"], -2.0)

    def test_empty_history(self):
        v = self.cv.gate([], [], [], [], [])
        self.assertFalse(v["converged"])
        self.assertTrue(v["reasons"])


class ConvergenceTrigger(unittest.TestCase):
    """`python3 convergence.py <case> --trigger`, run by the systemCall function object every 5 iterations."""

    @classmethod
    def setUpClass(cls):
        cls.cv = importlib.import_module("wind_tunnel.convergence")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _main(self):
        with contextlib.redirect_stdout(io.StringIO()):          # the gate prints its verdict for the solver log
            return self.cv.main([str(self.case), "--trigger"])

    def test_pass_writes_stop_file(self):
        write_history(self.case, 0, *steady(600))
        self.assertEqual(self._main(), 0)
        self.assertEqual((self.case / "wt_stop").read_text(), "action=writeNow\n")

    def test_open_gate_writes_nothing(self):
        write_history(self.case, 0, *steady(600, res=2e-3))
        self.assertEqual(self._main(), 0)
        self.assertFalse((self.case / "wt_stop").exists())

    def test_no_history_is_not_an_error(self):
        self.assertEqual(self._main(), 0)
        self.assertFalse((self.case / "wt_stop").exists())

    def test_unreadable_history_is_not_an_error(self):
        d = self.case / "postProcessing" / "forces" / "0"
        d.mkdir(parents=True)
        (d / "force.dat").write_text("# Time total_x total_y total_z\n1 abc 0 0\n", newline="\n")
        self.assertEqual(self._main(), 0)
        self.assertFalse((self.case / "wt_stop").exists())


class Case3DGate(unittest.TestCase):
    """FIX_PLAN step 2: the controlDict, fvSolution and Allrun text case3d writes (design constraints 2, 3)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "3d_Cube"
        self.s = case3d.Setup3D(rho=1.2, iterations=2500)
        self.script, _ = case3d.write_case(self.root, cube_triangles(), self.s)
        self.cd = (self.root / "system/controlDict").read_text()

    def tearDown(self):
        self.tmp.cleanup()

    def _entry(self, key):
        return [ln.split()[1].rstrip(";") for ln in self.cd.splitlines() if ln.split()[:1] == [key]]

    def test_default_cap_3000(self):
        self.assertEqual(case3d.Setup3D().iterations, 3000)

    def test_end_time_is_the_cap(self):
        self.assertEqual(self._entry("endTime"), ["2500"])

    def test_function_objects_in_order(self):
        pos = [self.cd.index(f"type {t};") for t in ("forces", "solverInfo", "systemCall", "abort")]
        self.assertEqual(pos, sorted(pos))

    def test_forces_fo(self):
        fo = self.cd[self.cd.index("type forces;"):self.cd.index("type solverInfo;")]
        for txt in ("patches (body);", "rho rhoInf;", "rhoInf 1.2;", "CofR (0 0 0);",
                    "writeControl timeStep;", "writeInterval 1;"):
            self.assertIn(txt, fo)

    def test_solver_info_fo(self):
        fo = self.cd[self.cd.index("type solverInfo;"):self.cd.index("type systemCall;")]
        self.assertIn("fields (p);", fo)
        self.assertIn("writeResidualFields no;", fo)

    def test_gate_and_stop_fo(self):
        gate = self.cd[self.cd.index("type systemCall;"):self.cd.index("type abort;")]
        for txt in ("master yes;", "executeControl timeStep;", "executeInterval 5;", "writeControl none;",
                    'executeCalls ("python3 convergence.py . --trigger");'):
            self.assertIn(txt, gate)
        stop = self.cd[self.cd.index("type abort;"):]
        self.assertIn('file "wt_stop";', stop)
        self.assertIn("action writeNow;", stop)

    def test_no_residual_control(self):
        self.assertNotIn("residualControl", (self.root / "system/fvSolution").read_text())

    def test_gate_script_copied(self):
        self.assertTrue((self.root / "convergence.py").exists())

    def test_allrun_clears_stop_file_before_solve(self):
        lines = self.script.read_text().splitlines()
        rm = [i for i, ln in enumerate(lines) if ln.strip() == "rm -f wt_stop"]
        solve = [i for i, ln in enumerate(lines) if "simpleFoam -parallel" in ln]
        self.assertEqual(len(rm), 1)
        self.assertLess(rm[0], solve[0])

    def test_allrun_refuses_root_before_meshing(self):
        """systemCall is fatal as root (systemCall.C:123): fail at once with a clear status."""
        lines = self.script.read_text().splitlines()
        root = [i for i, ln in enumerate(lines) if "id -u" in ln]
        mesh = [i for i, ln in enumerate(lines) if ln.startswith("blockMesh")]
        self.assertEqual(len(root), 1)
        self.assertLess(root[0], mesh[0])

    def test_export_gets_the_cap(self):
        self.assertIn("--cap 2500", self.script.read_text())


class SolidMask(unittest.TestCase):
    """Open issue e: a wall that lies exactly on a grid plane gives the same node layer on every face."""

    @classmethod
    def setUpClass(cls):
        global np
        import numpy as np
        cls.ef = importlib.import_module("wind_tunnel.export_field")
        h = 0.05                                            # the _anim/Cube grid (171 x 101 x 101)
        cls.gx, cls.gy = -2.5 + h * np.arange(171), -2.5 + h * np.arange(101)

    @staticmethod
    def cube(lo, hi):
        v = [[x, y, z] for x in (lo, hi) for y in (lo, hi) for z in (lo, hi)]
        quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        return np.array([t for a, b, c, d in quads for t in ((v[a], v[b], v[c]), (v[a], v[c], v[d]))], float)

    def spans(self, m):
        out = []
        for ax, g in ((0, self.gx), (1, self.gy), (2, self.gy)):
            idx = np.where(m.any(axis=tuple(i for i in range(3) if i != ax)))[0]
            out.append((round(g[idx[0]], 6), round(g[idx[-1]], 6)))
        return out

    def test_grid_aligned_cube_is_closed_and_symmetric(self):
        m = self.ef.inside_mask(self.cube(-1.0, 1.0), self.gx, self.gy, self.gy)
        self.assertEqual(self.spans(m), [(-1.0, 1.0)] * 3)
        self.assertEqual(int(m.sum()), 41 ** 3)             # every node with |x|, |y|, |z| <= 1 m
        self.assertTrue((m == m[:, ::-1, :]).all() and (m == m[:, :, ::-1]).all())

    def test_cube_between_nodes_is_not_inflated(self):
        m = self.ef.inside_mask(self.cube(-0.97, 0.97), self.gx, self.gy, self.gy)
        self.assertEqual(self.spans(m), [(-0.95, 0.95)] * 3)
        self.assertEqual(int(m.sum()), 39 ** 3)


class AnimPure(unittest.TestCase):
    """ANIMATION A+B Stage 3: the pure rules the slice, legend, label and sweep are built from."""

    @classmethod
    def setUpClass(cls):
        global np
        import numpy as np
        cls.an = importlib.import_module("wind_tunnel.anim")

    def test_cp_to_ramp_two_sided_and_clamped(self):
        f = self.an.cp_to_ramp
        self.assertEqual([f(c, -1.0, 1.0) for c in (-1.0, -0.5, 0.0, 0.5, 1.0)], [0.0, 0.25, 0.5, 0.75, 1.0])
        self.assertEqual([f(c, -2.0, 1.0) for c in (-1.0, 0.0, 0.5)], [0.25, 0.5, 0.75])   # 0 stays neutral
        self.assertEqual((f(-3.0, -1.0, 1.0), f(1.025, -1.0, 1.0)), (0.0, 1.0))
        self.assertAlmostEqual(f(-0.70, -1.0, 1.0), 0.15)                  # the cube's deepest suction

    def test_cp_stops_are_the_spec_table(self):
        st = self.an.CP_STOPS
        self.assertEqual([t for t, _ in st], [k / 8 for k in range(9)])
        self.assertEqual(st[0][1], (0.0437, 0.0723, 0.5271))
        self.assertEqual(st[4][1], (0.7207, 0.7207, 0.7205))
        self.assertEqual(st[8][1], (0.4564, 0.0012, 0.0194))
        for (_, lin), srgb in zip(st, self.an.CP_STOPS_SRGB):              # the columns agree to 8 bits
            self.assertEqual(tuple(round(255 * self.an.linear_to_srgb(c)) for c in lin), srgb)

    def test_sweep_keyframes_pingpong_constant_speed(self):
        keys = self.an.sweep_keyframes("Y", (0.0, 0.1, 0.0), 2.0, 192, True)
        frames = [f for f, _ in keys]
        y = [p[1] for _, p in keys]
        self.assertEqual(frames, list(range(1, 193)))
        self.assertEqual((y[0], y[96]), (-1.9, 2.1))                        # ends exactly at the limits
        self.assertTrue(all(p[0] == 0.0 and p[2] == 0.0 for _, p in keys))
        steps = np.abs(np.diff(y + [y[0]]))                                 # closes the loop at frame 193
        self.assertTrue(np.allclose(steps, 4.0 / 96, atol=1e-12))
        self.assertTrue(all(abs(y[f - 1] - y[194 - f - 1]) < 1e-12 for f in range(2, 193)))

    def test_sweep_half_range_clamped_to_grid(self):
        f = self.an.sweep_half_range
        lo, hi = (-2.5, -2.5, -2.5), (6.0, 2.5, 2.5)
        self.assertAlmostEqual(f("Y", (0, 0, 0), 2.0, lo, hi, 0.05), 2.0)
        self.assertAlmostEqual(f("X", (0, 0, 0), 2.0, lo, hi, 0.05), 2.0)
        self.assertAlmostEqual(f("Y", (0, 0, 0), 4.0, lo, hi, 0.05), 2.0)  # 1 L would leave the grid
        self.assertAlmostEqual(f("Z", (0, 0, 1.0), 2.0, lo, hi, 0.05), 1.0)

    def test_slice_keep_grid_bounds_and_solid(self):
        solid = np.zeros((11, 11, 11), bool)
        solid[5, 5, 5] = True
        pts = np.array([[2.5, 2.5, 2.5], [4.5, 5.0, 5.0], [5.0, 5.0, 6.0], [-0.1, 2, 2], [10.0, 2, 2],
                        [10.01, 2, 2], [5.5, 5.5, 5.5]])
        keep = self.an.slice_keep(pts, (0.0, 0.0, 0.0), 1.0, solid)
        self.assertEqual(keep.tolist(), [True, False, True, False, True, False, False])

    def test_slice_keep_symmetric_for_symmetric_mask(self):
        g = -2.5 + 0.05 * np.arange(101)
        solid = (np.abs(g)[:, None, None] <= 1.0) & (np.abs(g)[None, :, None] <= 1.0) & (np.abs(g)[None, None, :] <= 1.0)
        a = np.linspace(-2.5, 2.5, 161)
        P = np.array([[x, 0.3, z] for x in a for z in a])
        k = self.an.slice_keep(P, (-2.5, -2.5, -2.5), 0.05, solid).reshape(161, 161)
        self.assertTrue((k == k[::-1, :]).all() and (k == k[:, ::-1]).all())
        self.assertFalse(k[80, 80])
        self.assertEqual(int((~k).sum()), int((~k[:, 80]).sum()) ** 2)    # a square hole

    def test_label_text(self):
        f = self.an.label_text
        self.assertEqual(f("Y", 0.85, 2.0, True), "Slice y = +0.85 m (+0.43 L) | Cp")
        self.assertEqual(f("X", -2.0, 2.0, False), "Slice x = -2.00 m (-1.00 L) | speed/U_inf")

    def test_legend_ticks(self):
        f = self.an.legend_ticks
        self.assertEqual(f(True, -1.0, 1.0),
                         [(0.0, "<= -1.0"), (0.25, "-0.5"), (0.5, "0"), (0.75, "+0.5"), (1.0, ">= +1.0")])
        self.assertEqual(f(True, -2.0, 1.0)[1], (0.25, "-1.0"))
        self.assertEqual(f(False, -1.0, 1.0),
                         [(0.0, "0.3"), (0.25, "0.7"), (0.5, "1.1"), (0.75, "1.5"), (1.0, "1.9")])


class ExportVerdict(unittest.TestCase):
    """FIX_PLAN step 2 design constraint 4: forces.json verdict keys from the full history."""

    @classmethod
    def setUpClass(cls):
        global np
        import numpy as np
        cls.ef = importlib.import_module("wind_tunnel.export_field")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.case = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    KEYS = {"converged", "reasons", "iterations", "window", "Cd_band", "p_initial", "p_trend",
            "Cd_mean", "Cd_min", "Cd_max", "Cl_mean", "Cl_min", "Cl_max", "Cs_mean", "Cs_min", "Cs_max",
            "drag_N_mean", "lift_N_mean", "side_N_mean"}

    def test_converged_record(self):
        write_history(self.case, 0, *steady(601, rel=0.004))
        rec = self.ef.verdict_record(self.case, 3000, 4.0, 20.0, 1.225)
        self.assertEqual(set(rec), self.KEYS)
        q = 0.5 * 1.225 * 20.0 ** 2
        self.assertIs(rec["converged"], True)
        self.assertEqual(rec["reasons"], [])
        self.assertEqual(rec["iterations"], 601)
        self.assertEqual(rec["window"], [402, 601])
        self.assertAlmostEqual(rec["drag_N_mean"], 1002.0)
        self.assertAlmostEqual(rec["Cd_mean"], 1002.0 / (q * 4.0))
        self.assertAlmostEqual(rec["Cd_max"], 1004.0 / (q * 4.0))
        self.assertAlmostEqual(rec["Cl_mean"], -2.0 / (q * 4.0))
        self.assertAlmostEqual(rec["Cs_mean"], 3.0 / (q * 4.0))
        self.assertAlmostEqual(rec["side_N_mean"], 3.0)
        self.assertAlmostEqual(rec["lift_N_mean"], -2.0)
        json.dumps(rec)

    def test_no_history_not_converged(self):
        rec = self.ef.verdict_record(self.case, 3000, 4.0, 20.0, 1.225)
        self.assertIs(rec["converged"], False)
        self.assertTrue(rec["reasons"])
        json.dumps(rec)


class Verdict3D(unittest.TestCase):
    """FIX_PLAN step 2 decision Q4: what the panel shows, and which runs count as solved."""

    CONVERGED = {"converged": True, "reasons": [], "iterations": 1437, "Cd_band": 0.0031, "p_initial": 9.87e-4,
                 "Cd_mean": 1.1512, "Cd_min": 1.1490, "Cd_max": 1.1526, "Cl_mean": 0.0012, "Cl_min": -0.03,
                 "Cl_max": 0.03, "Cs_mean": -0.0021, "Cs_min": -0.04, "Cs_max": 0.04,
                 "drag_N_mean": 1128.3, "lift_N_mean": 1.2, "side_N_mean": -2.1, "Cd": 1.30}

    def test_converged_flag(self):
        self.assertTrue(results.forces_converged(self.CONVERGED))
        self.assertFalse(results.forces_converged({"converged": False}))
        self.assertFalse(results.forces_converged({"Cd": 1.26}))          # v0.4.x forces.json
        self.assertFalse(results.forces_converged({"converged": "yes"}))

    def test_converged_lines(self):
        lines = results.verdict_lines(self.CONVERGED)
        self.assertEqual(lines[:2], ["Converged at iteration 1437", "p residual 9.9e-04, Cd band 0.31 %"])
        self.assertEqual(lines[2:5], ["Cd 1.151 (1.149 to 1.153)", "Cl 0.001 (-0.030 to 0.030)",
                                      "Cs -0.002 (-0.040 to 0.040)"])
        self.assertEqual(lines[5:], ["Drag 1128.30 N", "Lift 1.20 N", "Side -2.10 N"])
        self.assertFalse(any("1.30" in ln for ln in lines))               # never the snapshot Cd

    def test_lines_fit_the_default_sidebar(self):
        """Stage 6 QA: the default-width sidebar cut lines longer than about 38 characters."""
        long_reason = "p residual 1.6e-03 >= 0.001 (trend -0.09 orders per 100 iterations)"
        f = dict(self.CONVERGED, converged=False, reasons=["stopped at the cap of 3000 iterations", long_reason])
        for rec in (self.CONVERGED, f, {"Cd": 1.26}):
            for ln in results.verdict_lines(rec):
                self.assertLessEqual(len(ln), results.PANEL_CHARS, ln)
        wrapped = results.verdict_lines(f)[2:]
        self.assertEqual(" ".join(w.strip() for w in wrapped), long_reason)   # wrapped, nothing lost
        self.assertTrue(all(w.startswith("  ") for w in wrapped[1:]))         # continuation indented

    def test_not_converged_lines_have_no_numbers_of_forces(self):
        f = dict(self.CONVERGED, converged=False,
                 reasons=["stopped at the cap of 3000 iterations", "p residual 1.6e-03 >= 1e-3"])
        lines = results.verdict_lines(f)
        self.assertEqual(lines[0], "Not converged:")
        self.assertEqual(lines[1:], ["stopped at the cap of 3000 iterations", "p residual 1.6e-03 >= 1e-3"])
        self.assertFalse(any("Cd " in ln or "Drag" in ln for ln in lines))

    def test_v04_case_is_not_converged(self):
        lines = results.verdict_lines({"Cd": 1.26, "drag_N": 1200.0})
        self.assertEqual(lines[0], "Not converged:")
        self.assertIn("no convergence record", lines[1])


class Stop3D(unittest.TestCase):
    """Stage 6 QA: `pkill -f "<case>/Allrun"` matched the `sh -c` that ran it, so the shell killed
    itself before writing `stopped`. pkill -f matches an extended regex against full command lines."""

    ROOT = "/home/bilal/wind_tunnel/3d_QASolve"

    def test_pkill_pattern_spares_its_own_shell(self):
        import re, shlex
        cmd = wsl.stop3d_command(self.ROOT)
        lex = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        words = list(lex)
        pattern = words[words.index("pkill") + 2]                    # pkill -f <pattern>
        self.assertIsNotNone(re.search(pattern, f"bash {self.ROOT}/Allrun"))
        self.assertIsNone(re.search(pattern, f"sh -c {cmd}"))

    def test_writes_stopped(self):
        self.assertTrue(wsl.stop3d_command(self.ROOT).endswith(f'echo stopped > "{self.ROOT}/status"'))

    def test_progress_reads_first_p_solve_of_last_iteration(self):
        log = ("Time = 401\n\nsmoothSolver:  Solving for Ux, Initial residual = 0.1, Final residual = 0.01\n"
               "GAMG:  Solving for p, Initial residual = 0.0236, Final residual = 1e-3, No Iterations 3\n"
               "GAMG:  Solving for p, Initial residual = 0.0041, Final residual = 1e-4, No Iterations 2\n"
               "ExecutionTime = 1 s\n\nTime = 402\n\n"
               "GAMG:  Solving for p, Initial residual = 0.0230, Final residual = 1e-3, No Iterations 3\n"
               "GAMG:  Solving for p, Initial residual = 0.0040, Final residual = 1e-4, No Iterations 2\n"
               "ExecutionTime = 2 s\n\nTime = 403\n\nsmoothSolver:  Solving for Ux, Initial residual = 0.1\n")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "log.simpleFoam").write_text(log, newline="\n")
            self.assertEqual(results.progress(Path(d)), (403, 0.0230))


class Transient3D(unittest.TestCase):
    """TRANSIENT T1 Stage 3: the pimpleFoam case text (docs/reference/transient_t1_spec.md Q1 and Q3)."""

    SRC = "/home/bilal/wind_tunnel/_anim/Cube"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "Cube"
        self.s = case3d.Setup3D()
        self.tr = case3d.Transient()
        self.script = case3d.write_transient_case(self.root, self.SRC, self.s, self.tr, L=2.0, Aref=4.0)
        self.cd = (self.root / "system/controlDict").read_text()
        self.fvs = (self.root / "system/fvSolution").read_text()
        self.allrun = self.script.read_text()

    def tearDown(self):
        self.tmp.cleanup()

    def _entry(self, key, text=None):
        return [ln.split()[1].rstrip(";") for ln in (text or self.cd).splitlines() if ln.split()[:1] == [key]]

    def _fo(self, kind):
        i = self.cd.index(f"type {kind};")
        return self.cd[self.cd.rindex("{", 0, i):self.cd.index("}", i)]

    def test_defaults_are_the_spec(self):
        tr = case3d.Transient()
        self.assertEqual((tr.end_time, tr.frames_per_s, tr.max_co, tr.n_outer, tr.n_corr, tr.full_write, tr.procs),
                         (2.0, 60, 1.0, 1, 2, 0.5, 24))
        self.assertIsNone(tr.steps)

    def test_control_dict_time(self):
        for key, val in (("application", "pimpleFoam"), ("startFrom", "latestTime"), ("stopAt", "endTime"),
                         ("endTime", "2"), ("deltaT", "0.001"), ("adjustTimeStep", "yes"), ("maxCo", "1"),
                         ("maxDeltaT", "1"), ("writeControl", "adjustableRunTime"), ("writeInterval", "0.5"),
                         ("purgeWrite", "0"), ("writeFormat", "ascii"), ("timePrecision", "8")):
            self.assertEqual(self._entry(key), [val], key)

    def test_write_objects_every_frame(self):
        fo = self._fo("writeObjects")
        for txt in ("libs (utilityFunctionObjects);", "objects (U p);", "writeControl adjustableRunTime;"):
            self.assertIn(txt, fo)
        wi = [ln.split()[1].rstrip(";") for ln in fo.splitlines() if ln.split()[:1] == ["writeInterval"]]
        self.assertAlmostEqual(float(wi[0]), 1 / 60, delta=1e-12)

    def test_force_coeffs_every_step(self):
        fo = self._fo("forceCoeffs")
        for txt in ("libs (forces);", "patches (body);", "rho rhoInf;", "rhoInf 1.225;", "CofR (0 0 0);",
                    "liftDir (0 0 1);", "dragDir (1 0 0);", "pitchAxis (0 1 0);", "magUInf 20;", "lRef 2;",
                    "Aref 4;", "writeControl timeStep;", "writeInterval 1;"):
            self.assertIn(txt, fo)

    def test_schemes_are_the_steady_ones_with_backward(self):
        steady = Path(self.tmp.name) / "steady"
        case3d.write_system(steady, self.s)
        st = (steady / "system/fvSchemes").read_text()
        tr = (self.root / "system/fvSchemes").read_text()
        self.assertNotIn("bounded", tr)
        self.assertIn("ddtSchemes { default backward; }", tr)
        self.assertEqual(tr, st.replace("default steadyState;", "default backward;").replace("bounded Gauss", "Gauss"))

    def test_pimple_and_solvers(self):
        pimple = self.fvs[self.fvs.index("PIMPLE"):self.fvs.index("potentialFlow")]
        for key, val in (("momentumPredictor", "yes"), ("nOuterCorrectors", "1"), ("nCorrectors", "2"),
                         ("nNonOrthogonalCorrectors", "1")):
            self.assertEqual(self._entry(key, pimple), [val], key)
        self.assertIn("pFinal { $p; relTol 0; }", self.fvs)
        self.assertIn('"(U|k|omega)Final" { $U; relTol 0; }', self.fvs)
        self.assertIn("potentialFlow { nNonOrthogonalCorrectors 5; }", self.fvs)
        self.assertIn("relTol 0.01;", self.fvs[self.fvs.index("p "):self.fvs.index("pFinal")])
        self.assertNotIn("SIMPLE", self.fvs)
        self.assertNotIn("residualControl", self.fvs)

    def test_allrun_copies_mesh_then_potential_then_pimple(self):
        lines = self.allrun.splitlines()
        at = lambda pat: [i for i, ln in enumerate(lines) if pat in ln]
        self.assertIn(f'SRC="{self.SRC}"', self.allrun)
        cp_mesh, pot, pim, exp = at("processor*/constant"), at("potentialFoam"), at("pimpleFoam"), at("--frames")
        self.assertTrue(cp_mesh and pot and pim and exp)
        self.assertLess(cp_mesh[0], pot[0])
        self.assertLess(pot[0], pim[0])
        self.assertLess(pim[-1], exp[0])
        self.assertIn("mpirun -np 24 --oversubscribe potentialFoam -parallel -writep", self.allrun)
        self.assertIn("mpirun -np 24 --oversubscribe pimpleFoam -parallel", self.allrun)

    def test_allrun_refuses_to_restart_the_potential_start(self):
        """potentialFoam overwrites processor*/0: the Allrun stops if any later time already exists."""
        lines = self.allrun.splitlines()
        guard = [i for i, ln in enumerate(lines) if "already has time steps" in ln]
        pot = [i for i, ln in enumerate(lines) if "potentialFoam" in ln]
        self.assertEqual(len(guard), 1)
        self.assertLess(guard[0], pot[0])

    def test_cost_mode_stops_after_n_steps_and_does_not_export(self):
        root = Path(self.tmp.name) / "cost"
        script = case3d.write_transient_case(root, self.SRC, self.s, case3d.Transient(steps=50), L=2.0, Aref=4.0)
        cd = (root / "system/controlDict").read_text()
        for key, val in (("stopAt", "nextWrite"), ("writeControl", "timeStep"), ("writeInterval", "50")):
            self.assertEqual(self._entry(key, cd), [val], key)
        self.assertIn("type writeObjects;", cd)
        self.assertNotIn("--frames", script.read_text())


class TransientPure(unittest.TestCase):
    """TRANSIENT T1 Stage 3: frame index and physical time, VDB sequence, smoke inputs, Q4 gate maths."""

    @classmethod
    def setUpClass(cls):
        global np
        import numpy as np
        cls.tr = importlib.import_module("wind_tunnel.transient")

    def test_frame_time_and_flow_throughs(self):
        self.assertEqual(self.tr.frame_time(30), 0.5)
        self.assertEqual(self.tr.frame_time(120), 2.0)
        self.assertAlmostEqual(self.tr.frame_tUL(6, 20.0, 2.0), 1.0)
        self.assertAlmostEqual(self.tr.frame_tUL(120, 20.0, 2.0), 20.0)

    def test_frame_from_time_dir_tolerant(self):
        f = self.tr.frame_from_time
        self.assertEqual(f("0.016666667"), 1)
        self.assertEqual(f("0.033333333"), 2)
        self.assertEqual(f("0.5"), 30)
        self.assertEqual(f("2"), 120)
        self.assertEqual(f("1.9999999"), 120)
        self.assertIsNone(f("0"))                   # the potential start is not a frame
        self.assertIsNone(f("0.0175"))              # a time step between frames
        self.assertIsNone(f("constant"))

    def test_vdb_names_and_sequence(self):
        self.assertEqual(self.tr.frame_name(1, "vdb"), "flow_0001.vdb")
        self.assertEqual(self.tr.frame_name(120, "npz"), "flow_0120.npz")
        self.assertEqual(self.tr.vdb_sequence(120),
                         {"is_sequence": True, "frame_start": 1, "frame_duration": 120, "frame_offset": 0,
                          "sequence_mode": "CLIP"})

    def test_time_label(self):
        self.assertEqual(self.tr.time_label(30, 20.0, 2.0), "t = 0.500 s (t U/L = 5.00)")
        self.assertEqual(self.tr.time_label(1, 20.0, 2.0), "t = 0.017 s (t U/L = 0.17)")

    def test_plain_smoke_inputs(self):
        L, U, fps, h = 2.0, 20.0, 24, 0.05
        d = self.tr.plain_smoke_inputs(L, U, fps, h)
        self.assertAlmostEqual(d["Time Scale"] * (1 / fps), 1 / 60)    # one CFD frame per scene frame
        step = 1.5 * U / 60 / d["Substeps"]                              # 1.5 U_inf: fastest flow near the cube
        self.assertLessEqual(step, h)
        self.assertGreater(1.5 * U / 60 / (d["Substeps"] - 1), h)        # the fewest substeps that do it
        self.assertAlmostEqual(d["Rate"] * (1.4 * L) ** 2, 40.0)        # 40 new particles a frame (was 150)
        self.assertAlmostEqual(U * d["Trail"], 0.1 * L)                 # streak 0.1 L at U_inf
        self.assertTrue(d["Plain"])
        self.assertTrue(d["Use Field"])
        self.assertGreaterEqual(d["Lifetime"] * U / 60, 4.25 * L)         # lives long enough to cross the grid

    def test_frame_continuity_last_corrector_of_frame_steps(self):
        log = ("Courant Number mean: 0.1 max: 0.9\ndeltaT = 0.0006\nTime = 0.0166\n"
               "time step continuity errors : sum local = 1e-09, global = 1e-12, cumulative = 1e-12\n"
               "time step continuity errors : sum local = 2e-11, global = 1e-13, cumulative = 1e-12\n"
               "deltaT = 0.00006666\nTime = 0.016666667\n"
               "time step continuity errors : sum local = 3e-09, global = 1e-12, cumulative = 1e-12\n"
               "time step continuity errors : sum local = 4e-11, global = 1e-13, cumulative = 1e-12\n"
               "ExecutionTime = 1 s\nTime = 0.0172\n"
               "time step continuity errors : sum local = 5e-08, global = 1e-12, cumulative = 1e-12\n"
               "time step continuity errors : sum local = 6e-10, global = 1e-13, cumulative = 1e-12\n"
               "Time = 0.033333333\n"
               "time step continuity errors : sum local = 7e-09, global = 1e-12, cumulative = 1e-12\n")
        self.assertEqual(self.tr.frame_continuity(log), {1: 4e-11, 2: 7e-09})
        self.assertEqual(self.tr.step_continuity(log)[-2], (0.0172, 6e-10))

    def test_window_mean_is_time_weighted(self):
        t = np.array([0.9, 1.0, 1.1, 1.5, 2.0])
        cd = np.array([9.0, 1.0, 1.0, 3.0, 3.0])
        # trapezoid on [1, 2]: 0.1 * 1 + 0.4 * 2 + 0.5 * 3 = 2.4
        self.assertAlmostEqual(self.tr.window_mean(t, cd, 1.0, 2.0), 2.4)

    def test_strouhal_from_side_force(self):
        U, L = 20.0, 2.0
        t = np.arange(0.0, 2.0, 6.5e-4)
        cs = 0.3 * np.sin(2 * np.pi * 1.1 * t + 0.4)                     # St = 1.1 * 2 / 20 = 0.11
        r = self.tr.strouhal(t, cs, U, L, 0.0, 2.0)
        self.assertAlmostEqual(r["St_crossings"], 0.11, delta=0.002)
        self.assertAlmostEqual(r["St_spectrum"], 0.11, delta=0.03)       # 2 s record: df = 0.5 Hz, St step 0.05
        self.assertGreaterEqual(r["periods"], 2)
        short = self.tr.strouhal(t, cs, U, L, 1.0, 2.0)                  # 1.1 periods in the window
        self.assertIsNone(short["St_crossings"])
        self.assertIsNone(short["St_spectrum"])
        self.assertEqual(short["verdict"], "not measurable")


class FrameExport(unittest.TestCase):
    """TRANSIENT T1 Stage 3: frames from processor fields, interpolation weights computed once."""

    @classmethod
    def setUpClass(cls):
        global np
        import numpy as np
        cls.ef = importlib.import_module("wind_tunnel.export_field")

    def test_gather_cells_in_global_order(self):
        parts = [(np.array([3, 0]), np.array([30.0, 0.0])), (np.array([1, 2]), np.array([10.0, 20.0]))]
        np.testing.assert_array_equal(self.ef.gather_cells(parts, 4), [0.0, 10.0, 20.0, 30.0])
        vec = [(np.array([1, 0]), np.array([[1.0, 1, 1], [0, 0, 0]]))]
        np.testing.assert_array_equal(self.ef.gather_cells(vec, 2), [[0, 0, 0], [1, 1, 1]])

    def test_gather_cells_must_cover_every_cell(self):
        with self.assertRaises(ValueError):
            self.ef.gather_cells([(np.array([0, 2]), np.array([1.0, 2.0]))], 3)

    def test_idw_weights_cached_and_exact_at_a_centre(self):
        cc = np.array([[0.0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1]])
        q = np.array([[1.0, 0, 0], [0.3, 0.3, 0.3]])
        idx, w = self.ef.idw_weights(cc, q, dtype=np.float32)
        self.assertEqual((idx.dtype, w.dtype), (np.dtype(np.int32), np.dtype(np.float32)))
        np.testing.assert_allclose(w.sum(axis=1), 1.0, rtol=1e-6)
        vals = np.array([5.0, 7.0, 1.0, 2.0, 3.0])
        self.assertAlmostEqual(float(self.ef.idw_apply(vals, idx, w)[0]), 7.0, places=5)
        U = np.column_stack([vals, 2 * vals, 0 * vals])
        np.testing.assert_allclose(self.ef.idw_apply(U, idx, w)[0], [7.0, 14.0, 0.0], rtol=1e-6)

    def test_frame_dirs_are_matched_by_time(self):
        with tempfile.TemporaryDirectory() as d:
            p0 = Path(d) / "processor0"
            for name in ("0", "0.016666667", "0.0175", "0.033333333", "0.5", "constant"):
                (p0 / name).mkdir(parents=True)
            for name in ("0.016666667", "0.033333333", "0.5"):
                (p0 / name / "U").write_text("x")
            self.assertEqual(self.ef.frame_dirs(Path(d)), {1: "0.016666667", 2: "0.033333333", 30: "0.5"})


class Step0Check(unittest.TestCase):
    def test_nu_read_from_case(self):
        spec = importlib.util.spec_from_file_location("step0_check", REPO / "tools" / "audit" / "step0_check.py")
        sc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sc)
        with tempfile.TemporaryDirectory() as d:
            con = Path(d) / "constant"
            con.mkdir()
            (con / "transportProperties").write_text(
                "FoamFile\n{\n    version 2.0;\n    object transportProperties;\n}\n"
                "transportModel Newtonian;\nnu 1.8e-05;\n")
            self.assertEqual(sc.case_nu(Path(d)), 1.8e-5)


if __name__ == "__main__":
    unittest.main()
