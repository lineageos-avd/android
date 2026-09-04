# LineageOS 23.2 ranchu emulator images

Build date: 2026-07-17

These are Android Studio Emulator (ranchu/goldfish device tree) SDK system-image
packages for LineageOS 23.2, Android 16 / API 36, build ID
`BP4A.251205.006`.

## Packages

- `lineage-23.2-ranchu-x86_64-linux-6.12-ksunext-v3.3.0.zip`
  - ABI: `x86_64`
  - kernel: `6.12.89-android16-6-ksunext-v3.3.0`
- `lineage-23.2-ranchu-arm64-v8a-linux-6.12-ksunext-v3.3.0.zip`
  - ABI: `arm64-v8a`
  - kernel: `6.12.89-android16-6-ksunext-v3.3.0-4k`
- `KernelSU_Next_v3.3.0_33214-release.apk`
  - byte-for-byte copy of the official KernelSU-Next Manager, kept separately
    for updates or reinstalling

Both Linux 6.12 kernels have KernelSU-Next v3.3.0 (version code 33214) built
in. Their release strings are reproducibly stamped and contain no
`maybe-dirty` suffix.

The official KernelSU-Next Manager is preinstalled as
`/product/app/KernelSU_Next/KernelSU_Next.apk`; no `adb install` step is
needed. Its package name is `com.rifsxd.ksunext`, version `v3.3.0` (33214).
The image retains the Manager's ABI-specific JNI libraries and executable
`libksud.so` beside the system APK, avoiding the launch crash caused when
Android does not extract native libraries for a preinstalled app.

The image omits the interactive LineageOS Setup Wizard at build time and uses
Android Emulator SdkSetup for non-interactive first-boot provisioning. It sets
fully gestural navigation as the image-level first-boot default and declares
the software navigation bar in the ranchu phone framework overlay. The
installer writes `hw.mainKeys=no`, so the gesture home handle is not hidden by
an emulated hardware-key configuration.

KernelSU-Next additionally recognizes the signature-verified Manager at its
preinstalled `/product/app` path. Upstream normally discovers the Manager only
under `/data/app`; supporting the immutable product path lets the bundled
Manager receive its KernelSU driver descriptor without requiring a separate
`adb install`.

Revision 3 pairs every GKI and goldfish kernel module with the exact signing
key used by its KernelSU-Next kernel. This fixes the first-stage init abort in
revision 2 where `virtio_pci_modern_dev.ko` was rejected as an untrusted
protected-symbol exporter, leaving the Emulator window black before adbd
started.

## Graphics

Both images include the ranchu/gfxstream Vulkan HAL, Vulkan loader, ANGLE,
OpenGL ES emulation libraries, Vulkan compute/level/dEQP declarations, and the
Vulkan 1.3 feature declaration (`0x00403000`). Use a recent Android Emulator
with host graphics enabled (`-gpu host` or Android Studio's Hardware graphics
setting). Runtime Vulkan support also depends on the host GPU and driver.

## Install on macOS

Place the matching ZIP beside `install-lineageos-macos.sh`, then run:

```sh
chmod +x install-lineageos-macos.sh
./install-lineageos-macos.sh
```

The script automatically detects Apple Silicon versus Intel, finds the default
macOS SDK at `$HOME/Library/Android/sdk` when `ANDROID_SDK_ROOT` and
`ANDROID_HOME` are unset, installs the proper ABI, creates
`LineageOS_23_2_KSUNext`, and launches it with `-gpu host`. It also works around
recent SDK Tools not registering manually extracted custom images.

The default virtual display is 1080x2400 at 420 dpi. Override it when needed:

```sh
DISPLAY_WIDTH=1440 DISPLAY_HEIGHT=3200 DISPLAY_DENSITY=560 \
  ./install-lineageos-macos.sh
```

Pass an explicit ZIP path as the first argument. Set `FORCE_REINSTALL=1` to
replace an already installed revision 3 image unconditionally. Installing a
new image revision or forcing a reinstall automatically wipes incompatible AVD
userdata and performs a cold boot.

For an image that is already installed, set `WIPE_AVD_DATA=1` to reset only the
AVD userdata without reinstalling the ZIP. Set `WIPE_AVD_DATA=0` only when you
intentionally need to preserve userdata across an image replacement. Android
persists the navigation-mode overlay in userdata, so newly created or wiped
AVDs use the image-level gestural default without any `adb settings` command.

## Manual SDK installation

The archive supplies the final ABI directory, so extract it under the API 36
LineageOS image directory:

```sh
SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}"
mkdir -p "$SDK_ROOT/system-images/android-36/lineage"
unzip lineage-23.2-ranchu-arm64-v8a-linux-6.12-ksunext-v3.3.0.zip \
  -d "$SDK_ROOT/system-images/android-36/lineage"
```

Use the x86_64 ZIP on an Intel Mac. The resulting directory is one of:

```text
$SDK_ROOT/system-images/android-36/lineage/x86_64
$SDK_ROOT/system-images/android-36/lineage/arm64-v8a
```

Use `x86_64` on an Intel/AMD host and `arm64-v8a` on an ARM64 host. A guest ABI
that does not match the host loses hardware virtualization and can be extremely
slow or unavailable.

## Start from Android Studio

After the script runs, `LineageOS_23_2_KSUNext` appears directly in Android
Studio Device Manager and can be launched there. Recent SDK Tools may not list
a manually extracted custom image on the system-image selection screen; the
script creates a compatible AVD and then redirects its image path for that
reason.

After boot, **KernelSU-Next** is already present in the launcher. Verify the
preinstall, kernel release, and advertised Vulkan features with:

```sh
adb shell pm path com.rifsxd.ksunext
adb shell uname -r
adb shell pm list features | grep -i vulkan
```

If the AVD does not appear in Android Studio, confirm that **SDK Manager >
Android SDK Location** matches the SDK root printed by the installer, then
restart Android Studio.

Verify the release files with `sha256sum -c SHA256SUMS` (or
`shasum -a 256 -c SHA256SUMS` on macOS).
