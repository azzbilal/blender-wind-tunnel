"""Install the add-on from this repo into Blender and build dist/wind_tunnel.zip.

Usage (Git Bash, from the repo root):
    py tools/deploy.py                 # Blender 5.2, the default
    py tools/deploy.py --blender 4.5   # another Blender version folder

After it runs, restart Blender (or disable and enable the add-on) to load the new code.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "wind_tunnel"
SKIP = {"__pycache__"}


def files():
    for p in sorted(SRC.rglob("*")):
        if p.is_file() and not (SKIP & set(p.parts)) and p.suffix in (".py", ".toml"):
            yield p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", default="5.2", help="Blender version folder under %%APPDATA%%")
    ap.add_argument("--zip-only", action="store_true")
    a = ap.parse_args()

    dist = REPO / "dist"
    dist.mkdir(exist_ok=True)
    zpath = dist / "wind_tunnel.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files():
            z.write(p, p.relative_to(SRC).as_posix())
    print(f"built {zpath}")

    if a.zip_only:
        return 0
    appdata = os.environ.get("APPDATA")
    if not appdata:
        print("APPDATA not set: not on Windows? Use --zip-only.")
        return 1
    target = Path(appdata) / "Blender Foundation" / "Blender" / a.blender / "scripts" / "addons" / "wind_tunnel"
    target.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in files():
        out = target / p.relative_to(SRC)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        n += 1
    stale = target / "__pycache__"
    if stale.exists():
        shutil.rmtree(stale, ignore_errors=True)
    print(f"installed {n} files into {target}")
    print("Restart Blender, or disable and enable 'Wind Tunnel (OpenFOAM)', to load them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
