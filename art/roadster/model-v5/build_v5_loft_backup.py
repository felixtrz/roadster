"""Roadster v5: one idempotent build from the measured fits.

    Blender -b roadster_v5.blend -P build_v5.py -- [--export] [--bake]

Conventions (Blender): metres, Z up, the car faces -Y, its left is +X, floor z = 0.
Inputs: fit/loft.npz (measured body loft), fit/wheels.json, reference/faces.npz (texture colour per
reference face, used to bake the paint/glass/trim map). Output collection RoadsterV5; with --export,
public/models/roadster.glb (glTF +Y up; root turned +90 deg about up so the car faces +X).
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '')
REPO = os.path.abspath(os.path.join(ROOT, '..', '..', '..'))
S = os.environ.get('MESH_REBUILD_SKILL', '')
if not os.path.isdir(S):
    raise SystemExit('Set MESH_REBUILD_SKILL to the rebuild-generated-mesh skill scripts directory '
                     '(the one containing blender_lib.py, facets.py and extract_reference.py).')
S = os.path.join(S, '')
L = {}
exec(open(S + 'blender_lib.py').read(), L)
L['guard']('/art/roadster/model-v5/roadster_v5.blend')
ARGS = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
COL = 'RoadsterV5'
WHEEL = {'F': dict(y=-1.414, r=0.362, w=0.300, x=1.000), 'R': dict(y=1.437, r=0.385, w=0.330, x=1.000)}
ARCH_PAD = 0.075


# ---------------------------------------------------------------- materials
def principled(name, base=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, coat=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs[0], out.inputs[0])
    b.inputs['Base Color'].default_value = (*base, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Coat Weight'].default_value = coat
    b.inputs['Coat Roughness'].default_value = 0.04
    if emit:
        b.inputs['Emission Color'].default_value = (*emit, 1)
        b.inputs['Emission Strength'].default_value = strength
    return m, b


def body_material(base_img, orm_img):
    m, b = principled('M_Body', coat=1.0)
    nt = m.node_tree
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = base_img
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    o = nt.nodes.new('ShaderNodeTexImage')
    o.image = orm_img
    o.image.colorspace_settings.name = 'Non-Color'
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(o.outputs['Color'], sep.inputs[0])
    nt.links.new(sep.outputs[1], b.inputs['Roughness'])
    nt.links.new(sep.outputs[2], b.inputs['Metallic'])
    return m


# ---------------------------------------------------------------- body loft
def body_mesh():
    d = np.load(ROOT + 'fit/loft.npz')
    co, quads, M = d['co'], d['quads'], int(d['M'])
    Sn = len(co) // M
    me = bpy.data.meshes.new('BodyShell')
    faces = [tuple(q) for q in quads] + [tuple(d['cap0']), tuple(d['cap1'])]
    me.from_pydata(co.tolist(), [], faces)
    uv = me.uv_layers.new(name='UVMap')
    nq = len(quads)
    for f in me.polygons:
        f.material_index = 0 if f.index < nq else 1
        for li in f.loop_indices:
            vi = me.loops[li].vertex_index
            i, j = divmod(vi, M)
            if f.index < nq:
                # faces that wrap the ring seam take u = 1 on their wrapped side
                js = [me.loops[k].vertex_index % M for k in f.loop_indices]
                if j == 0 and max(js) == M - 1:
                    j = M
                uv.data[li].uv = (j / M, i / (Sn - 1))
            else:
                uv.data[li].uv = (0.0, 0.0)
    me.validate()
    return me, M, Sn, co.reshape(Sn, M, 3)


def bake_paint(grid, M, Sn, ref):
    """Base colour + ORM maps from the reference texture colour nearest each texel's surface point."""
    W, H = 2048, 1024
    bvh = BVHTree.FromObject(ref, bpy.context.evaluated_depsgraph_get())
    F = np.load(ROOT + 'reference/faces.npz')
    col = F['col']
    lum = col.mean(1)
    # map the reference polygons (as evaluated) to face-table rows: same triangulation order
    ws, hs = 1024, 512
    u = (np.arange(ws) + 0.5) / ws * M
    v = (np.arange(hs) + 0.5) / hs * (Sn - 1)
    j0 = np.floor(u).astype(int) % M
    j1 = (j0 + 1) % M
    fu = (u - np.floor(u))[None, :, None]
    i0 = np.clip(np.floor(v).astype(int), 0, Sn - 2)
    fv = (v - i0)[:, None, None]
    g = grid
    P = ((1 - fv) * ((1 - fu) * g[i0][:, j0] + fu * g[i0][:, j1])
         + fv * ((1 - fu) * g[i0 + 1][:, j0] + fu * g[i0 + 1][:, j1]))        # (hs, ws, 3)
    white = np.zeros((hs, ws), np.float32)
    assert len(ref.data.polygons) == len(lum), (len(ref.data.polygons), len(lum))
    Mi = ref.matrix_world.inverted()
    for b in range(hs):
        row = P[b]
        for a in range(ws):
            loc, nrm, idx, dist = bvh.find_nearest(Mi @ Vector(row[a]))
            white[b, a] = lum[idx] if idx is not None else 0.5
    np.save(ROOT + 'fit/paint_lum.npy', white)
    return P, white


def blur(a, sigma, wrap_u=True):
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.concatenate([a[:, -r:], a, a[:, :r]], 1) if wrap_u else np.pad(a, ((0, 0), (r, r)), mode='edge')
    a = np.apply_along_axis(lambda x: np.convolve(x, k, 'valid'), 1, pad)
    pad = np.pad(a, ((r, r), (0, 0)), mode='edge')
    return np.apply_along_axis(lambda x: np.convolve(x, k, 'valid'), 0, pad)


def paint_images(P, lum):
    """Classify (white paint / gloss-black trim / smoked glass), smooth the class fields so the
    boundaries are clean curves, upsample x2 and threshold with a narrow ramp (antialiased edges)."""
    w = np.clip((lum - 0.40) / 0.35, 0, 1)
    from numpy.lib.stride_tricks import sliding_window_view as sw
    for k in (9, 7):
        pad = np.pad(w, k // 2, mode='wrap')
        w = np.median(sw(pad, (k, k)), axis=(2, 3))
    w = blur(w, 2.6)
    z = P[..., 2]
    x = np.abs(P[..., 0])
    y = P[..., 1]
    # glass: the measured dark canopy above the belt, faired hard so the DLO reads as one clean shape
    g = (1 - w) * (z > 0.86)
    g = blur(g, 7.0)
    # paint below the belt is drawn from lines measured on the reference (fit/paint.json), not
    # sampled per texel: the generated texture is too noisy around the intakes and lamps
    ky = [-2.4, -1.9, -1.05, 0.0, 0.5, 1.05, 1.6, 2.4]
    kz = [0.30, 0.30, 0.275, 0.31, 0.37, 0.47, 0.62, 0.64]
    sill = np.interp(y, ky, kz)
    soft = lambda d, s=0.006: np.clip(0.5 + d / s, 0, 1)
    white = soft(z - sill)
    front = (y < -2.0) & (x < 0.80)
    white = np.where(front, white * soft(z - 0.49), white)
    rear = y > 2.02
    white = np.where(rear, white * soft(z - 0.50) * (1 - soft(0.045 - np.abs(z - 0.905))), white)
    belt = soft(z - 0.86, 0.03)
    w = white * (1 - (g > 0.5) * belt)
    glass = (g > 0.5) * belt
    # door shut lines (reference side view): front cut behind the front arch, rear cut slanting back
    def seg_dist(p0, p1):
        a, bb = np.array(p0), np.array(p1)
        q = np.dstack([y, z]) - a
        d = bb - a
        t = np.clip((q @ d) / (d @ d), 0, 1)
        return np.linalg.norm(q - t[..., None] * d, axis=-1)
    side = x > 0.88
    seam = np.zeros_like(z)
    for p0, p1 in (((-0.985, 0.30), (-0.94, 0.86)), ((0.42, 0.38), (0.66, 0.87))):
        seam = np.maximum(seam, side * np.clip(1 - seg_dist(p0, p1) / 0.007, 0, 1))
    up = lambda a: np.kron(a, np.ones((2, 2)))
    w, glass = blur(up(w), 1.0), blur(up(glass.astype(np.float32)), 1.0)
    seam = blur(up(seam), 0.8)
    ramp = lambda a: np.clip((a - 0.5) / 0.08 + 0.5, 0, 1)
    wt = ramp(w)
    H, W = wt.shape
    pearl = np.array([0.86, 0.865, 0.87])
    trim = np.array([0.012, 0.012, 0.013])
    smoke = np.array([0.006, 0.007, 0.009])
    dark = trim[None, None] * (1 - glass[..., None]) + smoke[None, None] * glass[..., None]
    base = wt[..., None] * pearl + (1 - wt[..., None]) * dark
    base = base * (1 - 0.85 * np.clip(seam, 0, 1)[..., None])
    rough = wt * 0.32 + (1 - wt) * (glass * 0.04 + (1 - glass) * 0.42)
    orm = np.dstack([np.ones_like(rough), rough, np.zeros_like(rough)])
    def img(name, arr, alpha=True):
        im = bpy.data.images.get(name)
        if im:
            bpy.data.images.remove(im)
        im = bpy.data.images.new(name, W, H, alpha=False, float_buffer=False)
        px = np.dstack([arr, np.ones((H, W))]).astype(np.float32)
        im.pixels.foreach_set(px.ravel())
        return im
    # base colour pixels are linear in Blender's buffer: convert to sRGB-encoded values for the byte image
    srgb = np.where(base <= 0.0031308, base * 12.92, 1.055 * np.power(base, 1 / 2.4) - 0.055)
    bi = img('roadster_body_base', srgb)
    bi.file_format = 'JPEG'
    bi.filepath_raw = ROOT + 'renders/roadster_body_base.jpg'
    bi.save()
    oi = img('roadster_body_orm', orm)
    oi.file_format = 'PNG'
    oi.filepath_raw = ROOT + 'renders/roadster_body_orm.png'
    oi.save()
    bi.colorspace_settings.name = 'sRGB'
    return bi, oi


# ---------------------------------------------------------------- wheels
def lathe(profile, sides, axis_x_sign=1, caps=True):
    """Surface of revolution about the X axis. profile: [(x, r)] open polyline (outer face first)."""
    bm = bmesh.new()
    rings = []
    for x, r in profile:
        rings.append([bm.verts.new((x * axis_x_sign, r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides)))
                      for k in range(sides)])
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    if caps and profile[0][1] > 1e-4:
        bm.faces.new(list(reversed(rings[0])))
    if caps and profile[-1][1] > 1e-4:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def tyre_profile(r, w):
    h = w / 2
    pts = []
    # outer sidewall (x = +h) from rim seat up, round shoulder, tread, inner sidewall
    rim = r - 0.105
    for t in np.linspace(0, 1, 5):
        pts.append((h - 0.012 * t * t, rim + (r - 0.045 - rim) * t))
    for t in np.linspace(0, 1, 7)[1:]:
        a = t * math.pi / 2
        pts.append((h - 0.03 + 0.03 * math.cos(a) - 0.012 * (1 - math.cos(a)) * 0, r - 0.045 + 0.045 * math.sin(a)))
    for xx in np.linspace(h - 0.03, -h + 0.03, 6)[1:-1]:
        pts.append((xx, r))
    for t in np.linspace(0, 1, 7)[:-1]:
        a = (1 - t) * math.pi / 2
        pts.append((-h + 0.03 - 0.03 * math.cos(a), r - 0.045 + 0.045 * math.sin(a)))
    for t in np.linspace(0, 1, 5):
        pts.append((-h + 0.012 * (1 - t) * (1 - t), r - 0.045 - (r - 0.045 - rim) * t))
    return pts


def aero_disc(r, sides=96, slots=10):
    """Aero wheel cover: shallow cone with a raised outer lip, turbine slots and a centre cap."""
    bm = lathe([(0.0, 0.0), (0.004, 0.055), (0.0, 0.07), (-0.012, 0.12), (-0.022, r * 0.82), (-0.012, r * 0.93),
                (-0.004, r), (-0.03, r), (-0.03, 0.0)], sides)
    return bm


def turbine_vanes(r, n=10):
    bm = bmesh.new()
    for k in range(n):
        a0 = 2 * math.pi * k / n
        pts = []
        for t in np.linspace(0, 1, 6):
            rr = 0.13 + (r * 0.80 - 0.13) * t
            a = a0 + 0.55 * t
            pts.append((rr * math.cos(a), rr * math.sin(a)))
        verts = []
        for (py, pz), wdt in zip(pts, np.linspace(0.010, 0.022, 6)):
            nrm = Vector((0, -pz, py)).normalized() if (py or pz) else Vector((0, 1, 0))
            verts.append([bm.verts.new((dx, py + nrm.y * s * wdt, pz + nrm.z * s * wdt))
                          for dx, s in ((0.004, 1), (0.004, -1), (-0.012, -1), (-0.012, 1))])
        for a, b in zip(verts, verts[1:]):
            for q in range(4):
                bm.faces.new((a[q], a[(q + 1) % 4], b[(q + 1) % 4], b[q]))
        bm.faces.new(list(reversed(verts[0])))
        bm.faces.new(verts[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def add_wheel(rig, root, name, side, axle, mats):
    c = WHEEL[axle]
    x = side * (c['x'] + 0.012)
    piv = rig.pivot(name, root, (x, c['y'], c['r']))
    out = side
    def place(bm, flip):
        if flip < 0:
            bmesh.ops.scale(bm, vec=(-1, 1, 1), verts=bm.verts)
            bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bmesh.ops.translate(bm, vec=(x, c['y'], c['r']), verts=bm.verts)
        return bm
    tyre = place(lathe(tyre_profile(c['r'], c['w']), 64, caps=False), out)
    ob = rig.part(name + '_Tire', tyre, mats['tyre'], piv)
    disc_bm = aero_disc(c['r'] - 0.11)
    bmesh.ops.translate(disc_bm, vec=(c['w'] / 2 - 0.035, 0, 0), verts=disc_bm.verts)
    rig.part(name + '_AeroDisc', place(disc_bm, out), mats['disc'], piv)
    vanes = turbine_vanes(c['r'] - 0.11)
    bmesh.ops.translate(vanes, vec=(c['w'] / 2 - 0.05, 0, 0), verts=vanes.verts)
    rig.part(name + '_Vanes', place(vanes, out), mats['vane'], piv)
    cap = lathe([(0.0, 0.0), (0.0, 0.045), (-0.02, 0.05), (-0.02, 0.0)], 32)
    bmesh.ops.translate(cap, vec=(c['w'] / 2 - 0.022, 0, 0), verts=cap.verts)
    rig.part(name + '_Hub', place(cap, out), mats['brass'], piv)
    rotor = L['bm_cyl'](c['r'] - 0.14, 0.03, 48, (1, 0, 0), (0, 0, 0))
    bmesh.ops.translate(rotor, vec=(-0.02, 0, 0), verts=rotor.verts)
    rig.part(name + '_Rotor', place(rotor, out), mats['rotor'], piv)
    for o in piv.children:
        smooth(o, 40)
    return piv


# ---------------------------------------------------------------- helpers
def smooth(ob, angle=38):
    for p in ob.data.polygons:
        p.use_smooth = True
    me = ob.data
    if hasattr(me, 'set_sharp_from_angle'):
        me.set_sharp_from_angle(angle=math.radians(angle))


def boolean(target, cutter, op='DIFFERENCE'):
    m = target.modifiers.new('bool', 'BOOLEAN')
    m.operation = op
    m.object = cutter
    m.solver = 'EXACT'
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)


def temp_object(name, bm, mat=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if mat:
        me.materials.append(mat)
    return ob


def surface_point(bvh, origin, direction):
    loc, nrm, idx, dist = bvh.ray_cast(Vector(origin), Vector(direction).normalized())
    return loc, nrm


def strip_on_surface(bvh, name, xs, z, y_from, depth=0.012, height=0.018, inset=0.0):
    """A thin lamp strip that follows the body surface: rays from the front/back along y."""
    bm = bmesh.new()
    rows = []
    dirn = 1 if y_from < 0 else -1
    for x in xs:
        col = []
        for dz in (-height / 2, height / 2):
            loc, nrm = surface_point(bvh, (x, y_from, z + dz), (0, dirn, 0))
            if loc is None:
                loc, nrm = Vector((x, -y_from, z + dz)), Vector((0, -dirn, 0))
            col.append((loc - nrm * inset, nrm))
        rows.append(col)
    vs = []
    for col in rows:
        ring = []
        for (p, n) in col:
            ring.append(bm.verts.new(p + n * depth))
            ring.append(bm.verts.new(p - n * 0.01))
        vs.append(ring)
    for a, b in zip(vs, vs[1:]):
        # ring order: lo_out, lo_in, hi_out, hi_in
        bm.faces.new((a[0], b[0], b[2], a[2]))   # face
        bm.faces.new((a[2], b[2], b[3], a[3]))
        bm.faces.new((a[1], b[1], b[0], a[0]))
        bm.faces.new((a[3], b[3], b[1], a[1]))
    bm.faces.new((vs[0][0], vs[0][2], vs[0][3], vs[0][1]))
    bm.faces.new((vs[-1][1], vs[-1][3], vs[-1][2], vs[-1][0]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


# ---------------------------------------------------------------- build
def build(bake=True):
    for c in bpy.data.collections:
        lc = bpy.context.view_layer.layer_collection.children.get(c.name)
        if lc:
            lc.exclude = False
    rig = L['Rig'](COL)
    root = rig.pivot('Roadster', None, (0, 0, 0))
    ref = bpy.data.objects['RefMesh']

    me, M, Sn, grid = body_mesh()
    if bake or not os.path.exists(ROOT + 'fit/paint_lum.npy'):
        P, lum = bake_paint(grid, M, Sn, ref)
    else:
        lum = np.load(ROOT + 'fit/paint_lum.npy')
        ws, hs = lum.shape[1], lum.shape[0]
        u = (np.arange(ws) + 0.5) / ws * M
        v = (np.arange(hs) + 0.5) / hs * (Sn - 1)
        j0 = np.floor(u).astype(int) % M; j1 = (j0 + 1) % M
        fu = (u - np.floor(u))[None, :, None]
        i0 = np.clip(np.floor(v).astype(int), 0, Sn - 2); fv = (v - i0)[:, None, None]
        g = grid
        P = ((1 - fv) * ((1 - fu) * g[i0][:, j0] + fu * g[i0][:, j1]) + fv * ((1 - fu) * g[i0 + 1][:, j0] + fu * g[i0 + 1][:, j1]))
    base_img, orm_img = paint_images(P, lum)

    mats = {
        'body': body_material(base_img, orm_img),
        'trim': principled('M_Trim', (0.012, 0.012, 0.013), 0.55)[0],
        'paint': principled('M_Paint', (0.86, 0.865, 0.87), 0.32, coat=1.0)[0],
        'well': principled('M_WheelWell', (0.006, 0.006, 0.007), 0.85)[0],
        'tyre': principled('M_Tyre', (0.018, 0.018, 0.019), 0.82)[0],
        'disc': principled('M_AeroDisc', (0.20, 0.205, 0.21), 0.30, 0.7, coat=0.6)[0],
        'vane': principled('M_AeroVane', (0.05, 0.052, 0.055), 0.35, 0.6)[0],
        'rotor': principled('M_Rotor', (0.25, 0.25, 0.26), 0.45, 1.0)[0],
        'brass': principled('M_Brass', (0.80, 0.56, 0.28), 0.28, 1.0)[0],
        'nozzle_in': principled('M_NozzleThroat', (0.05, 0.03, 0.015), 0.6, 1.0)[0],
        'lamp_w': principled('M_LampWhite', (1, 1, 1), 0.2, emit=(0.85, 0.93, 1.0), strength=6.0)[0],
        'lamp_r': principled('M_LampRed', (0.5, 0.0, 0.01), 0.25, emit=(1.0, 0.02, 0.04), strength=6.0)[0],
        'lamp_a': principled('M_LampAmber', (0.6, 0.3, 0.0), 0.25, emit=(1.0, 0.45, 0.05), strength=4.0)[0],
        'lens': principled('M_LampLens', (0.01, 0.01, 0.012), 0.05, coat=1.0)[0],
        'plate': principled('M_Plate', (0.7, 0.71, 0.72), 0.4, 0.2)[0],
    }
    body = bpy.data.objects.new('BodyShell', me)
    bpy.context.scene.collection.objects.link(body)
    me.materials.append(mats['body'])
    me.materials.append(mats['trim'])
    me.materials.append(mats['paint'])
    me.polygons[-1].material_index = 2

    # wheel arches: two cutters per axle so the floor between the wheels stays closed
    for axle, c in WHEEL.items():
        for side in (1, -1):
            cut = L['bm_cyl'](c['r'] + ARCH_PAD, 0.9, 72, (1, 0, 0), (side * (0.58 + 0.45), c['y'], c['r']))
            cob = temp_object(f'cut_{axle}{side}', cut, mats['well'])
            boolean(body, cob)
            bpy.data.objects.remove(cob)
    smooth(body, 34)
    for c in list(body.users_collection):
        c.objects.unlink(body)
    rig.col.objects.link(body)
    body.parent = root

    bvh = BVHTree.FromObject(body, bpy.context.evaluated_depsgraph_get())

    # ---- lamps (positions from the approved reference turnaround, seated on the measured shell)
    # front face (planar cap at y = -2.285): light bar along its top edge, lamp eyes at the corners,
    # grille slats and a splitter blade below (reference front view proportions)
    yF = -2.285
    rig.part('FrontLightBar', L['bm_box'](1.52, 0.016, 0.026, (0, yF - 0.014, 0.505)), mats['lamp_w'], root)
    rig.part('FrontLightBarHousing', L['bm_box'](1.56, 0.010, 0.045, (0, yF - 0.001, 0.505)), mats['lens'], root)
    for s in (1, -1):
        loc, nrm = surface_point(bvh, (s * 0.86, -3.0, 0.585), (0, 1, 0))
        if loc is not None:
            eye = L['bm_box'](0.15, 0.03, 0.034, (s * 0.86, loc.y - 0.004, 0.585))
            bmesh.ops.rotate(eye, cent=(s * 0.86, loc.y, 0.585), matrix=Matrix.Rotation(math.radians(-s * 28), 3, 'Z'), verts=eye.verts)
            rig.part(f'Headlight_{"L" if s > 0 else "R"}', eye, mats['lamp_w'], root)
    for k, z in enumerate(np.linspace(0.26, 0.44, 5)):
        rig.part(f'GrilleSlat_{k + 1}', L['bm_box'](1.40, 0.03, 0.012, (0, yF - 0.004, z)), mats['vane'], root)
    rig.part('FrontSplitter', L['bm_box'](1.66, 0.12, 0.022, (0, yF + 0.02, 0.165)), mats['vane'], root)
    rx = list(np.linspace(-0.93, 0.93, 45))
    rig.part('RearLightBar', L['bm_box'](1.86, 0.016, 0.026, (0, 2.262, 0.905)), mats['lamp_r'], root)
    rig.part('RearLampHousing', L['bm_box'](1.98, 0.012, 0.085, (0, 2.257, 0.900)), mats['lens'], root)
    plate = L['bm_box'](0.52, 0.02, 0.12, (0, 2.248, 0.70))
    rig.part('RearPlate', plate, mats['plate'], root)
    for s in (1, -1):
        loc, nrm = surface_point(bvh, (s * 2.0, -0.98, 0.80), (-s, 0, 0))
        if loc is not None:
            mk = L['bm_box'](0.012, 0.07, 0.022, tuple(loc))
            rig.part(f'SideMarker_{"L" if s > 0 else "R"}', mk, mats['lamp_a'], root)
        loc, nrm = surface_point(bvh, (s * 2.0, 2.18, 0.62), (-s, 0, 0))
        if loc is not None:
            mk = L['bm_box'](0.012, 0.06, 0.02, tuple(loc))
            rig.part(f'RearMarker_{"L" if s > 0 else "R"}', mk, mats['lamp_r'], root)

    # ---- rear diffuser, strakes and the four brass thrust nozzles (reference back view)
    for k, x in enumerate(np.linspace(-0.75, 0.75, 6)):
        fin = bmesh.new()
        prof = [(1.45, 0.10), (2.24, 0.24), (2.24, 0.43), (1.45, 0.13)]
        vs = [[fin.verts.new((x + dx, py, pz)) for py, pz in prof] for dx in (-0.011, 0.011)]
        fin.faces.new(vs[0][::-1]); fin.faces.new(vs[1])
        for q in range(4):
            fin.faces.new((vs[0][q], vs[0][(q + 1) % 4], vs[1][(q + 1) % 4], vs[1][q]))
        bmesh.ops.recalc_face_normals(fin, faces=fin.faces)
        rig.part(f'DiffuserStrake_{k + 1}', fin, mats['trim'], root)
    for k, x in enumerate((-0.456, -0.152, 0.152, 0.456)):
        anchor = rig.pivot(f'NozzleAnchor_{k + 1}', root, (x, 2.215, 0.367))
        bell = lathe([(0.0, 0.050), (0.0, 0.062), (-0.05, 0.058), (-0.16, 0.042), (-0.16, 0.034), (-0.05, 0.046), (-0.004, 0.050)], 40)
        bmesh.ops.rotate(bell, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'Z'), verts=bell.verts)
        bmesh.ops.translate(bell, vec=(x, 2.215, 0.367), verts=bell.verts)
        rig.part(f'Nozzle_{k + 1}', bell, mats['brass'], anchor)
        throat = L['bm_cyl'](0.044, 0.01, 32, (0, 1, 0), (x, 2.18, 0.367))
        rig.part(f'Nozzle_{k + 1}_Interior', throat, mats['nozzle_in'], anchor)
    rig.part('Undercarriage', L['bm_box'](1.70, 3.9, 0.03, (0, 0.05, 0.105)), mats['trim'], root)

    # ---- wheels on their own pivots (spin about local X)
    for name, side, axle in (('Wheel_FL', 1, 'F'), ('Wheel_FR', -1, 'F'), ('Wheel_RL', 1, 'R'), ('Wheel_RR', -1, 'R')):
        add_wheel(rig, root, name, side, axle, mats)

    for ob in bpy.data.collections[COL].all_objects:
        if ob.type == 'MESH' and ob.name != 'BodyShell' and not ob.name.startswith('Wheel_'):
            smooth(ob, 30)
    return rig


def export():
    root = bpy.data.objects['Roadster']
    keep = root.matrix_world.copy()
    root.matrix_world = Matrix.Rotation(math.radians(90), 4, 'Z') @ Matrix.Translation((0, -0.0115, 0))
    for c in bpy.data.collections:
        lc = bpy.context.view_layer.layer_collection.children.get(c.name)
        if lc:
            lc.exclude = c.name != COL
    bpy.ops.object.select_all(action='DESELECT')
    for ob in bpy.data.collections[COL].all_objects:
        ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(REPO, 'public', 'models', 'roadster.glb'), export_format='GLB',
                              use_selection=True, export_yup=True, export_apply=True, export_image_format='AUTO')
    root.matrix_world = keep
    for c in bpy.data.collections:
        lc = bpy.context.view_layer.layer_collection.children.get(c.name)
        if lc:
            lc.exclude = False


if __name__ == '__main__':
    build(bake='--bake' in ARGS)
    bpy.ops.wm.save_mainfile()
    if '--export' in ARGS:
        export()
    tris = 0
    for o in bpy.data.collections[COL].all_objects:
        if o.type == 'MESH':
            o.data.calc_loop_triangles(); tris += len(o.data.loop_triangles)
    print('BUILD OK triangles', tris)
