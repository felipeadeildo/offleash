#!/usr/bin/env bash
# Colhe as credenciais P2P do cloud UMA vez, e depois disto nunca mais.
#
#   ./harvest.sh send          manda o código de verificação para o seu e-mail
#   ./harvest.sh code 123456   fecha o login e grava o creds.json
#
# O e-mail e a senha ficam em $FURBO_DATA_DIR/harvest.env (modo 600) para não
# precisar digitar de novo no segundo passo, e para re-colher no futuro. Apague
# o arquivo se preferir digitar toda vez.
#
# Esse arquivo nunca é interpretado pelo shell. Senha tem $, aspas e espaço, e
# source nele quebra com "unbound variable"; o Docker lê o arquivo direto e
# repassa as variáveis como texto.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${FURBO_IMAGE:-furbo-bridge:local}"
DATA="${FURBO_DATA_DIR:-$HOME/.furbo-local}"
CREDS_ENV="$DATA/harvest.env"

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

# Lê um campo sem avaliar o conteúdo.
field() {
  [ -f "$CREDS_ENV" ] || return 0
  sed -n "s/^$1=//p" "$CREDS_ENV" | head -n 1
}

mkdir -p "$DATA"
if [ -z "$(field FURBO_EMAIL)" ] || [ -z "$(field FURBO_PASSWORD)" ]; then
  read -rp 'email do Furbo: ' email
  read -rsp 'senha do Furbo: ' password
  echo
  umask 077
  printf 'FURBO_EMAIL=%s\nFURBO_PASSWORD=%s\n' "$email" "$password" > "$CREDS_ENV"
  chmod 600 "$CREDS_ENV"
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
  --env-file "$CREDS_ENV" \
  --entrypoint python3 \
  -e PYTHONPATH=/app \
  -e "FURBO_SESSION_FILE=/data/furbo_session.json" \
  -e "FURBO_P2P_CREDS=/local/creds.json" \
  -e "FURBO_HARVEST_ENV=$CREDS_ENV" \
  -e "FURBO_DEVICE=${FURBO_DEVICE:-}" \
  -v "$HERE:/local" \
  -v "$DATA:/data" \
  "$IMAGE" "${args[@]}"

if [ "$step" = "code" ]; then
  echo
  echo "próximo passo: ./run.sh    e depois    ./run.sh logs"
  echo "(o e-mail e a senha seguem em $CREDS_ENV, modo 600)"
fi
