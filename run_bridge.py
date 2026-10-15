#!/usr/bin/env python3
"""Bridge do Furbo com credenciais locais, sem passar pelo cloud.

O patch precisa ser instalado antes de o servidor subir, e é só por isso que
este arquivo existe em vez de chamar o furbo_p2p.py direto.

Uso:
    run_bridge.py serve --token SEGREDO --lib /usr/local/lib/libIOTCAPIs_ALL.so
"""

from __future__ import annotations

import sys
from pathlib import Path

# Na imagem do bridge os módulos ficam em /app e o bridge original é executado
# de lá. Aqui o script mora em /local, então /app precisa entrar no caminho.
APP = Path("/app")
if APP.is_dir() and str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import static_creds

static_creds.install()

import furbo_p2p  # noqa: E402  (o patch tem que vir antes)

if __name__ == "__main__":
    raise SystemExit(furbo_p2p.main())
