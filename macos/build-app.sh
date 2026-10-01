#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
app_bundle=${1:?usage: macos/build-app.sh /tmp/MarcoTranslatorP2.app}
target_dir=${CARGO_TARGET_DIR:-"$repo_root/runtime/target"}
runtime_library="$target_dir/release/libmarco_runtime.a"
MACOSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-14.0}
CARGO_PROFILE_RELEASE_DEBUG=${CARGO_PROFILE_RELEASE_DEBUG:-0}
export MACOSX_DEPLOYMENT_TARGET
export CARGO_PROFILE_RELEASE_DEBUG

if [ -e "$app_bundle" ]; then
    printf 'Refusing to overwrite existing app bundle: %s\n' "$app_bundle" >&2
    exit 2
fi

if [ -n "${CARGO:-}" ]; then
    "$CARGO" build --manifest-path "$repo_root/runtime/Cargo.toml" --release --locked
else
    cargo build --manifest-path "$repo_root/runtime/Cargo.toml" --release --locked
fi
test -f "$runtime_library"

case "$(uname -m)" in
    arm64|x86_64) host_arch=$(uname -m) ;;
    *) printf 'Unsupported macOS architecture: %s\n' "$(uname -m)" >&2; exit 2 ;;
esac

mkdir -p "$app_bundle/Contents/MacOS"
cp "$repo_root/macos/Resources/Info.plist" "$app_bundle/Contents/Info.plist"
"${SWIFTC:-swiftc}" \
    -swift-version 5 \
    -O \
    -target "$host_arch-apple-macosx14.0" \
    -import-objc-header "$repo_root/runtime/include/marco_runtime.h" \
    "$repo_root/macos/Sources/CaptureCore.swift" \
    "$repo_root/macos/Sources/RegionCropView.swift" \
    "$repo_root/macos/Sources/MarcoCaptureApp.swift" \
    "$runtime_library" \
    -framework AppKit \
    -framework CoreGraphics \
    -framework ScreenCaptureKit \
    -framework Vision \
    -o "$app_bundle/Contents/MacOS/MarcoTranslatorP2"
/usr/bin/codesign --force --sign - "$app_bundle"
/usr/bin/codesign --verify --deep --strict "$app_bundle"
printf 'Built %s\n' "$app_bundle"
