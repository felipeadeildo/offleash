# offleash

Stream e controles do **Furbo** direto da sua rede: vídeo em 2K, pan, petisco e
ajustes, sem app e sem nuvem.

O nome é o duplo sentido de sempre, *off the leash* e *offline* na mesma
palavra: a câmera sai da coleira e o vídeo sai da nuvem.

## Por que isso existe

A câmera Furbo é boa. O que está em volta dela é que não. O vídeo passa pelo
cloud, o clipe que você grava sai com marca d'água, o histórico bom fica atrás
de assinatura, o alerta de latido é uma caixa preta que você não pode auditar
nem ajustar, e não existe forma de gravar na sua máquina, plugar no seu NVR ou
automatizar qualquer coisa.

Só que a câmera já está na sua rede, e o que ela faz é software. **A ambição
aqui não é clonar o app: é ser melhor em tudo o que depende de rodar na sua casa
em vez de no servidor de outra pessoa.**

## Onde isso pode ser melhor

| | Furbo | offleash |
| --- | --- | --- |
| latência | relay pelo cloud, segundos | P2P na sua LAN, fração de segundo |
| onde o vídeo vive | servidor deles | a sua rede |
| gravação | clipes no cloud, com marca d'água | arquivo seu, em 2K, sem marca |
| histórico | atrás de assinatura | o seu disco, sem limite artificial |
| alerta de latido | caixa preta no cloud | modelo local, e você vê o que ele faz |
| integração | nenhuma | RTSP, API HTTP, MQTT, webhooks |
| automação | nenhuma | qualquer coisa, porque é software livre |
| quantas pessoas assistindo | uma | uma também, por enquanto: é limite da câmera |

O que ainda não é melhor: o app deles é polido e o nosso é uma página com
botões. Isso é a parte fácil de melhorar.

## Estado

Funciona, e foi medido numa câmera de verdade, não num emulador: **Furbo Mini
360°**, produto `MC0030`, firmware `045`.

| | |
| --- | --- |
| vídeo | 2560x1440, H.264 Main, 15 fps, pela sessão P2P na própria LAN |
| saídas | RTSP, WebRTC e uma web app com player embutido |
| controles | pan, petisco, som do petisco, volume, visão noturna, sensibilidade ao latido, autotracking, autozoom, qualidade |
| sem | app no celular, relay, e nenhuma conta no cloud depois da colheita inicial |

## Arquitetura

```
câmera ──(TUTK/Kalay P2P, DTLS)──▶ bridge ──HTTP──▶ go2rtc ──▶ RTSP / WebRTC
                                     │                        │
                                     └── API local ──▶ web app ──▶ navegador
```

Três processos, todos em containers do mesmo image, todos em `--network host`:

- **bridge** mantém a sessão P2P, lê o H.264 cru e expõe uma API HTTP com o
  estado e os comandos da câmera
- **go2rtc** transforma esse H.264 em RTSP e WebRTC, sob demanda
- **web app** serve a interface e faz de proxy para a API injetando o token, de
  modo que o navegador nunca vê o segredo

## Começando

Precisa de Docker e de uma câmera Furbo já configurada na sua rede.

```sh
git clone https://github.com/felipeadeildo/offleash.git
cd offleash

# a imagem traz python, ffmpeg, go2rtc e a lib nativa do TUTK.
# ela é construída hoje a partir do projeto de onde a camada de bridge vem
# (ver Dependências); o roadmap é trazer esse código para cá.
git clone https://github.com/willbeeching/ha-furbo ~/ha-furbo
docker build -t furbo-bridge:local ~/ha-furbo/furbo-bridge

# colhe as credenciais uma vez (pede e-mail, senha e o código que chega por e-mail)
./harvest.sh send
./harvest.sh code 123456

./run.sh          # só loopback: nada na rede alcança a câmera
./run.sh tailnet  # também no IP do Tailscale, para ver do celular
./run.sh logs
./run.sh stop
```

Depois disso:

| endereço | para quê |
| --- | --- |
| `http://127.0.0.1:8080/` | a web app, com player e controles |
| `rtsp://furbo:<senha>@127.0.0.1:8554/furbo` | mpv, VLC, Home Assistant |

A senha do RTSP é derivada do token da API, não é o token: uma URL de vídeo
vazada dá vídeo e não dá acesso aos controles.

## A credencial, sem rodeios

Esta é a parte que quase nenhum projeto documenta, e é o que decide se o seu
acesso vai funcionar amanhã.

A câmera não aceita conexão local por RTSP nem ONVIF. Todo o vídeo sai por
TUTK/Kalay, um P2P da ThroughTek que autentica nas duas pontas com quatro
valores:

| campo | o que é | muda ao longo do tempo? |
| --- | --- | --- |
| `uid` | o P2PUuid da câmera, 20 caracteres | não |
| `auth_key` | a AuthKey do transporte IOTC, 8 caracteres | **não**, medido em duas colheitas |
| `account` | o P2PAccountId, que no Mini 360 é o próprio MAC da câmera | não |
| `password` | o P2PAccountKey da camada de áudio e vídeo | **sim, é reemitido a cada consulta** |

E daí vem a regra que governa tudo:

> **Só existe uma sessão de vídeo por vez, e cada consulta ao cloud reemite a
> senha, invalidando a anterior.** Abrir a live view no app oficial derruba o
> `offleash`, e usar o `offleash` derruba o app.

O sintoma de senha vencida é enganoso e vale conhecer, porque imita câmera
travada: a sessão de transporte **conecta** (ela usa a `auth_key`, que continua
válida) e o canal de vídeo falha com `avClientStartEx -20011 AV_ER_TIMEOUT`.
Reiniciar a câmera não resolve. Recuperar custa um minuto:

```sh
./harvest.sh send
./harvest.sh code 123456
```

Como a senha é reemitida, quem quiser usar o app junto vai ter de re-colher a
credencial a cada uso. É o preço de não passar pelo cloud no dia a dia.

## O pan: o que o app faz de verdade

O comportamento documentado aqui saiu da leitura do bytecode do app oficial
(versão 7.84.1), e corrige um erro que está em outras implementações.

`FurboP2pCmdImplTutkV3.setRotate` monta seis bytes:

```
[0] = direção        [1] = velocidade   [2..4] = zero   [5] = terceiro argumento
```

Só que o valor do segundo byte é **velocidade**, não graus, e a classe
`LiveViewModel.e2` mostra isso:

```
isHwMini3() ? 50 : 60        # 50 no Mini 3, 60 nos outros modelos
if (soltando) esse valor = 0
```

Ou seja, o app **prende o comando enquanto o botão está pressionado** e manda
`[direção, 0, 0, 0, 0, 0]` **ao soltar**. O zero é o pare. Quem manda o comando
uma vez só, sem o pare, vê a câmera girar até o batente, que foi exatamente o
bug que originou este projeto.

A câmera também reporta a posição no opcode `NOTIFY_PAN` (`0x30007`), que as
implementações existentes ignoram: cinco bytes com um estado e um inteiro de 32
bits, na faixa de `-668` a `+668`. É por ele que dá para medir o movimento de
verdade em vez de adivinhar.

**Como o passo é escolhido aqui:** em **tempo**, não em graus. A taxa medida é
de aproximadamente 110 unidades por segundo na escala da câmera, mas a
conversão disso para graus não foi medida com confiança, então a interface
oferece passos de 0,2 s a 1,6 s em vez de prometer graus.

## Limites conhecidos

- **Uma sessão de vídeo por vez**, e o app oficial compete com este projeto.
- **Petisco e som do petisco** não foram testados no hardware, e o primeiro
  ejetaria um petisco de verdade.
- **Áudio** não foi testado; o codec é escolhido por tentativa.
- **Stream com a câmera sem internet** não foi medido. O SDK resolve o UID pelos
  servidores da ThroughTek e a busca em LAN costuma bastar, mas isso é hipótese.
- **Uma câmera.** O código do bridge suporta várias, a interface ainda não.
- A lib nativa do TUTK é x86_64 ou arm64; não roda em Windows nem em macOS.

## Dependências e licenças

O código deste repositório é MIT. Duas dependências merecem atenção antes de
qualquer uso que não seja pessoal:

1. **A camada de bridge** é hoje importada de
   [`willbeeching/ha-furbo`](https://github.com/willbeeching/ha-furbo) (MIT), com
   as correções deste projeto aplicadas em volta, sem modificar o original. O
   objetivo do roadmap é assumir esse código aqui dentro, mantendo a atribuição.
2. **A biblioteca nativa do TUTK** (`libIOTCAPIs_ALL.so`) é da ThroughTek, e é
   baixada em tempo de build do
   [`mrlt8/docker-wyze-bridge`](https://github.com/mrlt8/docker-wyze-bridge) com
   commit fixo e verificação de SHA-256. Ela **não** está sob a licença MIT
   deste repositório. Para uso pessoal é o caminho que a comunidade usa; para
   distribuir como produto, o correto é licenciar a SDK com a ThroughTek.

## Roadmap

O que falta para ser melhor que o Furbo de verdade, na ordem em que faz sentido
construir.

**Primeiras vitórias**, cada uma é uma coisa que o fabricante não faz:

- [ ] **Gravar em disco**: 2K contínuo ou por evento, sem marca d'água, com
      retenção configurável e um índice de eventos. É o pedido mais óbvio de
      quem já tem a câmera.
- [ ] **Latido local**: detector de áudio rodando aqui, com limiar ajustável e
      sem caixa preta. O Furbo esconde isso atrás de assinatura.
- [ ] **Aviso onde você já está**: Telegram, WhatsApp ou webhook, com o clipe
      anexado, em vez de notificação genérica que só abre o app deles.
- [ ] **Assumir o código**: trazer a camada de bridge para dentro do repo, com
      atribuição, e eliminar a dependência de importação.

**Depois**, quando as primeiras estiverem de pé:

- [ ] **IA na sua máquina**: detecção de cão, pessoa e movimento com modelo
      local, e resumo do dia em linguagem natural a partir dos eventos.
- [ ] **Busca no histórico**: "quando ele latiu ontem à noite" resolvido por
      descrição, em vez de arrastar uma linha do tempo.
- [ ] **Treino com reforço**: petisco com tempo de clique, sessões registradas,
      e o reforço certo na hora certa.
- [ ] **Pan em graus de verdade** e posições salvas ("olhar o sofá").
- [ ] **Várias câmeras** e vários endereços, com uma interface só.
- [ ] **Virar serviço**: sobe com um comando, autentica na interface, faz backup
      da configuração.
- [ ] **Talkback** e agendamento de petisco.

## Créditos

O trabalho pesado de reverter o protocolo é de
[`willbeeching/ha-furbo`](https://github.com/willbeeching/ha-furbo), que leu o
protocolo no app e publicou sob MIT. A leitura do pan neste repositório veio do
APK do app oficial, e as pesquisas públicas que abriram o caminho foram as da
[Somerset Recon](https://www.somersetrecon.com/blog) (partes I a III) e da
[Software Secured](https://www.softwaresecured.com/technical-research) (partes 1
a 6). Para qualquer coisa que o bridge não cubra,
[`Fredde87/cuboai-tutk`](https://github.com/Fredde87/cuboai-tutk) é uma
implementação de TUTK em Python puro e ótima referência.
