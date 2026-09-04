#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd "$(dirname "$0")" && pwd)
kind=${1:?Usage: sync.sh system|kernel WORKSPACE [MANIFEST_REVISION]}
workspace=${2:?Missing workspace}
revision=${3:-avd-main}
case "$kind" in system|kernel) ;; *) echo 'Expected system or kernel' >&2; exit 2;; esac
mkdir -p "$workspace"
workspace=$(cd "$workspace" && pwd)
case "$workspace" in /home/ubuntu/lineageos|/home/ubuntu/lineageos-kernel-6.12) echo 'Refusing to modify the original import workspace' >&2; exit 2;; esac
cd "$workspace"
repo init -u https://github.com/lineageos-avd/android.git -b "$revision" -m "manifests/$kind.xml" \
  --depth=1 --no-clone-bundle \
  --repo-url https://github.com/GerritCodeReview/git-repo.git --repo-rev v2.66.1
# The official GitHub mirror tag peels to the same signed Google repo commit.
test "$(git -C .repo/repo rev-parse HEAD)" = b85886fa9f5b4e2189cc5b2f40bd0a80459d4c77
python3 "$script_dir/sync-projects.py" --workspace "$workspace" --jobs "${SYNC_JOBS:-16}"
