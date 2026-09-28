#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
project="$repo_root/runtime/hosts/ios/MarcoRuntimeSmoke.xcodeproj"
derived_data="$repo_root/runtime/target/ios-derived"
app="$derived_data/Build/Products/Release-iphonesimulator/MarcoRuntimeSmoke.app"
mkdir -p "$repo_root/runtime/target/p1f"

xcodebuild \
  -project "$project" \
  -scheme MarcoRuntimeSmoke \
  -configuration Release \
  -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath "$derived_data" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  build

simulator_info="$(xcrun simctl list devices available -j | python3 -c '
import json,sys
devices=json.load(sys.stdin)["devices"]
available=[d for runtime in devices for d in runtime if d.get("isAvailable") and d["name"].startswith("iPhone")]
if not available: raise SystemExit("No available iPhone simulator")
booted=next((d for d in available if d.get("state")=="Booted"), None)
device=booted or available[0]
print(device["udid"],device["state"])
')"
device_id="${simulator_info%% *}"
device_state="${simulator_info##* }"
if [[ "$device_state" != "Booted" ]]; then
  xcrun simctl boot "$device_id"
fi
xcrun simctl bootstatus "$device_id" -b
xcrun simctl install "$device_id" "$app"
xcrun simctl launch "$device_id" org.box5789.marco-runtime-smoke

app_data="$(xcrun simctl get_app_container "$device_id" org.box5789.marco-runtime-smoke data)"
report="$app_data/Documents/p1f-report.json"
for attempt in $(seq 1 30); do
  if [[ -f "$report" ]]; then break; fi
  sleep 1
done
test -f "$report"
cat "$report"
printf 'P1F_IOS_APP_BYTES=%s\n' "$(du -sk "$app" | awk '{print $1 * 1024}')" | tee "$repo_root/runtime/target/p1f/P1F_RESOURCE_ios.txt"
cp "$report" "$repo_root/runtime/target/p1f/P1F_REPORT_ios.json"
