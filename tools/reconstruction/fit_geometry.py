"""Fit two broadcast views to a constrained, extruded ramp profile.

This is a *model-based* reconstruction. It cannot resolve the metric gauge of
uncalibrated monocular footage without priors. Inputs are deliberately public.
"""
from pathlib import Path
import json
import cv2
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from scipy.interpolate import PchipInterpolator

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'references/roadster/reconstruction'

# Visually digitized rail points in original 1920x1080 source pixels. Curve
# samples do NOT assume equal arc-length or matching rows between the cameras.
MAIN = [
 [[936,871],[972,843],[994,790],[1011,715],[1024,615],[1027,515],
  [1020,426],[1007,359],[981,288],[945,223],[898,156],[830,84]],
 [[1073,871],[1096,824],[1113,762],[1123,687],[1126,610],[1125,515],
  [1114,422],[1099,346],[1075,274],[1042,200],[1006,132],[960,67]]
]
OVERHEAD = [
 [[1391,376],[1452,345],[1507,295],[1540,240],[1555,180],
  [1555,125],[1542,85],[1520,55],[1490,40],[1420,38],[1350,36],[1280,35]],
 [[1448,414],[1498,375],[1540,335],[1587,269],[1607,210],
  [1610,155],[1590,92],[1562,50]]
]

def profile(rx, ry, extension, angle, n=350):
    a=np.linspace(0,angle,n)
    xy=np.c_[rx*np.sin(a),ry*(1-np.cos(a))]
    tangent=np.array([rx*np.cos(angle),ry*np.sin(angle)])
    tangent/=np.linalg.norm(tangent)
    xy=np.r_[xy,xy[-1]+np.linspace(.02,extension,100)[:,None]*tangent]
    return np.c_[xy,np.zeros(len(xy))]

def look_rotation(pos, target):
    f=np.array(target)-pos;f=f/np.linalg.norm(f)
    r=np.cross(f,[0,1,0]);r/=np.linalg.norm(r)
    down=np.cross(f,r)
    return Rotation.from_matrix(np.array([r,down,f])).as_rotvec()

def project(p, cam):
    rv=cam[:3];t=cam[3:6];f=np.exp(cam[6])
    q=Rotation.from_rotvec(rv).apply(p)+t
    return q[:,:2]/q[:,2,None]*f+np.array([960.,540.])

def cam_initial(pos,target,f=2500):
    pos=np.array(pos,dtype=float);rv=look_rotation(pos,np.array(target))
    return np.r_[rv,-Rotation.from_rotvec(rv).apply(pos),np.log(f)]

def fit():
    # Shape priors: HUD scale ~21m, 170-degree top pitch, circular transition.
    # Unsurveyed width/extension/ellipse aspect remain regularized assumptions.
    init=np.r_[10.,10.,7.,np.deg2rad(170),3.5,
               cam_initial([-67,3,29],[0,11,0],2500),
               cam_initial([-35,32,42],[0,10,0],1600)]
    # This long-lens aerial view puts the ramp in the upper-right quadrant.
    ov=init[12:19];origin=project(np.zeros((1,3)),ov)[0]
    ov[3]+=(1420-origin[0])*ov[5]/np.exp(ov[6])
    ov[4]+=(395-origin[1])*ov[5]/np.exp(ov[6])
    # Four training correspondences link the otherwise ambiguous cameras.
    # Alternate wide observations12/14/16 remain withheld for validation.
    calibration_wide={10:[1230,52],11:[1121.5,115],13:[895,382],15:[694.5,530.5]}
    observed=json.loads((OUT/'calibration-observations.json').read_text())['mainCarTracks']
    main_uv=PchipInterpolator([a['time']for a in observed],[a['observedCanonicalPx']for a in observed],axis=0)
    frame_manifest=json.loads((OUT/'wide-frames.json').read_text())
    wide_times={int(a['file'][5:7]):a['sourceTime']for a in frame_manifest}
    time_center=np.mean([wide_times[n]for n in calibration_wide])
    init=np.r_[init,29.65,1.0]
    traces=[MAIN,OVERHEAD]
    def residual(v,include_priors=True):
        rx,ry,ext,ang,width=v[:5];p=profile(rx,ry,ext,ang)
        vals=[]
        for j,tr in enumerate(traces):
            cam=v[5+j*7:12+j*7]
            for side,trace in enumerate(tr):
                rail=p.copy();rail[:,2]=(side-.5)*width
                uv=project(rail,cam);tree=cKDTree(uv)
                dist=tree.query(np.array(trace))[0]
                vals.extend(dist/3)
                vals.extend((uv[0]-trace[0])/1.5)
                if j==0 or side==0: vals.extend((uv[-1]-trace[-1])/1.5)
        # The white apron centerline continues the ramp lane on y=0,z=0.
        # Rails alone leave this ground-axis direction ambiguous, materially
        # biasing the landing area. This independent vanishing-direction cue
        # constrains the actual ground plane instead of inventing lateral drift.
        groundline=np.cross([0.,760.,1.],[1280.,430.,1.])
        groundline/=np.linalg.norm(groundline[:2])
        ground_uv=project(np.array([[-40.,0,0],[-10.,0,0],[0.,0,0]]),v[12:19])
        vals.extend((np.c_[ground_uv,np.ones(3)]@groundline)/2.5)
        matrices=[]
        for k in [5,12]:
            c=v[k:k+7];f=np.exp(c[6]);K=np.array([[f,0,960],[0,f,540],[0,0,1.]])
            matrices.append(K@np.c_[Rotation.from_rotvec(c[:3]).as_matrix(),c[3:6]])
        for n,widepoint in calibration_wide.items():
            t=(wide_times[n]-time_center)*v[20]+time_center-v[19]
            mainpoint=main_uv(t)
            pp=cv2.triangulatePoints(matrices[0],matrices[1],mainpoint[:,None],np.array(widepoint,float)[:,None])
            xyz=pp[:3,0]/pp[3,0]
            for mat,ob in zip(matrices,[mainpoint,widepoint]):
                qq=mat@np.r_[xyz,1];vals.extend((qq[:2]/qq[2]-ob)/6)
            vals.append(xyz[2]/2)
        # A visible departure bracket anchors timing; a free affine warp alone
        # must not turn camera/profile error into arbitrary replay speed.
        lip_time=(wide_times[10]-time_center)*v[20]+time_center-v[19]
        vals.extend([(lip_time-8.15)/.20,(v[20]-1)/.15])
        if include_priors:
            height=p[-1,1]
            vals.extend([(height-22.0)/.35,(rx/ry-1)/.1,
                         (width-3.5)/.45,(ext-7)/2.0,
                         (ang-np.deg2rad(170))/np.deg2rad(4)])
            for j in range(2):vals.append((v[11+j*7]-init[11+j*7])/.4)
            main_center=-Rotation.from_rotvec(v[5:8]).inv().apply(v[8:11])
            vals.append((main_center[1]-1.7)/.7)
        return np.array(vals)
    low=np.r_[5,7,2,np.deg2rad(155),2.5,np.full(14,-np.inf),28.5,.7]
    high=np.r_[15,13,15,np.deg2rad(180),5,np.full(14,np.inf),30.5,1.3]
    fit=least_squares(residual,init,bounds=(low,high),max_nfev=1800,
                      loss='linear',x_scale='jac',diff_step=1e-4)
    v=fit.x;p=profile(*v[:4]);r={
      'method':'joint pinhole rail reprojection fit; geometry priors explicitly regularized',
      'shape':{'rx_m':v[0],'ry_m':v[1],'top_extension_m':v[2],
               'arc_end_radians':v[3],'width_m':v[4],'height_m':p[-1,1]},
      'main_camera':v[5:12].tolist(),'overhead_camera':v[12:19].tolist(),
      'camera_parameter_order':['rx_rotvec','ry_rotvec','rz_rotvec','tx','ty','tz','log_focal_px'],
      'main_rails_px':MAIN,'overhead_rails_px':OVERHEAD,
      'overheadGroundCenterline_px':[[0,760],[1280,430]],
      'crossViewCalibration':{'trainingWideIds':list(calibration_wide),'withheldWideIds':[12,14,16],
                              'offsetAtTimeCenter_s':v[19],'rate':v[20],'timeCenter_s':time_center,
                              'formula':'main=(official-timeCenter)*rate+timeCenter-offsetAtTimeCenter',
                              'status':'joint fitted camera/timing calibration; not hardware synchronization'},
      'rms_weighted_residual':float(np.sqrt(np.mean(residual(v)**2))),
      'status':fit.message,'cost':float(fit.cost)}
    errors=[]
    for j,tr in enumerate(traces):
        per=[]
        for side,trace in enumerate(tr):
            rail=p.copy();rail[:,2]=(side-.5)*v[4]
            d=cKDTree(project(rail,v[5+j*7:12+j*7])).query(trace)[0];per.extend(d.tolist())
        errors.append({'view':['main','overhead'][j],'rms_px':float(np.sqrt(np.mean(np.square(per)))),
                       'max_px':max(per),'n_landmarks':len(per)})
    r['rail_reprojection']=errors
    gl=np.cross([0.,760.,1.],[1280.,430.,1.]);gl/=np.linalg.norm(gl[:2])
    guv=project(np.array([[-40.,0,0],[-10.,0,0],[0.,0,0]]),v[12:19])
    r['overheadGroundLineRmsPx']=float(np.sqrt(np.mean((np.c_[guv,np.ones(3)]@gl)**2)))
    (OUT/'geometry-fit.json').write_text(json.dumps(r,indent=2)+'\n')
    for j,name in enumerate(['main','overhead']):
        imagepath=OUT/'frame_14.jpg' if j==0 else OUT/'overhead-32.jpg'
        im=cv2.imread(str(imagepath))
        for side in range(2):
            rail=p.copy();rail[:,2]=(side-.5)*v[4]
            uv=project(rail,v[5+j*7:12+j*7]).astype(np.int32)
            cv2.polylines(im,[uv],False,(0,255,255),2)
            for point in traces[j][side]: cv2.circle(im,point,5,(255,128,0),2)
        if j==1:
            guv=project(np.c_[np.linspace(-80,0,200),np.zeros((200,2))],v[12:19]).astype(np.int32)
            cv2.polylines(im,[guv],False,(0,255,255),2)
            cv2.line(im,(0,760),(1280,430),(255,128,0),1)
        cv2.putText(im,f'MODEL FIT: yellow | observed rail landmarks: blue | {errors[j]["rms_px"]:.1f}px RMS',
                    (40,1030),cv2.FONT_HERSHEY_SIMPLEX,.8,(255,255,255),2)
        cv2.imwrite(str(OUT/f'{name}-geometry-reprojection.jpg'),im)
    print(json.dumps(r,indent=2))
    return r

if __name__=='__main__':fit()
