"""Record V4 fair primary rails and their source/proxy departures."""
from pathlib import Path
import json
import numpy as np

ROOT=Path(__file__).resolve().parent
patch=json.loads((ROOT/'fit/surface-patches.json').read_text())
fit=json.loads((ROOT/'fit/roadster.json').read_text())
stations=patch['stations'];ys=np.array([s['y'] for s in stations]);front=float(ys[0]);back=float(ys[-1])
knots=[front,front+.30,front+.60,-1.46,fit['front_wheel']['y'],-1.02,-.60,0,.55,1.0,fit['rear_wheel']['y'],1.82,back]
def samples(key):return [[float(y),float(np.interp(y,ys,[s[key] for s in stations]))] for y in knots]
width=samples('half_width');width[0][1]=1.105;width[1][1]=1.155
lower=[[float(y),float(np.interp(y,[s['y'] for s in fit['stations']],[s['lower'] for s in fit['stations']]))] for y in knots]
centre=[[front,.558],[front+.30,.685],[front+.60,.820],[-1.46,.891],[-.30,1.305],
        [0,1.321],[.45,1.307],[.91,1.262],[1.84,1.064],[back,.930]]
shoulder=[[front,.695],[front+.30,.785],[front+.60,.850],[fit['front_wheel']['y'],.865],
          [-1.02,.883],[-.60,.903],[0,.930],[.55,.953],[1.0,.977],
          [fit['rear_wheel']['y'],.990],[1.82,.975],[back,.920]]
outer=[[front,.600],[front+.30,.710],[front+.60,.780],[fit['front_wheel']['y'],.795],
       [-1.02,.813],[-.60,.833],[0,.860],[.55,.883],[1.0,.907],
       [fit['rear_wheel']['y'],.920],[1.82,.895],[back,.840]]
result={'revision':'v4','method':'Piecewise cubic Hermite rails with continuous first derivatives and monotonic slope limiting; fixed semantic cross-section sample order.',
 'source_views':['references/roadster/frames/D01_event_09-38.000.jpg','references/roadster/frames/D02_event_11-01.000.jpg',
                 'art/roadster/reference-images/front-v2.png','art/roadster/reference-images/left-v2.png'],
 'proxy':'fit/surface-patches.json; source probes retained for comparison, not copied triangles',
 'width':width,'lower':lower,'centre':centre,'shoulder':shoulder,'outer':outer,
 'source_sampled_width':samples('half_width'),
 'side_glass_yz':patch['glass_landmarks']['side_glass_yz'],
 'departures':[
 'The front is a flat forward-facing cap rather than a swept rounded plan curve.',
 'Front centre, shoulder and outer rails rise monotonically rearward to the fender crown; no cap-to-hood blend can create an upturned terminal.',
 'The leading corner shoulder is .695m; the outer rail is .600m, leaving a forward-facing lamp area on the designed fender transition.',
 'Sampled half widths are retained through the main cabin/haunch; foremost two widths are authored1.105/1.155m to avoid the proxy narrow pointed nose.',
 'V4-b shoulder rises steadily .865m at the front axle to .990m at the rear axle; the outer white rail stays .070m below through the door. This replaces the preflight sag/broad dark bevel with a source-related rising beltline.',
 'Only the outermost60mm of the nose has a local corner fillet; the lower cap is raked backward35mm. The central cap, lens and bar retain forward presentation rather than a broad rounded plan sweep.',
 'Canopy centre heights retain existing landmarks with continuous tangents, rather than abrupt piecewise planar band changes.',
 'These controls are source-informed authoring decisions, not a calibrated millimetre reconstruction of the real car.'
 ]}
(ROOT/'fit/fair-body-v4.json').write_text(json.dumps(result,indent=2)+'\n')
print('Recorded V4 fair primary rails and deliberate source/proxy departures.')
