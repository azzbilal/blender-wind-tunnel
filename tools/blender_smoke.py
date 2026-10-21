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
import numpy as np  # noqa: E402


def _field(path, solid_cube, cp_slope=0.1):
    """Synthetic field.npz on the _anim/Cube grid: U = (20, 0, 0), Cp = cp_slope * x, optional solid cube."""
    h, o = 0.05, np.array([-2.5, -2.5, -2.5])
    gx, gy = o[0] + h * np.arange(171), o[1] + h * np.arange(101)
    X = gx[:, None, None] + 0 * gy[None, :, None] + 0 * gy[None, None, :]
    solid = np.zeros(X.shape, bool)
    if solid_cube:
        a = lambda g: np.abs(g) <= 1.0 + 1e-9
        solid = a(gx)[:, None, None] & a(gy)[None, :, None] & a(gy)[None, None, :]
    U = np.zeros(X.shape + (3,), np.float32)
    U[..., 0] = 20.0
    p = (cp_slope * X * 0.5 * 1.225 * 20.0 ** 2).astype(np.float32)
    U[solid], p[solid] = 0.0, 0.0
    np.savez_compressed(path, origin=o, voxel=h, U=U, p=p, solid=solid, speed=20.0, p_inf_Pa=0.0)
    return solid


def _points(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.data                                            # keeps the materials the nodes set
    co = np.empty(3 * len(me.vertices), np.float32)
    me.vertices.foreach_get("co", co)
    attrs = {}
    for name in ("cp", "show", "speed"):
        if name in me.attributes:
            a = np.empty(len(me.vertices), np.float32)
            me.attributes[name].data.foreach_get("value", a)
            attrs[name] = a
    mats = sorted({me.materials[p.material_index].name for p in me.polygons} if me.polygons else set())
    return co.reshape(-1, 3), attrs, mats, len(me.polygons)


def _strings_match(viz3d, cases):
    """Builds the label and tick strings in nodes with constant inputs and compares each with the
    pure text (STRING Compare stored on one vertex)."""
    tree = viz3d._new_tree("WT probe")
    viz3d._sock(tree, "Geometry", "NodeSocketGeometry", out=True)
    go = tree.nodes.new("NodeGroupOutput")
    geo = tree.nodes.new("GeometryNodeMeshLine")
    geo.inputs["Count"].default_value = 1
    out = geo.outputs["Mesh"]
    for k, (sock, expect) in enumerate(cases(tree)):
        c = tree.nodes.new("FunctionNodeCompare")
        c.data_type, c.operation = "STRING", "EQUAL"
        tree.links.new(sock, c.inputs[0])
        c.inputs[1].default_value = expect
        out = viz3d._store(tree, out, f"ok{k}", c.outputs["Result"], "BOOLEAN")
    tree.links.new(out, go.inputs["Geometry"])
    ob = bpy.data.objects.new("WT probe", bpy.data.meshes.new("WT probe"))
    bpy.context.scene.collection.objects.link(ob)
    ob.modifiers.new("n", "NODES").node_group = tree
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    res = [bool(me.attributes[a].data[0].value) for a in sorted(me.attributes.keys()) if a.startswith("ok")]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    return res


def anim_checks(report, cube):
    """ANIMATION A+B Stage 3 (spec docs/reference/anim_ab_spec.md)."""
    import wind_tunnel as wt
    from wind_tunnel import anim, viz3d
    # The add-on hides WT Slice unless the loaded field is the Test Object's solved one; this
    # synthetic field is not, so its handler is out of the way for these checks.
    hs = bpy.app.handlers.depsgraph_update_post
    if wt._on_depsgraph in hs:
        hs.remove(wt._on_depsgraph)
    ok = True
    scene = bpy.context.scene
    scene.render.fps = 24
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        solid = _field(d / "field.npz", True)
        lo, hi, U = viz3d.write_vdb(d / "field.npz", d / "flow.vdb")
        viz3d.load_volume(d / "flow.vdb")
        report["vdb_grids"] = sorted(g.name for g in bpy.data.volumes[viz3d.FLOW].grids)
        ok &= "fluid" in report["vdb_grids"]
        sl = viz3d.build_slice(lo, hi, (-1, -1, -1), (1, 1, 1))
        for name in (viz3d.SLICE, viz3d.LEGEND, viz3d.LABEL):
            bpy.data.objects[name].hide_viewport = bpy.data.objects[name].hide_render = False
        mod = sl.modifiers["Wind Tunnel"]
        for name, tree in (("legend", bpy.data.node_groups["WT Legend"]), ("label", bpy.data.node_groups["WT Label"])):
            bad = [(l.from_node.bl_idname, l.to_node.bl_idname) for l in tree.links if not l.is_valid]
            report[f"{name}_invalid_links"] = bad
            ok &= not bad

        # Cp mode: diverging material on the slice and the legend, its ramp read back equals CP_STOPS.
        viz3d.set_input(mod, "Pressure", True)
        pts, attrs, mats, _ = _points(sl)
        _, _, leg_mats, leg_faces = _points(bpy.data.objects[viz3d.LEGEND])
        _, _, _, lab_faces = _points(bpy.data.objects[viz3d.LABEL])
        ramp = next(n for n in bpy.data.materials["WT Slice Cp"].node_tree.nodes if n.type == "VALTORGB")
        back = [(e.position, tuple(e.color[:3])) for e in ramp.color_ramp.elements]
        ramp_ok = len(back) == 9 and all(abs(a - b) < 1e-4 and np.allclose(ca, cb, atol=1e-4)
                                         for (a, ca), (b, cb) in zip(back, anim.CP_STOPS))
        world = np.array(sl.matrix_world)
        P = pts @ world[:3, :3].T + world[:3, 3]
        real = attrs["speed"] > 0.5                         # not the loose vertex (speed 0)
        rest = np.array([v.co for v in sl.data.vertices]) @ world[:3, :3].T + world[:3, 3]
        keep = anim.slice_keep(rest, (-2.5, -2.5, -2.5), 0.05, solid)
        body = np.all(np.abs(P[real]) < 1.05, axis=1) & (np.abs(P[real, 1]) < 1.0)
        report["cp_mode"] = {"slice_materials": mats, "legend_materials": leg_mats, "ramp_equals_stops": ramp_ok,
                             "legend_faces": leg_faces, "label_faces": lab_faces,
                             "kept": int(real.sum()), "loose": int((~real).sum()), "kept_pure": int(keep.sum()),
                             "cp_err_max": float(np.abs(attrs["cp"][real] - 0.1 * P[real, 0]).max()),
                             "show_err_max": float(max(abs(s - anim.cp_to_ramp(c)) for s, c in
                                                       zip(attrs["show"][real], attrs["cp"][real]))),
                             "vertices_in_body_layer": int(body.sum())}
        c = report["cp_mode"]
        ok &= (mats == ["WT Slice Cp"] and leg_mats == ["WT Slice Cp", "WT Text"] and ramp_ok and leg_faces > 0
               and lab_faces > 0 and c["kept"] == c["kept_pure"] and c["loose"] == 1 and c["cp_err_max"] < 1e-5
               and c["show_err_max"] < 1e-6 and c["vertices_in_body_layer"] == 0)
        viz3d.set_input(mod, "Pressure", False)
        report["speed_mode_materials"] = _points(sl)[2]
        ok &= report["speed_mode_materials"] == ["WT Slice"]

        # Label and tick text: nodes equal the pure functions.
        cases = lambda t: [(viz3d._label_string(t, "y", 0.85, 0.85 / 2.0, True), anim.label_text("Y", 0.85, 2.0, True)),
                           (viz3d._label_string(t, "x", -2.0, -1.0, False), anim.label_text("X", -2.0, 2.0, False))] + \
            [(s, txt) for pr, lo_, hi_ in ((True, -1.0, 1.0), (True, -2.0, 1.0), (False, -1.0, 1.0))
             for s, (_, txt) in zip(viz3d._tick_strings(t, pr, lo_, hi_), anim.legend_ticks(pr, lo_, hi_))]
        report["strings_match"] = _strings_match(viz3d, cases)
        ok &= len(report["strings_match"]) == 17 and all(report["strings_match"])

        # Sweep keyframes: ping-pong over +-2.0 m in y, read back by the renderer's frame evaluation.
        keys = viz3d.animate_slice("Y", 192, scene)
        got = {}
        for f in (1, 49, 97, 145, 192):
            scene.frame_set(f)
            got[f] = round(sl.matrix_world.translation.y, 6)
        want = {f: round(keys[f - 1][1][1], 6) for f in got}
        report["sweep_y"] = {"got": got, "want": want, "frame_end": scene.frame_end}
        ok &= got == want and want[1] == -2.0 and want[97] == 2.0 and scene.frame_end == 192
        viz3d.animate_slice("Y", 192, scene)               # replaces, never stacks
        fcs = [fc for fc in _fcurves(sl)]
        report["sweep_fcurves"] = [(fc.data_path, fc.array_index, len(fc.keyframe_points)) for fc in fcs]
        ok &= len(fcs) == 3 and all(len(fc.keyframe_points) == 192 for fc in fcs)
        viz3d.clear_slice_animation()
        report["cleared"] = sl.animation_data is None and tuple(sl.location) == tuple(sl["wt_rest"])
        ok &= report["cleared"]

        # Smoke: solved mode moves by the field only (no slide, no push back); preview keeps both (Q4).
        _field(d / "uniform.npz", False)
        viz3d.write_vdb(d / "uniform.npz", d / "uniform.vdb")
        viz3d.load_volume(d / "uniform.vdb")
        report["smoke"] = _smoke_steps(viz3d, cube)
        s = report["smoke"]
        ok &= (s["use_field_nots"] == 1 and abs(s["solved"][0][0] - 0.0667) < 1e-3 and s["solved"][0][1:] == [0.0, 0.0]
               and abs(s["preview"][1][0] - 0.0667) < 1e-3 and s["preview"][1][1:] == [0.0, 0.0]
               and s["preview_x_end"][2] < -1.0)
    viz3d.remove_all()
    hs.append(wt._on_depsgraph)
    return bool(ok)


def _fcurves(ob):
    from bpy_extras import anim_utils
    ad = ob.animation_data
    return list(anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot).fcurves)


def _smoke_steps(viz3d, cube):
    """One step from frame 1 to 2 for three injected particles, solved and preview mode:
    A 3 cm in front of the front face, B the Q4 edge case, C 1 mm inside the front face."""
    start = [(-1.03, 0.3, 0.2), (-1.066, -1.467, -0.25), (-0.999, 0.3, 0.2)]
    smoke = viz3d.build_smoke(cube, 2.0, 20.0, 24, use_field=True)
    smoke.data.from_pydata(start, [], [])
    mod = smoke.modifiers["Wind Tunnel"]
    tree = mod.node_group
    N = tree.nodes
    gi = next(n for n in N if n.bl_idname == "NodeGroupInput")
    nots = [n for n in N if n.bl_idname == "FunctionNodeBooleanMath" and n.operation == "NOT"
            and any(l.from_node == gi and l.from_socket.name == "Use Field" for l in n.inputs[0].links)]
    sim_in = next(n for n in N if n.bl_idname == "GeometryNodeSimulationInput")
    sim_out = next(n for n in N if n.bl_idname == "GeometryNodeSimulationOutput")
    m2p = N.new("GeometryNodeMeshToPoints")
    tree.links.new(gi.outputs["Geometry"], m2p.inputs["Mesh"])
    tree.links.new(m2p.outputs["Points"], sim_in.inputs["Geometry"])
    go = next(n for n in N if n.bl_idname == "NodeGroupOutput")
    p2v = N.new("GeometryNodePointsToVertices")
    tree.links.new(sim_out.outputs["Geometry"], p2v.inputs["Points"])
    tree.links.new(p2v.outputs["Mesh"], go.inputs["Geometry"])
    viz3d.set_input(mod, "Rate", 0.0)
    scene = bpy.context.scene
    scene.frame_start = 1
    res = {"use_field_nots": len(nots), "time_scale": viz3d.get_input(mod, "Time Scale")}
    for mode, use in (("solved", True), ("preview", False)):
        viz3d.set_input(mod, "Use Field", use)
        scene.frame_set(1)
        p1 = _points(smoke)[0]
        scene.frame_set(2)
        p2 = _points(smoke)[0]
        res[mode] = [[round(float(v), 4) for v in (b - a)] for a, b in zip(p1, p2)]
        res[mode + "_x_end"] = [round(float(b[0]), 4) for b in p2]
        res[mode + "_n"] = [len(p1), len(p2)]
    return res


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

    ok &= anim_checks(report, cube)

    wt.unregister()
    report["unregistered"] = not hasattr(bpy.types.Scene, "wind_tunnel")
except Exception:
    ok = False
    report["error"] = traceback.format_exc()[-2000:]

report["ok"] = bool(ok)
print("SMOKE " + json.dumps(report))
sys.exit(0 if ok else 1)
