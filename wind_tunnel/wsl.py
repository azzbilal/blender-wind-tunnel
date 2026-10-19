"""Talks to OpenFOAM inside WSL from Windows: finds the distro, maps paths, starts and stops runs.

No Blender import, so it can be tested on its own.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# The first OpenFOAM environment script found: openfoam.com builds, then Ubuntu's own package.
PROBE = ("ls -d /usr/lib/openfoam/openfoam*/etc/bashrc /opt/openfoam*/etc/bashrc "
         "/usr/share/openfoam/etc/bashrc 2>/dev/null | sort -V | tail -1; echo \"HOME=$HOME\"; nproc")


def _decode(raw: bytes) -> str:
    """wsl.exe itself answers in UTF-16; programs inside the distro answer in UTF-8."""
    text = raw.decode("utf-16-le", "replace") if raw.count(b"\x00") > len(raw) // 4 else raw.decode("utf-8", "replace")
    return text.replace("\x00", "").strip()


def run(args, timeout: float = 30.0):
    p = subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WINDOW)
    return p.returncode, _decode((p.stdout or b"") + (p.stderr or b""))


def distros():
    if os.name != "nt":
        return []
    _, out = run(["wsl", "-l", "-q"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def find_openfoam(preferred: str = ""):
    """The first distro with OpenFOAM in it: {'distro', 'bashrc', 'home', 'cores'}, or None.

    The default distro is often Docker's, which has no bash, so every call names the distro.
    """
    names = distros()
    names.sort(key=lambda d: (d != preferred, d.lower().startswith("docker")))
    for d in names:
        if d.lower().startswith("docker"):
            continue
        try:
            _, out = run(["wsl", "-d", d, "-e", "sh", "-c", PROBE], timeout=90)
        except (subprocess.TimeoutExpired, OSError):
            continue
        lines = out.splitlines()
        rc = [line for line in lines if line.endswith("/etc/bashrc")]
        home = [line[5:] for line in lines if line.startswith("HOME=")]
        cores = [line for line in lines if line.isdigit()]
        if rc and home:
            return {"distro": d, "bashrc": rc[0], "home": home[0], "cores": int(cores[0]) if cores else 1}
    return None


def windows_path(distro: str, linux_path: str) -> Path:
    """A Linux path inside the distro, as Windows (and Blender) can open it."""
    tail = linux_path.replace("/", "\\")
    for host in ("wsl.localhost", "wsl$"):
        root = Path(f"\\\\{host}\\{distro}\\")
        if root.exists():
            return Path(f"\\\\{host}\\{distro}{tail}")
    return Path(f"\\\\wsl.localhost\\{distro}{tail}")


def own_folder(distro: str, folder_linux: str, home: str):
    """Creates `folder_linux` and hands it (recursively) to the owner of `home`, so Windows can write in it
    whichever Linux user the \\wsl.localhost share maps to."""
    run(["wsl", "-d", distro, "-u", "root", "-e", "sh", "-c",
         f'mkdir -p "{folder_linux}" && chown -R --reference="{home}" "{folder_linux}" && chmod -R u+rwX "{folder_linux}"'],
        timeout=60)


def launch(distro: str, script_linux: str, home: str = ""):
    """Starts `bash <script>` in the distro without a console window; returns the process handle.

    Files written from Windows through \\wsl.localhost belong to root, so the run folder is first
    handed to the owner of `home` (the distro's normal user, who then runs the solver).
    """
    if home:
        folder = script_linux.rsplit("/", 1)[0]
        run(["wsl", "-d", distro, "-u", "root", "-e", "chown", "-R", f"--reference={home}", folder], timeout=60)
    return subprocess.Popen(["wsl", "-d", distro, "-e", "bash", script_linux],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)


def stop(distro: str, root_linux: str):
    """Stops the solvers of one run: every simpleFoam whose working folder is inside `root_linux`."""
    cmd = (f'for p in $(pgrep -x simpleFoam); do case "$(readlink /proc/$p/cwd)" in "{root_linux}"/*) kill $p;; esac; done; '
           f'echo stopped > "{root_linux}/status"')
    return run(["wsl", "-d", distro, "-e", "sh", "-c", cmd], timeout=30)
