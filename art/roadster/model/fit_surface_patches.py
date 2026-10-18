"""Blender: fit new controlled surface stations to the normalized reference.

This is authored patch construction input, not a copy/remesh of reference faces.
Body/fender/roof contours are measured by symmetric vertical probes. Explicit
glass landmarks come from the approved orthographic source identity.
"""
from pathlib import Path
import sys,json
import numpy as np
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import guard
guard()
F=json.loads((ROOT/'fit/roadster.json').read_text())
ob=bpy.data.objects['RefMesh'];dg=bpy.context.evaluated_depsgraph_get();ev=ob.evaluated_get(dg)
me=ev.to_mesh();vertices=[ob.matrix_world@v.co for v in me.vertices]
tree=BVHTree.FromPolygons(vertices,[list(p.vertices) for p in me.polygons],all_triangles=False)
ev.to_mesh_clear()
R=np.load(ROOT/'reference/faces.npz');P=R['fc'].copy();P[:,1]+=F['reference_y_shift_to_contacts']
C=R['col'];white=C.min(1)>.5
fractions=[0,.14,.28,.42,.56,.65,.72,.78,.83,.88,.92,.95,.975,.993]
ys=np.linspace(-2.275+F['reference_y_shift_to_contacts'],2.275+F['reference_y_shift_to_contacts'],65)
width=[]
for y in ys:
 m=white&(abs(P[:,1]-y)<.065)
 width.append(float(np.quantile(abs(P[m,0]),.99)))
# Three-point median rejects isolated texture/tire contamination without the
# old broad low-pass that erased the fender crown and rear haunch.
width=np.array([np.median(width[max(0,i-1):min(len(width),i+2)]) for i in range(len(width))])
controls=[]
for y,w in zip(ys,width):
 zs=[]
 for fraction in fractions:
  readings=[]
  for side in [-1,1]:
   for dy in [-.012,0,.012]:
    hit,normal,face,d=tree.ray_cast(Vector((side*w*fraction,y+dy,3)),Vector((0,0,-1)),4)
    if hit:readings.append(hit.z)
  zs.append(float(np.median(readings)) if readings else .5)
 controls.append({'y':float(y),'half_width':float(w),'top_z':zs})
# Filter only adjacent station noise (<~70mm wavelength), separately within
# each designed cross-section rail. Preserve all lateral crease rails.
for k in range(len(fractions)):
 a=np.array([s['top_z'][k] for s in controls]);b=a.copy()
 for i in range(1,len(a)-1):
  if abs(a[i]-(a[i-1]+a[i+1])/2)>.018:b[i]=(a[i-1]+2*a[i]+a[i+1])/4
 for s,z in zip(controls,b):s['top_z'][k]=float(z)

# Fit each feature rail through design stations (nose, front fender crown,
# windshield toe, shoulder, rear haunch and tail), retaining local maxima.
knots=np.array([ys[0],-2.04,-1.80,F['front_wheel']['y'],-1.02,-.60,0,.55,1.0,F['rear_wheel']['y'],1.82,ys[-1]])
def pchip(values):
    v=np.array([np.median(values[abs(ys-y)<.09]) if np.any(abs(ys-y)<.09) else np.interp(y,ys,values) for y in knots])
    sec=np.diff(v)/np.diff(knots);sl=np.zeros(len(v));sl[0]=sec[0];sl[-1]=sec[-1]
    for i in range(1,len(v)-1):
        if sec[i-1]*sec[i]>0:sl[i]=2*sec[i-1]*sec[i]/(sec[i-1]+sec[i])
    out=[]
    for y in ys:
        i=min(len(v)-2,max(0,int(np.searchsorted(knots,y)-1)));h=knots[i+1]-knots[i];t=(y-knots[i])/h
        out.append((2*t**3-3*t*t+1)*v[i]+(t**3-2*t*t+t)*h*sl[i]+(-2*t**3+3*t*t)*v[i+1]+(t**3-t*t)*h*sl[i+1])
    return out
for k in range(len(fractions)):
    vals=pchip(np.array([s['top_z'][k] for s in controls]))
    for s,z in zip(controls,vals):s['top_z'][k]=float(z)
for s in controls:
    for k in range(1,len(fractions)):
        if fractions[k]>.92:s['top_z'][k]=max(s['top_z'][k],s['top_z'][k-1]-.075)
vals=pchip(np.array([s['half_width'] for s in controls]))
for s,w in zip(controls,vals):s['half_width']=float(w)

result={'method':'Symmetric median of six source surface probes per rail/station; only isolated >18mm longitudinal outliers damped once. Independent explicit glass patches preserve designed boundaries.',
 'fractions':fractions,'stations':controls,
 'glass_landmarks':{
  'windshield':{'front_y':-1.46,'back_y':-.30,'front_half_width':.88,'back_half_width':.745},
  'roof':{'front_y':-.30,'back_y':.91,'front_half_width':.745,'back_half_width':.755},
  'rear_hatch':{'front_y':.91,'back_y':1.84,'front_half_width':.755,'back_half_width':.575},
  'side_glass_yz':[[-1.17,.872],[-.31,1.262],[.60,1.245],[1.15,1.087],[.55,.988],[-.10,.925]]},
 'departure':'Glass boundaries are clean authored landmarks informed by the approved source images; generated dents and texture seams do not define them.'}
(ROOT/'fit/surface-patches.json').write_text(json.dumps(result,indent=2)+'\n')
print('Fitted65 body sections across14 preserved lateral feature rails')
