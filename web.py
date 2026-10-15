#!/usr/bin/env python3
"""Web app local do Furbo: player, controles e nenhum cloud no caminho.

Serve a página e faz de proxy para a API do bridge injetando o bearer token.
O navegador nunca vê o token, e nenhuma requisição sai para a internet.

O vídeo não passa por aqui: a página aponta um iframe para a própria página de
player do go2rtc (WebRTC). O iframe é cross-origin, o que é permitido, e assim
não precisamos reimplementar o WebSocket de sinalização nem tocar no H.264.

Escuta em loopback por padrão. Para ver do celular use a interface do
Tailscale: FURBO_WEB_HOST=100.x.y.z, e o mesmo endereço no listener do go2rtc
(o run.sh tem um modo para isso). Nada precisa ficar exposto na LAN.
"""

from __future__ import annotations

import os
from pathlib import Path

from aiohttp import ClientError, ClientSession, web

HERE = Path(__file__).resolve().parent
BRIDGE = os.environ.get("FURBO_BRIDGE_URL", "http://127.0.0.1:8791")
GO2RTC_PORT = os.environ.get("FURBO_GO2RTC_PLAYER_PORT", "1984")
STREAM = os.environ.get("FURBO_STREAM_NAME", "furbo")
TOKEN = os.environ.get("FURBO_API_TOKEN", "")
HOST = os.environ.get("FURBO_WEB_HOST", "127.0.0.1")
PORT = int(os.environ.get("FURBO_WEB_PORT", "8080"))
# Do que o bridge devolve, só isto interessa repassar para o navegador.
PASS_HEADERS = {"content-type", "cache-control"}


async def page(request: web.Request) -> web.FileResponse:
    return web.FileResponse(HERE / "static" / "index.html")


async def config(request: web.Request) -> web.Response:
    """O endereço do player, no mesmo host por onde a página foi aberta.

    Assim a UI funciona tanto em 127.0.0.1 quanto pelo IP do Tailscale, sem
    configuração: quem abriu a página é quem diz onde o go2rtc está.
    """
    host = request.host.split(":")[0]
    return web.json_response(
        {"player": f"http://{host}:{GO2RTC_PORT}/stream.html?src={STREAM}", "stream": STREAM}
    )


async def api(request: web.Request) -> web.StreamResponse:
    """Repassa /api/** para o bridge com o token, sem bufferizar o vídeo."""
    url = f"{BRIDGE}/api/{request.match_info['tail']}"
    body = await request.read()
    headers = {"Authorization": f"Bearer {TOKEN}"}
    try:
        async with request.app["http"].request(
            request.method, url, params=request.query, data=body or None, headers=headers
        ) as upstream:
            response = web.StreamResponse(
                status=upstream.status,
                headers={
                    key: value
                    for key, value in upstream.headers.items()
                    if key.lower() in PASS_HEADERS
                },
            )
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(65536):
                await response.write(chunk)
            await response.write_eof()
            return response
    except ClientError as exc:
        return web.json_response(
            {"error": "bridge_fora_do_ar", "detail": f"{exc}"}, status=502
        )


async def on_startup(app: web.Application) -> None:
    app["http"] = ClientSession()


async def on_cleanup(app: web.Application) -> None:
    await app["http"].close()


def main() -> None:
    if not TOKEN:
        raise SystemExit("FURBO_API_TOKEN é obrigatório: a API controla a câmera")
    app = web.Application()
    app.add_routes(
        [
            web.get("/", page),
            web.get("/config.json", config),
            web.route("*", "/api/{tail:.*}", api),
        ]
    )
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    print(f"[web] http://{HOST}:{PORT}/   bridge={BRIDGE}  player=:{GO2RTC_PORT}")
    web.run_app(app, host=HOST, port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
