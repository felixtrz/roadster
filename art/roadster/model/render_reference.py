"""Same-camera normalized raw-reference evidence; no project save."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import *
guard()
render_views(ROOT/'reference/renders',groups=('Ref',),modes=('material',),
             views=('front','left','back','top','quarter','rear-quarter','low-front','low-quarter'))
print('Updated aligned same-camera reference renders; no project save.')
