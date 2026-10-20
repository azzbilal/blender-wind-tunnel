"""Tests for the add-on's pure-Python modules (no Blender, no WSL, no OpenFOAM).

Run from the repo root:   py -m unittest discover -s tests -v

The package __init__ imports bpy, so the modules are loaded through a stub package that
skips it. Tests marked expectedFailure encode accuracy targets from docs/FIX_PLAN.md that the
current code does not meet yet: when a fix lands they start "unexpectedly succeeding", which
is the signal to remove the marker.
"""
from __future__ import annotations

import importlib
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
