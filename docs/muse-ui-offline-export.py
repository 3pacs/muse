"""Export immutable Muse UI source and delivered images using standard Python.

Run from a fetched repository: python3 export_recipe.py --repo . --revision SHA --output preview.zip
The exporter does not modify application source or contact providers.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', required=True)
parser.add_argument('--revision', required=True)
parser.add_argument('--output', required=True)
args = parser.parse_args()
output = Path(args.output)
if output.exists():
    raise SystemExit('Refusing to overwrite an existing export.')

def git(*parts):
    return subprocess.check_output(['git', '-C', args.repo, *parts])

revision = git('rev-parse', '--verify', args.revision + '^{commit}').decode().strip()
names = git('ls-tree', '-r', '--name-only', revision, 'uig1').decode().splitlines()
if not names:
    raise SystemExit('Revision has no uig1 source.')
members = {name: git('show', revision + ':' + name) for name in names}
html_name = 'uig1/frontend/gex-granular-dashboard.html'
manifest = json.loads(members['uig1/MANIFEST.json'])
html = members[html_name]
html_hash = hashlib.sha256(html).hexdigest()
if html_hash != manifest['produced_html_sha256']:
    raise SystemExit('Owner manifest does not match the actual HTML.')
content_pin = manifest['source_pin']
if git('show', content_pin + ':' + html_name) != html:
    raise SystemExit('Claimed content-source revision has different HTML.')

for name in names:
    if '/screenshot_evidence_' not in name:
        continue
    record = json.loads(members[name])
    filename = record['filename']
    if PurePosixPath(filename).name != filename:
        raise SystemExit('Image filename must be a basename.')
    encoded = record.get('image_base64', record.get('png_base64'))
    image = base64.b64decode(encoded, validate=True)
    digest = hashlib.sha256(image).hexdigest()
    expected = record.get('delivered_sha256', record.get('sha256'))
    if digest != expected or len(image) != record['bytes']:
        raise SystemExit('Delivered image bytes do not match their receipt.')
    members['uig1/screenshots/' + filename] = image

members['index.html'] = html
members['EXPORT-README.md'] = (
    '# Muse immutable offline source export\n\n'
    'Open index.html directly. Run python3 uig1/tests/ui/test_dashboard.py.\n\n'
    'This export preserves the owner source bytes and original receipts. '
    'EXPORT-MANIFEST.json records the exact review/content revisions and all member hashes. '
    'Decoded screenshot files come from source-contained JSON evidence. '
    'Export integrity does not imply UI acceptance, live data, hosted linkage or deployment.\n'
).encode()
receipt = {
    'review_revision': revision,
    'content_source_revision': content_pin,
    'html_sha256': html_hash,
    'application_source_unchanged': True,
    'files': [{'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
              for name, data in sorted(members.items())],
}
members['EXPORT-MANIFEST.json'] = (json.dumps(receipt, indent=2) + '\n').encode()
with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
    for name, data in sorted(members.items()):
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, data)
with zipfile.ZipFile(output) as archive:
    for name, data in members.items():
        if archive.read(name) != data:
            raise SystemExit('Archive readback failed.')
print(json.dumps({'review_revision': revision, 'content_source_revision': content_pin,
                  'output': str(output), 'bytes': output.stat().st_size,
                  'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                  'all_member_bytes_verified': True}, indent=2))
