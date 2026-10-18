"""Render measured skill-format section overlays with millimetre distances.

Pillow is used because the local runtime has no Matplotlib. Distances are
one-sided reference section samples -> nearest authored section segment;
internal authored part boundaries do not falsely inflate that direction.
"""
from pathlib import Path
import json
import math
import argparse
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--section-dir',default='sections');args=parser.parse_args()
SECTION=(ROOT/args.section_dir).resolve()
if not SECTION.is_relative_to(ROOT):raise SystemExit('Section evidence must remain inside the model folder.')
data=json.loads((SECTION/'roadster.json').read_text())


def samples(segments):
    points=[]
    for x0,y0,x1,y1 in segments:
        a=np.array([x0,y0]);b=np.array([x1,y1]);n=max(1,math.ceil(np.linalg.norm(b-a)/.004))
        points.extend(a+(b-a)*t for t in (np.arange(n)+.5)/n)
    return np.asarray(points)


def distances(points,segments):
    segments=np.asarray(segments).reshape(-1,4)
    a,b=segments[:,:2],segments[:,2:]
    ab=b-a;den=np.maximum((ab*ab).sum(1),1e-16)
    result=[]
    for start in range(0,len(points),128):
        delta=points[start:start+128,None,:]-a[None,:,:]
        t=np.clip((delta*ab[None,:,:]).sum(2)/den,0,1)
        d=delta-t[:,:,None]*ab[None,:,:]
        result.extend(np.sqrt((d*d).sum(2)).min(1))
    return np.asarray(result)


sheet=Image.new('RGB',(1280,1590),'white');draw=ImageDraw.Draw(sheet)
draw.text((24,12),'Roadster: preserved Tripo section (blue) / authored model (red)',fill='#151b25')
draw.text((24,32),'Distances are one-sided ref -> nearest authored segment; 4mm arc samples. Hidden underbody is an authored assumption.',fill='#333333')
scores=[]
for index,plane in enumerate(data['planes']):
    x=index%2*640;y=index//2*510+62;W,H=592,440;left,top=x+30,y+42
    u0,u1,v0,v1=plane['window'];scale=min(W/(u1-u0),H/(v1-v0));cx=left+W/2;cy=top+H/2
    def xy(u,v):return (cx+(u-(u0+u1)/2)*scale,cy-(v-(v0+v1)/2)*scale)
    for u in np.arange(math.ceil(u0/.25)*.25,u1+.001,.25):
        draw.line([xy(u,v0),xy(u,v1)],fill='#e8edf1',width=1)
    for v in np.arange(math.ceil(v0/.25)*.25,v1+.001,.25):
        draw.line([xy(u0,v),xy(u1,v)],fill='#e8edf1',width=1)
    for key,color,width in [('ref','#1a65c2',2),('auth','#d23535',2)]:
        for a,b,c,d in plane[key]:draw.line([xy(a,b),xy(c,d)],fill=color,width=width)
    points=samples(plane['ref']);score=plane.get('score',plane['window'])
    keep=(points[:,0]>=score[0])&(points[:,0]<=score[1])&(points[:,1]>=score[2])&(points[:,1]<=score[3])
    error=distances(points[keep],plane['auth'])*1000
    rec={'name':plane['name'],'axis':plane['axis'],'value_m':plane['value'],'samples':len(error),
         'mean_mm':float(error.mean()),'p90_mm':float(np.quantile(error,.9)),'max_mm':float(error.max())}
    scores.append(rec)
    draw.text((x+25,y+2),plane['name']+'; '+plane['axis']+'='+str(round(plane['value'],3))+'m',fill='#111111')
    draw.text((x+25,y+19),f"Mean {rec['mean_mm']:.1f}mm | p90 {rec['p90_mm']:.1f}mm | max {rec['max_mm']:.1f}mm",fill='#333333')
    draw.text((x+25,y+485),'Grid: 250mm. Whole-model surfaces include authored hidden geometry and simplified body sections.',fill='#555555')
sheet.save(SECTION/'roadster-overlays.png')
summary={'method':'One-sided uniform 4mm reference section samples to closest authored section segment; intentional hidden underbody/regularization departures remain included.',
         'source_to_authored':scores,'not_a_certification':'These are measured section differences from the generated reference, not proof of exact real-car geometry or video-calibrated dimensions.'}
(SECTION/'measurement-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
