#!/usr/bin/env bash
set -euo pipefail
kind=${1:?Usage: sync.sh system|kernel WORKSPACE [MANIFEST_REVISION]}
workspace=${2:?Missing workspace}
revision=${3:-avd-main}
case "$kind" in system|kernel) ;; *) echo 'Expected system or kernel' >&2; exit 2;; esac
mkdir -p "$workspace"
workspace=$(cd "$workspace" && pwd)
case "$workspace" in /home/ubuntu/lineageos|/home/ubuntu/lineageos-kernel-6.12) echo 'Refusing to modify the original import workspace' >&2; exit 2;; esac
cd "$workspace"
repo init -u https://github.com/lineageos-avd/android.git -b "$revision" -m "manifests/$kind.xml" --no-clone-bundle
repo sync -c --no-tags --no-clone-bundle -j "${SYNC_JOBS:-16}"
repo manifest -r -o manifest.lock.xml
