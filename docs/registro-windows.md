🌐 [Read in English](en/windows-registry.md)

# Registro do Windows — artefatos forenses

## O conceito de artefato

Artefato digital é um rastro que o sistema ou um programa deixa e que permite reconstruir o que o usuário fez. Um artefato sozinho raramente prova tudo — a força da perícia está em **correlacionar** vários. Prefetch diz *o que* rodou; UserAssist e o `NTUSER.DAT` ajudam a dizer *quem*.

## Hives — os blocos do Registro

O Registro é o banco de configurações do Windows. Cada arquivo dele é uma *hive*.

| Hive | Escopo | O que guarda |
|---|---|---|
| **SAM** | Máquina | Contas locais, SIDs, hashes de senha |
| **SYSTEM** | Máquina | Hardware, drivers, USBSTOR (pendrives), ComputerName, TimeZoneInformation, MountedDevices, Services |
| **SOFTWARE** | Máquina | Programas instalados, Run, Uninstall, versão do Windows, App Paths |
| **SECURITY** | Máquina | Políticas e auditoria |
| **NTUSER.DAT** | Usuário | UserAssist, RecentDocs, RunMRU, TypedPaths, Run, MountPoints2 |

- Hives da máquina: `C:\Windows\System32\config`. `NTUSER.DAT`: `C:\Users\<usuário>\`.
- Pergunta sobre uma **pessoa específica** → `NTUSER.DAT`. Sobre a **máquina** → SYSTEM/SOFTWARE.
- Programas executados pela interface → `NTUSER.DAT` (UserAssist). Pendrives conectados → SYSTEM (USBSTOR); `MountPoints2` liga o volume ao usuário.
- Ferramenta: **Registry Explorer** (Eric Zimmerman), abre hives offline. Precisa do .NET 9 Desktop Runtime: `winget install Microsoft.DotNet.DesktopRuntime.9`.

## Anti-forense

- O usuário comum edita o próprio `NTUSER.DAT`; o SYSTEM exige administrador.
- Apagar o rastro em um lugar só não basta: o mesmo fato tende a aparecer em mais de uma hive e também no Prefetch e no Event Log.
- Valores apagados no Registro às vezes são recuperáveis, dependendo da ferramenta.
- **Regra de ouro:** correlacionar artefatos derruba a tentativa de adulterar um só.

## Prefetch

Um arquivo `.pf` por programa executado, em `C:\Windows\Prefetch`. Registra o nome do executável, quantas vezes rodou, a última execução, as últimas execuções e os arquivos/pastas referenciados.

- **Não prova quem rodou** nem **o que o programa fez**.
- Sobrevive à desinstalação do programa.
- O sufixo do nome do arquivo é um hash do caminho do executável **e** da linha de comando — por isso um mesmo programa pode ter vários `.pf` (parâmetros como `/prefetch:N` geram arquivos diferentes).
- Contagem de execuções não é o mesmo que aberturas pelo usuário: serviços e atualizadores também geram `.pf`.
- O valor `EnablePrefetcher` (`...\Memory Management\PrefetchParameters`) controla o que é gerado (desligado / só aplicativos / só boot / ambos) — os números exatos variam entre fontes, **confira a documentação oficial da Microsoft antes de citar isso num laudo**.

### PECmd — sintaxe

```powershell
& "<caminho>\PECmd.exe" -d "<pasta com os .pf>"
```

- `&` executa o programa pelo caminho completo, quando ele não está no PATH.
- `-d <pasta>` analisa uma pasta inteira; `-f <arquivo>` um único `.pf`.
- `--csv <pasta>` / `--json <pasta>` exportam; `--csvf <nome>` define o nome do CSV.
- Horários saem em UTC — o laudo precisa declarar o fuso usado.
- `Keywords: temp, tmp` só marca caminhos que contêm essas palavras. É filtro de busca, não detector de malware.
- "Created on" = quando o arquivo `.pf` foi copiado pra máquina do perito. "Last run" = a execução real registrada.

## UserAssist

Lista, dentro do perfil de cada usuário, os programas que **aquela pessoa** abriu pela interface gráfica (Explorer, área de trabalho, menu Iniciar). Guarda quantas vezes e quando foi a última.

```
ROOT\Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist\{GUID}\Count
```

- Fica no **NTUSER.DAT** — por isso liga a ação a um usuário específico (o Prefetch não faz isso).
- Os nomes são codificados em **ROT13** (cada letra deslocada 13 posições). Ferramentas como o Registry Explorer decodificam sozinhas.
- Execução só por linha de comando normalmente não aparece aqui.

**Cruzamento útil:** Prefetch (o que rodou) + UserAssist (quem abriu e quantas vezes) + RunMRU (o que foi digitado). Três fontes, uma história.

## RunMRU

Lista dos últimos comandos digitados na caixa Executar (`Win+R`). Guarda o texto exato.

```
ROOT\Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU
```

- *MRU* = Most Recently Used. Posição 0 é a mais recente.
- O Windows grava o texto com um marcador `\1` no fim; ferramentas de análise geralmente mostram sem ele.
- A data ("Opened On") só existe pra posição 0, porque vem do *last write* da própria chave.
- Algo digitado dentro de um `cmd` já aberto não aparece nem aqui, nem no UserAssist.

## RecentDocs

Arquivos e pastas que **este usuário abriu**, organizados por extensão (uma subchave por tipo, mais uma `Folder` pra pastas).

```
ROOT\Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs
```

- Prova que o arquivo foi **aberto**, não que foi **copiado**. O nome continua na lista mesmo se o arquivo for apagado depois.
- Combinado com o USBSTOR (SYSTEM), monta o caso de um pendrive: o SYSTEM diz quando conectou, o RecentDocs diz o que foi aberto naquela janela de tempo.
- Horário só é registrado pra posição 0 de cada subchave.

## Rastreando USB: USBSTOR, MountedDevices, MountPoints2

- **USBSTOR** (hive SYSTEM, `ROOT\ControlSet001\Enum\USBSTOR`): fabricante, modelo, firmware, **número de série**, e as datas *First Installed*, *Last Connected* e *Last Removed* (UTC). Não guarda capacidade nem os arquivos copiados.
  - *Last Removed* vazio = horário não registrado, não significa que o dispositivo ficou plugado.
  - Série com `&` na segunda posição = o dispositivo não tem série própria; o Windows gerou uma. Não identifica o aparelho físico de forma única.
- O USBSTOR sozinho **não diz qual usuário** nem **qual letra de unidade**.
- **MountPoints2** (`NTUSER.DAT`): liga um volume à sessão de um usuário.
- **MountedDevices** (SYSTEM, `ROOT\MountedDevices`): liga o GUID do volume ao número de série e à letra de unidade — é essa chave que fecha o elo entre dispositivo e letra.
- Letras de unidade são **reatribuídas** com o tempo — só confie numa letra junto com o número de série do dispositivo.

## Event Log

Arquivos `.evtx` em `winevt\Logs`. Ferramentas: Event Viewer (`eventvwr.msc`) e EvtxECmd.

| Log | ID | Significado |
|---|---|---|
| Security | 4624 | Logon com sucesso |
| Security | 4625 | Falha de logon |
| Security | 4634 / 4647 | Logoff |
| Security | 4648 | Logon com credenciais explícitas |
| Security | 4672 | Privilégios especiais atribuídos ao logon (normal em contas administrativas) |
| Security | 4800 / 4801 | Tela bloqueada / desbloqueada |
| System | 6005 / 6006 | Serviço de log iniciou / parou (liga/desliga) |
| System | 6008 | Desligamento inesperado |
| System | 1074 | Desligamento iniciado pelo usuário |
| Security | 1102 | Log de auditoria apagado (registra quem apagou) |
| Security | 4688 | Processo criado (só existe se a auditoria de criação de processo estiver ativada — desligada por padrão) |
| Security | 4797 | Consulta de senha em branco de uma conta (rotina comum no logon) |
| Security | 5379 | Credenciais lidas do Gerenciador de Credenciais (rotina comum no logon) |
| System | 104 | Log apagado |

- Logs têm um tamanho máximo padrão (o Security costuma rodar perto de 20 MB); quando enche, pode sobrescrever os eventos mais antigos (*rollover*). Confira a data do primeiro evento antes de assumir que um período mais antigo ainda está ali.
- O arquivo guarda os horários em **UTC**; o Event Viewer mostra no fuso configurado na máquina que está sendo usada para analisar.
- **4672** não é escalada de privilégio — é "privilégios especiais atribuídos ao novo logon", normal pra contas administrativas. No **4624**, o que importa é o **Tipo de Logon**: 2 = interativo (teclado), 3 = rede, 5 = serviço, 7 = desbloqueio, 10 = remoto (RDP), 11 = interativo com cache.
- **4719** (mudança da política de auditoria do sistema) é diferente de **4907** (mudança nas configurações de auditoria de um objeto específico, como um arquivo ou pasta) — não confundir os dois.
- Desligamento normal deixa 1074 + 6006. Desligamento brusco (queda de energia) deixa 6008 e, na próxima inicialização, um Kernel-Power 41.
- Apagar um log deixa rastro: 1102 (Security) e 104 (System). A ferramenta usada pra apagar (Event Viewer ou `wevtutil`) também deixa rastro — vale procurar no UserAssist e no Prefetch.

## Outros artefatos

- **TypedPaths** (`NTUSER.DAT`, `...\Explorer\TypedPaths`): caminhos **digitados** na barra de endereços do Explorer. Digitar um caminho mostra que a pessoa sabia o local exato; não é, por si só, tentativa de ocultar rastro.
- **Windows Search** (`Windows.edb`, formato ESE, aberto com o ESEDatabaseView): um catálogo de metadados (nome, caminho, tamanho, datas, trechos de conteúdo), separado do sistema de arquivos — a linha do índice pode continuar existindo mesmo depois de o arquivo original ser apagado ou sobrescrito. *Carving* recupera **conteúdo** do disco; o índice mostra o **registro** de que o arquivo existiu — são coisas diferentes.
  - Tabelas mais relevantes: `MSysObjects` (estrutura do banco, só nomes), `SystemIndex_PropertyStore` (uma linha por item indexado, com datas e propriedades), `SystemIndex_Gthr` (itens coletados), `SystemIndex_GthrPth` (hierarquia de pastas). As tabelas `SystemIndex_1_DATA_*` e `SystemIndex_1_OCC_*` são partes internas do índice de texto completo — geralmente ignoráveis.
  - Valores em visualizadores crus aparecem em **little-endian**. Datas costumam estar em **FILETIME** (contagem de intervalos de 100 ns desde 1601-01-01 UTC) — pra converter à mão, inverta a ordem dos bytes antes de interpretar o hexadecimal.
- **Recent Files**: atalhos `.lnk` em `AppData\Roaming\Microsoft\Windows\Recent`. Mesma ideia da chave `RecentDocs` do `NTUSER.DAT`.
- **KAPE**: *Targets* (`.tkape`) definem o que coletar; *Modules* (`.mkape`) rodam ferramentas e geram CSV/JSON. `gkape` é a interface gráfica e exige administrador. O KAPE coleta — quem conclui o caso é o perito.

## Comandos usados

| Comando | Pra que serve |
|---|---|
| `Get-FileHash -Algorithm SHA256 "<caminho>"` | Calcula o hash SHA-256 |
| `Set-Alias 7z "C:\Program Files\7-Zip\7z.exe"` | Cria o atalho `7z` nesta sessão do PowerShell |
| `7z l "<zip>"` | Lista o conteúdo sem extrair |
| `7z x "<zip>" -o"<destino>"` | Extrai (sem espaço entre `-o` e o caminho) |
| `Copy-Item "<origem>" "<destino>" -Recurse` | Copia pastas inteiras |
| `explorer "<caminho>"` | Abre a pasta no Explorer |

## Pegadinhas comuns

- **Prefetch** prova que o executável rodou, mas não prova quem rodou nem o que ele fez. Dizer que "não prova nada" é exagero.
- **UserAssist** registra programas abertos pela **interface** (Explorer, menu Iniciar, `Win+R`). O que roda *dentro* de um terminal já aberto não aparece ali.
- **RunMRU** é a caixa **Executar** (`Win+R`), não histórico de terminal. Comando digitado dentro de um `cmd` já aberto fica em outro lugar (histórico do PowerShell, Event Log com auditoria de linha de comando ativada).
- **RecentDocs** mostra arquivo **aberto**, não **transferido**. Letra de unidade é pista, não conclusão — letras são reatribuídas; a ligação confiável entre letra e dispositivo vem de `MountedDevices` e `MountPoints2`.
- Terminologia comum em ferramentas: "Run Counter" = vezes executado; "Focus Time" = tempo com a janela em foco.

## Quiz de revisão

<details><summary>Por que o hash não muda se eu renomear o arquivo?</summary>O hash é calculado só sobre o conteúdo. Nome e data ficam fora.</details>

<details><summary>Qual hive responde "quais pendrives já foram conectados?" e qual responde "o que ESTE usuário executou?"</summary>Pendrives: SYSTEM (USBSTOR). Usuário específico: NTUSER.DAT (UserAssist).</details>

<details><summary>O Prefetch prova quem executou um programa? Por quê?</summary>Não. Ele mostra qual executável rodou, quantas vezes e quando, mas não o usuário. Serviços também geram <code>.pf</code>.</details>

<details><summary>Por que um mesmo programa pode ter vários .pf com sufixos diferentes?</summary>O sufixo é um hash do caminho e da linha de comando. Parâmetros diferentes na execução geram arquivos diferentes.</details>

<details><summary>O que significa um filtro como "Keywords: temp, tmp" numa ferramenta de Prefetch?</summary>É um aviso de que algum caminho referenciado contém essas palavras — um filtro de busca, não prova de malware.</details>

<details><summary>Qual ID indica falha de logon? E desligamento inesperado?</summary>Falha de logon: 4625 (Security). Desligamento inesperado: 6008 (System).</details>

<details><summary>O usuário apagou o próprio rastro no NTUSER.DAT. Como ainda provar a ação?</summary>Correlacionando outras fontes: USBSTOR no SYSTEM (exige administrador para editar), Event Log, valores apagados que às vezes são recuperáveis no Registro, e outros artefatos de arquivos recentes.</details>

<details><summary>Programa rodado só pelo prompt de comando aparece no UserAssist?</summary>Em geral não. UserAssist registra lançamentos pela interface gráfica. O Prefetch registra a execução de qualquer forma; o RunMRU guarda o que foi digitado em Win+R.</details>
