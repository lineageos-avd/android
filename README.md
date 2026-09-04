# LineageOS AVD

LineageOS 23.2 / Android API 36.1 system images for Google Android Emulator, with Linux 6.12 and KernelSU-Next v3.3.0. This repository is a fork of the LineageOS manifest repository; `avd-main` adds pinned source integration, releases and Nix build automation.

[Imported revision 3 images](https://github.com/lineageos-avd/android/releases/tag/lab-import-r3) are the existing Lab-Ubuntu build, uploaded without changing their bytes. [Emulator Hub](https://github.com/moeleak/emulator-hub) consumes [`images/catalog-v1.json`](images/catalog-v1.json). Use ARM64 guests on Apple Silicon and x86_64 guests on Intel/AMD hosts. API 36.1 is preserved as a major/minor version.

## Sources and changes

`manifests/system.xml` pins 1,164 repositories; `manifests/kernel.xml` pins 50 upstream repositories plus KernelSU-Next. Only modified projects point to forks. All historical upstream branches remain available.

- [Goldfish](https://github.com/lineageos-avd/android_device_generic_goldfish): module-signature preservation, syscall-hardening switch and gestural navigation.
- [Lineage vendor](https://github.com/lineageos-avd/android_vendor_lineage): noninteractive setup, enlarged ARM64 partitions, bundled KernelSU Manager and ABI-specific native payloads.
- [Linux common](https://github.com/lineageos-avd/android_kernel_common): KernelSU integration and the imported syscall changes. A follow-up commit assigns `INDIRECT_SAFE` its own CPU-feature bit.
- [KernelSU-Next](https://github.com/lineageos-avd/KernelSU-Next): version stamping, sulog compatibility and discovery of the signature-verified Manager under `/product/app`.

Each modified project has a `lab-import-r3` tag at its unaltered working-tree import. Later fixes are separate commits. The original pinned manifests, kernel configs, checksums and provenance are preserved in [`import/lab-r3`](import/lab-r3). A source snapshot taken after a historical build does not prove that the historical ZIP is bit-for-bit reproducible from it. Imported ZIPs retain the original known CPU-bit collision; fresh builds include its fix.

## Rebuild with Nix

Full Android and kernel builds need an x86_64 Linux host with KVM for runtime tests, ample disk (at least 1 TB recommended) and memory. The locked Nix FHS environment supplies host tools while Android/Kleaf use the toolchains pinned by their manifests. macOS can inspect manifests with `nix develop`; the system build itself runs on Linux. Original Lab source directories are never reused for builds.

```sh
nix build .#android-env
result/bin/lineageos-build-env scripts/sync.sh kernel "$HOME/Projects/avd/kernel"
result/bin/lineageos-build-env scripts/sync.sh system "$HOME/Projects/avd/system"
result/bin/lineageos-build-env scripts/build-kernels.sh "$HOME/Projects/avd/kernel"
python3 scripts/stage-kernels.py "$HOME/Projects/avd/system" --kernel-workspace "$HOME/Projects/avd/kernel"
result/bin/lineageos-build-env scripts/build-system.sh "$HOME/Projects/avd/system" "$PWD/artifacts"
```

To rebuild only Android using the matching historical kernels, replace kernel building/staging with `python3 scripts/stage-kernels.py SYSTEM_WORKSPACE --imported`. The script verifies the pinned SHA256 and replaces complete kernel/module directories, preserving all signatures and deleted-module state. It rejects unsafe archive entries and unsigned GKI modules. It does not copy private module-signing keys.

`BUILD_JOBS` defaults to 32 and `SYNC_JOBS` to 16. Checkouts use shallow history at the exact pinned commits; complete history remains available in the upstream and fork repositories. The repo bootstrap uses the official GerritCodeReview GitHub mirror at signed v2.66.1 and checks its exact commit. `sync.sh` accepts an optional third argument to pin the manifest repository itself to an exact commit. Check out the desired integration commit and pass it for archival reproduction.

## Actions

Public PRs run manifest and script validation on GitHub-hosted runners. Only trusted `avd-main` commits and `avd-v*` tags use the dedicated `lineageos-avd-android` self-hosted runner on Lab. The workflow builds both kernels before both system images and retains checksums and locked source manifests. Version tags publish prereleases. The download catalog remains on the imported revision until a newly built pair has completed boot validation.

## Boot verification

Use `python3 tools/smoke.py IMAGE.zip --emulator /path/to/emulator --adb /path/to/adb --output evidence` on a host matching the guest ABI. It creates an isolated temporary AVD and private ADB server, requires hardware acceleration, waits for cold boot, checks the kernel release and bundled Manager, verifies that the Manager UI reports **Working**, and saves PNG/JSON evidence. All temporary guest storage and processes are cleaned up. The x86_64 check also verifies the imported syscall-hardening command-line setting. The script defaults to a 600-second boot deadline.

## Licenses

Android, LineageOS, the Linux kernel, KernelSU-Next and bundled software retain their original licenses; see each pinned source project's license and NOTICE files. The Linux/KernelSU modifications and build scripts needed to produce the kernel are published in the linked forks and pinned kernel manifest. KernelSU Manager is preserved byte-for-byte from the official v3.3.0 (33214) artifact. This repository does not redistribute Google proprietary system images.
