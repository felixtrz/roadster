"""Held-out wide-view checks of a constrained camera/timing reconstruction.

Geometry calibration uses body IDs10/11/13/15; the trajectory uses ground
IDs18/20. IDs12/14/16/17/19 are excluded from those numerical objectives.
Camera/timing parameters stay frozen here; additional timing fits are retained
only as sensitivity diagnostics. No unique metric6-DoF ground truth is claimed.
"""
import json
import cv2
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import minimize_scalar,least_squares
from scipy.spatial.transform import Rotation
from PIL import Image,ImageDraw
from fit_geometry import OUT,project

# Body-center proxies from the new official wide shot. Four are calibration
# inputs; alternate observations are reserved for the explicitly flagged checks.
WIDE={10:[1230,52],11:[1121.5,115],12:[1002,236.5],13:[895,382],
      14:[797,490],15:[694.5,530.5],16:[586.5,569]}
LATE={18:[390,650],20:[145,715]}
LATE_WITHHELD={17:[486,624],19:[298,681]}
EARLY={1:[1527,294],4:[1571,142],6:[1536,71]}

def main():
    data=json.loads((OUT/'reconstruction.json').read_text())
    geo=json.loads((OUT/'geometry-fit.json').read_text())
    obs=json.loads((OUT/'observations.json').read_text())
    arr=data['samples'];times=np.array([x['time'] for x in arr]);positions=np.array([x['position'] for x in arr])
    rots=Rotation.from_quat([x['quaternion'] for x in arr]);body=positions+rots.apply(np.tile(data['car']['bodyReferenceOffset'],(len(arr),1)))
    cam=np.array(geo['overhead_camera']);uv=project(body,cam);inter=PchipInterpolator(times,uv,axis=0)
    # Exact source timestamps recovered by matching extracted JPEGs to decoded
    # official clip frames, not trusting the nominal -ss/fps output labels.
    # first JPEG = source frame797; subsequent images advance12 source frames.
    manifest=json.loads((OUT/'wide-frames.json').read_text())
    pts={int(x['file'][5:7]):x['sourceTime']for x in manifest}
    frameids={int(x['file'][5:7]):x['sourceFrame']for x in manifest}
    def residual(offset):
        return np.array([inter(pts[n]-offset)-point for n,point in WIDE.items()])
    result=minimize_scalar(lambda off:np.mean(residual(off)**2),bounds=(28.5,30.5),method='bounded')
    offset=float(result.x)
    calibration=geo.get('crossViewCalibration')
    def main_time(wide_time):
        if calibration:
            return (wide_time-calibration['timeCenter_s'])*calibration['rate']+calibration['timeCenter_s']-calibration['offsetAtTimeCenter_s']
        return wide_time-offset
    allpoints=dict(sorted({**WIDE,**LATE,**LATE_WITHHELD}.items()))
    withheld=[n for n in allpoints if n not in calibration['trainingWideIds'] and n not in LATE]
    errs=np.array([np.linalg.norm(inter(main_time(pts[n]))-allpoints[n])for n in withheld])
    # Offset sensitivity: profiles within +10% RMS are descriptive fit ranges,
    # not hardware-synchronization or statistical confidence intervals.
    grid=np.linspace(offset-.5,offset+.5,1001);rms=np.array([np.sqrt(np.mean(np.sum(residual(t)**2,axis=1)))for t in grid]);good=grid[rms<=rms.min()*1.1]
    matrices=[]
    for name in ['main_camera','overhead_camera']:
        c=np.array(geo[name]);f=np.exp(c[6]);K=np.array([[f,0,960],[0,f,540],[0,0,1.]])
        matrices.append(K@np.c_[Rotation.from_rotvec(c[:3]).as_matrix(),c[3:6]])
    tr=obs['carTracks'];mt=np.array([x['time'] for x in tr]);mu=np.array([x['observedCanonicalPx']for x in tr]);mainobs=PchipInterpolator(mt,mu,axis=0)
    stereo=[];samples=[];sheet=Image.new('RGB',(1600,1600))
    for i,(n,point) in enumerate(allpoints.items()):
        t=main_time(pts[n]);pred=inter(t)
        if mt[0]<=t<=mt[-1]:
            uvm=mainobs(t)
            raw=cv2.triangulatePoints(matrices[0],matrices[1],uvm[:,None],np.array(point,float)[:,None]);xyz=raw[:3,0]/raw[3,0]
            repro=[]
            for P,observed in zip(matrices,[uvm,point]):
                q=P@np.r_[xyz,1];repro.append(float(np.linalg.norm(q[:2]/q[2]-observed)))
            stereo.append({'mainTime':t,'officialTime':pts[n],'bodyPoint':xyz.tolist(),'reprojectionPx':repro})
        samples.append({'wideImage':f'wide_{n:02d}.jpg','officialTime':pts[n],'sourceFrame':frameids[n],
                        'mainTime':t,'observedPx':point,'predictedPx':pred.tolist(),'residualPx':float(np.linalg.norm(pred-point)),
                        'usedToFitCameraAndTiming':n in calibration['trainingWideIds'],
                        'usedToFitGroundTrajectory':n in LATE,
                        'observationMethod':('manual cloud-obscured body-center proxy, about±20px initialization uncertainty' if n in LATE_WITHHELD else 'manual body-silhouette center, about±8px initialization uncertainty; systematic viewpoint error may be larger')})
        im=cv2.imread(str(OUT/f'wide_{n:02d}.jpg'));cv2.circle(im,tuple(np.int32(point)),12,(255,255,0),2);cv2.drawMarker(im,tuple(np.int32(pred)),(0,255,255),cv2.MARKER_CROSS,28,2)
        cv2.line(im,tuple(np.int32(point)),tuple(np.int32(pred)),(0,180,255),2)
        cv2.putText(im,f'wide {pts[n]:.3f}s -> main {t:.3f}s | residual {np.linalg.norm(pred-point):.1f}px',(40,1020),cv2.FONT_HERSHEY_SIMPLEX,.9,(255,255,255),2)
        cv2.imwrite(str(OUT/f'wide-validation-{n:02d}.jpg'),im)
        th=Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB));th.thumbnail((533,300));sheet.paste(th,((i%3)*533,(i//3)*400))
    sheet.save(OUT/'wide-independent-validation-sheet.jpg')
    lag_times=np.array([x[0] for x in obs['airborneXYConditionalOnZ0']]);modelheight=np.array([x[2]+data['car']['bodyReferenceOffset'][1] for x in obs['airborneXYConditionalOnZ0']]);hud=obs['hud'];ht=np.arange(len(hud['values']))*hud['timeStep'];hfun=PchipInterpolator(ht,np.array(hud['values'])*.3048+data['car']['bodyReferenceOffset'][1])
    fitlag=minimize_scalar(lambda lag:np.mean((hfun(lag_times+lag)-modelheight)**2),bounds=(0,1.2),method='bounded')
    center=np.mean([pts[n]for n in WIDE])
    def affine_error(v):
        return np.array([inter((pts[n]-center)*v[1]+center-v[0])-point for n,point in WIDE.items()]).ravel()
    affine=least_squares(affine_error,[offset,1.0],bounds=([offset-.6,.8],[offset+.6,1.2]))
    check={
      'method':'camera/timing calibration on10/11/13/15; ground trajectory uses18/20; alternate12/14/16/17/19 withheld',
      'wideSource':'tesla-the-ramp.source.json','mainSource':'../source-metadata.json',
      'sync':{'appliedJointCalibration':calibration,
              'fixedRate1DiagnosticOffset_s':offset,'speedRatio':calibration['rate'],
              'fixedRate1OffsetRangeWithin10PercentRms_s':[float(good.min()),float(good.max())],
              'status':'visual/model alignment, not timecode synchronization',
              'timestampRecovery':'each JPEG matched to a decoded official source-frame; see wide-frames.json',
              'affineSensitivity':{'rate':float(affine.x[1]),'offsetAtMeanTime':float(affine.x[0]),
                                     'rmsPx':float(np.sqrt(np.mean(np.sum(affine.fun.reshape(-1,2)**2,axis=1)))),
                                     'status':'diagnostic only; camera/path/proxy bias can mimic a speed change'}},
      'rmsPx':float(np.sqrt(np.mean(errs**2))),'maxPx':float(errs.max()),'nWithheldPoints':len(withheld),
      'withheldWideIds':withheld,'calibrationTrainingWideIds':calibration['trainingWideIds'],
      'groundTrajectoryTrainingWideIds':list(LATE),
      'timingFitPointCount':len(calibration['trainingWideIds']),'latePointsExcludedFromTimingFit':len(LATE),
      'samples':samples,'stereoDiagnostics':stereo,
      'stereoLateralZ_m':{'min':float(min(x['bodyPoint'][2]for x in stereo)),
                           'max':float(max(x['bodyPoint'][2]for x in stereo)),
                           'median':float(np.median([x['bodyPoint'][2]for x in stereo]))},
      'hudLatencyDiagnostic':{'fittedDelay_s':float(fitlag.x),
                              'uncorrectedRms_m':float(np.sqrt(np.mean((hfun(lag_times)-modelheight)**2))),
                              'lagAdjustedRms_m':float(np.sqrt(fitlag.fun)),
                              'status':'descriptive discrepancy; camera/plane/datum errors also contribute, not proof of actual telemetry delay'}}
    early=[]
    for n,point in EARLY.items():
        mapped=main_time(pts[n]);estimate=minimize_scalar(lambda t:np.sum((inter(t)-point)**2),bounds=(2.5,8.15),method='bounded')
        early.append({'wideImage':f'wide_{n:02d}.jpg','sourceTime':pts[n],'observedPx':point,
                      'airWindowAffineMappedMainTime':mapped,'mappedResidualPx':float(np.linalg.norm(inter(mapped)-point)),
                      'nearestRampPathMainTime':float(estimate.x),'nearestPathResidualPx':float(np.sqrt(estimate.fun)),
                      'status':'diagnostic only; affine air-window mapping does not establish timing throughout edited replay'})
    check['earlyClimbTimingDiagnostics']=early
    check['sync']['scope']='calibrated on air-window source37.75–40.25s; early climb affine mismatch is retained, not hidden'
    (OUT/'independent-validation.json').write_text(json.dumps(check,indent=2)+'\n')
    data['validation']['withheldWideView']={k:check[k]for k in ['rmsPx','maxPx','nWithheldPoints']}
    data['validation']['withheldWideView']['sync']=calibration
    (OUT/'reconstruction.json').write_text(json.dumps(data,separators=(',',':'))+'\n')
    print(json.dumps({k:check[k]for k in ['sync','rmsPx','maxPx','stereoLateralZ_m','hudLatencyDiagnostic']},indent=2))

if __name__=='__main__':main()
