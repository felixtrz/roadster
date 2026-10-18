"""Inspect the exported binary glTF hierarchy, geometry and semantic basis."""
from pathlib import Path
import json
import struct
import numpy as np

ROOT=Path(__file__).resolve().parent
PATH=ROOT.parents[2]/'public/models/roadster.glb'
blob=PATH.read_bytes()
magic,version,length=struct.unpack_from('<4sII',blob)
assert magic==b'glTF' and version==2 and length==len(blob)
size,kind=struct.unpack_from('<I4s',blob,12)
assert kind==b'JSON'
gltf=json.loads(blob[20:20+size])
bin_size,bin_kind=struct.unpack_from('<I4s',blob,20+size)
assert bin_kind==b'BIN\x00'
binary=blob[28+size:28+size+bin_size]
TYPES={5121:np.uint8,5123:np.uint16,5125:np.uint32,5126:np.float32}
COUNTS={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}


def accessor(index):
    a=gltf['accessors'][index];v=gltf['bufferViews'][a['bufferView']]
    dtype=np.dtype(TYPES[a['componentType']]);width=COUNTS[a['type']]
    offset=v.get('byteOffset',0)+a.get('byteOffset',0)
    stride=v.get('byteStride',dtype.itemsize*width)
    return np.ndarray((a['count'],width),dtype=dtype,buffer=binary,offset=offset,strides=(stride,dtype.itemsize))


def local_matrix(node):
    if 'matrix'in node:return np.asarray(node['matrix']).reshape(4,4).T
    x,y,z,w=node.get('rotation',[0,0,0,1]);r=np.array([
        [1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w,0],
        [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w,0],
        [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y,0],[0,0,0,1]],dtype=float)
    r[:3,:3]=r[:3,:3]@np.diag(node.get('scale',[1,1,1]))
    r[:3,3]=node.get('translation',[0,0,0]);return r


world={}
def visit(index,parent=np.eye(4)):
    m=parent@local_matrix(gltf['nodes'][index]);world[index]=m
    for child in gltf['nodes'][index].get('children',[]):visit(child,m)
for root in gltf['scenes'][gltf.get('scene',0)]['nodes']:visit(root)
names={n.get('name'):i for i,n in enumerate(gltf['nodes'])}
assert not any('RefMesh' in str(name) for name in names)
all_positions=[];triangles=0;degenerate=0;bad_normals=0;mesh_parts=0;degenerate_parts={};glass_owners=[];glass_triangles=0;corner_led_area=0;corner_led_forward_area=0
for index,m in world.items():
    node=gltf['nodes'][index]
    if 'mesh'not in node:continue
    mesh_parts+=1
    for primitive in gltf['meshes'][node['mesh']]['primitives']:
        assert primitive.get('mode',4)==4
        p=accessor(primitive['attributes']['POSITION']);n=accessor(primitive['attributes']['NORMAL'])
        assert np.isfinite(p).all() and np.isfinite(n).all()
        assert len(p)==len(n)
        indices=accessor(primitive['indices']).ravel().astype(int).reshape(-1,3)
        assert indices.min()>=0 and indices.max()<len(p)
        # Match the official IWSDK preview exactly: geometry-local float32
        # positions are promoted to double precision for AB×AC and dot(cross,cross).
        triangle=p[indices].astype(np.float64)
        cross=np.cross(triangle[:,1]-triangle[:,0],triangle[:,2]-triangle[:,0])
        squared_double_area=np.einsum('ij,ij->i',cross,cross)
        areas=np.sqrt(squared_double_area)
        count=int((squared_double_area<1e-16).sum());degenerate+=count;triangles+=len(indices)
        mat=gltf['materials'][primitive.get('material',0)]
        if mat.get('name')=='SmokedCanopy':
            glass_owners.append(node.get('name'));glass_triangles+=len(indices)
        if node.get('name')=='BodyShell' and mat.get('name')=='WhiteLED':
            corner_led_area+=float(areas.sum()/2)
            face_normals=n[indices].mean(1)@m[:3,:3].T
            corner_led_forward_area+=float(areas[face_normals[:,0]>.8].sum()/2)
        if count:degenerate_parts[node.get('name',str(index))]=count
        bad_normals+=int((abs(np.linalg.norm(n,axis=1)-1)>.001).sum())
        all_positions.append(p@m[:3,:3].T+m[:3,3])
points=np.concatenate(all_positions)
assert triangles<100000 and bad_normals==0 and degenerate==0
assert abs(float(points[:,1].min()))<1e-5,'Model must retain the exact tire-contact floor origin'
assert float(np.ptp(points[:,2]))<2.45,'Unexpected object/cutter outside the authored lateral envelope'
assert corner_led_area>.01,'Corner lamp face material missing or implausibly small'
assert corner_led_forward_area/corner_led_area>.95,'Corner lamps must face forward at source-like low views'
cavity=next(m for m in gltf['materials'] if m.get('name')=='IntakeAbsorbent')['pbrMetallicRoughness']
led=next(m for m in gltf['materials'] if m.get('name')=='WhiteLED')
assert cavity['metallicFactor']>=.9 and cavity['roughnessFactor']>=.75
checks={}
for name in ('Wheel_FL','Wheel_FR','Wheel_RL','Wheel_RR'):
    assert name in names;mat=world[names[name]]
    checks[name]={'position':np.round(mat[:3,3],6).tolist(),'local_x_world':np.round(mat[:3,0],6).tolist()}
assert checks['Wheel_FL']['position'][0]>0 and checks['Wheel_RL']['position'][0]<0
assert checks['Wheel_FL']['position'][2]<0 and checks['Wheel_FR']['position'][2]>0
for i in range(1,5):
    name='NozzleAnchor_'+str(i);assert name in names;mat=world[names[name]]
    forward=mat[:3,2]/np.linalg.norm(mat[:3,2])
    assert np.allclose(forward,[-1,0,0],atol=1e-5),name
    checks[name]={'position':np.round(mat[:3,3],6).tolist(),'local_z_world':np.round(forward,6).tolist()}
report={'file':str(PATH.relative_to(ROOT.parents[2])),'file_bytes':len(blob),'triangles':triangles,
 'mesh_parts':mesh_parts,'nodes':len(gltf['nodes']),'nonunit_normals':bad_normals,'degenerate_triangles':degenerate,'degenerate_parts':degenerate_parts,
 'degenerate_threshold':{'official_iwsdk_preview':'dot(AB×AC,AB×AC)<1e-16','double_area_m2':1e-8,'triangle_area_m2':5e-9,'arithmetic':'float32 exported coordinates promoted to float64, in geometry-local coordinates'},
 'runtime_bounds':{'min':points.min(0).tolist(),'max':points.max(0).tolist()},'semantic_checks':checks,
 'basis_verified':{'forward':'+X','up':'+Y','left':'-Z','nozzle_local_plus_z':'rearward -X'},
 'source_mesh_shipped':False,
 'front_material_checks':{'corner_led_area_m2':corner_led_area,
  'corner_led_forward_area_fraction':corner_led_forward_area/corner_led_area,
  'white_led_emissive_factor':led.get('emissiveFactor',[0,0,0]),
  'white_led_emissive_strength':led.get('extensions',{}).get('KHR_materials_emissive_strength',{}).get('emissiveStrength',1),
  'corner_led_surface_owner':'BodyShell',
  'cavity_core_gltf':cavity}}
if set(glass_owners)=={'BodyShell'}:
    report['glazing_ownership']={'owners':sorted(set(glass_owners)),'triangles':glass_triangles,
      'overlay_meshes':0,'method':'Single exterior BodyShell topology has paint/glass face material regions; no underlying duplicate shell is retained beneath an overlay.'}
    assert not any(k in names for k in ['Windshield','RoofGlass','RearHatchGlass','SideGlass_L','SideGlass_R'])
(ROOT/'glb-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
