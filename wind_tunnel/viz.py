"""Blender objects that show the OpenFOAM flow: streamline tubes, particles that ride the real
velocities, and a side wall painted with speed or pressure. All of them are children of the
airfoil, in its frame, so they turn with it when the angle of attack is shown.

Data flow:  flowfield.trace() -> "WT Paths" (a hidden point mesh, one point per time step)
            -> "WT Streamlines" (Geometry Nodes: points -> curves -> tubes, coloured by speed)
            -> "WT Particles"   (Geometry Nodes: each particle reads its point along a path from
                                 the frame number, so it moves exactly as fast as the air)
"""
from __future__ import annotations

import numpy as np
import bpy

PATHS, STREAM, PARTS, WALL = "WT Paths", "WT Streamlines", "WT Particles", "WT Side wall"


# ---------------------------------------------------------------- helpers
def _object(name, data, parent):
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, data)
        (parent.users_collection[0] if parent.users_collection else bpy.context.scene.collection).objects.link(ob)
    else:
        ob.data = data
    ob.parent = parent
    ob.matrix_parent_inverse.identity()
    ob.location, ob.rotation_euler, ob.scale = (0, 0, 0), (0, 0, 0), (1, 1, 1)
    return ob


def _fresh_mesh(name):
    me = bpy.data.meshes.get(name)
    if me is not None:
        me.clear_geometry()
        return me
    return bpy.data.meshes.new(name)


def _ramp(ramp, stops):
    # Blender keeps elements sorted by position, so build them in order instead of moving them.
    els = ramp.color_ramp.elements
    while len(els) > 1:
        els.remove(els[-1])
    els[0].position, els[0].color = stops[0][0], (*stops[0][1], 1.0)
    for pos, col in stops[1:]:
        els.new(pos).color = (*col, 1.0)


# Speed |U| / U_inf mapped from SPEED_RANGE: slow wake navy, freestream teal, fast suction yellow to red.
SPEED_RANGE = (0.3, 1.9)
SPEED_STOPS = [(0.0, (0.01, 0.02, 0.12)), (0.25, (0.02, 0.18, 0.55)), (0.44, (0.0, 0.55, 0.6)),
               (0.62, (0.55, 0.8, 0.15)), (0.8, (1.0, 0.65, 0.0)), (1.0, (0.9, 0.08, 0.02))]


def _emission_material(name, attr, lo, hi, strength, instancer=False, stops=None):
    """Emission coloured by a named attribute mapped from [lo, hi] onto a colour ramp (speed stops by default)."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = attr
    a.attribute_type = "INSTANCER" if instancer else "GEOMETRY"
    m = nt.nodes.new("ShaderNodeMapRange")
    m.inputs["From Min"].default_value, m.inputs["From Max"].default_value = lo, hi
    r = nt.nodes.new("ShaderNodeValToRGB")
    _ramp(r, SPEED_STOPS if stops is None else stops)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    for i, n in enumerate((a, m, r, e, o)):
        n.location = (i * 220 - 600, 0)
    nt.links.new(a.outputs["Fac"], m.inputs["Value"])
    nt.links.new(m.outputs["Result"], r.inputs["Fac"])
    nt.links.new(r.outputs["Color"], e.inputs["Color"])
    nt.links.new(e.outputs["Emission"], o.inputs["Surface"])
    return mat


def _tree(name):
    tree = bpy.data.node_groups.get(name)
    if tree is None:
        tree = bpy.data.node_groups.new(name, "GeometryNodeTree")
    tree.nodes.clear()
    tree.interface.clear()
    tree.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi = tree.nodes.new("NodeGroupInput")
    go = tree.nodes.new("NodeGroupOutput")
    return tree, gi, go


def _modifier(ob, tree):
    mod = ob.modifiers.get("Wind Tunnel") or ob.modifiers.new("Wind Tunnel", "NODES")
    mod.node_group = tree
    return mod


def _math(tree, op, a=None, b=None, loc=(0, 0)):
    n = tree.nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = loc
    for k, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[k].default_value = v
        else:
            tree.links.new(v, n.inputs[k])
    return n.outputs[0]


# ---------------------------------------------------------------- the paths
def write_paths(parent, paths, speeds, stations):
    """One vertex per time step of every path, at every spanwise station; edges only where it moves.
    Attributes: speed (|U| / U_inf) and len (number of moving points of that path)."""
    n, N = speeds.shape
    moved = np.any(np.abs(np.diff(paths, axis=1)) > 1e-12, axis=2)          # (n, N-1)
    lens = np.array([max(int(np.nonzero(m)[0].max()) + 2 if m.any() else 1, 2) for m in moved])
    verts, spd, ln, edges = [], [], [], []
    for y in stations:
        for i in range(n):
            base = len(verts)
            verts.extend((x, y, z) for x, z in paths[i])
            spd.extend(speeds[i])
            ln.extend([lens[i]] * N)
            edges.extend((base + k, base + k + 1) for k in range(lens[i] - 1))
    me = _fresh_mesh(PATHS)
    me.from_pydata(verts, edges, [])
    for name, vals in (("speed", spd), ("len", ln)):
        at = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
        at.data.foreach_set("value", np.asarray(vals, dtype=np.float32))
    me.update()
    ob = _object(PATHS, me, parent)
    ob.hide_viewport = ob.hide_render = True
    return ob, n * len(stations), N


# ---------------------------------------------------------------- streamlines
def build_streamlines(parent, paths_ob, radius=0.0025):
    tree, gi, go = _tree("WT Streamline tubes")
    info = tree.nodes.new("GeometryNodeObjectInfo")
    info.inputs["Object"].default_value = paths_ob
    m2c = tree.nodes.new("GeometryNodeMeshToCurve")
    circ = tree.nodes.new("GeometryNodeCurvePrimitiveCircle")
    circ.inputs["Resolution"].default_value = 6
    circ.inputs["Radius"].default_value = radius
    c2m = tree.nodes.new("GeometryNodeCurveToMesh")
    setm = tree.nodes.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = _emission_material("WT Streamlines", "speed", *SPEED_RANGE, 1.0)
    for i, n in enumerate((info, m2c, c2m, setm, go)):
        n.location = (i * 220 - 400, 0)
    circ.location = (0, -250)
    tree.links.new(info.outputs["Geometry"], m2c.inputs["Mesh"])
    tree.links.new(m2c.outputs["Curve"], c2m.inputs["Curve"])
    tree.links.new(circ.outputs["Curve"], c2m.inputs["Profile Curve"])
    tree.links.new(c2m.outputs["Mesh"], setm.inputs["Geometry"])
    tree.links.new(setm.outputs["Geometry"], go.inputs["Geometry"])
    ob = _object(STREAM, _fresh_mesh(STREAM), parent)
    _modifier(ob, tree)
    return ob


# ---------------------------------------------------------------- particles
def build_particles(parent, paths_ob, n_paths, N, per_path=24, steps_per_frame=3.0, radius=0.006):
    """Points that ride the paths. Particle i sits on path i // per_path, at the point
    floor((frame * steps_per_frame + phase) mod len): one path point is one solver time step, so
    the particles slow down at the nose and race over the top exactly as the solved air does."""
    tree, gi, go = _tree("WT Particles")
    info = tree.nodes.new("GeometryNodeObjectInfo")
    info.inputs["Object"].default_value = paths_ob
    info.location = (-900, 300)
    geo = info.outputs["Geometry"]
    idx = tree.nodes.new("GeometryNodeInputIndex").outputs[0]
    frame = tree.nodes.new("GeometryNodeInputSceneTime").outputs["Frame"]

    path = _math(tree, "FLOOR", _math(tree, "DIVIDE", idx, float(per_path)))
    k = _math(tree, "FLOORED_MODULO", idx, float(per_path))
    base = _math(tree, "MULTIPLY", path, float(N))

    def sample(field, index, dtype="FLOAT"):
        s = tree.nodes.new("GeometryNodeSampleIndex")
        s.data_type, s.domain = dtype, "POINT"
        tree.links.new(geo, s.inputs["Geometry"])
        tree.links.new(field, s.inputs["Value"])
        tree.links.new(index, s.inputs["Index"])
        return s.outputs[0]

    def named(name):
        a = tree.nodes.new("GeometryNodeInputNamedAttribute")
        a.data_type = "FLOAT"
        a.inputs["Name"].default_value = name
        return a.outputs["Attribute"]

    length = sample(named("len"), base)
    phase = _math(tree, "MULTIPLY", _math(tree, "DIVIDE", k, float(per_path)), length)
    t = _math(tree, "FLOORED_MODULO", _math(tree, "ADD", _math(tree, "MULTIPLY", frame, steps_per_frame), phase), length)
    at = _math(tree, "ADD", base, _math(tree, "FLOOR", t))
    pos = sample(tree.nodes.new("GeometryNodeInputPosition").outputs[0], at, "FLOAT_VECTOR")
    spd = sample(named("speed"), at)

    pts = tree.nodes.new("GeometryNodePoints")
    pts.inputs["Count"].default_value = n_paths * per_path
    tree.links.new(pos, pts.inputs["Position"])
    store = tree.nodes.new("GeometryNodeStoreNamedAttribute")
    store.data_type, store.domain = "FLOAT", "POINT"
    store.inputs["Name"].default_value = "speed"
    tree.links.new(pts.outputs["Points"], store.inputs["Geometry"])
    tree.links.new(spd, store.inputs["Value"])
    ico = tree.nodes.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = radius
    ico.inputs["Subdivisions"].default_value = 1
    inst = tree.nodes.new("GeometryNodeInstanceOnPoints")
    tree.links.new(store.outputs["Geometry"], inst.inputs["Points"])
    tree.links.new(ico.outputs["Mesh"], inst.inputs["Instance"])
    setm = tree.nodes.new("GeometryNodeSetMaterial")
    setm.inputs["Material"].default_value = _emission_material("WT Particles", "speed", *SPEED_RANGE, 2.5, instancer=True)
    tree.links.new(inst.outputs["Instances"], setm.inputs["Geometry"])
    tree.links.new(setm.outputs["Geometry"], go.inputs["Geometry"])
    for i, n in enumerate((pts, store, inst, setm, go)):
        n.location = (i * 220, 0)
    ob = _object(PARTS, _fresh_mesh(PARTS), parent)
    _modifier(ob, tree)
    return ob


# ---------------------------------------------------------------- side wall
def _colour(values, lo, hi, stops):
    f = np.clip((values - lo) / (hi - lo), 0, 1)
    pos = np.array([s[0] for s in stops])
    cols = np.array([s[1] for s in stops])
    return np.stack([np.interp(f, pos, cols[:, c]) for c in range(3)], axis=-1)


PRESSURE_STOPS = [(0.0, (0.02, 0.1, 0.6)), (0.45, (0.4, 0.7, 1.0)), (0.66, (0.92, 0.92, 0.92)),
                  (0.85, (1.0, 0.55, 0.25)), (1.0, (0.75, 0.05, 0.03))]


def build_wall(parent, field, quantity="SPEED", y=1.0):
    """A plane at one end of the span, painted with |U| or Cp from the solved field (an image texture)."""
    if quantity == "PRESSURE":
        cp = 2.0 * field.p
        rgb = _colour(np.nan_to_num(cp), -2.5, 1.0, PRESSURE_STOPS)
    else:
        rgb = _colour(np.hypot(field.ux, field.uy), *SPEED_RANGE, SPEED_STOPS)
    alpha = (~field.solid).astype(float)
    rgba = np.concatenate([rgb, alpha[..., None]], axis=-1).astype(np.float32)
    img = bpy.data.images.get("WT field") or bpy.data.images.new("WT field", field.nx, field.ny, alpha=True, float_buffer=True)
    if tuple(img.size) != (field.nx, field.ny):
        img.scale(field.nx, field.ny)
    img.pixels.foreach_set(rgba.ravel())
    img.update()

    x0, x1, z0, z1 = field.bounds()
    me = _fresh_mesh(WALL)
    me.from_pydata([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for li, (u, v) in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    me.update()

    mat = bpy.data.materials.get("WT Side wall") or bpy.data.materials.new("WT Side wall")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"
    em = nt.nodes.new("ShaderNodeEmission")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    for i, n in enumerate((tex, em, mix, out)):
        n.location = (i * 240 - 500, 0)
    tr.location = (-260, -200)
    if mat.name not in me.materials:
        me.materials.append(mat)
    ob = _object(WALL, me, parent)
    return ob


def data_colours(scene):
    """Standard view transform, so colours on screen are the colour-map values and not AgX's
    film look, which washes bright emission out to white."""
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"


def remove_all():
    for name in (PARTS, STREAM, WALL, PATHS):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob)
