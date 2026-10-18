"""Check primary design constraints before spending full render/export work."""
from pathlib import Path
import json
import numpy as np
from fair_body import C,RAILS,deck,dimension

ROOT=Path(__file__).resolve().parent
y0=C['centre'][0][0];toe=-1.46
ys=np.linspace(y0,toe,1001)
minimum_steps={}
for f in (0,.40,.72,.80,.91,.993):
    z=np.array([deck(y,f) for y in ys]);minimum_steps[str(f)]=float(np.diff(z).min())
    assert minimum_steps[str(f)]>=-1e-6,f'Upturned nose or falling rearward hood rail at fraction{f}'
continuity={}
for key,curve in RAILS.items():
    errors=[]
    for x in curve.x[1:-1]:
        h=1e-5;left=(curve(x)-curve(x-h))/h;right=(curve(x+h)-curve(x))/h
        errors.append(abs(left-right))
    continuity[key]=max(errors,default=0)
    assert continuity[key]<.001,f'Rail tangent jump at{key}'
report={'revision':'v4','front_rail_minimum_rearward_step_m':minimum_steps,
        'rail_maximum_numerical_left_right_slope_difference':continuity,
        'method':'1001 front-profile samples and one-sided10micrometre tangent probes at all interior C1 rail controls.',
        'limits':'Checks continuity and monotonic design constraints only; source fidelity still requires independent visual judgement.'}
(ROOT/'fit/form-validation-v4.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
