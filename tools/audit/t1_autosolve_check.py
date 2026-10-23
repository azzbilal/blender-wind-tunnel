"""TRANSIENT T1 polish (0.6.1): headless check that tools/audit/t1_scene.py keeps Auto solve off on every
scene while WT_T1 exists and restores each scene's own value at cleanup.

    "/c/Program Files/Blender Foundation/Blender 5.2/blender.exe" --background --factory-startup \
        --python-exit-code 1 --python tools/audit/t1_autosolve_check.py

The add-on is registered (so scenes carry wind_tunnel.auto_resolve); "Scene" starts with Auto solve on,
a second scene "Other" with it off. build() runs twice (a second build must keep the first saved values),
then cleanup(). Pass: every scene off during the build, afterwards Scene on and Other off, the saved
values gone from bpy.app.driver_namespace, the Test Object handler back. Prints AUTOCHK {json}.
Needs renders/t1_frames (the T1 frame VDBs).
"""
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
for k in [k for k in sys.modules if k == "wind_tunnel" or k.startswith("wind_tunnel.")]:
    del sys.modules[k]

import bpy  # noqa: E402

import wind_tunnel as wt  # noqa: E402

wt.register()
other = bpy.data.scenes.new("Other")
other.wind_tunnel.auto_resolve = False
bpy.data.scenes["Scene"].wind_tunnel.auto_resolve = True
spec = importlib.util.spec_from_file_location("t1_scene", REPO / "tools" / "audit" / "t1_scene.py")
t1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t1)
t1.build(REPO / "renders" / "t1_frames")
t1.build(REPO / "renders" / "t1_frames")
during = {s.name: s.wind_tunnel.auto_resolve for s in bpy.data.scenes}
saved = dict(bpy.app.driver_namespace.get(t1.AUTO_KEY, {}))
t1.cleanup()
after = {s.name: s.wind_tunnel.auto_resolve for s in bpy.data.scenes}
ok = (not any(during.values()) and after == {"Scene": True, "Other": False}
      and t1.AUTO_KEY not in bpy.app.driver_namespace
      and wt._on_depsgraph in bpy.app.handlers.depsgraph_update_post)
print("AUTOCHK " + json.dumps({"during": during, "saved": saved, "after": after, "ok": ok}))
sys.exit(0 if ok else 1)
