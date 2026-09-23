🌐 [Ler em português](../sleuthkit.md)

# Sleuth Kit — command reference

Commands for [The Sleuth Kit](https://www.sleuthkit.org/) (TSK 4.12.1), tested on WSL (Ubuntu). Organized by the layer of the image each tool reads — from the raw container down to a single deleted file — plus the multi-step recipes that actually get used on a case.

Install: `sudo apt install sleuthkit` (package `sleuthkit`, no hyphen). The default build already reads `.E01` directly (linked with `libewf2`) — no conversion needed.

## The one rule that trips everyone up: the `-o` offset

1. A disk image holds a **partition table**. Filesystem tools can't see it on their own — they need to be told where the filesystem *starts*.
2. Run `mmls image.E01` first. Read the **Start** sector of the partition you want (e.g. `2048`).
3. Pass that value to **every** filesystem/metadata/data-unit tool: `fls -o 2048`, `fsstat -o 2048`, `icat -o 2048`...
4. The offset is in **sectors**. The default sector size is 512 bytes; change it with `-b`. A wrong `-o` gives the error "Cannot determine file system type."

## The six layers

| # | Layer | Tools |
|---|---|---|
| 1 | Image / container | `img_stat`, `img_cat`, `tsk_imageinfo` |
| 2 | Volume / partition | `mmls`, `mmstat`, `mmcat` |
| 3 | File system | `fsstat` |
| 4 | Metadata / inode | `istat`, `ils`, `icat`, `ifind` |
| 5 | Data unit / block | `blkcat`, `blkls`, `blkstat`, `blkcalc` |
| 6 | File name | `fls`, `ffind` |

## 1 — Image

```bash
img_stat image.E01               # format, size, sector size, segments (E01/split)
img_cat image.E01 > image.raw    # export as plain raw/dd
tsk_imageinfo image.E01          # summary of the image + volume system
```

## 2 — Volume

```bash
mmls image.E01                   # partition table — note the Start of each one
mmcat image.E01 2 > part2.dd     # extract partition slot 2 into its own file
mmstat image.E01                 # just the volume-system type (dos, gpt...)
```

Useful `mmls` flags: `-t dos|gpt|mac|bsd|sun` forces the type when autodetect fails; `-B` shows sizes in bytes; `-a`/`-A` show only allocated/only unallocated.

## 3 — File system

```bash
fsstat -o 2048 image.E01
```

Volume label, filesystem type and version, block/cluster size, first and last inode, FAT/MFT layout, and mount history. `-f ntfs|ext4|fat32...` forces the type; `-o N` is the start sector (required on a whole-disk image); `-b N` changes the sector size.

## 4 — Metadata

This layer can still see files whose names are gone — deleted entries, orphans — as long as the metadata structure survives.

```bash
istat -o 2048 image.E01 12345              # everything about inode 12345: MAC times, size, blocks
icat -o 2048 image.E01 12345 > recovered.bin   # file content by inode, even with no name
ils -e -o 2048 image.E01                   # list inodes; default is deleted/unallocated only
ifind -o 2048 -n "/Users/alex/notes.txt" image.E01  # path → inode
```

`icat`: `-r` attempts recovery even from an unallocated inode; `-s` includes slack space. `ils`: `-e` = every inode (allocated + not); `-m` = timeline format (for `mactime`).

## 5 — Data unit

The starting point for unallocated-space carving and slack-space analysis.

```bash
blkstat -o 2048 image.E01 5678                # is block 5678 allocated or free?
blkcat -o 2048 image.E01 5678 16 | xxd | less # dump 16 blocks starting at 5678
blkls -o 2048 image.E01 > unalloc.dd          # concatenate all unallocated blocks
blkcalc -o 2048 -u 900 image.E01              # offset in a carved stream → real block in the image
```

`blkls`: `-e` = every block; `-s` = slack only; `-A`/`-a` = unallocated only/allocated only.

## 6 — File name

```bash
fls -o 2048 -r -p image.E01          # recursive listing with full path
ffind -a -o 2048 image.E01 12345     # the name(s) pointing at inode 12345
```

`fls`: `-r`/`-p` recurse/full path; `-d` deleted only, `-u` undeleted only; `-l` long format (size, MAC times, UID/GID); `-m /mnt` timeline format; `-z UTC` timezone.

## Timeline

Two stages: TSK tools emit a **body file** (pipe-delimited MAC-time records); `mactime` sorts it into a chronological report.

```bash
tsk_gettimes image.E01 > bodyfile     # whole image, all partitions, no -o needed
mactime -b bodyfile -d -y -z America/Sao_Paulo 2024-01-01..2024-12-31 > timeline.csv
```

`-d` = CSV; `-y` = ISO-8601 dates; `-z` = timezone of the evidence; `-i day summary.csv` also produces a per-day/hour activity histogram.

## Recovery and export

```bash
tsk_recover -o 2048 image.E01 ./recovered   # export reconstructed deleted files
fcat -o 2048 "/etc/passwd" image.E01        # like icat, but addressed by path instead of inode
fiwalk -X inventory.xml image.E01           # XML inventory: names, inodes, hashes
```

`tsk_recover`: `-e` = everything (allocated + deleted); `-a` = allocated only.

## Search and classify

```bash
srch_strings -a -t d unalloc.dd > strings.txt     # ASCII strings with byte offset
sigfind -o 2048 -t jpeg image.E01                 # scan sectors for a magic signature
sorter -o 2048 -d ./sorter-out -h -s image.E01     # classify by real type, build an HTML index
usnjls -o 2048 image.E01 > usn.txt                # NTFS $UsnJrnl — change journal
hfind NSRLFile.txt d41d8cd98f00b204e9800998ecf8427e  # hash lookup against NSRL/custom set
```

## Mounting an E01 (separate package: `ewf-tools`)

TSK reads `.E01` directly — no mounting needed for `mmls`/`fls`/`icat`. Mount only when a file manager or a non-forensic tool needs to see the data. `ewfmount` isn't part of Sleuth Kit — it ships in `ewf-tools`.

```bash
sudo apt install ewf-tools   # ewfmount, ewfinfo, ewfverify, ewfexport, ewfacquire

ewfverify case.E01   # integrity: recomputes the acquisition hash
ewfinfo case.E01      # acquisition metadata: examiner, date, notes, media size

mkdir -p ~/mnt/ewf ~/mnt/evid
ewfmount case.E01 ~/mnt/ewf              # -> ~/mnt/ewf/ewf1 : read-only raw view
mmls ~/mnt/ewf/ewf1                      # read the partition's Start (e.g. 2048)
sudo mount -o ro,loop,offset=$((2048*512)),show_sys_files,streams_interface=windows \
     ~/mnt/ewf/ewf1 ~/mnt/evid           # NTFS; for ext4 just ro,loop,offset=...
ls ~/mnt/evid

# unmount, in reverse order:
sudo umount ~/mnt/evid
fusermount -u ~/mnt/ewf
```

`ro` always — never mount evidence writable. `offset` is the same number as `-o`, but in **bytes** (Start sector × 512).

## Recipes

### R1 — First 90 seconds with an unknown image

```bash
sha256sum image.E01 | tee image.E01.sha256
img_stat image.E01
mmls image.E01                       # note the Start of each partition
fsstat -o 2048 image.E01
fls -o 2048 -r -p image.E01 > files.txt
```

Produces `files.txt` — every path + inode, deleted entries marked with `*`.

### R2 — Extract a file found in the listing

Say `files.txt` shows `r/r 4128-128-1: Users/alex/Desktop/plan.docx`:

```bash
istat -o 2048 image.E01 4128            # confirm dates and size
icat -o 2048 image.E01 4128 > plan.docx
sha256sum plan.docx
```

### R3 — Recover deleted files

```bash
fls -o 2048 -r -d image.E01             # preview what's deleted
tsk_recover -o 2048 image.E01 ./deleted
find ./deleted -type f | wc -l
```

On ext4/APFS expect many zero-length files (data blocks wiped on delete); NTFS/FAT recover much better.

### R4 — Full activity timeline

```bash
tsk_gettimes image.E01 > bodyfile
mactime -b bodyfile -d -y -z America/Sao_Paulo > timeline.csv
mactime -b bodyfile -d -y -z America/Sao_Paulo -i day activity-by-day.csv > /dev/null
```

### R5 — Carve and locate data in unallocated space

```bash
blkls -o 2048 image.E01 > unalloc.dd
srch_strings -a -t d unalloc.dd | grep -i "confidential"
blkcalc -o 2048 -u <offset/blocksize> image.E01     # -> real block
ifind -o 2048 -d <real block> image.E01             # -> owning inode, if any
```

### R6 — Triage a large image by file type

```bash
sorter -o 2048 -d ./sorter-out -h -s image.E01
xdg-open ./sorter-out/index.html
```

## Gotchas

- **Your image is slow to read from WSL if it's on the Windows side.** If it's under `/mnt/c/...`, copy it into the Linux filesystem first (`cp /mnt/c/.../image.E01 ~/cases/`) and work from there.
- **Never work on the original.** Copy it, set it read-only (`chmod 444 image.E01`), and record `sha256sum` before and after every session.
- **"Cannot determine file system type"** almost always means a wrong or missing `-o`. Re-run `mmls`. A single-partition image with no table: use `-o 0` or drop `-o`.
- **`-o` isn't universal.** Filesystem-layer tools need it; whole-image tools reject it. `tsk_gettimes: invalid option -- 'o'` means you passed `-o` to a tool that walks the partitions itself.
- **Timezone is evidence.** `mactime -z` controls interpretation; the wrong zone shifts every event. Note the machine's configured zone and state it in your report.
- **Deleted ≠ recoverable.** ext4 and APFS zero out an inode's block pointers on delete, so `icat` often returns nothing even when `fls -d` still shows the name. NTFS and FAT hold on much longer.

---

Man pages: `man mmls`, `man fls`, `man mactime`. Every tool takes `-V` (version) and prints usage with no arguments.
