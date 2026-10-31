🌐 [Read in English](en/tools.md)

# Ferramentas em Python (pasta `ferramentas/`)

Scripts pequenos que poupam tempo na hora de responder quesitos de uma perícia: conversão de datas, junção de tabelas de banco de dados, linha do tempo, primeiro/último evento, URL mais acessada. Todos **só leem** a evidência: cada banco é copiado para uma pasta temporária antes de ser aberto, junto com os arquivos `-wal` e `-shm` (sem eles, dados recentes ficam de fora).

> Nada aqui é específico de um caso. Os caminhos abaixo são exemplos genéricos: troque pelo caminho da sua evidência.

## 1. Como rodar um script (passo a passo)

1. Abra o **PowerShell**.
2. Entre na pasta do repositório:
   ```powershell
   cd C:\forense-digital
   ```
   `cd` significa *change directory* (mudar de pasta).
3. Confira que o Python existe:
   ```powershell
   python --version
   ```
   Se aparecer "não é reconhecido", tente `py --version` e use `py` no lugar de `python` nos comandos.
4. Peça a ajuda de qualquer script (todos, menos o `sessao_chrome.py`, aceitam `--help`):
   ```powershell
   python ferramentas\linha_do_tempo.py --help
   ```

### Anatomia de um comando

```powershell
python ferramentas\linha_do_tempo.py --chrome "C:\evidencia\History" --fuso utc --dia 2025-11-03
```

| Parte | O que é |
|---|---|
| `python` | o programa que executa o script |
| `ferramentas\linha_do_tempo.py` | qual script rodar (caminho dele) |
| `--chrome "C:\evidencia\History"` | uma **opção** (começa com `--`) seguida do seu **valor** |
| `--fuso utc` | outra opção com valor |
| `--so-paginas`, `--url-completa` | opções sem valor: ligam um comportamento |

Regras de sintaxe:
- **Caminho com espaço ou acento vai entre aspas**: `"C:\meu caso\History"`.
- Para quebrar um comando longo em várias linhas no PowerShell, termine a linha com a crase `` ` ``.
- A ordem das opções não importa.
- Salve os resultados (`--csv`) **fora** da pasta da evidência. Arquivos `.csv` estão no `.gitignore` deste repositório para não subirem por engano.

## 2. Qual script usar para qual pergunta

| Pergunta do quesito | Script | Opção principal |
|---|---|---|
| Qual foi o primeiro / o último app instalado? | `analisa_packages.py` | (marca `PRIMEIRO` e `ULTIMO`) |
| Quantos apps o usuário instalou e quantas permissões cada um tem? | `analisa_packages.py` | `--so-usuario` |
| O que aconteceu em tal dia (SMS, chamadas, navegação, instalações)? | `linha_do_tempo.py` | `--dia` |
| Qual o site / URL mais acessado? | `linha_do_tempo.py` | `--top` |
| Mostrar só um site na linha do tempo | `linha_do_tempo.py` | `--filtro` |
| Qual página estava aberta quando o Chrome fechou? | `sessao_chrome.py` | (argumento único) |
| Há páginas com favicon que não estão no histórico (histórico apagado?) | `favicons_fora_do_historico.py` | (duas comparações, A e B) |
| Primeira / última / intermediária visita de um site, mais visitados, páginas de passagem, buscas | `resumo_navegacao.py` | `--site`, `--por-dia` |
| Qual URL foi usada para baixar um arquivo? Quando e para onde? | `downloads_chrome.py` | `--filtro` |
| Este banco desconhecido tem quais tabelas e onde estão as datas? | `mapa_sqlite.py` | `--so-datas`, `--tabela` |
| Modelo do celular, datas e GPS das fotos; há inconsistência? | `exif_fotos.py` | `--so-alertas` |
| Contatos + chamadas + SMS juntos; contatos apagados; números fora da agenda | `contatos_merge.py` | `--so-apagados` |
| Que data é este número? | `convert_date.py` | (valor na linha de comando) |

## 3. Os scripts

### `analisa_packages.py` — apps instalados (Android)

Lê o `packages.xml` (em `/data/system/`). Mostra total de pacotes, apps de usuário (`/data/app`) em ordem de instalação com **PRIMEIRO** e **ULTIMO**, e os que têm mais permissões.

```powershell
python ferramentas\analisa_packages.py "C:\evidencia\data\system\packages.xml" --so-usuario --csv resumo.csv
```

| Opção | Efeito |
|---|---|
| `--so-usuario` | só apps de `/data/app` (os de sistema vêm do firmware e têm quase todos a mesma data) |
| `--csv arquivo.csv` | grava a tabela completa, em ordem cronológica |

Notas: as datas `it` (primeira instalação) e `ut` (última atualização) ficam em hexadecimal no XML; o script converte. A coluna de permissões sensíveis sai vazia no Android 10, porque as permissões de uso ficam em `runtime-permissions.xml`. No Android 12 ou mais novo o `packages.xml` é binário (ABX) e este script não lê.

### `linha_do_tempo.py` — linha do tempo unificada

Junta SMS, chamadas, visitas do Chrome e instalações de apps numa lista única, ordenada, com o fuso que você escolher.

```powershell
python ferramentas\linha_do_tempo.py `
  --sms "C:\evidencia\mmssms.db" `
  --calls "C:\evidencia\calllog.db" `
  --chrome "C:\evidencia\History" `
  --packages "C:\evidencia\packages.xml" `
  --fuso -3 --dia 2025-11-03
```

| Opção | Efeito |
|---|---|
| `--sms`, `--calls`, `--chrome`, `--packages` | fontes (todas opcionais) |
| `--fuso` | `utc` ou horas de diferença (`-3`, `-5`, `+1`). Padrão: `-3` |
| `--dia AAAA-MM-DD` | só esse dia, **no fuso escolhido** |
| `--filtro texto` | só eventos com esse texto na URL/título/detalhe |
| `--top N` | antes da linha do tempo, as N URLs mais visitadas do Chrome |
| `--url-completa` | não corta as URLs (útil para ver parâmetros inteiros) |
| `--csv arquivo.csv` | salva o resultado |

Formatos de data tratados: SMS e chamadas em milissegundos Unix (13 dígitos); Chrome em microssegundos desde 1601 (17 dígitos); `packages.xml` em hexadecimal.
Limites: lê só o padrão Android/Chrome. Em iOS o `sms.db` usa datas desde 2001 e outras tabelas; WhatsApp não está coberto.

### `sessao_chrome.py` — abas abertas no fechamento

Lê um arquivo de sessão do Chrome (`Session_<número>`, pasta `Sessions` do perfil) e mostra as abas, a lista de páginas de cada uma e a **página atual**.

```powershell
python ferramentas\sessao_chrome.py "C:\evidencia\Session_13422390936860763"
```

Atenção: o número no nome do arquivo é a data de **criação** do arquivo de sessão (microssegundos desde 1601, UTC), não a hora do fechamento. Para estimar o fechamento, use a data de modificação **original** do arquivo (por exemplo, `7z l -slt arquivo.zip` mostra `Modified` sem ter sido alterada pela extração).

### `favicons_fora_do_historico.py` — favicon sem histórico

Cruza o banco `Favicons` com o `History` do Chrome. Duas comparações:
- **A) Páginas:** `page_url` do Favicons × URLs do History.
- **B) Ícones:** domínio de onde o ícone foi baixado × domínios do History (ex.: o ícone das buscas do Google vem de um CDN que nunca aparece como página).

```powershell
python ferramentas\favicons_fora_do_historico.py --favicons "C:\evidencia\Favicons" --history "C:\evidencia\History" --fuso utc --csv favicons.csv
```

| Opção | Efeito |
|---|---|
| `--so-paginas` | faz só a comparação A |
| `--fuso` | `utc` (padrão) ou horas |
| `--csv` | salva o resultado |

Interpretação: diferença **não prova** limpeza de histórico. Páginas geradas pelo próprio Chrome e CDNs aparecem aqui. Registre como fato.

### `resumo_navegacao.py` — resumo do histórico do Chrome

Junta `urls`, `visits` e `keyword_search_terms` do `History` e responde de uma vez: primeira e última visita (geral e por domínio), **visita intermediária** (a do meio da lista ordenada por horário), domínios e URLs mais visitados, **páginas de passagem** (redirecionamentos, como o login único do gov.br), termos pesquisados e visitas por dia.

```powershell
python ferramentas\resumo_navegacao.py "C:\evidencia\History" --fuso utc
python ferramentas\resumo_navegacao.py "C:\evidencia\History" --site gov.br --url-completa
python ferramentas\resumo_navegacao.py "C:\evidencia\History" --dia 2025-11-03 --por-dia --csv dominios.csv
```

| Opção | Efeito |
|---|---|
| `--fuso` | `utc` (padrão) ou horas (`-3`) |
| `--site texto` | detalha só as URLs que contêm o texto: primeira, intermediária e última visita, tipos de navegação e redirecionamentos |
| `--dia AAAA-MM-DD` | considera só aquele dia (no fuso escolhido) |
| `--top N` | tamanho dos rankings (padrão 10) |
| `--por-dia` | contagem de visitas por dia, com barras |
| `--url-completa` | não corta as URLs |
| `--csv arquivo.csv` | tabela por domínio: visitas, primeira, intermediária, última |

Cuidados: "visitas" aqui são linhas da tabela `visits` (cada acesso); a coluna `visit_count` de `urls` pode diferir. "Intermediária" é a visita do meio por horário, e não a *página* de redirecionamento: para essa, veja a seção "páginas de passagem" (papel `inicio`, `passagem` ou `fim` na cadeia).

### `downloads_chrome.py` — downloads do Chrome

Junta `downloads` e `downloads_url_chains`. Para cada arquivo: nome e pasta, **URL usada para baixar** (início da cadeia), URL final (se houve redirecionamento), página de origem, início, fim, duração, tamanho, estado, classificação de perigo e se foi aberto.

```powershell
python ferramentas\downloads_chrome.py "C:\evidencia\History" --fuso -3
python ferramentas\downloads_chrome.py "C:\evidencia\History" --filtro .zip --csv downloads.csv
```

| Opção | Efeito |
|---|---|
| `--fuso` | `utc` (padrão) ou horas |
| `--filtro texto` | só downloads cujo nome, URL ou página de origem contenham o texto |
| `--url-completa` | não corta as URLs |
| `--csv arquivo.csv` | salva tudo, inclusive hash, tipo MIME e último acesso |

O `History` prova que o Chrome registrou o download. Que o arquivo ainda existe, ou foi executado, precisa de outra fonte (sistema de arquivos, Prefetch, Event Log).

### `mapa_sqlite.py` — mapa de um banco desconhecido

Para cada tabela: número de linhas, colunas, tipo, quantas linhas têm valor, um exemplo e **quais colunas parecem datas** (formato e intervalo já convertidos). Bom ponto de partida para bancos de apps (WhatsApp, mensageiros, etc.).

```powershell
python ferramentas\mapa_sqlite.py "C:\evidencia\banco.db" --fuso -3
python ferramentas\mapa_sqlite.py "C:\evidencia\banco.db" --so-datas
python ferramentas\mapa_sqlite.py "C:\evidencia\banco.db" --tabela messages --amostra 5
```

| Opção | Efeito |
|---|---|
| `--so-datas` | lista só as colunas com cara de data |
| `--tabela nome` | só aquela tabela (nome exato) |
| `--amostra N` | com `--tabela`, mostra N linhas de exemplo |
| `--fuso` | fuso das datas convertidas |

A detecção olha a ordem de grandeza do número (até 500 valores por coluna, aceita só datas entre 2005 e o ano que vem). É uma **pista**: IDs de 9 a 10 dígitos podem parecer datas, e o script avisa quando a coluna não tem nome de data. Confirme olhando o nome da coluna e alguns valores.

### `exif_fotos.py` — EXIF e inconsistências em fotos

Lê o EXIF de JPEGs **sem instalar nada** (leitor próprio) e mostra marca, modelo, software, `DateTime`, `DateTimeOriginal`, `DateTimeDigitized`, fuso (`OffsetTime`), GPS e as datas do arquivo no sistema. Marca com `[!]`: sem EXIF, `DateTime` ou `DateTimeDigitized` diferente de `DateTimeOriginal`, campo Software preenchido, hora do GPS incompatível com a data local + fuso, arquivo modificado antes da captura.

```powershell
python ferramentas\exif_fotos.py "C:\evidencia\DCIM\Camera"
python ferramentas\exif_fotos.py "C:\evidencia\DCIM" --so-alertas --hash --csv fotos.csv
```

| Opção | Efeito |
|---|---|
| `--so-alertas` | só as fotos com `[!]` |
| `--hash` | inclui o SHA-256 de cada foto |
| `--csv arquivo.csv` | salva a tabela |

Limites: só JPEG (PNG, HEIC etc. aparecem como "sem EXIF"). As datas do EXIF são o horário local do aparelho; as do sistema de arquivos medem outra coisa (extração, cópia). Alerta é pista, não conclusão: registre o fato e mantenha a inconsistência em aberto até ter outra fonte.

### `contatos_merge.py` — contatos + chamadas + SMS

Cruza pelo número de telefone: `contacts2.db` (quem é o contato), `calllog.db` (chamadas) e `mmssms.db` (SMS). Agrupa os `raw_contacts` pelo `contact_id` (a mesma pessoa aparece uma vez por conta: telefone, Google, Signal...), mostra nome, telefones, e-mails, contas, apps ligados, apagado/na lixeira, e por contato a contagem, primeira e última chamada e SMS. No fim lista os **números que aparecem em chamadas/SMS mas não estão na agenda**.

```powershell
python ferramentas\contatos_merge.py --contacts "C:\evidencia\contacts2.db" `
  --calls "C:\evidencia\calllog.db" --sms "C:\evidencia\mmssms.db" --fuso -3 --csv contatos.csv
python ferramentas\contatos_merge.py --contacts "C:\evidencia\contacts2.db" --so-apagados
```

| Opção | Efeito |
|---|---|
| `--contacts` | `contacts2.db` (obrigatório) |
| `--calls` | `calllog.db`, ou outro banco com tabela `calls` (opcional) |
| `--sms` | `mmssms.db` (opcional) |
| `--so-apagados` | só contatos marcados como apagados ou na lixeira |
| `--fuso`, `--csv` | como nos outros scripts |

Casamento de números: só dígitos, comparando os últimos 9 (ignora `+55`, zero do DDD). Números curtos (como 611) só casam se forem idênticos. No Samsung, `contacts2.db` e `calllog.db` ficam em `com.samsung.android.providers.contacts/databases`; mantenha os `-wal` e `-shm` ao lado.

### `convert_date.py` — conversor de datas

Descobre o formato pela quantidade de dígitos e **mostra também as outras leituras plausíveis** (entre 2010 e 2035), porque alguns formatos se confundem. Aceita decimal e hexadecimal.

```powershell
python ferramentas\convert_date.py 1762202574476 --fuso -3
python ferramentas\convert_date.py 134159021410000000 --fuso utc
python ferramentas\convert_date.py 0x198d35fa587 --fuso -3
python ferramentas\convert_date.py 1762202574476 --formato unix-us
python ferramentas\convert_date.py                      # sem argumentos: pergunta o valor e o fuso
```

| Opção | Efeito |
|---|---|
| `valor` | número (decimal, `0x...` ou hexadecimal puro) |
| `--fuso` | `utc` (padrão), horas (`-3`, `-3:30`) ou nome (`America/Sao_Paulo`, no Windows exige `pip install tzdata`) |
| `--formato` | força um formato: `cocoa-s`, `unix-s`, `unix-ms`, `unix-us`, `webkit`, `filetime`, `cocoa-ns` |

| Dígitos | Formato (`--formato`) | Onde aparece |
|---|---|---|
| 9 | Cocoa, segundos desde 2001 (`cocoa-s`) | iOS |
| 10 | Unix, segundos desde 1970 (`unix-s`) | SQLite, Linux |
| 13 | Unix, milissegundos (`unix-ms`) | Android (SMS, chamadas) |
| 16 | Unix, microssegundos (`unix-us`) | Firefox |
| 17 | microssegundos desde 1601 (`webkit`) | Chrome, Edge |
| 18 | FILETIME, 100 ns desde 1601 (`filetime`) | **Windows** (Registro, Prefetch, EVTX) |
| 18 | Cocoa, nanossegundos desde 2001 (`cocoa-ns`) | iOS recente |

Os dois formatos de 18 dígitos são separados pela faixa do valor (FILETIME de 1970 a 2235 fica entre 1,16e17 e 2e17). Se o contexto indicar o outro, use `--formato`. Valores fora de qualquer faixa são tratados como Cocoa em segundos.

## 4. Conversões no próprio SQLite (sem Python)

No DB Browser, aba **Execute SQL**:

```sql
-- Unix em milissegundos (Android)
SELECT datetime(date/1000, 'unixepoch', '-3 hours') FROM sms;

-- Chrome (microssegundos desde 1601)
SELECT datetime(visit_time/1000000 - 11644473600, 'unixepoch', '-3 hours') FROM visits;
```

`/1000` (ou `/1000000`) leva a segundos; `- 11644473600` reposiciona 1601 para 1970; `'unixepoch'` avisa a base; `'-3 hours'` ajusta o fuso.

## 5. Boas práticas

- **Calcule o hash** da evidência antes de mexer e confira depois.
- **Mantenha `.db`, `-wal` e `-shm` juntos.** Um `calllog.db` aberto sozinho pode parecer vazio enquanto as chamadas estão no `-wal`.
- **Valide à mão** 2 ou 3 eventos do resultado no DB Browser.
- Escreva no laudo **fatos e hipóteses**, nunca motivação. "Compatível com" é mais seguro que "provou".
- Registre o **fuso** de cada horário. O relógio do aparelho pode ter outro fuso (o EXIF guarda `OffsetTime`).

## 6. Problemas comuns

| Mensagem | O que fazer |
|---|---|
| `'python' não é reconhecido` | Use `py` ou instale o Python marcando "Add to PATH" |
| `No such file or directory` | O caminho está errado ou sem aspas (espaço/acento) |
| `no such table: calls` | O banco foi aberto sem o `-wal`; mantenha os 3 arquivos juntos |
| Resultado vazio com `--dia` | O dia é interpretado no fuso de `--fuso`; confira o fuso |
| `Este arquivo não parece ser uma sessão do Chrome` | Falta o cabeçalho `SNSS`; é outro tipo de arquivo |
| `Tabela 'downloads' nao encontrada` | O arquivo não é um `History` do Chromium (confira o nome e a pasta) |
