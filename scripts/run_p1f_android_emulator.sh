#!/usr/bin/env bash
set -euo pipefail

ndk_home="$ANDROID_HOME/ndk/27.2.12479018"
toolchain="$ndk_home/toolchains/llvm/prebuilt/linux-x86_64/bin"

python scripts/p1f_generate_c_fixtures.py runtime/target/p1f/fixture_cases.h
(
  cd runtime
  export CARGO_TARGET_X86_64_LINUX_ANDROID_LINKER="$toolchain/x86_64-linux-android35-clang"
  export CC="$toolchain/x86_64-linux-android35-clang"
  export AR="$toolchain/llvm-ar"
  cargo build --release --locked --target x86_64-linux-android
)

"$toolchain/x86_64-linux-android35-clang" -std=c11 -O2 -Wall -Wextra -Werror \
  -Iruntime/include -Iruntime/target/p1f runtime/hosts/c_smoke.c \
  -Lruntime/target/x86_64-linux-android/release -lmarco_runtime \
  -o runtime/target/p1f/p1f_smoke_android

adb shell 'rm -rf /data/local/tmp/p1f'
adb shell 'mkdir -p /data/local/tmp/p1f'
adb push runtime/target/x86_64-linux-android/release/libmarco_runtime.so /data/local/tmp/p1f/
adb push runtime/target/p1f/p1f_smoke_android /data/local/tmp/p1f/p1f_smoke
adb shell 'chmod 755 /data/local/tmp/p1f/p1f_smoke'
adb shell 'cd /data/local/tmp/p1f && LD_LIBRARY_PATH=. ./p1f_smoke runtime.sqlite' \
  | tee runtime/target/p1f/P1F_REPORT_android.txt
printf 'P1F_ANDROID_API=%s\n' "$(adb shell getprop ro.build.version.sdk)" \
  | tee -a runtime/target/p1f/P1F_REPORT_android.txt
stat -c 'P1F_LIBRARY_BYTES=%s' runtime/target/x86_64-linux-android/release/libmarco_runtime.so \
  | tee -a runtime/target/p1f/P1F_REPORT_android.txt
readelf -d runtime/target/x86_64-linux-android/release/libmarco_runtime.so \
  | tee runtime/target/p1f/P1F_DEPENDENCIES_android.txt
