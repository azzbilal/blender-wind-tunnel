"""TRANSIENT T1 Stage 3: headless check that the slice and the smoke read the frame-matching VDB.

    "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup \
        --python-exit-code 1 --python tools/audit/t1_frames_check.py

Synthetic frames, no solve needed: on a 2 m grid (voxel 0.1 m) frame k has uniform U = (20, 0, 0) m/s
and uniform Cp = 0.1 k, written with viz3d.write_vdb as flow_000k.vdb (k = 1..4) and loaded as a VDB
sequence by viz3d.build_transient, exactly as the T1 scene is built. Checks:
  1. WT Slice at scene frame k stores cp = 0.1 k on every kept vertex (the frame-matching VDB), and at
     frame 5 (past the sequence, CLIP) it keeps no vertex;
  2. WT Smoke (plain inputs, Substeps > 1) moves particles U / 60 = 0.3333 m per scene frame: the
     distinct x positions at frame 4 are spaced by that step (one CFD frame interval per scene frame);
  3. each streak is |v| Trail = 0.1 L long and points along +X.
Prints T1CHECK {json} and exits 1 on any failure.
"""
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
for k in [k for k in sys.modules if k == "wind_tunnel" or k.startswith("wind_tunnel.")]:
    del sys.modules[k]

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from wind_tunnel import transient, viz3d  # noqa: E402

U, RHO, N, H = 20.0, 1.225, 4, 0.1
q = 0.5 * RHO * U ** 2
tmp = Path(tempfile.mkdtemp(prefix="t1check_"))
shape = (21, 21, 21)
for k in range(1, N + 1):
    Ug = np.zeros(shape + (3,), np.float32)
    Ug[..., 0] = U
    np.savez_compressed(tmp / transient.frame_name(k, "npz"), origin=np.array([-1.0, -1.0, -1.0]), voxel=H, U=Ug,
                        p=np.full(shape, 0.1 * k * q, np.float32), solid=np.zeros(shape, bool), speed=U,
                        p_inf_Pa=0.0)

scene = bpy.context.scene
scene.render.fps = 24
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
bpy.ops.mesh.primitive_cube_add(size=0.2, location=(0.0, 0.0, 0.0))
body = bpy.context.active_object
L = 0.2
viz3d.build_transient(tmp, body, N, scene.render.fps, L, U, H, RHO)
slice_ob, smoke = bpy.data.objects[viz3d.SLICE], bpy.data.objects[viz3d.SMOKE]
smod = smoke.modifiers["Wind Tunnel"]
inputs = {k: viz3d.get_input(smod, k) for k in ("Time Scale", "Substeps", "Trail", "Plain", "Use Field", "Rate")}

fails, cps = [], {}
for f in range(1, N + 2):
    scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    me = slice_ob.evaluated_get(dg).to_mesh()
    n = len(me.vertices)
    cp = np.zeros(n, np.float32)                     # no "cp" at all when nothing is kept (past the sequence)
    if "cp" in me.attributes:
        me.attributes["cp"].data.foreach_get("value", cp)
    slice_ob.evaluated_get(dg).to_mesh_clear()
    if int((cp == 0).sum()) != 1:                    # the one loose data vertex (cp 0), wherever Join puts it
        fails.append(f"slice frame {f}: {int((cp == 0).sum())} vertices with cp 0, expected 1")
    kept = cp[cp != 0]
    cps[f] = {"kept": int(len(kept)), "cp_min": float(kept.min()) if len(kept) else None,
              "cp_max": float(kept.max()) if len(kept) else None}
    if f <= N:
        if len(kept) == 0 or abs(kept.min() - 0.1 * f) > 1e-5 or abs(kept.max() - 0.1 * f) > 1e-5:
            fails.append(f"slice frame {f}: {cps[f]}")
    elif len(kept):
        fails.append(f"slice frame {f} past the sequence kept {len(kept)} vertices")

scene.frame_set(1)
for f in range(1, N + 1):
    scene.frame_set(f)
dg = bpy.context.evaluated_depsgraph_get()
inst = [i.matrix_world.copy() for i in dg.object_instances
        if i.is_instance and i.parent is not None and i.parent.original == smoke]
x = np.array([m.translation[0] for m in inst])
xs = np.unique(np.round(x, 4))
steps = np.diff(xs)
lengths = np.array([m.col[0].xyz.length for m in inst])
dirs = np.array([tuple(m.col[0].xyz.normalized()) for m in inst])
step_ok = len(xs) >= 3 and np.allclose(steps, U / 60, atol=2e-4)
if not step_ok:
    fails.append(f"smoke x positions {xs.tolist()} not spaced by U/60 = {U / 60:.4f}")
if not np.allclose(lengths, 0.1 * L, rtol=1e-3):
    fails.append(f"streak lengths {lengths.min():.5f}..{lengths.max():.5f}, expected {0.1 * L}")
if not np.allclose(dirs, [1.0, 0.0, 0.0], atol=1e-4):
    fails.append("streaks not along +X")

# 4. The label's time text, built in nodes from constants, equals transient.time_label.
probe = viz3d._new_tree("WT probe")
viz3d._sock(probe, "Geometry", "NodeSocketGeometry", out=True)
geo = probe.nodes.new("GeometryNodeMeshLine")
geo.inputs["Count"].default_value = 1
out = geo.outputs["Mesh"]
KS = (1, 7, 30, 59, 120)
for k in KS:
    c = probe.nodes.new("FunctionNodeCompare")
    c.data_type, c.operation = "STRING", "EQUAL"
    probe.links.new(viz3d._time_string(probe, k / 60, k / 60 * 20.0 / 2.0), c.inputs[0])
    c.inputs[1].default_value = transient.time_label(k, 20.0, 2.0)
    out = viz3d._store(probe, out, f"ok{k:04d}", c.outputs["Result"], "BOOLEAN")
probe.links.new(out, probe.nodes.new("NodeGroupOutput").inputs["Geometry"])
pob = bpy.data.objects.new("WT probe", bpy.data.meshes.new("WT probe"))
scene.collection.objects.link(pob)
pob.modifiers.new("n", "NODES").node_group = probe
pme = pob.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
labels = {k: bool(pme.attributes[f"ok{k:04d}"].data[0].value) for k in KS}
if not all(labels.values()):
    fails.append(f"time label text differs from transient.time_label: {labels}")

rep = {"frames": cps, "smoke_inputs": inputs, "time_labels_match": labels, "particles": len(inst), "x_levels": xs.tolist(),
       "x_steps": steps.tolist(), "streak_len": [float(lengths.min()), float(lengths.max())],
       "fails": fails, "blender": bpy.app.version_string}
print("T1CHECK " + json.dumps(rep))
sys.exit(1 if fails else 0)
