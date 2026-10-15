#!/usr/bin/env bash
# Puxa o APK do app Furbo de um Android conectado por adb.
#
#   tools/pull_apk.sh [pasta-de-saida]
#
# Existe porque o pan desta câmera gira até o batente e o payload que o
# upstream usa (`[direção, graus, 0,0,0,0]`) foi deduzido do app sem que o
# autor publicasse o decompilado. Com o APK em mãos a gente lê o
# FurboP2pCmdImplTutkV3 e para de adivinhar.
#
# Serve tanto para adb por cabo quanto por depuração sem fio (`adb connect`).
set -euo pipefail

ADB="${ADB:-$HOME/.local/share/platform-tools/adb}"
PKG="${FURBO_PKG:-com.tomofun.furbo}"
OUT="${1:-$HOME/furbo-apk}"

if [ ! -x "$ADB" ]; then
  echo "adb não está em $ADB" >&2
  echo "baixe com: curl -sSL -o /tmp/pt.zip https://dl.google.com/android/repository/platform-tools-latest-linux.zip && unzip -q -o -d ~/.local/share /tmp/pt.zip" >&2
  exit 1
fi

echo "esperando o aparelho aparecer (ctrl+c para desistir)"
"$ADB" wait-for-device

model="$("$ADB" shell getprop ro.product.model | tr -d '\r')"
android="$("$ADB" shell getprop ro.build.version.release | tr -d '\r')"
version="$("$ADB" shell dumpsys package "$PKG" 2>/dev/null | grep -m1 versionName | cut -d= -f2 | tr -d '\r')"
echo "aparelho: $model  Android $android"
echo "app:      $PKG  versão ${version:-?}"

paths="$("$ADB" shell pm path "$PKG" | tr -d '\r' | sed 's/^package://')"
if [ -z "$paths" ]; then
  echo "o pacote $PKG não está instalado neste aparelho" >&2
  exit 1
fi

mkdir -p "$OUT"
for path in $paths; do
  name="$(basename "$path")"
  printf 'puxando %s ... ' "$name"
  "$ADB" pull "$path" "$OUT/$name" >/dev/null
  printf '%s\n' "$(du -h "$OUT/$name" | cut -f1)"
done

echo
echo "conteúdo de $OUT:"
ls -la "$OUT"
echo
echo "me diga o caminho e eu abro o dex do pan com as ferramentas de Android."
