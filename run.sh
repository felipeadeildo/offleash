#!/usr/bin/env bash
# Sobe as três peças do furbo-local, todas no host network e todas do mesmo
# image, que já traz python3, aiohttp, ffmpeg, go2rtc e a lib nativa do TUTK:
#
#   furbo-bridge   sessão P2P única, credenciais de arquivo, sem cloud
#   furbo-go2rtc   transforma o H.264 cru em RTSP e WebRTC
#   furbo-web      a UI, com proxy que injeta o token
#
# Uso:
#   ./run.sh            só loopback (desktop)
#   ./run.sh tailnet    também no IP do Tailscale, para ver do celular
#   ./run.sh logs       segue o log dos três
#   ./run.sh stop       derruba
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${FURBO_IMAGE:-furbo-bridge:local}"
DATA="${FURBO_DATA_DIR:-$HOME/.furbo-local}"
LIB="/usr/local/lib/libIOTCAPIs_ALL.so"

if [ "${1:-}" = "stop" ]; then
  docker rm -f furbo-bridge furbo-go2rtc furbo-web >/dev/null 2>&1 || true
  echo "parado"
  exit 0
fi
if [ "${1:-}" = "logs" ]; then
  docker logs -f furbo-bridge & docker logs -f furbo-go2rtc & docker logs -f furbo-web &
  wait
  exit 0
fi

# Em loopback nada além da máquina alcança a câmera. No Tailscale, o player e
# a UI ficam no IP da tailnet, que só existe para os seus dispositivos: a LAN
# continua sem ver nada, e o go2rtc não precisa de porta aberta.
case "${1:-local}" in
  local) BIND_HOST="${FURBO_WEB_HOST:-127.0.0.1}" ;;
  tailnet)
    TS_IP="$(tailscale ip -4 2>/dev/null | head -1 || true)"
    if [ -z "$TS_IP" ]; then
      echo "tailscale não devolveu um IPv4; está rodando e logado?" >&2
      exit 1
    fi
    BIND_HOST="${FURBO_WEB_HOST:-$TS_IP}"
    ;;
  *) echo "uso: ./run.sh [local|tailnet|logs|stop]" >&2; exit 2 ;;
esac

if [ ! -f "$HERE/creds.json" ]; then
  echo "falta $HERE/creds.json" >&2
  echo "copie de creds.json.example e preencha com o que está no aparelho." >&2
  exit 1
fi
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "imagem $IMAGE não existe; construa com:" >&2
  echo "  docker build -t $IMAGE ~/Projects/ha-furbo/furbo-bridge/" >&2
  exit 1
fi

chmod +x "$HERE/stream.sh" "$HERE/run.sh"
mkdir -p "$DATA"

# Um token só, gerado uma vez, guardado em $DATA. A senha do RTSP é derivada
# dele, então uma URL de vídeo vazada não dá acesso à API de controle.
TOKEN_FILE="$DATA/api_token"
[ -f "$TOKEN_FILE" ] || openssl rand -hex 32 > "$TOKEN_FILE"
TOKEN="$(cat "$TOKEN_FILE")"
RTSP_PASSWORD="$(printf 'furbo-rtsp:%s' "$TOKEN" | sha256sum | cut -c1-32)"
# Qualidade inicial. A câmera é 2K, então 1440p é o teto real; a UI reescreve
# estes arquivos e o bridge lê na próxima abertura do stream.
for name in quality "quality.default"; do
  [ -f "$DATA/$name" ] || echo "1440p" > "$DATA/$name"
done

ENV=(-e "FURBO_API_TOKEN=$TOKEN" -e "FURBO_P2P_CREDS=/local/creds.json"
     -e "FURBO_QUALITY_FILE=/data/quality" -e "FURBO_AUDIO=${FURBO_AUDIO:-false}"
     -e "FURBO_WEB_HOST=$BIND_HOST" -e "FURBO_WEB_PORT=${FURBO_WEB_PORT:-8080}"
     -e "FURBO_GO2RTC_PLAYER_PORT=1984" -e "RTSP_PASSWORD=$RTSP_PASSWORD"
     -e "FURBO_SESSION_FILE=/data/furbo_session.json"
     -e "GO2RTC_LOG=${FURBO_LOG:-info}"
     -e "GO2RTC_API_LISTEN=$BIND_HOST:1984" -e "GO2RTC_RTSP_LISTEN=$BIND_HOST:8554"
     -e "GO2RTC_WEBRTC_LISTEN=$BIND_HOST:8555" -e "PYTHONPATH=/app")
# Como o seu usuário, para que o que os containers escrevem em $DATA (qualidade,
# sessão, token) saia com o seu dono e continue fácil de editar e apagar.
WHO=(--user "$(id -u):$(id -g)")
MOUNTS=(-v "$HERE:/local:ro" -v "$DATA:/data")

docker rm -f furbo-bridge furbo-go2rtc furbo-web >/dev/null 2>&1 || true

docker run -d --name furbo-bridge --network host --restart unless-stopped \
  "${WHO[@]}" "${MOUNTS[@]}" "${ENV[@]}" --entrypoint python3 "$IMAGE" \
  /local/run_bridge.py serve --token "$TOKEN" --lib "$LIB" \
  --host 127.0.0.1 --port 8791 --interval 30 >/dev/null

docker run -d --name furbo-go2rtc --network host --restart unless-stopped \
  "${WHO[@]}" "${MOUNTS[@]}" "${ENV[@]}" --entrypoint /usr/local/bin/go2rtc "$IMAGE" \
  -config /local/go2rtc.yaml >/dev/null

docker run -d --name furbo-web --network host --restart unless-stopped \
  "${WHO[@]}" "${MOUNTS[@]}" "${ENV[@]}" --entrypoint python3 "$IMAGE" /local/web.py >/dev/null

sleep 2
cat <<INFO

  web    http://$BIND_HOST:${FURBO_WEB_PORT:-8080}/
  rtsp   rtsp://furbo:$RTSP_PASSWORD@$BIND_HOST:8554/furbo
  mpv    mpv 'rtsp://furbo:$RTSP_PASSWORD@$BIND_HOST:8554/furbo'

  ver     ./run.sh logs
  parar   ./run.sh stop

INFO
