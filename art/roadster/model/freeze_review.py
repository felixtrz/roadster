"""Copy one complete review input without overwriting an earlier snapshot."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[2]

parser=argparse.ArgumentParser()
parser.add_argument('--version',required=True,choices=['v3','v4','v5','v6','v7','v8','v9'])
parser.add_argument('--expected-sha256',required=True)
args=parser.parse_args()
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
asset=PROJECT/'public/models/roadster.glb'
if digest(asset)!=args.expected_sha256:
    raise SystemExit('Export differs from the specifically approved review input hash.')
target=ROOT/f'review-input-{args.version}'
if target.exists():
    raise SystemExit('Refusing to overwrite an immutable review snapshot.')

sources={Path('roadster.glb'):asset}
for name in ['Roadster.blend','model-contract.json','glb-validation.json','README.md','source-comparison.png']:
    sources[Path(name)]=ROOT/name
for folder in ['renders','runtime-glb-renders','runtime-captures','sections','fit']:
    for source in sorted((ROOT/folder).rglob('*')):
        if source.is_file():sources[source.relative_to(ROOT)]=source
for source in sorted(ROOT.glob('*.py')):
    sources[Path('scripts')/source.name]=source
for source in sources.values():
    if not source.is_file():raise SystemExit(f'Missing evidence: {source}')
target.mkdir()
records=[]
for relative,source in sources.items():
    output=target/relative;output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,output)
    if digest(output)!=digest(source):raise RuntimeError(f'Copy mismatch: {relative}')
    records.append({'file':str(relative),'source':str(source.relative_to(PROJECT)),
                    'sha256':digest(output),'bytes':output.stat().st_size})
manifest={'version':args.version,'created_utc':datetime.now(timezone.utc).isoformat(),
    'status':'frozen for fresh independent review; no quality score claimed',
    'public_glb_sha256':args.expected_sha256,
    'source_reference_sha256':digest(PROJECT/'art/roadster/tripo/h31-reference-v1/model_url.glb'),
    'files':records}
(target/'snapshot-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'snapshot':str(target.relative_to(PROJECT)),'files':len(records),
                  'public_glb_sha256':args.expected_sha256}))
