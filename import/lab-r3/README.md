# Lab revision 3 import

Imported 2026-09-05 from the existing 2026-07-17 Lab-Ubuntu output, without rebuilding or modifying the image ZIPs. `system.xml` (1164 projects) and `kernel.xml` (50 projects) pin the original source HEADs; `sources.json` records the additional dirty-tree import commits. KernelSU-Next is an additional repository beside kernel `common`, linked by `common/drivers/kernelsu`.

The original manifests preserve the original remote spelling. Use the normalized `manifests/*.xml` for public checkouts. The original disabled local compatibility manifest was not active and is not needed to reproduce this tree. The original image description incorrectly says API 16; the actual `AndroidVersion.ApiLevel` is 36.1. Later source commits fix the description and an x86 CPU feature-bit collision; these fixes are not present in imported ZIPs.

The complete matching qemu kernel/module prebuilt directories are a release asset, not Git binaries. No source directory on Lab-Ubuntu was changed. Existing outputs are labelled imported artifacts; the source snapshot was captured after the historical build and does not assert bit-for-bit reproducibility of that historical build.
