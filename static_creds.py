"""Credenciais P2P de arquivo local, para o bridge rodar sem cloud.

O bridge original pega as credenciais em /v5/device/p2p_connection/get, e o
token da conta precisa ser renovado com código por e-mail. Aqui a mesma
estrutura de dicionário vem de creds.json, e as duas funções que o bridge usa
para descobrir câmeras são substituídas antes de o servidor subir. Do ponto de
vista do bridge, nada muda: ele não sabe que a resposta não veio da internet.

Os quatro valores de cada câmera (uid, auth_key, account, password) saem do
próprio aparelho. O README explica como lê-los.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import furbo_p2p as fp

DEFAULT_FILE = Path(__file__).resolve().with_name("creds.json")
REQUIRED = ("uid", "auth_key", "account", "password")


def creds_path() -> Path:
    return Path(os.environ.get("FURBO_P2P_CREDS") or DEFAULT_FILE)


def _camera(raw: dict, index: int) -> dict:
    """Valida e normaliza uma câmera. A forma é a que o bridge espera."""
    missing = [key for key in REQUIRED if not raw.get(key)]
    if missing:
        raise SystemExit(f"{creds_path()}: câmera {index} sem {', '.join(missing)}")
    return {
        "name": str(raw.get("name") or f"camera{index + 1}"),
        "device_id": str(raw.get("device_id") or "default"),
        "uid": str(raw["uid"]),
        "auth_key": str(raw["auth_key"]),
        "account": str(raw["account"]),
        "password": str(raw["password"]),
        "legacy": bool(raw.get("legacy", False)),
        "device_token": str(raw.get("device_token") or ""),
        "product": str(raw.get("product") or ""),
        "proto": str(raw.get("proto") or "v3"),
    }


def load() -> list[dict]:
    path = creds_path()
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        raise SystemExit(
            f"{path} não existe. Copie creds.json.example para creds.json e "
            "preencha com o que está no aparelho (veja o README)."
        ) from None
    except ValueError as exc:
        raise SystemExit(f"{path} não é JSON válido: {exc}") from None
    cameras = data.get("cameras") if isinstance(data, dict) else None
    listed = cameras if cameras else [data]
    if not isinstance(listed, list):
        raise SystemExit(f"{path}: 'cameras' precisa ser uma lista")
    return [_camera(raw, index) for index, raw in enumerate(listed)]


def install() -> None:
    """Substitui no módulo do bridge as duas funções que falariam com o cloud."""

    async def fetch_p2p_credentials(device_id: str | None = None) -> dict:
        cameras = load()
        if device_id:
            for camera in cameras:
                if camera["device_id"] == device_id:
                    return camera
            known = ", ".join(c["device_id"] for c in cameras)
            raise SystemExit(f"device_id {device_id} não está em {creds_path()}; tem: {known}")
        if len(cameras) > 1:
            known = ", ".join(c["device_id"] for c in cameras)
            raise SystemExit(f"{len(cameras)} câmeras em {creds_path()}; use --device: {known}")
        return cameras[0]

    def session_devices() -> list[dict[str, str]]:
        return [
            {"device_id": c["device_id"], "name": c["name"], "product": c["product"]}
            for c in load()
        ]

    fp.fetch_p2p_credentials = fetch_p2p_credentials
    fp.session_devices = session_devices

    cameras = load()
    names = ", ".join(f"{c['name']} ({c['device_id']}, {c['proto']})" for c in cameras)
    print(f"[local] credenciais de {creds_path()}, sem cloud: {names}", file=sys.stderr)
