"""ANIMATION A+B Q3: solid entries and smoke vs RK4 streamline drift, from anim_q3_smoke.py output.

    py -3.12 tools/audit/anim_q3_drift.py FIELD.npz OFF.npz ON.npz OUT.json

Field: field.npz node lattice, value (i, j, k) at origin + h (i, j, k), exactly as write_vdb puts it
into WT Flow; sampled trilinearly (the Sample Grid default, recorded by anim_q3_smoke.py) with 0
outside the grid (the VDB background).
1. Twin check: one midpoint step in Python reproduces Blender's frame k -> k+1 positions.
2. Solid entries: distinct particles whose position ever lies in the solid mask (nearest node) or
   inside the cube box |x|, |y|, |z| < 1 m, per 100 frames and as a fraction of particles released.
3. Drift: RK4 streamlines (step dt/24, at most 0.1 voxel up to 36 m/s) from the same release
   points; smoke and reference compared at equal arc length up to 1 L. Near-body path: the
   reference comes within 0.25 L of the cube surface within its first 1 L; else freestream.
"""
import json
import sys

import numpy as np

L, HALF = 2.0, 1.0


def load_field(path):
    d = np.load(path)
    return (d["U"].astype(np.float64), d["solid"], np.asarray(d["origin"], float), float(d["voxel"]))


def sampler(U, o, h):
    n = np.array(U.shape[:3])

    def at(x):
        g = (x - o) / h
        i0 = np.floor(g).astype(int)
        f = g - i0
        out = np.zeros(x.shape)
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    idx = i0 + (dx, dy, dz)
                    ok = np.all((idx >= 0) & (idx < n), axis=1)
                    w = (np.where(dx, f[:, 0], 1 - f[:, 0]) * np.where(dy, f[:, 1], 1 - f[:, 1])
                         * np.where(dz, f[:, 2], 1 - f[:, 2]))
                    v = np.zeros(x.shape)
                    j = idx[ok]
                    v[ok] = U[j[:, 0], j[:, 1], j[:, 2]]
                    out += w[:, None] * v
        return out
    return at


def in_solid(x, solid, o, h):
    i = np.rint((x - o) / h).astype(int)
    ok = np.all((i >= 0) & (i < np.array(solid.shape)), axis=1)
    s = np.zeros(len(x), bool)
    j = i[ok]
    s[ok] = solid[j[:, 0], j[:, 1], j[:, 2]]
    return s


def in_box(x):
    return np.all(np.abs(x) < HALF, axis=1)


def box_gap(x):
    """Distance from points outside the cube to its surface (0 inside)."""
    return np.linalg.norm(np.maximum(np.abs(x) - HALF, 0.0), axis=1)


def load_run(path):
    r = np.load(path)
    return {k: r[k] for k in ("pos", "pid", "p0", "frame")}, json.loads(str(r["settings"]))


def tracks(run, pids):
    """pid -> (frames, positions) sorted by frame, for the requested pids."""
    sel = np.isin(run["pid"], pids)
    pid, fr, pos = run["pid"][sel], run["frame"][sel], run["pos"][sel].astype(np.float64)
    order = np.lexsort((fr, pid))
    pid, fr, pos = pid[order], fr[order], pos[order]
    cut = np.flatnonzero(np.diff(pid)) + 1
    return dict(zip(pid[np.r_[0, cut]], zip(np.split(fr, cut), np.split(pos, cut))))


def entries(run, solid, o, h, last_frame):
    m = run["frame"] <= last_frame
    pos, pid = run["pos"][m].astype(np.float64), run["pid"][m]
    released = len(np.unique(pid))
    s_mask = np.unique(pid[in_solid(pos, solid, o, h)])
    s_box = np.unique(pid[in_box(pos)])
    return {"frames": last_frame, "released": int(released),
            "entered_solid_mask": int(len(s_mask)), "entered_cube_box": int(len(s_box)),
            "fraction_mask": len(s_mask) / released, "fraction_box": len(s_box) / released}


def arc(poly):
    return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(poly, axis=0), axis=1))]


def at_arc(poly, s_poly, s):
    return np.stack([np.interp(s, s_poly, poly[:, c]) for c in range(3)], axis=1)


def main(field_path, off_path, on_path, out_path):
    U, solid, o, h = load_field(field_path)
    U_at = sampler(U, o, h)
    off, cfg = load_run(off_path)
    on, _ = load_run(on_path)
    dt = (1.0 / cfg["fps"]) * cfg["time_scale"]
    report = {"settings": cfg, "dt_s": dt, "voxel_m": h,
              "step_freestream_voxels": cfg["speed_inf"] * dt / h,
              "U_max_field": float(np.linalg.norm(U, axis=-1).max())}

    # 1. Twin check on the slide-off run: Python midpoint step vs Blender, frames 40 -> 41.
    a, b = off["frame"] == 40, off["frame"] == 41
    common, ia, ib = np.intersect1d(off["pid"][a], off["pid"][b], return_indices=True)
    xa = off["pos"][a][ia].astype(np.float64)
    xb = off["pos"][b][ib].astype(np.float64)
    pred = xa + dt * U_at(xa + 0.5 * dt * U_at(xa))
    err = np.linalg.norm(pred - xb, axis=1)
    report["twin_check"] = {"particles": int(len(common)), "max_err_m": float(err.max()),
                            "max_err_voxels": float(err.max() / h)}

    # 2. Solid entries per 100 frames, slide off and slide on (still-air deletion disabled in both).
    report["entries"] = {"slide_off": entries(off, solid, o, h, 100),
                         "slide_on": entries(on, solid, o, h, 100)}
    released_by = {}
    for name, run in (("slide_off", off), ("slide_on", on)):
        m = in_box(run["pos"].astype(np.float64))
        released_by[name] = sorted(set(map(int, np.unique(run["frame"][m]))))[:3]
    report["first_frames_with_box_entry"] = released_by

    # 3. Drift: particles born at frames 2..60 (frame 1 has zero Delta Time), every 3rd.
    born = np.unique(off["pid"][(off["frame"] >= 2) & (off["frame"] <= 60)])
    born = born[::3]
    tr_off, tr_on = tracks(off, born), tracks(on, born)
    _, first = np.unique(off["pid"], return_index=True)
    p0 = off["p0"][first[np.searchsorted(np.unique(off["pid"]), born)]].astype(np.float64)
    f_birth = born // 100000
    n_steps = int(130 - f_birth.min() + 1)
    sub = 24
    ht = dt / sub
    x = p0.copy()
    ref = [x.copy()]
    ref_solid = np.zeros(len(born), bool)
    for _ in range(n_steps * sub):
        k1 = U_at(x)
        k2 = U_at(x + 0.5 * ht * k1)
        k3 = U_at(x + 0.5 * ht * k2)
        k4 = U_at(x + ht * k3)
        x = x + ht / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        ref.append(x.copy())
        ref_solid |= in_box(x)
    ref = np.stack(ref, axis=1)                                  # (paths, steps + 1, 3)

    groups = {"near_body": {}, "freestream": {}}
    for mode, tr in (("slide_off", tr_off), ("slide_on", tr_on)):
        rows = {"near_body": [], "freestream": []}
        short = 0
        for i, p in enumerate(born):
            fr, pos = tr[p]
            smoke = np.vstack([p0[i], pos])
            s_sm = arc(smoke)
            keep = s_sm <= L
            if s_sm[-1] < L:
                short += 1
            r = ref[i]
            s_r = arc(r)
            r1 = r[s_r <= L]
            near = box_gap(r1).min() < 0.25 * L
            d = np.linalg.norm(smoke[keep] - at_arc(r, s_r, s_sm[keep]), axis=1) / h
            rows["near_body" if near else "freestream"].append(
                (d.max(), d.mean(), bool(in_box(smoke[keep]).any())))
        for g, v in rows.items():
            v = np.array(v, dtype=float).reshape(-1, 3)
            groups[g][mode] = {"paths": int(len(v)),
                               "max_drift_voxels": float(v[:, 0].max()) if len(v) else None,
                               "mean_of_path_max_voxels": float(v[:, 0].mean()) if len(v) else None,
                               "mean_drift_voxels": float(v[:, 1].mean()) if len(v) else None,
                               "paths_smoke_in_box": int(v[:, 2].sum())}
        groups.setdefault("paths_shorter_than_1L", {})[mode] = short
    report["drift"] = groups
    report["drift"]["rk4_paths_entering_box"] = int(ref_solid.sum())
    report["drift"]["rk4_step"] = {"dt_s": ht, "voxels_at_U_max": report["U_max_field"] * ht / h}
    with open(out_path, "w", newline="\n") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
