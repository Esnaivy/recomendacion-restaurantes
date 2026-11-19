#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/app/src/main"
SDK="${ANDROID_SDK_ROOT:-$HOME/android-sdk}"
BT="$SDK/build-tools/35.0.0"
PLATFORM="$SDK/platforms/android-35/android.jar"
OUT="${1:-$ROOT/antojo.apk}"
WORK="$(mktemp -d)"

"$BT/aapt2" compile --dir "$SRC/res" -o "$WORK/res.zip"
"$BT/aapt2" link \
  -o "$WORK/base.apk" \
  -I "$PLATFORM" \
  --manifest "$SRC/AndroidManifest.xml" \
  --java "$WORK/gen" \
  --min-sdk-version 24 \
  --target-sdk-version 35 \
  --version-code 1 \
  --version-name 1.0 \
  -A "$SRC/assets" \
  "$WORK/res.zip"

mkdir -p "$WORK/classes"
javac --release 21 -classpath "$PLATFORM" -d "$WORK/classes" \
  "$WORK/gen/com/esnaivy/antojo/R.java" \
  "$SRC/java/com/esnaivy/antojo/MainActivity.java"

"$BT/d8" --min-api 24 --lib "$PLATFORM" --output "$WORK" "$WORK/classes/com/esnaivy/antojo/"*.class
(cd "$WORK" && zip -q -j base.apk classes.dex)

"$BT/zipalign" -f -p 4 "$WORK/base.apk" "$WORK/aligned.apk"

KS="${ANTOJO_KEYSTORE:-$HOME/.antojo-debug.keystore}"
if [[ ! -f "$KS" ]]; then
  keytool -genkeypair -keystore "$KS" -storepass android -keypass android \
    -alias antojo -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Antojo, O=Esnaivy, C=MX"
fi

"$BT/apksigner" sign \
  --ks "$KS" \
  --ks-pass pass:android \
  --key-pass pass:android \
  --out "$OUT" \
  "$WORK/aligned.apk"

"$BT/apksigner" verify "$OUT"
echo "APK listo: $OUT"
