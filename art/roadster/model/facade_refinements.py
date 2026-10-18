"""Source-shaped front/rear volumes; restrained manufactured finishing."""
import math
import bpy
import bmesh
import numpy as np
from model_lib import *
from fair_body import front_cap_y


def remove(names):
    for name in names:
        if ob:=bpy.data.objects.get(name):bpy.data.objects.remove(ob,do_unlink=True)


def difference(target,cutter):
    bpy.context.view_layer.objects.active=target
    mod=target.modifiers.new('SourceVolumeCut','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name);bpy.data.objects.remove(cutter,do_unlink=True)


def remove_opening_cut_walls(target,front,bottom):
    """The authored black jamb/back own the cavity; discard white cut walls."""
    bm=bmesh.new();bm.from_mesh(target.data);remove=[];top=.552
    for face in bm.faces:
        points=[v.co for v in face.verts];center=face.calc_center_median()
        if not front-.1001<center.y<front+.5001:continue
        def inside(p):
            bound=.86+(.552-p.z)/(.552-bottom)*.12
            return bottom-1e-5<=p.z<=top+1e-5 and abs(p.x)<=bound+2e-5
        side=all(bottom-1e-5<=p.z<=top+1e-5 and
             abs(abs(p.x)-(.86+(.552-p.z)/(.552-bottom)*.12))<2e-5 for p in points)
        ceiling=all(abs(p.z-top)<2e-5 and abs(p.x)<.8601 for p in points)
        floor=all(abs(p.z-bottom)<2e-5 and abs(p.x)<.9801 for p in points)
        backwall=all(abs(p.y-(front+.50))<2e-5 and inside(p) for p in points)
        if side or ceiling or floor or backwall:remove.append(face)
    count=len(remove)
    if remove:bmesh.ops.delete(bm,geom=remove,context='FACES_ONLY')
    bm.to_mesh(target.data);bm.free();target.data.update()
    target['discarded_duplicate_cavity_wall_faces']=count


def remove_belt_roof(target):
    bm=bmesh.new();bm.from_mesh(target.data)
    faces=[face for face in bm.faces if face.material_index==1]
    target['discarded_duplicate_roof_faces']=len(faces)
    if faces:bmesh.ops.delete(bm,geom=faces,context='FACES_ONLY')
    bm.to_mesh(target.data);bm.free()
    if len(target.data.materials)>1:target.data.materials.pop(index=1)
    target.data.update()


def refine_facades(root,mats,front,back,deck,dimension,primary=False):
    guard()
    # A dark rough conductor has a near-black F0 in core glTF. This avoids a
    # dielectric cavity floor turning pale under the runtime's bright IBL.
    intake=material('IntakeAbsorbent',(.003,.004,.005),metallic=.95,roughness=.80)
    shader=intake.node_tree.nodes.get('Principled BSDF')
    shader.inputs['IOR'].default_value=1.45;shader.inputs['Specular IOR Level'].default_value=.50
    remove(['FrontFascia','FrontLEDRecess','FrontLightBar','Headlamp_L','Headlamp_R',
       'RearDiffuser','DiffuserFrame','DiffuserCavityBack','RearLampHousing','RearLightBar','RearUpperBrakeLamp']+
       ['DiffuserStrake_'+str(i) for i in range(1,7)])
    shell=bpy.data.objects['BodyShell']
    def nose_y(x,z=.56):return front_cap_y(x,z)
    outer=[(-.86,nose_y(.86,.552),.552),(.86,nose_y(.86,.552),.552),
           (.98,nose_y(.98,.143),.143),(-.98,nose_y(.98,.143),.143)]
    cutter=mesh('TemporaryOpening',[(x,front-.10,z) for x,y,z in outer]+[(x,front+.50,z) for x,y,z in outer],
        [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],None,root)
    duplicate=cutter.copy();duplicate.data=cutter.data.copy();collection('Authored').objects.link(duplicate)
    # The belt must be removed below the visible mouth lip as well. Stopping
    # its cut at .143 left a broad horizontal carbon floor above the intended
    # recess floor, confirmed by exported-GLB first-hit rays.
    for vertex in duplicate.data.vertices:
        if vertex.co.z<.20:vertex.co.z=.065
    duplicate.data.update()
    difference(shell,cutter);difference(bpy.data.objects['Undercarriage'],duplicate)
    remove_opening_cut_walls(bpy.data.objects['Undercarriage'],front,.065)
    remove_belt_roof(bpy.data.objects['Undercarriage'])
    # The intake floor stays below the mouth lip as it recedes. An upward
    # sloping floor exposed a large lit tray from normal front-quarter views.
    inner=[(-.77,front+.41,.516),(.77,front+.41,.516),(.87,front+.41,.130),(-.87,front+.41,.130)]
    mesh('FrontOpeningJambs',outer+inner,[(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],intake,root)
    mesh('FrontRecessBack',inner,[(0,1,2,3)],intake,root)
    # A narrow low lip, not a deep exposed board across the whole cavity.
    leading=[(float(x),nose_y(x,.125)-.012,.125) for x in np.linspace(-1.055,1.055,25)]
    trailing=[(x,y+.077,z) for x,y,z in leading[::-1]]
    splitter=leading+trailing
    n=len(splitter);verts=splitter+[(x,y,z-.025) for x,y,z in splitter]
    faces=[tuple(range(n)),tuple(range(2*n-1,n-1,-1))]
    for i in range(n):faces.append((i,(i+1)%n,(i+1)%n+n,i+n))
    mesh('FrontSplitter',verts,faces,intake,root)
    # White fender terminals and corner lenses share BodyShell's exterior;
    # the exact triangular lens boundaries are cut on its upper chamfer later.
    # No overlapping hexahedra, warped boolean unions or overlaid lamp patches.
    # The emitting line sits wholly against a dark cavity background instead
    # of merging with the saturated white hood edge in neutral/night views.
    solid_box('FrontLEDRecess',[(-.865,front+.020,.512),(.865,front+.045,.550)],intake,root)
    line_tube('FrontLightBar',[(float(x),front+.010,.531) for x in np.linspace(-.855,.855,25)],.008,mats['whiteLight'],root,sides=8)

    # Deep white scalloped relief under the rear lamp. It is a measured-style
    # designed surface, replacing the flat back slab rather than decorating it.
    cut=solid_box('TemporaryRearRelief',[(-1.00,back-.215,.505),(1.00,back+.055,.845)],None,root)
    difference(shell,cut)
    # No subsequent body Boolean may run after opening this interface.
    remove_opening_cut_walls(shell,front,.143)
    verts=[];faces=[];cols=44;rows=12
    for j,t in enumerate(np.linspace(0,1,rows+1)):
        for i,x in enumerate(np.linspace(-1.0,1.0,cols+1)):
            lower=.535+.075*math.sin(math.pi*abs(x))**2
            z=.835*(1-t)+lower*t
            depth=.025+.145*math.sin(math.pi*t)*(1-.25*abs(x))
            verts.append((x,back-depth,z))
    for j in range(rows):
        for i in range(cols):
            a=j*(cols+1)+i;faces.append((a,a+1,a+cols+2,a+cols+1))
    mesh('RearWhiteRelief',verts,faces,mats['white'],root,smooth=True)
    # Dark outboard pockets are part of the bumper volume and expose depth.
    for side,label in [(1,'L'),(-1,'R')]:
        points=[(side*.85,back-.006,.54),(side*1.065,back-.018,.57),
                (side*1.07,back-.04,.35),(side*.94,back-.012,.30),
                (side*.85,back-.19,.54),(side*1.065,back-.19,.57),
                (side*1.07,back-.19,.35),(side*.94,back-.19,.30)]
        mesh('RearSidePocket_'+label,points,[(0,1,5,4),(1,2,6,5),(2,3,7,6),(4,5,6,7)],mats['black'],root)
    rz=.892
    solid_box('RearLampHousing',[(-1.035,back-.025,rz-.023),(1.035,back+.003,rz+.026)],mats['black'],root)
    line_tube('RearLightBar',[(-1.025,back+.009,rz),(1.025,back+.009,rz)],.010,mats['redLight'],root,sides=8)
    line_tube('RearUpperBrakeLamp',[(-.38,back+.010,rz+.032),(.38,back+.010,rz+.032)],.007,mats['redLight'],root,sides=8)
    # Five tapering curved carbon channels: concave aerodynamic ducts, no fan
    # circles and no empty rectangular fence standing in for the whole diffuser.
    for channel in range(5):
        centre=(channel-2)*.346;vertices=[];polys=[];cols=14;rows=10
        for j,t in enumerate(np.linspace(0,1,rows+1)):
            y=back-.44+t*.37;half=.137+.024*t
            for i,u in enumerate(np.linspace(-1,1,cols+1)):
                z=.165+.095*(abs(u)**2)+.055*(1-t)**2
                vertices.append((centre+u*half,y,z))
        for j in range(rows):
            for i in range(cols):
                a=j*(cols+1)+i;polys.append((a,a+1,a+cols+2,a+cols+1))
        mesh('DiffuserChannel_'+str(channel+1),vertices,polys,mats['carbon'],root,smooth=True)
    line_tube('DiffuserFrame',[(-.96,back+.015,.15),(-.96,back+.015,.39),(-.76,back+.015,.49),
              (.76,back+.015,.49),(.96,back+.015,.39),(.96,back+.015,.15)],.025,mats['carbon'],root,sides=8)
    solid_box('DiffuserUpperBeam',[(-.76,back-.08,.477),(.76,back+.025,.512)],mats['carbon'],root)
    solid_box('DiffuserLowerShroud',[(-.96,back-.23,.105),(.96,back+.027,.162)],mats['carbon'],root)
    for side,label in [(1,'L'),(-1,'R')]:
        solid_box('DiffuserOuterShroud_'+label,[(min(side*.90,side*.98),back-.30,.13),
                  (max(side*.90,side*.98),back+.025,.395)],mats['carbon'],root)
    if not primary:
        for name in ['Wheel_FL','Wheel_FR','Wheel_RL','Wheel_RR']:
            pivot=bpy.data.objects[name];side=1 if name.endswith('L') else -1;r=pivot['radius_m'];x=side*(.1375+.004)
            verts=[];polys=[]
            for i in range(32):
                angle=2*math.pi*i/32;rad=r*.855;da=.035
                for radius,theta in [(rad-.008,angle-da),(rad+.008,angle-da),(rad+.008,angle+da),(rad-.008,angle+da)]:
                    verts.append((x,radius*math.cos(theta),radius*math.sin(theta)))
                n=len(verts)-4;polys.append((n,n+1,n+2,n+3))
            mesh(name+'_AeroRimSegments',verts,polys,mats['black'],pivot)
    # Export booleans after removing truly zero-area hidden fragments.
    for ob in collection('Authored').objects:
        if ob.type!='MESH':continue
        bm=bmesh.new();bm.from_mesh(ob.data)
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bad=[f for f in bm.faces if f.calc_area()<1e-10]
        if bad:bmesh.ops.delete(bm,geom=bad,context='FACES')
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free()
        ob.data.validate(verbose=False,clean_customdata=True);ob.data.update()
