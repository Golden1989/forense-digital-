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
4. Ask any script for help (all of them except `convert_date.py` and `sessao_chrome.py` accept `--help`):
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
| What date is this number? | `convert_date.py` | (interactive) |
| What was downloaded by the browser, from where and to where? | `downloads_chrome.py` | `--filtro` |
| General browsing summary: most visited domains/URLs, searches, visits per day | `resumo_navegacao.py` | `--site`, `--por-dia` |
| I don't know what's in this SQLite database or where the dates are | `mapa_sqlite.py` | `--so-datas` |
| Who is this number? Any deleted contact? Numbers missing from the address book? | `contatos_merge.py` | `--so-apagados` |
| Was this photo edited? Does the date match the GPS? | `exif_fotos.py` | `--so-alertas` |

## 3. The scripts

### `analisa_packages.py` — installed apps (Android)

Reads `packages.xml` (in `/data/system/`). Shows total packages, user apps (`/data/app`) in install order with **PRIMEIRO** (first) and **ULTIMO** (last), and the ones with the most permissions.

```powershell
python ferramentas\analisa_packages.py "C:\evidence\data\system\packages.xml" --so-usuario --csv summary.csv
```

| Option | Effect |
|---|---|
| `--so-usuario` | only apps in `/data/app` (system apps come from the firmware and almost all share the same date) |
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

### `convert_date.py` — date converter

Interactive: asks for the number and the time zone and guesses the format from the digit count.

```powershell
python ferramentas\convert_date.py
```

Quick reference:

| Digits | Format | Where it appears |
|---|---|---|
| 9 | Cocoa, seconds since 2001 | iOS |
| 10 | Unix, seconds since 1970 | SQLite, Linux |
| 13 | Unix, milliseconds | Android (SMS, calls) |
| 16 | Unix, microseconds | Firefox |
| 17 | microseconds since 1601 | Chrome, Edge |
| 18 | FILETIME, 100 ns since 1601 | **Windows** (Registry, Prefetch, EVTX) |
| 18 | Cocoa, nanoseconds since 2001 | recent iOS |

**Known limitation:** 18-digit Windows values (FILETIME, ~1.3e17) are treated as Cocoa nanoseconds and give a wrong date (for example, 2026 becomes 2005). For FILETIME, check by hand: `(value / 10_000_000) - 11644473600` gives Unix seconds. On Windows, zone names such as `America/Sao_Paulo` need the `tzdata` package (`pip install tzdata`); a number (`-3`) always works.

### `downloads_chrome.py` — browser downloads

Reads the `downloads` and `downloads_url_chains` tables from `History` (Chrome/Edge/Brave). Shows the file name and destination folder, the URL used to download and the final URL (if redirected), the originating page, start/end/duration, size, state, danger classification and hash (when the browser kept one).

```powershell
python ferramentas\downloads_chrome.py "C:\evidence\History" --fuso -3 --csv downloads.csv
```

Warning: `History` records that the browser **downloaded** the file; whether it still exists on disk, or was opened/run, must be confirmed from another source (file system, Prefetch, etc.).

### `resumo_navegacao.py` — general browsing summary

Joins `urls`, `visits` and `keyword_search_terms` and answers the most common questions at once: first/last/middle visit (overall, per domain or for a chosen site), most visited domains and URLs, pass-through pages (redirects) and searched terms.

```powershell
python ferramentas\resumo_navegacao.py "C:\evidence\History" --site gov.br --por-dia
```

| Option | Effect |
|---|---|
| `--site text` | only details URLs containing this text |
| `--dia YYYY-MM-DD` | only this day (in the chosen time zone) |
| `--por-dia` | shows the visit count per day |
| `--csv file.csv` | saves the per-domain table |

### `mapa_sqlite.py` — map of an unknown database

For any SQLite database (WhatsApp, messaging apps, Android/iOS app databases), shows per table: row count, columns, how many have a value, an example, and, most importantly, **which columns look like dates**, in what format, and the converted range. A starting point for a database you've never seen.

```powershell
python ferramentas\mapa_sqlite.py "C:\evidence\some_database.db" --so-datas
```

Detects dates from the order of magnitude of the number — it's a **clue**, not proof; check the column name and a few values.

### `contatos_merge.py` — contacts + calls + SMS

Cross-references `contacts2.db` (address book) with calls and SMS by phone number (matches only the last 9 digits, so `+55 11 9...`, `011 9...` and `9...` are treated as the same number). For each contact, shows name, phone numbers, emails, source account, whether it's marked deleted/trashed, linked apps (WhatsApp, Signal, Telegram...), and, per number, how many calls/SMS and their first/last timestamp. At the end, lists numbers that appear in calls/SMS but are missing from the address book.

```powershell
python ferramentas\contatos_merge.py --contacts "C:\evidence\contacts2.db" --calls "C:\evidence\calllog.db" --sms "C:\evidence\mmssms.db" --fuso -3
```

| Option | Effect |
|---|---|
| `--so-apagados` | only contacts marked deleted/trashed |
| `--csv file.csv` | saves the contacts table |

On Samsung devices, `contacts2.db` and `calllog.db` live under `com.samsung.android.providers.contacts/databases`; on stock Android, calls live inside `contacts2.db` itself (`calls` table).

### `exif_fotos.py` — photo EXIF and inconsistencies

Reads EXIF from JPEGs with no dependencies (a small built-in parser) and flags what deserves attention: no EXIF at all (screenshot, re-sent via an app), `DateTime` different from `DateTimeOriginal` (edited afterwards), a filled-in `Software` field, GPS time inconsistent with the local date, or a file modified on disk before its capture time.

```powershell
python ferramentas\exif_fotos.py "C:\evidence\photos" --hash --so-alertas --csv photos.csv
```

| Option | Effect |
|---|---|
| `--hash` | computes SHA-256 for each photo |
| `--so-alertas` | shows only photos with a `[!]` flag |
| `--csv file.csv` | saves the table |

Flags are **clues**, not proof: record them as facts ("Software field set to X"), never as a conclusion ("the photo was edited").

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
