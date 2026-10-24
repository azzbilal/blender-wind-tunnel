"""FIX_PLAN step 3 probe round 2: a Blender icosphere (5 subdivisions, r = 1 m, at the origin) as a
binary STL, to separate the UV sphere's faceting and poles from layer stack depth.

  blender --background --factory-startup --python tools/audit/step3_icosphere.py -- OUT.stl
"""
import struct
import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1.0, location=(0, 0, 0))
me = bpy.context.active_object.data
me.calc_loop_triangles()
v = me.vertices
buf = bytearray(b"body".ljust(80, b" ")) + struct.pack("<I", len(me.loop_triangles))
for t in me.loop_triangles:
    a, b, c = (v[i].co for i in t.vertices)
    n = (b - a).cross(c - a)
    buf += struct.pack("<12fH", *n, *a, *b, *c, 0)
open(out, "wb").write(bytes(buf))
print("icosphere triangles", len(me.loop_triangles), "vertices", len(v))
