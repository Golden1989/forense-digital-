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
4. Peça a ajuda de qualquer script (todos, menos o `convert_date.py` e o `sessao_chrome.py`, aceitam `--help`):
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
| Que data é este número? | `convert_date.py` | (interativo) |
| O que foi baixado pelo navegador, de onde e para onde? | `downloads_chrome.py` | `--filtro` |
| Resumo geral de navegação: domínios/URLs mais visitados, buscas, visitas por dia | `resumo_navegacao.py` | `--site`, `--por-dia` |
| Não sei o que tem neste banco SQLite nem onde estão as datas | `mapa_sqlite.py` | `--so-datas` |
| Quem é esse número? Tem contato apagado? Números fora da agenda? | `contatos_merge.py` | `--so-apagados` |
| Essa foto foi editada? A data bate com o GPS? | `exif_fotos.py` | `--so-alertas` |

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

### `convert_date.py` — conversor de datas

Interativo: pergunta o número e o fuso e tenta descobrir o formato pela quantidade de dígitos.

```powershell
python ferramentas\convert_date.py
```

Tabela de apoio:

| Dígitos | Formato | Onde aparece |
|---|---|---|
| 9 | Cocoa, segundos desde 2001 | iOS |
| 10 | Unix, segundos desde 1970 | SQLite, Linux |
| 13 | Unix, milissegundos | Android (SMS, chamadas) |
| 16 | Unix, microssegundos | Firefox |
| 17 | microssegundos desde 1601 | Chrome, Edge |
| 18 | FILETIME, 100 ns desde 1601 | **Windows** (Registro, Prefetch, EVTX) |
| 18 | Cocoa, nanossegundos desde 2001 | iOS recente |

**Limitação conhecida:** valores de 18 dígitos do Windows (FILETIME, ~1.3e17) são tratados como Cocoa em nanossegundos e saem com data errada (por exemplo, 2026 vira 2005). Para FILETIME, confira à mão: `(valor / 10_000_000) - 11644473600` dá os segundos Unix. No Windows, nomes de fuso como `America/Sao_Paulo` precisam do pacote `tzdata` (`pip install tzdata`); com número (`-3`) funciona sempre.

### `downloads_chrome.py` — downloads do navegador

Lê as tabelas `downloads` e `downloads_url_chains` do `History` (Chrome/Edge/Brave). Mostra nome e pasta de destino, URL usada para baixar e URL final (se houve redirecionamento), página de origem, início/fim/duração, tamanho, estado, classificação de perigo e hash (quando o navegador guardou).

```powershell
python ferramentas\downloads_chrome.py "C:\evidencia\History" --fuso -3 --csv downloads.csv
```

Atenção: o `History` registra que o navegador **baixou** o arquivo; se ele ainda existe no disco, ou foi aberto/executado, confirme em outra fonte (sistema de arquivos, Prefetch etc.).

### `resumo_navegacao.py` — resumo geral do histórico

Junta `urls`, `visits` e `keyword_search_terms` e responde de uma vez as perguntas mais comuns de quesito: primeira/última/intermediária visita (geral, por domínio ou por site escolhido), domínios e URLs mais visitados, páginas de passagem (redirecionamentos) e termos pesquisados.

```powershell
python ferramentas\resumo_navegacao.py "C:\evidencia\History" --site gov.br --por-dia
```

| Opção | Efeito |
|---|---|
| `--site texto` | detalha só URLs que contenham este texto |
| `--dia AAAA-MM-DD` | considera só este dia (no fuso escolhido) |
| `--por-dia` | mostra a contagem de visitas por dia |
| `--csv arquivo.csv` | salva a tabela por domínio |

### `mapa_sqlite.py` — mapa de um banco desconhecido

Para um banco SQLite qualquer (WhatsApp, apps de mensagem, bancos de apps Android/iOS), mostra por tabela: número de linhas, colunas, quantas têm valor, um exemplo e, principalmente, **quais colunas parecem datas**, em qual formato e o intervalo já convertido. Ponto de partida para um banco que você nunca viu.

```powershell
python ferramentas\mapa_sqlite.py "C:\evidencia\algum_banco.db" --so-datas
```

Detecta datas pela ordem de grandeza do número — é uma **pista**, não uma prova; confira o nome da coluna e alguns valores.

### `contatos_merge.py` — contatos + chamadas + SMS

Cruza `contacts2.db` (agenda) com chamadas e SMS pelo número de telefone (compara só os últimos 9 dígitos, pra casar `+55 11 9...`, `011 9...` e `9...` como o mesmo número). Para cada contato mostra nome, telefones, e-mails, conta de origem, se está apagado/na lixeira, apps ligados (WhatsApp, Signal, Telegram...) e, por número, quantidade e primeira/última chamada e SMS. No fim lista os números que aparecem em chamadas/SMS mas não estão na agenda.

```powershell
python ferramentas\contatos_merge.py --contacts "C:\evidencia\contacts2.db" --calls "C:\evidencia\calllog.db" --sms "C:\evidencia\mmssms.db" --fuso -3
```

| Opção | Efeito |
|---|---|
| `--so-apagados` | só contatos marcados como apagados/na lixeira |
| `--csv arquivo.csv` | salva a tabela de contatos |

No Samsung, `contacts2.db` e `calllog.db` ficam em `com.samsung.android.providers.contacts/databases`; no Android puro, as chamadas ficam dentro do próprio `contacts2.db` (tabela `calls`).

### `exif_fotos.py` — EXIF de fotos e inconsistências

Lê o EXIF de JPEGs sem precisar instalar nada (parser próprio) e aponta o que merece atenção: foto sem EXIF (print de tela, reenviada por app), `DateTime` diferente de `DateTimeOriginal` (editada depois), campo `Software` preenchido, hora do GPS incompatível com a data local, arquivo modificado no sistema antes da captura.

```powershell
python ferramentas\exif_fotos.py "C:\evidencia\fotos" --hash --so-alertas --csv fotos.csv
```

| Opção | Efeito |
|---|---|
| `--hash` | calcula SHA-256 de cada foto |
| `--so-alertas` | mostra só as fotos com algum `[!]` |
| `--csv arquivo.csv` | salva a tabela |

Alertas são **pistas**, não prova: registre como fato ("Software preenchido com X"), nunca como conclusão ("foto foi editada").

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
