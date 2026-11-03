🌐 [Ler em português](../ferramentas.md)

# Python tools (`ferramentas/` folder)

Small scripts that save time when answering forensic questions: date conversion, merging database tables, timelines, first/last event, most visited URL. All of them **only read** the evidence: each database is copied to a temporary folder before it is opened, together with its `-wal` and `-shm` files (without them, recent data is missed).

> Nothing here is specific to one case. The paths below are generic examples: replace them with the path to your evidence.

## 1. How to run a script (step by step)

1. Open **PowerShell**.
2. Go to the repository folder:
   ```powershell
   cd C:\forense-digital
   ```
   `cd` means *change directory*.
3. Check that Python is installed:
   ```powershell
   python --version
   ```
   If you get "not recognized", try `py --version` and use `py` instead of `python` in the commands.
4. Ask any script for help (all of them except `sessao_chrome.py` accept `--help`):
   ```powershell
   python ferramentas\linha_do_tempo.py --help
   ```

### Anatomy of a command

```powershell
python ferramentas\linha_do_tempo.py --chrome "C:\evidence\History" --fuso utc --dia 2025-11-03
```

| Part | What it is |
|---|---|
| `python` | the program that runs the script |
| `ferramentas\linha_do_tempo.py` | which script to run (its path) |
| `--chrome "C:\evidence\History"` | an **option** (starts with `--`) followed by its **value** |
| `--fuso utc` | another option with a value |
| `--so-paginas`, `--url-completa` | options without a value: they switch a behavior on |

Syntax rules:
- **A path with spaces or accents goes inside quotes**: `"C:\my case\History"`.
- To split a long command over several lines in PowerShell, end the line with a backtick `` ` ``.
- The order of options does not matter.
- Save results (`--csv`) **outside** the evidence folder. `.csv` files are in this repository's `.gitignore` so they are not pushed by mistake.

## 2. Which script answers which question

| Question | Script | Main option |
|---|---|---|
| Which was the first / last app installed? | `analisa_packages.py` | (marks `PRIMEIRO` and `ULTIMO`) |
| How many apps did the user install and how many permissions does each have? | `analisa_packages.py` | `--so-usuario` |
| What happened on a given day (SMS, calls, browsing, installs)? | `linha_do_tempo.py` | `--dia` |
| Which site / URL was visited the most? | `linha_do_tempo.py` | `--top` |
| Show only one site in the timeline | `linha_do_tempo.py` | `--filtro` |
| Which page was open when Chrome closed? | `sessao_chrome.py` | (single argument) |
| Are there favicons for pages that are not in the history (cleared history?) | `favicons_fora_do_historico.py` | (two comparisons, A and B) |
| First / last / middle visit of a site, most visited, redirect pages, searches | `resumo_navegacao.py` | `--site`, `--por-dia` |
| Which URL was used to download a file? When and where to? | `downloads_chrome.py` | `--filtro` |
| Which tables does this unknown database have, and where are the dates? | `mapa_sqlite.py` | `--so-datas`, `--tabela` |
| Phone model, dates and GPS of photos; any inconsistency? | `exif_fotos.py` | `--so-alertas` |
| Contacts + calls + SMS together; deleted contacts; numbers not in the address book | `contatos_merge.py` | `--so-apagados` |
| What date is this number? | `convert_date.py` | (value on the command line) |

## 3. The scripts

### `analisa_packages.py` — installed apps (Android)

Reads `packages.xml` (in `/data/system/`). Shows total packages, user apps (`/data/app`) in install order with **PRIMEIRO** (first) and **ULTIMO** (last), and the ones with the most permissions.

```powershell
python ferramentas\analisa_packages.py "C:\evidence\data\system\packages.xml" --so-usuario --csv summary.csv
```

| Option | Effect |
|---|---|
| `--so-usuario` | only apps in `/data/app` (system apps come from the firmware and almost all share the same date) |
| `--fuso` | `utc` or hours (default: `-3`) — use the same timezone as the other scripts when cross-referencing output |
| `--csv file.csv` | writes the full table in chronological order |

Notes: `it` (first install) and `ut` (last update) are hexadecimal in the XML; the script converts them. The sensitive-permissions column is empty on Android 10 because runtime permissions live in `runtime-permissions.xml`. On Android 12+ `packages.xml` is binary (ABX) and this script cannot read it.

### `linha_do_tempo.py` — unified timeline

Merges SMS, calls, Chrome visits and app installs into one sorted list, in the time zone you choose.

```powershell
python ferramentas\linha_do_tempo.py `
  --sms "C:\evidence\mmssms.db" `
  --calls "C:\evidence\calllog.db" `
  --chrome "C:\evidence\History" `
  --packages "C:\evidence\packages.xml" `
  --fuso -3 --dia 2025-11-03
```

| Option | Effect |
|---|---|
| `--sms`, `--calls`, `--chrome`, `--packages` | sources (all optional) |
| `--fuso` | `utc` or hours offset (`-3`, `-5`, `+1`). Default: `-3` |
| `--dia YYYY-MM-DD` | only that day, **in the chosen time zone** |
| `--filtro text` | only events with this text in URL/title/detail |
| `--top N` | before the timeline, the N most visited Chrome URLs |
| `--url-completa` | do not truncate URLs (useful to see full parameters) |
| `--csv file.csv` | save the result |

Date formats handled: SMS and calls in Unix milliseconds (13 digits); Chrome in microseconds since 1601 (17 digits); `packages.xml` in hexadecimal.
Limits: Android/Chrome layout only. On iOS `sms.db` uses dates since 2001 and different tables; WhatsApp is not covered.

### `sessao_chrome.py` — tabs open at closing time

Reads a Chrome session file (`Session_<number>`, in the profile's `Sessions` folder) and shows the tabs, each tab's page list and the **current page**.

```powershell
python ferramentas\sessao_chrome.py "C:\evidence\Session_13422390936860763"
```

Warning: the number in the file name is the **creation** time of the session file (microseconds since 1601, UTC), not the closing time. To estimate when the browser closed, use the file's **original** modified time (for example, `7z l -slt archive.zip` shows `Modified` before extraction changes anything).

### `favicons_fora_do_historico.py` — favicons without history

Cross-checks Chrome's `Favicons` database against `History`. Two comparisons:
- **A) Pages:** `page_url` in Favicons × URLs in History.
- **B) Icons:** the domain the icon was downloaded from × domains in History (e.g. the Google search icon comes from a CDN that never appears as a visited page).

```powershell
python ferramentas\favicons_fora_do_historico.py --favicons "C:\evidence\Favicons" --history "C:\evidence\History" --fuso utc --csv favicons.csv
```

| Option | Effect |
|---|---|
| `--so-paginas` | only comparison A |
| `--fuso` | `utc` (default) or hours |
| `--csv` | save the result |

Interpretation: a difference **does not prove** history was cleared. Chrome-generated pages and CDNs show up here. Report it as a fact.

### `resumo_navegacao.py` — Chrome history summary

Joins `urls`, `visits` and `keyword_search_terms` from `History` and answers in one go: first and last visit (overall and per domain), **middle visit** (the one in the middle of the time-sorted list), most visited domains and URLs, **pass-through pages** (redirects, such as the gov.br single sign-on), search terms and visits per day.

```powershell
python ferramentas\resumo_navegacao.py "C:\evidence\History" --fuso utc
python ferramentas\resumo_navegacao.py "C:\evidence\History" --site gov.br --url-completa
python ferramentas\resumo_navegacao.py "C:\evidence\History" --dia 2025-11-03 --por-dia --csv domains.csv
```

| Option | Effect |
|---|---|
| `--fuso` | `utc` (default) or hours (`-3`) |
| `--site text` | details only URLs containing the text: first, middle and last visit, navigation types and redirects |
| `--dia YYYY-MM-DD` | only that day (in the chosen time zone) |
| `--top N` | size of the rankings (default 10) |
| `--por-dia` | visits per day, with bars |
| `--url-completa` | do not truncate URLs |
| `--csv file.csv` | per-domain table: visits, first, middle, last |

Cautions: "visits" here are rows of the `visits` table (each access); `urls.visit_count` may differ. "Middle" is the visit in the middle by time, not the redirect *page*: for that, see the "pass-through pages" section (role `inicio` = start, `passagem` = hop, `fim` = end of the chain).

### `downloads_chrome.py` — Chrome downloads

Joins `downloads` and `downloads_url_chains`. For each file: name and folder, the **URL used to download** (start of the chain), the final URL (if redirected), source page, start, end, duration, size, state, danger classification and whether it was opened.

```powershell
python ferramentas\downloads_chrome.py "C:\evidence\History" --fuso -3
python ferramentas\downloads_chrome.py "C:\evidence\History" --filtro .zip --csv downloads.csv
```

| Option | Effect |
|---|---|
| `--fuso` | `utc` (default) or hours |
| `--filtro text` | only downloads whose name, URL or source page contain the text |
| `--url-completa` | do not truncate URLs |
| `--csv file.csv` | saves everything, including hash, MIME type and last access |

`History` shows that Chrome recorded the download. Whether the file still exists or was executed needs another source (file system, Prefetch, Event Log).

### `mapa_sqlite.py` — map of an unknown database

For each table: row count, columns, type, how many rows have a value, an example and **which columns look like dates** (format and range already converted). A good starting point for app databases (WhatsApp, messengers, etc.).

```powershell
python ferramentas\mapa_sqlite.py "C:\evidence\database.db" --fuso -3
python ferramentas\mapa_sqlite.py "C:\evidence\database.db" --so-datas
python ferramentas\mapa_sqlite.py "C:\evidence\database.db" --tabela messages --amostra 5
```

| Option | Effect |
|---|---|
| `--so-datas` | list only date-like columns |
| `--tabela name` | only that table (exact name) |
| `--amostra N` | with `--tabela`, show N sample rows |
| `--fuso` | time zone of converted dates |

Detection looks at the magnitude of the number (up to 500 values per column, accepts only dates between 2005 and next year). It is a **hint**: 9–10 digit IDs can look like dates, and the script warns when the column name does not suggest a date. Confirm with the column name and a few values.

### `exif_fotos.py` — EXIF and inconsistencies in photos

Reads JPEG EXIF **with nothing to install** (own reader) and shows make, model, software, `DateTime`, `DateTimeOriginal`, `DateTimeDigitized`, time zone (`OffsetTime`), GPS and the file-system dates. It flags with `[!]`: no EXIF, `DateTime` or `DateTimeDigitized` different from `DateTimeOriginal`, Software field filled in, GPS time inconsistent with local date + offset, file modified before capture.

```powershell
python ferramentas\exif_fotos.py "C:\evidence\DCIM\Camera"
python ferramentas\exif_fotos.py "C:\evidence\DCIM" --so-alertas --hash --csv photos.csv
```

| Option | Effect |
|---|---|
| `--so-alertas` | only photos with `[!]` |
| `--hash` | include each photo's SHA-256 |
| `--csv file.csv` | save the table |

Limits: JPEG only (PNG, HEIC, etc. show as "no EXIF"). EXIF dates are the device's local time; file-system dates measure something else (extraction, copy). An alert is a hint, not a conclusion: record the fact and keep the inconsistency open until another source confirms it.

### `contatos_merge.py` — contacts + calls + SMS

Cross-references by phone number: `contacts2.db` (who the contact is), `calllog.db` (calls) and `mmssms.db` (SMS). It groups `raw_contacts` by `contact_id` (the same person appears once per account: phone, Google, Signal...), and shows name, phones, e-mails, accounts, linked apps, deleted/in trash, plus per contact the count, first and last call and SMS. At the end it lists the **numbers that appear in calls/SMS but are not in the address book**.

```powershell
python ferramentas\contatos_merge.py --contacts "C:\evidence\contacts2.db" `
  --calls "C:\evidence\calllog.db" --sms "C:\evidence\mmssms.db" --fuso -3 --csv contacts.csv
python ferramentas\contatos_merge.py --contacts "C:\evidence\contacts2.db" --so-apagados
```

| Option | Effect |
|---|---|
| `--contacts` | `contacts2.db` (required) |
| `--calls` | `calllog.db`, or another database with a `calls` table (optional) |
| `--sms` | `mmssms.db` (optional) |
| `--so-apagados` | only contacts marked as deleted or in trash |
| `--fuso`, `--csv` | as in the other scripts |

Number matching: digits only, comparing the last 9 (ignores `+55`, the area-code zero). Short numbers (like 611) match only if identical. On Samsung, `contacts2.db` and `calllog.db` live in `com.samsung.android.providers.contacts/databases`; keep the `-wal` and `-shm` files next to them.

### `convert_date.py` — date converter

Guesses the format from the digit count and **also shows the other plausible readings** (between 2010 and 2035), because some formats get confused. Accepts decimal and hexadecimal.

```powershell
python ferramentas\convert_date.py 1762202574476 --fuso -3
python ferramentas\convert_date.py 134159021410000000 --fuso utc
python ferramentas\convert_date.py 0x198d35fa587 --fuso -3
python ferramentas\convert_date.py 1762202574476 --formato unix-us
python ferramentas\convert_date.py                      # no arguments: asks for the value and time zone
```

| Option | Effect |
|---|---|
| `valor` | number (decimal, `0x...` or plain hexadecimal) |
| `--fuso` | `utc` (default), hours (`-3`, `-3:30`) or name (`America/Sao_Paulo`, needs `pip install tzdata` on Windows) |
| `--formato` | force a format: `cocoa-s`, `unix-s`, `unix-ms`, `unix-us`, `webkit`, `filetime`, `cocoa-ns` |

| Digits | Format (`--formato`) | Where it appears |
|---|---|---|
| 9 | Cocoa, seconds since 2001 (`cocoa-s`) | iOS |
| 10 | Unix, seconds since 1970 (`unix-s`) | SQLite, Linux |
| 13 | Unix, milliseconds (`unix-ms`) | Android (SMS, calls) |
| 16 | Unix, microseconds (`unix-us`) | Firefox |
| 17 | microseconds since 1601 (`webkit`) | Chrome, Edge |
| 18 | FILETIME, 100 ns since 1601 (`filetime`) | **Windows** (Registry, Prefetch, EVTX) |
| 18 | Cocoa, nanoseconds since 2001 (`cocoa-ns`) | recent iOS |

The two 18-digit formats are told apart by value range (FILETIME from 1970 to 2235 sits between 1.16e17 and 2e17). If the context points to the other one, use `--formato`. Values outside every range are read as Cocoa seconds.

## 4. Conversions inside SQLite (no Python)

In DB Browser, **Execute SQL** tab:

```sql
-- Unix milliseconds (Android)
SELECT datetime(date/1000, 'unixepoch', '-3 hours') FROM sms;

-- Chrome (microseconds since 1601)
SELECT datetime(visit_time/1000000 - 11644473600, 'unixepoch', '-3 hours') FROM visits;
```

`/1000` (or `/1000000`) converts to seconds; `- 11644473600` moves 1601 to 1970; `'unixepoch'` tells SQLite the base; `'-3 hours'` adjusts the time zone.

## 5. Good practice

- **Hash the evidence** before touching it and check again afterwards.
- **Keep `.db`, `-wal` and `-shm` together.** A `calllog.db` opened alone can look empty while the calls are in the `-wal`.
- **Check by hand** 2 or 3 events from the output in DB Browser.
- Write **facts and hypotheses** in the report, never motives. "Consistent with" is safer than "proved".
- Record the **time zone** of every timestamp. The device clock may use another zone (EXIF stores `OffsetTime`).

## 6. Common problems

| Message | What to do |
|---|---|
| `'python' is not recognized` | Use `py` or install Python with "Add to PATH" ticked |
| `No such file or directory` | The path is wrong or missing quotes (spaces/accents) |
| `no such table: calls` | The database was opened without its `-wal`; keep the 3 files together |
| Empty output with `--dia` | The day is read in the `--fuso` zone; check the zone |
| `Este arquivo não parece ser uma sessão do Chrome` | The `SNSS` header is missing; it is another file type |
| `Tabela 'downloads' nao encontrada` | The file is not a Chromium `History` (check name and folder) |
