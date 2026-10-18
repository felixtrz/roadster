"""Meaningful data QA for the delivered replay; does not mutate its JSON."""
import hashlib,json
import numpy as np
from pathlib import Path
from fit_geometry import OUT

def main():
    payload=(OUT/'reconstruction.json').read_bytes();d=json.loads(payload)
    p=np.array([s['position']for s in d['samples']]);q=np.array([s['quaternion']for s in d['samples']]);t=np.array([s['time']for s in d['samples']])
    v=np.diff(p,axis=0)*60;a=np.diff(v,axis=0)*60
    release=int(round(d['events']['lastWheelDetachmentEstimate']*60))
    tests={
      '1081_samples':len(t)==1081,
      '60hz_timestamps':bool(np.max(np.abs(np.diff(t)-1/60))<1e-6),
      'finite_pose_velocity_acceleration':bool(np.isfinite(p).all() and np.isfinite(q).all() and np.isfinite(v).all() and np.isfinite(a).all()),
      'unit_quaternions':bool(np.max(np.abs(np.linalg.norm(q,axis=1)-1))<1e-7),
      'no_quaternion_sign_flips':bool(np.min(np.sum(q[1:]*q[:-1],axis=1))>0),
      'no_negative_ground_height':bool(p[:,1].min()>=-1e-6),
      'release_no_velocity_impulse':bool(np.linalg.norm(v[release]-v[release-1])<.8),
      'acceleration_below_regularization_ceiling':bool(np.linalg.norm(a,axis=1).max()<40),
      'ground_after_nominal_touchdown':bool(np.max(np.abs(p[t>=d['events']['nominalTouchdown'],1]))<1e-6),
      'ramp_wider_than_authored_car':d['ramp']['width']>d['car']['width']+.5,
      'delivered_polyline_contact_error_below_1cm':d['validation']['maxModelWheelContactError_m']<.01,
      'in_sample_pixel_fit_below_20px':d['validation']['carCenterRmsPx']<20,
      'withheld_pixel_evidence_reported':d['validation']['withheldWideView']['nWithheldPoints']==5,
      'extrapolated_tail_explicit':all('extrapolation' in s['confidence']['provenance']for s in d['samples']if s['time']>d['events']['groundExtrapolationStarts'])}
    result={'reconstructionSha256':hashlib.sha256(payload).hexdigest(),'allPassed':all(tests.values()),'checks':tests,
            'maxAcceleration_mps2':float(np.linalg.norm(a,axis=1).max()),
            'maxQuaternionNormError':float(np.max(np.abs(np.linalg.norm(q,axis=1)-1))),
            'releaseAdjacentVelocityChange_mps':float(np.linalg.norm(v[release]-v[release-1])),
            'scope':'numerical consistency and evidence bookkeeping, not proof of metric accuracy or physical capability'}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if not result['allPassed']:raise SystemExit(1)

if __name__=='__main__':main()
