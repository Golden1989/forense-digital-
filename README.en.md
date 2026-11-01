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
| [`docs/en/smartphone.md`](docs/en/smartphone.md) | Android and iOS forensics: extraction levels, BFU/AFU, SQLite (WAL/SHM), each system's artifacts, date formats, Chrome, ADB, forensic reasoning, with a review quiz |
| [`docs/en/tools.md`](docs/en/tools.md) | Python scripts in `ferramentas/`: how to run them, options explained, which script answers which question (timeline, installed apps, Chrome session, favicons, dates) |

## Scripts

[`ferramentas/`](ferramentas/) folder: Python scripts that only read the evidence (never write anything into it) and automate common forensic questions — installed apps, a unified timeline, Chrome session recovery, downloads, a browsing summary, favicons without matching history, a map of an unknown SQLite database, contacts/calls/SMS, photo EXIF, and a date converter. Step-by-step, options for each script, and which one to use for which question: [`docs/en/tools.md`](docs/en/tools.md).

## Tools used

- [The Sleuth Kit](https://www.sleuthkit.org/) 4.12.1, via WSL (Ubuntu)
- [IPED](https://github.com/sepinf-inc/IPED) 4.3.1
- FTK Imager

## About

Digital forensics student, organizing what I learn in class and in my own testing. Notes written with Claude's help while using these tools for the first time.
