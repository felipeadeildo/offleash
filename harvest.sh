#!/usr/bin/env bash
# Colhe as credenciais P2P do cloud UMA vez, e depois disto nunca mais.
#
#   ./harvest.sh send          manda o código de verificação para o seu e-mail
#   ./harvest.sh code 123456   fecha o login e grava o creds.json
#
# O e-mail e a senha ficam em $FURBO_DATA_DIR/harvest.env (modo 600) para não
# precisar digitar de novo no segundo passo, e para re-colher no futuro. Apague
# o arquivo se preferir digitar toda vez.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${FURBO_IMAGE:-furbo-bridge:local}"
DATA="${FURBO_DATA_DIR:-$HOME/.furbo-local}"

step="${1:-}"
case "$step" in
  send) : ;;
  code)
    if [ -z "${2:-}" ]; then
      echo "uso: ./harvest.sh code NNNNNN" >&2
      exit 2
    fi
    ;;
  *)
    echo "uso: ./harvest.sh send | ./harvest.sh code NNNNNN" >&2
    exit 2
    ;;
esac

mkdir -p "$DATA"
if [ -f "$DATA/harvest.env" ]; then
  # shellcheck disable=SC1090
  . "$DATA/harvest.env"
fi
if [ -z "${FURBO_EMAIL:-}" ] || [ -z "${FURBO_PASSWORD:-}" ]; then
  read -rp 'email do Furbo: ' FURBO_EMAIL
  read -rsp 'senha do Furbo: ' FURBO_PASSWORD
  echo
  umask 077
  printf 'FURBO_EMAIL=%s\nFURBO_PASSWORD=%s\n' "$FURBO_EMAIL" "$FURBO_PASSWORD" > "$DATA/harvest.env"
  chmod 600 "$DATA/harvest.env"
fi

if [ "$step" = "send" ]; then
  args=(/local/harvest_creds.py --send)
else
  args=(/local/harvest_creds.py --code "$2")
fi

# Roda como o seu usuário para que o creds.json no diretório deste projeto
# saia com o seu dono, e não com root.
docker run --rm --network host \
  --user "$(id -u):$(id -g)" \
  --entrypoint python3 \
  -e PYTHONPATH=/app \
  -e "FURBO_EMAIL=$FURBO_EMAIL" \
  -e "FURBO_PASSWORD=$FURBO_PASSWORD" \
  -e "FURBO_SESSION_FILE=/data/furbo_session.json" \
  -e "FURBO_P2P_CREDS=/local/creds.json" \
  -e "FURBO_HARVEST_ENV=/data/harvest.env" \
  -e "FURBO_DEVICE=${FURBO_DEVICE:-}" \
  -v "$HERE:/local" \
  -v "$DATA:/data" \
  "$IMAGE" "${args[@]}"

if [ "$step" = "code" ]; then
  echo
  echo "próximo passo: ./run.sh    e depois    ./run.sh logs"
  echo "(o e-mail e a senha seguem em $DATA/harvest.env, modo 600)"
fi
