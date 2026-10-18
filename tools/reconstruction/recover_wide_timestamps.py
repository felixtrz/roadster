"""Recover actual official source frames selected by FFmpeg's fps filter.

The filter selects nearest frames around a half-output-frame phase; nominal
labels alone can be wrong by .25s and fractional-frame drift can remove a frame.
"""
import cv2,json,numpy as np
from fit_geometry import OUT

def main():
    targets={n:cv2.resize(cv2.imread(str(OUT/f'wide_{n:02d}.jpg')),(192,108)).astype(float)for n in range(1,25)}
    best={n:(1e9,0)for n in targets}
    cap=cv2.VideoCapture(str(OUT/'tesla-the-ramp.mp4'));fps=cap.get(cv2.CAP_PROP_FPS);i=0
    while True:
        ok,f=cap.read()
        if not ok:break
        t=i/fps
        if 32.8<t<45.3:
            small=cv2.resize(f,(192,108)).astype(float)
            for n,tar in targets.items():
                if abs(t-(33.25+(n-1)*.5))<.20:
                    mse=float(np.mean((small-tar)**2))
                    if mse<best[n][0]:best[n]=(mse,i)
        i+=1
    cap.release()
    metadata=[{'file':f'wide_{n:02d}.jpg','sourceFrame':best[n][1],
               'sourceTime':best[n][1]/fps,'jpegMseAt192x108':best[n][0],
               'timestampMethod':'nearest decoded source-frame image match; CFR24000/1001'}for n in targets]
    (OUT/'wide-frames.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))

if __name__=='__main__':main()
