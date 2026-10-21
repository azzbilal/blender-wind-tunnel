"""ANIMATION A+B Q3: record WT Smoke particle paths in headless Blender (no live scene touched).

    "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup \
        --python-exit-code 1 --python tools/audit/anim_q3_smoke.py -- FIELD.npz OUT.npz MODE FRAMES

Builds WT Flow from FIELD.npz and WT Smoke on a 2 m cube at the origin (the _anim/Cube body) in
scene WT_ANIM of a factory-startup Blender, exactly as the add-on does (viz3d.build_smoke, 24 fps,
U_inf from the field). Then edits only this throwaway tree:
  - every particle gets pid (birth frame * 100000 + index) and p0 (release point) at birth;
  - the "still" deletion (speed < 0.02) is disabled, so particles that enter the solid stay there
    and can be counted instead of vanishing in the same step;
  - MODE "off": the surface slide band (0.05 L) and the push back (0.004 L) are disabled too;
    MODE "on": slide and push back stay as shipped;
  - the output is the bare points (Points to Vertices) so positions can be read.
Writes per frame position, pid, p0 for frames 1..FRAMES to OUT.npz, plus the tree settings.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
for k in [k for k in sys.modules if k == "wind_tunnel" or k.startswith("wind_tunnel.")]:
    del sys.modules[k]

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from wind_tunnel import viz3d  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
field, out, mode, frames = Path(argv[0]), Path(argv[1]), argv[2], int(argv[3])
assert mode in ("on", "off")

scene = bpy.context.scene
scene.name = "WT_ANIM"
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
scene.render.fps, scene.render.fps_base = 24, 1.0
scene.frame_start, scene.frame_end = 1, frames

vdb = out.with_suffix(".vdb")
lo, hi, speed_inf = viz3d.write_vdb(field, vdb)
viz3d.load_volume(vdb)
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.0))
body = bpy.context.active_object
body.name = "Q3 Cube"
smoke = viz3d.build_smoke(body, 2.0, speed_inf, scene.render.fps, use_field=True)
mod = smoke.modifiers["Wind Tunnel"]
tree = mod.node_group
N = tree.nodes


def unlinked_input(value, types):
    """The one node of the given types with an unlinked input at this default value."""
    hits = [(n, s) for n in N if n.bl_idname in types for s in n.inputs
            if not s.is_linked and isinstance(getattr(s, "default_value", None), float)
            and abs(s.default_value - value) < 1e-9]
    assert len(hits) == 1, (value, [(n.name, s.name) for n, s in hits])
    return hits[0][1]


band = unlinked_input(0.05, {"ShaderNodeMath"})       # slide band = L * 0.05
margin = unlinked_input(0.004, {"ShaderNodeMath"})    # push back margin = L * 0.004
still = unlinked_input(0.02, {"FunctionNodeCompare"})  # speed < 0.02 deletion
still.default_value = -1.0
if mode == "off":
    band.default_value = -1.0e9
    margin.default_value = -1.0e9

# pid and p0 at birth, inserted after the "age" store on the distributed points.
dist = next(n for n in N if n.bl_idname == "GeometryNodeDistributePointsOnFaces")
born = next(l.to_node for l in tree.links if l.from_node == dist and l.from_socket.name == "Points")
join_link = next(l for l in tree.links if l.from_node == born)
join_sock = join_link.to_socket
tree.links.remove(join_link)
frame = N.new("GeometryNodeInputSceneTime").outputs["Frame"]
idx = N.new("GeometryNodeInputIndex").outputs[0]
pid_val = viz3d._math(tree, "ADD", viz3d._math(tree, "MULTIPLY", frame, 100000.0), idx)
s_pid = N.new("GeometryNodeStoreNamedAttribute")
s_pid.data_type, s_pid.domain = "INT", "POINT"
s_pid.inputs["Name"].default_value = "pid"
tree.links.new(born.outputs["Geometry"], s_pid.inputs["Geometry"])
tree.links.new(pid_val, s_pid.inputs["Value"])
s_p0 = N.new("GeometryNodeStoreNamedAttribute")
s_p0.data_type, s_p0.domain = "FLOAT_VECTOR", "POINT"
s_p0.inputs["Name"].default_value = "p0"
tree.links.new(s_pid.outputs["Geometry"], s_p0.inputs["Geometry"])
tree.links.new(N.new("GeometryNodeInputPosition").outputs[0], s_p0.inputs["Value"])
tree.links.new(s_p0.outputs["Geometry"], join_sock)

sim_out = next(n for n in N if n.bl_idname == "GeometryNodeSimulationOutput")
go = next(n for n in N if n.bl_idname == "NodeGroupOutput")
p2v = N.new("GeometryNodePointsToVertices")
tree.links.new(sim_out.outputs["Geometry"], p2v.inputs["Points"])
tree.links.new(p2v.outputs["Mesh"], go.inputs["Geometry"])
bad = [(l.from_node.bl_idname, l.to_node.bl_idname) for l in tree.links if not l.is_valid]
assert not bad, bad

samplers = sorted({n.inputs["Interpolation"].default_value for n in N if n.bl_idname == "GeometryNodeSampleGrid"})
settings = {
    "mode": mode, "fps": scene.render.fps, "speed_inf": speed_inf,
    "time_scale": viz3d.get_input(mod, "Time Scale"), "rate": viz3d.get_input(mod, "Rate"),
    "lifetime": viz3d.get_input(mod, "Lifetime"), "sample_grid_interpolation": samplers,
    "band": band.default_value, "margin": margin.default_value, "still": still.default_value,
    "grid_lo": list(map(float, lo)), "grid_hi": list(map(float, hi)),
    "blender": bpy.app.version_string,
}

pos, pid, p0, fr = [], [], [], []
for f in range(1, frames + 1):
    scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = smoke.evaluated_get(dg)
    me = ev.to_mesh()
    n = len(me.vertices)
    co = np.empty(3 * n, np.float32)
    me.vertices.foreach_get("co", co)
    a_pid = np.empty(n, np.int32)
    me.attributes["pid"].data.foreach_get("value", a_pid) if n else None
    a_p0 = np.empty(3 * n, np.float32)
    me.attributes["p0"].data.foreach_get("vector", a_p0) if n else None
    ev.to_mesh_clear()
    pos.append(co.reshape(-1, 3))
    pid.append(a_pid)
    p0.append(a_p0.reshape(-1, 3))
    fr.append(np.full(n, f, np.int32))

np.savez_compressed(out, pos=np.concatenate(pos), pid=np.concatenate(pid), p0=np.concatenate(p0),
                    frame=np.concatenate(fr), settings=json.dumps(settings))
print("Q3SMOKE " + json.dumps({**settings, "rows": int(sum(len(x) for x in pid)),
                               "alive_last": int(len(pid[-1]))}))
