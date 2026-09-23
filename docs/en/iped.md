🌐 [Ler em português](../iped.md)

# IPED — usage guide

[IPED](https://github.com/sepinf-inc/IPED) (Indexador e Processador de Evidências Digitais — Digital Evidence Indexer and Processor) 4.3.1, installed from the official GitHub release. Two-program flow: `iped.exe` processes the image and generates a case folder; `IPED-SearchApp.exe`, generated inside that folder, is where the analysis happens.

## The image before IPED

A forensic image is a bit-by-bit copy of the device — sector by sector, including free space, deleted files, and areas the operating system doesn't show.

- **Write blocker:** lets you read the original disk but blocks any write to it.
- **Hash at acquisition**, verification and chain of custody: see [`hashes.md`](hashes.md). IPED calculates the hash of **each file inside the image** — it doesn't verify the hash of the whole image.

### Formats IPED opens (the `-d` parameter)

| Format | Extension | What it is |
|---|---|---|
| RAW / dd | `.dd` `.001` `.img` | Raw copy, no compression or metadata |
| EnCase / EWF | `.E01` `.Ex01` | Most common forensic format: compresses, stores hash, case, examiner and date |
| AccessData | `.AD1` | Logical image — only the chosen files, not the whole disk |
| Phone (Cellebrite) | `.UFDR` | Mobile device extraction |
| Virtual machines | `.VMDK` `.VHD` `.VHDX` | VM disks |
| Optical | `.ISO` | CD/DVD image |
| Live | physical drive / folder | A connected disk, or a loose folder of files |

`.iped` is IPED's own format for reprocessing marked items. `AFF` only works on Linux.

## Processing — `iped.exe`

```powershell
PS C:\IPED\iped-4.3.1> .\iped.exe -d "D:\case\hd.E01" -o "C:\cases\case01" -tz GMT-3
# -d = input evidence   -o = output folder   -tz = filesystem timezone
```

Under the hood: mounts the partitions with the Sleuth Kit, extracts active and deleted files, computes hashes, runs *parsers* (email, browser, registry, WhatsApp...), indexes all text into a Lucene index, categorizes by type, and carves unallocated space.

### Parameters that matter

| Parameter | For |
|---|---|
| `-d` | **Required.** Input image, folder or drive. Can repeat for several |
| `-o` | **Required.** Folder where the case will be created |
| `-dname` | Display name/alias for that evidence |
| `-tz` | Timezone of the disk. FAT/exFAT store local time — without this, dates come out wrong |
| `-profile` | Processing profile (table below) |
| `-p` | Password for encrypted images or containers |
| `--append` | Adds another piece of evidence to an existing case |
| `--continue` | Resumes a processing run that stalled or was aborted — **not** for reopening an already-finished case |
| `--nogui` | No windows — processes in text mode (server, script) |
| `--portable` | Relative paths, to carry the case on an external drive |

To just reopen an already-processed case: don't run `iped.exe` again — open `IPED-SearchApp.exe` from inside the case folder.

### Profiles (`-profile`)

| Profile | When to use |
|---|---|
| `forensic` | Full exam: extracts everything, hashes, OCR, container expansion. Most thorough, slowest |
| `fastmode` | Faster: skips heavy parts. Good for a first pass |
| `triage` | Just the essentials to quickly decide whether that device matters |
| `blind` | Indexes without generating previews — used in blind/server workflows |
| `pedo` | Tuned for child-abuse-material cases (specific categories and lists) |

## Analysis — IPED-SearchApp

The screen has four regions: **search bar** (top, Lucene syntax), **left panel** (Evidence, Categories, Metadata, Bookmarks tabs), **center panel** (table/gallery/map/timeline), **viewer** (selected item + Metadata tab with all extracted properties).

### Columns worth adding

Right-click the table header → choose columns:

| Column | What it tells you |
|---|---|
| Size | File size in bytes |
| Path | The file's address inside the image, e.g. `/image.E01/vol_vol2/folder/file` — the partition shows up by the name Sleuth Kit gave it (`vol_volN`), not by the drive letter |
| MD5 / SHA-1 / SHA-256 | Each file's hash |
| Deleted | `true` = deleted, recovered from the filesystem's own record (name and dates preserved) |
| Carved | `true` = recovered by signature, no metadata, no original name/date |
| Offset / Sector | The file's physical position inside the image |
| Dates | Creation, modification, access, record change. Discrepancies between them flag tampering |
| Type / MIME | Real type from content. If it clashes with the extension, IPED flags a signature mismatch |
| Category | Automatic classification |
| Hash hits | Matched a loaded known-hash list (KFF) |

### Search

Lucene syntax: term, `"exact phrase"`, wildcard `note*`, range, `field:value`, regex.

```
name:*.jpg
size:[1000000 TO *]        # >= 1 MB
deleted:true
category:"documents" AND password
```

The exact field names appear at the top of each column and in the Metadata tab.

## Bookmarks

A bookmark is a named label you attach to relevant items while analyzing.

- **Selecting items:** the checkbox column marks items one by one; `Space` toggles the box on the focused item; `Shift`/`Ctrl` + click for several at once.
- **Create/apply:** right-click the items → Bookmarks menu → new bookmark (you name it) or add to an existing one. The same item can be in several bookmarks.
- **Bookmarks panel** (left tab): lists all of them with an item count; clicking one filters the table to it.
- **Comments** on the item and on the bookmark carry through to the report.
- **Stored in** `Bookmarks-<case>.json` in the case folder, with automatic backup in `iped/bkp` every hour.
- **The report comes from bookmarks:** when generating a report, IPED asks which bookmarks go in.

## Exporting

| Destination | What comes out | For |
|---|---|---|
| Folder on disk | Copies of the original files | Delivering the files themselves, opening in another tool |
| Properties CSV | The table — visible columns, one row per item | Spreadsheet, report attachment. `Lista de Arquivos.csv` (File List) is already exported automatically at the case root |
| HTML report (`htmlreport/`) | Self-contained package browsable offline, generated from the bookmarks | Final delivery, no need for IPED installed |
| `.iped` sub-case | Only the chosen items, reprocessed into a new case | Isolating the relevant material |
| KML / Google Earth | GPS points of georeferenced items | Seeing movement on a real map |
| Clipboard | Cell/row content | Quick paste into an email/note |

Automatic export during processing: `enableAutomaticExportFiles = true` in `IPEDConfig.txt` + categories uncommented in `conf/CategoriesToExport.txt`. Only the exported items enter the case, which becomes independent of the original image.

## Anatomy of a disk

Largest to smallest:

```
PHYSICAL DISK
└── Partition table
    └── Partition / Volume
        └── File system (MFT / FAT / inodes)
            └── Data area, divided into clusters
                ├── File A — allocated clusters
                ├── slack space (leftover in a file's last cluster)
                ├── UNALLOCATED space — where a deleted file's content lives until overwritten
                └── File B — allocated clusters
```

- 1 sector = 512 B (or 4 KiB). 1 cluster = a group of sectors — the smallest unit the OS allocates.
- Deleting a file just marks its clusters as free in the table. The content stays there until another file takes the space.
- **Slack space:** a file doesn't fill its last cluster completely; the leftover can hold remains of previous data.

## Deleted files and carving

Deleting doesn't zero the content — it just marks the record (MFT/directory) and the clusters as free.

| Situation | How it's recovered | Column |
|---|---|---|
| Record still exists, clusters not reused | Reads the MFT/directory and rebuilds it with original name, path and dates | `Deleted = true` |
| Record is gone, but the content is in unallocated space or slack | **Carving:** scans the bytes for known signatures (header/footer) and extracts the block | `Carved = true` |

- A carved file has no original name or date.
- Fragmentation hurts carving.
- **Signature mismatch:** the extension doesn't match the real content — a classic sign of a hidden file.

## Configuration — `IPEDConfig.txt`

File at the root of the install, the on/off panel for processing. **A change only applies to the next processing run** — it doesn't touch an already-finished case.

| Line | What it turns on | Cost |
|---|---|---|
| `enableCarving` | Recovers files by signature in areas with no metadata | Slower processing |
| `enableOCR` | Reads text inside images and scanned PDFs, feeds it into the index | Much slower. Language in `conf/OCRConfig.txt` |
| `enableHash` | MD5/SHA-1/SHA-256 for each file (on by default) | Low |
| `enableRegexSearch` | Email, URL, IP, tax-ID, card-number hits in the Regex group (on by default) | Low |
| `expandContainers` | Opens zip, mailboxes, Office documents (on by default) | Medium |

Full carving (unallocated space + slack) needs two more lines, in `conf/FileSystemConfig.txt`:

```
addUnallocated = true
addFileSlacks  = true
```

Reprocessing with the new config requires an empty or new `-o` folder — you can't reuse the folder of an already-processed case. Without `-profile`, it uses the root `IPEDConfig.txt`; with `-profile <name>`, it layers `profiles/<name>/IPEDConfig.txt` on top, which may override your edit.

## Treasure map — "I want X → where's Y"

| You want... | Where it is in IPED |
|---|---|
| A file's hash | The item's Metadata tab, or the MD5/SHA-256 columns |
| Size and dates | Size and date columns |
| Deleted files | Deleted column/filter, `deleted:true` |
| Signature-recovered files | Carved column/filter, `carved:true` |
| Position on disk | Offset/Sector columns |
| Photos and videos | Images/Videos category + Gallery view |
| Location (GPS) | EXIF metadata + Map view |
| Web browsing | Internet History category |
| Programs that ran | Prefetch, Amcache, SRUM |
| USB devices | Windows Registry |
| Emails | Emails category |
| Messenger conversations | WhatsApp, Telegram parsers |
| Specific text | Search bar |
| Patterns (tax ID, card number, email) | Regex search |
| Known/illicit files | Hash matching (KFF) |
| Password-protected files | Encryption flag on the item's properties |

## Examination checklist

- **Accounts and timezone:** local users, OS install, timezone, last shutdown.
- **Browser:** history, downloads, searches, cache, cookies.
- **Execution:** Prefetch, Amcache, SRUM.
- **Recent use:** recent files, LNK, Jump Lists, shellbags.
- **USB:** removable-device history.
- **Communication:** emails, messaging apps.
- **Media:** photos/videos, EXIF, GPS.
- **Keywords:** case terms, regex.
- **Deleted items:** Deleted + Carved, unallocated space and slack.
- **Encryption:** protected files and volumes.
- **Hash:** comparison against known-hash lists (KFF/NSRL).
- **Timeline:** events ordered by date.

## Command cheat sheet

```powershell
# quick test: process any folder
.\iped.exe -d "C:\some\folder" -o "C:\cases\test"

# E01 image, with timezone and alias
.\iped.exe -d "D:\ev\hd.E01" -dname "HD-01" -o "C:\cases\case01" -tz GMT-3

# add another piece of evidence to the same case
.\iped.exe -d "E:\ev\usb.E01" -o "C:\cases\case01" --append

# resume interrupted processing / see all options
.\iped.exe -d "D:\ev\hd.E01" -o "C:\cases\case01" --continue
.\iped.exe --help
```

What's left in the case folder: `IPED-SearchApp.exe` (opens the analysis), `iped/` (internal index, don't touch), `IPED-*.log` (processing log), `Bookmarks-*.json` (bookmarks), `htmlreport/` (after generating the report).

Large cases write a lot to temp storage — in `LocalConfig.txt`, point `indexTemp` to an SSD with room to spare and no antivirus scanning it.
