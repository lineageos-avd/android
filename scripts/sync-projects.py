#!/usr/bin/env python3
"""Sync exact manifest commits with optional transport-only AOSP mirror fallback.

The mirror transport/fallback follows lineageos-avd/android-emulator/scripts/sync.py.
Neither the public manifest remotes nor the user's global Git configuration change.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def run(*command, **kwargs):
    subprocess.run([str(value) for value in command], check=True, **kwargs)



def recover_incomplete_checkouts(source, manifest, env, direct_env, jobs):
    """Repair interrupted repo initialization without fetching entire branch history.

    Repo 2.66 treats an existing gitdir without a shallow file as a deliberately
    unshallowed repository. An interrupted first clone has the same shape. Probe
    only the pinned snapshot, then refetch that snapshot when it is incomplete.
    """
    default_remote = manifest.find('default').get('remote')

    def recover(project):
        path = project.get('path', project.get('name'))
        gitdir = source / '.repo/projects' / (path + '.git')
        if not (gitdir / 'config').is_file():
            return
        objdir = source / '.repo/project-objects' / (project.get('name') + '.git') / 'objects'
        if not objdir.is_dir():
            return
        revision = project.get('revision')
        probe_env = dict(direct_env, GIT_DIR=str(gitdir), GIT_OBJECT_DIRECTORY=str(objdir))

        def complete():
            result = subprocess.run(['git', 'rev-list', '--objects', '--missing=print', '--no-walk', revision],
                                    cwd=source, env=probe_env, capture_output=True, text=True)
            return result.returncode == 0 and not any(line.startswith('?') for line in result.stdout.splitlines())

        if complete():
            return
        remote = project.get('remote', default_remote)
        have_commit = subprocess.run(['git', 'cat-file', '-e', revision + '^{commit}'], cwd=source, env=probe_env, capture_output=True).returncode == 0
        command = ['git', 'fetch', *(['--refetch'] if have_commit else []), '--depth=1', '--no-tags', '--no-auto-gc',
                   '--recurse-submodules=no', remote, revision]
        fetch_env = dict(env, GIT_DIR=str(gitdir), GIT_OBJECT_DIRECTORY=str(objdir))
        print(f'Recovering incomplete pinned snapshot: {path} {revision}', flush=True)
        try:
            run(*command, cwd=source, env=fetch_env)
        except subprocess.CalledProcessError:
            if env == direct_env:
                raise
            print(f'Mirror recovery failed for {path}; retrying original remote', flush=True)
            run(*command, cwd=source, env=probe_env)
        if not complete():
            raise RuntimeError(f'Pinned snapshot remains incomplete after refetch: {path}')

    with ThreadPoolExecutor(max_workers=min(jobs, 4)) as pool:
        list(pool.map(recover, manifest.findall('project')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=16)
    parser.add_argument('--reference', type=Path)
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
    manifest = ET.fromstring(subprocess.check_output(['repo', 'manifest', '-o', '-'], cwd=source, env=direct_env))
    if args.reference:
        reference = args.reference.resolve()
        for project in manifest.findall('project'):
            objdir = source / '.repo/project-objects' / (project.get('name') + '.git') / 'objects'
            seed = reference / '.repo/project-objects' / (project.get('name') + '.git') / 'objects'
            if objdir.is_dir() and seed.is_dir():
                alternate = objdir / 'info/alternates'
                alternate.parent.mkdir(parents=True, exist_ok=True)
                entries = alternate.read_text().splitlines() if alternate.exists() else []
                if str(seed) not in entries:
                    entries.append(str(seed))
                    alternate.write_text('\n'.join(entries) + '\n')
                seed_shallow = seed.parent / 'shallow'
                gitdir = source / '.repo/projects' / (project.get('path', project.get('name')) + '.git')
                if seed_shallow.is_file() and gitdir.is_dir():
                    boundary = gitdir / 'shallow'
                    lines = set(boundary.read_text().splitlines()) if boundary.exists() else set()
                    lines.update(seed_shallow.read_text().splitlines())
                    boundary.write_text('\n'.join(sorted(lines)) + '\n')
    recover_incomplete_checkouts(source, manifest, env, direct_env, args.jobs)
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
