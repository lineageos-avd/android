#!/usr/bin/env python3
"""Sync exact manifest commits with optional transport-only AOSP mirror fallback.

The mirror transport/fallback follows lineageos-avd/android-emulator/scripts/sync.py.
Neither the public manifest remotes nor the user's global Git configuration change.
"""
import argparse
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def run(*command, **kwargs):
    subprocess.run([str(value) for value in command], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=16)
    parser.add_argument('--aosp-mirror', default=os.environ.get('AOSP_MIRROR'))
    args = parser.parse_args()
    if args.aosp_mirror and not args.aosp_mirror.startswith('https://'):
        parser.error('--aosp-mirror must be an HTTPS URL')
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    source = args.workspace.resolve()
    env = os.environ.copy()
    direct_env = env.copy()
    if args.aosp_mirror:
        index = int(env.get('GIT_CONFIG_COUNT', '0'))
        env[f'GIT_CONFIG_KEY_{index}'] = f'url.{args.aosp_mirror.rstrip("/")}/.insteadOf'
        env[f'GIT_CONFIG_VALUE_{index}'] = 'https://android.googlesource.com/'
        env['GIT_CONFIG_COUNT'] = str(index + 1)
        print(f'Fetching exact AOSP commits through {args.aosp_mirror}', flush=True)
    sync_command = ['repo', 'sync', '-c', '--no-clone-bundle', '--no-tags', '--fail-fast',
                    '-j', str(min(args.jobs, 4) if args.aosp_mirror else args.jobs)]
    try:
        run(*sync_command, cwd=source, env=env)
    except subprocess.CalledProcessError:
        if not args.aosp_mirror:
            raise
        print('Mirror synchronization failed; retrying remaining commits from Google', flush=True)
        run(*sync_command, cwd=source, env=direct_env)
    # All public manifest revisions are immutable SHA1 commits; verify every checkout.
    run('repo', 'forall', '-c', 'test "$(git rev-parse HEAD)" = "$REPO_RREV"', cwd=source, env=direct_env)
    lock = source / 'manifest.lock.xml'
    run('repo', 'manifest', '-r', '-o', lock, cwd=source, env=direct_env)
    print(f'Verified {len(ET.parse(lock).getroot().findall("project"))} exact project commits in {source}', flush=True)


if __name__ == '__main__':
    main()
