"""Render current approved candidate without rebuilding or exporting it."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import *
guard()
render_views(ROOT/'renders',groups=('Authored',),modes=('material','clay'),
 views=('front','left','back','top','quarter','rear-quarter','low-front','low-quarter'))
parts=[o for o in collection('Authored').objects if o.type=='MESH']
stats={'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in parts),
       'mesh_parts':len(parts),'objects':len(collection('Authored').objects),
       'source_triangles':188630,'primary_checkpoint':False}
(ROOT/'renders/stats.json').write_text(json.dumps(stats,indent=2)+'\n')
print('Read-only authored render batch complete; no GLB export or project save.')
