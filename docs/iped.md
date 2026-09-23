🌐 [Read in English](en/iped.md)

# IPED — guia de uso

[IPED](https://github.com/sepinf-inc/IPED) (Indexador e Processador de Evidências Digitais) 4.3.1, instalado a partir do release oficial do GitHub. Fluxo em dois programas: `iped.exe` processa a imagem e gera uma pasta de caso; `IPED-SearchApp.exe`, gerado dentro dessa pasta, é onde a análise acontece.

## A imagem antes do IPED

Uma imagem forense é uma cópia bit a bit do dispositivo — setor por setor, incluindo espaço livre, arquivos apagados e áreas que o sistema operacional não mostra.

- **Bloqueador de escrita** (*write blocker*): deixa ler o disco original mas impede qualquer gravação nele.
- **Hash na aquisição**, verificação e cadeia de custódia: ver [`hashes.md`](hashes.md). O IPED calcula o hash de **cada arquivo dentro da imagem** — não é ele quem verifica o hash da imagem inteira.

### Formatos que o IPED abre (parâmetro `-d`)

| Formato | Extensão | O que é |
|---|---|---|
| RAW / dd | `.dd` `.001` `.img` | Cópia crua, sem compressão nem metadados |
| EnCase / EWF | `.E01` `.Ex01` | Formato pericial mais comum: comprime, guarda hash, caso, examinador e data |
| AccessData | `.AD1` | Imagem lógica — só os arquivos escolhidos, não o disco inteiro |
| Celular (Cellebrite) | `.UFDR` | Extração de dispositivo móvel |
| Máquinas virtuais | `.VMDK` `.VHD` `.VHDX` | Discos de VM |
| Óptico | `.ISO` | Imagem de CD/DVD |
| Ao vivo | drive físico / pasta | Um disco conectado, ou uma pasta solta de arquivos |

`.iped` é o formato do IPED pra reprocessar itens marcados. `AFF` só funciona no Linux.

## Processar — `iped.exe`

```powershell
PS C:\IPED\iped-4.3.1> .\iped.exe -d "D:\pericia\hd.E01" -o "C:\casos\caso01" -tz GMT-3
# -d = dado de entrada   -o = pasta de saída   -tz = fuso do sistema de arquivos
```

Por baixo: monta as partições com o Sleuth Kit, extrai arquivos ativos e apagados, calcula hashes, roda *parsers* (e-mail, navegador, registro, WhatsApp...), indexa todo o texto num índice Lucene, categoriza por tipo e faz carving no espaço não alocado.

### Parâmetros que importam

| Parâmetro | Pra quê |
|---|---|
| `-d` | **Obrigatório.** Imagem, pasta ou drive de entrada. Pode repetir pra vários |
| `-o` | **Obrigatório.** Pasta onde o caso será criado |
| `-dname` | Nome/apelido de exibição daquela evidência |
| `-tz` | Fuso horário do disco. FAT/exFAT gravam hora local — sem isso as datas saem erradas |
| `-profile` | Perfil de processamento (tabela abaixo) |
| `-p` | Senha pra imagens ou containers criptografados |
| `--append` | Adiciona outra evidência a um caso que já existe |
| `--continue` | Retoma um processamento que travou ou foi abortado — **não** serve pra reabrir um caso já terminado |
| `--nogui` | Sem janelas — processa em modo texto (servidor, script) |
| `--portable` | Caminhos relativos, pra levar o caso num HD externo |

Pra só reabrir um caso já processado: não roda `iped.exe` de novo — abre o `IPED-SearchApp.exe` de dentro da pasta do caso.

### Perfis (`-profile`)

| Perfil | Quando usar |
|---|---|
| `forensic` | Exame completo: extrai tudo, hashes, OCR, expansão de containers. Mais minucioso, mais demorado |
| `fastmode` | Mais rápido: pula partes pesadas. Bom pra uma primeira passada |
| `triage` | Só o essencial pra decidir rápido se aquele dispositivo interessa |
| `blind` | Indexa sem gerar visualizações — usado em fluxos cegos/servidor |
| `pedo` | Ajustado pra casos de abuso infantil (categorias e listas específicas) |

## Analisar — IPED-SearchApp

A tela tem quatro regiões: **barra de busca** (topo, sintaxe Lucene), **painel esquerdo** (abas Evidência, Categorias, Metadados, Marcadores), **painel central** (tabela/galeria/mapa/linha do tempo), **visualizador** (item selecionado + aba Metadados com todas as propriedades extraídas).

### Colunas que valem a pena adicionar

Botão direito no cabeçalho da tabela → escolher colunas:

| Coluna | O que te diz |
|---|---|
| Tamanho | Bytes do arquivo |
| Caminho | Endereço do arquivo dentro da imagem, ex.: `/imagem.E01/vol_vol2/pasta/arquivo` — a partição aparece pelo nome que o Sleuth Kit deu (`vol_volN`), não pela letra do drive |
| MD5 / SHA-1 / SHA-256 | Hash de cada arquivo |
| Deletado | `true` = apagado, recuperado pelo registro do sistema de arquivos (nome e datas preservados) |
| Carved | `true` = recuperado por assinatura, sem metadados, sem nome/data originais |
| Offset / Setor | Posição física do arquivo dentro da imagem |
| Datas | Criação, modificação, acesso, alteração do registro. Divergências entre elas denunciam adulteração |
| Tipo / MIME | Tipo real pelo conteúdo. Se briga com a extensão, o IPED marca divergência de assinatura |
| Categoria | Classificação automática |
| Hash hits | Bateu com alguma lista de hash conhecida (KFF) carregada |

### Busca

Sintaxe Lucene: termo, `"frase exata"`, curinga `nota*`, intervalo, `campo:valor`, regex.

```
name:*.jpg
size:[1000000 TO *]        # ≥ 1 MB
deleted:true
category:"documents" AND senha
```

Os nomes exatos dos campos aparecem no topo de cada coluna e na aba Metadados.

## Marcadores (bookmarks)

Marcador é um rótulo nomeado que você prega nos itens relevantes enquanto analisa.

- **Selecionar itens:** coluna de caixa de seleção; `Espaço` alterna a caixa do item em foco; `Shift`/`Ctrl` + clique pra vários de uma vez.
- **Criar/aplicar:** botão direito nos itens → menu Marcadores → novo marcador ou adicionar a um existente. Um item pode estar em vários marcadores.
- **Painel Marcadores** (aba esquerda): lista todos com contagem; clicar filtra a tabela pra aquele marcador.
- **Comentários** no item e no marcador vão junto pro relatório.
- **Salvo em** `Bookmarks-<caso>.json` na pasta do caso, com backup automático em `iped/bkp` a cada hora.
- **O relatório sai dos marcadores:** ao gerar relatório, o IPED pergunta quais marcadores entram.

## Exportar

| Destino | O que sai | Pra quê |
|---|---|---|
| Pasta no disco | Cópia dos arquivos originais | Entregar os arquivos, abrir noutra ferramenta |
| CSV de propriedades | A tabela — colunas visíveis, uma linha por item | Planilha, anexo de laudo. `Lista de Arquivos.csv` já sai sozinho na raiz do caso |
| Relatório HTML (`htmlreport/`) | Pacote autocontido navegável no browser, gerado a partir dos marcadores | Entrega final, sem precisar do IPED instalado |
| Sub-caso `.iped` | Só os itens escolhidos, reprocessados num caso novo | Isolar o material relevante |
| KML / Google Earth | Pontos GPS dos itens georreferenciados | Ver deslocamento num mapa |
| Área de transferência | Conteúdo da célula/linha | Colar rápido em e-mail/anotação |

Exportação automática durante o processamento: `enableAutomaticExportFiles = true` no `IPEDConfig.txt` + categorias descomentadas em `conf/CategoriesToExport.txt`. Só os itens exportados entram no caso, que fica independente da imagem original.

## Anatomia de um disco

Do maior pro menor:

```
DISCO FÍSICO
└── Tabela de partições
    └── Partição / Volume
        └── Sistema de arquivos (MFT / FAT / inodes)
            └── Área de dados, dividida em clusters
                ├── Arquivo A — clusters alocados
                ├── slack space (sobra no último cluster de um arquivo)
                ├── espaço NÃO alocado — onde vive o conteúdo de um arquivo apagado, até ser sobrescrito
                └── Arquivo B — clusters alocados
```

- 1 setor = 512 B (ou 4 KiB). 1 cluster = grupo de setores — a menor unidade que o SO aloca.
- Apagar um arquivo = marcar os clusters dele como livres na tabela. O conteúdo continua lá até outro arquivo ocupar o espaço.
- **Slack space:** o arquivo não preenche o último cluster inteiro; a sobra pode guardar restos do dado anterior.

## Apagados e carving

Apagar não zera o conteúdo — só marca o registro (MFT/diretório) e os clusters como livres.

| Situação | Como se recupera | Coluna |
|---|---|---|
| Registro ainda existe, clusters não reaproveitados | Lê a MFT/diretório e remonta com nome, caminho e datas originais | `Deletado = true` |
| Registro sumiu, mas o conteúdo está no não alocado ou no slack | **Carving:** varre os bytes procurando assinaturas (cabeçalho/rodapé conhecido) e extrai o bloco | `Carved = true` |

- Arquivo carved não tem nome nem data original.
- Fragmentação atrapalha o carving.
- **Divergência de assinatura:** extensão não bate com o conteúdo real — clássico de arquivo escondido.

## Configuração — `IPEDConfig.txt`

Arquivo na raiz da instalação, painel de liga/desliga do processamento. **Mudança só vale pro próximo processamento** — não afeta um caso já pronto.

| Linha | O que liga | Custo |
|---|---|---|
| `enableCarving` | Recupera arquivos por assinatura em áreas sem metadado | Processamento mais lento |
| `enableOCR` | Lê texto dentro de imagens e PDFs escaneados, joga pro índice | Bem mais lento. Idioma em `conf/OCRConfig.txt` |
| `enableHash` | MD5/SHA-1/SHA-256 de cada arquivo (ligado por padrão) | Baixo |
| `enableRegexSearch` | Hits de e-mail, URL, IP, CPF, cartão no grupo Regex (ligado por padrão) | Baixo |
| `expandContainers` | Abre zip, e-mail box, documentos Office (ligado por padrão) | Médio |

Carving completo (espaço não alocado + slack) precisa de mais duas linhas, em `conf/FileSystemConfig.txt`:

```
addUnallocated = true
addFileSlacks  = true
```

Reprocessar com a config nova exige uma pasta `-o` vazia ou nova — não dá pra reaproveitar a de um caso já processado. Sem `-profile`, usa o `IPEDConfig.txt` da raiz; com `-profile <nome>`, usa `profiles/<nome>/IPEDConfig.txt` por cima, que pode ignorar sua edição.

## Mapa do tesouro — "quero X → onde está Y"

| Você quer... | Onde está no IPED |
|---|---|
| Hash de um arquivo | Aba Metadados do item, ou colunas MD5/SHA-256 |
| Tamanho e datas | Colunas Tamanho e datas |
| Arquivos apagados | Coluna/filtro Deletado, `deleted:true` |
| Recuperados por assinatura | Coluna/filtro Carved, `carved:true` |
| Posição no disco | Colunas Offset/Setor |
| Fotos e vídeos | Categoria Imagens/Vídeos + visão Galeria |
| Localização (GPS) | Metadados EXIF + visão Mapa |
| Navegação na web | Categoria Histórico de Internet |
| Programas que rodaram | Prefetch, Amcache, SRUM |
| Dispositivos USB | Registro do Windows |
| E-mails | Categoria E-mails |
| Conversas de mensageiro | Parsers de WhatsApp, Telegram |
| Texto específico | Barra de busca |
| Padrões (CPF, cartão, e-mail) | Busca por regex |
| Arquivos conhecidos/ilícitos | Correspondência de hash (KFF) |
| Arquivos com senha | Alerta de criptografia na propriedade |

## Checklist da perícia

- **Contas e fuso:** usuários locais, instalação do SO, fuso horário, último desligamento.
- **Navegador:** histórico, downloads, buscas, cache, cookies.
- **Execução:** Prefetch, Amcache, SRUM.
- **Uso recente:** arquivos recentes, LNK, Jump Lists, shellbags.
- **USB:** histórico de dispositivos removíveis.
- **Comunicação:** e-mails, apps de mensagem.
- **Mídia:** fotos/vídeos, EXIF, GPS.
- **Palavras-chave:** termos do caso, regex.
- **Apagados:** Deletado + Carved, não alocado e slack.
- **Criptografia:** arquivos e volumes protegidos.
- **Hash:** comparação com listas conhecidas (KFF/NSRL).
- **Linha do tempo:** eventos ordenados por data.

## Cola de comandos

```powershell
# teste rápido: processar uma pasta qualquer
.\iped.exe -d "C:\alguma\pasta" -o "C:\casos\teste"

# imagem E01, com fuso e apelido
.\iped.exe -d "D:\ev\hd.E01" -dname "HD-01" -o "C:\casos\caso01" -tz GMT-3

# adicionar outra evidência ao mesmo caso
.\iped.exe -d "E:\ev\pendrive.E01" -o "C:\casos\caso01" --append

# retomar processamento interrompido / ver todas as opções
.\iped.exe -d "D:\ev\hd.E01" -o "C:\casos\caso01" --continue
.\iped.exe --help
```

O que fica na pasta do caso: `IPED-SearchApp.exe` (abre a análise), `iped/` (índice interno, não mexer), `IPED-*.log` (log do processamento), `Bookmarks-*.json` (marcadores), `htmlreport/` (depois de gerar o relatório).

Casos grandes escrevem muito em disco temporário — no `LocalConfig.txt`, aponte `indexTemp` pra um SSD com espaço sobrando e sem antivírus varrendo.
