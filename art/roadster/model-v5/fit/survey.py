import os, sys
_SKILL = os.environ.get('MESH_REBUILD_SKILL', '')
if not os.path.isdir(_SKILL):
    raise SystemExit('Set MESH_REBUILD_SKILL to the rebuild-generated-mesh skill scripts directory (contains facets.py).')
sys.path.insert(0, _SKILL)
from facets import *
R = load('reference/faces.npz')
C, share, lab = palette(R, k=7)
for c, s in zip(C, share): print(np.round(c, 3), round(float(s), 3))
np.save('fit/palette_labels.npy', lab)
# per class: bounding region
for j in range(len(C)):
    m = lab == j; P = R['fc'][m]
    print(j, np.round(np.percentile(P, 2, 0), 2), np.round(np.percentile(P, 98, 0), 2))
shell = np.ones(len(R['fa']), bool)
s, rows = mirror_offset(R, box(R, (-3, -1.5, 0.5), (3, 1.5, 1.3)), [('side', (1, 0, 0)), ('corner', (0.7, -0.3, 0.6))])
print('mirror offset', s); print(rows)
