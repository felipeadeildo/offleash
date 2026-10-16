# Falar com o hardware

Guia para abrir e ler uma câmera embarcada como o Furbo. A habilidade é geral:
UART existe em praticamente toda placa que roda Linux, de roteador a televisão.

O objetivo aqui não é modificar nada de primeira. É **ler**, porque o log de
boot responde quase tudo antes de você arriscar qualquer coisa:

- qual SoC e qual kernel
- como o flash está dividido (o mapa de partições)
- se o bootloader verifica assinatura
- se o UART pede senha e se o bootloader é interrompível

Sem essa leitura, qualquer plano de reescrever firmware é chute.

## O que comprar

| item | para quê | preço aproximado |
| --- | --- | --- |
| adaptador USB-serial **de 3,3 V** (CH340 ou FT232) | é o console | R$ 15 a 60 |
| cabo JST SH de 4 vias | encaixa nos conectores Qwiic/STEMMA, comuns nesses aparelhos | R$ 10 a 20 |
| jumpers fêmea-fêmea | quando são pads em vez de conector | R$ 10 |
| multímetro | achar GND e 3,3 V e confirmar o TX | R$ 40 |
| analisador lógico de 8 canais (opcional, mas resolve) | identifica o UART sozinho, sem tentativa e erro | R$ 50 a 80 |
| **CH341A com garra SOIC-8** | ler o flash direto, o plano B quando o UART está travado | R$ 50 a 90 |
| Raspberry Pi Pico (alternativa) | serve de ponte serial e de analisador quando não há adaptador | R$ 40 |

Se o chip de flash for **NAND** (escrito `NAND` na serigrafia), a garra e o
CH341A não servem: aí é programador de NAND, e às vezes dessoldar. Identifique o
chip pelas inscrições antes de comprar qualquer coisa.

## Antes de abrir: olhe a placa

O FCC publica **fotos internas** de todo aparelho homologado, em alta resolução.
No caso do Mini 360 é o ID `2BPVM-MINICAM3`, e a página de fotos internas mostra
os dois lados da placa. Olhe ali primeiro: muitos aparelhos têm um conector de 4
pinos já rotulado, poupando meia hora de multímetro.

- `https://fccid.io/2BPVM-MINICAM3/Internal-Photos/Internal-Photos-8514684`

## Achar o UART sem rótulo

UART quase sempre são **três ou quatro pads em fila** (às vezes um conector). A
ordem é livre, então identifique com o multímetro, com a placa **desligada**
exceto para medir tensão:

1. **GND**: continuidade com o terra da placa, ou com a blindagem do conector
   USB. É o primeiro a identificar e o primeiro a conectar.
2. **VCC ou 3,3 V**: com a placa ligada, o pad que mede 3,3 V estável. **Não
   conecte esse** no adaptador: a placa já tem fonte, e alimentar por dois
   lados queima.
3. **TX** (o que a placa fala): 3,3 V em repouso e a tensão oscila durante o
   boot. É a linha que você liga no **RX** do adaptador.
4. **RX** (o que a placa ouve): também em 3,3 V em repouso, mas parado. É a
   linha que você liga no **TX** do adaptador.

O truque do momento: no instante em que você liga a câmera, o TX fica agitado
por segundos. Se o multímetro oscilar em um dos pads só nos primeiros segundos,
esse é o TX. Com um analisador lógico isso leva trinta segundos, sem chute.

## Ligar sem queimar

- **Sempre GND primeiro**, e o adaptador configurado em **3,3 V** (muitos têm
  jumper de 5 V e 5 V mata o SoC).
- **Nunca conecte o VCC** do adaptador. A câmera tem fonte própria.
- **Cruze as linhas**: TX da placa no RX do adaptador, RX da placa no TX do
  adaptador. Se você ligar TX com TX, nada aparece e nada quebra.
- Energize a câmera só depois de tudo conectado. Estática e ponta solta são os
  dois assassinos que aparecem primeiro.

## Abrir o console

```sh
# descubra o nome do adaptador
ls /dev/ttyUSB* /dev/ttyACM*

# leia e guarde TUDO: o log vale mais que qualquer tentativa
picocom -b 115200 /dev/ttyUSB0 | tee ~/furbo-boot.log
```

`screen`, `minicom` e `tio` servem igual. 115200 8N1 é de longe o mais comum;
depois dele, 57600 e 38400. Se aparecer **caractere embaralhado mas com padrão
repetitivo**, a velocidade está errada, e não a ligação: tente as outras. Se não
aparecer nada, troque TX e RX.

## O que ler no boot log

Ligue a câmera e observe, nesta ordem:

1. **O banner do bootloader** (U-Boot costuma anunciar versão e a placa).
2. **`Linux version ...`**: kernel e compilador.
3. **A linha de comando do kernel** (`console=ttyS0`, `root=`, `init=`). É aqui
   que quase sempre está escrito qual dispositivo é o console.
4. **A tabela de partições do flash**: procure por `mtd`, `Creating N MTD
   partitions`, `0x0000000XXXXX : "uboot"`, `"kernel"`, `"rootfs"`, `"user"`.
   Esse é o mapa que decide tudo, inclusive se existe partição gravável.
5. **Sinais de assinatura ou boot verificado**: `verified`, `signature`, `FIT`,
   `secure boot`, `hash mismatch`. Se aparecer, firmware modificado não sobe
   nesse aparelho e o plano de reescrever muda de nível.
6. **A contagem do autoboot**: algo como `Hit any key to stop autoboot: 3`. É a
   sua janela de entrada, e ela dura de um a três segundos.

## Parar o bootloader

Na contagem do autoboot, **segure ou martele uma tecla** no terminal. Com sorte
você cai no prompt do U-Boot (`=>`). Dali, sem gravar nada:

```
printenv          # o ambiente inteiro: bootargs, partições, IP, tudo
help              # o que esse bootloader sabe fazer
```

O clássico para um shell de emergência, **quando o bootloader permite**:

```
setenv bootargs <os mesmos do printenv> init=/bin/sh
boot
```

Isso troca o init do sistema por um shell, sem escrever nada no flash. Se a
placa subir com `#` em vez de um login, você tem root.

Se aparecer um **login** pedindo senha, o UART está travado para escrita mas
**o log continua legível**, e o log já entrega três das quatro respostas.

## Quando o UART está travado: a escada

1. **Ler o flash com garra** (CH341A + SOIC-8, placa desligada). Não é destrutivo
   e devolve a imagem inteira. Dependendo do layout do flash, você encontra ali
   o ambiente do bootloader, o rootfs, e **segredos do aparelho**, incluindo
   arquivos de credencial que o aparelho escreve na partição gravável. É o
   caminho mais curto quando o acesso por UART foi fechado.
2. **JTAG**, se a placa expõe. Dá depuração de verdade, às vezes leitura e
   escrita de memória.
3. **Dessoldar o chip** (chip-off) e ler num programador. Exige estação de ar
   quente e paciência, e é o último recurso antes de virar peso de papel.
4. **Glitching** (falha de tensão ou de clock para furar o boot verificado).
   É o nível de quem tem ChipWhisperer, e não vale a pena para uma câmera de pet.

## Ferramentas de software que ajudam

| para | ferramenta |
| --- | --- |
| analisar a imagem do flash | `binwalk -e imagem.bin` (acha e extrai SquashFS, kernel, uboot) |
| ler e gravar flash SPI | `flashrom`, `ch341eeprom` |
| flash SPI NAND | `SNANDer` |
| procurar segredo na imagem | `strings` + `grep`, e `binwalk` para achar os sistemas de arquivos |

## A regra que economiza mais tempo

**Grave o log sempre, e leia antes de tentar.** Em quase todo aparelho, o log de
boot responde "dá para modificar?" sem que você encoste em nada além dos três
fios. Tentativa e erro com bootloader queima aparelho; leitura de log não.
