#!/usr/bin/env python3
"""Validate immutable source pins, fork coverage and published image metadata."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
for kind, count in [('system', 1164), ('kernel', 51)]:
    manifest = ET.parse(ROOT / f'manifests/{kind}.xml').getroot()
    projects = manifest.findall('project')
    assert len(projects) == count, (kind, len(projects))
    paths = set()
    for project in projects:
        assert re.fullmatch('[a-f0-9]{40}', project.get('revision', '')), project.attrib
        path = project.get('path', project.get('name'))
        assert path not in paths, path
        paths.add(path)
    for remote in manifest.findall('remote'):
        assert remote.get('fetch', '').startswith('https://'), remote.attrib
catalog = json.loads((ROOT / 'images/catalog-v1.json').read_text())
assert catalog['schema_version'] == 1
assert {image['abi'] for image in catalog['images']} == {'arm64-v8a', 'x86_64'}
for image in catalog['images']:
    assert image['api'] == {'major': 36, 'minor': 1}
    assert image['checksum']['algorithm'] == 'sha256'
    assert re.fullmatch('[a-f0-9]{64}', image['checksum']['value'])
    assert image['size'] > 0 and image['url'].startswith('https://github.com/lineageos-avd/android/releases/download/')
print('Validated 1,215 immutable project pins and both API 36.1 image descriptors')
