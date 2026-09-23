🌐 [Read in English](en/sleuthkit.md)

# Sleuth Kit — referência de comandos

Comandos do [The Sleuth Kit](https://www.sleuthkit.org/) (TSK 4.12.1), testados em WSL (Ubuntu). Organizados pela camada da imagem que cada um lê — do container bruto até um único arquivo apagado — mais as receitas de várias etapas que resolvem tarefas de verdade.

Instalação: `sudo apt install sleuthkit` (pacote `sleuthkit`, sem hífen). O build padrão já lê `.E01` direto (linkado com `libewf2`) — não precisa converter.

## A regra que todo mundo erra primeiro: o offset `-o`

1. Uma imagem de disco tem uma **tabela de partições**. Ferramentas de sistema de arquivos não enxergam isso sozinhas — precisam saber onde o sistema de arquivos *começa*.
2. Rode `mmls image.E01` primeiro. Leia o **Start** (setor inicial) da partição que você quer (ex.: `2048`).
3. Passe esse valor pra **toda** ferramenta de sistema de arquivos, metadado ou dado: `fls -o 2048`, `fsstat -o 2048`, `icat -o 2048`...
4. O offset é em **setores**. O tamanho padrão de setor é 512 bytes; muda com `-b`. `-o` errado dá o erro "Cannot determine file system type".

## As seis camadas

| # | Camada | Ferramentas |
|---|---|---|
| 1 | Imagem / container | `img_stat`, `img_cat`, `tsk_imageinfo` |
| 2 | Volume / partição | `mmls`, `mmstat`, `mmcat` |
| 3 | Sistema de arquivos | `fsstat` |
| 4 | Metadado / inode | `istat`, `ils`, `icat`, `ifind` |
| 5 | Unidade de dados / bloco | `blkcat`, `blkls`, `blkstat`, `blkcalc` |
| 6 | Nome de arquivo | `fls`, `ffind` |

## 1 — Imagem

```bash
img_stat image.E01               # formato, tamanho, setor, segmentos (E01/split)
img_cat image.E01 > image.raw    # exporta como raw/dd puro
tsk_imageinfo image.E01          # resumo da imagem + sistema de volumes
```

## 2 — Volume

```bash
mmls image.E01                   # tabela de partições — anote o Start de cada uma
mmcat image.E01 2 > part2.dd     # extrai a partição de slot 2 pra um arquivo isolado
mmstat image.E01                 # só o tipo de sistema de volume (dos, gpt...)
```

Flags úteis de `mmls`: `-t dos|gpt|mac|bsd|sun` força o tipo quando o autodetect falha; `-B` mostra tamanho em bytes; `-a`/`-A` mostram só alocado/não alocado.

## 3 — Sistema de arquivos

```bash
fsstat -o 2048 image.E01
```

Label do volume, tipo e versão do sistema de arquivos, tamanho de bloco/cluster, primeiro e último inode, layout da FAT/MFT, e histórico de montagem. `-f ntfs|ext4|fat32...` força o tipo; `-o N` é o setor de início (obrigatório numa imagem de disco inteiro); `-b N` muda o tamanho de setor.

## 4 — Metadado

Essa camada ainda enxerga arquivos sem nome — entradas apagadas, órfãos — enquanto a estrutura de metadado sobreviver.

```bash
istat -o 2048 image.E01 12345              # tudo sobre o inode 12345: MAC times, tamanho, blocos
icat -o 2048 image.E01 12345 > recuperado.bin   # conteúdo do arquivo por inode, mesmo sem nome
ils -e -o 2048 image.E01                   # lista inodes; padrão é só apagado/não alocado
ifind -o 2048 -n "/Users/alex/notas.txt" image.E01  # caminho → inode
```

`icat`: `-r` tenta recuperar mesmo com inode não alocado; `-s` inclui o slack space. `ils`: `-e` = todo inode (alocado + não); `-m` = formato timeline (pra `mactime`).

## 5 — Unidade de dados

O ponto de partida pra carving em espaço não alocado e análise de slack.

```bash
blkstat -o 2048 image.E01 5678                # bloco 5678 está alocado ou livre?
blkcat -o 2048 image.E01 5678 16 | xxd | less # dump de 16 blocos a partir de 5678
blkls -o 2048 image.E01 > unalloc.dd          # concatena todo o não alocado
blkcalc -o 2048 -u 900 image.E01              # offset num carving → bloco real na imagem
```

`blkls`: `-e` = todo bloco; `-s` = só slack; `-A`/`-a` = só não alocado/só alocado.

## 6 — Nome de arquivo

```bash
fls -o 2048 -r -p image.E01          # listagem recursiva com caminho completo
ffind -a -o 2048 image.E01 12345     # nome(s) que apontam pro inode 12345
```

`fls`: `-r`/`-p` recursivo/caminho completo; `-d` só apagados, `-u` só não apagados; `-l` formato longo (tamanho, datas, UID/GID); `-m /mnt` formato timeline; `-z UTC` fuso horário.

## Linha do tempo

Duas etapas: as ferramentas TSK geram um **body file** (registros delimitados por `|`); `mactime` ordena isso num relatório cronológico.

```bash
tsk_gettimes image.E01 > bodyfile     # imagem inteira, todas partições, sem precisar de -o
mactime -b bodyfile -d -y -z America/Sao_Paulo 2024-01-01..2024-12-31 > timeline.csv
```

`-d` = CSV; `-y` = datas ISO-8601; `-z` = fuso da evidência; `-i day resumo.csv` também gera um histograma de atividade por dia/hora.

## Recuperação e exportação

```bash
tsk_recover -o 2048 image.E01 ./recuperados   # exporta arquivos apagados reconstruídos
fcat -o 2048 "/etc/passwd" image.E01          # como icat, mas por caminho em vez de inode
fiwalk -X inventario.xml image.E01            # inventário XML: nomes, inodes, hashes
```

`tsk_recover`: `-e` = tudo (alocado + apagado); `-a` = só alocado.

## Busca e classificação

```bash
srch_strings -a -t d unalloc.dd > strings.txt     # strings ASCII com offset em bytes
sigfind -o 2048 -t jpeg image.E01                 # varre setores por assinatura mágica
sorter -o 2048 -d ./sorter-out -h -s image.E01     # categoriza por tipo real, gera índice HTML
usnjls -o 2048 image.E01 > usn.txt                # NTFS $UsnJrnl — jornal de mudanças
hfind NSRLFile.txt d41d8cd98f00b204e9800998ecf8427e  # busca hash em base NSRL/customizada
```

## Montando um E01 (pacote separado: `ewf-tools`)

O TSK lê `.E01` direto — não precisa montar nada pra `mmls`/`fls`/`icat`. Monte só quando um gerenciador de arquivos ou ferramenta não-forense precisar enxergar os dados. `ewfmount` não é do Sleuth Kit — vem do pacote `ewf-tools`.

```bash
sudo apt install ewf-tools   # ewfmount, ewfinfo, ewfverify, ewfexport, ewfacquire

ewfverify case.E01   # integridade: recalcula o hash de aquisição
ewfinfo case.E01      # metadados de aquisição: examinador, data, notas, tamanho

mkdir -p ~/mnt/ewf ~/mnt/evid
ewfmount case.E01 ~/mnt/ewf              # -> ~/mnt/ewf/ewf1 : visão raw somente leitura
mmls ~/mnt/ewf/ewf1                      # lê o Start da partição (ex.: 2048)
sudo mount -o ro,loop,offset=$((2048*512)),show_sys_files,streams_interface=windows \
     ~/mnt/ewf/ewf1 ~/mnt/evid           # NTFS; pra ext4 basta ro,loop,offset=...
ls ~/mnt/evid

# desmontar, na ordem inversa:
sudo umount ~/mnt/evid
fusermount -u ~/mnt/ewf
```

`ro` sempre — nunca montar evidência gravável. O `offset` é o mesmo número do `-o`, mas em **bytes** (setor Start × 512).

## Receitas

### R1 — Primeiros 90 segundos com uma imagem desconhecida

```bash
sha256sum image.E01 | tee image.E01.sha256
img_stat image.E01
mmls image.E01                       # anote o Start de cada partição
fsstat -o 2048 image.E01
fls -o 2048 -r -p image.E01 > files.txt
```

Produz `files.txt` — todo caminho + inode, entradas apagadas marcadas com `*`.

### R2 — Extrair um arquivo achado na listagem

Supondo que `files.txt` mostra `r/r 4128-128-1: Users/alex/Desktop/plano.docx`:

```bash
istat -o 2048 image.E01 4128            # confirma datas e tamanho
icat -o 2048 image.E01 4128 > plano.docx
sha256sum plano.docx
```

### R3 — Recuperar arquivos apagados

```bash
fls -o 2048 -r -d image.E01             # prévia do que está apagado
tsk_recover -o 2048 image.E01 ./apagados
find ./apagados -type f | wc -l
```

Em ext4/APFS espere muitos arquivos vazios (blocos de dado zerados no delete); NTFS/FAT recuperam muito melhor.

### R4 — Linha do tempo completa

```bash
tsk_gettimes image.E01 > bodyfile
mactime -b bodyfile -d -y -z America/Sao_Paulo > timeline.csv
mactime -b bodyfile -d -y -z America/Sao_Paulo -i day atividade-por-dia.csv > /dev/null
```

### R5 — Carving em espaço não alocado

```bash
blkls -o 2048 image.E01 > unalloc.dd
srch_strings -a -t d unalloc.dd | grep -i "confidencial"
blkcalc -o 2048 -u <offset/tamanho_bloco> image.E01      # -> bloco real
ifind -o 2048 -d <bloco real> image.E01                  # -> inode dono, se houver
```

### R6 — Triagem por tipo de arquivo

```bash
sorter -o 2048 -d ./sorter-out -h -s image.E01
xdg-open ./sorter-out/index.html
```

## Gotchas

- **A imagem no lado do Windows é lenta pra ler do WSL.** Se ela estiver em `/mnt/c/...`, copie pro sistema de arquivos do Linux primeiro (`cp /mnt/c/.../image.E01 ~/cases/`) e trabalhe de lá.
- **Nunca trabalhe no original.** Copie, deixe só leitura (`chmod 444 image.E01`) e registre `sha256sum` antes e depois de cada sessão.
- **"Cannot determine file system type"** quase sempre é `-o` errado ou faltando. Rode `mmls` de novo. Imagem de partição única sem tabela: use `-o 0` ou tire o `-o`.
- **`-o` não é universal.** Ferramentas de camada de sistema de arquivos precisam; ferramentas de imagem inteira rejeitam. `tsk_gettimes: invalid option -- 'o'` significa que você passou `-o` pra uma ferramenta que já percorre as partições sozinha.
- **Fuso horário é evidência.** `mactime -z` controla a interpretação; fuso errado desloca todo evento. Anote o fuso configurado na máquina e declare isso no laudo.
- **Deletado ≠ recuperável.** ext4 e APFS zeram os ponteiros de bloco do inode ao apagar, então `icat` pode não retornar nada mesmo com `fls -d` ainda mostrando o nome. NTFS e FAT seguram muito mais tempo.

---

Man pages: `man mmls`, `man fls`, `man mactime`. Toda ferramenta aceita `-V` (versão) e mostra o uso sem argumento nenhum.
