#!/usr/bin/env bash
set -euo pipefail
workspace=${1:?Usage: build-kernels.sh KERNEL_WORKSPACE}
cd "$workspace"
test -f common/workspace_status.json
test "$(readlink common/drivers/kernelsu)" = '../../KernelSU-Next/kernel'
# The baseline enables KSU by default and stamps its original v3.3.0 release.
# Keep signing enabled: system_dlkm_staging_archive contains the signed GKI modules.
for arch in aarch64 x86_64; do
  tools/bazel run --config=stamp --jobs="${BUILD_JOBS:-32}" "//common-modules/virtual-device:virtual_device_${arch}_dist"
done
