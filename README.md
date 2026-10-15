# furbo-local

Stream e controles do Furbo na sua rede, sem app e sem cloud: o bridge roda a
sessão P2P local, o go2rtc publica em RTSP e WebRTC, e a web app dá player e
botões. Nada de conta, nada de MFA, nada saindo para a Furbo.

```
Furbo Mini 360 ──(TUTK P2P, DTLS-PSK)──▶ furbo-bridge ──HTTP──▶ go2rtc
                                              │                    │
                                              └── /api/** ──▶ furbo-web ──▶ navegador
                                                                   │
                                                     rtsp://…:8554/furbo ──▶ mpv, VLC, HA
```

## A credencial, sem rodeios

Não dá para fugir dela, e vale entender por quê antes de abrir a câmera.

O vídeo não passa por nenhum protocolo aberto que dê para interceptar. Ele sai
por TUTK/Kalay, um P2P da ThroughTek que autentica nas duas pontas com uma
chave de 8 caracteres (o `AuthKey`) e um par conta/senha da camada de áudio e
vídeo, tudo dentro de um handshake DTLS-PSK com a chave do fabricante
compilada no binário. Não é texto claro em lugar nenhum, então sniffar não
resolve, e não há como derivar de outro valor.

Esses quatro valores existem em três lugares:

| Onde | O que tem | Serve? |
| --- | --- | --- |
| Cloud da Furbo (`/v5/device/p2p_connection/get`) | tudo, mas reemitido a cada consulta | precisa de conta e MFA |
| Flash da câmera (`/mnt/flash/furbo/p2p_auth.json`) | `authKey` e `password` | é o que queremos |
| Memória do app no celular | o que o cloud mandou | morre quando o cloud reemite |

Ou seja: para ser independente do cloud, os valores têm de sair da câmera, uma
vez. Depois disso, nada mais precisa de internet.

O que já não precisamos buscar em lugar nenhum está no código do bridge, e é o
que mais assusta: a `License Key` do vendor, que é o que habilita a SDK 4.x do
TUTK, está em `furbo_p2p.py` como constante, extraída do app. Todo o resto do
protocolo (opcodes de IOCTL, comandos de pan, de petisco, mapeamento de
qualidade por versão de produto) também já está implementado e testado.

## Os dois jeitos de conseguir os quatro valores

### Do cloud, uma vez (mais rápido)

```sh
./harvest.sh send          # digita e-mail e senha, e recebe o código por e-mail
./harvest.sh code 123456   # fecha o login, colhe e grava o creds.json
```

O script loga, chama `/v5/device/p2p_connection/get`, grava os quatro valores e
**apaga a sessão de cloud no fim**: nenhum token seu fica no disco. Ele termina
com o aviso que é o coração de todo esse assunto:

> Daqui para frente, não abra a live view no app da Furbo. Cada vez que o app
> pede credenciais ao cloud, as daqui são reemitidas e as gravadas morrem.

Se isso acontecer, é só rodar `./harvest.sh send` outra vez. O e-mail e a senha
ficam em `$FURBO_DATA_DIR/harvest.env` (modo 600), então re-colher custa um
código novo do e-mail e mais nada.

### Do aparelho, sem cloud nenhum

É o caminho de baixo, e exige abrir a câmera. Serve para quando você quiser
independência total, ou se a conta não deixar mais o login entrar.

## O que quebra a credencial, e o que não quebra

| Quebra | Não quebra |
| --- | --- |
| Abrir a live view no app | Reiniciar a câmera, o PC, ou os containers |
| Reconfigurar a rede da câmera pelo app | A câmera ficar sem internet |
| Reset de fábrica, ou firmware que apague o `p2p_auth.json` | O tempo passar |

A primeira linha da coluna da esquerda é a que importa: **o app e este projeto
são mutuamente exclusivos na live view.** Usar um derruba o outro, porque há
um só conjunto de credenciais P2P por vez. Quem quiser as duas coisas ao mesmo
tempo vai ter de aceitar re-colher a credencial a cada uso do app.

## Vida sem o app

Pode desinstalar. Depois da colheita, o app não faz falta para nada aqui.

Uma distinção que vale ter clara: "offline" neste projeto quer dizer que **o
nosso lado** não precisa do cloud, e não que a câmera vá ficar muda. A câmera
segue falando com o cloud dela por conta própria, empurrando alertas e
gravações, e isso é independente do app no seu celular. Para cortar isso também
seria preciso bloquear a saída da câmera no roteador. Não testei o stream com a
câmera totalmente sem internet: o SDK resolve o UID pelos servidores da
ThroughTek, e a busca em LAN costuma bastar, mas isso só vale como afirmação
depois de medir com a câmera na mão.

## Preenchendo creds.json

Copie e preencha:

```sh
cp creds.json.example creds.json && chmod 600 creds.json
```

| Campo | De onde vem |
| --- | --- |
| `uid` | `P2PUuid`, em `/mnt/flash/furbo/setup_info.json`. 20 caracteres |
| `auth_key` | `authKey`, em `/mnt/flash/furbo/p2p_auth.json`. 8 caracteres |
| `password` | `password`, no mesmo `p2p_auth.json` |
| `account` | `P2PAccountId`, no corpo de `/v5/device/p2p_connection/get` |
| `proto` | `v3` no Mini 2, Mini 3, Mini 360 e 360. `v2` nos FB001, FB002, FB0025 |

Teste rápido, sem subir a stack inteira:

```sh
docker run --rm --network host --entrypoint python3 -e PYTHONPATH=/app \
  -v "$PWD:/local:ro" -e FURBO_P2P_CREDS=/local/creds.json furbo-bridge:local \
  /local/run_bridge.py p2p-status --lib /usr/local/lib/libIOTCAPIs_ALL.so
```

Se as credenciais estiverem certas, ele imprime o estado da câmera (energia,
volume, visão noturna, sensibilidade). Errado dá `IOTC_ER_UNLICENSE` (-10) para
UID inválido ou `IOTC_ER_DEVICE_REJECT_BY_WRONG_AUTH_KEY` (-90) para chave
errada, e essa diferença já diz qual dos dois campos está torto.

## Como chegar nos arquivos do aparelho

Isto exige abrir a câmera. O Furbo Mini 360 é o FCC ID `2BPVM-MINICAM3`, e as
fotos internas são públicas em
`https://fccid.io/2BPVM-MINICAM3/Internal-Photos/Internal-Photos-8514684`, o que
dá o mapa da placa antes de mexer em nada.

1. Adaptador USB-serial **de 3,3 V** (CH340 ou FTDI). O 360 tem um conector de
   4 pinos; nos relatos, um cabo JST SH de 4 vias encaixa melhor do que
   garras.
2. `115200 8N1`. Aterre antes de energizar a câmera e abra o terminal.
3. Na inicialização, interrompa o uboot e troque o init:
   `setenv bootargs … init=/bin/sh` e `boot`.
4. `cat /mnt/flash/furbo/p2p_auth.json` e `cat /mnt/flash/furbo/setup_info.json`.

O `P2PAccountId` não costuma estar nesses dois arquivos. Ele sai fácil do
cloud com o token da conta, ou do corpo de `p2p_connection/get` capturado uma
vez.

Três avisos honestos sobre esta etapa:

- No Furbo Mini de 2021 (MINICAM2) o uboot era interrompível e isso deu root
  direto. No Furbo 360, os pesquisadores da Software Secured encontraram o
  UART **protegido por senha** e não conseguiram o mesmo atalho. O MINICAM3 é de
  2025, então espere encontrar algo mais duro, não mais mole.
- Alternativas se o uboot estiver trancado: interceptar a atualização de
  firmware (o Mini antigo baixava de um bucket S3 com `curl -k` e sem
  verificação de assinatura, o que permitia subir um firmware com telnet), ou
  leitura direta do flash com programador depois de dessoldar o chip.
- Nada disso é necessário se você aceitar o cloud só para tirar a credencial
  uma vez. O `ha-furbo` faz isso de forma automatizada; este projeto existe
  para o dia em que a credencial for sua.

## Rodando

```sh
./run.sh            # só loopback: nada na rede alcança a câmera
./run.sh tailnet    # também no IP do Tailscale, para ver do celular
./run.sh logs
./run.sh stop
```

| Endereço | Para quê |
| --- | --- |
| `http://127.0.0.1:8080/` | a web app: player, pan, petisco, ajustes |
| `rtsp://furbo:<senha>@127.0.0.1:8554/furbo` | mpv, VLC, Home Assistant |
| `http://127.0.0.1:1984/stream.html?src=furbo` | o player do go2rtc, que a UI embute |

A senha do RTSP não é o `api_token`: ela é derivada dele
(`printf 'furbo-rtsp:%s' "$TOKEN" | sha256sum | cut -c1-32`), para que uma URL
de vídeo vazada não dê acesso aos controles. Homologação com Home Assistant:
aponte a integração genérica de câmera para a URL do RTSP.

## Limites conhecidos

- **Uma sessão P2P só.** A câmera reemite a credencial a cada nova conexão e
  invalida a anterior. É por isso que o `stream.sh` lê da sessão do bridge em
  vez de abrir a sua, e por isso a UI não tem talkback.
- **App e bridge competem.** Se você abrir o app da Furbo e ele pedir
  credenciais novas, as que estão no `creds.json` podem parar de valer. Sem app,
  sem problema.
- **O SDK ainda fala com os servidores de rendezvous da TUTK** para resolver o
  UID, a menos que encontre a câmera pela busca em LAN. É a infraestrutura da
  ThroughTek, não a sua conta na Furbo: nenhum login, nenhuma credencial é
  emitida, e nada é enviado sobre a câmera.
- **Áudio desligado por padrão.** Ligue com `FURBO_AUDIO=true` no `run.sh`. O
  formato da trilha de áudio é decidido testando um decodificador, porque o
  codec que a câmera manda não está documentado.

## Créditos

O trabalho pesado é do projeto [willbeeching/ha-furbo](https://github.com/willbeeching/ha-furbo),
que reverteu o protocolo a partir do app e publicou tudo sob MIT. Este diretório
não modifica o código dele: importa o módulo e troca duas funções por outras que
leem credenciais de arquivo, então um `git pull` continua limpo.

A pesquisa pública que tornou isso possível: Somerset Recon (partes I a III),
Software Secured (partes 1 a 6) e o `Fredde87/cuboai-tutk`, que implementa TUTK
puro em Python e serve de referência para qualquer coisa que este bridge não
cubra.
