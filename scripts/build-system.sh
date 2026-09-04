#!/usr/bin/env bash
set -euo pipefail
workspace=${1:?Usage: build-system.sh SYSTEM_WORKSPACE OUTPUT_DIRECTORY}
output=${2:?Missing output directory}
mkdir -p "$output"
output=$(cd "$output" && pwd)
cd "$workspace"
set +u
source build/envsetup.sh
for arch in arm64 x86_64; do
  export OUT_DIR="out/avd-$arch"
  lunch "lineage_sdk_phone_${arch}-bp4a-userdebug"
  m -j"${BUILD_JOBS:-32}" sdk_addon
  case "$arch" in arm64) product=emu64a;abi=arm64-v8a;; x86_64) product=emu64x;abi=x86_64;; esac
  cp "$OUT_DIR/target/product/$product/sdk-repo-linux-system-images.zip" "$output/lineage-23.2-api36.1-$abi.zip"
done
set -u
cp manifest.lock.xml "$output/system-manifest.xml"
(cd "$output" && sha256sum ./*.zip > SHA256SUMS)
