# Digital Forensics — Study Notes

🌐 [Ler em português](README.md)

Study repository for a digital forensics course: tool guides, methodology and commands organized as I learn. Nothing here is case-specific — **no disk image, no filled-in report, no evidence data**.

## Why there's no image or report here

The forensic image and the solved report are left out on purpose. They're coursework assessment material — publishing them would hand the exam answer to anyone taking the course later, even years later (it's common for the same image to be reused across classes). What lives here is tool knowledge, the **"how"**, never the **"what this specific exam asked"**.

If an example below uses a case name, a company or a question number, it's **fictional**, written only to illustrate the method.

## Contents

| File | Content |
|---|---|
| [`docs/en/methodology.md`](docs/en/methodology.md) | How to approach an image "in the dark": investigation order, how to define the questions to answer, what makes a file suspicious |
| [`docs/en/hashes.md`](docs/en/hashes.md) | How to hash a forensic image (PowerShell and WSL), MD5/SHA-1/SHA-256/SHA-512, and why the `.E01` file's hash differs from the acquired content's hash |
| [`docs/en/sleuthkit.md`](docs/en/sleuthkit.md) | Sleuth Kit (TSK) command reference, organized by the 6 layers of an image, with ready-to-run terminal recipes (Linux/WSL) |
| [`docs/en/iped.md`](docs/en/iped.md) | IPED guide: processing, analysis, bookmarks, export, configuration, disk anatomy |
| [`docs/en/windows-registry.md`](docs/en/windows-registry.md) | Windows Registry: hives, UserAssist, Prefetch, RunMRU, RecentDocs, USBSTOR/MountedDevices, Event Log, Windows Search, with a review quiz |

## Scripts

| Script | What it does |
|---|---|
| [`ferramentas/analisa_packages.py`](ferramentas/analisa_packages.py) | Summarizes the `packages.xml` from an Android extraction: total packages, how many are user vs. system, user apps numbered in chronological install order (first and last flagged — only among user apps, since firmware apps mostly share the same date) and the 10 user apps with the most granted permissions. Exports a CSV (opens straight in Excel), already in chronological order but re-sortable by any column. Only reads the file — never writes anything into the evidence folder. |
| [`ferramentas/linha_do_tempo.py`](ferramentas/linha_do_tempo.py) | Merges SMS, calls, Chrome history and installed apps into a single timeline, with timestamps already converted to UTC and UTC-3. Every source is optional — use whichever ones you have. Before opening a database, it copies it (plus any neighboring `-wal`/`-shm` files) into a temp folder, so the original is never touched and data still sitting in the WAL is included. Can filter to a single day and export CSV. |

```bash
python ferramentas/analisa_packages.py path/packages.xml
python ferramentas/analisa_packages.py path/packages.xml --so-usuario
python ferramentas/analisa_packages.py path/packages.xml --csv output.csv

python ferramentas/linha_do_tempo.py --sms mmssms.db --chrome History --calls calllog.db --packages packages.xml --csv timeline.csv
python ferramentas/linha_do_tempo.py --sms mmssms.db --chrome History --dia 2025-11-03
```

## Tools used

- [The Sleuth Kit](https://www.sleuthkit.org/) 4.12.1, via WSL (Ubuntu)
- [IPED](https://github.com/sepinf-inc/IPED) 4.3.1
- FTK Imager

## About

Digital forensics student, organizing what I learn in class and in my own testing. Notes written with Claude's help while using these tools for the first time.
