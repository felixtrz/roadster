"""Roadster v6: assembled from authored parts.

    Blender -b roadster_v6.blend -P build_v6.py -- [--export]

The body skin comes from shell.npz (character lines in design.py, traced from the orthographic
turnaround). It is cut into the car's real panels (front bumper, hood, fenders, doors, rear quarters,
rockers, canopy glass, side glass, rear deck, tail) with panel gaps, then the front fascia, tail,
diffuser, nozzles, wheels and lamps are added as their own parts. Blender axes: metres, z up, faces -Y,
left +X, floor z = 0. Export turns the root +90 deg about up so the glTF car faces +X.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

# Paths are resolved from this script (Blender sets __file__ for -P scripts); fall back to the .blend.
try:
    HERE = os.path.dirname(os.path.abspath(__file__)) + os.sep
except NameError:
    HERE = os.path.dirname(bpy.data.filepath) + os.sep
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
import importlib
import design as D
importlib.reload(D)

ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
if not bpy.data.filepath.endswith('/art/roadster/model-v6/roadster_v6.blend'):
    raise RuntimeError(f'refusing to run in {bpy.data.filepath!r}')
COL = 'RoadsterV6'
GAP = 0.003


# ---------------------------------------------------------------- materials
def mat(name, base, rough=0.5, metal=0.0, coat=0.0, emit=None, strength=0.0, coat_rough=0.03):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs[0])
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = coat_rough
    if name.startswith('Glass'):
        b.inputs['Specular IOR Level'].default_value = 0.35
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = strength
    m.diffuse_color = (*base, 1)
    return m


def materials():
    return {
        'paint': mat('Paint_PearlWhite', (0.90, 0.905, 0.91), 0.09, 0.0, coat=1.0, coat_rough=0.015),
        'black': mat('Trim_GlossBlack', (0.008, 0.008, 0.009), 0.18, 0.0, coat=1.0),
        'satin': mat('Trim_SatinBlack', (0.006, 0.006, 0.0065), 0.75),
        'glass': mat('Glass_GoldTint', (0.085, 0.056, 0.03), 0.04, 0.55, coat=1.0, coat_rough=0.0),
        'gap': mat('PanelGap', (0.002, 0.002, 0.002), 0.9),
        'tyre': mat('Tyre_Rubber', (0.006, 0.006, 0.0065), 0.9),
        'disc': mat('Wheel_AeroGraphite', (0.05, 0.052, 0.056), 0.38, 0.5, coat=0.2, coat_rough=0.3),
        'discdark': mat('Wheel_SlotInsert', (0.004, 0.004, 0.005), 0.7, 0.0),
        'rotor': mat('Brake_Rotor', (0.22, 0.22, 0.23), 0.4, 1.0),
        'brass': mat('Nozzle_Brass', (0.78, 0.55, 0.27), 0.26, 1.0),
        'throat': mat('Nozzle_Throat', (0.03, 0.02, 0.012), 0.6, 1.0),
        'headlamp': mat('Lamp_Headlamp', (1, 1, 1), 0.15, emit=(0.92, 0.97, 1.0), strength=18.0),
        'drl': mat('Lamp_DRL', (1, 1, 1), 0.2, emit=(0.88, 0.95, 1.0), strength=7.0),
        'red': mat('Lamp_TailRed', (0.4, 0.0, 0.01), 0.25, emit=(1.0, 0.03, 0.05), strength=7.0),
        'redhot': mat('Lamp_TailRedCentre', (0.5, 0.02, 0.03), 0.25, emit=(1.0, 0.12, 0.12), strength=11.0),
        'tray': mat('Underbody_Tray', (0.035, 0.037, 0.04), 0.55, 0.3),
        'amber': mat('Lamp_Amber', (0.6, 0.3, 0.0), 0.25, emit=(1.0, 0.42, 0.05), strength=8.0),
        'lens': mat('Lamp_Lens', (0.01, 0.01, 0.012), 0.04, coat=1.0),
        'plate': mat('Plate', (0.72, 0.73, 0.74), 0.35, 0.2),
        'spoke': mat('Wheel_SpokeGunmetal', (0.018, 0.019, 0.021), 0.42, 0.6, coat=0.2, coat_rough=0.2),
        'wheelface': mat('Wheel_AeroFace', (0.80, 0.805, 0.81), 0.22, 0.35, coat=0.6, coat_rough=0.05),
    }


# ---------------------------------------------------------------- helpers
def new_obj(name, bm, material, parent, smooth_angle=None, mats=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if mats:
        for m in mats:
            me.materials.append(m)
    else:
        me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    bpy.data.collections[COL].objects.link(ob)
    ob.parent = parent
    for p in me.polygons:
        p.use_smooth = True
    if smooth_angle is not None:
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    return ob


def empty(name, parent, loc=(0, 0, 0)):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.05
    bpy.data.collections[COL].objects.link(e)
    e.parent = parent
    e.location = loc
    return e


def box(w, d, h, c):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * w + c[0], v.co.y * d + c[1], v.co.z * h + c[2]))
    return bm


def prism(poly_xz, y0, y1):
    """Extrude a convex/concave polygon in the x-z plane along y."""
    bm = bmesh.new()
    a = [bm.verts.new((x, y0, z)) for x, z in poly_xz]
    b = [bm.verts.new((x, y1, z)) for x, z in poly_xz]
    bm.faces.new(a)
    bm.faces.new(b[::-1])
    n = len(a)
    for k in range(n):
        bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def lathe(profile, sides, caps=True):
    """Surface of revolution about +X; profile [(x, r)]."""
    bm = bmesh.new()
    rings = [[bm.verts.new((x, r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides)))
              for k in range(sides)] for x, r in profile]
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    if caps and profile[0][1] > 1e-4:
        bm.faces.new(list(reversed(rings[0])))
    if caps and profile[-1][1] > 1e-4:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def side_plane(p0, p1):
    """Plane containing the side-view (y, z) line p0->p1 and the x axis: (co, normal)."""
    (y0, z0), (y1, z1) = p0, p1
    n = Vector((0, z1 - z0, -(y1 - y0))).normalized()
    return Vector((0, y0, z0)), n


def side_of(p, plane):
    co, n = plane
    return (Vector(p) - co).dot(n)


# ---------------------------------------------------------------- body skin and panels
def body_skin():
    d = np.load(HERE + 'shell.npz')
    co, quads, region, M = d['co'], d['quads'], d['region'], int(d['M'])
    S = len(co) // M
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(p)) for p in co]
    reg = bm.faces.layers.string.new('region')
    for q, r in zip(quads, region):
        f = bm.faces.new([vs[i] for i in q])
        f[reg] = str(r).encode()
    # sharp creases on the character lines (constant ring columns)
    sharp_cols = set(int(c) for c in d['sharp_cols'])
    bm.verts.index_update()
    for e in bm.edges:
        a, b = e.verts[0].index, e.verts[1].index
        if a // M != b // M and a % M == b % M and a % M in sharp_cols:
            pass
        if a // M == b // M:
            continue
        if a % M == b % M and a % M in sharp_cols:
            e.smooth = False
    # end rings (front and tail outlines) for the fascia and tail
    front = [vs[j] for j in range(M)]
    tail = [vs[(S - 1) * M + j] for j in range(M)]
    return bm, reg, front, tail, M, S


def cut(bm, plane, faces):
    co, n = plane
    geom = list({v for f in faces for v in f.verts}) + list({e for f in faces for e in f.edges}) + list(faces)
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=n, clear_inner=False, clear_outer=False)


def region_faces(bm, reg, names):
    names = {n.encode() for n in names}
    return [f for f in bm.faces if f[reg] in names]


HOOD_SEAM = -1.60     # transverse hood line about a quarter of the hood ahead of the windscreen (press top view)


def classify(bm, reg):
    """Material/part label per skin face after the design cuts."""
    dfront = side_plane(*D.DLO_FRONT)
    drear = side_plane(*D.DLO_REAR)
    dfr = side_plane(*D.DOOR_FRONT)
    drr = side_plane(*D.DOOR_REAR)
    lab = {}
    for f in bm.faces:
        c = f.calc_center_median()
        r = f[reg].decode()
        y, z, x = c.y, c.z, abs(c.x)
        if r in ('C', 'RM') and D.CANOPY[0] - 0.07 < y < D.CANOPY[0]:
            part = 'Cowl'
        elif r == 'C':
            if D.CANOPY[0] < y < D.CANOPY[1]:
                part = 'CanopyGlass'
            elif y < D.CANOPY[0]:
                part = 'HoodFront' if y < HOOD_SEAM else 'Hood'
            else:
                part = 'RearDeck'
        elif r in ('RM', 'RP') and D.CANOPY[0] < y < -1.18:
            part = 'CanopyGlass'
        elif r == 'RM':
            part = ('HoodFront' if y < HOOD_SEAM else 'Hood') if y < D.CANOPY[0] else 'RoofRail'
        elif r == 'RP':
            in_dlo = side_of(c, dfront) > 0 and side_of(c, drear) < 0
            if in_dlo:
                part = 'SideGlass'
            elif y < D.CANOPY[0]:
                part = 'Fender'
            elif y < 0.5:
                part = 'APillar'
            else:
                part = 'RearDeck'
        elif r in ('B', 'S', 'W'):
            if side_of(c, dfr) < 0:
                part = 'Fender'
            elif side_of(c, drr) < 0:
                part = 'Door'
            elif y < 2.16:
                part = 'RearQuarter'
            else:
                part = 'RearQuarter'
        elif r == 'K':
            part = 'Rocker' if -1.95 < y < 1.95 else ('FrontBumperLower' if y < 0 else 'RearBumperLower')
        else:
            part = 'Floor'
        # headlamp pod: the fender tip between the two lamp cuts, ahead of y -2.16
        if part in ('Fender', 'Door', 'RearQuarter', 'Rocker', 'SideGlass', 'APillar', 'RoofRail', 'Headlamp'):
            part += '_L' if c.x > 0 else '_R'
        lab[f.index] = part
    return lab


PART_MAT = {'APillar': 'black', 'Headlamp': 'headlamp', 'Cowl': 'black', 'CanopyGlass': 'glass', 'SideGlass': 'glass', 'Rocker': 'black', 'FrontBumperLower': 'black',
            'RearBumperLower': 'black', 'Floor': 'satin'}


def split_parts(bm, lab, mats, parent):
    """One object per panel; boundary edges pulled in by GAP to open real panel gaps."""
    groups = {}
    for f in bm.faces:
        groups.setdefault(lab[f.index], []).append(f.index)
    objs = []
    bm.faces.ensure_lookup_table()
    for name, idx in groups.items():
        sub = bmesh.new()
        vmap = {}
        for fi in idx:
            f = bm.faces[fi]
            vv = []
            for v in f.verts:
                if v.index not in vmap:
                    vmap[v.index] = sub.verts.new(v.co)
                vv.append(vmap[v.index])
            nf = sub.faces.new(vv)
            nf.smooth = True
            for e_old, e_new in zip(f.edges, nf.edges):
                pass
        sub.verts.ensure_lookup_table()
        sub.normal_update()
        # carry the crease flags: an edge is sharp if the matching skin edge is sharp
        sharp = {(min(e.verts[0].index, e.verts[1].index), max(e.verts[0].index, e.verts[1].index))
                 for e in bm.edges if not e.smooth}
        inv = {nv: ov for ov, nv in vmap.items()}
        for e in sub.edges:
            a, b = inv[e.verts[0]], inv[e.verts[1]]
            if (min(a, b), max(a, b)) in sharp:
                e.smooth = False
        # panel gaps: move boundary vertices inward along the surface
        base = name.rsplit('_', 1)[0]
        if base not in ('Floor',):
            bnd = [e for e in sub.edges if e.is_boundary]
            move = {}
            for e in bnd:
                a, b = e.verts
                f = e.link_faces[0]
                t = (b.co - a.co).normalized()
                inward = f.normal.cross(t)
                if inward.dot(f.calc_center_median() - (a.co + b.co) / 2) < 0:
                    inward = -inward
                for v in (a, b):
                    move.setdefault(v, Vector()).__iadd__(inward)
            for v, m in move.items():
                if m.length > 1e-9:
                    v.co += m.normalized() * (GAP * 1.4 if base in ('Door', 'Hood', 'HoodFront') else GAP)
        material = mats[PART_MAT.get(base, 'paint')]
        ob = new_obj(name, sub, material, parent)
        objs.append(ob)
    return objs


# ---------------------------------------------------------------- arches
def arch_cut(objs, mats):
    for axle, w in D.WHEELS.items():
        for side in (1, -1):
            cyl = lathe([(0.0, w['r'] + 0.035), (0.75, w['r'] + 0.035)], 64)
            bmesh.ops.translate(cyl, vec=(side * 0.55 if side > 0 else -1.30, w['y'], w['r']), verts=cyl.verts)
            me = bpy.data.meshes.new('cut')
            cyl.to_mesh(me)
            cyl.free()
            cutter = bpy.data.objects.new('cut', me)
            bpy.context.scene.collection.objects.link(cutter)
            for ob in objs:
                bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
                ys = [p.y for p in bb]
                xs = [p.x for p in bb]
                if max(ys) < w['y'] - 0.6 or min(ys) > w['y'] + 0.6:
                    continue
                if max(side * x for x in xs) < 0.3:
                    continue
                m = ob.modifiers.new('arch', 'BOOLEAN')
                m.operation = 'DIFFERENCE'
                m.object = cutter
                m.solver = 'EXACT'
                bpy.context.view_layer.objects.active = ob
                n0 = len(ob.data.polygons)
                bpy.ops.object.modifier_apply(modifier=m.name)
                print('ARCH', axle, side, ob.name, n0, '->', len(ob.data.polygons))
            bpy.data.objects.remove(cutter)


def wheel_wells(mats, parent):
    for axle, w in D.WHEELS.items():
        for side in (1, -1):
            r = w['r'] + 0.033
            liner = lathe([(0.0, r), (0.62, r)], 64, caps=False)
            # keep only the upper part of the tube (the arch ceiling)
            bmesh.ops.delete(liner, geom=[f for f in liner.faces if f.calc_center_median().z < -0.05], context='FACES')
            bmesh.ops.translate(liner, vec=(0.56 if side > 0 else -1.18, w['y'], w['r']), verts=liner.verts)
            bmesh.ops.reverse_faces(liner, faces=liner.faces)
            wall = lathe([(0.0, 0.0), (0.0, r)], 64)
            bmesh.ops.translate(wall, vec=(side * 0.56, w['y'], w['r']), verts=wall.verts)
            new_obj(f'WheelWell_{axle}{"L" if side > 0 else "R"}', liner, mats['satin'], parent)
            new_obj(f'WheelWellWall_{axle}{"L" if side > 0 else "R"}', wall, mats['satin'], parent)


# ---------------------------------------------------------------- fascia and tail
# plan-view notch (x, y): apex at the nose corner, base toward the windshield, along the hood crease
NOTCH = [(0.81, -2.274), (0.760, -1.844), (0.640, -1.876)]
NOTCH_D0, NOTCH_D1 = 0.015, 0.030     # pocket depth at the apex, extra depth at the base


def headlamps(skin, core, mats, parent):
    """Headlamps as triangular notches cut into the top surface at each front corner, running back and
    inward along the hood crease, with the lamp inside (press photos: lit arrows in the hood corners).
    The notch is cut from the skin and the inner body, then lined with a recessed pocket."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(skin, bpy.context.evaluated_depsgraph_get())

    def top(x, y):
        loc, nrm, idx, dist = bvh.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))
        return loc.z if loc is not None else 0.52

    A, B1, B2 = (Vector(p) for p in NOTCH)
    base = (B1 + B2) / 2
    axis = base - A
    L = axis.length
    axis.normalize()
    ring = []                               # (point, t along the notch) around the outline
    for P, Q in ((A, B1), (B1, B2), (B2, A)):
        for k in range(10):
            u = k / 10
            q = P.lerp(Q, u)
            ring.append(q)
    cen = (A + B1 + B2) / 3
    pockets = []
    for side in (1, -1):
        m = lambda v: Vector((side * v.x, v.y))
        tops, bots = [], []
        for q in ring:
            t = max(0.0, min(1.0, (q - A).dot(axis) / L))
            depth = NOTCH_D0 + NOTCH_D1 * t
            out = q + (q - cen).normalized() * 0.004
            qo, qm = m(out), m(q)
            tops.append(Vector((qo.x, qo.y, top(qo.x, qo.y) + 0.0015)))
            bots.append(Vector((qm.x, qm.y, top(qm.x, qm.y) - depth)))
        pockets.append((side, tops, bots))
    # cut the notch through the skin and the inner body
    for side in (1, -1):
        bm = bmesh.new()
        lo = [bm.verts.new((side * v[0], v[1], 0.45)) for v in NOTCH]
        hi = [bm.verts.new((side * v[0], v[1], 1.30)) for v in NOTCH]
        bm.faces.new(lo[::-1])
        bm.faces.new(hi)
        for i in range(3):
            j = (i + 1) % 3
            bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new('notch')
        bm.to_mesh(me)
        bm.free()
        cutter = bpy.data.objects.new('notch', me)
        bpy.context.scene.collection.objects.link(cutter)
        # the inner body is only opened under the notch (a boolean on it keeps stray cutter walls)
        cb = bmesh.new()
        cb.from_mesh(core.data)
        tri = [Vector((side * v[0], v[1])) for v in NOTCH]
        def inside(c):
            p = Vector((c.x, c.y))
            d = [(tri[(i + 1) % 3] - tri[i]).cross(p - tri[i]) for i in range(3)]
            return all(x >= -0.02 for x in d) or all(x <= 0.02 for x in d)
        drop = [f for f in cb.faces if f.calc_center_median().z > 0.42 and inside(f.calc_center_median())]
        bmesh.ops.delete(cb, geom=drop, context='FACES')
        cb.to_mesh(core.data)
        cb.free()
        for ob in (skin,):
            mod = ob.modifiers.new('notch', 'BOOLEAN')
            mod.operation = 'DIFFERENCE'
            mod.object = cutter
            mod.solver = 'EXACT'
            bpy.context.view_layer.objects.active = ob
            bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cutter)
    # pocket: walls from the surface down to a sloped floor, then the lamps inside
    for side, tops, bots in pockets:
        nm = 'L' if side > 0 else 'R'
        bm = bmesh.new()
        T = [bm.verts.new(v) for v in tops]
        Bv = [bm.verts.new(v) for v in bots]
        n = len(T)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((T[i], T[j], Bv[j], Bv[i]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        # walls face into the notch (toward its centreline)
        c3 = sum(bots, Vector()) / n
        if sum((f.normal.dot(c3 - f.calc_center_median())) for f in bm.faces) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        new_obj(f'HeadlampPocket_{nm}', bm, mats['black'], parent)
        fl = bmesh.new()
        fv = [fl.verts.new(v) for v in bots]
        f = fl.faces.new(fv)
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
        bmesh.ops.triangulate(fl, faces=list(fl.faces))
        new_obj(f'HeadlampFloor_{nm}', fl, mats['lens'], parent)
        # lamp: a bright arrow along the floor and the lamp face on the back wall
        def floor_at(q):
            return top(q.x, q.y)
        lamp = bmesh.new()
        rows = []
        hb = (B1 - B2).length / 2
        for k in range(9):
            t = 0.04 + 0.92 * k / 8
            q = A + axis * (L * t)
            hw = 0.42 * hb * t
            perp = Vector((axis.y, -axis.x))
            row = []
            for sgn in (-1, 1):
                qq = q + perp * (sgn * hw)
                qm = Vector((side * qq.x, qq.y))
                depth = NOTCH_D0 + NOTCH_D1 * t
                row.append(lamp.verts.new((qm.x, qm.y, top(qm.x, qm.y) - depth + 0.004)))
            rows.append(row)
        for k in range(8):
            q4 = (rows[k][0], rows[k][1], rows[k + 1][1], rows[k + 1][0])
            lamp.faces.new(q4)
        for f in lamp.faces:
            f.normal_update()
            if f.normal.z < 0:
                f.normal_flip()
        new_obj(f'Headlight_{nm}', lamp, mats['headlamp'], parent)
        edge = bmesh.new()
        er = []
        for k in range(13):
            u = k / 12 * 0.8
            q = A.lerp(B1, u)
            qm = Vector((side * q.x, q.y))
            zt = top(qm.x, qm.y)
            er.append((edge.verts.new((qm.x, qm.y, zt - 0.003)), edge.verts.new((qm.x, qm.y, zt - 0.011))))
        for k in range(12):
            edge.faces.new((er[k][0], er[k + 1][0], er[k + 1][1], er[k][1]))
        for f in edge.faces:
            f.normal_update()
            if f.normal.x * side > 0:
                f.normal_flip()
        new_obj(f'HeadlightEdge_{nm}', edge, mats['drl'], parent)
        back = bmesh.new()
        p1 = B1 + (B2 - B1) * 0.1 - axis * 0.006
        p2 = B1 + (B2 - B1) * 0.9 - axis * 0.006
        zs = []
        vv = []
        for q in (p1, p2):
            qm = Vector((side * q.x, q.y))
            fz = top(qm.x, qm.y) - (NOTCH_D0 + NOTCH_D1)
            vv.append((qm, fz))
        quad = [back.verts.new((vv[0][0].x, vv[0][0].y, vv[0][1] + 0.006)), back.verts.new((vv[1][0].x, vv[1][0].y, vv[1][1] + 0.006)),
                back.verts.new((vv[1][0].x, vv[1][0].y, vv[1][1] + 0.032)), back.verts.new((vv[0][0].x, vv[0][0].y, vv[0][1] + 0.032))]
        f = back.faces.new(quad)
        f.normal_update()
        if f.normal.dot(Vector((-axis.x * side, -axis.y, 0))) < 0:
            f.normal_flip()
        new_obj(f'HeadlightLens_{nm}', back, mats['headlamp'], parent)


def _decal(bvh, outline, lift, material, name, parent):
    n = 10
    for s in (1, -1):
        bm = bmesh.new()
        grid = []
        for i in range(n + 1):
            u = i / n
            lo = Vector(outline[0]).lerp(Vector(outline[1]), u)
            hi = Vector(outline[3]).lerp(Vector(outline[2]), u)
            row = []
            for j in range(4):
                p = lo.lerp(hi, j / 3)
                loc, nrm, idx, dist = bvh.ray_cast(Vector((s * p.x, -3.5, p.y)), Vector((0, 1, 0)))
                if loc is None:
                    loc, nrm = Vector((s * p.x, -2.28, p.y)), Vector((0, -1, 0))
                row.append(bm.verts.new(loc + nrm.normalized() * lift))
            grid.append(row)
        for i in range(n):
            for j in range(3):
                q = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
                bm.faces.new(q if s > 0 else q[::-1])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if sum(f.normal.y for f in bm.faces) > 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        new_obj(f'{name}_{"L" if s > 0 else "R"}', bm, material, parent)


def side_intakes(skin, mats, parent):
    """Dark wedge vent at the top rear of the front arch, ending at the door shut line, with the amber
    marker in it (press side photos); projected onto the skin along -x/+x and lifted 2 mm."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(skin, bpy.context.evaluated_depsgraph_get())
    shapes = {'SideIntake': ([(-1.232, 0.660), (-1.085, 0.700), (-1.085, 0.742), (-1.250, 0.745)], 'black'),
              # side (yaw) thruster outlet on each front bumper corner, ahead of the arch (close replay 92.6-97.1 s)
              'SideThrusterRim': ([(-2.115, 0.362), (-2.005, 0.362), (-2.005, 0.438), (-2.115, 0.438)], 'brass'),
              'SideThrusterPort': ([(-2.100, 0.374), (-2.020, 0.374), (-2.020, 0.426), (-2.100, 0.426)], 'throat')}
    lift = {'SideIntake': 0.002, 'SideThrusterRim': 0.002, 'SideThrusterPort': 0.0035}
    for s in (1, -1):
        for name, (poly, m) in shapes.items():
            bm = bmesh.new()
            n = 8
            grid = []
            for i in range(n + 1):
                u = i / n
                lo = Vector(poly[0]).lerp(Vector(poly[1]), u)
                hi = Vector(poly[3]).lerp(Vector(poly[2]), u)
                row = []
                for j in range(n + 1):
                    p = lo.lerp(hi, j / n)
                    loc, nrm, idx, dist = bvh.ray_cast(Vector((s * 2.5, p.x, p.y)), Vector((-s, 0, 0)))
                    if loc is None:
                        loc, nrm = Vector((s * 1.1, p.x, p.y)), Vector((s, 0, 0))
                    row.append(bm.verts.new(loc + nrm.normalized() * lift[name]))
                grid.append(row)
            for i in range(n):
                for j in range(n):
                    q = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
                    bm.faces.new(q)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            if sum(f.normal.x for f in bm.faces) * s < 0:
                bmesh.ops.reverse_faces(bm, faces=bm.faces)
            new_obj(f'{name}_{"L" if s > 0 else "R"}', bm, mats[m], parent)


def front_fascia(outline, mats, parent):
    """Front face from the nose outline: a gloss black face stepped back under the light blade between
    white angled fangs, a dark lower lip and a thin splitter blade (press top and front views)."""
    y0 = outline[0].co.y
    pts = [(v.co.x, v.co.z) for v in outline]
    bm = bmesh.new()
    face = bm.faces.new([bm.verts.new((x, y0, z)) for x, z in pts][::-1])
    face.normal_update()
    if face.normal.y > 0:
        face.normal_flip()
    geom = lambda: list(bm.verts) + list(bm.edges) + list(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=geom(), plane_co=(0, y0, 0.50), plane_no=(0, 0, 1))
    for s in (1, -1):
        p0, p1 = Vector((s * 0.80, y0, 0.50)), Vector((s * 0.90, y0, 0.27))
        n = Vector((0, 1, 0)).cross(p1 - p0).normalized()
        bmesh.ops.bisect_plane(bm, geom=geom(), plane_co=p0, plane_no=n)
    mouth = [f for f in bm.faces if f.calc_center_median().z < 0.50 and abs(f.calc_center_median().x) < 0.80]
    ext = bmesh.ops.extrude_face_region(bm, geom=mouth)
    nv = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, 0.018, 0), verts=nv)
    bmesh.ops.delete(bm, geom=mouth, context='FACES')
    newf = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMFace)]
    for f in bm.faces:
        c = f.calc_center_median()
        f.material_index = 1 if (f in newf or c.z < 0.30) else 0
    ob = new_obj('FrontFascia', bm, None, parent, smooth_angle=20, mats=[mats['paint'], mats['black']])
    # DRL flush along the mouth's top edge, ending in the corner lamps
    new_obj('FrontLightBar', box(1.60, 0.02, 0.013, (0, y0 + 0.004, 0.503)), mats['drl'], parent)
    new_obj('FrontSplitter', prism([(-0.80, 0.17), (0.80, 0.17), (0.78, 0.182), (-0.78, 0.182)], y0 + 0.30, y0 + 0.03),
            mats['satin'], parent)
    return ob


def tail(outline, mats, parent):
    """Kamm tail from the rear outline (press rear views): the deck ends in a white lip carrying the
    full-width red bar on its trailing edge; everything under it is a recessed black face with a small
    RDSTR plate, then a deeper nozzle bay with four round nozzles low over the diffuser. Wing end
    plates stand just outboard of the rear corners (low-drag mode)."""
    y0 = outline[0].co.y
    pts = [(v.co.x, v.co.z) for v in outline]
    bm = bmesh.new()
    tf = bm.faces.new([bm.verts.new((x, y0, z)) for x, z in pts])
    tf.normal_update()
    if tf.normal.y < 0:
        tf.normal_flip()
    geom = lambda: list(bm.verts) + list(bm.edges) + list(bm.faces)
    for z in (0.915, 0.58):
        bmesh.ops.bisect_plane(bm, geom=geom(), plane_co=(0, y0, z), plane_no=(0, 0, 1))
    band = [f for f in bm.faces if 0.58 < f.calc_center_median().z < 0.915]
    ext = bmesh.ops.extrude_face_region(bm, geom=band)
    bandv = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, -0.03, 0), verts=bandv)
    bmesh.ops.delete(bm, geom=band, context='FACES')
    bandf = [g for g in ext['geom'] if isinstance(g, bmesh.types.BMFace)]
    bayf = [f for f in bm.faces if f.calc_center_median().z < 0.58 and f not in bandf]
    ext2 = bmesh.ops.extrude_face_region(bm, geom=bayf)
    bmesh.ops.translate(bm, vec=(0, -0.10, 0), verts=[g for g in ext2['geom'] if isinstance(g, bmesh.types.BMVert)])
    bmesh.ops.delete(bm, geom=bayf, context='FACES')
    for f in bm.faces:
        c = f.calc_center_median()
        # body colour: the deck lip and the recessed band under the red bar; black below it
        f.material_index = 0 if c.z > 0.585 else 1
    new_obj('TailPanel', bm, None, parent, smooth_angle=20, mats=[mats['paint'], mats['black']])
    # red bar on the lip's trailing edge, under the overhang
    new_obj('RearLightBar', box(2.0, 0.016, 0.016, (0, y0 - 0.010, 0.905)), mats['red'], parent)
    yf = y0 - 0.03
    new_obj('RearPlate', box(0.30, 0.008, 0.15, (0, yf + 0.004, 0.655)), mats['plate'], parent)
    txt = bpy.data.curves.new('PlateText', 'FONT')
    txt.body = 'RDSTR'
    txt.size = 0.075
    txt.extrude = 0.0008
    txt.align_x = 'CENTER'
    txt.align_y = 'CENTER'
    tob = bpy.data.objects.new('PlateText', txt)
    bpy.context.scene.collection.objects.link(tob)
    tob.rotation_euler = (math.radians(90), 0, math.radians(180))
    tob.location = (0, yf + 0.0095, 0.65)
    dg = bpy.context.evaluated_depsgraph_get()
    tme = bpy.data.meshes.new_from_object(tob.evaluated_get(dg))
    tbm = bmesh.new()
    tbm.from_mesh(tme)
    bmesh.ops.transform(tbm, matrix=tob.matrix_world, verts=tbm.verts)
    bpy.data.objects.remove(tob)
    bpy.data.curves.remove(txt)
    bpy.data.meshes.remove(tme)
    new_obj('RearPlateText', tbm, mats['black'], parent)
    # nozzle bay (press rear photos): a row of thin-walled brass tubes alternating with dark round ports,
    # over a diffuser of tall vertical fins
    yb = y0 - 0.10
    for k, x in enumerate((-0.52, -0.26, 0.0, 0.26, 0.52)):
        fin = prism([(x - 0.007, 0.05), (x + 0.007, 0.05), (x + 0.007, 0.40), (x - 0.007, 0.40)], y0 - 0.45, y0 - 0.11)
        new_obj(f'DiffuserStrake_{k + 1}', fin, mats['satin'], parent)
    new_obj('DiffuserCrossbar', prism([(-0.72, 0.124), (0.72, 0.124), (0.72, 0.140), (-0.72, 0.140)], y0 - 0.08, y0 - 0.03), mats['satin'], parent)
    new_obj('DiffuserLip', prism([(-0.90, 0.40), (0.90, 0.40), (0.90, 0.415), (-0.90, 0.415)], yb + 0.006, y0 - 0.01), mats['satin'], parent)
    zn = 0.48

    def along_y(bm, x, y):
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'Z'), verts=bm.verts)
        bmesh.ops.translate(bm, vec=(x, y, zn), verts=bm.verts)
        return bm
    for k, x in enumerate((-0.52, -0.26, 0.0, 0.26, 0.52)):
        port = along_y(lathe([(0.0, 0.036), (0.0, 0.044), (-0.08, 0.044), (-0.08, 0.036)], 40), x, y0 - 0.098)
        new_obj(f'Port_{k + 1}', port, mats['satin'], parent)
        back = along_y(lathe([(0.0, 0.0), (0.0, 0.037)], 32), x, y0 - 0.17)
        new_obj(f'Port_{k + 1}_Interior', back, mats['throat'], parent)
    for k, x in enumerate((-0.385, -0.13, 0.13, 0.385)):
        anchor = empty(f'NozzleAnchor_{k + 1}', parent, (x, y0 - 0.10, zn))
        anchor.rotation_euler = (0, 0, math.pi)
        tube = along_y(lathe([(0.0, 0.039), (0.0, 0.046), (-0.16, 0.046), (-0.16, 0.039)], 48), x, y0 - 0.092)
        new_obj(f'Nozzle_{k + 1}', tube, mats['brass'], parent)
        throat = along_y(lathe([(0.0, 0.0), (0.0, 0.040)], 32), x, y0 - 0.24)
        new_obj(f'Nozzle_{k + 1}_Interior', throat, mats['throat'], parent)
    # wing tips and end plates just outboard of the rear corners (low-drag mode)
    for side in (1, -1):
        nm = 'L' if side > 0 else 'R'
        x0, x1 = side * 0.99, side * 1.10
        tip = prism([(min(x0, x1), 0.931), (max(x0, x1), 0.931), (max(x0, x1), 0.942), (min(x0, x1), 0.942)], y0 - 0.28, y0 + 0.005)
        new_obj(f'WingTip_{nm}', tip, mats['black'], parent)
        ep = bmesh.new()
        xo = side * 1.10
        prof = [(y0 - 0.28, 0.942), (y0 + 0.005, 0.942), (y0 + 0.015, 0.83), (y0 - 0.12, 0.82)]
        vin = [ep.verts.new((xo - side * 0.004, y, z)) for y, z in prof]
        vout = [ep.verts.new((xo + side * 0.004 + side * (0.942 - z) * 0.25, y, z)) for y, z in prof]
        for v in vin:
            v.co.x += side * (0.942 - v.co.z) * 0.25
        ep.faces.new(vin[::-1])
        ep.faces.new(vout)
        for i in range(4):
            j = (i + 1) % 4
            ep.faces.new((vin[i], vin[j], vout[j], vout[i]))
        bmesh.ops.recalc_face_normals(ep, faces=ep.faces)
        new_obj(f'WingEndPlate_{nm}', ep, mats['black'], parent)


# ---------------------------------------------------------------- wheels
def tyre_profile(r, w, rim):
    h = w / 2
    pts = [(h - 0.004, rim)]
    for t in np.linspace(0.15, 1, 4):
        pts.append((h - 0.004 + 0.003 * math.sin(t * math.pi), rim + (r - 0.04 - rim) * t))
    for t in np.linspace(0, 1, 6)[1:]:
        a = t * math.pi / 2
        pts.append((h - 0.02 + 0.02 * math.cos(a), r - 0.04 + 0.04 * math.sin(a)))
    for x in np.linspace(h - 0.02, -h + 0.02, 6)[1:-1]:
        pts.append((x, r))
    for t in np.linspace(0, 1, 6)[:-1]:
        a = (1 - t) * math.pi / 2
        pts.append((-h + 0.02 - 0.02 * math.cos(a), r - 0.04 + 0.04 * math.sin(a)))
    for t in np.linspace(0, 1, 4)[1:]:
        pts.append((-h + 0.004, r - 0.04 - (r - 0.04 - rim) * t))
    return pts


def wheel(name, side, axle, mats, parent):
    """Tyre with a thin sidewall; a near-flush white aero disc; a star of six spokes, each two gloss
    black blades with a bronze insert between them, swept slightly; a dark centre cap (press photos)."""
    w = D.WHEELS[axle]
    x = side * w['x']
    piv = empty(name, parent, (x, w['y'], w['r']))
    rim = w['r'] - 0.06

    def place(bm):
        if side < 0:
            bmesh.ops.scale(bm, vec=(-1, 1, 1), verts=bm.verts)
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        return bm
    new_obj(name + '_Tire', place(lathe(tyre_profile(w['r'], w['w'], rim), 72, caps=False)), mats['tyre'], piv, smooth_angle=50)
    fx = w['w'] / 2 - 0.022                      # disc face plane
    lip = lathe([(fx - 0.004, rim + 0.004), (fx + 0.004, rim - 0.002), (fx + 0.002, rim - 0.014), (fx - 0.004, rim - 0.016)], 96, caps=False)
    new_obj(name + '_RimLip', place(lip), mats['satin'], piv, smooth_angle=40)
    disc = lathe([(fx - 0.004, rim - 0.014), (fx - 0.008, 0.20), (fx - 0.012, 0.075), (fx - 0.03, 0.06), (fx - 0.03, 0.0)], 96, caps=False)
    new_obj(name + '_AeroDisc', place(disc), mats['wheelface'], piv, smooth_angle=35)
    blades, inserts = bmesh.new(), bmesh.new()
    r0, r1 = 0.072, rim - 0.008

    def yz(r, a, t):
        # point at radius r, spoke angle a (with sweep), tangential offset t
        aa = a                       # straight radial spokes (press wheel photos)
        return (r * math.cos(aa) - t * math.sin(aa), r * math.sin(aa) + t * math.cos(aa))

    def slab(bm, quad, x0, x1):
        lo = [bm.verts.new((x0, y, z)) for y, z in quad]
        hi = [bm.verts.new((x1, y, z)) for y, z in quad]
        bm.faces.new(lo[::-1])
        bm.faces.new(hi)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    def strip(bm, inner, outer, x0, x1):
        """Closed blade from two edge polylines (inner/outer edge points in y, z), extruded x0..x1."""
        n = len(inner)
        L0 = [bm.verts.new((x0, *p)) for p in inner]
        O0 = [bm.verts.new((x0, *p)) for p in outer]
        L1 = [bm.verts.new((x1, *p)) for p in inner]
        O1 = [bm.verts.new((x1, *p)) for p in outer]
        for i in range(n - 1):
            bm.faces.new((L1[i], L1[i + 1], O1[i + 1], O1[i]))
            bm.faces.new((L0[i], O0[i], O0[i + 1], L0[i + 1]))
            bm.faces.new((L0[i], L0[i + 1], L1[i + 1], L1[i]))
            bm.faces.new((O0[i], O1[i], O1[i + 1], O0[i + 1]))
        bm.faces.new((L0[0], L1[0], O1[0], O0[0]))
        bm.faces.new((L0[-1], O0[-1], O1[-1], L1[-1]))
    n = 10
    for k in range(6):
        a = 2 * math.pi * k / 6
        # each spoke: two constant-width bars spreading into a V toward the rim, bronze fins between
        gap = lambda u: 0.006 + 0.03 * u             # half-gap: 0.012 m at the hub to 0.072 m at the rim
        for sgn in (-1, 1):
            inner, outer = [], []
            for i in range(n + 1):
                u = i / n
                r = r0 + (r1 - r0) * u
                inner.append(yz(r, a, sgn * gap(u)))
                outer.append(yz(r, a, sgn * (gap(u) + 0.036 + 0.008 * u)))
            strip(blades, inner, outer, fx - 0.02, fx + 0.007)
        inner = [yz(r0 + (r1 - r0) * i / n, a, -gap(i / n)) for i in range(n + 1)]
        outer = [yz(r0 + (r1 - r0) * i / n, a, gap(i / n)) for i in range(n + 1)]
        strip(inserts, inner, outer, fx - 0.03, fx - 0.013)
    bmesh.ops.recalc_face_normals(blades, faces=blades.faces)
    bmesh.ops.recalc_face_normals(inserts, faces=inserts.faces)
    new_obj(name + '_Spokes', place(blades), mats['spoke'], piv, smooth_angle=15)
    new_obj(name + '_SpokeInserts', place(inserts), mats['brass'], piv, smooth_angle=15)
    hub = lathe([(fx + 0.004, 0.0), (fx + 0.004, 0.050), (fx - 0.002, 0.066), (fx - 0.02, 0.07)], 48)
    new_obj(name + '_Hub', place(hub), mats['rotor'], piv)
    rotor = lathe([(-0.02, 0.07), (-0.02, rim - 0.04), (-0.05, rim - 0.04), (-0.05, 0.07)], 48)
    new_obj(name + '_Rotor', place(rotor), mats['rotor'], piv)
    return piv


# ---------------------------------------------------------------- lamps on the body sides
def skin_x(y, z):
    """Half-width of the body skin at side-view point (y, z) (outermost crossing of the section)."""
    d = np.load(HERE + 'shell.npz')
    co, M = d['co'], int(d['M'])
    ys = d['stations']
    i = int(np.clip(np.searchsorted(ys, y) - 1, 0, len(ys) - 2))
    best = 0.0
    for r in (i, i + 1):
        ring = co[r * M:(r + 1) * M]
        for j in range(M):
            p, q = ring[j], ring[(j + 1) % M]
            if p[0] < 0 or q[0] < 0 or (p[2] - z) * (q[2] - z) > 0 or p[2] == q[2]:
                continue
            t = (z - p[2]) / (q[2] - p[2])
            best = max(best, p[0] + t * (q[0] - p[0]))
    return best


def side_lamps(mats, parent):
    for s in (1, -1):
        sl = 'L' if s > 0 else 'R'
        # amber marker along the top of the arch vent, at its rear end (press side photos)
        x0, x1 = skin_x(-1.17, 0.73), skin_x(-1.095, 0.73)
        mk = bmesh.new()
        q = [(-1.17, 0.724, x0), (-1.095, 0.724, x1), (-1.095, 0.737, x1), (-1.17, 0.737, x0)]
        vs = [[mk.verts.new((s * (x + dx), y, z)) for y, z, x in q] for dx in (-0.01, 0.004)]
        mk.faces.new(vs[0]); mk.faces.new(vs[1][::-1])
        for k in range(4):
            mk.faces.new((vs[0][k], vs[0][(k + 1) % 4], vs[1][(k + 1) % 4], vs[1][k]))
        bmesh.ops.recalc_face_normals(mk, faces=mk.faces)
        new_obj(f'SideMarker_{sl}', mk, mats['amber'], parent)
        xr = skin_x(2.10, 0.60)
        rm = prism([(s * (xr - 0.01), 0.59), (s * (xr + 0.004), 0.59), (s * (xr + 0.004), 0.61), (s * (xr - 0.01), 0.61)], 2.03, 2.17)
        new_obj(f'RearMarker_{sl}', rm, mats['red'], parent)
        # vertical vent blade in the gap behind the front wheel (reference: white fin over a dark slot)




def buttress_vents(skin, mats, parent):
    """Dark slots on the flying buttresses either side of the rear glass (rear three-quarter photos):
    plan-view outlines projected down onto the skin."""
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromObject(skin, bpy.context.evaluated_depsgraph_get())
    for s in (1, -1):
        bm = bmesh.new()
        poly = [(0.66, 1.28), (0.74, 1.30), (0.72, 1.86), (0.63, 1.84)]
        n = 10
        grid = []
        for i in range(n + 1):
            lo = Vector(poly[0]).lerp(Vector(poly[1]), i / n)
            hi = Vector(poly[3]).lerp(Vector(poly[2]), i / n)
            row = []
            for j in range(n + 1):
                p = lo.lerp(hi, j / n)
                loc, nrm, idx, dist = bvh.ray_cast(Vector((s * p.x, p.y, 3.0)), Vector((0, 0, -1)))
                if loc is None:
                    loc, nrm = Vector((s * p.x, p.y, 1.0)), Vector((0, 0, 1))
                row.append(bm.verts.new(loc + nrm.normalized() * 0.003))
            grid.append(row)
        for i in range(n):
            for j in range(n):
                bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        if sum(f.normal.z for f in bm.faces) < 0:
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        new_obj(f'ButtressVent_{"L" if s > 0 else "R"}', bm, mats['black'], parent)


def underbody(mats, parent):
    """Visible during the flip: a battery tray with transverse ribs and side rails, a front
    subframe and rear diffuser ramp, and suspension arms at each wheel (overhead frames d011-d015)."""
    zb = 0.098
    new_obj('BatteryTray', box(1.50, 2.30, 0.03, (0, 0.0, zb)), mats['tray'], parent)
    for k, y in enumerate(np.linspace(-1.0, 1.0, 9)):
        new_obj(f'TrayRib_{k + 1}', box(1.40, 0.035, 0.02, (0, y, zb - 0.022)), mats['satin'], parent)
    for s in (1, -1):
        new_obj(f'TrayRail_{"L" if s > 0 else "R"}', box(0.06, 2.40, 0.04, (s * 0.72, 0.0, zb - 0.01)), mats['satin'], parent)
    # tubular space frame under the tray (overhead in-flight photo)
    zt = 0.068
    for s in (1, -1):
        new_obj(f'FrameTube_{"L" if s > 0 else "R"}', box(0.045, 3.1, 0.045, (s * 0.52, 0.0, zt)), mats['tray'], parent)
    for k, y in enumerate((-1.45, -0.75, 0.0, 0.75, 1.45)):
        new_obj(f'FrameCross_{k + 1}', box(1.08, 0.04, 0.04, (0, y, zt)), mats['tray'], parent)
    for k, (y0d, y1d) in enumerate(((-1.45, -0.75), (-0.75, 0.0), (0.0, 0.75), (0.75, 1.45))):
        d = prism([(-0.02, zt - 0.02), (0.02, zt - 0.02), (0.02, zt + 0.02), (-0.02, zt + 0.02)], y0d, y1d)
        bmesh.ops.shear = None
        for v in d.verts:
            t = (v.co.y - y0d) / (y1d - y0d)
            v.co.x += (-0.5 + t) * (1.0 if k % 2 else -1.0)
        new_obj(f'FrameDiag_{k + 1}', d, mats['tray'], parent)
    new_obj('FrontSubframe', box(1.20, 0.55, 0.05, (0, -1.47, 0.16)), mats['satin'], parent)
    new_obj('RearSubframe', box(1.20, 0.55, 0.05, (0, 1.43, 0.17)), mats['satin'], parent)
    for axle, w in D.WHEELS.items():
        for s in (1, -1):
            for dz, dy in ((-0.10, -0.12), (0.10, 0.12)):
                arm = prism([(s * 0.55, w['r'] + dz - 0.02), (s * (w['x'] - 0.12), w['r'] + dz - 0.015),
                             (s * (w['x'] - 0.12), w['r'] + dz + 0.015), (s * 0.55, w['r'] + dz + 0.02)],
                            w['y'] + dy - 0.03, w['y'] + dy + 0.03)
                new_obj(f'Arm_{axle}{"L" if s > 0 else "R"}{"U" if dz > 0 else "D"}', arm, mats['rotor'], parent)


# ---------------------------------------------------------------- build
def build():
    old = bpy.data.collections.get(COL)
    if old:
        for ob in list(old.all_objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(old)
    for me in list(bpy.data.meshes):
        if me.users == 0:
            bpy.data.meshes.remove(me)
    col = bpy.data.collections.new(COL)
    bpy.context.scene.collection.children.link(col)
    mats = materials()
    root = empty('Roadster', None)
    bm, reg, front, tail_ring, M, S = body_skin()
    # design cuts: canopy ends, daylight opening ends, door shut lines, bumper and deck splits
    cut(bm, (Vector((0, D.CANOPY[0], 0)), Vector((0, 1, 0))), region_faces(bm, reg, ['C', 'RM']))
    cut(bm, (Vector((0, D.CANOPY[0] - 0.07, 0)), Vector((0, 1, 0))), region_faces(bm, reg, ['C', 'RM']))
    cut(bm, (Vector((0, D.CANOPY[1], 0)), Vector((0, 1, 0))), region_faces(bm, reg, ['C']))
    cut(bm, side_plane(*D.DLO_FRONT), region_faces(bm, reg, ['RP']))
    cut(bm, side_plane(*D.DLO_REAR), region_faces(bm, reg, ['RP']))
    cut(bm, side_plane(*D.DOOR_FRONT), region_faces(bm, reg, ['B', 'S', 'W']))
    cut(bm, side_plane(*D.DOOR_REAR), region_faces(bm, reg, ['B', 'S', 'W']))
    for yy in (-1.95, 1.95):
        cut(bm, (Vector((0, yy, 0)), Vector((0, 1, 0))), region_faces(bm, reg, ['K']))
    hood = [f for f in region_faces(bm, reg, ['C', 'RM']) if f.calc_center_median().y < D.CANOPY[0] - 0.07]
    cut(bm, (Vector((0, HOOD_SEAM, 0)), Vector((0, 1, 0))), hood)
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()
    lab = classify(bm, reg)
    # arches are cut from the whole skin (and the inner body) before it is split into panels: exact
    # booleans are reliable on the continuous skin but not on panels whose edges were pulled back
    names = sorted(set(lab.values()))
    pid = bm.faces.layers.int.new('pid')
    for f in bm.faces:
        f[pid] = names.index(lab[f.index]) + 1
    core = bm.copy()
    bmesh.ops.recalc_face_normals(core, faces=core.faces)
    core.normal_update()
    for v in core.verts:
        v.co -= v.normal * 0.04
    skin_ob = new_obj('_Skin', bm, mats['paint'], root)
    core_ob = new_obj('BodyCore', core, mats['gap'], root)
    arch_cut([skin_ob, core_ob], mats)
    headlamps(skin_ob, core_ob, mats, root)
    buttress_vents(skin_ob, mats, root)
    side_intakes(skin_ob, mats, root)
    bm = bmesh.new()
    bm.from_mesh(skin_ob.data)
    bpy.data.objects.remove(skin_ob)
    pid = bm.faces.layers.int.get('pid')
    drop = [f for f in bm.faces if f[pid] == 0]
    bmesh.ops.delete(bm, geom=drop, context='FACES')
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()
    lab = {f.index: names[f[pid] - 1] for f in bm.faces}
    parts = split_parts(bm, lab, mats, root)
    bm.free()
    wheel_wells(mats, root)
    d = np.load(HERE + 'shell.npz')
    co, Mn = d['co'], int(d['M'])
    class P:  # outline points as simple objects with .co
        def __init__(self, c): self.co = Vector(c)
    front_fascia([P(c) for c in co[:Mn]][::-1], mats, root)
    tail([P(c) for c in co[-Mn:]], mats, root)
    side_lamps(mats, root)
    underbody(mats, root)
    for name, side, axle in (('Wheel_FL', 1, 'F'), ('Wheel_FR', -1, 'F'), ('Wheel_RL', 1, 'R'), ('Wheel_RR', -1, 'R')):
        wheel(name, side, axle, mats, root)
    return root


def merge_for_export():
    """Fewer draw calls at runtime: join the meshes that share a parent (the root or a wheel pivot)
    and a single material. Runs after the .blend is saved, so the source file keeps its named parts;
    the runtime only relies on the Roadster root and the Wheel_* pivots."""
    groups = {}
    for ob in bpy.data.collections[COL].all_objects:
        if ob.type != 'MESH' or len(ob.data.materials) != 1 or ob.data.materials[0] is None:
            continue
        key = (ob.parent.name if ob.parent else '', ob.data.materials[0].name)
        groups.setdefault(key, []).append(ob)
    for (parent, material), obs in sorted(groups.items()):
        if len(obs) < 2:
            continue
        bpy.ops.object.select_all(action='DESELECT')
        for o in obs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = obs[0]
        bpy.ops.object.join()
        obs[0].name = f'{parent}_{material}'
    meshes = [o for o in bpy.data.collections[COL].all_objects if o.type == 'MESH']
    print('MERGED', len(meshes), 'meshes for export')


def export():
    root = bpy.data.objects['Roadster']
    keep = root.matrix_world.copy()
    cy = 0.5 * (D.WHEELS['F']['y'] + D.WHEELS['R']['y'])
    root.matrix_world = Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Translation((0, -cy, 0))
    for c in bpy.data.collections:
        lc = bpy.context.view_layer.layer_collection.children.get(c.name)
        if lc:
            lc.exclude = c.name != COL
    merge_for_export()
    bpy.ops.object.select_all(action='DESELECT')
    for ob in bpy.data.collections[COL].all_objects:
        ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(REPO, 'public', 'models', 'roadster.glb'), export_format='GLB',
                              use_selection=True, export_yup=True, export_apply=True)
    root.matrix_world = keep
    for c in bpy.data.collections:
        lc = bpy.context.view_layer.layer_collection.children.get(c.name)
        if lc:
            lc.exclude = False


if __name__ == '__main__':
    build()
    bpy.ops.wm.save_mainfile()
    if '--export' in ARGS:
        export()
    tris = 0
    for o in bpy.data.collections[COL].all_objects:
        if o.type == 'MESH':
            o.data.calc_loop_triangles()
            tris += len(o.data.loop_triangles)
    print('BUILD OK objects', len(bpy.data.collections[COL].all_objects), 'triangles', tris)
