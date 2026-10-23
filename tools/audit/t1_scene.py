"""TRANSIENT T1 Stage 4: the WT_T1 scene in Bilal's live Blender (run through the MCP), never his scenes.

    exec(open(r"<repo>/tools/audit/t1_scene.py").read()); build(FRAMES_DIR); render(OUT_MP4)

render() plays frames 1..120 in order first (play()): the render reads the Simulation Zone cache only.

build(): a new scene WT_T1 (bpy.data.scenes.new, made the window's scene), a 2 m cube "T1Cube" at the
origin, viz3d.build_transient (WT Flow as a VDB sequence, WT Slice at y = 0 in Cp mode, legend, label
with t and t U/L, plain smoke), a camera on -Y looking at the slice, a sun, Standard view. The add-on's
Test Object handler and 1 s watch timer are suspended while WT_T1 exists (the T1 field is no Test
Object's solved field, open issue f), and Auto solve is switched off on EVERY scene: the add-on finds
WT Smoke (and so the Test Object T1Cube) by its global name but reads Auto solve from whichever scene
is current, so any scene with it on could start a steady solve of T1Cube (this happened once, the
unrequested ~/wind_tunnel/3d_T1Cube of 2026-10-24). The previous values are kept in
bpy.app.driver_namespace (session only, never saved in the .blend). cleanup() removes everything WT_T1
made, then restores Auto solve, then the handler and timer.
"""
import math
import sys
from pathlib import Path

import bpy

REPO = Path(r"D:\10_PROJECTS\aerodynamics blender openfoam")
N_FRAMES, FPS, L, U = 120, 12, 2.0, 20.0     # 12 fps: 120 frames, 10 s video (HIL round)
SCENE = "WT_T1"


def _addon():
    import wind_tunnel as wt
    return wt


def suspend_handler():
    wt = _addon()
    hs = bpy.app.handlers.depsgraph_update_post
    if wt._on_depsgraph in hs:
        hs.remove(wt._on_depsgraph)
    if bpy.app.timers.is_registered(wt._watch):
        bpy.app.timers.unregister(wt._watch)


def restore_handler():
    wt = _addon()
    hs = bpy.app.handlers.depsgraph_update_post
    if wt._on_depsgraph not in hs:
        hs.append(wt._on_depsgraph)
    if not bpy.app.timers.is_registered(wt._watch):
        bpy.app.timers.register(wt._watch, first_interval=1.0, persistent=True)


AUTO_KEY = "wt_t1_auto_resolve"          # bpy.app.driver_namespace: {scene name: Auto solve before build}


def auto_solve_off():
    """Auto solve off on every scene, first values kept (a second build keeps the originals)."""
    saved = bpy.app.driver_namespace.setdefault(AUTO_KEY, {})
    for s in bpy.data.scenes:
        p = getattr(s, "wind_tunnel", None)          # absent when the add-on is not registered (headless)
        if p is None:
            continue
        saved.setdefault(s.name, bool(p.auto_resolve))
        if p.auto_resolve:
            p.auto_resolve = False


def auto_solve_restore():
    saved = bpy.app.driver_namespace.pop(AUTO_KEY, {})
    for name, v in saved.items():
        s = bpy.data.scenes.get(name)
        p = getattr(s, "wind_tunnel", None) if s is not None else None
        if p is not None and p.auto_resolve != v:
            p.auto_resolve = v


def build(frames_dir):
    from wind_tunnel import viz3d
    import numpy as np
    suspend_handler()
    auto_solve_off()
    sc = bpy.data.scenes.get(SCENE) or bpy.data.scenes.new(SCENE)
    if bpy.context.window is not None:           # None in headless Blender (tools/audit/t1_visibility.py)
        bpy.context.window.scene = sc
    auto_solve_off()                             # WT_T1 itself (new scenes default to Auto solve on)
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    sc.frame_start, sc.frame_end = 1, N_FRAMES
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform, sc.view_settings.look = "Standard", "None"
    sc.view_settings.exposure, sc.view_settings.gamma = 0.0, 1.0
    world = bpy.data.worlds.get("WT_T1 World") or bpy.data.worlds.new("WT_T1 World")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.02, 0.025, 1.0)
    sc.world = world

    me = bpy.data.meshes.get("T1Cube") or bpy.data.meshes.new("T1Cube")
    me.clear_geometry()
    h = L / 2
    v = [(x, y, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
    me.from_pydata(v, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    me.update()
    cube = bpy.data.objects.get("T1Cube") or bpy.data.objects.new("T1Cube", me)
    if cube.name not in sc.collection.objects:
        sc.collection.objects.link(cube)
    mat = bpy.data.materials.get("T1Cube") or bpy.data.materials.new("T1Cube")
    mat.diffuse_color = (0.35, 0.35, 0.37, 1.0)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.35, 0.37, 1.0)
    me.materials.clear()
    me.materials.append(mat)

    voxel = float(np.load(Path(frames_dir) / "flow_0001.npz")["voxel"])
    lo, hi = viz3d.build_transient(Path(frames_dir), cube, N_FRAMES, FPS, L, U, voxel)
    for name in (viz3d.FLOW, viz3d.SLICE, viz3d.SMOKE, viz3d.LEGEND, viz3d.LABEL):
        ob = bpy.data.objects[name]
        for col in list(ob.users_collection):
            if col != sc.collection:
                col.objects.unlink(ob)
        if ob.name not in sc.collection.objects:
            sc.collection.objects.link(ob)

    cam_data = bpy.data.cameras.get("T1Cam") or bpy.data.cameras.new("T1Cam")
    cam_data.lens = 50.0
    cam = bpy.data.objects.get("T1Cam") or bpy.data.objects.new("T1Cam", cam_data)
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2 + 0.4
    cam.location = (cx, -15.0, cz)
    cam.rotation_euler = (math.pi / 2, 0.0, 0.0)
    sc.camera = cam
    sun_data = bpy.data.lights.get("T1Sun") or bpy.data.lights.new("T1Sun", "SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.get("T1Sun") or bpy.data.objects.new("T1Sun", sun_data)
    if sun.name not in sc.collection.objects:
        sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(60), 0.0, math.radians(-30))
    sc.frame_set(1)
    return {"grid_lo": [float(x) for x in lo], "grid_hi": [float(x) for x in hi], "voxel": voxel}


def play(n=N_FRAMES):
    """Plays frames 1..n in order. An unbaked Simulation Zone advances only in the scene's depsgraph and a
    render only reads that cache: without this every rendered frame shows just the particles born in it
    (the release column of the 0.6.0 video)."""
    sc = bpy.data.scenes[SCENE]
    for f in range(1, n + 1):
        sc.frame_set(f)


def render(out_mp4):
    sc = bpy.data.scenes[SCENE]
    play()
    if hasattr(sc.render.image_settings, "media_type"):          # Blender 5: FFMPEG needs media type VIDEO
        sc.render.image_settings.media_type = "VIDEO"
    sc.render.image_settings.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"
    sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    sc.render.filepath = str(out_mp4)
    bpy.ops.render.render(animation=True, scene=SCENE)
    return str(out_mp4)


def cleanup():
    """Removes WT_T1 and every datablock it made, then restores Auto solve, then the handler and timer."""
    from wind_tunnel import viz3d
    sc = bpy.data.scenes.get(SCENE)
    other = [s for s in bpy.data.scenes if s.name != SCENE]
    if sc is not None and other and bpy.context.window is not None:
        bpy.context.window.scene = other[0]
    viz3d.remove_all()
    for name in ("T1Cube", "T1Cam", "T1Sun"):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob)
    if sc is not None:
        bpy.data.scenes.remove(sc)
    for coll, names in ((bpy.data.meshes, ("T1Cube",)), (bpy.data.cameras, ("T1Cam",)),
                        (bpy.data.lights, ("T1Sun",)), (bpy.data.materials, ("T1Cube",)),
                        (bpy.data.worlds, ("WT_T1 World",))):
        for n in names:
            d = coll.get(n)
            if d is not None and d.users == 0:
                coll.remove(d)
    # WT meshes, node groups and the volume first; their materials lose their last user with them.
    for coll in (bpy.data.meshes, bpy.data.node_groups, bpy.data.volumes, bpy.data.materials):
        for d in list(coll):
            if d.name.startswith("WT ") and d.users == 0:
                coll.remove(d)
    auto_solve_restore()
    restore_handler()
