"""3D flow in Blender: OpenFOAM's solved field plus the Test Object assigned in the node setup.

  "WT Flow"   a Volume object holding the OpenFOAM result as OpenVDB grids:
              velocity (m/s), speed (|U| / U_inf), cp (pressure coefficient)
  "WT Smoke"  Geometry Nodes Simulation Zone with a Test Object field. Every frame, new particles appear
              on a plane upstream of the Test Object (sized from its bounding box) and every particle
              moves by the velocity it samples from the grid (midpoint rule), or by the plain wind in
              preview. Near the Test Object the inward part of the velocity is removed, so particles
              slide along whatever shape is assigned, at once, before any solve.
  "WT Slice"  a plane that samples the grid at its vertices and colours itself by speed or Cp;
              move and rotate it anywhere, like a cutting plane in ParaView
"""
from __future__ import annotations

import math
from pathlib import Path

import bpy
import numpy as np

from .viz import SPEED_STOPS, _emission_material, _fresh_mesh, _math, _ramp

FLOW, RAKE, SMOKE, SLICE = "WT Flow", "WT Rake", "WT Smoke", "WT Slice"


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
    openvdb.write(str(vdb), grids=grids)
    lo = np.array([ox, oy, oz])
    return lo, lo + h * (np.array(U.shape[:3]) - 1), speed_inf


def _link(ob, collection=None):
    col = collection or bpy.context.scene.collection
    if ob.name not in col.objects:
        col.objects.link(ob)
    return ob


def load_volume(vdb: Path):
    vol = bpy.data.volumes.get(FLOW) or bpy.data.volumes.new(FLOW)
    vol.filepath = str(vdb)
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


def build_slice(box_lo, box_hi, body_lo, body_hi):
    cy = (body_lo[1] + body_hi[1]) / 2
    sx, sz = box_hi[0] - box_lo[0], box_hi[2] - box_lo[2]
    centre = ((box_lo[0] + box_hi[0]) / 2, cy, (box_lo[2] + box_hi[2]) / 2)
    ob = _plane(SLICE, sx, sz, "Y", centre, res=(int(min(400, sx / sz * 160)), 160))
    tree = _slice_tree()
    mod = ob.modifiers.get("Wind Tunnel") or ob.modifiers.new("Wind Tunnel", "NODES")
    mod.node_group = tree
    _set_input(mod, tree, "Flow", bpy.data.objects[FLOW])
    return ob


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

    Every step: velocity = the solved field (Use Field on) or the plain wind (preview); near the
    Test Object the inward part of that velocity is removed, so particles slide along its surface,
    and any particle that still ends up inside is put back on the surface. New particles come from
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

    # Velocity: the solved field (midpoint rule) or the plain wind.
    dt = _math(tree, "MULTIPLY", sim_in.outputs["Delta Time"], gi.outputs["Time Scale"])
    v1 = _sample(tree, vel_grid, P(), "VECTOR")
    mid = _vmath(tree, "ADD", P(), _vmath(tree, "SCALE", v1, scale=_math(tree, "MULTIPLY", dt, 0.5)))
    v2 = _sample(tree, vel_grid, mid, "VECTOR")
    v = _vsw(tree, gi.outputs["Use Field"], gi.outputs["Wind"], v2)

    # The Test Object's surface: nearest point and its normal.
    near = tree.nodes.new("GeometryNodeProximity")
    near.target_element = "FACES"
    tree.links.new(body_geo, near.inputs["Geometry"])
    tree.links.new(P(), near.inputs["Source Position"])
    nrm_s = tree.nodes.new("GeometryNodeSampleNearestSurface")
    nrm_s.data_type = "FLOAT_VECTOR"
    tree.links.new(body_geo, nrm_s.inputs["Mesh"])
    tree.links.new(tree.nodes.new("GeometryNodeInputNormal").outputs[0], nrm_s.inputs["Value"])
    tree.links.new(P(), nrm_s.inputs["Sample Position"])
    n = _vmath(tree, "NORMALIZE", nrm_s.outputs["Value"])
    gap = _vmath(tree, "DOT_PRODUCT", _vmath(tree, "SUBTRACT", P(), near.outputs["Position"]), n)
    has_body = near.outputs["Is Valid"]
    band = _cmp(tree, "LESS_THAN", gap, _math(tree, "MULTIPLY", L, 0.05))
    into = _math(tree, "MINIMUM", _vmath(tree, "DOT_PRODUCT", v, n), 0.0)
    slide = _vmath(tree, "SUBTRACT", v, _vmath(tree, "SCALE", n, scale=into))
    v_eff = _vsw(tree, _bool(tree, "AND", has_body, band), v, slide)

    move = tree.nodes.new("GeometryNodeSetPosition")
    tree.links.new(join.outputs["Geometry"], move.inputs["Geometry"])
    tree.links.new(_vmath(tree, "SCALE", v_eff, scale=dt), move.inputs["Offset"])
    speed_now = _math(tree, "DIVIDE", _vmath(tree, "LENGTH", v_eff),
                      _math(tree, "MAXIMUM", _vmath(tree, "LENGTH", gi.outputs["Wind"]), 1e-6))
    stored = _store(tree, move.outputs["Geometry"], "speed", speed_now)

    # Anything that still ended up inside goes back onto the surface.
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
    inside = _bool(tree, "AND", near2.outputs["Is Valid"], _cmp(tree, "LESS_THAN", gap2, margin))
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
    inst = tree.nodes.new("GeometryNodeInstanceOnPoints")
    tree.links.new(sim_out.outputs["Geometry"], inst.inputs["Points"])
    tree.links.new(ico.outputs["Mesh"], inst.inputs["Instance"])
    setm = tree.nodes.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = _emission_material("WT Smoke", "speed", 0.3, 1.9, 2.5, instancer=True)
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


def set_input(mod, name, value):
    _set_input(mod, mod.node_group, name, value)


# ---------------------------------------------------------------- slice
def _slice_tree():
    tree = _new_tree("WT Slice")
    _sock(tree, "Geometry", "NodeSocketGeometry")
    _sock(tree, "Flow", "NodeSocketObject")
    _sock(tree, "Pressure", "NodeSocketBool", False)
    _sock(tree, "Geometry", "NodeSocketGeometry", out=True)
    gi = tree.nodes.new("NodeGroupInput")
    go = tree.nodes.new("NodeGroupOutput")
    flow = tree.nodes.new("GeometryNodeObjectInfo")
    flow.transform_space = "RELATIVE"
    tree.links.new(gi.outputs["Flow"], flow.inputs["Object"])
    pos = tree.nodes.new("GeometryNodeInputPosition").outputs[0]
    spd = _sample(tree, _grid(tree, flow.outputs["Geometry"], "speed", "FLOAT"), pos, "FLOAT")
    cp = _sample(tree, _grid(tree, flow.outputs["Geometry"], "cp", "FLOAT"), pos, "FLOAT")
    # Both mapped to 0..1 for one colour ramp: speed 0.3..1.9, Cp -2.5..1 (suction dark, stagnation red).
    m_s = tree.nodes.new("ShaderNodeMapRange")
    m_s.inputs["From Min"].default_value, m_s.inputs["From Max"].default_value = 0.3, 1.9
    tree.links.new(spd, m_s.inputs["Value"])
    m_p = tree.nodes.new("ShaderNodeMapRange")
    m_p.inputs["From Min"].default_value, m_p.inputs["From Max"].default_value = -2.5, 1.0
    tree.links.new(cp, m_p.inputs["Value"])
    sw = tree.nodes.new("GeometryNodeSwitch")
    sw.input_type = "FLOAT"
    tree.links.new(gi.outputs["Pressure"], sw.inputs["Switch"])
    tree.links.new(m_s.outputs["Result"], sw.inputs["False"])
    tree.links.new(m_p.outputs["Result"], sw.inputs["True"])
    shown = _store(tree, gi.outputs["Geometry"], "show", sw.outputs["Output"])
    # Hide the faces that fall inside the body (no air movement there).
    still = _math(tree, "LESS_THAN", spd, 0.01)
    delete = tree.nodes.new("GeometryNodeDeleteGeometry")
    delete.domain = "POINT"
    tree.links.new(shown, delete.inputs["Geometry"])
    tree.links.new(still, delete.inputs["Selection"])
    setm = tree.nodes.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = _emission_material("WT Slice", "show", 0.0, 1.0, 1.0)
    tree.links.new(delete.outputs["Geometry"], setm.inputs["Geometry"])
    tree.links.new(setm.outputs["Geometry"], go.inputs["Geometry"])
    _layout(tree)
    return tree


def remove_all():
    for name in (SMOKE, SLICE, RAKE, FLOW):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob)
