"""Fit symmetric authored construction inputs from the untouched Tripo shell.

Uses area/colour masks, robust wheel circle fits, and measured longitudinal
sections. Authored simplifications are recorded rather than disguised as fits.
"""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parent
R=np.load(ROOT/'reference/faces.npz')
P,N,A,C=R['fc'],R['fn'],R['fa'],R['col']
V=R['co']
WHITE=C.min(1)>.5
BLACK=C.mean(1)<.31
W=float(np.quantile(abs(P[:,0]),.999))
HEIGHT=float(V[:,2].max())


def circle3(points):
    matrix=np.column_stack((2*points[:,0],2*points[:,1],np.ones(len(points))))
    answer=np.linalg.lstsq(matrix,(points*points).sum(1),rcond=None)[0]
    centre=answer[:2];radius=np.sqrt(max(0,answer[2]+centre@centre))
    return centre,float(radius)


def wheel_fit(y_hint):
    mask=(abs(P[:,0])>W*.85)&(abs(P[:,1]-y_hint)<.58)&(P[:,2]<.29)&BLACK&(abs(N[:,0])<.55)
    q=P[mask,1:3]
    random=np.random.default_rng(20261017)
    best=None
    for _ in range(1800):
        rows=random.choice(len(q),3,replace=False)
        centre,radius=circle3(q[rows])
        if not .29<radius<.46 or abs(centre[0]-y_hint)>.2 or abs(centre[1]-radius)>.07:
            continue
        errors=abs(np.linalg.norm(q-centre,axis=1)-radius)
        inliers=errors<.009
        score=int(inliers.sum())
        if best is None or score>best[0]:best=(score,centre,radius,inliers)
    if best is None:raise RuntimeError('Wheel RANSAC could not fit a tire')
    centre,radius=circle3(q[best[3]])
    errors=abs(np.linalg.norm(q[best[3]]-centre,axis=1)-radius)
    side=(abs(P[:,1]-centre[0])<radius*.65)&(abs(P[:,2]-centre[1])<radius*.6)&BLACK
    side &= (abs(P[:,0])>W*.75)&(abs(N[:,0])>.9)
    outer=float(np.quantile(abs(P[side,0]),.95))
    tire_width=.275  # deliberate constant: dark inner wheel surfaces are occluded.
    return {'y':float(centre[0]),'radius':float(radius),'z':float(radius),'outer_x':outer,
            'centre_x':outer-tire_width/2,'tire_width':tire_width,
            'fit':{'inlier_points':int(best[3].sum()),'mean_radial_error_mm':float(errors.mean()*1000),
                   'p90_radial_error_mm':float(np.quantile(errors,.9)*1000),
                   'raw_centre_z':float(centre[1]),'floor_correction_mm':float((radius-centre[1])*1000)}}


front=wheel_fit(-1.42);back=wheel_fit(1.47)
ORIGIN_Y=(front['y']+back['y'])/2
front['y']-=ORIGIN_Y;back['y']-=ORIGIN_Y


def quantile(values,q,default):
    return float(np.quantile(values,q)) if len(values)>5 else default


stations=[]
previous_w=.9
previous_top=.56
for y in np.linspace(float(V[:,1].min())+.025,float(V[:,1].max())-.025,43):
    band=(abs(P[:,1]-y)<.09)&WHITE
    points=P[band]
    w=quantile(abs(points[:,0]),.99,previous_w)
    w=float(np.clip(w,.83,W))
    side=band&(abs(P[:,0])>w*.80)&(P[:,2]>.35)
    shoulder=quantile(P[side,2],.94,previous_top)
    middle=band&(abs(P[:,0])<w*.50)
    centre=quantile(P[middle,2],.90,shoulder)
    # The white roof/pillars are not the primary body deck. Upper cabin is
    # authored independently from the full reference's high silhouette.
    if -1.26<y<1.25:centre=min(centre,shoulder+.014)
    top=[]
    for fraction in (0,.32,.62,.82,.95,1.0):
        m=band&(abs(abs(P[:,0])/w-fraction)<.12)
        z=quantile(P[m,2],.89,centre+(shoulder-centre)*fraction)
        if -1.26<y<1.25:z=min(z,shoulder+.02)
        if fraction==0:z=centre
        top.append(z)
    lower=quantile(P[band&(abs(P[:,0])>w*.65),2],.03,.29)
    lower=float(np.clip(lower,.285,.57))
    stations.append({'y':float(y-ORIGIN_Y),'half_width':w,'top':top,'lower':lower})
    previous_w,previous_top=w,shoulder

# Suppress local source bumps while preserving the fitted wedge and arch humps.
for key in ('half_width','lower'):
    a=np.array([s[key] for s in stations]);filtered=np.convolve(np.pad(a,(1,1),mode='edge'),[.25,.5,.25],mode='valid')
    for s,val in zip(stations,filtered):s[key]=float(val)
for k in range(6):
    a=np.array([s['top'][k] for s in stations]);filtered=np.convolve(np.pad(a,(1,1),mode='edge'),[.25,.5,.25],mode='valid')
    for s,val in zip(stations,filtered):s['top'][k]=float(val)

# Fit the designed longitudinal trends rather than the shell's local dents.
# A symmetric nine-station low-pass is deterministic and leaves source units
# explicit; it is recorded as a deliberate denoising departure below.
kernel=np.array([1,2,3,4,5,4,3,2,1],dtype=float)/25
def denoise(a,passes=2):
    for _ in range(passes):a=np.convolve(np.pad(a,(4,4),mode='edge'),kernel,mode='valid')
    return a
for key in ('half_width','lower'):
    for s,val in zip(stations,denoise(np.array([s[key] for s in stations]))):s[key]=float(val)
for k in range(6):
    for s,val in zip(stations,denoise(np.array([s['top'][k] for s in stations]))):s['top'][k]=float(val)

cabin=[]
for y in np.linspace(-1.65,1.93,43):
    band=(abs(P[:,1]-y)<.055)&(abs(P[:,0])<.35)&(P[:,2]>.66)
    points=P[band]
    z=quantile(points[:,2],.97,.83)
    shoulder=float(np.interp(y-ORIGIN_Y,[s['y'] for s in stations],[s['top'][2] for s in stations]))
    dark=(abs(P[:,1]-y)<.07)&(abs(P[:,0])<.96)&BLACK&(P[:,2]>shoulder+.025)
    half=quantile(abs(P[dark,0]),.97,.75)
    half=float(np.clip(half,.52,.92))
    cabin.append({'y':float(y-ORIGIN_Y),'top_z':z,'base_z':shoulder,'half_width':half})
for key in ('top_z','half_width'):
    values=np.array([s[key] for s in cabin])
    ys=np.array([s['y'] for s in cabin])
    values=np.polyval(np.polyfit(ys,values,7 if key=='top_z' else 5),ys)
    for s,val in zip(cabin,values):s[key]=float(val)
for index in (0,-1):
    s=cabin[index]
    s['top_z']=float(np.interp(s['y'],[r['y'] for r in stations],[r['top'][0] for r in stations]))+.002

fit={'nominal_length':4.6,'reference_height':HEIGHT,'reference_width':float(V[:,0].max()-V[:,0].min()),
     'reference_y_shift_to_contacts':-ORIGIN_Y,'front_wheel':front,'rear_wheel':back,
     'wheelbase':back['y']-front['y'],'front_track':2*front['centre_x'],'rear_track':2*back['centre_x'],
     'stations':stations,'cabin':cabin,
     'deliberate_departures':['Exact bilateral symmetry; the reference shell has small generated asymmetries.',
       'Wheel centres are floored to z=radius; tiny generated tire flattening is removed.',
       'Inner tire width is authored at 0.275m because inner surfaces are occluded.',
       'The white primary body is a continuous fitted section loft; roof and dark canopy are separate authored surfaces.',
       'Nine-station symmetric low-pass denoising removes local shell dents from body profile fits; canopy height/width use seventh/fifth-degree trends and flush hood/deck end constraints.',
       'Small texture noise and generated window dents are removed; no original generated triangles are exported.']}
(ROOT/'fit').mkdir(exist_ok=True)
(ROOT/'fit/roadster.json').write_text(json.dumps(fit,indent=2)+'\n')
print(json.dumps({k:fit[k] for k in ('reference_width','reference_height','wheelbase','front_track','rear_track')}))
print(json.dumps({'front_wheel':front,'rear_wheel':back},indent=2))
