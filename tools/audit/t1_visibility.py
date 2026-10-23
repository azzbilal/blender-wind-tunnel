"""TRANSIENT T1 polish: headless check that the plain smoke streaks are visible in the T1 render.

    "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup \
        --python-exit-code 1 --python tools/audit/t1_visibility.py -- FRAMES_DIR OUT_DIR [OVERRIDES.json]

Builds the WT_T1 scene of tools/audit/t1_scene.py (same camera, light, slice, smoke inputs from
transient.plain_smoke_inputs; OVERRIDES.json can replace smoke inputs for a trial, never for the
record), plays frames 1..120 in order and renders them to OUT_DIR/vis_kkkk.png exactly as
t1_scene.render does (the render reads the Simulation Zone cache only), then renders frames 30, 60, 120 again with WT Smoke hidden (ref_kkkk.png) as the
false-positive baseline of the classifier.

Camera scale (t1_scene): 15 m from the y = 0 sheet, 50 mm lens, 36 mm sensor, 1280 px wide:
15 * 36 / 50 / 1280 = 8.44 mm per pixel at y = 0.

Streak pixel: sRGB max(R, G, B) <= 80 and max - min <= 16. The streaks are charcoal (48, 48, 48)
emission under the Standard view; every Cp colour of the slice has max >= 180 and the cube faces
lie outside the regions, so only (nearly) fully covered streak pixels pass.
Regions, in the y = 0 plane projected through the camera, inside the slice rectangle (4 px margin)
and outside the cube's projected box (its 8 corners, 4 px margin; the -Y face at y = -1 projects
about 7 % larger than +-1 m):
  over: x in [-1, 1] m and |z| in [1.1 m, grid edge] (above and below the cube: with the +-0.05 L
        sheet no streak can pass in front of the -Y face, so "over the cube" is above/below here);
  wake: x in [1.15 m, grid end] and |z| <= 1 m (behind the cube, its height).
Threshold, each of frames 30, 60, 120: over >= 400 px and wake >= 1000 px, i.e. about 2 and 5
full streaks at 3 px x 0.3 L (0.6 m / 8.44 mm = 71 px long, about 200 px each).
Prints VIS {json} and exits 1 when a frame misses a threshold.
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
for k in [k for k in sys.modules if k == "wind_tunnel" or k.startswith("wind_tunnel.")]:
    del sys.modules[k]

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

from wind_tunnel import viz3d  # noqa: E402

FRAMES = (30, 60, 120)
MIN_PX = {"over": 400, "wake": 1000}
GREY_MAX, GREY_SPREAD, MARGIN_PX = 80, 16, 4

argv = sys.argv[sys.argv.index("--") + 1:]
frames_dir, out_dir = Path(argv[0]).resolve(), Path(argv[1]).resolve()
overrides = json.loads(Path(argv[2]).read_text()) if len(argv) > 2 else {}
out_dir.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("t1_scene", REPO / "tools" / "audit" / "t1_scene.py")
t1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t1)
info = t1.build(frames_dir)
sc = bpy.data.scenes[t1.SCENE]
mod = bpy.data.objects[viz3d.SMOKE].modifiers["Wind Tunnel"]
for key, v in overrides.items():
    viz3d.set_input(mod, key, v)
inputs = {k: viz3d.get_input(mod, k) for k in ("Radius", "Trail", "Rate", "Sheet", "Lifetime", "Substeps")}

W, H = sc.render.resolution_x, sc.render.resolution_y
cam = sc.camera


def px(x, z, y=0.0):
    c = world_to_camera_view(sc, cam, Vector((x, y, z)))
    return c.x * W, (1.0 - c.y) * H          # column, row from the top


def rect(pts, grow=0.0):
    cs, rs = zip(*pts)
    return min(cs) - grow, max(cs) + grow, min(rs) - grow, max(rs) + grow


lo, hi = info["grid_lo"], info["grid_hi"]
slice_r = rect([px(lo[0], lo[2]), px(hi[0], hi[2])], -MARGIN_PX)
cube_r = rect([px(x, z, y) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)], MARGIN_PX)
regions = {
    "over": [rect([px(-1.0, 1.1), px(1.0, hi[2])]), rect([px(-1.0, lo[2]), px(1.0, -1.1)])],
    "wake": [rect([px(1.15, -1.0), px(hi[0], 1.0)])],
}
cols, rows = np.meshgrid(np.arange(W) + 0.5, np.arange(H) + 0.5)


def inside(r):
    return (cols >= r[0]) & (cols <= r[1]) & (rows >= r[2]) & (rows <= r[3])


keep = inside(slice_r) & ~inside(cube_r)
masks = {name: keep & np.any([inside(r) for r in rs], axis=0) for name, rs in regions.items()}


def srgb8(path):
    img = bpy.data.images.load(str(path))
    buf = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return np.round(buf.reshape(H, W, 4)[::-1, :, :3] * 255.0)    # rows from the top, 0..255 as stored


def count(path):
    a = srgb8(path)
    mx, mn = a.max(axis=2), a.min(axis=2)
    grey = (mx <= GREY_MAX) & (mx - mn <= GREY_SPREAD)
    return {name: int((grey & m).sum()) for name, m in masks.items()}, a


t0 = time.time()
if hasattr(sc.render.image_settings, "media_type"):          # Blender 5: still images need media type IMAGE
    sc.render.image_settings.media_type = "IMAGE"
sc.render.image_settings.file_format = "PNG"
sc.render.image_settings.color_mode = "RGB"
sc.render.filepath = str(out_dir / "vis_####")
sc.frame_start, sc.frame_end = 1, max(FRAMES)
t1.play(max(FRAMES))                     # as t1_scene.render: fill the Simulation Zone cache, then render
bpy.ops.render.render(animation=True, scene=sc.name)
t_anim = time.time() - t0

res, fails = {}, []
for f in FRAMES:
    n, a = count(out_dir / f"vis_{f:04d}.png")
    res[f] = n
    for name, need in MIN_PX.items():
        if n[name] < need:
            fails.append(f"frame {f}: {name} {n[name]} px < {need}")
    if f == FRAMES[0]:
        # Scale check of the decode: the world background (left of the slice) and the slice centre.
        sanity = {"background_srgb": a[H // 2, 5].tolist(), "charcoal_target": [48, 48, 48]}

smoke = bpy.data.objects[viz3d.SMOKE]
smoke.hide_render = True
ref = {}
for f in FRAMES:
    sc.frame_set(f)
    sc.render.filepath = str(out_dir / f"ref_{f:04d}.png")
    bpy.ops.render.render(write_still=True, scene=sc.name)
    ref[f] = count(out_dir / f"ref_{f:04d}.png")[0]

rep = {"inputs": inputs, "overrides": overrides, "streak_px": res, "baseline_no_smoke_px": ref,
       "threshold_px": MIN_PX, "classifier": {"max_le": GREY_MAX, "spread_le": GREY_SPREAD},
       "mask_px": {k: int(m.sum()) for k, m in masks.items()}, "sanity": sanity,
       "camera": {"distance_m": round(-cam.location.y, 3), "lens_mm": cam.data.lens,
                  "sensor_mm": cam.data.sensor_width, "sensor_fit": cam.data.sensor_fit},
       "mm_per_px_at_y0": round(-cam.location.y * cam.data.sensor_width / cam.data.lens / W * 1000.0, 3),
       "fails": fails,
       "render_s": round(t_anim, 1), "blender": bpy.app.version_string}
print("VIS " + json.dumps(rep))
(out_dir / "visibility.json").write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8")
sys.exit(1 if fails else 0)
