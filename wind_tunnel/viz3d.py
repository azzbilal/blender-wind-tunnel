"""3D flow in Blender: OpenFOAM's solved field plus the Test Object assigned in the node setup.

  "WT Flow"   a Volume object holding the OpenFOAM result as OpenVDB grids:
              velocity (m/s), speed (|U| / U_inf), cp (pressure coefficient)
  "WT Smoke"  Geometry Nodes Simulation Zone with a Test Object field. Every frame, new particles appear
              on a plane upstream of the Test Object (sized from its bounding box) and every particle
              moves by the velocity it samples from the grid (midpoint rule), or by the plain wind in
              preview. Near the Test Object the inward part of the velocity is removed, so particles
              slide along whatever shape is assigned, at once, before any solve.
  "WT Slice"  a plane that samples the grid at its vertices and colours itself by speed or Cp
              (diverging ramp centred on Cp = 0); move and rotate it anywhere, like a cutting plane in
              ParaView. It shows only vertices whose eight grid corners are fluid ("fluid" grid), so it
              ends at the grid edge and about one voxel off the body. "Animate slice" sweeps it.
  "WT Legend" colour strip and ticks by the top edge of the grid, read from WT Slice's own inputs
  "WT Label"  "Slice y = +0.85 m (+0.43 L) | Cp", from WT Slice's location

OpenVDB grids in flow.vdb: velocity (m/s), speed (|U| / U_inf), cp, fluid (1 at fluid nodes, 0 in the
solid mask; outside the grid the background is 0).
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np

from . import anim, transient
from .viz import SPEED_RANGE, SPEED_STOPS, _emission_material, _fresh_mesh, _math, _ramp

FLOW, RAKE, SMOKE, SLICE = "WT Flow", "WT Rake", "WT Smoke", "WT Slice"
LEGEND, LABEL = "WT Legend", "WT Label"


# ---------------------------------------------------------------- Blender mesh -> STL triangles
def object_triangles(ob, depsgraph=None):
    """World-space triangles of the evaluated object (modifiers applied)."""
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        me.calc_loop_triangles()
        mw = ob.matrix_world
        co = [mw @ v.co for v in me.vertices]
        return [tuple(tuple(co[i]) for i in t.vertices) for t in me.loop_triangles]
    finally:
        ev.to_mesh_clear()


# ---------------------------------------------------------------- field.npz -> OpenVDB
def write_vdb(npz: Path, vdb: Path, rho: float = 1.225):
    import openvdb
    d = np.load(npz)
    U = d["U"].astype(np.float32)
    speed_inf = float(d["speed"])
    h = float(d["voxel"])
    ox, oy, oz = (float(v) for v in d["origin"])
    q = 0.5 * rho * speed_inf ** 2
    xf = openvdb.createLinearTransform([[h, 0, 0, 0], [0, h, 0, 0], [0, 0, h, 0], [ox, oy, oz, 1]])
    grids = []
    g = openvdb.Vec3SGrid()
    g.copyFromArray(U)
    g.name, g.transform = "velocity", xf
    grids.append(g)
    sp = openvdb.FloatGrid()
    sp.copyFromArray((np.linalg.norm(U, axis=-1) / speed_inf).astype(np.float32))
    sp.name, sp.transform = "speed", xf
    grids.append(sp)
    cp = openvdb.FloatGrid()
    cp.copyFromArray((d["p"] / q).astype(np.float32))
    cp.name, cp.transform = "cp", xf
    grids.append(cp)
    fl = openvdb.FloatGrid()
    fl.copyFromArray((~d["solid"].astype(bool)).astype(np.float32))
    fl.name, fl.transform = "fluid", xf
    grids.append(fl)
    openvdb.write(str(vdb), grids=grids)
    lo = np.array([ox, oy, oz])
    return lo, lo + h * (np.array(U.shape[:3]) - 1), speed_inf


def _link(ob, collection=None):
    col = collection or bpy.context.scene.collection
    if ob.name not in col.objects:
        col.objects.link(ob)
    return ob


def load_volume(vdb: Path, sequence: int | None = None):
    """WT Flow from one VDB, or with sequence = n from flow_0001.vdb .. flow_000n.vdb (scene frame k
    loads frame k, transient.vdb_sequence)."""
    vol = bpy.data.volumes.get(FLOW) or bpy.data.volumes.new(FLOW)
    vol.filepath = str(vdb)
    seq = transient.vdb_sequence(sequence) if sequence else {"is_sequence": False}
    for key, v in seq.items():
        setattr(vol, key, v)
    if sequence:
        # The original datablock has no scene frame (a load would look for flow_0000.vdb and keep the
        # failure); each evaluated frame loads its own file.
        vol.grids.unload()
    else:
        vol.grids.load()
    ob = bpy.data.objects.get(FLOW) or _link(bpy.data.objects.new(FLOW, vol))
    ob.data = vol
    ob.display_type = "BOUNDS"
    ob.hide_render = True
    # The volume only carries data for the node trees: an empty material so it never draws as fog.
    mat = bpy.data.materials.get("WT Data only") or bpy.data.materials.new("WT Data only")
    mat.use_nodes = True
    for n in [n for n in mat.node_tree.nodes if n.type != "OUTPUT_MATERIAL"]:
        mat.node_tree.nodes.remove(n)
    if mat.name not in vol.materials:
        vol.materials.clear()
        vol.materials.append(mat)
    if hasattr(vol, "display"):
        vol.display.density = 0.0
    return ob


# ---------------------------------------------------------------- rake and slice planes
def _plane(name, size_a, size_b, axis, centre, res=(1, 1)):
    """A plane of size_a x size_b, normal along `axis` ('X' or 'Y'), res cells each way."""
    na, nb = res
    verts = []
    for j in range(nb + 1):
        for i in range(na + 1):
            a = (i / na - 0.5) * size_a
            b = (j / nb - 0.5) * size_b
            verts.append((0.0, a, b) if axis == "X" else (a, 0.0, b))
    faces = [(j * (na + 1) + i, j * (na + 1) + i + 1, (j + 1) * (na + 1) + i + 1, (j + 1) * (na + 1) + i)
             for j in range(nb) for i in range(na)]
    me = _fresh_mesh(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.get(name) or _link(bpy.data.objects.new(name, me))
    ob.data = me
    ob.location = centre
    return ob


def build_rake(lo, hi, L):
    """Release plane half a body length upstream, a little larger than the body's frontal outline."""
    cy, cz = (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2
    ob = _plane(RAKE, (hi[1] - lo[1]) + 0.4 * L, (hi[2] - lo[2]) + 0.4 * L, "X", (lo[0] - 0.5 * L, cy, cz))
    ob.display_type = "WIRE"
    ob.hide_render = True
    return ob


def build_slice(box_lo, box_hi, body_lo, body_hi, voxel=None):
    """WT Slice through the body centre (normal Y), plus WT Legend and WT Label that read it."""
    cy = (body_lo[1] + body_hi[1]) / 2
    sx, sz = box_hi[0] - box_lo[0], box_hi[2] - box_lo[2]
    centre = ((box_lo[0] + box_hi[0]) / 2, cy, (box_lo[2] + box_hi[2]) / 2)
    ob = _plane(SLICE, sx, sz, "Y", centre, res=(int(min(400, sx / sz * 160)), 160))
    ob.rotation_euler = (0.0, 0.0, 0.0)
    vol = bpy.data.volumes.get(FLOW)
    grid = vol.grids.get("cp") if vol is not None else None
    h = voxel or (float(grid.matrix_object[0][0]) if grid is not None else (box_hi[0] - box_lo[0]) / 170)
    for key, v in (("wt_grid_lo", box_lo), ("wt_grid_hi", box_hi), ("wt_body_lo", body_lo),
                   ("wt_body_hi", body_hi), ("wt_rest", centre)):
        ob[key] = [float(x) for x in v]
    ob["wt_voxel"] = h
    tree = _slice_tree()
    mod = ob.modifiers.get("Wind Tunnel") or ob.modifiers.new("Wind Tunnel", "NODES")
    mod.node_group = tree
    _set_input(mod, tree, "Flow", bpy.data.objects[FLOW])
    _set_input(mod, tree, "Cp Lo", anim.CP_RANGE[0])
    _set_input(mod, tree, "Cp Hi", anim.CP_RANGE[1])
    build_legend(ob, box_hi, body_lo, body_hi)
    return ob


def _overlay(name, tree, inputs):
    """An empty mesh object at the world origin whose node tree draws everything in world space."""
    me = _fresh_mesh(name)
    ob = bpy.data.objects.get(name) or _link(bpy.data.objects.new(name, me))
    ob.data = me
    ob.location, ob.rotation_euler, ob.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    mod = ob.modifiers.get("Wind Tunnel") or ob.modifiers.new("Wind Tunnel", "NODES")
    mod.node_group = tree
    for k, v in inputs.items():
        _set_input(mod, tree, k, v)
    return ob


def build_legend(slice_ob, box_hi, body_lo, body_hi):
    """WT Legend (strip 2 L long above the grid's top edge, in the XZ plane through the body centre,
    facing -Y) and WT Label above it."""
    c = [(body_lo[i] + body_hi[i]) / 2 for i in range(3)]
    L = max(body_hi[i] - body_lo[i] for i in range(3))
    origin = (c[0] - L, c[1], box_hi[2] + 0.2 * L)
    legend = _overlay(LEGEND, _legend_tree(), {"Slice": slice_ob, "Origin": origin, "Length": 2 * L,
                                               "Height": 0.08 * L, "Text Size": 0.07 * L})
    label = _overlay(LABEL, _label_tree(), {"Slice": slice_ob, "Axis": 1, "Centre": c, "L": L,
                                            "Origin": (origin[0], origin[1], origin[2] + 0.18 * L),
                                            "Text Size": 0.09 * L})
    return legend, label


# ---------------------------------------------------------------- slice sweep (spec Q1)
SWEEP_ROTATION = {"X": (0.0, 0.0, math.pi / 2), "Y": (0.0, 0.0, 0.0), "Z": (math.pi / 2, 0.0, 0.0)}


def clear_slice_animation(ob=None):
    """Removes the sweep keyframes and puts WT Slice back at rest (normal Y, through the body)."""
    ob = ob or bpy.data.objects.get(SLICE)
    if ob is None:
        return None
    ob.animation_data_clear()
    if "wt_rest" in ob:
        ob.location = tuple(ob["wt_rest"])
    ob.rotation_euler = SWEEP_ROTATION["Y"]
    lab = bpy.data.objects.get(LABEL)
    if lab is not None and lab.modifiers.get("Wind Tunnel"):
        set_input(lab.modifiers["Wind Tunnel"], "Axis", 1)
    return ob


def animate_slice(axis="Y", frames=192, scene=None):
    """One location keyframe per frame on WT Slice: ping-pong over +-1 L about the body centre along
    `axis`, kept 10 voxels inside the grid (anim.sweep_*). Replaces earlier keyframes; sets the scene
    range to 1..frames. Returns the keyframes."""
    scene = scene or bpy.context.scene
    ob = clear_slice_animation()
    blo, bhi = ob["wt_body_lo"], ob["wt_body_hi"]
    centre = [(blo[i] + bhi[i]) / 2 for i in range(3)]
    L = max(bhi[i] - blo[i] for i in range(3))
    R = anim.sweep_half_range(axis, centre, L, ob["wt_grid_lo"], ob["wt_grid_hi"], ob["wt_voxel"])
    i = "XYZ".index(axis)
    start = list(ob["wt_rest"])
    start[i] = centre[i]
    keys = anim.sweep_keyframes(axis, start, R, frames, True)
    ob.rotation_euler = SWEEP_ROTATION[axis]
    prefs = bpy.context.preferences.edit
    old = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    try:
        for f, loc in keys:
            ob.location = loc
            ob.keyframe_insert("location", frame=f)
    finally:
        prefs.keyframe_new_interpolation_type = old
    lab = bpy.data.objects.get(LABEL)
    if lab is not None and lab.modifiers.get("Wind Tunnel"):
        set_input(lab.modifiers["Wind Tunnel"], "Axis", i)
    scene.frame_start, scene.frame_end = 1, frames
    return keys


# ---------------------------------------------------------------- node helpers
def _new_tree(name):
    tree = bpy.data.node_groups.get(name)
    if tree is None:
        tree = bpy.data.node_groups.new(name, "GeometryNodeTree")
    tree.nodes.clear()
    tree.interface.clear()
    return tree


def _sock(tree, name, kind, default=None, out=False, lo=None, hi=None):
    s = tree.interface.new_socket(name, in_out="OUTPUT" if out else "INPUT", socket_type=kind)
    if default is not None and hasattr(s, "default_value"):
        s.default_value = default
    if lo is not None and hasattr(s, "min_value"):
        s.min_value = lo
    if hi is not None and hasattr(s, "max_value"):
        s.max_value = hi
    return s


def _set_input(mod, tree, name, value):
    """Sets a modifier input by its socket name (Blender 5.x: modifier.properties.inputs, older: ID properties)."""
    for item in tree.interface.items_tree:
        if getattr(item, "in_out", None) == "INPUT" and item.name == name:
            props = getattr(mod, "properties", None)
            if props is not None and hasattr(props, "inputs"):
                getattr(props.inputs, item.identifier).value = value
            else:
                mod[item.identifier] = value
            mod.id_data.update_tag()                        # re-evaluate the object now
            return


def _grid(tree, volume_geo, name, dtype):
    g = tree.nodes.new("GeometryNodeGetNamedGrid")
    g.data_type = dtype
    g.inputs["Name"].default_value = name
    tree.links.new(volume_geo, g.inputs["Volume"])
    return g.outputs["Grid"]


def _sample(tree, grid, position, dtype):
    s = tree.nodes.new("GeometryNodeSampleGrid")
    s.data_type = dtype
    tree.links.new(grid, s.inputs["Grid"])
    tree.links.new(position, s.inputs["Position"])
    return s.outputs["Value"]


def _vmath(tree, op, a, b=None, scale=None):
    n = tree.nodes.new("ShaderNodeVectorMath")
    n.operation = op
    tree.links.new(a, n.inputs[0])
    if b is not None:
        if isinstance(b, (tuple, list)):
            n.inputs[1].default_value = b
        else:
            tree.links.new(b, n.inputs[1])
    if scale is not None:
        if isinstance(scale, (int, float)):
            n.inputs["Scale"].default_value = scale
        else:
            tree.links.new(scale, n.inputs["Scale"])
    return n.outputs["Value"] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else n.outputs["Vector"]


def _store(tree, geo, name, value, dtype="FLOAT"):
    st = tree.nodes.new("GeometryNodeStoreNamedAttribute")
    st.data_type, st.domain = dtype, "POINT"
    st.inputs["Name"].default_value = name
    tree.links.new(geo, st.inputs["Geometry"])
    tree.links.new(value, st.inputs["Value"])
    return st.outputs["Geometry"]


def _named(tree, name, dtype="FLOAT"):
    a = tree.nodes.new("GeometryNodeInputNamedAttribute")
    a.data_type = dtype
    a.inputs["Name"].default_value = name
    return a.outputs["Attribute"]


def _layout(tree):
    """Spreads nodes left to right by link depth so the tree is readable when opened."""
    depth = {n: 0 for n in tree.nodes}
    for _ in range(len(tree.nodes)):
        changed = False
        for l in tree.links:
            if depth[l.to_node] < depth[l.from_node] + 1:
                depth[l.to_node] = depth[l.from_node] + 1
                changed = True
        if not changed:
            break
    rows = {}
    for n, d in depth.items():
        k = rows.setdefault(d, 0)
        n.location = (d * 230, -k * 170)
        rows[d] = k + 1


# ---------------------------------------------------------------- smoke particles
def _vsw(tree, cond, if_false, if_true):
    """Vector switch."""
    sw = tree.nodes.new("GeometryNodeSwitch")
    sw.input_type = "VECTOR"
    tree.links.new(cond, sw.inputs["Switch"])
    for key, v in (("False", if_false), ("True", if_true)):
        if isinstance(v, (tuple, list)):
            sw.inputs[key].default_value = v
        else:
            tree.links.new(v, sw.inputs[key])
    return sw.outputs["Output"]


def _cmp(tree, op, a, b):
    """Float compare -> boolean."""
    c = tree.nodes.new("FunctionNodeCompare")
    c.data_type, c.operation = "FLOAT", op
    for k, v in enumerate((a, b)):
        if isinstance(v, (int, float)):
            c.inputs[k].default_value = v
        else:
            tree.links.new(v, c.inputs[k])
    return c.outputs["Result"]


def _bool(tree, op, a, b=None):
    n = tree.nodes.new("FunctionNodeBooleanMath")
    n.operation = op
    tree.links.new(a, n.inputs[0])
    if b is not None:
        tree.links.new(b, n.inputs[1])
    return n.outputs[0]


def _smoke_tree():
    """Particles that know the Test Object.

    Every step: velocity = the solved field (Use Field on) or the plain wind (preview). In preview
    only, near the Test Object the inward part of the wind is removed, so particles slide along its
    surface, and any particle that still ends up inside is put back on the surface; with the field
    on, particles in still air (speed < 0.02 U_inf, the solid) are removed instead. New particles come from
    a plane half a body length upstream, sized from the Test Object's bounding box.
    """
    tree = _new_tree("WT Smoke")
    _sock(tree, "Geometry", "NodeSocketGeometry")
    _sock(tree, "Test Object", "NodeSocketObject")
    _sock(tree, "Flow", "NodeSocketObject")
    _sock(tree, "Use Field", "NodeSocketBool", True)
    _sock(tree, "Wind", "NodeSocketVector", (20.0, 0.0, 0.0))
    _sock(tree, "Rate", "NodeSocketFloat", 40.0, lo=0.0)
    _sock(tree, "Lifetime", "NodeSocketFloat", 140.0, lo=1.0)
    _sock(tree, "Time Scale", "NodeSocketFloat", 0.05, lo=0.0)
    _sock(tree, "Radius", "NodeSocketFloat", 0.01, lo=0.0)
    # Time-resolved field (transient.plain_smoke_inputs): white, the frame step split into substeps,
    # each particle drawn as a streak |v| Trail long behind it (Trail 0: a dot).
    _sock(tree, "Plain", "NodeSocketBool", False)
    _sock(tree, "Substeps", "NodeSocketInt", 1, lo=1)
    _sock(tree, "Trail", "NodeSocketFloat", 0.0, lo=0.0)
    _sock(tree, "Geometry", "NodeSocketGeometry", out=True)
    gi = tree.nodes.new("NodeGroupInput")
    go = tree.nodes.new("NodeGroupOutput")
    P = lambda: tree.nodes.new("GeometryNodeInputPosition").outputs[0]

    body = tree.nodes.new("GeometryNodeObjectInfo")
    body.transform_space = "RELATIVE"
    tree.links.new(gi.outputs["Test Object"], body.inputs["Object"])
    body_geo = body.outputs["Geometry"]
    flow = tree.nodes.new("GeometryNodeObjectInfo")
    flow.transform_space = "RELATIVE"
    tree.links.new(gi.outputs["Flow"], flow.inputs["Object"])
    vel_grid = _grid(tree, flow.outputs["Geometry"], "velocity", "VECTOR")
    spd_grid = _grid(tree, flow.outputs["Geometry"], "speed", "FLOAT")

    # Size of the Test Object: L = largest side of its bounding box.
    bb = tree.nodes.new("GeometryNodeBoundBox")
    tree.links.new(body_geo, bb.inputs["Geometry"])
    size = _vmath(tree, "SUBTRACT", bb.outputs["Max"], bb.outputs["Min"])
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(size, sep.inputs[0])
    L = _math(tree, "MAXIMUM", _math(tree, "MAXIMUM", sep.outputs["X"], sep.outputs["Y"]), sep.outputs["Z"])
    centre = _vmath(tree, "SCALE", _vmath(tree, "ADD", bb.outputs["Max"], bb.outputs["Min"]), scale=0.5)
    margin = _math(tree, "MULTIPLY", L, 0.004)

    # Release plane: a grid facing +X, half a body length upstream, 20 % of L wider than the body.
    grid = tree.nodes.new("GeometryNodeMeshGrid")
    grid.inputs["Vertices X"].default_value = grid.inputs["Vertices Y"].default_value = 2
    tree.links.new(_math(tree, "ADD", sep.outputs["Z"], _math(tree, "MULTIPLY", L, 0.4)), grid.inputs["Size X"])
    tree.links.new(_math(tree, "ADD", sep.outputs["Y"], _math(tree, "MULTIPLY", L, 0.4)), grid.inputs["Size Y"])
    xf = tree.nodes.new("GeometryNodeTransform")
    tree.links.new(grid.outputs["Mesh"], xf.inputs["Geometry"])
    xf.inputs["Rotation"].default_value = (0.0, math.pi / 2, 0.0)
    minx = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(bb.outputs["Min"], minx.inputs[0])
    cen = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(centre, cen.inputs[0])
    at = tree.nodes.new("ShaderNodeCombineXYZ")
    tree.links.new(_math(tree, "SUBTRACT", minx.outputs["X"], _math(tree, "MULTIPLY", L, 0.5)), at.inputs["X"])
    tree.links.new(cen.outputs["Y"], at.inputs["Y"])
    tree.links.new(cen.outputs["Z"], at.inputs["Z"])
    tree.links.new(at.outputs[0], xf.inputs["Translation"])

    sim_in = tree.nodes.new("GeometryNodeSimulationInput")
    sim_out = tree.nodes.new("GeometryNodeSimulationOutput")
    sim_in.pair_with_output(sim_out)

    frame = tree.nodes.new("GeometryNodeInputSceneTime").outputs["Frame"]
    dist = tree.nodes.new("GeometryNodeDistributePointsOnFaces")
    dist.distribute_method = "RANDOM"
    tree.links.new(xf.outputs["Geometry"], dist.inputs["Mesh"])
    tree.links.new(gi.outputs["Rate"], dist.inputs["Density"])          # per square metre per frame
    tree.links.new(frame, dist.inputs["Seed"])
    born = _store(tree, dist.outputs["Points"], "age", _math(tree, "MULTIPLY", 0.0, 0.0))
    join = tree.nodes.new("GeometryNodeJoinGeometry")
    tree.links.new(sim_in.outputs["Geometry"], join.inputs["Geometry"])
    tree.links.new(born, join.inputs["Geometry"])

    # Velocity: the solved field (midpoint rule) or the plain wind; the frame step dt is taken in
    # Substeps equal steps inside a Repeat Zone.
    dt = _math(tree, "DIVIDE", _math(tree, "MULTIPLY", sim_in.outputs["Delta Time"], gi.outputs["Time Scale"]),
               gi.outputs["Substeps"])
    v1 = _sample(tree, vel_grid, P(), "VECTOR")
    mid = _vmath(tree, "ADD", P(), _vmath(tree, "SCALE", v1, scale=_math(tree, "MULTIPLY", dt, 0.5)))
    v2 = _sample(tree, vel_grid, mid, "VECTOR")
    v = _vsw(tree, gi.outputs["Use Field"], gi.outputs["Wind"], v2)

    # Preview only (Use Field off): within 0.05 L of the Test Object's surface (true distance), the
    # part of the wind towards the nearest surface point is removed, so particles slide along it.
    # With the field on, particles move by the solved velocity alone (spec Q3).
    preview = _bool(tree, "NOT", gi.outputs["Use Field"])
    near = tree.nodes.new("GeometryNodeProximity")
    near.target_element = "FACES"
    tree.links.new(body_geo, near.inputs["Geometry"])
    tree.links.new(P(), near.inputs["Source Position"])
    away = _vmath(tree, "NORMALIZE", _vmath(tree, "SUBTRACT", P(), near.outputs["Position"]))
    band = _cmp(tree, "LESS_THAN", near.outputs["Distance"], _math(tree, "MULTIPLY", L, 0.05))
    into = _math(tree, "MINIMUM", _vmath(tree, "DOT_PRODUCT", v, away), 0.0)
    slide = _vmath(tree, "SUBTRACT", v, _vmath(tree, "SCALE", away, scale=into))
    v_eff = _vsw(tree, _bool(tree, "AND", _bool(tree, "AND", near.outputs["Is Valid"], band), preview), v, slide)

    rep_in = tree.nodes.new("GeometryNodeRepeatInput")
    rep_out = tree.nodes.new("GeometryNodeRepeatOutput")
    rep_in.pair_with_output(rep_out)
    tree.links.new(gi.outputs["Substeps"], rep_in.inputs["Iterations"])
    tree.links.new(join.outputs["Geometry"], rep_in.inputs["Geometry"])
    move = tree.nodes.new("GeometryNodeSetPosition")
    tree.links.new(rep_in.outputs["Geometry"], move.inputs["Geometry"])
    tree.links.new(_vmath(tree, "SCALE", v_eff, scale=dt), move.inputs["Offset"])
    tree.links.new(move.outputs["Geometry"], rep_out.inputs["Geometry"])
    speed_now = _math(tree, "DIVIDE", _vmath(tree, "LENGTH", v_eff),
                      _math(tree, "MAXIMUM", _vmath(tree, "LENGTH", gi.outputs["Wind"]), 1e-6))
    stored = _store(tree, _store(tree, rep_out.outputs["Geometry"], "speed", speed_now), "vel", v_eff,
                    dtype="FLOAT_VECTOR")

    # Preview only: anything that still ended up inside goes back onto the surface.
    near2 = tree.nodes.new("GeometryNodeProximity")
    near2.target_element = "FACES"
    tree.links.new(body_geo, near2.inputs["Geometry"])
    tree.links.new(P(), near2.inputs["Source Position"])
    nrm2 = tree.nodes.new("GeometryNodeSampleNearestSurface")
    nrm2.data_type = "FLOAT_VECTOR"
    tree.links.new(body_geo, nrm2.inputs["Mesh"])
    tree.links.new(tree.nodes.new("GeometryNodeInputNormal").outputs[0], nrm2.inputs["Value"])
    tree.links.new(P(), nrm2.inputs["Sample Position"])
    n2 = _vmath(tree, "NORMALIZE", nrm2.outputs["Value"])
    gap2 = _vmath(tree, "DOT_PRODUCT", _vmath(tree, "SUBTRACT", P(), near2.outputs["Position"]), n2)
    inside = _bool(tree, "AND", _bool(tree, "AND", near2.outputs["Is Valid"], _cmp(tree, "LESS_THAN", gap2, margin)),
                   preview)
    fix = tree.nodes.new("GeometryNodeSetPosition")
    tree.links.new(stored, fix.inputs["Geometry"])
    tree.links.new(inside, fix.inputs["Selection"])
    tree.links.new(_vmath(tree, "ADD", near2.outputs["Position"], _vmath(tree, "SCALE", n2, scale=margin)),
                   fix.inputs["Position"])

    aged = _store(tree, fix.outputs["Geometry"], "age", _math(tree, "ADD", _named(tree, "age"), 1.0))
    # Remove old particles, and (with the field on) those in still air: off the grid or in a solid cell.
    old = _cmp(tree, "GREATER_THAN", _named(tree, "age"), gi.outputs["Lifetime"])
    still = _bool(tree, "AND", gi.outputs["Use Field"],
                  _cmp(tree, "LESS_THAN", _sample(tree, spd_grid, P(), "FLOAT"), 0.02))
    far = _cmp(tree, "GREATER_THAN", _vmath(tree, "DISTANCE", P(), centre), _math(tree, "MULTIPLY", L, 6.0))
    delete = tree.nodes.new("GeometryNodeDeleteGeometry")
    delete.domain = "POINT"
    tree.links.new(aged, delete.inputs["Geometry"])
    tree.links.new(_bool(tree, "OR", _bool(tree, "OR", old, still), far), delete.inputs["Selection"])
    tree.links.new(delete.outputs["Geometry"], sim_out.inputs["Geometry"])

    ico = tree.nodes.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Subdivisions"].default_value = 1
    tree.links.new(gi.outputs["Radius"], ico.inputs["Radius"])
    # Streak: a unit-long thin cylinder along +X from x = -1 to 0, turned along the particle's velocity
    # and scaled to |v| Trail (at least two radii), so it ends at the particle.
    cyl = tree.nodes.new("GeometryNodeMeshCylinder")
    cyl.inputs["Vertices"].default_value = 6
    cyl.inputs["Depth"].default_value = 1.0
    tree.links.new(gi.outputs["Radius"], cyl.inputs["Radius"])
    cxf = tree.nodes.new("GeometryNodeTransform")
    tree.links.new(cyl.outputs["Mesh"], cxf.inputs["Geometry"])
    cxf.inputs["Rotation"].default_value = (0.0, math.pi / 2, 0.0)
    cxf.inputs["Translation"].default_value = (-0.5, 0.0, 0.0)
    streak = _cmp(tree, "GREATER_THAN", gi.outputs["Trail"], 0.0)
    shape = tree.nodes.new("GeometryNodeSwitch")
    shape.input_type = "GEOMETRY"
    tree.links.new(streak, shape.inputs["Switch"])
    tree.links.new(ico.outputs["Mesh"], shape.inputs["False"])
    tree.links.new(cxf.outputs["Geometry"], shape.inputs["True"])
    vel = _named(tree, "vel", "FLOAT_VECTOR")
    align = tree.nodes.new("FunctionNodeAlignRotationToVector")
    align.axis = "X"
    tree.links.new(vel, align.inputs["Vector"])
    length = _math(tree, "MAXIMUM", _math(tree, "MULTIPLY", _vmath(tree, "LENGTH", vel), gi.outputs["Trail"]),
                   _math(tree, "MULTIPLY", gi.outputs["Radius"], 2.0))
    sx = tree.nodes.new("ShaderNodeCombineXYZ")
    tree.links.new(length, sx.inputs["X"])
    sx.inputs["Y"].default_value = sx.inputs["Z"].default_value = 1.0
    one = tree.nodes.new("ShaderNodeCombineXYZ")
    one.inputs["X"].default_value = one.inputs["Y"].default_value = one.inputs["Z"].default_value = 1.0
    inst = tree.nodes.new("GeometryNodeInstanceOnPoints")
    tree.links.new(sim_out.outputs["Geometry"], inst.inputs["Points"])
    tree.links.new(shape.outputs["Output"], inst.inputs["Instance"])
    tree.links.new(_vsw(tree, streak, one.outputs[0], sx.outputs[0]), inst.inputs["Scale"])
    rot = tree.nodes.new("GeometryNodeSwitch")
    rot.input_type = "ROTATION"
    tree.links.new(streak, rot.inputs["Switch"])
    tree.links.new(align.outputs["Rotation"], rot.inputs["True"])
    tree.links.new(rot.outputs["Output"], inst.inputs["Rotation"])
    msw = tree.nodes.new("GeometryNodeSwitch")
    msw.input_type = "MATERIAL"
    tree.links.new(gi.outputs["Plain"], msw.inputs["Switch"])
    msw.inputs["False"].default_value = _emission_material("WT Smoke", "speed", 0.3, 1.9, 2.5, instancer=True)
    msw.inputs["True"].default_value = _emission_material("WT Smoke Plain", "speed", 0.0, 1.0, 1.0,
                                                          instancer=True, stops=[(0.0, (1.0, 1.0, 1.0))])
    setm = tree.nodes.new("GeometryNodeSetMaterial")
    tree.links.new(msw.outputs["Output"], setm.inputs["Material"])
    tree.links.new(inst.outputs["Instances"], setm.inputs["Geometry"])
    tree.links.new(setm.outputs["Geometry"], go.inputs["Geometry"])
    _layout(tree)
    return tree


def get_input(mod, name):
    """Value of a modifier input by its socket name, or None."""
    tree = mod.node_group
    if tree is None:
        return None
    for item in tree.interface.items_tree:
        if getattr(item, "in_out", None) == "INPUT" and item.name == name:
            props = getattr(mod, "properties", None)
            if props is not None and hasattr(props, "inputs"):
                return getattr(props.inputs, item.identifier).value
            return mod.get(item.identifier)
    return None


def smoke_modifier():
    ob = bpy.data.objects.get(SMOKE)
    return ob.modifiers.get("Wind Tunnel") if ob else None


def tune_smoke(mod, L, speed_inf, fps):
    """Scales release rate, particle size and time so freestream particles cross about L/30 per frame."""
    tree = mod.node_group
    _set_input(mod, tree, "Wind", (speed_inf, 0.0, 0.0))
    _set_input(mod, tree, "Rate", 150.0 / max(1.4 * L * 1.4 * L, 1e-6))   # about 150 new particles a frame
    _set_input(mod, tree, "Time Scale", (L / 30.0) / (speed_inf / fps))
    _set_input(mod, tree, "Radius", L / 250.0)


def build_smoke(body, L, speed_inf, fps, use_field=False):
    """The particle object, with `body` in its Test Object field."""
    me = _fresh_mesh(SMOKE)
    ob = bpy.data.objects.get(SMOKE) or _link(bpy.data.objects.new(SMOKE, me))
    ob.data = me
    tree = _smoke_tree()
    mod = ob.modifiers.get("Wind Tunnel") or ob.modifiers.new("Wind Tunnel", "NODES")
    mod.node_group = tree
    _set_input(mod, tree, "Test Object", body)
    _set_input(mod, tree, "Flow", bpy.data.objects.get(FLOW))
    _set_input(mod, tree, "Use Field", use_field)
    _set_input(mod, tree, "Lifetime", 140.0)
    tune_smoke(mod, L, speed_inf, fps)
    return ob


def build_transient(frames_dir: Path, body, n_frames, scene_fps, L, speed_inf, voxel, rho=1.225):
    """TRANSIENT T1 scene objects: flow_kkkk.vdb from every flow_kkkk.npz (written once), WT Flow as a
    VDB sequence, WT Slice through the body centre in Cp mode, the label with flow time, and plain
    smoke advected through the time-varying field. Returns (grid lo, grid hi)."""
    frames_dir = Path(frames_dir)
    lo = hi = None
    for k in range(1, n_frames + 1):
        npz, vdb = frames_dir / transient.frame_name(k, "npz"), frames_dir / transient.frame_name(k, "vdb")
        if not vdb.exists() or vdb.stat().st_mtime < npz.stat().st_mtime:
            lo, hi, _ = write_vdb(npz, vdb, rho)
    if lo is None:
        d = np.load(frames_dir / transient.frame_name(1, "npz"))
        lo = np.array(d["origin"], float)
        hi = lo + float(d["voxel"]) * (np.array(d["U"].shape[:3]) - 1)
    load_volume(frames_dir / transient.frame_name(1, "vdb"), sequence=n_frames)
    body_lo = [min(v[i] for v in (body.matrix_world @ c.co for c in body.data.vertices)) for i in range(3)]
    body_hi = [max(v[i] for v in (body.matrix_world @ c.co for c in body.data.vertices)) for i in range(3)]
    sl = build_slice(lo, hi, body_lo, body_hi, voxel=voxel)
    set_input(sl.modifiers["Wind Tunnel"], "Pressure", True)
    label = bpy.data.objects[LABEL].modifiers["Wind Tunnel"]
    set_input(label, "CFD fps", float(transient.FPS_CFD))
    set_input(label, "U", float(speed_inf))
    sm = build_smoke(body, L, speed_inf, scene_fps, use_field=True)
    for key, v in transient.plain_smoke_inputs(L, speed_inf, scene_fps, voxel).items():
        set_input(sm.modifiers["Wind Tunnel"], key, v)
    return lo, hi


def set_input(mod, name, value):
    _set_input(mod, mod.node_group, name, value)


# ---------------------------------------------------------------- slice, legend, label
def _ramp_coord(tree, pressure, spd, cp, lo, hi):
    """0..1 ramp coordinate: speed/U_inf over SPEED_RANGE, or anim.cp_to_ramp (two clamped Map Range
    nodes summed, so Cp = 0 is always 0.5)."""
    def mr(v, a, b, c, d):
        m = tree.nodes.new("ShaderNodeMapRange")
        m.clamp = True
        for key, x in (("Value", v), ("From Min", a), ("From Max", b), ("To Min", c), ("To Max", d)):
            if isinstance(x, (int, float)):
                m.inputs[key].default_value = x
            else:
                tree.links.new(x, m.inputs[key])
        return m.outputs["Result"]
    s_coord = mr(spd, SPEED_RANGE[0], SPEED_RANGE[1], 0.0, 1.0)
    cp_coord = _math(tree, "SUBTRACT", _math(tree, "ADD", mr(cp, lo, 0.0, 0.0, 0.5), mr(cp, 0.0, hi, 0.5, 1.0)), 0.5)
    sw = tree.nodes.new("GeometryNodeSwitch")
    sw.input_type = "FLOAT"
    tree.links.new(pressure, sw.inputs["Switch"])
    tree.links.new(s_coord, sw.inputs["False"])
    tree.links.new(cp_coord, sw.inputs["True"])
    return sw.outputs["Output"]


def _materials():
    """(speed, Cp, text) emission materials, strength exactly 1 so a Standard view shows the stops."""
    return (_emission_material("WT Slice", "show", 0.0, 1.0, 1.0),
            _emission_material("WT Slice Cp", "show", 0.0, 1.0, 1.0, stops=anim.CP_STOPS),
            _emission_material("WT Text", "show", 0.0, 1.0, 1.0, stops=[(0.0, (1.0, 1.0, 1.0))]))


def _set_mat(tree, geo, pressure, speed_mat, cp_mat):
    sw = tree.nodes.new("GeometryNodeSwitch")
    sw.input_type = "MATERIAL"
    tree.links.new(pressure, sw.inputs["Switch"])
    sw.inputs["False"].default_value, sw.inputs["True"].default_value = speed_mat, cp_mat
    setm = tree.nodes.new("GeometryNodeSetMaterial")
    tree.links.new(geo, setm.inputs["Geometry"])
    tree.links.new(sw.outputs["Output"], setm.inputs["Material"])
    return setm.outputs["Geometry"]


def _slice_tree():
    tree = _new_tree("WT Slice")
    _sock(tree, "Geometry", "NodeSocketGeometry")
    _sock(tree, "Flow", "NodeSocketObject")
    _sock(tree, "Pressure", "NodeSocketBool", False)
    _sock(tree, "Cp Lo", "NodeSocketFloat", anim.CP_RANGE[0], hi=-1e-3)
    _sock(tree, "Cp Hi", "NodeSocketFloat", anim.CP_RANGE[1], lo=1e-3)
    _sock(tree, "Geometry", "NodeSocketGeometry", out=True)
    gi = tree.nodes.new("NodeGroupInput")
    go = tree.nodes.new("NodeGroupOutput")
    flow = tree.nodes.new("GeometryNodeObjectInfo")
    flow.transform_space = "RELATIVE"
    tree.links.new(gi.outputs["Flow"], flow.inputs["Object"])
    pos = tree.nodes.new("GeometryNodeInputPosition").outputs[0]
    sample = lambda name: _sample(tree, _grid(tree, flow.outputs["Geometry"], name, "FLOAT"), pos, "FLOAT")
    spd, cp, fluid = sample("speed"), sample("cp"), sample("fluid")
    show = _ramp_coord(tree, gi.outputs["Pressure"], spd, cp, gi.outputs["Cp Lo"], gi.outputs["Cp Hi"])
    geo = _store(tree, _store(tree, _store(tree, gi.outputs["Geometry"], "show", show), "cp", cp), "speed", spd)
    # Keep a vertex only where all eight grid corners around it are fluid and inside the grid
    # (anim.slice_keep): no value blended with the zeroed solid nodes, nothing past the grid edge.
    delete = tree.nodes.new("GeometryNodeDeleteGeometry")
    delete.domain = "POINT"
    tree.links.new(geo, delete.inputs["Geometry"])
    tree.links.new(_cmp(tree, "LESS_THAN", fluid, anim.KEEP_MIN), delete.inputs["Selection"])
    # One loose vertex (never rendered) keeps the inputs readable by WT Legend and WT Label even when
    # the whole plane is outside the grid; they read cp_lo, cp_hi and pressure from this geometry.
    one = tree.nodes.new("GeometryNodeMeshLine")
    one.inputs["Count"].default_value = 1
    join = tree.nodes.new("GeometryNodeJoinGeometry")
    tree.links.new(one.outputs["Mesh"], join.inputs["Geometry"])
    tree.links.new(delete.outputs["Geometry"], join.inputs["Geometry"])
    sw = tree.nodes.new("GeometryNodeSwitch")
    sw.input_type = "FLOAT"
    tree.links.new(gi.outputs["Pressure"], sw.inputs["Switch"])
    sw.inputs["False"].default_value, sw.inputs["True"].default_value = 0.0, 1.0
    geo = _store(tree, join.outputs["Geometry"], "cp_lo", gi.outputs["Cp Lo"])
    geo = _store(tree, _store(tree, geo, "cp_hi", gi.outputs["Cp Hi"]), "pressure", sw.outputs["Output"])
    speed_mat, cp_mat, _ = _materials()
    tree.links.new(_set_mat(tree, geo, gi.outputs["Pressure"], speed_mat, cp_mat), go.inputs["Geometry"])
    _layout(tree)
    return tree


def _slice_inputs(tree, slice_geo):
    """(pressure bool, Cp lo, Cp hi) as single values, from the attributes WT Slice stores."""
    def stat(name):
        st = tree.nodes.new("GeometryNodeAttributeStatistic")
        st.data_type, st.domain = "FLOAT", "POINT"
        tree.links.new(slice_geo, st.inputs["Geometry"])
        tree.links.new(_named(tree, name), st.inputs["Attribute"])
        return st.outputs["Max"]
    return _cmp(tree, "GREATER_THAN", stat("pressure"), 0.5), stat("cp_lo"), stat("cp_hi")


def _fmt(tree, fmt, **items):
    """Format String node (fmt syntax, for example {d:+.2f}); items are sockets or constants."""
    n = tree.nodes.new("FunctionNodeFormatString")
    n.inputs["Format"].default_value = fmt
    for name, v in items.items():
        is_str = isinstance(v, str) or getattr(v, "type", "") == "STRING"
        n.format_items.new("STRING" if is_str else "FLOAT", name)
        if isinstance(v, (str, int, float)):
            n.inputs[name].default_value = v
        else:
            tree.links.new(v, n.inputs[name])
    return n.outputs["String"]


def _ssw(tree, cond, if_false, if_true):
    """String switch; cond is a socket or a bool."""
    sw = tree.nodes.new("GeometryNodeSwitch")
    sw.input_type = "STRING"
    if isinstance(cond, bool):
        sw.inputs["Switch"].default_value = cond
    else:
        tree.links.new(cond, sw.inputs["Switch"])
    for key, v in (("False", if_false), ("True", if_true)):
        if isinstance(v, str):
            sw.inputs[key].default_value = v
        else:
            tree.links.new(v, sw.inputs[key])
    return sw.outputs["Output"]


def _tick_strings(tree, pressure, lo, hi):
    """The five legend tick texts (anim.legend_ticks); lo, hi are sockets or constants."""
    half = lambda v: 0.5 * v if isinstance(v, (int, float)) else _math(tree, "MULTIPLY", v, 0.5)
    cp = [_fmt(tree, "<= {v:.1f}", v=lo), _fmt(tree, "{v:+.1f}", v=half(lo)), "0",
          _fmt(tree, "{v:+.1f}", v=half(hi)), _fmt(tree, ">= {v:+.1f}", v=hi)]
    return [_ssw(tree, pressure, sp, c) for (_, sp), c in zip(anim.legend_ticks(False), cp)]


def _label_string(tree, axis_letter, d, r, pressure):
    """anim.label_text built in nodes: d = offset from the body centre (m), r = d / L."""
    return _fmt(tree, "Slice {a} = {d:+.2f} m ({r:+.2f} L) | {w}", a=axis_letter, d=d, r=r,
                w=_ssw(tree, pressure, "speed/U_inf", "Cp"))


def _time_string(tree, t, tul):
    """transient.time_label built in nodes: t = flow time (s), tul = t U / L."""
    return _fmt(tree, "t = {t:.3f} s (t U/L = {r:.2f})", t=t, r=tul)


def _text(tree, string, size, at, align="LEFT"):
    """Text as a filled mesh in the XZ plane (reads from -Y), baseline starting at `at`."""
    sc = tree.nodes.new("GeometryNodeStringToCurves")
    for key, v in (("String", string), ("Size", size)):
        if isinstance(v, (str, int, float)):
            sc.inputs[key].default_value = v
        else:
            tree.links.new(v, sc.inputs[key])
    sc.inputs["Align X"].default_value = {"LEFT": "Left", "CENTER": "Center"}[align]
    real = tree.nodes.new("GeometryNodeRealizeInstances")
    tree.links.new(sc.outputs["Curve Instances"], real.inputs["Geometry"])
    fill = tree.nodes.new("GeometryNodeFillCurve")
    tree.links.new(real.outputs["Geometry"], fill.inputs["Curve"])
    xf = tree.nodes.new("GeometryNodeTransform")
    tree.links.new(fill.outputs["Mesh"], xf.inputs["Geometry"])
    xf.inputs["Rotation"].default_value = (math.pi / 2, 0.0, 0.0)
    tree.links.new(at, xf.inputs["Translation"])
    return xf.outputs["Geometry"]


def _overlay_tree(name, extra):
    tree = _new_tree(name)
    _sock(tree, "Geometry", "NodeSocketGeometry")
    _sock(tree, "Slice", "NodeSocketObject")
    for args in extra:
        _sock(tree, *args)
    _sock(tree, "Geometry", "NodeSocketGeometry", out=True)
    gi = tree.nodes.new("NodeGroupInput")
    go = tree.nodes.new("NodeGroupOutput")
    info = tree.nodes.new("GeometryNodeObjectInfo")
    info.transform_space = "ORIGINAL"
    tree.links.new(gi.outputs["Slice"], info.inputs["Object"])
    return tree, gi, go, info


def _legend_tree():
    tree, gi, go, info = _overlay_tree("WT Legend", [
        ("Origin", "NodeSocketVector", (0.0, 0.0, 0.0)), ("Length", "NodeSocketFloat", 4.0),
        ("Height", "NodeSocketFloat", 0.16), ("Text Size", "NodeSocketFloat", 0.14)])
    pressure, lo, hi = _slice_inputs(tree, info.outputs["Geometry"])
    speed_mat, cp_mat, text_mat = _materials()
    # Strip: 257 x 2 vertices, show = 0..1 along it (the ramp coordinate itself), so the stops at
    # k / 8 fall on vertices.
    grid = tree.nodes.new("GeometryNodeMeshGrid")
    grid.inputs["Vertices X"].default_value, grid.inputs["Vertices Y"].default_value = 257, 2
    tree.links.new(gi.outputs["Length"], grid.inputs["Size X"])
    tree.links.new(gi.outputs["Height"], grid.inputs["Size Y"])
    sep = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(tree.nodes.new("GeometryNodeInputPosition").outputs[0], sep.inputs[0])
    u = _math(tree, "ADD", _math(tree, "DIVIDE", sep.outputs["X"], gi.outputs["Length"]), 0.5)
    strip = _store(tree, grid.outputs["Mesh"], "show", u)
    xf = tree.nodes.new("GeometryNodeTransform")
    tree.links.new(strip, xf.inputs["Geometry"])
    xf.inputs["Rotation"].default_value = (math.pi / 2, 0.0, 0.0)
    off = tree.nodes.new("ShaderNodeCombineXYZ")
    tree.links.new(_math(tree, "MULTIPLY", gi.outputs["Length"], 0.5), off.inputs["X"])
    tree.links.new(_math(tree, "MULTIPLY", gi.outputs["Height"], 0.5), off.inputs["Z"])
    tree.links.new(_vmath(tree, "ADD", gi.outputs["Origin"], off.outputs[0]), xf.inputs["Translation"])
    join = tree.nodes.new("GeometryNodeJoinGeometry")
    tree.links.new(_set_mat(tree, xf.outputs["Geometry"], pressure, speed_mat, cp_mat), join.inputs["Geometry"])
    # Ticks below the strip at ramp coordinates 0, 0.25, ..., 1 (anim.legend_ticks).
    texts = tree.nodes.new("GeometryNodeJoinGeometry")
    for k, s in enumerate(_tick_strings(tree, pressure, lo, hi)):
        at = tree.nodes.new("ShaderNodeCombineXYZ")
        tree.links.new(_math(tree, "MULTIPLY", gi.outputs["Length"], k / 4), at.inputs["X"])
        tree.links.new(_math(tree, "MULTIPLY", gi.outputs["Text Size"], -1.3), at.inputs["Z"])
        pos = _vmath(tree, "ADD", gi.outputs["Origin"], at.outputs[0])
        tree.links.new(_text(tree, s, gi.outputs["Text Size"], pos, "CENTER"), texts.inputs["Geometry"])
    setm = tree.nodes.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = text_mat
    tree.links.new(texts.outputs["Geometry"], setm.inputs["Geometry"])
    tree.links.new(setm.outputs["Geometry"], join.inputs["Geometry"])
    tree.links.new(join.outputs["Geometry"], go.inputs["Geometry"])
    _layout(tree)
    return tree


def _pick(tree, index, values, dtype="FLOAT"):
    """Index Switch over three values (sockets or constants)."""
    sw = tree.nodes.new("GeometryNodeIndexSwitch")
    sw.data_type = dtype
    tree.links.new(index, sw.inputs["Index"])
    while len([s for s in sw.inputs if s.name.isdigit()]) < len(values):
        sw.index_switch_items.new()
    for k, v in enumerate(values):
        if isinstance(v, (str, int, float)):
            sw.inputs[str(k)].default_value = v
        else:
            tree.links.new(v, sw.inputs[str(k)])
    return sw.outputs["Output"]


def _label_tree():
    tree, gi, go, info = _overlay_tree("WT Label", [
        ("Axis", "NodeSocketInt", 1, False, 0, 2), ("Centre", "NodeSocketVector", (0.0, 0.0, 0.0)),
        ("L", "NodeSocketFloat", 1.0), ("Origin", "NodeSocketVector", (0.0, 0.0, 0.0)),
        ("Text Size", "NodeSocketFloat", 0.18),
        # Time-resolved field: scene frame k is flow time k / CFD fps (0 = steady, no time shown).
        ("CFD fps", "NodeSocketFloat", 0.0, False, 0.0), ("U", "NodeSocketFloat", 20.0)])
    pressure, _, _ = _slice_inputs(tree, info.outputs["Geometry"])

    def comp(vec):
        sep = tree.nodes.new("ShaderNodeSeparateXYZ")
        tree.links.new(vec, sep.inputs[0])
        return _pick(tree, gi.outputs["Axis"], [sep.outputs[c] for c in "XYZ"])
    d = _math(tree, "SUBTRACT", comp(info.outputs["Location"]), comp(gi.outputs["Centre"]))
    r = _math(tree, "DIVIDE", d, gi.outputs["L"])
    letter = _pick(tree, gi.outputs["Axis"], ["x", "y", "z"], "STRING")
    # transient.time_label + " | " + anim.label_text
    t = _math(tree, "DIVIDE", tree.nodes.new("GeometryNodeInputSceneTime").outputs["Frame"],
              _math(tree, "MAXIMUM", gi.outputs["CFD fps"], 1e-6))
    tul = _math(tree, "DIVIDE", _math(tree, "MULTIPLY", t, gi.outputs["U"]), gi.outputs["L"])
    when = _ssw(tree, _cmp(tree, "GREATER_THAN", gi.outputs["CFD fps"], 0.0), "",
                _fmt(tree, "{a} | ", a=_time_string(tree, t, tul)))
    full = _fmt(tree, "{a}{b}", a=when, b=_label_string(tree, letter, d, r, pressure))
    text = _text(tree, full, gi.outputs["Text Size"], gi.outputs["Origin"])
    setm = tree.nodes.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = _materials()[2]
    tree.links.new(text, setm.inputs["Geometry"])
    tree.links.new(setm.outputs["Geometry"], go.inputs["Geometry"])
    _layout(tree)
    return tree


def remove_all():
    for name in (SMOKE, LEGEND, LABEL, SLICE, RAKE, FLOW):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob)
