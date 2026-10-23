"""Count WT Smoke particles inside the 2 m cube, headless Blender (no live scene touched).

    "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup \
        --python-exit-code 1 --python tools/audit/anim_inside.py -- FIELD.npz FRAMES [OUT.json]
        ... -- FRAMES_DIR FRAMES [OUT.json]      (TRANSIENT T1: flow_0001.npz .. as a VDB sequence)

Builds WT Flow from FIELD.npz and the shipped WT Smoke tree in solved mode (Use Field on, no
slide, no push back, still rule kept) on a 2 m cube at the origin, 24 fps, then plays frames
1..FRAMES in order (the Simulation Zone advances only frame to frame). Particle positions are the
translations of the evaluated WT Smoke instances (the `position` attribute is not usable in 5.2).

Counts particle-frames inside the body box |x|, |y|, |z| < 1 m (target 0) and reports two gaps for
the particles outside it:
  - min_gap_euclidean_m: straight-line distance to the box surface, |max(|x_i| - 1, 0)|;
  - min_gap_chebyshev_m: per-axis gap, max over axes of (|x_i| - 1). For a point outside an
    axis-aligned box it is at most the Euclidean distance.
With a frames directory (TRANSIENT T1 Q4 gate 4) the scene is viz3d.build_transient's: WT Flow as a
VDB sequence (scene frame k = flow frame k), plain smoke with substeps, as rendered.
ANIMATION A+B record: 2477893 particle-frames, 0 inside, Chebyshev 0.73 mm, Euclidean 0.98 mm
(docs/reviews/anim_ab_review.md item 3, validation/anim_ab_v2512.json).
"""
import json
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
for k in [k for k in sys.modules if k == "wind_tunnel" or k.startswith("wind_tunnel.")]:
    del sys.modules[k]

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import wind_tunnel as wt  # noqa: E402
from wind_tunnel import viz3d  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
field, frames = Path(argv[0]), int(argv[1])
out = Path(argv[2]) if len(argv) > 2 else None

hs = bpy.app.handlers.depsgraph_update_post
if wt._on_depsgraph in hs:
    hs.remove(wt._on_depsgraph)
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)

bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
cube = bpy.context.active_object
cube.name = "InsideCube"
scene = bpy.context.scene
scene.render.fps, scene.render.fps_base = 24, 1.0
scene.frame_start, scene.frame_end = 1, frames
if field.is_dir():
    voxel = float(np.load(field / "flow_0001.npz")["voxel"])
    viz3d.build_transient(field, cube, frames, 24, 2.0, 20.0, voxel)
    smoke = bpy.data.objects[viz3d.SMOKE]
else:
    tmp = Path(tempfile.mkdtemp())
    viz3d.write_vdb(field, tmp / "flow.vdb")
    viz3d.load_volume(tmp / "flow.vdb")
    smoke = viz3d.build_smoke(cube, 2.0, 20.0, 24, use_field=True)
mod = smoke.modifiers["Wind Tunnel"]
tree = mod.node_group
gi = next(n for n in tree.nodes if n.bl_idname == "NodeGroupInput")
nots = [n for n in tree.nodes if n.bl_idname == "FunctionNodeBooleanMath" and n.operation == "NOT"
        and any(lk.from_node == gi and lk.from_socket.name == "Use Field" for lk in n.inputs[0].links)]

t0 = time.time()
total, inside, alive_max = 0, 0, 0
gap_euc, gap_cheb = 1e9, 1e9
first_inside = None
for f in range(1, frames + 1):
    scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    P = [inst.matrix_world.translation[:] for inst in dg.object_instances
         if inst.is_instance and inst.parent is not None and inst.parent.original == smoke]
    if not P:
        continue
    a = np.abs(np.array(P))
    ins = np.all(a < 1.0, axis=1)
    total += len(a)
    inside += int(ins.sum())
    alive_max = max(alive_max, len(a))
    if ins.any() and first_inside is None:
        first_inside = (f, a[ins][0].tolist())
    o = a[~ins]
    if len(o):
        gap_euc = min(gap_euc, float(np.linalg.norm(np.maximum(o - 1.0, 0.0), axis=1).min()))
        gap_cheb = min(gap_cheb, float((o - 1.0).max(axis=1).min()))

rep = {"field": str(field), "frames": frames, "use_field": viz3d.get_input(mod, "Use Field"),
       "use_field_nots": len(nots), "particle_frames": total, "inside_body_box_abs_lt_1m": inside,
       "particles_alive_max": alive_max, "min_gap_euclidean_m": gap_euc,
       "min_gap_chebyshev_m": gap_cheb, "first_inside": first_inside,
       "seconds": round(time.time() - t0, 1)}
print("INSIDE " + json.dumps(rep))
if out:
    out.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
