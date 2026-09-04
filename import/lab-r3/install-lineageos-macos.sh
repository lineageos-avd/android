#!/usr/bin/env bash

set -Eeuo pipefail

AVD_NAME="${AVD_NAME:-LineageOS_23_2_KSUNext}"
SDK_ROOT="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-$HOME/Library/Android/sdk}}"
DISPLAY_WIDTH="${DISPLAY_WIDTH:-1080}"
DISPLAY_HEIGHT="${DISPLAY_HEIGHT:-2400}"
DISPLAY_DENSITY="${DISPLAY_DENSITY:-420}"
FORCE_REINSTALL="${FORCE_REINSTALL:-0}"
WIPE_AVD_DATA="${WIPE_AVD_DATA:-auto}"
REQUIRED_IMAGE_REVISION="3"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_INSTALLED=0
RESET_AVD_DATA=0

info() {
  printf '\n==> %s\n' "$*"
}

die() {
  printf '\n错误: %s\n' "$*" >&2
  exit 1
}

set_ini() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp="${file}.tmp.$$"

  awk -F= -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    $1 == key { print key "=" value; found = 1; next }
    { print }
    END { if (!found) print key "=" value }
  ' "$file" > "$tmp"
  mv "$tmp" "$file"
}

find_zip() {
  local name="$1"
  local candidate

  if [[ $# -ge 2 && -n "$2" ]]; then
    [[ -f "$2" ]] || die "找不到 ZIP: $2"
    printf '%s\n' "$2"
    return
  fi

  for candidate in \
    "$SCRIPT_DIR/$name" \
    "$PWD/$name" \
    "$HOME/Downloads/$name"; do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  done

  die "找不到 $name。请把脚本和 ZIP 放在同一目录，或把 ZIP 路径作为第一个参数。"
}

[[ "$(uname -s)" == "Darwin" ]] || die "此脚本只能在 macOS 上运行。"

case "$WIPE_AVD_DATA" in
  auto|0|1) ;;
  *) die "WIPE_AVD_DATA 只能是 auto、0 或 1。" ;;
esac

case "$(uname -m)" in
  arm64)
    ABI="arm64-v8a"
    ZIP_NAME="lineage-23.2-ranchu-arm64-v8a-linux-6.12-ksunext-v3.3.0.zip"
    ;;
  x86_64)
    ABI="x86_64"
    ZIP_NAME="lineage-23.2-ranchu-x86_64-linux-6.12-ksunext-v3.3.0.zip"
    ;;
  *)
    die "不支持的 Mac 架构: $(uname -m)"
    ;;
esac

IMAGE_BASE="$SDK_ROOT/system-images/android-36/lineage"
IMAGE_DIR="$IMAGE_BASE/$ABI"
INSTALLED_REVISION=""

if [[ -f "$IMAGE_DIR/source.properties" ]]; then
  INSTALLED_REVISION="$(awk -F= '$1 == "Pkg.Revision" { print $2; exit }' \
    "$IMAGE_DIR/source.properties")"
fi

if [[ "$INSTALLED_REVISION" == "$REQUIRED_IMAGE_REVISION" && \
      "$FORCE_REINSTALL" != "1" ]]; then
  ZIP_PATH=""
else
  ZIP_PATH="$(find_zip "$ZIP_NAME" "${1:-}")"
fi

info "架构: $ABI"
info "Android SDK: $SDK_ROOT"
if [[ -n "$ZIP_PATH" ]]; then
  info "镜像 ZIP: $ZIP_PATH"
fi

mkdir -p "$IMAGE_BASE"

if [[ -d "$IMAGE_DIR" && \
      ( "$FORCE_REINSTALL" == "1" || \
        "$INSTALLED_REVISION" != "$REQUIRED_IMAGE_REVISION" ) ]]; then
  info "正在移除旧的系统镜像 (revision ${INSTALLED_REVISION:-unknown})"
  rm -rf "$IMAGE_DIR"
fi

if [[ ! -f "$IMAGE_DIR/source.properties" ]]; then
  info "正在安装 LineageOS 系统镜像"
  ditto -x -k "$ZIP_PATH" "$IMAGE_BASE"
  IMAGE_INSTALLED=1
else
  info "系统镜像已经解压，跳过解压"
fi

for required in source.properties system.img vendor.img ramdisk.img kernel-ranchu; do
  [[ -f "$IMAGE_DIR/$required" ]] || die "镜像不完整，缺少: $IMAGE_DIR/$required"
done

INSTALLED_REVISION="$(awk -F= '$1 == "Pkg.Revision" { print $2; exit }' \
  "$IMAGE_DIR/source.properties")"
[[ "$INSTALLED_REVISION" == "$REQUIRED_IMAGE_REVISION" ]] || \
  die "镜像 revision 为 ${INSTALLED_REVISION:-unknown}，需要 revision $REQUIRED_IMAGE_REVISION。请使用最新 ZIP。"

AVDMANAGER="$SDK_ROOT/cmdline-tools/latest/bin/avdmanager"
SDKMANAGER="$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"

if [[ ! -x "$AVDMANAGER" ]]; then
  AVDMANAGER="$(find "$SDK_ROOT/cmdline-tools" -type f -path '*/bin/avdmanager' -perm -111 -print 2>/dev/null | head -n 1 || true)"
  [[ -n "$AVDMANAGER" ]] || die "缺少 Android SDK Command-line Tools (latest)，请先在 SDK Manager > SDK Tools 中安装。"
  SDKMANAGER="$(dirname "$AVDMANAGER")/sdkmanager"
fi

[[ -x "$SDKMANAGER" ]] || die "找不到 sdkmanager: $SDKMANAGER"
[[ -x "$SDK_ROOT/emulator/emulator" ]] || die "缺少 Android Emulator，请在 SDK Manager > SDK Tools 中安装。"

if [[ ! -f "$SDK_ROOT/platforms/android-36/android.jar" ]]; then
  info "正在安装 Android SDK Platform 36"
  "$SDKMANAGER" "platforms;android-36" || \
    printf '警告: Platform 36 安装失败；仍会继续创建模拟器。\n' >&2
fi

AVD_DIR="$HOME/.android/avd/${AVD_NAME}.avd"
AVD_INI="$HOME/.android/avd/${AVD_NAME}.ini"
EXPECTED_IMAGE="system-images/android-36/lineage/$ABI/"

if [[ -f "$AVD_DIR/config.ini" ]] && \
   grep -Fqx "image.sysdir.1=$EXPECTED_IMAGE" "$AVD_DIR/config.ini"; then
  if [[ "$WIPE_AVD_DATA" == "1" || \
        ( "$WIPE_AVD_DATA" == "auto" && "$IMAGE_INSTALLED" -eq 1 ) ]]; then
    RESET_AVD_DATA=1
    info "AVD 已存在；将清除旧用户数据并执行冷启动"
  else
    info "AVD 已存在并已指向 LineageOS，保留现有用户数据"
  fi
else
  info "正在创建 AVD: $AVD_NAME"

  BASE_PACKAGE="$("$SDKMANAGER" --list_installed 2>/dev/null | awk -F '|' -v abi="$ABI" '
    $1 ~ /^[[:space:]]*system-images;/ && index($1, abi) && $1 !~ /;lineage;/ {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $1)
      print $1
      exit
    }
  ')"

  if [[ -z "$BASE_PACKAGE" ]]; then
    BASE_PACKAGE="system-images;android-35;default;$ABI"
    info "没有可用的基础镜像，正在安装 $BASE_PACKAGE"
    "$SDKMANAGER" "$BASE_PACKAGE"
  fi

  printf 'no\n' | "$AVDMANAGER" create avd \
    --force \
    --name "$AVD_NAME" \
    --package "$BASE_PACKAGE"

  [[ -f "$AVD_DIR/config.ini" ]] || die "AVD 创建失败: $AVD_DIR/config.ini 不存在"
  [[ -f "$AVD_INI" ]] || die "AVD 创建失败: $AVD_INI 不存在"
  RESET_AVD_DATA=1
fi

set_ini "$AVD_DIR/config.ini" "image.sysdir.1" "$EXPECTED_IMAGE"
set_ini "$AVD_DIR/config.ini" "target" "android-36"
set_ini "$AVD_DIR/config.ini" "tag.id" "lineage"
set_ini "$AVD_DIR/config.ini" "tag.display" "LineageOS"
set_ini "$AVD_DIR/config.ini" "hw.mainKeys" "no"
set_ini "$AVD_DIR/config.ini" "hw.gpu.enabled" "yes"
set_ini "$AVD_DIR/config.ini" "hw.gpu.mode" "host"
set_ini "$AVD_DIR/config.ini" "hw.lcd.width" "$DISPLAY_WIDTH"
set_ini "$AVD_DIR/config.ini" "hw.lcd.height" "$DISPLAY_HEIGHT"
set_ini "$AVD_DIR/config.ini" "hw.lcd.density" "$DISPLAY_DENSITY"
set_ini "$AVD_DIR/config.ini" "hw.cpu.ncore" "4"
set_ini "$AVD_DIR/config.ini" "hw.ramSize" "4096"
set_ini "$AVD_DIR/config.ini" "vm.heapSize" "512"
set_ini "$AVD_DIR/config.ini" "disk.dataPartition.size" "8G"
set_ini "$AVD_DIR/config.ini" "skin.dynamic" "yes"
set_ini "$AVD_DIR/config.ini" "showDeviceFrame" "no"
set_ini "$AVD_DIR/config.ini" "fastboot.forceColdBoot" "yes"
set_ini "$AVD_INI" "target" "android-36"

info "AVD 已就绪: $AVD_NAME"
printf '镜像路径: %s\n' "$IMAGE_DIR"
printf '默认分辨率: %sx%s @ %s dpi\n' "$DISPLAY_WIDTH" "$DISPLAY_HEIGHT" "$DISPLAY_DENSITY"
printf 'KernelSU-Next Manager 已预装，无需 adb install。\n'

EMULATOR_ARGS=(
  -avd "$AVD_NAME"
  -gpu host
  -no-snapshot-load
)

if [[ "$RESET_AVD_DATA" -eq 1 ]]; then
  EMULATOR_ARGS+=(-wipe-data)
fi

info "正在启动 Android Emulator"
exec "$SDK_ROOT/emulator/emulator" "${EMULATOR_ARGS[@]}"
