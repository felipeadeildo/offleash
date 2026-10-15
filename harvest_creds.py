#!/usr/bin/env python3
"""Colhe as credenciais P2P do cloud uma única vez e grava o creds.json.

Depois disto o bridge nunca mais fala com o cloud: nem login, nem token, nem
MFA. O preço, e é o ponto todo, é este: cada consulta a
/v5/device/p2p_connection/get reemite a credencial da câmera e invalida a que
ficou gravada aqui, e quem faz essa consulta é a live view do app da Furbo. Ou
seja, usar o app e usar este projeto puxam para lados opostos.

Conta com MFA tem dois passos:

    harvest_creds.py --send           manda o código para o e-mail e para
    harvest_creds.py --code 123456    fecha o login, colhe e grava

O código é o único momento em que um humano é necessário. Depois dele a câmera
é nossa.

Entrada: FURBO_EMAIL e FURBO_PASSWORD (ou um .env no diretório atual).
Saídas: o creds.json em FURBO_P2P_CREDS, e a sessão de cloud é apagada no fim,
salvo com --keep-session.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import furbo_p2p

CREDS = Path(os.environ.get("FURBO_P2P_CREDS") or "creds.json")
FIELDS = ("uid", "auth_key", "account", "password")

# O que cada código do cloud quer dizer, para o erro não chegar cru.
LOGIN_HELP = {
    12002: "e-mail ou senha errados (o endpoint de login usa este código para senha errada)",
    20001: "conta não encontrada, ou o cloud recusou por formato do e-mail",
}


def masked(value: str) -> str:
    """Mostra o suficiente para conferir e não o suficiente para vazar."""
    if not value:
        return "(vazio)"
    if len(value) <= 8:
        return value[:2] + "*" * (len(value) - 2)
    return f"{value[:4]}...{value[-4:]}  ({len(value)} caracteres)"


def usage() -> int:
    print(__doc__)
    return 2


def explain(exc: furbo_p2p.FurboError) -> int:
    """Falha de login é rotina, então vira uma frase e não um traceback."""
    print()
    print(f"o cloud recusou: {exc}")
    if exc.code is None:
        print("  não houve resposta: rede, DNS ou bloqueio no caminho")
    else:
        print("  " + LOGIN_HELP.get(exc.code, "código não mapeado, veja a mensagem acima"))
    env_file = os.environ.get("FURBO_HARVEST_ENV")
    if env_file:
        print()
        print(f"confira o que está em {env_file}, ou apague o arquivo para digitar de novo")
    print("se a conta realmente pedir código por e-mail, use: ./harvest.sh send")
    return 1


async def harvest(send_only: bool, code: str | None, keep_session: bool) -> int:
    await furbo_p2p.cloud_login(code=code, send_only=send_only)
    if send_only:
        print()
        print("Código a caminho do seu e-mail. Feche com:")
        print("    ./harvest.sh code 123456")
        return 0

    credentials = await furbo_p2p.fetch_p2p_credentials(os.environ.get("FURBO_DEVICE") or None)

    camera = {
        "name": credentials["name"],
        "device_id": "default",
        "uid": credentials["uid"],
        "auth_key": credentials["auth_key"],
        "account": credentials["account"],
        "password": credentials["password"],
        "legacy": bool(credentials["legacy"]),
        "device_token": credentials["device_token"],
        "product": credentials["product"],
        "proto": credentials["proto"],
    }
    CREDS.write_text(json.dumps({"cameras": [camera]}, indent=2) + "\n")
    CREDS.chmod(0o600)

    print()
    print(f"credenciais em {CREDS}, modo {oct(CREDS.stat().st_mode)[-3:]}")
    for field in FIELDS:
        print(f"  {field:9} {masked(credentials[field])}")
    print(f"  camera    {credentials['name']} ({credentials['product']}, {credentials['proto']})")
    if credentials["legacy"]:
        print()
        print("  O cloud não devolveu AuthKey, então esta câmera é do caminho legado:")
        print("  ela autentica pelo DeviceToken. Já está gravado no creds.json.")

    session_files = [path for path in (furbo_p2p.SESSION_FILE, furbo_p2p.PENDING_FILE) if path.exists()]
    if keep_session:
        print()
        print("sessão de cloud mantida em " + ", ".join(str(p) for p in session_files))
    else:
        for path in session_files:
            path.unlink()
        gone = ", ".join(path.name for path in session_files) or "nada a apagar"
        print()
        print(f"sessão de cloud apagada ({gone}): nenhum token vosso ficou no disco.")

    print()
    print("Daqui para frente, não abra a live view no app da Furbo. Cada vez que")
    print("o app pede credenciais ao cloud, as daqui são reemitidas e morrem.")
    print("Se isso acontecer, basta rodar ./harvest.sh send outra vez.")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    keep_session = "--keep-session" in argv
    argv = [arg for arg in argv if arg != "--keep-session"]
    send_only = "--send" in argv
    code = argv[argv.index("--code") + 1] if "--code" in argv else None
    if not send_only and code is None:
        return usage()
    try:
        return asyncio.run(harvest(send_only, code, keep_session))
    except furbo_p2p.FurboError as exc:
        if os.environ.get("FURBO_DEBUG"):
            raise
        return explain(exc)


if __name__ == "__main__":
    raise SystemExit(main())
