"""Talks to OpenFOAM inside WSL from Windows: finds the distro, maps paths, starts and stops runs.

No Blender import, so it can be tested on its own.
"""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Every OpenFOAM environment script present; pick_bashrc chooses one (same rule as case.ENV).
PROBE = ("ls -d /usr/lib/openfoam/openfoam*/etc/bashrc /opt/openfoam*/etc/bashrc "
         "/usr/share/openfoam/etc/bashrc 2>/dev/null; echo \"HOME=$HOME\"; nproc")

_COM_VERSION = re.compile(r"/openfoam-?v?(\d+)/etc/bashrc$", re.IGNORECASE)


def pick_bashrc(paths):
    """The newest openfoam.com build (/usr/lib/openfoam/openfoamNNNN or /opt/openfoamNNNN), else
    Ubuntu's /usr/share/openfoam package, else None. Versions compare as numbers, not as text."""
    com = [(int(m.group(1)), p) for p in paths if (m := _COM_VERSION.search(p))]
    if com:
        return max(com)[1]
    return next((p for p in paths if p.endswith("/etc/bashrc")), None)


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
        rc = pick_bashrc([line for line in lines if line.endswith("/etc/bashrc")])
        home = [line[5:] for line in lines if line.startswith("HOME=")]
        cores = [line for line in lines if line.isdigit()]
        if rc and home:
            return {"distro": d, "bashrc": rc, "home": home[0], "cores": int(cores[0]) if cores else 1}
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


def stop3d_command(root_linux: str) -> str:
    """Shell text that stops one 3D run: its Allrun, then every snappyHexMesh or simpleFoam working
    inside `root_linux`, then marks the run stopped. pkill -f matches a regex against whole command
    lines, and this text is itself the command line of the `sh -c` that runs it, so the last letter
    is bracketed: `Allru[n]` matches "Allrun" but not its own spelling."""
    return (f'pkill -f "{root_linux}/Allru[n]"; for n in snappyHexMesh simpleFoam; do '
            f'for q in $(pgrep -x $n); do case "$(readlink /proc/$q/cwd)" in "{root_linux}"*) kill $q;; esac; done; done; '
            f'echo stopped > "{root_linux}/status"')
