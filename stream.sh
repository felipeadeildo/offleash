#!/usr/bin/env bash
# Fonte exec do go2rtc: lê o H.264 da sessão P2P que o bridge já mantém.
#
# Não abre sessão nova de propósito. Uma segunda sessão P2P invalidaria a
# credencial da primeira, porque a câmera reemite a chave a cada nova conexão,
# e as duas acabam falhando em avClientStartEx. go2rtc chama este script sob
# demanda, só enquanto alguém assiste, e mata o grupo quando o último sai.
set -euo pipefail

PORT="${FURBO_API_PORT:-8791}"
TOKEN="${FURBO_API_TOKEN:-}"
DEVICE="${2:-default}"
URL="http://127.0.0.1:${PORT}/api/cameras/${DEVICE}/stream"
# Sem estes limites o ffmpeg chega a ler 5 segundos de vídeo antes de achar o
# parameter set, e isso é atraso visível. O bridge abre o stream já num
# parameter set, então a resposta está nos primeiros bytes.
PROBE=(-probesize 500000 -analyzeduration 1000000)

if [ -z "$TOKEN" ]; then
  echo "[stream] FURBO_API_TOKEN não definido" >&2
  exit 1
fi

if [ "${FURBO_AUDIO:-false}" = "true" ]; then
  # Um stream com as duas trilhas. O bridge muxa usando o timestamp da própria
  # câmera, que é o único relógio que as duas compartilham.
  exec curl -sS -N --fail-with-body -H "Authorization: Bearer ${TOKEN}" \
      "${URL%/stream}/av" \
    | exec ffmpeg -hide_banner -loglevel error -fflags nobuffer \
        "${PROBE[@]}" -f mpegts -i - \
        -c:v copy -c:a aac -rtsp_transport tcp -f rtsp "$1"
fi

exec curl -sS -N --fail-with-body -H "Authorization: Bearer ${TOKEN}" \
    "$URL" \
  | exec ffmpeg -hide_banner -loglevel error -fflags nobuffer \
      "${PROBE[@]}" \
      -f h264 -i - -c copy -rtsp_transport tcp -f rtsp "$1"
