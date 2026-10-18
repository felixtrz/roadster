"""Reproducible constrained ramp-stunt reconstruction; see the generated README.

Run from any cwd with opencv-python-headless, scipy, numpy, matplotlib, Pillow.
The output is an evidence-constrained replay, not a unique surveyed 6-DoF solve.
"""
from pathlib import Path
import sys, json, hashlib
import cv2
import numpy as np
from scipy.optimize import brentq, minimize_scalar, least_squares
from scipy.interpolate import PchipInterpolator, CubicHermiteSpline, CubicSpline
from scipy.spatial.transform import Rotation, Slerp
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw
from fit_geometry import ROOT, OUT, profile, project, fit

# Human transcription of actual HUD digits at each decoded every-15th frame.
# Source is the main broadcast, NOT the slow-motion replay. See HUD evidence sheet.
HUD_FT=[0,0,0,0,0,.1,.6,2.9,8.7,17.8,27.6,37.5,45.6,52.9,58.7,62.5,
        65.3,67.8,66.6,60.5,39.3,18.7,10.1,7.4,3.8,.9,.4,.6,1.2,.4]
RELEASE=8.15
LAND=12.65
WHEELBASE=2.826421
TRACK=2.10275
BODY_HEIGHT=1.321016/2
# Tight human-initialized body rectangles in original source pixels. CV refines
# the visible silhouette within these boxes; dark underbody and bright plumes
# make a fully unattended detector unreliable. These are NOT 3D keyframes.
AIR_BOXES={16:[833,43,114,114],17:[884,151,92,121],18:[940,392,126,108],
           19:[930,592,145,76],20:[886,751,185,66],21:[828,704,219,68],
           22:[737,650,279,74]}

def decode():
    cap=cv2.VideoCapture(str(ROOT/'references/roadster/media/ramp-main_0708-0726.mp4'))
    fps=cap.get(cv2.CAP_PROP_FPS);frames={};i=0
    while True:
        ok,im=cap.read()
        if not ok:break
        if i%15==0:
            n=i//15;frames[n]=im
            cv2.imwrite(str(OUT/f'frame_{n:02d}.jpg'),im)
        i+=1
    cap.release()
    return frames,15/fps

def register(frames):
    """SIFT + RANSAC homographies on fixed ramp texture, excluding the moving car."""
    base=frames[14];mask=np.zeros(base.shape[:2],np.uint8)
    mask[45:900,790:1170]=255
    mask[170:330,900:1060]=0 # car in template
    sift=cv2.SIFT_create(nfeatures=2200)
    kb,db=sift.detectAndCompute(base,mask);out={}
    for n,im in frames.items():
        if not 2<=n<=22:continue
        k,d=sift.detectAndCompute(im,None)
        pairs=cv2.BFMatcher().knnMatch(d,db,k=2)
        good=[a for a,b in pairs if a.distance<.72*b.distance]
        src=np.array([k[m.queryIdx].pt for m in good],np.float32)
        dst=np.array([kb[m.trainIdx].pt for m in good],np.float32)
        H,inliers=cv2.findHomography(src,dst,cv2.RANSAC,2)
        inliers=inliers[:,0].astype(bool)
        err=np.linalg.norm(cv2.perspectiveTransform(src[:,None],H)[:,0]-dst,axis=1)
        out[n]={'H':H,'inliers':int(inliers.sum()),'matches':len(good),
                'rms_px':float(np.sqrt(np.mean(err[inliers]**2))),
                'median_px':float(np.median(err[inliers]))}
    return out

def main():
    global LAND
    OUT.mkdir(parents=True,exist_ok=True)
    geometry=fit();shape=geometry['shape']
    # Main camera loses the landing inside vapor. The wide shot supplies two
    # later *observed* body positions; their roots land on the calibrated z=0
    # ground within12cm. Keep these distinct from the air calibration points.
    late_pixels={18:[390,650],20:[145,715]}
    wide_manifest=json.loads((OUT/'wide-frames.json').read_text())
    wide_times={int(a['file'][5:7]):a['sourceTime']for a in wide_manifest}
    timing=geometry['crossViewCalibration'];widecam=np.array(geometry['overhead_camera'])
    wide_rotation=Rotation.from_rotvec(widecam[:3]);wide_origin=-wide_rotation.inv().apply(widecam[3:6])
    late=[]
    for n,uv in late_pixels.items():
        t=(wide_times[n]-timing['timeCenter_s'])*timing['rate']+timing['timeCenter_s']-timing['offsetAtTimeCenter_s']
        ray=wide_rotation.inv().apply([(uv[0]-960)/np.exp(widecam[6]),(uv[1]-540)/np.exp(widecam[6]),1])
        body=wide_origin-ray*wide_origin[2]/ray[2]
        late.append({'wideImage':f'wide_{n:02d}.jpg','mainTime':t,'sourcePixel':uv,
                     'conditionalBodyPoint':body.tolist(),'rootHeightBeforeGroundConstraint':float(body[1]-BODY_HEIGHT)})
    LAND=float(late[0]['mainTime']-.05)
    p=profile(shape['rx_m'],shape['ry_m'],shape['top_extension_m'],shape['arc_end_radians'],1500)
    ds=np.linalg.norm(np.diff(p,axis=0),axis=1);s=np.r_[0,np.cumsum(ds)];end=s[-1]
    along=PchipInterpolator(s,p,axis=0)
    start_tangent=np.array([1.,0,0]);top_tangent=p[-1]-p[-2];top_tangent/=np.linalg.norm(top_tangent)
    def point(a):
        if a<0:return np.array([a,0.,0.])
        if a>end:return p[-1]+top_tangent*(a-end)
        return along(a)
    def contact(a):
        # Front/rear axle chord solves contact on the deck rather than imposing
        # the local tangent and accepting tire penetration on a curved surface.
        d=brentq(lambda h:np.linalg.norm(point(a+h)-point(a-h))-WHEELBASE,WHEELBASE/2-.01,WHEELBASE/2+.8)
        front=point(a+d);rear=point(a-d);root=(front+rear)*.5
        tangent=(front-rear)/WHEELBASE
        pitch=np.arctan2(tangent[1],tangent[0]);rot=Rotation.from_euler('z',pitch)
        return root,rot,d
    metric=np.linspace(.02,end+WHEELBASE/2,2000)
    hud_pred=np.array([contact(a)[0][1]+contact(a)[1].apply([0,BODY_HEIGHT,0])[1]-BODY_HEIGHT for a in metric])
    # Use the observed altitude displacement to recover progress while attached.
    # The authored-model half-height reference is explicit because Tesla does not specify
    # the sensor datum; it is not interpreted as exact tire clearance.
    keep=np.r_[True,np.diff(hud_pred)>1e-7]
    altitude_to_s=PchipInterpolator(hud_pred[keep],metric[keep],extrapolate=True)
    frames,dt=decode();regs=register(frames);cam=np.array(geometry['main_camera'])
    hud_times=np.arange(len(HUD_FT))*dt
    altitude=PchipInterpolator(hud_times,np.array(HUD_FT)*.3048)
    s_release=end+WHEELBASE/2
    release_root,release_rot,_=contact(s_release)
    # A single release interval brackets the partially supported body in the
    # broadcast; end-wheel detachment is not inferred from smoke or replay speed.
    s_keys=[]
    for t in hud_times:
        if 2.5<=t<=8.01:s_keys.append([t,float(altitude_to_s(altitude(t)))])
    # Preserve all HUD-derived progress values, then reach the lip continuously.
    sk=np.array([[0,-6],[1.5,-6],[2,-4.7],[2.3,-3.2]]+s_keys+[[RELEASE,s_release]])
    progress=PchipInterpolator(sk[:,0],sk[:,1])
    landing_rot=Rotation.from_euler('y',np.pi)
    orientation=Slerp([0,1],Rotation.concatenate([release_rot,landing_rot]))
    def rotation(t):
        if t<=RELEASE:return contact(float(progress(t)))[1]
        u=float(np.clip((t-RELEASE)/(9.95-RELEASE),0,1))
        ease=u*u*u*(10+u*(-15+6*u))
        return orientation(ease)
    # Median static background in the stabilized reference camera.
    warped={n:cv2.warpPerspective(frames[n],r['H'],(1920,1080)) for n,r in regs.items()}
    background=np.median(np.stack(list(warped.values())),axis=0).astype(np.uint8)
    tracks=[];debug=[]
    for n in range(6,23):
        t=n*dt;rot=rotation(t)
        if t<=RELEASE:root=contact(float(progress(t)))[0]
        else:root=np.array([release_root[0]-(t-RELEASE)*13, float(altitude(t))+BODY_HEIGHT-rot.apply([0,BODY_HEIGHT,0])[1],0])
        pred=project(np.array([root+rot.apply([0,BODY_HEIGHT,0])]),cam)[0]
        im=warped[n];gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
        diff=cv2.cvtColor(cv2.absdiff(im,background),cv2.COLOR_BGR2GRAY)
        # Moving silhouette on gray deck, then compact neutral body in the sky.
        r=120 if t>RELEASE else 85
        x0=max(0,int(pred[0]-r));x1=min(1920,int(pred[0]+r));y0=max(0,int(pred[1]-75));y1=min(900,int(pred[1]+75))
        binary=(diff>26).astype(np.uint8)*255
        roi=np.zeros_like(binary);roi[y0:y1,x0:x1]=255;binary&=roi
        debug.append({'frame':n,'pred':pred.tolist(),'roi':[x0,y0,x1,y1]})
        di=im.copy();cv2.rectangle(di,(x0,y0),(x1,y1),(0,255,255),2)
        cv2.imwrite(str(OUT/f'tracking-search-{n:02d}.jpg'),di)
        binary=cv2.morphologyEx(binary,cv2.MORPH_CLOSE,np.ones((5,5),np.uint8))
        cnts,_=cv2.findContours(binary,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        choices=[]
        for c in cnts:
            x,y,w,h=cv2.boundingRect(c);area=cv2.contourArea(c)
            if area<120 or w>180 or h>130:continue
            center=np.array([x+w*.5,y+h*.5]);score=area/(1+np.linalg.norm(center-pred)/60)
            choices.append((score,center,[x,y,w,h]))
        if n in AIR_BOXES:
            # Original-view silhouette avoids clipping a foreground car when the
            # stabilized virtual camera moves it outside its 1920-pixel canvas.
            x,y,w,h=AIR_BOXES[n];raw=frames[n][y:y+h,x:x+w]
            bright=(cv2.cvtColor(raw,cv2.COLOR_BGR2GRAY)>38).astype(np.uint8)*255
            yy,xx=np.where(bright>0)
            if len(xx):
                bx,by,bw,bh=int(xx.min()),int(yy.min()),int(xx.max()-xx.min()+1),int(yy.max()-yy.min()+1)
                original_center=np.array([x+bx+bw/2,y+by+bh/2])
            else:original_center=np.array([x+w/2,y+h/2])
            center=cv2.perspectiveTransform(original_center[None,None].astype(np.float32),regs[n]['H'])[0,0]
            bbox=AIR_BOXES[n]
        else:
            if not choices:continue
            _,center,bbox=max(choices,key=lambda x:x[0])
        record={'frame':n,'time':t,'observedCanonicalPx':center.tolist(),'predictedPx':pred.tolist(),
                'bbox':bbox,'method':'SIFT/RANSAC camera registration + human-initialized brightness silhouette' if n in AIR_BOXES else 'SIFT camera registration + median-background canopy segmentation',
                'reprojectionPx':float(np.linalg.norm(center-pred)),
                'visibility':'visible' if n<=21 else 'partially_occluded'}
        tracks.append(record)
    # Fit attached progress to actual car image positions. HUD established the
    # metric height prior; it does not get to override visible movement timing.
    refined=[]
    for tr in tracks:
        if tr['time']>7.52:continue
        observed=np.array(tr['observedCanonicalPx'])
        guess=float(progress(tr['time']))
        def error(a):
            root,rot,_=contact(a)
            uv=project(np.array([root+rot.apply([0,BODY_HEIGHT,0])]),cam)[0]
            return np.sum((uv-observed)**2)
        result=minimize_scalar(error,bounds=(max(-1,guess-5),min(end+1.35,guess+5)),method='bounded')
        refined.append([tr['time'],float(result.x)])
    refined=np.array(refined);refined[:,1]=np.maximum.accumulate(refined[:,1])
    progress_keys=np.r_[[[0,-6],[1.5,-6],[2,-4.7],[2.3,-3.2]],refined,[[RELEASE,s_release]]]
    shape_progress=PchipInterpolator(progress_keys[:,0],progress_keys[:,1])
    progress_velocity=shape_progress.derivative()(progress_keys[:,0])
    # Source pixel proxies around partial support are not allowed to make the car
    # stop at the lip. One shared boundary speed owns both the attached Hermite
    # progress curve and the airborne spline. 10m/s is a regularized boundary
    # estimate consistent with the preceding half-second observed travel.
    progress_velocity[-1]=10.0
    progress=CubicHermiteSpline(progress_keys[:,0],progress_keys[:,1],progress_velocity)
    moving_keys=progress_keys[1:]
    mt=moving_keys[:,0];ms=moving_keys[:,1]
    regularization_times=np.linspace(1.5,RELEASE,180)
    def progress_curve(values):
        return CubicSpline(mt,np.r_[ms[0],values,ms[-1]],bc_type=((1,0),(1,10)))
    def progress_residual(values):
        curve=progress_curve(values);acceleration=curve(regularization_times,2)
        return np.r_[(values-ms[1:-1])/.45,
                      np.maximum(np.abs(acceleration)-8,0)/2,
                      acceleration/60,
                      np.diff(acceleration)/3,
                      np.maximum(-curve(regularization_times,1),0)*3]
    progress_optimization=least_squares(progress_residual,ms[1:-1],max_nfev=200)
    smooth_progress=progress_curve(progress_optimization.x)
    def progress(t):return smooth_progress(np.maximum(t,1.5))
    # Airborne position is a camera-ray intersection with z=0. The static ramp
    # fit supplies the camera. This uses *both* observed pixel coordinates and
    # does not trust the visibly delayed broadcast altitude during rapid descent.
    camera_rotation=Rotation.from_rotvec(cam[:3]);camera_origin=-camera_rotation.inv().apply(cam[3:6])
    airborne=[]
    for track in tracks:
        t=track['time']
        if t<=RELEASE:continue
        rot=rotation(t);up=rot.apply([0,BODY_HEIGHT,0])
        observed=np.array(track['observedCanonicalPx'])
        ray=camera_rotation.inv().apply([(observed[0]-960)/np.exp(cam[6]),(observed[1]-540)/np.exp(cam[6]),1])
        body=camera_origin+ray*(up[2]-camera_origin[2])/ray[2]
        root=body-up
        # The plane constraint belongs to the body reference; keep the root on
        # that same canonical plane, with the small roll offset absorbed in its
        # stated lateral uncertainty.
        root[2]=0
        airborne.append([t,float(root[0]),float(root[1])])
    (OUT/'tracking-debug.json').write_text(json.dumps({'debug':debug,'tracks':tracks},indent=2))
    if len(airborne)<3:raise RuntimeError('Airborne tracking failed: inspect segmentation overlays')
    ar=np.array(airborne)
    last_speed=float((late[1]['conditionalBodyPoint'][0]-late[0]['conditionalBodyPoint'][0])/(late[1]['mainTime']-late[0]['mainTime']))
    epsilon=.0001
    r0=contact(float(progress(RELEASE-epsilon)))[0]
    shared_velocity=(release_root-r0)/epsilon
    # Joint airborne fit uses the actual main-view pixel observations plus weak
    # acceleration/jerk penalties. Boundary position AND velocity are shared with
    # ramp contact; independently joined PCHIPs would spuriously stop at the lip.
    late_t=np.array([x['mainTime']for x in late]);late_x=np.array([x['conditionalBodyPoint'][0]for x in late])
    xt=np.r_[RELEASE,ar[:,0],late_t,18];yt=np.r_[RELEASE,ar[:,0],LAND]
    target_tracks=[x for x in tracks if x['time']>RELEASE]
    acceleration_times=np.linspace(RELEASE,LAND,180)
    def splines(values):
        xs=values[:len(ar)];ys=values[len(ar):]
        xx=np.r_[release_root[0],xs,late_x,late_x[-1]+last_speed*(18-late_t[-1])]
        yy=np.r_[release_root[1],ys,0]
        return (CubicSpline(xt,xx,bc_type=((1,shared_velocity[0]),(1,last_speed))),
                CubicSpline(yt,yy,bc_type=((1,shared_velocity[1]),(1,0))))
    def fit_residual(values):
        sx,sy=splines(values);res=[]
        for track in target_tracks:
            t=track['time'];rot=rotation(t)
            body=np.array([float(sx(t)),float(sy(t)),0])+rot.apply([0,BODY_HEIGHT,0])
            uv=project(body[None],cam)[0];res.extend((uv-track['observedCanonicalPx'])/12)
        acceleration=np.c_[sx(acceleration_times,2),sy(acceleration_times,2)]
        mag=np.linalg.norm(acceleration,axis=1)
        res.extend(np.maximum(mag-35,0)/4)
        res.extend((acceleration/140).ravel())
        res.extend((np.diff(acceleration,axis=0)/15).ravel())
        res.extend(np.maximum(sx(acceleration_times,1)+1,0)/2)
        res.extend(np.maximum(-sy(acceleration_times),0)*8)
        return np.array(res)
    optimization=least_squares(fit_residual,np.r_[ar[:,1],ar[:,2]],max_nfev=600)
    air_x,air_y=splines(optimization.x)
    last_air_time=float(ar[-1,0])
    samples=[];contact_errors=[]
    for t in np.linspace(0,18,1081):
        rot=rotation(t)
        if t<=RELEASE:
            a=float(progress(t));root,rot,d=contact(a)
            phase='ready' if t<1.5 else ('approach' if a<0 else ('climb' if a+d<=end else 'release'))
            if t<8.0:
                f=point(a+d);r=point(a-d)
                for x,expected in [(WHEELBASE/2,f),(-WHEELBASE/2,r)]:
                    actual=root+rot.apply([x,0,0]);contact_errors.append(float(np.linalg.norm(actual-expected)))
            provenance='registered canopy/silhouette timing + fitted ramp chord-contact constraint'
            confxy=.8;confori=.84
        else:
            height=float(air_y(t)) if t<LAND else 0
            root=np.array([float(air_x(t)),height,0])
            if t>=LAND:root[1]=0
            phase='reorient' if t<9.95 else ('descent' if t<LAND-.4 else ('landing' if t<LAND+.3 else 'drive-away'))
            provenance='CV pixel fit conditional on z=0, shared release velocity and acceleration regularization; inferred quaternion' if t<last_air_time else 'wide-camera observed ground positions with fitted replay-time mapping; smoothed contact continuation'
            confxy=.67 if t<11.5 else .43;confori=.5
            if t>late_t[-1]:
                provenance='constant-speed extrapolation after final wide-camera ground observation; not recovered motion'
                confxy=.30
        visible='visible' if t<11.4 or t>13.2 else 'occluded_or_partial'
        attitude=float(np.interp(t,[0,8.25,8.40,8.85,9.5,9.9,18],[0,0,.8,1,.7,0,0]))
        lift=float(np.interp(t,[0,9.05,9.35,9.85,10.55,11.3,LAND+.3,18],[0,0,.2,.85,1,.55,0,0]))
        samples.append({'time':round(float(t),6),'position':np.round(root,6).tolist(),
                        'quaternion':np.round(rot.as_quat(),8).tolist(),'phase':phase,
                        'thrusters':{'attitude':round(attitude,4),'lift':round(lift,4)},
                        'confidence':{'positionXY':confxy,'positionZ':.25,'orientation':confori,
                                      'visibility':visible,'provenance':provenance}})
    # Compute in-sample pixel consistency after fitting; this is not independent
    # metric3D validation. The held-out wide checks are written separately.
    for tr in tracks:
        idx=int(round(tr['time']*60));sample=samples[min(idx,len(samples)-1)]
        root=np.array(sample['position']);rot=Rotation.from_quat(sample['quaternion'])
        uv=project(np.array([root+rot.apply([0,BODY_HEIGHT,0])]),cam)[0]
        tr['fittedCanonicalPx']=uv.tolist();tr['finalReprojectionPx']=float(np.linalg.norm(uv-tr['observedCanonicalPx']))
    rms=float(np.sqrt(np.mean([t['finalReprojectionPx']**2 for t in tracks])))
    delivered_centerline=np.r_[p[::5],p[-1][None]]
    # Numerical checks are against the exact delivered polyline and 60Hz track.
    # A continuous-profile algebraic contact error alone would be uninformative.
    segment_a=delivered_centerline[:-1,:2];segment_v=np.diff(delivered_centerline[:,:2],axis=0)
    segment_l2=np.sum(segment_v**2,axis=1)
    polyline_contact=[]
    for sample in samples:
        if sample['time']<2.6 or sample['time']>7.85:continue
        root=np.array(sample['position']);rot=Rotation.from_quat(sample['quaternion'])
        for localx in [-WHEELBASE/2,WHEELBASE/2]:
            point_xy=(root+rot.apply([localx,0,0]))[:2]
            if point_xy[1]<.001:continue
            tau=np.clip(np.sum((point_xy-segment_a)*segment_v,axis=1)/np.maximum(segment_l2,1e-12),0,1)
            nearest=segment_a+tau[:,None]*segment_v
            polyline_contact.append(float(np.min(np.linalg.norm(nearest-point_xy,axis=1))))
    vv=np.diff(np.array([s['position']for s in samples]),axis=0)*60
    aa=np.diff(vv,axis=0)*60
    acceleration_magnitude=np.linalg.norm(aa,axis=1)
    rr=Rotation.from_quat([s['quaternion']for s in samples])
    angular_velocity=(rr[1:]*rr[:-1].inv()).as_rotvec()*60
    angular_acceleration=np.diff(angular_velocity,axis=0)*60
    release_index=int(round(RELEASE*60))
    motion_checks={'finite':bool(np.isfinite(vv).all() and np.isfinite(aa).all()),
                   'maxSpeed_mps':float(np.linalg.norm(vv,axis=1).max()),
                   'maxAcceleration_mps2':float(acceleration_magnitude.max()),
                   'maxAccelerationTime_s':float(samples[int(acceleration_magnitude.argmax())+1]['time']),
                   'releaseSharedAnalyticVelocity_mps':shared_velocity.tolist(),
                   'releaseFiniteDifferenceVelocityBefore_mps':vv[release_index-1].tolist(),
                   'releaseFiniteDifferenceVelocityAfter_mps':vv[release_index].tolist(),
                   'maxAirAcceleration_mps2':float(acceleration_magnitude[release_index:].max()),
                   'maxAngularSpeed_rps':float(np.linalg.norm(angular_velocity,axis=1).max()),
                   'maxAngularAcceleration_rps2':float(np.linalg.norm(angular_acceleration,axis=1).max()),
                   'status':'regularized replay kinematics; no force or vehicle capability measurement'}
    # Quantify the material depth-plane ambiguity with the same actual observed
    # source pixel, changing only its assumed world z plane by±2m.
    sensitivity_track=min(tracks,key=lambda x:abs(x['time']-9.009))
    sensitivity_up=rotation(sensitivity_track['time']).apply([0,BODY_HEIGHT,0])
    suv=np.array(sensitivity_track['observedCanonicalPx'])
    sray=camera_rotation.inv().apply([(suv[0]-960)/np.exp(cam[6]),(suv[1]-540)/np.exp(cam[6]),1])
    sensitivity=[]
    for plane_z in [-2.,0.,2.]:
        body=camera_origin+sray*(plane_z+sensitivity_up[2]-camera_origin[2])/sray[2]
        sensitivity.append({'assumedRootZ':plane_z,'conditionalRootXYZ':(body-sensitivity_up).tolist()})
    full_contact_end=next(s['time']for s in samples if s['phase']=='release')
    data={
      'schemaVersion':1,'duration':18,'timeOrigin':{'eventSeconds':428,'sourceClip':'ramp-main_0708-0726.mp4'},
      'reconstructionStatus':{'kind':'evidence-constrained approximate replay, not unique metric 6-DoF recovery',
                              'metricScale':'HUD-based22m ramp-height prior chooses otherwise ambiguous global scale',
                              'airPosition':'registered main-view silhouette fit conditional on world z=0',
                              'airOrientation':'inferred eased quaternion interpolation between inversion and wheels-down endpoints',
                              'thrusters':'authored0–1 visual envelopes from observed plume phases; not force measurements',
                              'editedReplayTiming':'fitted affine nuisance parameter on air window only; early-climb mismatch retained'},
      'coordinateSystem':{'units':'metres','handedness':'right','forward':'+X','up':'+Y','right':'+Z','quaternionOrder':'xyzw'},
      'car':{'length':4.666,'width':2.393876,'height':1.321016,'wheelbase':WHEELBASE,'track':TRACK,'wheelRadius':.353,
             'wheelRadiusFront':.3483,'wheelRadiusRear':.3577,
             'origin':'midpoint of four nominal tire-contact points; ground y=0',
             'bodyReferenceOffset':[0,BODY_HEIGHT,0],'dimensionsStatus':'measured from length-normalized generated Tripo model; not surveyed vehicle'},
      'ramp':{'centerline':np.round(delivered_centerline,6).tolist(),
              'width':shape['width_m'],'height':shape['height_m'],'topExtension':shape['top_extension_m'],
              'construction':'elliptical half-loop followed by tangent overhang',
              'fitStatus':'regularized two-view inverse-rendered geometry; not survey',
              'source':'geometry-fit.json'},
      'events':{'movementStart':1.5,'fullWheelContactEnds':full_contact_end,'lastWheelDetachmentEstimate':RELEASE,
                'upright':9.95,'landingInterval':[LAND-.3,LAND+.3],'nominalTouchdown':LAND,
                'groundExtrapolationStarts':float(late_t[-1])},
      'uncertainty':{'rampHeight_m':1.0,'rampWidth_m':.7,'rampTopExtension_m':2.5,
                     'airPositionX_m':5.0,'airPositionY_m':2.0,'airPositionZ_m':2.0,
                     'airOrientation_degrees':25,'nominalTouchdown_s':.5,
                     'kind':'plausible modeling ranges, not statistical confidence intervals'},
      'depthPlaneSensitivity':{'mainTime':sensitivity_track['time'],'method':'same observed pixel ray, varying assumed root z plane; conditional on fitted camera',
                               'samples':sensitivity},
      'validation':{'railReprojection':geometry['rail_reprojection'],'carCenterRmsPx':rms,
                    'carCenterRmsMeaning':'in-sample 2D fit consistency; not independent metric 3D accuracy',
                    'maxModelWheelContactError_m':max(polyline_contact),
                    'continuousProfileContactError_m':max(contact_errors),
                    'contactErrorMeaning':'distance to delivered fitted-deck polyline for assumed wheelbase; excludes physical tire/deck uncertainty',
                    'motion':motion_checks},
      'samples':samples}
    (OUT/'reconstruction.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    (OUT/'observations.json').write_text(json.dumps({'fps':15/dt,'sourceEveryFrames':15,
        'hud':{'units':'feet','timeStep':dt,'values':HUD_FT,'method':'manually transcribed; see main-dense-sheet.jpg'},
        'registration':{n:{**{k:v for k,v in r.items() if k!='H'},'H_to_frame14':r['H'].tolist()} for n,r in regs.items()},
        'carTracks':tracks,'airborneXYConditionalOnZ0':airborne,'wideGroundTrajectoryInputs':late},indent=2)+'\n')
    # Overlay evidence in stabilized camera; cyan observed, yellow reconstructed.
    sheet=Image.new('RGB',(1600,1650))
    for i,tr in enumerate(tracks):
        n=tr['frame'];im=warped[n].copy()
        cv2.circle(im,tuple(np.int32(tr['observedCanonicalPx'])),10,(255,255,0),2)
        cv2.drawMarker(im,tuple(np.int32(tr['fittedCanonicalPx'])),(0,255,255),cv2.MARKER_CROSS,24,2)
        cv2.putText(im,f't={tr["time"]:.3f}s residual={tr["finalReprojectionPx"]:.1f}px',(40,60),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255),2)
        cv2.imwrite(str(OUT/f'pose-overlay-{n:02d}.jpg'),im)
        thumb=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB));thumb.thumbnail((400,270))
        sheet.paste(thumb,((i%4)*400,(i//4)*300))
    sheet.save(OUT/'pose-reprojection-sheet.jpg')
    arr=np.array([x['position'] for x in samples]);ts=np.array([x['time'] for x in samples])
    fig,axes=plt.subplots(2,2,figsize=(13,9))
    axes[0,0].plot(p[:,0],p[:,1],label='fitted deck');axes[0,0].plot(arr[:,0],arr[:,1],label='car contact-root path');axes[0,0].set_aspect('equal');axes[0,0].legend();axes[0,0].set(xlabel='World X (m)',ylabel='World Y (m)',title='Constrained vertical-plane reconstruction')
    axes[0,1].plot(ts,arr[:,1],label='contact root height');axes[0,1].scatter(hud_times,np.array(HUD_FT)*.3048,s=12,label='broadcast HUD displacement');axes[0,1].legend();axes[0,1].set(xlabel='Main-clip seconds',ylabel='m',title='HUD datum is not tire clearance')
    axes[1,0].plot([t['time'] for t in tracks],[t['finalReprojectionPx'] for t in tracks],'o-');axes[1,0].set(xlabel='Main-clip seconds',ylabel='Pixel residual',title=f'Car center validation, RMS {rms:.1f}px')
    axes[1,1].plot(ts,arr[:,2]);axes[1,1].fill_between(ts,-2,2,alpha=.2);axes[1,1].set(xlabel='Main-clip seconds',ylabel='World Z (m)',title='Lateral depth constrained to 0, plausible ±2m')
    fig.tight_layout();fig.savefig(OUT/'reconstruction-plots.png',dpi=170);plt.close(fig)
    print(json.dumps({'path':str(OUT/'reconstruction.json'),'ramp':shape,'carCenterRmsPx':rms,'nTracks':len(tracks),'nSamples':len(samples),'wheelContactError':max(contact_errors)},indent=2))

if __name__=='__main__':main()
