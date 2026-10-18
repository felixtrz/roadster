"""Fit one coherent pane to the source-informed authored aperture corners."""
from pathlib import Path
import json
import numpy as np
from fair_body import C,plane_x

ROOT=Path(__file__).resolve().parent
yz=np.array(C['side_glass_yz']);x=np.array([plane_x(y,z) for y,z in yz])
matrix=np.column_stack([np.ones(len(yz)),yz]);co=np.linalg.lstsq(matrix,x,rcond=None)[0]
result={'method':'Least-squares x=a+b*y+c*z plane through the six source-informed authored side-aperture controls; bilateral symmetry.',
 'coefficients':co.tolist(),'aperture_yz':yz.tolist(),'original_control_x':x.tolist(),
 'control_departure_mm':((matrix@co-x)*1000).tolist(),
 'maximum_control_departure_mm':float(np.max(np.abs(matrix@co-x))*1000),
 'frame_blend_margin_m':.080,'white_front_frame_width_yz_m':.025,
 'limits':'This is an explicit fairing departure from the ruled proxy, not a certified source-car glass plane. The aperture YZ landmarks and accepted body/nose/shoulder rails are preserved.'}
(ROOT/'fit/side-glass-plane-v4.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
