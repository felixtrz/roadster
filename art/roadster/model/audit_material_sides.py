"""Record why the current double-sided export flags are deliberately retained."""
from pathlib import Path
import sys,json
import bpy,bmesh
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from model_lib import guard,collection
guard()
notes={
 'PearlWhite':'Shared exterior skin has open intake/arch/underside boundaries and rear relief sheets. Both sides intentionally remain visible during airborne low views.',
 'SmokedCanopy':'Single shared exterior glass skin has no duplicate thickness/backing shell. DoubleSide preserves the sheet at low/inside sightlines.',
 'DeepBlack':'Shared by cavity back/pocket regions, open shut-line tubes and nozzle interior sheets. DoubleSide is intentional for these cavity and sheet uses.',
 'WhiteLED':'Shared exterior corner-lens regions and open-ended light-bar tubes. No duplicate white or glass layer is retained below the lens.',
 'StructuralTrim':'Single shared skin trim next to glazing, without a separate thickness shell.',
 'CarbonUndercarriage':'Undercarriage is opened at the body join and intake; diffuser frames/strips have exposed sheet boundaries.',
 'TireRubber':'Revolved tire carcass intentionally has small open inner hub rings; no unseen end-cap thickness is claimed.',
 'AeroDiscGraphite':'Closed aero discs could use FrontSide. DoubleSide is deliberately retained for current material/render parity; the extra backface work is bounded by the complete model triangle budget.',
 'RimEdge':'Open revolved rim ribbon; both sides of its narrow edge are visible at wheel oblique views.',
 'ThrusterBrass':'Open-ended flare with authored inner and outer walls. DoubleSide retained at the thin end rings for complete airborne rear/low views.',
 'RedLED':'Open-ended thin rear light tubes.',
 'AmberLED':'Open-ended side-marker tubes.',
 'IntakeAbsorbent':'Open cavity jamb/back and narrow lower-lip surfaces. Their backside must not reveal the scene through a cut sheet.',
}
materials={}
for ob in collection('Authored').objects:
    if ob.type!='MESH':continue
    bm=bmesh.new();bm.from_mesh(ob.data)
    boundary=sum(not e.is_manifold for e in bm.edges);bm.free()
    for mat in ob.data.materials:
        entry=materials.setdefault(mat.name,{'double_sided':not mat.use_backface_culling,
            'reason':notes.get(mat.name,'Unclassified: review required'), 'objects':[]})
        entry['objects'].append({'name':ob.name,'nonmanifold_or_boundary_edges':boundary})
assert set(materials)<=set(notes)
report={'policy':'Retain reviewed DoubleSide flags; no visible ownership/normal changes made merely to suppress an informational warning.',
 'culling_limit':'This is a material intent audit, not proof that every part is watertight. Named closed discs can be culled as a future optimization without being required for correctness.',
 'materials':materials}
(ROOT/'fit/material-side-audit-v4.json').write_text(json.dumps(report,indent=2)+'\n')
print('Material-side audit written for '+str(len(materials))+' materials; no scene mutation or save.')
