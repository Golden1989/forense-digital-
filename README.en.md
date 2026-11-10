# Digital Forensics — Study Notes

[![tests](https://github.com/Golden1989/forense-digital-/actions/workflows/tests.yml/badge.svg)](https://github.com/Golden1989/forense-digital-/actions/workflows/tests.yml)

🌐 [Ler em português](README.md)

Study repository for a digital forensics course: tool guides, methodology and commands organized as I learn. Nothing here is case-specific — **no disk image, no filled-in report, no evidence data**.

## Why there's no image or report here

The forensic image and the solved report are left out on purpose. They're coursework assessment material — publishing them would hand the exam answer to anyone taking the course later, even years later (it's common for the same image to be reused across classes). What lives here is tool knowledge, the **"how"**, never the **"what this specific exam asked"**.

If an example below uses a case name, a company or a question number, it's **fictional**, written only to illustrate the method.

**Exception:** [`docs/en/fictional-case.md`](docs/en/fictional-case.md) uses a **public** forensic image (unrelated to the course) to show this repository's scripts working on a fictional investigation end to end — questions, findings and conclusion.

## Contents

| File | Content |
|---|---|
| [`docs/en/methodology.md`](docs/en/methodology.md) | How to approach an image "in the dark": investigation order, how to define the questions to answer, what makes a file suspicious |
| [`docs/en/fictional-case.md`](docs/en/fictional-case.md) | Complete fictional case using a public image (Digital Corpora): questions, findings and conclusion using this repository's scripts |
| [`docs/en/hashes.md`](docs/en/hashes.md) | How to hash a forensic image (PowerShell and WSL), MD5/SHA-1/SHA-256/SHA-512, and why the `.E01` file's hash differs from the acquired content's hash |
| [`docs/en/sleuthkit.md`](docs/en/sleuthkit.md) | Sleuth Kit (TSK) command reference, organized by the 6 layers of an image, with ready-to-run terminal recipes (Linux/WSL) |
| [`docs/en/iped.md`](docs/en/iped.md) | IPED guide: processing, analysis, bookmarks, export, configuration, disk anatomy |
| [`docs/en/windows-registry.md`](docs/en/windows-registry.md) | Windows Registry: hives, UserAssist, Prefetch, RunMRU, RecentDocs, USBSTOR/MountedDevices, Event Log, Windows Search, with a review quiz |
| [`docs/en/smartphone.md`](docs/en/smartphone.md) | Android and iOS forensics: extraction levels, BFU/AFU, SQLite (WAL/SHM), each system's artifacts, date formats, Chrome, ADB, forensic reasoning, with a review quiz |
| [`docs/en/tools.md`](docs/en/tools.md) | Python scripts in `ferramentas/`: how to run them, options explained, which script answers which question (timeline, installed apps, Chrome session, favicons, dates) |

## Scripts

[`ferramentas/`](ferramentas/) folder: Python scripts that only read the evidence (never write anything into it) and automate common forensic questions. Step-by-step and every option for each script: [`docs/en/tools.md`](docs/en/tools.md).

> **WhatsApp viewer (iOS and Android):** a larger tool with a browser interface, kept in its own folder with its own README: [`ferramentas/visualizador_whatsapp/`](ferramentas/visualizador_whatsapp/README.en.md).

| Script | Answers | Example output (fictional) |
|---|---|---|
| `analisa_packages.py` | When each app was installed/updated, by whom, and which user apps have the most sensitive permissions | ` 3  2025-10-30 14:02:11  com.example.messenger  (installer: com.android.vending)  <-- LAST` |
| `linha_do_tempo.py` | What happened on a given day/period, merging SMS, calls, browsing and app installs into one timeline | `2025-11-03 10:00:00  CHROME  visit  https://www.example.gov/services  Services - Example Gov` |
| `sessao_chrome.py` | Which tabs were open when Chrome was closed | `[2] https://www.example.com/cart  My Cart - Example Store` |
| `favicons_fora_do_historico.py` | Whether there's a sign of history clearing (a favicon with no matching page in `History`) | `removed-from-history-page   icon: https://www.gstatic.com/favicon.ico` |
| `resumo_navegacao.py` | Browsing overview: most visited domains/URLs, first and last visit, redirect chains | `1. www.example.gov  visits=3  first: 2025-11-01 09:10:00 \| last: 2025-11-03 10:00:00` |
| `downloads_chrome.py` | What was downloaded by the browser, from which URL and when | `report.pdf  [completed, 2048 bytes]   downloaded from: https://www.example.gov/report.pdf` |
| `mapa_sqlite.py` | What's inside an unknown SQLite database and which columns hold dates | `visit_time  INTEGER  non-null=4  <-- DATE webkit: 2025-11-01 09:10:00 -> 2025-11-03 10:00:00` |
| `contatos_merge.py` | Who the contact behind a number is, and which numbers show up in calls/SMS but aren't in the address book | `#100 John Example   phones: +15559990001 \| calls: 1 [made=1] ...` |
| `exif_fotos.py` | Whether a photo's EXIF metadata (camera, date, GPS) is consistent or altered | `IMG_0231.jpg  taken: 2025-10-12 16:40:02  [!] file modification date is earlier than the photo's` |
| `convert_date.py` | Convert a timestamp number (Android, iOS, Chrome, Windows) into a readable date | `Date: 2025-11-03 15:42:54 -03:00 (Chrome/Edge, microseconds since 1601)` |

## Tests

[`tests/`](tests/): automated tests with [pytest](https://pytest.org/), running every script against **synthetic** SQLite databases and a `packages.xml` (generated in [`tests/dados_fake.py`](tests/dados_fake.py) — fictional names, numbers and URLs, never real evidence). They make sure the scripts still work after any change.

```
pip install -r requirements-dev.txt
pytest
```

## Tools used

- [The Sleuth Kit](https://www.sleuthkit.org/) 4.12.1, via WSL (Ubuntu)
- [IPED](https://github.com/sepinf-inc/IPED) 4.3.1
- FTK Imager
- [DB Browser for SQLite](https://sqlitebrowser.org/)
- [Registry Explorer](https://ericzimmerman.github.io/) (Eric Zimmerman)

## License

[MIT](LICENSE).

## About

Digital forensics student, organizing what I learn in class and in my own testing. 
