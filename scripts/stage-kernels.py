#!/usr/bin/env python3
"""Stage whole matching kernel/module sets, preserving every module signature."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SIGNATURE = b'~Module signature appended~\n'


def checked_members(archive):
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts or not (member.isdir() or member.isfile()):
            raise ValueError(f'Unsafe archive entry: {member.name}')
        yield member


def extract(archive_path, destination):
    with tarfile.open(archive_path) as archive:
        members = list(checked_members(archive))
        archive.extractall(destination, members=members, filter='data')


def validate(root):
    for arch, kernel in [('arm64', 'kernel-6.12-gz'), ('x86_64', 'kernel-6.12')]:
        base = root / arch / '6.12'
        if not (base / kernel).is_file() or not list((base / 'goldfish_modules').glob('*.ko')):
            raise ValueError(f'Missing kernel or goldfish modules: {base}')
        modules = list((base / 'gki_modules').glob('*.ko'))
        if not modules or not (base / 'gki_modules/virtio_pci_modern_dev.ko').is_file():
            raise ValueError(f'Missing GKI modules: {base}')
        for module in modules:
            if not module.read_bytes().endswith(SIGNATURE):
                raise ValueError(f'GKI module signature missing: {module}')


def stage_dist(kernel_workspace, destination):
    for arch, target, image in [('arm64', 'aarch64', 'Image.gz'), ('x86_64', 'x86_64', 'bzImage')]:
        dist = kernel_workspace / f'out/virtual_device_{target}/dist'
        base = destination / arch / '6.12'
        (base / 'gki_modules').mkdir(parents=True)
        (base / 'goldfish_modules').mkdir()
        shutil.copy2(dist / image, base / ('kernel-6.12-gz' if arch == 'arm64' else 'kernel-6.12'))
        with tarfile.open(dist / 'system_dlkm_staging_archive.tar.gz') as archive:
            for member in checked_members(archive):
                normalized = member.name.removeprefix('./')
                if member.isfile() and normalized.startswith('flatten/lib/modules/') and normalized.endswith('.ko'):
                    with archive.extractfile(member) as source, (base / 'gki_modules' / PurePosixPath(normalized).name).open('wb') as output:
                        shutil.copyfileobj(source, output)
        for module in dist.glob('*.ko'):
            shutil.copy2(module, base / 'goldfish_modules' / module.name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('system_workspace', type=Path)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--kernel-workspace', type=Path)
    source.add_argument('--imported', action='store_true')
    parser.add_argument('--archive', type=Path, help='Already downloaded imported archive (SHA256 is still verified)')
    args = parser.parse_args()
    system = args.system_workspace.resolve()
    if system == Path('/home/ubuntu/lineageos'):
        parser.error('Refusing to modify the original import workspace')
    target = system / 'prebuilts/qemu-kernel'
    if not (system / '.repo').is_dir() or not target.is_dir():
        parser.error('Expected a synced Android repo workspace')
    with tempfile.TemporaryDirectory(prefix='avd-kernel-', dir=system) as temp:
        staging = Path(temp) / 'staging'
        staging.mkdir()
        if args.imported:
            metadata = json.loads((ROOT / 'import/lab-r3/kernel-prebuilts.json').read_text())
            archive = args.archive or Path(temp) / 'prebuilts.tar.gz'
            if not args.archive:
                with urllib.request.urlopen(metadata['url']) as response, archive.open('wb') as output:
                    shutil.copyfileobj(response, output)
            with archive.open('rb') as payload:
                digest = hashlib.file_digest(payload, 'sha256').hexdigest()
            if digest != metadata['sha256']:
                raise ValueError('Imported archive SHA256 mismatch')
            extract(archive, staging)
        else:
            if args.archive:
                parser.error('--archive requires --imported')
            stage_dist(args.kernel_workspace.resolve(), staging)
        validate(staging)
        # Replace the entire version directory so removed upstream modules cannot survive.
        for arch in ('arm64', 'x86_64'):
            old = target / arch / '6.12'
            old.parent.mkdir(parents=True, exist_ok=True)
            backup = Path(temp) / f'old-{arch}'
            if old.exists():
                old.rename(backup)
            try:
                (staging / arch / '6.12').rename(old)
            except BaseException:
                if backup.exists():
                    backup.rename(old)
                raise
        print(f'Staged signed matching ARM64 and x86_64 kernels in {target}')


if __name__ == '__main__':
    main()
