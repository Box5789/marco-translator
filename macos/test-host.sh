#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target_dir=${CARGO_TARGET_DIR:-"$repo_root/runtime/target"}
runtime_library="$target_dir/release/libmarco_runtime.a"
test_binary=${P2_HOST_TEST_BINARY:-"${TMPDIR:-/tmp}/marco-translator-p2-host-checks-$$"}
MACOSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET:-14.0}
CARGO_PROFILE_RELEASE_DEBUG=${CARGO_PROFILE_RELEASE_DEBUG:-0}
export MACOSX_DEPLOYMENT_TARGET
export CARGO_PROFILE_RELEASE_DEBUG
trap 'rm -f "$test_binary"' EXIT HUP INT TERM

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

"${SWIFTC:-swiftc}" \
    -swift-version 5 \
    -target "$host_arch-apple-macosx14.0" \
    -import-objc-header "$repo_root/runtime/include/marco_runtime.h" \
    "$repo_root/macos/Sources/CaptureCore.swift" \
    "$repo_root/macos/Tests/HostChecks.swift" \
    "$runtime_library" \
    -framework AppKit \
    -framework CoreGraphics \
    -framework Vision \
    -o "$test_binary"
"$test_binary"
