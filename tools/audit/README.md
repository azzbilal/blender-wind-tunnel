# Accuracy audit scripts

These run **inside WSL Ubuntu** on a solved, reconstructed case. They import
`export_field.py` from the case folder (every case has its own copy).

| Script | What it checks |
|---|---|
| `audit.py CASE ORIG` | Recomputes face/cell geometry like OpenFOAM's `primitiveMesh`, compares forces with the add-on's method, y+ distribution, inlet static Cp, blockage, mass balance and divergence of `field.npz`. `CASE` must contain time folders `300` and `400`; `ORIG` is the solved run folder (for `forces.json`, `field.npz`). U0 = 20 m/s is hard-coded. |
| `history.py CASE` | Cd, Cs, Cl at every saved time of a case (frontal area from `forces.json`). |
| `extend.sh` | Continues the `_audit` copies of Cube and Cone from 400 to 1200 iterations, writing every 50. |

Typical use from Git Bash on Windows:

```bash
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -e bash -lc "mkdir -p ~/wind_tunnel/_audit && cp /mnt/d/10_PROJECTS/'aerodynamics blender openfoam'/tools/audit/*.py ~/wind_tunnel/_audit/"
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -e bash -lc ". /usr/share/openfoam/etc/bashrc; cd ~/wind_tunnel/_audit && python3 history.py Cube"
```

Known limits: fixed speed, fixed time names, no CLI flags. Turning these into a proper
`validate` command that runs after every solve is part of FIX_PLAN step 5.
