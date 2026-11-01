🌐 [Read in English](en/smartphone.md)

# Perícia em smartphones (Android e iOS)

O celular é um computador de bolso: concentra conversas, localização, fotos e navegação. Cada app deixa rastro — a perícia é reconstruir esse rastro sem presumir a motivação por trás dele.

Scripts para automatizar as consultas deste guia (SQLite, EXIF, datas, contatos) estão em [`ferramentas/`](../ferramentas/), documentados em [`docs/ferramentas.md`](ferramentas.md).

## Os quatro níveis de extração

Quanto mais fundo, mais dado — e mais difícil. Parte da informação simplesmente não existe no nível mais superficial.

| Nível | O que alcança | Exige root/jailbreak? |
|---|---|---|
| **1. Lógica** | Dados acessíveis pelo próprio sistema: contatos, SMS, apps | Não |
| **2. Sistema de arquivos** | Estrutura de pastas e arquivos, inclusive bancos dos apps | Depende do método |
| **3. Física** | Imagem completa da memória: recupera **apagados** e fragmentos | Pode exigir root, jailbreak ou chip-off/JTAG |
| **4. Nuvem** | Dados sincronizados (Google, Apple) | Não toca no aparelho |

- Nuvem é útil quando o aparelho está bloqueado ou os dados foram apagados localmente — em geral exige ordem judicial.
- Nem toda ferramenta faz todos os níveis: conhecer essa limitação faz parte do laudo.

## BFU x AFU: o estado do aparelho na apreensão

| | BFU (Before First Unlock) | AFU (After First Unlock) |
|---|---|---|
| **Significa** | Ligado, mas ainda não desbloqueado desde o boot | Já foi desbloqueado ao menos uma vez desde que ligou |
| **Chaves de criptografia** | Protegidas | Várias ficam na memória, mesmo com a tela bloqueada de novo |
| **Acessível** | Info básica, alguns metadados, partes limitadas do sistema de arquivos | Mensagens, fotos, contatos, bancos SQLite, tokens e sessões |
| **Não acessível** | Conversas descriptografadas, bancos completos de apps | — |

Na apreensão: **não desligar**, manter carregado e usar **modo avião** (isolar da rede sem perder o estado AFU).

## SQLite: onde os apps guardam tudo

Banco de dados leve, em um único arquivo, sem servidor — apps e o próprio sistema o usam. Arquivos terminam em `.db` ou `.sqlite`.

- Permite recuperar mensagens (inclusive antigas), ver contatos e relações, e **correlacionar eventos por data/hora**.
- Dados apagados podem sobrar em páginas não sobrescritas e no **WAL**.
- `banco.db-wal` = log das transações recentes. `banco.db-shm` = memória compartilhada. Os três arquivos **andam juntos**: abrir só o `.db` pode mostrar uma tabela vazia ou incompleta quando o dado mais recente ainda está no WAL.

**DB Browser for SQLite** (leitura): abra em modo somente leitura (*Open Database Read Only*). Aba **Browse Data** mostra as linhas; **Execute SQL** roda consultas.

```powershell
winget install DBBrowserForSQLite.DBBrowserForSQLite
```

Consultas comuns:

```sql
-- data de SMS ou chamada (milissegundos Unix) em UTC-3
SELECT datetime(date/1000, 'unixepoch', '-3 hours') FROM sms;

-- visita do Chrome (microssegundos desde 1601) em UTC-3
SELECT datetime(visit_time/1000000 - 11644473600, 'unixepoch', '-3 hours') FROM visits;

-- contatos com telefone (contacts2.db)
SELECT r._id, r.display_name, d.data1 AS telefone
FROM raw_contacts r
JOIN data d ON d.raw_contact_id = r._id
JOIN mimetypes m ON m._id = d.mimetype_id
WHERE m.mimetype LIKE '%phone_v2';
```

`/1000` leva milissegundos a segundos; `- 11644473600` muda a origem de 1601 para 1970; `'unixepoch'` diz ao SQLite que o número é Unix; `'-3 hours'` ajusta o fuso. `JOIN` liga tabelas por uma chave — aqui, cada telefone (`data`) ao seu contato (`raw_contacts`), e `mimetypes` diz que tipo de dado é aquela linha.

## Android: onde olhar

Kernel Linux, camadas: Linux Kernel, HAL, runtime ART, framework Java, aplicações. Antes do Android 4.0 o aparelho montava como pendrive (**MSC**); depois passou a **MTP**, que monta em nível lógico e impede acesso direto ao sistema de arquivos.

| Pasta | O que é |
|---|---|
| `/system` | Sistema operacional |
| `/data` | Dados do usuário (a mais importante na perícia) |
| `/data/data/<app>` | Dados de cada app (`databases/`, `shared_prefs/`) |
| `/data/system` | Configurações do sistema (`packages.xml`, contas) |
| `/data/misc` | Dados auxiliares: `wifi/`, `bluetooth/`, `vpn/`, `keystore/` |
| `/cache`, `/sdcard` | Temporário; armazenamento externo (fotos em `DCIM`) |

| Dado | Arquivo | Notas |
|---|---|---|
| Contatos | `/data/data/com.android.providers.contacts/databases/contacts2.db` | No **Samsung** fica em `com.samsung.android.providers.contacts/databases`. Tabelas: `raw_contacts`, `data`, `mimetypes`, `accounts` |
| Ligações | `contacts2.db` (tabela `calls`) | No Samsung costuma vir separado: `calllog.db`, tabela `calls` |
| SMS | `/data/data/com.android.providers.telephony/databases/mmssms.db` | Tabela `sms`: `type` 1 recebido, 2 enviado |
| Wi-Fi | `/data/misc/wifi/WifiConfigStore.xml` (novos) · `wpa_supplicant.conf` (antigos) | Android 11+: `/data/misc/apexdata/com.android.wifi/` |
| Contas | `/data/system/accounts.db` · `accounts_ce.db` (novos) | Google, Samsung, redes sociais, apps de mensagem |
| Apps instalados | `/data/system/packages.xml` | Datas em hexadecimal; script `analisa_packages.py` |
| Navegação | `/data/data/com.android.chrome/app_chrome/Default/` | Arquivo `History` (SQLite) |
| Localização | `com.google.android.gms` · `com.android.location` | Google Location History |
| WhatsApp | `/data/data/com.whatsapp/databases/msgstore.db` · `wa.db` | `msgstore.db`: mensagens (`messages`, `chat`); `wa.db`: contatos |

**Modo desenvolvedor:** Configurações → Sobre o telefone → toque 7 vezes em "Número da versão" → informe PIN/senha. Em "Opções do desenvolvedor": **Depuração USB** (necessária para ADB) e **Desbloqueio OEM** (desbloqueia o bootloader — pode apagar dados e reduzir a segurança).

**Ferramentas:** ADB para extrair (`adb pull`), DB Browser for SQLite para ler bancos, Autopsy (Android Analyzer / aLEAPP) para estrutura e arquivos apagados.

**Hash de um APK** (fica em `/data/app/<pacote>-<hash>/base.apk`):

```powershell
Get-FileHash "C:\evidencia\data\app\<pasta-do-app>\base.apk" -Algorithm SHA1
```

## iOS: o outro lado

Base Unix (Darwin). Camadas: Core OS, Core Services, Media, Cocoa Touch. Sistema fechado, criptografia forte, controle rígido de apps. Sistema de arquivos **APFS**. iPhones não aceitam MSC: a coleta usa extração lógica específica ou backups (iTunes/iCloud).

- `/System` é o sistema. `/private/var` é o equivalente ao `/data` do Android.
- Cada app tem sua pasta isolada, identificada por um **UUID**: `/private/var/mobile/Containers/Data/Application/<UUID>`.

| Dado | Arquivo |
|---|---|
| Contatos | `/private/var/mobile/Library/AddressBook/AddressBook.sqlitedb` |
| Ligações | `/private/var/mobile/Library/CallHistoryDB/CallHistory.storedata` |
| SMS | `/private/var/mobile/Library/SMS/sms.db` |
| Wi-Fi | `/private/var/preferences/SystemConfiguration/com.apple.wifi.plist` |
| Contas | `/private/var/mobile/Library/Accounts/` |
| Locais | `/private/var/mobile/Library/Caches/com.apple.routined/Cache.sqlite` |
| WhatsApp | Container do app (`ChatStorage.sqlite`, tabelas `ZWAMESSAGE`, `ZWACHATSESSION`) |
| Fotos | `DCIM/` + metadados EXIF |

No iOS as datas costumam ser **Cocoa** (segundos ou nanossegundos desde 2001) — ver a seção de datas.

## Datas: o relógio de cada artefato

Metade dos erros de perícia é data lida no formato errado. O truque: **conte os dígitos**.

| Dígitos | Formato | Onde aparece | Exemplo |
|---|---|---|---|
| 9 | Cocoa: segundos desde 2001 | iOS | `700000000` ≈ 2023-03-08 20:26:40 UTC |
| 10 | Unix: segundos desde 1970 | Linux, SQLite | — |
| 13 | Unix: **milissegundos** | Android (SMS, chamadas) | `1700000000000` = 2023-11-14 19:13:20 (UTC-3) |
| 16 | Unix: microssegundos | Firefox | — |
| 17 | WebKit: microssegundos desde **1601** | Chrome, Edge | `13370000000000000` = 2024-09-05 05:53:20 (UTC-3) |
| 18 | FILETIME: intervalos de 100 ns desde 1601 | **Windows** | `133700000000000000` = 2024-09-05 08:53:20 UTC |
| 18 | Cocoa em nanossegundos desde 2001 | iOS/APFS recente | — |
| hex | Milissegundos Unix em hexadecimal | `packages.xml` (`it`, `ut`, `ft`) | use `convert_date.py` ou `analisa_packages.py` |

As duas leituras de 18 dígitos (Windows e iOS) se confundem; o contexto decide. O `convert_date.py` separa pela faixa de valor e mostra a outra leitura possível.

- **SMS:** `date` = quando o **aparelho** recebeu; `date_sent` = quando a **operadora** enviou. É normal diferirem por segundos.
- Sempre diga o **fuso** no laudo. Banco costuma estar em UTC; o relógio do aparelho pode estar em outro fuso.

**Os relógios de uma foto:**

| Relógio | Quem escreve | O que mede |
|---|---|---|
| Nome do arquivo (`IMG_AAAAMMDD_HHMMSS`) | App da câmera | Data local no momento de salvar |
| `DateTimeOriginal` | Câmera | Momento da captura (hora local, sem fuso) |
| `DateTimeDigitized` | Câmera | Quando a imagem foi digitalizada; em celular costuma ser igual ao Original. É um **horário**, não uma duração |
| `DateTime` | Quem gravou o arquivo por último | Data de modificação do EXIF |
| GPS (data e hora) | Receptor GPS | Sempre UTC. Pode existir **sem coordenadas** |
| `OffsetTime` | Câmera | Fuso do horário local (ex.: `-03:00`) |
| Modificado / Criado no sistema | Sistema de arquivos | Em disco de evidência, "Criado" costuma ser a data da **extração/cópia**, não da foto |

## Chrome: o histórico em tabelas

No celular o Chrome fica em `com.android.chrome/app_chrome/Default/`. No computador, na pasta do perfil. O formato é o mesmo (Chromium: Chrome, Edge, Brave).

| Arquivo / tabela | O que responde |
|---|---|
| `History` → `urls` | Cada URL, título, `visit_count`, `typed_count`, `last_visit_time` |
| `History` → `visits` | Cada acesso: `visit_time`, `from_visit` (de onde veio), `transition` |
| `transition` | Tipo no byte baixo (link, digitada, formulário...). Bits altos: redirecionamento de cliente (`0x40000000`) ou de servidor (`0x80000000`), início/fim de cadeia |
| `keyword_search_terms` | Termos pesquisados |
| `downloads` + `downloads_url_chains` | Nome, pasta, estado, horários e a **URL usada para baixar** |
| `Favicons` | Ícones por página. Pode sobrar após o histórico ser apagado |
| `Sessions/Session_*` | Abas abertas no fechamento (formato SNSS). O número no nome é a **criação** do arquivo, não o fechamento |
| `Local Storage`, `IndexedDB` | Dados persistidos por domínio (pasta com o nome do site) |

- Página "de passagem" (como um login único) aparece como redirecionamento: ela é a visita do meio da cadeia.
- Domínio do **ícone** (ex.: um CDN) ausente do histórico não significa que a pessoa visitou o CDN, nem que algo foi apagado. É um fato a registrar.

## ADB: falando com o aparelho vivo

Exige depuração USB ligada e o aparelho autorizado. Cada comando roda no **computador**; `>` manda a saída para um arquivo.

```powershell
adb devices
adb shell content query --uri content://com.android.contacts/data > contacts_dump.txt
adb shell "content query --uri content://sms/ --projection address:date:body" > sms_export.txt
adb shell content query --uri content://call_log/calls > calls.txt
adb shell dumpsys location > location_log.txt
adb shell dumpsys wifi > wifi.txt
adb shell dumpsys account
adb pull /sdcard/DCIM ./fotos
```

- `adb devices` lista aparelhos conectados e autorizados — o primeiro teste.
- `adb shell` executa um comando **dentro** do aparelho. `content query` consulta um *content provider* (a porta oficial do Android para ler contatos, SMS, chamadas); `--uri` diz qual provedor, `--projection` escolhe as colunas.
- `dumpsys` despeja o estado de um serviço do sistema (localização, Wi-Fi, contas).
- `adb pull origem destino` copia do aparelho para o computador — extração de pastas inteiras, nível lógico.
- Isso é extração **lógica**: só vê o que o sistema entrega. Apagados e bancos internos dos apps pedem os níveis seguintes.

## Como raciocinar: fatos, não vereditos

- **Descreva o fato** e use "compatível com" em vez de "prova". A interpretação cabe ao contexto do caso.
- **Ausência não é prova.** Um app, um SMS ou uma página que não aparece pode ter sido apagado, estar em outra fonte, ou nunca ter existido. Diga qual dessas é possível.
- **Correlacione** artefatos independentes (SMS + Chrome + app instalado, por exemplo). Uma fonte sozinha engana; duas coincidindo sustentam.
- **Mantenha a inconsistência em aberto** até haver outra fonte. Não invente explicação.
- **Não misture fontes** (extrações diferentes, aparelhos diferentes) nem datas de relógios diferentes.
- **Hash antes de mexer**, trabalhe em cópia, mantenha `.db` + `-wal` + `-shm` juntos.
- **Valide à mão** 2 ou 3 linhas do resultado de um script no DB Browser. Script ajuda, mas o perito responde pelo número.

> Regra de ouro: correlacionar artefatos derruba a tentativa de adulterar um só.

## Pegadinhas comuns

- **"Prova" é palavra forte.** Dois artefatos coincidindo são "compatíveis"; o laudo não afirma o que os dados não mostram.
- **Modo avião.** Na apreensão, a resposta certa é *ligar* o modo avião (isolar da rede), não desligar o aparelho — desligar perde o estado AFU.
- **`DateTimeDigitized`** é um horário, não uma duração.
- **Data do arquivo x data da foto.** "Criado" no disco de evidência costuma ser a data da extração. O que fala da foto é o EXIF.
- **Contagens de contatos** mudam conforme a consulta (`raw_contacts` x contatos agrupados, apagados incluídos ou não). Confira no DB Browser antes de escrever o número.
- **Primeiro app instalado** vale só entre apps de **usuário** (`/data/app`). O "primeiro" entre os de sistema é o firmware.
- **`Session_` no Chrome:** o número no nome é a criação do arquivo, não o fechamento da sessão.
- **Banco "vazio".** Um `.db` aberto sem o `-wal` ao lado pode parecer sem dados recentes — confira se os três arquivos foram copiados juntos.

## Quiz de revisão

<details><summary>Quais são os quatro níveis de extração e qual não toca no aparelho?</summary>Lógica, sistema de arquivos, física e nuvem. A de nuvem não toca no aparelho (e a lógica não exige root).</details>

<details><summary>O que é BFU e por que se evita desligar um celular apreendido?</summary>BFU: ligado, mas sem desbloqueio desde o boot, com as chaves protegidas e quase nada acessível. Desligar leva de volta ao BFU; manter ligado e carregado preserva o AFU, onde bancos, mensagens e tokens estão acessíveis.</details>

<details><summary>Por que copiar o .db junto com -wal e -shm?</summary>O WAL guarda transações recentes ainda não consolidadas no arquivo principal. Sem ele, o banco pode parecer vazio ou desatualizado.</details>

<details><summary>Em mmssms.db, o que diferem date e date_sent, e como saber se foi recebido?</summary><code>date</code> é quando o aparelho recebeu; <code>date_sent</code> é quando a operadora enviou. <code>type</code> 1 = recebido, 2 = enviado.</details>

<details><summary>Que formato tem um número Unix de 13 dígitos? E um de 17?</summary>13 dígitos: Unix em milissegundos (Android). 17 dígitos: WebKit/Chrome, microssegundos desde 1601.</details>

<details><summary>Dois formatos têm 18 dígitos. Quais, e como decidir qual é?</summary>FILETIME do Windows (100 ns desde 1601) e Cocoa em nanossegundos (iOS, desde 2001). O contexto (a origem do arquivo) decide; o <code>convert_date.py</code> separa pela faixa do valor e mostra a outra leitura.</details>

<details><summary>Por que o mesmo contato pode aparecer em mais de um raw_contacts?</summary>Cada conta (telefone, Google, um app de mensagem...) cria seu próprio <code>raw_contact</code>. O <code>contact_id</code> agrupa os que são a mesma pessoa. Contar sem agrupar duplica contatos e chamadas.</details>

<details><summary>Como se descobre o primeiro e o último app instalado no Android?</summary>No <code>packages.xml</code>, campo <code>it</code> (hexadecimal, ms Unix), considerando só apps de usuário (<code>/data/app</code>) — os de sistema vêm do firmware e têm quase todos a mesma data.</details>

<details><summary>A foto tem coordenadas GPS só porque existe um bloco GPS no EXIF?</summary>Não necessariamente. O bloco pode ter só data/hora, sem latitude/longitude. É preciso confirmar se as coordenadas estão realmente presentes.</details>

<details><summary>A data "Criada" de uma foto no disco de evidência é a data em que ela foi tirada?</summary>Não necessariamente — é a data do sistema de arquivos no disco onde a evidência está (muitas vezes a da extração/cópia). A captura real está no EXIF (<code>DateTimeOriginal</code>).</details>

<details><summary>O app X não aparece no packages.xml. Isso prova que nunca foi instalado?</summary>Não. Ausência não é prova: pode ter sido desinstalado, estar em outra fonte, ou o arquivo pode ser parcial/de outro formato (Android 12+ usa ABX binário).</details>

<details><summary>O que o número no nome de um arquivo Session_ do Chrome indica?</summary>A criação do arquivo de sessão (WebKit, UTC), não a hora do fechamento. Para estimar o fechamento, usa-se a data de modificação original do arquivo.</details>

<details><summary>Onde ficam SMS e contatos no iOS, e em que formato costumam estar as datas?</summary><code>/private/var/mobile/Library/SMS/sms.db</code> e <code>AddressBook/AddressBook.sqlitedb</code>. As datas costumam ser Cocoa (segundos ou nanossegundos desde 2001).</details>
