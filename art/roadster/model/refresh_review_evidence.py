"""Render/measure the current saved candidate without rebuilding/exporting/saving."""
from pathlib import Path
import runpy,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import guard
guard()
for script in ('measure_roadster.py','diagnose_surface_ownership.py','audit_material_sides.py',
               'render_authored.py','render_underside.py','render_runtime_glb.py'):
    print('READ_ONLY_EVIDENCE '+script,flush=True)
    runpy.run_path(str(ROOT/script),run_name='__review__')
print('Full evidence refresh complete; saved blend and public GLB untouched.')
