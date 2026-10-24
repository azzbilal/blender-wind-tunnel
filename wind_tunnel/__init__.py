"""Wind Tunnel: build a NACA airfoil in Blender, solve it with OpenFOAM in WSL, read the forces back.

Sidebar (N) > Wind Tunnel. The case files, the mesh and the force integration are plain Python
(case.py, meshgen.py, results.py); wsl.py starts the solver; this file is the Blender side.
"""
bl_info = {
    "name": "Wind Tunnel (OpenFOAM)",
    "author": "Bilal Azzouzi",
    "version": (0, 6, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Wind Tunnel",
    "description": "Airfoil polars with OpenFOAM (simpleFoam, k-omega SST) running in WSL",
    "category": "Physics",
}

import math
import os
import threading
import time
from pathlib import Path

import bmesh
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)

from . import case, results, wsl

RUN = {}          # the one active run: process, paths, analysis thread
MESHES = {}       # the last CFD mesh read back, reused when showing pressure
CHECK = {}        # result of the last OpenFOAM detection
FLOW = {}         # the flow visualisation being prepared in the background
RUN3D = {}        # the active 3D run


# ---------------------------------------------------------------- properties
class WT_Result(bpy.types.PropertyGroup):
    alpha: FloatProperty(name="Angle")
    state: StringProperty(default="queued")      # queued, running, finished, failed
    iteration: IntProperty()
    residual: FloatProperty()
    cl: FloatProperty()
    cd: FloatProperty()
    cm: FloatProperty()
    has_coeffs: BoolProperty()
    converged: BoolProperty()
    note: StringProperty()


class WT_Props(bpy.types.PropertyGroup):
    naca: StringProperty(name="NACA", default="0012", maxlen=4,
                         description="4-digit NACA code: max camber %, its position in tenths, thickness %")
    reynolds: FloatProperty(name="Reynolds", default=6.0e6, min=1e3, soft_max=2e7, precision=0,
                            description="Reynolds number on the chord")
    angles: StringProperty(name="Angles", default="0, 5, 10, 15",
                           description="Angles of attack in degrees, separated by commas")
    iterations: IntProperty(name="Iterations", default=3000, min=200, max=50000,
                            description="SIMPLE iterations per angle")
    y_plus: FloatProperty(name="Wall y+", default=50.0, min=20.0, max=300.0,
                          description="Target y+ of the first cell: 30 to 100 suits the wall functions used here")
    distro: StringProperty(name="WSL distro", default="")
    home: StringProperty(default="")
    bashrc: StringProperty(default="")
    cores: IntProperty(default=0)
    state: StringProperty(default="idle")
    message: StringProperty(default="")
    run_path: StringProperty(default="")
    results: CollectionProperty(type=WT_Result)
    # flow visualisation
    flow_alpha: FloatProperty(name="Angle", default=10.0, description="Angle whose flow is shown")
    flow_lines: IntProperty(name="Lines", default=30, min=4, max=200,
                            description="Streamlines per spanwise station")
    flow_stations: IntProperty(name="Stations", default=3, min=1, max=9,
                               description="Spanwise positions that get a sheet of streamlines")
    flow_streamlines: BoolProperty(name="Streamlines", default=True)
    flow_particles: BoolProperty(name="Particles", default=True)
    flow_speed: FloatProperty(name="Particle speed", default=3.0, min=0.25, max=20.0,
                              description="Solver time steps per animation frame (0.004 chord / U each)")
    # 3D wind tunnel
    wind_speed: FloatProperty(name="Wind", default=20.0, min=0.1, max=300.0, unit="VELOCITY",
                              description="Wind speed along +X (world axes)")
    ground: BoolProperty(name="Road", default=False,
                         description="A moving road under the object (cars); off means free air all round")
    quality: EnumProperty(name="Mesh", default="COARSE",
                          items=[("COARSE", "Coarse", "About 0.3 to 0.6 million cells: minutes"),
                                 ("MEDIUM", "Medium", "About 1 to 2 million cells: tens of minutes")])
    iterations3d: IntProperty(name="Max iterations", default=3000, min=400, max=10000,
                              description="Cap on the iterations; the run stops earlier when the convergence "
                                          "gate passes (Cd band < 0.5 % over 200 iterations and p residual < 1e-3)")
    auto_resolve: BoolProperty(name="Auto solve", default=True,
                               description="Solve by itself a few seconds after a Test Object is assigned or changed "
                                           "(a finished solve of the same shape is reused, not repeated)")
    sweep_axis: EnumProperty(name="Sweep", default="Y",
                             items=[("X", "X", "Slice faces X and moves along the wind"),
                                    ("Y", "Y", "Slice faces Y and moves side to side through the body"),
                                    ("Z", "Z", "Slice faces Z and moves up and down")])
    solved_sig: StringProperty(default="")
    field_stale: BoolProperty(default=False)
    run3d_path: StringProperty(default="")
    body3d: StringProperty(default="")
    forces_body: StringProperty(default="")
    message3d: StringProperty(default="")
    drag: FloatProperty()
    lift: FloatProperty()
    side: FloatProperty()
    cd3d: FloatProperty()
    cl3d: FloatProperty()
    area3d: FloatProperty()
    cells3d: IntProperty()
    converged3d: BoolProperty(default=False)
    verdict3d: StringProperty(default="")
    wall3d: StringProperty(default="")          # y+ and prism layer lines (results.wall_lines)
    wall_alert3d: BoolProperty(default=False)
    flow_wall: EnumProperty(name="Side wall", default="SPEED",
                            items=[("NONE", "None", "No side wall"),
                                   ("SPEED", "Speed", "Paint the side wall with |U| / U∞"),
                                   ("PRESSURE", "Pressure", "Paint the side wall with Cp")])


def _angles(text):
    out = []
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if part:
            out.append(round(float(part), 2))
    return sorted(set(out))


def _setup(p):
    return case.Setup(naca=p.naca, reynolds=p.reynolds, iterations=p.iterations, y_plus=p.y_plus)


def _redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


# ---------------------------------------------------------------- geometry in Blender
def build_airfoil(code: str, span: float = 2.0, name: str | None = None):
    """The NACA section as a closed, extruded mesh: chord 1 m along X, thickness along Z, span along Y."""
    up, lo = case.naca4(code, 120)
    loop = list(reversed(up)) + lo[1:-1]              # TE -> upper -> LE -> lower, closed back to TE
    n = len(loop)
    verts = [(x, -span / 2, y) for x, y in loop] + [(x, span / 2, y) for x, y in loop]
    faces = [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    faces += [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    name = name or f"NACA {code}"
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    me.from_pydata(verts, [], faces)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    for poly in me.polygons:
        poly.use_smooth = True
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
    else:
        ob.data = me
    ob["wind_tunnel_naca"] = code
    return ob


def _run_root(p):
    """The run folder for the current NACA code and Reynolds number, in Linux and Windows form."""
    tag = f"naca{p.naca}_re{p.reynolds:.3g}".replace("+", "").replace(".", "p")
    root_linux = f"{p.home}/wind_tunnel/{tag}"
    return root_linux, wsl.windows_path(p.distro, root_linux)


class _Finished:
    """Stands in for the solver process when results already on disk are reloaded."""

    def poll(self):
        return 0


def _airfoil_object(p):
    return bpy.data.objects.get(f"NACA {p.naca}")


# ---------------------------------------------------------------- operators
class WT_OT_check(bpy.types.Operator):
    bl_idname = "wind_tunnel.check"
    bl_label = "Find OpenFOAM"
    bl_description = "Look for a WSL distro with OpenFOAM installed"

    def execute(self, context):
        p = context.scene.wind_tunnel
        if os.name != "nt":
            self.report({"ERROR"}, "This add-on runs OpenFOAM through WSL, so it needs Windows")
            return {"CANCELLED"}
        try:
            CHECK["distros"] = wsl.distros()
            found = wsl.find_openfoam(p.distro)
        except Exception as e:
            self.report({"ERROR"}, f"WSL did not answer: {e}")
            return {"CANCELLED"}
        if not found:
            p.message = "No WSL distro with OpenFOAM. In Ubuntu: sudo apt install openfoam"
            self.report({"ERROR"}, p.message)
            return {"CANCELLED"}
        p.distro, p.home, p.bashrc, p.cores = found["distro"], found["home"], found["bashrc"], found["cores"]
        p.message = f"OpenFOAM found in {p.distro} ({p.cores} cores)"
        self.report({"INFO"}, p.message)
        return {"FINISHED"}


class WT_OT_airfoil(bpy.types.Operator):
    bl_idname = "wind_tunnel.airfoil"
    bl_label = "Build airfoil"
    bl_description = "Create (or rebuild) the NACA section as a mesh object, chord 1 m"

    def execute(self, context):
        p = context.scene.wind_tunnel
        if not (len(p.naca) == 4 and p.naca.isdigit()):
            self.report({"ERROR"}, "NACA code must be 4 digits, for example 2412")
            return {"CANCELLED"}
        ob = build_airfoil(p.naca)
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {"FINISHED"}


class WT_OT_run(bpy.types.Operator):
    bl_idname = "wind_tunnel.run"
    bl_label = "Run in OpenFOAM"
    bl_description = "Mesh the section and solve every angle in parallel in WSL"

    def execute(self, context):
        p = context.scene.wind_tunnel
        if RUN:
            self.report({"WARNING"}, "A run is already going")
            return {"CANCELLED"}
        if not p.distro and bpy.ops.wind_tunnel.check() != {"FINISHED"}:
            return {"CANCELLED"}
        try:
            alphas = _angles(p.angles)
        except ValueError:
            self.report({"ERROR"}, "Angles must be numbers separated by commas")
            return {"CANCELLED"}
        if not alphas:
            self.report({"ERROR"}, "Give at least one angle")
            return {"CANCELLED"}
        if not _airfoil_object(p):
            bpy.ops.wind_tunnel.airfoil()

        root_linux, root = _run_root(p)
        p.run_path = str(root)
        p.results.clear()
        for a in alphas:
            r = p.results.add()
            r.alpha = a
        p.state, p.message = "writing", "Writing the mesh and cases"
        RUN.update(scene=context.scene.name, root=root, root_linux=root_linux, distro=p.distro,
                   nu=1.0 / p.reynolds, alphas=alphas, proc=None, error=None, analysis=None,
                   thread=None, started=time.time())
        setup, home = _setup(p), p.home

        def prepare():
            try:
                wsl.own_folder(RUN["distro"], f"{home}/wind_tunnel", home)
                case.write_sweep(root, setup, alphas)
                RUN["proc"] = wsl.launch(RUN["distro"], f"{root_linux}/Allrun", home)
            except Exception as e:
                RUN["error"] = f"{type(e).__name__}: {e}"

        threading.Thread(target=prepare, daemon=True).start()
        bpy.app.timers.register(_poll, first_interval=1.0)
        return {"FINISHED"}


class WT_OT_load(bpy.types.Operator):
    bl_idname = "wind_tunnel.load"
    bl_label = "Load last run"
    bl_description = "Read back the results already solved for this NACA code and Reynolds number, without solving again"

    def execute(self, context):
        p = context.scene.wind_tunnel
        if RUN:
            return {"CANCELLED"}
        if not p.distro and bpy.ops.wind_tunnel.check() != {"FINISHED"}:
            return {"CANCELLED"}
        root_linux, root = _run_root(p)
        try:
            alphas = sorted(float(d.name[1:]) for d in root.iterdir() if d.is_dir() and d.name[:1] == "a"
                            and (d / "log.simpleFoam").exists())
        except OSError:
            alphas = []
        if not alphas:
            self.report({"ERROR"}, f"No solved run for NACA {p.naca} at Re {p.reynolds:.3g}")
            return {"CANCELLED"}
        if not _airfoil_object(p):
            bpy.ops.wind_tunnel.airfoil()
        p.run_path = str(root)
        p.angles = ", ".join(f"{a:g}" for a in alphas)
        p.results.clear()
        for a in alphas:
            r = p.results.add()
            r.alpha = a
        RUN.update(scene=context.scene.name, root=root, root_linux=root_linux, distro=p.distro,
                   nu=1.0 / p.reynolds, alphas=alphas, proc=_Finished(), error=None, analysis=None,
                   thread=None, started=time.time())
        bpy.app.timers.register(_poll, first_interval=0.2)
        return {"FINISHED"}


class WT_OT_stop(bpy.types.Operator):
    bl_idname = "wind_tunnel.stop"
    bl_label = "Stop"
    bl_description = "Stop the solvers of this run"

    def execute(self, context):
        if RUN:
            try:
                wsl.stop(RUN["distro"], RUN["root_linux"])
            except Exception as e:
                self.report({"WARNING"}, str(e))
            RUN["stopping"] = True
        return {"FINISHED"}


class WT_OT_show(bpy.types.Operator):
    bl_idname = "wind_tunnel.show"
    bl_label = "Show angle"
    bl_description = "Turn the airfoil to this angle of attack and colour it by surface pressure (blue: suction, red: pressure)"
    alpha: FloatProperty()

    def execute(self, context):
        p = context.scene.wind_tunnel
        ob = _airfoil_object(p)
        if not ob:
            return {"CANCELLED"}
        ob.rotation_euler = (0.0, math.radians(self.alpha), 0.0)
        p.flow_alpha = self.alpha
        c = Path(p.run_path) / case.case_name(self.alpha) if p.run_path else None
        try:
            times = results.saved_times(c) if c and c.is_dir() else []
        except OSError:
            times = []
        if not times:
            return {"FINISHED"}
        key = p.run_path
        if MESHES.get("key") != key:
            MESHES.clear()
            MESHES.update(key=key, mesh=results.Mesh(c))
        cp = results.wall_cp(c, times[-1], MESHES["mesh"])
        lo = min(v for _, _, v in cp)
        paint_pressure(ob, cp, lo)
        p.message = f"Cp at {self.alpha:g}°: suction peak {lo:.2f}, stagnation {max(v for _, _, v in cp):.2f}"
        for area in context.screen.areas:
            if area.type == "VIEW_3D":
                shading = area.spaces.active.shading
                if shading.type == "SOLID":
                    shading.color_type = "VERTEX"
        return {"FINISHED"}


def _cp_colour(v, lo):
    """Deep blue at the suction peak `lo`, light grey at Cp = 0, deep red at stagnation (Cp = 1).
    Suction uses a square-root scale so the whole upper surface shows, not just the leading edge."""
    grey, blue, red = (0.75, 0.75, 0.75), (0.02, 0.12, 0.85), (0.85, 0.05, 0.02)
    if v < 0:
        s, end = (min(v / lo, 1.0) ** 0.5 if lo < 0 else 0.0), blue
    else:
        s, end = min(v, 1.0), red
    return tuple(g + s * (e - g) for g, e in zip(grey, end)) + (1.0,)


def paint_pressure(ob, cp, lo):
    """Stores Cp and its colour on the airfoil's vertices (nearest face centre of the CFD wall),
    and gives the object a material that shows the colour when rendered."""
    me = ob.data
    vals = []
    for v in me.vertices:
        x, z = v.co.x, v.co.z
        best = min(cp, key=lambda q: (q[0] - x) ** 2 + (q[1] - z) ** 2)
        vals.append(best[2])
    attr = me.attributes.get("Cp") or me.attributes.new("Cp", "FLOAT", "POINT")
    attr.data.foreach_set("value", vals)
    col = me.color_attributes.get("Cp colour") or me.color_attributes.new("Cp colour", "FLOAT_COLOR", "POINT")
    flat = []
    for v in vals:
        flat.extend(_cp_colour(v, lo))
    col.data.foreach_set("color", flat)
    me.color_attributes.active_color = col
    me.update()

    mat = bpy.data.materials.get("Wind Tunnel Cp")
    if mat is None:
        mat = bpy.data.materials.new("Wind Tunnel Cp")
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        node = nt.nodes.new("ShaderNodeVertexColor")
        node.layer_name = "Cp colour"
        node.location = (-300, 300)
        nt.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.45
    if not ob.data.materials:
        ob.data.materials.append(mat)
    else:
        ob.data.materials[0] = mat


class WT_OT_flow(bpy.types.Operator):
    bl_idname = "wind_tunnel.flow"
    bl_label = "Show flow"
    bl_description = ("Read the solved flow at this angle and draw it: streamline tubes and particles that move at "
                      "the solved speeds, plus a side wall painted with speed or pressure")

    def execute(self, context):
        p = context.scene.wind_tunnel
        if FLOW:
            return {"CANCELLED"}
        ob = _airfoil_object(p)
        c = Path(p.run_path) / case.case_name(p.flow_alpha) if p.run_path else None
        if not ob or not c or not c.is_dir():
            self.report({"ERROR"}, "Run the case first, then pick an angle in the results table")
            return {"CANCELLED"}
        ob.rotation_euler = (0.0, math.radians(p.flow_alpha), 0.0)
        alpha, naca, lines, stations = p.flow_alpha, p.naca, p.flow_lines, p.flow_stations
        FLOW.update(scene=context.scene.name, done=None, error=None, started=time.time())
        p.message = f"Reading the {alpha:g}° flow field"

        def work():
            try:
                from . import flowfield
                times = results.saved_times(c)
                cache = c / f"field_{times[-1]}.npz"
                if cache.exists():
                    field = flowfield.Field.load(cache)
                else:
                    up, lo = case.naca4(naca, 200)
                    field = flowfield.Field.from_case(c, times[-1], list(reversed(up)) + lo[1:-1])
                    try:
                        field.save(cache)
                    except OSError:
                        pass
                seeds = flowfield.seed_line(alpha, lines, width=1.0)
                paths, speeds = flowfield.trace(field, seeds)
                FLOW["done"] = (field, paths, speeds)
            except Exception as e:
                FLOW["error"] = f"{type(e).__name__}: {e}"

        threading.Thread(target=work, daemon=True).start()
        bpy.app.timers.register(_flow_poll, first_interval=0.5)
        return {"FINISHED"}


def _flow_poll():
    st = FLOW
    if not st:
        return None
    scene = bpy.data.scenes.get(st["scene"])
    p = scene.wind_tunnel if scene else None
    if p is None or st["error"]:
        if p:
            p.message = st["error"]
        FLOW.clear()
        _redraw()
        return None
    if st["done"] is None:
        p.message = f"Reading the flow field, {int(time.time() - st['started'])} s"
        _redraw()
        return 0.5
    from . import viz
    field, paths, speeds = st["done"]
    ob = _airfoil_object(p)
    viz.remove_all()
    half = 0.8 if p.flow_stations > 1 else 0.0
    stations = [(-half + 2 * half * i / max(p.flow_stations - 1, 1)) for i in range(p.flow_stations)]
    paths_ob, n_paths, N = viz.write_paths(ob, paths, speeds, stations)
    if p.flow_streamlines:
        viz.build_streamlines(ob, paths_ob)
    if p.flow_particles:
        viz.build_particles(ob, paths_ob, n_paths, N, steps_per_frame=p.flow_speed)
    if p.flow_wall != "NONE":
        viz.build_wall(ob, field, p.flow_wall, y=1.0)
    sc = bpy.context.scene
    viz.data_colours(sc)
    sc.frame_start, sc.frame_end = 1, max(sc.frame_end, 250)
    p.message = f"Flow at {p.flow_alpha:g}°: {n_paths} streamlines, play the timeline for particles"
    FLOW.clear()
    _redraw()
    return None


class WT_OT_flow_clear(bpy.types.Operator):
    bl_idname = "wind_tunnel.flow_clear"
    bl_label = "Clear flow"
    bl_description = "Remove the streamlines, particles and side wall"

    def execute(self, context):
        from . import viz
        viz.remove_all()
        return {"FINISHED"}


# ---------------------------------------------------------------- 3D wind tunnel
def _safe(name):
    return "".join(c if c.isalnum() else "_" for c in name)[:40] or "body"


def signature(ob):
    """A cheap fingerprint of what OpenFOAM saw: name, mesh size, world bounding box, modifiers."""
    if ob is None:
        return ""
    from mathutils import Vector
    corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = [round(min(c[i] for c in corners), 4) for i in range(3)]
    hi = [round(max(c[i] for c in corners), 4) for i in range(3)]
    me = ob.data
    mods = ",".join(f"{m.type}:{m.show_viewport}" for m in ob.modifiers)
    return f"{ob.name}|{len(me.vertices)}|{len(me.polygons)}|{lo}|{hi}|{mods}"


def start_run3d(scene, ob):
    """Starts a 3D solve of `ob`; returns an error message, or None when it started."""
    from . import case3d, viz3d
    p = scene.wind_tunnel
    if RUN3D:
        return "A 3D run is already going"
    if ob is None or ob.type != "MESH" or ob.name.startswith("WT "):
        return "Select the mesh object to test"
    if not p.distro and bpy.ops.wind_tunnel.check() != {"FINISHED"}:
        return "OpenFOAM not found"
    tris = viz3d.object_triangles(ob)
    if len(tris) < 4:
        return "The object has no faces"
    levels = case3d.PRESETS[p.quality]
    s = case3d.Setup3D(speed=p.wind_speed, ground=p.ground, surface_levels=levels[0], wake_level=levels[1],
                       cells_per_L=levels[2], iterations=p.iterations3d, procs=max(1, min(p.cores or 4, 24)))
    root_linux = f"{p.home}/wind_tunnel/3d_{_safe(ob.name)}"
    root = wsl.windows_path(p.distro, root_linux)
    p.run3d_path, p.body3d, p.message3d = str(root), ob.name, f"Solving {ob.name}: writing the case"
    sig = signature(ob)
    RUN3D.update(scene=scene.name, root=root, proc=None, error=None, started=time.time(),
                 built=None, building=False, sig=sig, body=ob.name)
    WATCH["failed"] = ""
    _show_flow(False)
    home, distro = p.home, p.distro
    exporter = Path(__file__).parent / "export_field.py"

    def prepare():
        try:
            wsl.own_folder(distro, f"{home}/wind_tunnel", home)
            case3d.write_case(root, tris, s, exporter=exporter)
            (root / "sig.txt").write_text(sig, newline="\n")      # which shape this case solves
            RUN3D["proc"] = wsl.launch(distro, f"{root_linux}/Allrun", home)
        except Exception as e:
            RUN3D["error"] = f"{type(e).__name__}: {e}"

    threading.Thread(target=prepare, daemon=True).start()
    bpy.app.timers.register(_poll3d, first_interval=1.0)
    return None


def _show_flow(visible):
    """Shows or hides the slice (it only means something for the solved shape). The smoke always
    stays: without a matching field it runs in preview, still reacting to the Test Object's surface."""
    for name in ("WT Slice", "WT Legend", "WT Label"):
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.hide_viewport == visible:
            ob.hide_viewport = ob.hide_render = not visible


def _world_bounds(ob):
    from mathutils import Vector
    corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return ([min(c[i] for c in corners) for i in range(3)], [max(c[i] for c in corners) for i in range(3)])


def _testable(ob):
    return ob is not None and ob.type == "MESH" and not ob.name.startswith("WT ")


def ensure_smoke(scene, ob):
    """WT Smoke with `ob` in its Test Object field (created in preview mode when missing)."""
    from . import viz3d
    mod = viz3d.smoke_modifier()
    if mod is None:
        lo, hi = _world_bounds(ob)
        L = max(hi[i] - lo[i] for i in range(3)) or 1.0
        viz3d.build_smoke(ob, L, scene.wind_tunnel.wind_speed, scene.render.fps, use_field=False)
        scene.frame_start, scene.frame_end = 1, max(scene.frame_end, 250)
    elif viz3d.get_input(mod, "Test Object") != ob:
        viz3d.set_input(mod, "Test Object", ob)
    return viz3d.smoke_modifier()


def _cached(p, ob):
    """Run folder of a finished solve of exactly this shape, or None."""
    if not p.distro:
        return None
    root = wsl.windows_path(p.distro, f"{p.home}/wind_tunnel/3d_{_safe(ob.name)}")
    try:
        if (_read(root / "status") == "done" and (root / "field.npz").exists()
                and _read(root / "sig.txt") == signature(ob)):
            return root
    except OSError:
        pass
    return None


def load_cached(scene, ob, root):
    p = scene.wind_tunnel
    p.run3d_path, p.body3d, p.message3d = str(root), ob.name, f"Loading the solved flow of {ob.name}"
    RUN3D.update(scene=scene.name, root=root, proc=_Finished(), error=None, started=time.time(),
                 built=None, building=False, sig=signature(ob), body=ob.name)
    bpy.app.timers.register(_poll3d, first_interval=0.2)


class WT_OT_run3d(bpy.types.Operator):
    bl_idname = "wind_tunnel.run3d"
    bl_label = "Solve 3D"
    bl_description = ("Put the active object in a virtual wind tunnel: snappyHexMesh around its surface, "
                      "simpleFoam in parallel in WSL, then the flow comes back as a volume")

    def execute(self, context):
        from . import viz3d
        ob = context.active_object
        if not _testable(ob):
            mod = viz3d.smoke_modifier()
            ob = viz3d.get_input(mod, "Test Object") if mod else None
        if _testable(ob):
            ensure_smoke(context.scene, ob)
        err = start_run3d(context.scene, ob)
        if err:
            self.report({"ERROR"}, err)
            return {"CANCELLED"}
        return {"FINISHED"}


class WT_OT_load3d(bpy.types.Operator):
    bl_idname = "wind_tunnel.load3d"
    bl_label = "Load 3D result"
    bl_description = "Bring back the last finished 3D run of the active object (forces and flow volume)"

    def execute(self, context):
        p = context.scene.wind_tunnel
        ob = context.active_object
        if RUN3D:
            return {"CANCELLED"}
        if not p.distro and bpy.ops.wind_tunnel.check() != {"FINISHED"}:
            return {"CANCELLED"}
        name = ob.name if ob is not None and not ob.name.startswith("WT ") else p.body3d
        root = wsl.windows_path(p.distro, f"{p.home}/wind_tunnel/3d_{_safe(name)}")
        if not (root / "field.npz").exists():
            self.report({"ERROR"}, f"No finished 3D run for {name}")
            return {"CANCELLED"}
        body = bpy.data.objects.get(name)
        if _testable(body):
            ensure_smoke(context.scene, body)
            (root / "sig.txt").write_text(signature(body), newline="\n")   # loaded on purpose: trust it
            load_cached(context.scene, body, root)
        return {"FINISHED"}


class WT_OT_stop3d(bpy.types.Operator):
    bl_idname = "wind_tunnel.stop3d"
    bl_label = "Stop 3D"
    bl_description = "Stop the 3D run"

    def execute(self, context):
        p = context.scene.wind_tunnel
        if RUN3D:
            root_linux = f"{p.home}/wind_tunnel/3d_{_safe(p.body3d)}"
            cmd = wsl.stop3d_command(root_linux)
            try:
                wsl.run(["wsl", "-d", p.distro, "-e", "sh", "-c", cmd], timeout=30)
            except Exception as e:
                self.report({"WARNING"}, str(e))
        return {"FINISHED"}


class WT_OT_slice_animate(bpy.types.Operator):
    bl_idname = "wind_tunnel.slice_animate"
    bl_label = "Animate slice"
    bl_description = ("Sweep WT Slice over plus/minus 1 L about the body along the chosen axis, 192 frames "
                      "ping-pong, one keyframe per frame (replaces earlier sweep keyframes). The flow is "
                      "steady: every frame shows the same solved field at the slice's position")

    def execute(self, context):
        from . import viz3d
        if bpy.data.objects.get(viz3d.SLICE) is None:
            self.report({"ERROR"}, "Load a 3D result first (no WT Slice)")
            return {"CANCELLED"}
        viz3d.animate_slice(context.scene.wind_tunnel.sweep_axis, 192, context.scene)
        return {"FINISHED"}


class WT_OT_slice_clear(bpy.types.Operator):
    bl_idname = "wind_tunnel.slice_clear"
    bl_label = "Clear"
    bl_description = "Remove the slice sweep keyframes and put WT Slice back through the body centre"

    def execute(self, context):
        from . import viz3d
        viz3d.clear_slice_animation()
        return {"FINISHED"}


def apply_forces3d(p, f):
    """Panel values from a forces.json: forces, the convergence verdict, y+ and prism layers."""
    p.drag, p.lift, p.side = f["drag_N"], f["lift_N"], f["side_N"]
    p.cd3d, p.cl3d, p.area3d, p.cells3d = f["Cd"], f["Cl"], f["frontal_area_m2"], int(f["cells"])
    p.converged3d = results.forces_converged(f)
    p.verdict3d = "\n".join(results.verdict_lines(f))
    wall, p.wall_alert3d = results.wall_lines(f)
    p.wall3d = "\n".join(wall)
    if p.converged3d:                                  # window means, not the last iteration
        p.drag, p.lift, p.side = f["drag_N_mean"], f["lift_N_mean"], f["side_N_mean"]
        p.cd3d, p.cl3d = f["Cd_mean"], f["Cl_mean"]


def _poll3d():
    import json
    st = RUN3D
    if not st:
        return None
    scene = bpy.data.scenes.get(st["scene"])
    p = scene.wind_tunnel if scene else None
    if p is None:
        RUN3D.clear()
        return None
    root = Path(st["root"])
    if st["error"]:
        p.message3d = st["error"]
        WATCH["failed"] = st.get("sig", "")
        RUN3D.clear()
        _redraw()
        return None
    if st["proc"] is None:
        return 1.0
    elapsed = int(time.time() - st["started"])
    clock = f"{elapsed // 60}:{elapsed % 60:02d}"
    status = _read(root / "status") or "starting"
    if status.startswith("failed") or status == "stopped" or (st["proc"].poll() is not None and status not in ("done",)):
        step = status.replace("failed", "").strip()
        tail = ""
        if step:
            try:
                lines = (root / f"log.{step}").read_text(errors="replace").strip().splitlines()
                tail = next((l.strip() for l in reversed(lines) if "FOAM FATAL" in l or "Error" in l or "error" in l), lines[-1])
            except OSError:
                pass
        p.message3d = f"{status} after {clock}. {tail}"[:240]
        WATCH["failed"] = st.get("sig", "")
        RUN3D.clear()
        _redraw()
        return None
    if status != "done":
        it, res = results.progress(root)
        extra = f", iteration {it}" if status == "solving" and it else ""
        extra += f", p residual {res:.1e}" if extra and res else ""
        p.message3d = f"{status}{extra}, {clock}"
        _redraw()
        return 2.0

    # Finished: forces, then the volume (written in the background), then the scene objects.
    if st["built"] is None and not st["building"]:
        st["building"] = True

        def build():
            from . import viz3d
            try:
                lo, hi, U = viz3d.write_vdb(root / "field.npz", root / "flow.vdb")
                st["built"] = (lo, hi, U, json.loads((root / "forces.json").read_text()))
            except Exception as e:
                st["error"] = f"{type(e).__name__}: {e}"

        threading.Thread(target=build, daemon=True).start()
        p.message3d = "Writing the flow volume"
        return 0.5
    if st["built"] is None:
        return 0.5
    from . import viz3d
    lo, hi, U, f = st["built"]
    apply_forces3d(p, f)
    p.body3d = p.forces_body = st.get("body", p.body3d)
    body = bpy.data.objects.get(p.body3d)
    viz3d.load_volume(root / "flow.vdb")
    if body is not None:
        tris = viz3d.object_triangles(body)
        blo = [min(v[i] for t in tris for v in t) for i in range(3)]
        bhi = [max(v[i] for t in tris for v in t) for i in range(3)]
    else:
        blo, bhi = list(lo), list(hi)
    L = max(bhi[i] - blo[i] for i in range(3))
    for old in ("WT Rake", "WT Slice"):                  # the release plane now lives in the node tree
        if bpy.data.objects.get(old):
            bpy.data.objects.remove(bpy.data.objects[old])
    mod = viz3d.smoke_modifier()
    if mod is None:
        viz3d.build_smoke(body, L, U, scene.render.fps, use_field=False)
        mod = viz3d.smoke_modifier()
    viz3d.set_input(mod, "Flow", bpy.data.objects.get(viz3d.FLOW))
    viz3d.tune_smoke(mod, L, U, scene.render.fps)
    viz3d.build_slice(lo, hi, blo, bhi)
    from . import viz
    viz.data_colours(scene)
    scene.frame_start, scene.frame_end = 1, max(scene.frame_end, 250)
    p.solved_sig, p.field_stale = st.get("sig", ""), False
    RUN3D.clear()
    WATCH["key"] = None
    _apply(scene)
    if WATCH["key"] and WATCH["key"][0] in ("solved", "unconverged"):
        how = "loaded from its earlier run" if isinstance(st["proc"], _Finished) else f"finished in {clock}"
        verdict = "converged" if p.converged3d else "NOT converged"
        p.message3d = f"{p.body3d} {how}, {verdict}: play the timeline; WT Slice moves freely"
    _redraw()
    return None


# ---------------------------------------------------------------- keeping the field honest
WATCH = {"changed": 0.0, "key": None, "failed": ""}


def field_state(scene):
    """(Test Object, state): state is 'none' (no WT Smoke), 'empty' (no Test Object), 'solved' (the
    loaded field is this object's, as it is now, and its run passed the convergence gate),
    'unconverged' (the same, but the gate never passed), 'solving' (its run is going) or 'preview'."""
    from . import viz3d
    p = scene.wind_tunnel
    mod = viz3d.smoke_modifier()
    if mod is None:
        return None, "none"
    test = viz3d.get_input(mod, "Test Object")
    if not _testable(test):
        return None, "empty"
    sig = signature(test)
    if RUN3D and RUN3D.get("body") == test.name and RUN3D.get("sig") == sig:
        return test, "solving"
    if (bpy.data.objects.get(viz3d.FLOW) is not None and test.name == p.body3d and p.solved_sig == sig
            and not RUN3D):
        return test, "solved" if p.converged3d else "unconverged"
    return test, "preview"


def _apply(scene):
    """Makes the node setup match the Test Object: the solved field only when it belongs to it."""
    from . import viz3d
    p = scene.wind_tunnel
    test, state = field_state(scene)
    mod = viz3d.smoke_modifier()
    loaded = state in ("solved", "unconverged")
    if mod is not None and viz3d.get_input(mod, "Use Field") != loaded:
        viz3d.set_input(mod, "Use Field", loaded)
    _show_flow(loaded)
    p_stale = state == "preview"
    if p.field_stale != p_stale:
        p.field_stale = p_stale
    key = (state, test.name if test else "")
    if key != WATCH["key"]:
        WATCH["key"] = key
        if state == "solved":
            p.message3d = f"Flow matches {test.name} as solved"
        elif state == "unconverged":
            p.message3d = f"Flow of {test.name} is from a run that did NOT converge"
        elif state == "preview":
            p.message3d = (f"Preview for {test.name}: particles slide around its surface; "
                           f"OpenFOAM flow {'on its way' if p.auto_resolve else 'needs Solve 3D'}")
        elif state == "empty":
            p.message3d = "Assign a Test Object on WT Smoke (or select a mesh and Solve 3D)"
        _redraw()
    return test, state


def _auto_tick():
    scene = bpy.context.scene
    p = scene.wind_tunnel
    test, state = field_state(scene)
    if state != "preview":
        return None
    if time.time() - WATCH["changed"] < 3.0:
        return 1.0                                  # wait until editing has paused
    root = _cached(p, test)
    if root is not None and not RUN3D:
        load_cached(scene, test, root)
        return None
    if not p.auto_resolve:
        return None
    if RUN3D:
        p.message3d = f"Preview for {test.name}: waiting for the {RUN3D.get('body', '')} run to finish"
        return 2.0
    if signature(test) == WATCH["failed"]:
        return None                                 # this exact shape just failed: leave the message
    err = start_run3d(scene, test)
    if err:
        p.message3d = f"Auto solve: {err}"
    return None


def _react(scene):
    try:
        test, state = _apply(scene)
    except Exception:
        return
    if state == "preview" and not bpy.app.timers.is_registered(_auto_tick):
        bpy.app.timers.register(_auto_tick, first_interval=1.0)
    return state


@bpy.app.handlers.persistent
def _on_depsgraph(scene, depsgraph):
    if not depsgraph.id_type_updated("OBJECT") and not depsgraph.id_type_updated("MESH"):
        return
    if _react(scene) == "preview":
        WATCH["changed"] = time.time()                # an edit: restart the quiet-time count


def _watch():
    """Once a second: catches Test Object changes that arrive without a depsgraph update."""
    try:
        _react(bpy.context.scene)
    except Exception:
        pass
    return 1.0


class WT_OT_open(bpy.types.Operator):
    bl_idname = "wind_tunnel.open"
    bl_label = "Open case folder"
    bl_description = "Open the run folder (inside WSL) in Explorer"

    def execute(self, context):
        path = context.scene.wind_tunnel.run_path
        if path and os.path.isdir(path):
            os.startfile(path)
        return {"FINISHED"}


# ---------------------------------------------------------------- polling and analysis
def _read(path: Path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _analyse_all(st):
    out = {}
    try:
        mesh = None
        for a in st["alphas"]:
            c = Path(st["root"]) / case.case_name(a)
            try:
                mesh = mesh or results.Mesh(c)
                out[a] = results.analyse(c, st["nu"], a, mesh, last=3)
            except Exception as e:
                out[a] = {"error": f"{type(e).__name__}: {e}"}
    finally:
        st["analysis"] = out


def _poll():
    st = RUN
    if not st:
        return None
    scene = bpy.data.scenes.get(st["scene"])
    if scene is None:
        RUN.clear()
        return None
    p = scene.wind_tunnel
    root = Path(st["root"])

    if st["error"]:
        p.state, p.message = "failed", st["error"]
        RUN.clear()
        _redraw()
        return None
    if st["proc"] is None:
        return 1.0

    status = _read(root / "status") or "starting"
    for r in p.results:
        c = root / case.case_name(r.alpha)
        it, res = results.progress(c)
        r.iteration, r.residual = it, res or 0.0
        code = _read(c / "exit")
        if code:
            r.state = "finished" if code == "0" else "failed"
        elif it:
            r.state = "running"
    elapsed = int(time.time() - st["started"])
    p.state = status
    p.message = f"{status}, {elapsed // 60}:{elapsed % 60:02d}" if st["thread"] is None else "Integrating forces"

    finished = status in ("done", "stopped", "failed") or st["proc"].poll() is not None
    if finished and st["thread"] is None:
        p.message = "Integrating forces"
        st["thread"] = threading.Thread(target=_analyse_all, args=(st,), daemon=True)
        st["thread"].start()
    if st["analysis"] is not None:
        for r in p.results:
            o = st["analysis"].get(r.alpha, {})
            if "error" in o:
                r.note = o["error"]
                continue
            f = o.get("final")
            if f:
                r.cl, r.cd, r.cm, r.has_coeffs = f["Cl"], f["Cd"], f["Cm"], True
            r.converged = bool(o.get("converged"))
            r.note = "; ".join(o.get("reasons", []))
        p.state = "stopped" if st.get("stopping") else "done"
        p.message = f"Finished in {elapsed // 60}:{elapsed % 60:02d}"
        RUN.clear()
        _redraw()
        return None
    _redraw()
    return 2.0


# ---------------------------------------------------------------- panel
class WT_PT_panel(bpy.types.Panel):
    bl_idname = "WT_PT_panel"
    bl_label = "Wind Tunnel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Wind Tunnel"

    def draw(self, context):
        p = context.scene.wind_tunnel
        lay = self.layout

        box = lay.box()
        row = box.row()
        row.label(text=f"OpenFOAM: {p.distro}" if p.distro else "OpenFOAM: not found yet", icon="CONSOLE")
        row.operator("wind_tunnel.check", text="", icon="FILE_REFRESH")

        box = lay.box()
        box.label(text="Airfoil", icon="MOD_SIMPLIFY")
        row = box.row(align=True)
        row.prop(p, "naca")
        row.operator("wind_tunnel.airfoil", text="", icon="MESH_DATA")

        box = lay.box()
        box.label(text="Flow", icon="FORCE_WIND")
        box.prop(p, "reynolds")
        box.prop(p, "angles")
        row = box.row(align=True)
        row.prop(p, "iterations")
        row.prop(p, "y_plus")

        row = lay.row(align=True)
        row.scale_y = 1.4
        if RUN:
            row.operator("wind_tunnel.stop", icon="CANCEL")
        else:
            row.operator("wind_tunnel.run", icon="PLAY")
            row.operator("wind_tunnel.load", text="", icon="IMPORT")
        if p.message:
            lay.label(text=p.message, icon="INFO")

        box = lay.box()
        box.label(text="3D wind tunnel", icon="MOD_OCEAN")
        from . import viz3d
        mod = viz3d.smoke_modifier()
        drawn = False
        if mod is not None and mod.node_group is not None:
            for item in mod.node_group.interface.items_tree:
                if getattr(item, "in_out", None) == "INPUT" and item.name == "Test Object":
                    try:
                        props = getattr(mod, "properties", None)
                        if props is not None and hasattr(props, "inputs"):
                            box.prop(getattr(props.inputs, item.identifier), "value", text="Test Object")
                        else:
                            box.prop(mod, f'["{item.identifier}"]', text="Test Object")
                        drawn = True
                    except Exception:
                        pass
        if not drawn:
            ob = context.active_object
            box.label(text=f"Object: {ob.name}" if _testable(ob) else "Select the mesh to test",
                      icon="OBJECT_DATA")
        row = box.row(align=True)
        row.prop(p, "wind_speed")
        row.prop(p, "ground", toggle=True)
        row = box.row(align=True)
        row.prop(p, "quality", expand=True)
        row = box.row(align=True)
        row.prop(p, "iterations3d")
        row.prop(p, "auto_resolve", toggle=True, icon="FILE_REFRESH")
        if p.field_stale:
            warn = box.row()
            warn.alert = True
            warn.label(text="Preview only: not solved yet", icon="ERROR")
        row = box.row(align=True)
        row.scale_y = 1.4
        if RUN3D:
            row.operator("wind_tunnel.stop3d", icon="CANCEL")
        else:
            row.operator("wind_tunnel.run3d", icon="PLAY")
            row.operator("wind_tunnel.load3d", text="", icon="IMPORT")
        if p.message3d:
            box.label(text=p.message3d, icon="INFO")
        if p.cells3d:
            col = box.column(align=True)
            who = p.forces_body or p.body3d
            if field_state(context.scene)[1] not in ("solved", "unconverged"):
                col.alert = True
                who += " (last solve, not the Test Object)"
            col.label(text=f"{who}: {p.cells3d:,} cells, frontal area {p.area3d:.4f} m²")
            verdict = col.column(align=True)
            verdict.alert = not p.converged3d
            for line in (p.verdict3d or "Not converged:\nno convergence record").splitlines():
                verdict.label(text=line)
            if p.wall3d:
                wall = col.column(align=True)
                wall.alert = p.wall_alert3d
                for i, line in enumerate(p.wall3d.splitlines()):
                    wall.label(text=line, icon=("ERROR" if p.wall_alert3d else "CHECKMARK") if i == 0 else "NONE")
            if bpy.data.objects.get("WT Slice") is not None:
                row = box.row(align=True)
                row.prop(p, "sweep_axis", expand=True)
                row.operator("wind_tunnel.slice_animate", icon="ANIM")
                row.operator("wind_tunnel.slice_clear", icon="X")

        if not len(p.results):
            return
        nasa = results.NASA_0012_SST if p.naca == "0012" and abs(p.reynolds - 6e6) < 1 else {}
        box = lay.box()
        cols = box.grid_flow(row_major=True, columns=5, even_columns=False, align=True)
        for t in ("α°", "Cl", "Cd ×10⁴", "Cm", ""):
            cols.label(text=t)
        notes = []
        for r in p.results:
            cols.label(text=f"{r.alpha:g}")
            if r.has_coeffs:
                cols.label(text=f"{r.cl + 0.0:.3f}" if abs(r.cl) >= 5e-4 else "0.000")
                cols.label(text=f"{r.cd * 1e4:.0f}")
                cols.label(text=f"{r.cm:.3f}" if abs(r.cm) >= 5e-4 else "0.000")
            else:
                cols.label(text=r.state)
                cols.label(text=f"{r.iteration}" if r.iteration else "")
                cols.label(text=f"{r.residual:.0e}" if r.residual else "")
            icon = "CHECKMARK" if r.converged else ("ERROR" if r.has_coeffs else "TIME")
            op = cols.operator("wind_tunnel.show", text="", icon=icon, emboss=r.has_coeffs)
            op.alpha = r.alpha
            ref = nasa.get(r.alpha)
            if ref and r.has_coeffs:
                dcl = f" ({100 * (r.cl - ref[0]) / ref[0]:+.1f}%)" if ref[0] else ""
                notes.append(f"{r.alpha:g}°  NASA Cl {ref[0]:.3f}{dcl}, Cd {ref[1] * 1e4:.0f} ({100 * (r.cd - ref[1]) / ref[1]:+.0f}%)")
            if r.note and r.has_coeffs and not r.converged:
                notes.append(f"{r.alpha:g}°  {r.note}")
        if any(r.has_coeffs for r in p.results):
            box.label(text="Click a row's icon to show its pressure", icon="MOUSE_LMB")
        if notes:
            col = box.column(align=True)
            col.scale_y = 0.8
            for n in notes:
                col.label(text=n)
        if any(r.has_coeffs for r in p.results):
            box = lay.box()
            box.label(text=f"Flow at {p.flow_alpha:g}°", icon="MOD_FLUIDSIM")
            row = box.row(align=True)
            row.prop(p, "flow_streamlines", toggle=True)
            row.prop(p, "flow_particles", toggle=True)
            row = box.row(align=True)
            row.prop(p, "flow_lines")
            row.prop(p, "flow_stations")
            box.prop(p, "flow_speed")
            box.prop(p, "flow_wall", expand=True)
            row = box.row(align=True)
            row.scale_y = 1.3
            row.operator("wind_tunnel.flow", icon="PLAY" if not FLOW else "TIME")
            row.operator("wind_tunnel.flow_clear", text="", icon="TRASH")
        if p.run_path:
            lay.operator("wind_tunnel.open", icon="FILE_FOLDER")


classes = (WT_Result, WT_Props, WT_OT_check, WT_OT_airfoil, WT_OT_run, WT_OT_load, WT_OT_stop, WT_OT_show,
           WT_OT_flow, WT_OT_flow_clear, WT_OT_run3d, WT_OT_load3d, WT_OT_stop3d, WT_OT_slice_animate,
           WT_OT_slice_clear, WT_OT_open, WT_PT_panel)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.wind_tunnel = PointerProperty(type=WT_Props)
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    if not bpy.app.timers.is_registered(_watch):
        bpy.app.timers.register(_watch, first_interval=2.0, persistent=True)


def unregister():
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    for fn in (_poll, _flow_poll, _poll3d, _auto_tick, _watch):
        if bpy.app.timers.is_registered(fn):
            bpy.app.timers.unregister(fn)
    del bpy.types.Scene.wind_tunnel
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
