"""Pan pelo método do app: prender o comando e soltar.

O upstream manda UM comando `[direção, graus, 0, 0, 0, 0]` e trata isso como um
giro de `graus`. Não é. No APK 7.84.1, `LiveViewModel.e2` monta assim:

    isHwMini3() ? 50 : 60          <- segundo byte, por modelo
    if (soltando) segundo byte = 0
    PlayerHelper.m2(direção, esse_valor, 0)
    -> FurboP2pCmdImplTutkV3.setRotate
       payload = [direção, valor, 0, 0, 0, valor_do_terceiro_argumento]

O segundo byte é velocidade e o zero é o pare: o app segura o comando enquanto o
botão está pressionado e manda o pare ao soltar. Sem o pare, o comando gira até
o batente, que é o que fazia um toque virar varredura completa.

Medido nesta câmera (Mini 360, MC0030): ~110 unidades por segundo, e a faixa
±668 casa com os 360 graus, o que dá ~30 graus por segundo de rotação real.
"""

from __future__ import annotations

import os
import time

import furbo_bridge as fb
import furbo_p2p as fp

# O valor que o app manda no Mini 3. Nos outros modelos é 60.
SPEED = int(os.environ.get("FURBO_PAN_SPEED", "50"))
# Conversão graus -> tempo de aperto. ATENÇÃO: é estimativa, não medição firme.
#
# O que está medido: ~110 unidades por segundo na escala da própria câmera
# (a posição que ela reporta em NOTIFY_PAN vai de -668 a +668).
#
# O que NÃO está medido: quantos graus são essas unidades. Duas leituras de
# imagem se contradizem entre si e com 360 graus: um toque de 1,0 s andou 86 px,
# o que daria uma abertura horizontal de 220 graus, impossível para uma lente de
# 126. Com a unidade valendo um décimo de grau, a faixa dá ~134 graus e a
# rotação ~11 graus por segundo, que é o valor adotado aqui.
#
# Consequência prática: na UI o passo é escolhido em TEMPO, não em graus, e esta
# constante só converte para o que a API do bridge espera.
DEGREES_PER_SECOND = float(os.environ.get("FURBO_PAN_DEGREES_PER_SECOND", "11"))
# 0,1 s é o mínimo que move de fato; 3 s é o teto para segurar o lock do bridge.
MIN_HOLD = float(os.environ.get("FURBO_PAN_MIN_HOLD", "0.1"))
MAX_HOLD = float(os.environ.get("FURBO_PAN_MAX_HOLD", "3"))


def hold_seconds(degrees: int) -> float:
    return min(max(degrees / DEGREES_PER_SECOND, MIN_HOLD), MAX_HOLD)


def pan(self, direction: str, degrees: int) -> None:
    """Prende na direção por tempo proporcional aos graus, e solta."""
    with self._lock:
        p2p = self._ensure()
        if p2p.proto != "v3":
            raise fb.BridgeUnavailable("pan is only available on V3 cameras")
        forward = fp.PAN_DIR[direction]
        p2p.send(fp.CMD3["PAN"], bytes([forward, SPEED, 0, 0, 0, 0]))
        time.sleep(hold_seconds(degrees))
        p2p.send(fp.CMD3["PAN"], bytes([forward, 0, 0, 0, 0, 0]))
        p2p.drain(1.0)


def install() -> None:
    fb.P2PWorker.pan = pan
