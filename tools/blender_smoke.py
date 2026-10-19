"""Headless Blender check of the add-on in this repo (no OpenFOAM run).

    "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup \
        --python-exit-code 1 --python tools/blender_smoke.py

Loads wind_tunnel from this repo (not the installed copy), registers it, builds a NACA
airfoil, builds the 3D node trees, writes a 3D case for a cube, then unregisters.
Prints one JSON line starting with SMOKE and exits non-zero on any failure.
"""
import json
import sys
import tempfile
import traceback
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
for k in [k for k in sys.modules if k == "wind_tunnel" or k.startswith("wind_tunnel.")]:
    del sys.modules[k]

import bpy  # noqa: E402

report, ok = {}, True
try:
    import wind_tunnel as wt
    from wind_tunnel import case3d, viz3d

    report["source"] = str(Path(wt.__file__).parent)
    report["version"] = list(wt.bl_info["version"])
    wt.register()
    report["registered"] = hasattr(bpy.context.scene, "wind_tunnel")

    ob = wt.build_airfoil("0012")
    report["airfoil_vertices"] = len(ob.data.vertices)

    for name, fn in (("smoke", viz3d._smoke_tree), ("slice", viz3d._slice_tree)):
        tree = fn()
        bad = [(l.from_node.bl_idname, l.to_node.bl_idname) for l in tree.links if not l.is_valid]
        report[f"{name}_nodes"] = len(tree.nodes)
        report[f"{name}_invalid_links"] = bad
        ok &= not bad

    bpy.ops.mesh.primitive_cube_add(size=2.0)
    cube = bpy.context.active_object
    tris = viz3d.object_triangles(cube)
    with tempfile.TemporaryDirectory() as d:
        script, t = case3d.write_case(Path(d) / "3d_Cube", tris, case3d.Setup3D())
        report["case3d_cells_background"] = t["n"]
        report["case3d_files"] = sum(1 for _ in (Path(d) / "3d_Cube").rglob("*") if _.is_file())

    wt.unregister()
    report["unregistered"] = not hasattr(bpy.types.Scene, "wind_tunnel")
except Exception:
    ok = False
    report["error"] = traceback.format_exc()[-2000:]

report["ok"] = bool(ok)
print("SMOKE " + json.dumps(report))
sys.exit(0 if ok else 1)
