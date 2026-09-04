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
reference="${SOURCE_REFERENCE_ROOT:-$HOME/Projects/lineageos-avd-build/source-cache}/$kind"
reference_options=()
# During the initial Lab import, allow an independent read-only Docker copy to
# finish and be verified before using it. Ordinary builds have no such marker.
for attempt in {1..240}; do
  [[ ! -f "$reference/.import-in-progress" ]] && break
  (( attempt == 1 )) && echo "Waiting for verified local Git object import: $reference"
  sleep 15
done
if [[ -f "$reference/.import-in-progress" ]]; then
  echo "Local reference import did not finish within one hour: $reference" >&2
  exit 1
fi
if [[ -f "$reference/.avd-seed-complete.json" ]]; then
  reference=$(cd "$reference" && pwd)
  reference_options=(--reference "$reference")
fi
cd "$workspace"
repo init -u https://github.com/lineageos-avd/android.git -b "$revision" -m "manifests/$kind.xml" \
  --depth=1 --no-clone-bundle "${reference_options[@]}" \
  --repo-url https://github.com/GerritCodeReview/git-repo.git --repo-rev v2.66.1
# The official GitHub mirror tag peels to the same signed Google repo commit.
test "$(git -C .repo/repo rev-parse HEAD)" = b85886fa9f5b4e2189cc5b2f40bd0a80459d4c77
python3 "$script_dir/sync-projects.py" --workspace "$workspace" --jobs "${SYNC_JOBS:-16}" "${reference_options[@]}"
