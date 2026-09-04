#!/usr/bin/env python3
"""Verify a copied Lab Git object pool and prepare it as a repo --reference cache."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ALIASES = {
    'kernel': {'android_kernel_common.git': 'kernel/common.git'},
    'system': {
        'android_device_generic_goldfish.git': 'LineageOS/android_device_generic_goldfish.git',
        'android_vendor_lineage.git': 'LineageOS/android_vendor_lineage.git',
    },
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['kernel', 'system'])
    parser.add_argument('reference', type=Path)
    args = parser.parse_args()
    reference = args.reference.resolve()
    if str(reference).startswith(('/home/ubuntu/lineageos', '/home/ubuntu/lineageos-kernel-6.12')):
        parser.error('Refusing to modify the original import tree')
    manifest_path = ROOT / 'import/lab-r3' / f'{args.kind}.xml'
    projects = ET.parse(manifest_path).getroot().findall('project')
    pool = reference / '.repo/project-objects'
    if not (reference / '.repo/projects').is_dir():
        parser.error('Copy the original per-project shallow metadata before verifying the object pool')
    shallow_projects = 0
    for project in projects:
        gitdir = pool / (project.get('name') + '.git')
        commit = project.get('revision')
        original_shallow = reference / '.repo/projects' / (project.get('path', project.get('name')) + '.git') / 'shallow'
        if original_shallow.is_file():
            shallow_projects += 1
            boundary = gitdir / 'shallow'
            entries = set(boundary.read_text().splitlines()) if boundary.exists() else set()
            entries.update(original_shallow.read_text().splitlines())
            boundary.write_text('\n'.join(sorted(entries)) + '\n')
        subprocess.run(['git', '--git-dir', str(gitdir), 'cat-file', '-e', commit + '^{commit}'], check=True)
        subprocess.run(['git', '--git-dir', str(gitdir), 'rev-list', '-n', '2', commit], check=True, stdout=subprocess.DEVNULL)
        # Original repo object pools have objects but no refs. Add only a seed
        # ref in the COPY so fetch negotiation can advertise the existing base.
        subprocess.run(['git', '--git-dir', str(gitdir), 'update-ref', 'refs/avd-seed/lab-r3', commit], check=True)
    for alias, target in ALIASES[args.kind].items():
        link = pool / alias
        if link.is_symlink():
            if link.resolve() != (pool / target).resolve():
                raise ValueError(f'Unexpected reference alias: {link}')
        elif link.exists():
            raise ValueError(f'Refusing to replace existing cache repository: {link}')
        else:
            link.symlink_to(target, target_is_directory=True)
    result = {'kind': args.kind, 'verified_projects': len(projects), 'shallow_projects': shallow_projects, 'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              'aliases': ALIASES[args.kind], 'independent_copy': True}
    (reference / '.avd-seed-complete.json').write_text(json.dumps(result, indent=2) + '\n')
    (reference / '.import-in-progress').unlink(missing_ok=True)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
