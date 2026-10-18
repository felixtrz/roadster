"""Idempotently author the clean Roadster, measured against a preserved RefMesh."""
from pathlib import Path
import json
import math
import sys
import bpy
import bmesh
import numpy as np
from mathutils import Matrix

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import *

FIT=json.loads((ROOT/'fit/roadster.json').read_text())
PRIMARY='--primary' in sys.argv
QUICK='--quick' in sys.argv
PATCH=json.loads((ROOT/'fit/surface-patches.json').read_text())
old_stations=FIT['stations']
STATIONS=[{'y':s['y'],'half_width':s['half_width'],'top':s['top_z'],
 'lower':float(np.interp(s['y'],[r['y'] for r in old_stations],[r['lower'] for r in old_stations]))}
 for s in PATCH['stations']]
YS=np.array([s['y'] for s in STATIONS])
FRACTIONS=PATCH['fractions']
FRONT=float(YS[0])-.025
BACK=float(YS[-1])+.025
NOSE_SWEEP=0.0
# XZ outlines on the existing forward cap, not XY patches on the hood.
LAMP_POCKET=[(.835,.542),(1.045,.553),(1.045,.653)]
LAMP_LENS=[(.855,.558),(1.028,.570),(1.028,.638)]


# V4 uses a coherent source-informed C1 field and stable semantic rails.
from fair_body import dimension,glass_profile,shoulder,side_limits,plane_x,deck,body_surface_point
from fair_body import samples as fair_samples, C as FAIR_CONTROLS
from fair_body import surface_y,front_cap_y


def loft(name,rings,mat,parent):
    vertices=[v for ring in rings for v in ring];n=len(rings[0]);faces=[]
    for i in range(len(rings)-1):
        for j in range(n):
            faces.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
    if name=='BodyShell':
        cols=n//2;levels=32
        grid=[]
        for j in range(cols):
            a=np.array(rings[0][j]);b=np.array(rings[0][n-1-j]);column=[]
            for k in range(levels+1):
                if k==0:column.append(j)
                elif k==levels:column.append(n-1-j)
                else:
                    point=a+(b-a)*k/levels
                    point[1]=front_cap_y(point[0],point[2])
                    column.append(len(vertices));vertices.append(tuple(point))
            grid.append(column)
        for j in range(cols-1):
            for k in range(levels):faces.append((grid[j][k],grid[j+1][k],grid[j+1][k+1],grid[j][k+1]))
    else:faces.append(tuple(range(n-1,-1,-1)))
    faces.append(tuple((len(rings)-1)*n+j for j in range(n)))
    return mesh(name,vertices,faces,mat,parent)


def cut_wheel_arches(ob):
    guard()
    for axle in ('front_wheel','rear_wheel'):
        w=FIT[axle]
        for side in (-1,1):
            bpy.ops.mesh.primitive_cylinder_add(vertices=96,radius=w['radius']+.040,depth=.66,
                end_fill_type='NGON',location=(side*w['centre_x'],w['y'],w['z']),rotation=(0,math.pi/2,0))
            cutter=bpy.context.object;cutter.name='TemporaryWheelArchCutter'
            bpy.context.view_layer.objects.active=ob
            mod=ob.modifiers.new('FittedWheelArch','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
            bpy.ops.object.modifier_apply(modifier=mod.name)
            bpy.data.objects.remove(cutter,do_unlink=True)


def body(root,mats):
    rings=[];lower_rings=[]
    build_ys=sorted(set(list(YS)+[r[0] for r in FAIR_CONTROLS['centre']]+[r[0] for r in FAIR_CONTROLS['shoulder']]+[-1.46,-1.17,-.31,-.30,-.10,0,.45,.55,.60,.91,1.15,1.84]))
    for y in build_ys:
        w,low=dimension(y,'half_width'),dimension(y,'lower')
        xs=fair_samples(y)
        top=[]
        for sign in (-1,1):
            for x in (xs[::-1] if sign==-1 else xs[1:]):
                top.append(body_surface_point(y,sign*x))
        bottom=[(x,surface_y(y,x,low-.015),low-.015) for x,yy,z in top[::-1]]
        ring=top+bottom
        rings.append(ring)
        bottom=.115+max(0,y-.9)*.025
        lower_rings.append([(-w*.993,y,low-.015),(w*.993,y,low-.015),
                            (w*.985,y,bottom+.03),(w*.9,y,bottom),(-w*.9,y,bottom),(-w*.985,y,bottom+.03)])
        lower_rings[-1]=[(x,surface_y(y,x,z),z) for x,yy,z in lower_rings[-1]]
    shell=loft('BodyShell',rings,mats['white'],root)
    cut_wheel_arches(shell)
    belt=loft('Undercarriage',lower_rings,mats['carbon'],root)
    # Keep a closed solid through every Boolean. Tag the original upper roof
    # so only that duplicate interface can be deleted after the final cut.
    belt.data.materials.append(mats['carbon'])
    for face in belt.data.polygons:
        if face.normal.z>.90:face.material_index=1
    cut_wheel_arches(belt)
    # Actual rear negative space: the diffuser/nozzles sit in a recessed cavity,
    # not painted onto an unbroken black bumper slab.
    bpy.ops.mesh.primitive_cube_add(size=1,location=(0,BACK-.11,.325))
    cutter=bpy.context.object;cutter.dimensions=(1.92,.52,.39)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bpy.context.view_layer.objects.active=belt
    mod=belt.modifiers.new('RearDiffuserCavity','BOOLEAN');mod.operation='DIFFERENCE';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)
    for poly in shell.data.polygons:poly.use_smooth=True
    return shell


def canopy(root,mats):
    # V3 glazing is owned by BodyShell faces. No overlaid exterior surfaces.
    empty('Canopy',parent=root)['surface_ownership']='single shared exterior topology; glass material faces only'


def assign_glazing(mats):
    ob=bpy.data.objects['BodyShell'];ob.data.materials.clear()
    ob.data.materials.append(mats['white']);ob.data.materials.append(mats['glass']);ob.data.materials.append(mats['black']);ob.data.materials.append(mats['whiteLight'])
    ob.data.materials.append(mats['trim'])
    glass_faces=0
    for face in ob.data.polygons:
        p=face.center;x,y,z=abs(p.x),p.y,p.z;glass=False
        if info:=glass_profile(y):
            _,w,top=info
            glass=(x<=w+1e-6 and z>top-.04)
            if -1.17<y<1.15 and x>=w-.002:
                glass=glass or (inside_polygon((y,z),FAIR_CONTROLS['side_glass_yz']) and abs(face.normal.x)>.25)
        face.material_index=1 if glass else 0
        face.use_smooth=True
        if not glass and -1.17<y<-.31 and abs(face.normal.x)>.25:
            a,b=FAIR_CONTROLS['side_glass_yz'][:2];dy=b[0]-a[0];dz=b[1]-a[1]
            signed=(dy*(z-a[1])-dz*(y-a[0]))/math.hypot(dy,dz)
            if info and x>=info[1]-.002 and signed>.025:face.material_index=4
        if y<FRONT+.080 and face.normal.y<-.50:
            if inside_polygon((x,z),LAMP_POCKET):face.material_index=2
            if inside_polygon((x,z),LAMP_LENS):face.material_index=3
        glass_faces+=int(glass)
    ob['glazing_faces']=glass_faces;ob['overlay_glass_meshes']=0
    # Designed roof, shoulder and forward-cap creases own split normals; broad
    # continuous panels remain smooth instead of inflating across every corner.
    ob.data.set_sharp_from_angle(angle=math.radians(32));ob.data.update()


def project_side_glass():
    guard();ob=bpy.data.objects['BodyShell']
    fit=json.loads((ROOT/'fit/side-glass-plane-v4.json').read_text());a,b,c=fit['coefficients']
    polygon=FAIR_CONTROLS['side_glass_yz'];margin=fit['frame_blend_margin_m'];moves=[]
    def distance(y,z):
        if inside_polygon((y,z),polygon):return 0
        best=1e6
        for q,r in zip(polygon,polygon[1:]+polygon[:1]):
            dy=r[0]-q[0];dz=r[1]-q[1];den=dy*dy+dz*dz
            t=max(0,min(1,((y-q[0])*dy+(z-q[1])*dz)/den))
            best=min(best,math.hypot(y-q[0]-t*dy,z-q[1]-t*dz))
        return best
    for vertex in ob.data.vertices:
        x,y,z=vertex.co
        if not(-1.30<y<1.30 and .78<z<1.36):continue
        info=glass_profile(y)
        if not info:continue
        d=distance(y,z)
        if d>=margin:continue
        t=d/margin;weight=1-t*t*(3-2*t)
        side=max(0,min(1,(abs(x)-info[1]+.020)/.040));weight*=side*side*(3-2*side)
        target=(a+b*y+c*z)*(1 if x>=0 else -1)
        delta=(target-x)*weight;vertex.co.x+=delta;moves.append(abs(delta))
    ob.data.update();ob.data.set_sharp_from_angle(angle=math.radians(32));ob.data.update()
    (ROOT/'fit/side-glass-projection-v4.json').write_text(json.dumps({'vertices_adjusted':len(moves),
       'maximum_vertex_departure_mm':max(moves,default=0)*1000,'aperture_yz_preserved':True,
       'method':'One plane owns each side pane; shared surrounding paint/trim vertices blend over80mm. Sharp edges recomputed after projection.'},indent=2)+'\n')


def inside_polygon(point,polygon):
    inside=False;x,y=point
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside


def cut_boundaries(planes):
    ob=bpy.data.objects['BodyShell'];bm=bmesh.new();bm.from_mesh(ob.data)
    for point,normal in planes:
        bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),
            dist=1e-7,plane_co=point,plane_no=normal,clear_inner=False,clear_outer=False)
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bad=[f for f in bm.faces if f.calc_area()<1e-10]
    if bad:bmesh.ops.delete(bm,geom=bad,context='FACES')
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free();ob.data.update()


def cut_lamp_boundaries():
    planes=[]
    for side in (-1,1):
        for outline in (LAMP_POCKET,LAMP_LENS):
            points=[(side*x,z) for x,z in outline]
            for a,b in zip(points,points[1:]+points[:1]):
                planes.append(((a[0],0,a[1]),(b[1]-a[1],0,a[0]-b[0])))
    cut_boundaries(planes)


def cut_glass_boundaries():
    planes=[]
    # Exact YZ side-aperture boundary planes, shared by paint and glass.
    polygon=FAIR_CONTROLS['side_glass_yz']
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        planes.append(((0,a[0],a[1]),(0,b[1]-a[1],a[0]-b[0])))
    a,b=polygon[:2];dy=b[0]-a[0];dz=b[1]-a[1]
    offset=.025*math.hypot(dy,dz)/dy
    planes.append(((0,a[0],a[1]+offset),(0,dz,-dy)))
    # Exact XY top-glass edges and fore/aft extents. The semantic section grid
    # already follows these roof edges; cuts make every face ownership explicit.
    for key in ('windshield','roof','rear_hatch'):
        p=PATCH['glass_landmarks'][key]
        a=(p['front_y'],p['front_half_width']);b=(p['back_y'],p['back_half_width'])
        for side in (-1,1):
            planes.append(((side*a[1],a[0],0),(b[0]-a[0],-side*(b[1]-a[1]),0)))
        for y in (a[0],b[0]):planes.append(((0,y,0),(0,1,0)))
    cut_boundaries(planes)


def wheels(root,mats):
    for axle,prefix in (('front_wheel','F'),('rear_wheel','R')):
        w=FIT[axle];r=w['radius'];half=w['tire_width']/2
        for side,label in ((1,'L'),(-1,'R')):
            name='Wheel_'+prefix+label
            pivot=empty(name,(side*w['centre_x'],w['y'],r),parent=root)
            pivot['semantic']='wheel spin pivot';pivot['spin_axis']='local +X';pivot['radius_m']=r
            profile=[(-half,.02),(-half,r*.83),(-half*.90,r*.95),(-half*.55,r),
                     (half*.55,r),(half*.90,r*.95),(half,r*.83),(half,.02)]
            revolve(name+'_Tire',profile,'X',mats['rubber'],pivot,sides=96)
            outside=side*(half+.002)
            revolve(name+'_AeroDisc',[(outside,0),(outside,r*.72),(outside-side*.010,r*.83),
                    (outside-side*.021,r*.845),(outside-side*.025,0)],'X',mats['disc'],pivot,sides=96)
            revolve(name+'_RimRing',[(outside-side*.010,r*.83),(outside-side*.007,r*.85),
                    (outside-side*.013,r*.87),(outside-side*.022,r*.87)],'X',mats['rim'],pivot,sides=96)
            revolve(name+'_Hub',[(outside+side*.006,0),(outside+side*.006,r*.115),
                    (outside-side*.004,r*.14),(outside-side*.01,0)],'X',mats['black'],pivot,sides=48)


def make_materials():
    return {
      'white':material('PearlWhite',(.84,.87,.90),metallic=.24,roughness=.24),
      'glass':material('SmokedCanopy',(.008,.012,.017),metallic=.0,roughness=.27),
      'carbon':material('CarbonUndercarriage',(.020,.025,.030),metallic=.22,roughness=.38),
      'black':material('DeepBlack',(.006,.009,.012),metallic=.10,roughness=.32),
      'trim':material('StructuralTrim',(.003,.005,.007),metallic=.95,roughness=.65),
      'rubber':material('TireRubber',(.018,.020,.023),roughness=.83),
      'disc':material('AeroDiscGraphite',(.065,.075,.083),metallic=.68,roughness=.28),
      'rim':material('RimEdge',(.14,.17,.19),metallic=.85,roughness=.28),
      'brass':material('ThrusterBrass',(.48,.29,.10),metallic=.82,roughness=.30),
      'whiteLight':material('WhiteLED',(.8,.94,1),roughness=.23,emission=8),
      'redLight':material('RedLED',(1,.015,.008),roughness=.24,emission=3),
      'amberLight':material('AmberLED',(1,.20,.018),roughness=.24,emission=2),
    }


def details(root,mats):
    # Lights and shut lines follow the deck or their own body-mounted frame.
    fy=FRONT-.003;fz=min(.59,deck(FRONT+.03,0)-.036)
    solid_box('FrontLEDRecess',[(-.88,fy-.004,fz-.021),(.88,fy+.04,fz+.015)],mats['black'],root)
    line_tube('FrontLightBar',[(-.87,fy,fz),(0,fy-.010,fz),(.87,fy,fz)],.010,mats['whiteLight'],root,sides=8)
    for side,label in ((1,'L'),(-1,'R')):
        points=[]
        for y,fraction in ((FRONT+.14,.90),(FRONT+.24,.91),(FRONT+.37,.92)):
            w=dimension(y,'half_width')
            points.append((side*w*fraction,y,deck(y,fraction)+.005))
        line_tube('Headlamp_'+label,points,.019,mats['whiteLight'],root,sides=8)
        y=-1.0
        line_tube('SideMarker_'+label,[(side*(dimension(yy,'half_width')+.003),yy,deck(yy,1)-.05)
                  for yy in (y-.10,y+.10)],.009,mats['amberLight'],root,sides=6)
        # The door shut line follows the actual loft width and shoulder surface.
        for suffix,ys in (('Front',[-1.0,-.92,-.86]),('Rear',[.36,.26,.12])):
            points=[]
            for k,y in enumerate(ys):
                z=deck(y,.96)-k*.24
                points.append((side*(dimension(y,'half_width')+.002),y,max(z,dimension(y,'lower')+.025)))
            line_tube('DoorSeam_'+label+'_'+suffix,points,.003,mats['black'],root,sides=4)
        # The integrated undercarriage owns the rocker. The former standalone
        # sill tube intersected the white lower edge and is intentionally gone.
    rz=min(deck(BACK-.02,0),deck(BACK-.02,.85))-.035
    solid_box('RearLampHousing',[(-1.03,BACK-.07,rz-.032),(1.03,BACK+.004,rz+.035)],mats['black'],root)
    line_tube('RearLightBar',[(-1.015,BACK+.008,rz),(0,BACK+.012,rz),(1.015,BACK+.008,rz)],.012,mats['redLight'],root,sides=8)
    line_tube('RearUpperBrakeLamp',[(-.36,BACK+.012,rz+.035),(.36,BACK+.012,rz+.035)],.008,mats['redLight'],root,sides=8)
    # Sculpted diffuser floor with tapering channels rather than fan pockets.
    solid_box('DiffuserCavityBack',[(-.96,BACK-.365,.13),(.96,BACK-.345,.51)],mats['black'],root)
    line_tube('DiffuserFrame',[(-.95,BACK+.014,.15),(-.95,BACK+.014,.40),(-.76,BACK+.014,.49),
              (.76,BACK+.014,.49),(.95,BACK+.014,.40),(.95,BACK+.014,.15)],.018,mats['carbon'],root,sides=6)
    mesh('RearDiffuser',[(-.97,BACK-.50,.12),(.97,BACK-.50,.12),(.99,BACK+.02,.19),(-.99,BACK+.02,.19),
                        (-.97,BACK-.50,.10),(.97,BACK-.50,.10),(.99,BACK+.02,.15),(-.99,BACK+.02,.15)],
         [(0,1,2,3),(4,7,6,5),(0,4,5,1),(3,2,6,7),(0,3,7,4),(1,5,6,2)],mats['carbon'],root)
    for i,x in enumerate(np.linspace(-.82,.82,6)):
        mesh('DiffuserStrake_'+str(i+1),[(x-.008,BACK-.48,.11),(x+.008,BACK-.48,.11),
             (x+.010,BACK+.026,.13),(x-.010,BACK+.026,.13),
             (x-.008,BACK-.48,.13),(x+.008,BACK-.48,.13),
             (x+.010,BACK+.026,.35),(x-.010,BACK+.026,.35)],
             [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],mats['carbon'],root)
    solid_box('RearBlankPlate',[(-.205,BACK+.013,.655),(.205,BACK+.027,.83)],mats['white'],root)
    for index,x in enumerate((-.456,-.152,.152,.456),1):
        anchor=empty('NozzleAnchor_'+str(index),(x,BACK+.035,.367),parent=root)
        anchor.rotation_euler.z=math.pi
        anchor['semantic']='rear thruster attachment';anchor['rearward_blender']=[0,1,0]
        # glTF local +Z is rearward at this anchor; cancel the basis rotation on
        # the brass construction children so their fitted positions stay fixed.
        nozzle=revolve('Nozzle_'+str(index),[(-.14,.038),(-.12,.053),(-.045,.058),(.0,.063),(.008,.064),
                (.008,.049),(-.012,.046),(-.105,.032)],'Y',mats['brass'],anchor,sides=48)
        nozzle.rotation_euler.z=math.pi
        interior=revolve('Nozzle_'+str(index)+'_Interior',[(-.108,0),(-.108,.032),(-.13,.035),(-.13,0)],
                'Y',mats['black'],anchor,sides=48)
        interior.rotation_euler.z=math.pi


def export_model(root):
    guard()
    output=ROOT.parents[2]/'public/models/roadster.glb';output.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in collection('Authored').objects:ob.select_set(True)
    # Parent-only basis conversion: authored -Y becomes runtime +X; restore .blend.
    root.rotation_euler.z=math.pi/2;bpy.context.view_layer.update()
    bpy.ops.export_scene.gltf(filepath=str(output),export_format='GLB',use_selection=True,
          export_yup=True,export_apply=True,export_cameras=False,export_lights=False,
          export_extras=True,export_materials='EXPORT')
    root.rotation_euler.z=0;bpy.context.view_layer.update()
    return output


def build():
    guard();collection('Authored',clear=True)
    for datablock in list(bpy.data.meshes):
        if datablock.users==0:bpy.data.meshes.remove(datablock)
    mats=make_materials();root=empty('Roadster');root['units']='metres';root['authoring_forward']='-Y'
    body(root,mats);canopy(root,mats);wheels(root,mats)
    ref=bpy.data.objects['RefMesh']
    # Extraction coordinates are the immutable normalized reference; this one
    # transform aligns it to the fitted wheel-contact origin without changing data.
    if ref.get('wheel_origin_shift') is None:
        ref.matrix_world=Matrix.Translation((0,FIT['reference_y_shift_to_contacts'],0))@ref.matrix_world
        ref['wheel_origin_shift']=FIT['reference_y_shift_to_contacts']
    if not PRIMARY:details(root,mats)
    from facade_refinements import refine_facades
    refine_facades(root,mats,FRONT,BACK,deck,dimension,primary=PRIMARY)
    cut_lamp_boundaries();cut_glass_boundaries()
    assign_glazing(mats)
    project_side_glass()
    from cleanup_geometry import clean_cut_slivers
    clean_cut_slivers()
    if not PRIMARY:
        for side,label in [(1,'L'),(-1,'R')]:
            points=[]
            for t in np.linspace(0,1,28):
                y=(FRONT+.025)*(1-t)+(-1.46)*t;x=side*(.86*(1-t)+.88*t)
                xx,yy,z=body_surface_point(y,x);points.append((xx,yy,z+.0018))
            line_tube('HoodShutLine_'+label,points,.0017,mats['black'],root,sides=4)
    collection('Ref').hide_render=True
    save()
    folder=ROOT/('checkpoint-v4' if PRIMARY else 'repair-checkpoint-v4c' if QUICK else 'renders')
    if QUICK:
        render_views(folder,groups=('Authored',),modes=('material','clay'),views=('low-front','low-quarter'))
    elif PRIMARY:
        render_views(folder,groups=('Authored',),modes=('clay',),views=('front','left','quarter','rear-quarter'))
        render_views(folder,groups=('Authored',),modes=('material',),views=('front','quarter'))
    else:
        render_views(folder,groups=('Authored',),modes=('material','clay'),views=('front','left','back','top','quarter','rear-quarter','low-front','low-quarter'))
    meshes=[ob for ob in collection('Authored').objects if ob.type=='MESH']
    triangles=sum(sum(len(p.vertices)-2 for p in ob.data.polygons) for ob in meshes)
    stats={'triangles':triangles,'mesh_parts':len(meshes),'objects':len(collection('Authored').objects),
           'source_triangles':188630,'primary_checkpoint':PRIMARY}
    (folder/'stats.json').write_text(json.dumps(stats,indent=2)+'\n')
    if not PRIMARY:export_model(root)
    save();print('ROADSTER_BUILD '+json.dumps(stats))


build()
