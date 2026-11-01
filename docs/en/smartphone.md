🌐 [Ler em português](../smartphone.md)

# Smartphone forensics (Android and iOS)

A phone is a pocket computer: it concentrates conversations, location, photos and browsing. Every app leaves a trace — forensics is about reconstructing that trace without assuming the motive behind it.

Scripts that automate the queries in this guide (SQLite, EXIF, dates, contacts) live in [`ferramentas/`](../../ferramentas/), documented in [`docs/en/tools.md`](tools.md).

## The four levels of extraction

The deeper you go, the more data — and the harder it gets. Part of the information simply does not exist at the shallower levels.

| Level | What it reaches | Needs root/jailbreak? |
|---|---|---|
| **1. Logical** | Data the system itself exposes: contacts, SMS, apps | No |
| **2. File system** | Folder/file structure, including app databases | Depends on the method |
| **3. Physical** | Full memory image: recovers **deleted** data and fragments | May need root, jailbreak or chip-off/JTAG |
| **4. Cloud** | Synced data (Google, Apple) | Doesn't touch the device |

- Cloud extraction helps when the device is locked or data was deleted locally — usually needs a court order.
- Not every tool does every level: knowing that limitation is part of the report.

## BFU vs AFU: the device's state at seizure

| | BFU (Before First Unlock) | AFU (After First Unlock) |
|---|---|---|
| **Means** | Powered on, but not yet unlocked since boot | Already unlocked at least once since it powered on |
| **Encryption keys** | Protected | Several stay in memory, even if the screen locks again |
| **Accessible** | Basic info, a few metadata, limited parts of the file system | Messages, photos, contacts, SQLite databases, tokens and sessions |
| **Not accessible** | Decrypted conversations, full app databases | — |

At seizure: **do not power off**, keep it charged, and switch on **airplane mode** (isolate from the network without losing the AFU state).

## SQLite: where apps keep everything

A lightweight, single-file database with no server — apps and the OS itself use it. Files end in `.db` or `.sqlite`.

- Lets you recover messages (including old ones), see contacts and relationships, and **correlate events by date/time**.
- Deleted data can survive in pages that weren't overwritten, and in the **WAL**.
- `database.db-wal` = log of recent transactions. `database.db-shm` = shared memory. The three files **travel together**: opening just the `.db` can show an empty or incomplete table when the most recent data is still sitting in the WAL.

**DB Browser for SQLite** (read-only use): open with *Open Database Read Only*. The **Browse Data** tab shows rows; **Execute SQL** runs queries.

```powershell
winget install DBBrowserForSQLite.DBBrowserForSQLite
```

Common queries:

```sql
-- SMS or call date (Unix milliseconds) in UTC-3
SELECT datetime(date/1000, 'unixepoch', '-3 hours') FROM sms;

-- Chrome visit (microseconds since 1601) in UTC-3
SELECT datetime(visit_time/1000000 - 11644473600, 'unixepoch', '-3 hours') FROM visits;

-- contacts with a phone number (contacts2.db)
SELECT r._id, r.display_name, d.data1 AS phone
FROM raw_contacts r
JOIN data d ON d.raw_contact_id = r._id
JOIN mimetypes m ON m._id = d.mimetype_id
WHERE m.mimetype LIKE '%phone_v2';
```

`/1000` converts milliseconds to seconds; `- 11644473600` shifts the epoch from 1601 to 1970; `'unixepoch'` tells SQLite the number is Unix; `'-3 hours'` adjusts the time zone. `JOIN` links tables by a key — here, each phone number (`data`) to its contact (`raw_contacts`), with `mimetypes` saying what kind of data that row is.

## Android: where to look

Linux kernel, layered as Linux Kernel, HAL, ART runtime, Java framework, applications. Before Android 4.0 the device mounted as a thumb drive (**MSC**); afterwards it switched to **MTP**, which mounts at a logical level and blocks direct file-system access.

| Folder | What it is |
|---|---|
| `/system` | The OS itself |
| `/data` | User data (the most important one for forensics) |
| `/data/data/<app>` | Each app's data (`databases/`, `shared_prefs/`) |
| `/data/system` | System configuration (`packages.xml`, accounts) |
| `/data/misc` | Auxiliary data: `wifi/`, `bluetooth/`, `vpn/`, `keystore/` |
| `/cache`, `/sdcard` | Temporary; external storage (photos in `DCIM`) |

| Data | File | Notes |
|---|---|---|
| Contacts | `/data/data/com.android.providers.contacts/databases/contacts2.db` | On **Samsung** it lives under `com.samsung.android.providers.contacts/databases`. Tables: `raw_contacts`, `data`, `mimetypes`, `accounts` |
| Calls | `contacts2.db` (`calls` table) | On Samsung usually split out: `calllog.db`, `calls` table |
| SMS | `/data/data/com.android.providers.telephony/databases/mmssms.db` | `sms` table: `type` 1 received, 2 sent |
| Wi-Fi | `/data/misc/wifi/WifiConfigStore.xml` (newer) · `wpa_supplicant.conf` (older) | Android 11+: `/data/misc/apexdata/com.android.wifi/` |
| Accounts | `/data/system/accounts.db` · `accounts_ce.db` (newer) | Google, Samsung, social networks, messaging apps |
| Installed apps | `/data/system/packages.xml` | Dates in hex; `analisa_packages.py` script |
| Browsing | `/data/data/com.android.chrome/app_chrome/Default/` | `History` file (SQLite) |
| Location | `com.google.android.gms` · `com.android.location` | Google Location History |
| WhatsApp | `/data/data/com.whatsapp/databases/msgstore.db` · `wa.db` | `msgstore.db`: messages (`messages`, `chat`); `wa.db`: contacts |

**Developer mode:** Settings → About phone → tap "Build number" 7 times → enter PIN/password. Under "Developer options": **USB debugging** (needed for ADB) and **OEM unlocking** (unlocks the bootloader — can wipe data and weaken security).

**Tools:** ADB to extract (`adb pull`), DB Browser for SQLite to read databases, Autopsy (Android Analyzer / aLEAPP) for structure and deleted files.

**Hashing an APK** (lives at `/data/app/<package>-<hash>/base.apk`):

```powershell
Get-FileHash "C:\evidence\data\app\<app-folder>\base.apk" -Algorithm SHA1
```

## iOS: the other side

Unix-based (Darwin). Layers: Core OS, Core Services, Media, Cocoa Touch. Closed system, strong encryption, tight app sandboxing. File system is **APFS**. iPhones don't support MSC: collection uses dedicated logical extraction or backups (iTunes/iCloud).

- `/System` is the OS. `/private/var` is the Android `/data` equivalent.
- Each app has its own sandboxed folder, identified by a **UUID**: `/private/var/mobile/Containers/Data/Application/<UUID>`.

| Data | File |
|---|---|
| Contacts | `/private/var/mobile/Library/AddressBook/AddressBook.sqlitedb` |
| Calls | `/private/var/mobile/Library/CallHistoryDB/CallHistory.storedata` |
| SMS | `/private/var/mobile/Library/SMS/sms.db` |
| Wi-Fi | `/private/var/preferences/SystemConfiguration/com.apple.wifi.plist` |
| Accounts | `/private/var/mobile/Library/Accounts/` |
| Places | `/private/var/mobile/Library/Caches/com.apple.routined/Cache.sqlite` |
| WhatsApp | App container (`ChatStorage.sqlite`, tables `ZWAMESSAGE`, `ZWACHATSESSION`) |
| Photos | `DCIM/` + EXIF metadata |

On iOS, dates are usually **Cocoa** (seconds or nanoseconds since 2001) — see the dates section.

## Dates: each artifact's own clock

Half of all forensic mistakes come from reading a date in the wrong format. The trick: **count the digits**.

| Digits | Format | Where it appears | Example |
|---|---|---|---|
| 9 | Cocoa: seconds since 2001 | iOS | `700000000` ≈ 2023-03-08 20:26:40 UTC |
| 10 | Unix: seconds since 1970 | Linux, SQLite | — |
| 13 | Unix: **milliseconds** | Android (SMS, calls) | `1700000000000` = 2023-11-14 19:13:20 (UTC-3) |
| 16 | Unix: microseconds | Firefox | — |
| 17 | WebKit: microseconds since **1601** | Chrome, Edge | `13370000000000000` = 2024-09-05 05:53:20 (UTC-3) |
| 18 | FILETIME: 100 ns intervals since 1601 | **Windows** | `133700000000000000` = 2024-09-05 08:53:20 UTC |
| 18 | Cocoa nanoseconds since 2001 | recent iOS/APFS | — |
| hex | Unix milliseconds in hexadecimal | `packages.xml` (`it`, `ut`, `ft`) | use `convert_date.py` or `analisa_packages.py` |

The two 18-digit formats (Windows and iOS) get confused with each other; context decides. `convert_date.py` tells them apart by value range and shows the other possible reading.

- **SMS:** `date` is when the **device** received it; `date_sent` is when the **carrier** sent it. A few seconds apart is normal.
- Always state the **time zone** in the report. Databases are usually in UTC; the device clock may be set to a different zone.

**A photo's clocks:**

| Clock | Who writes it | What it measures |
|---|---|---|
| File name (`IMG_YYYYMMDD_HHMMSS`) | Camera app | Local date at the moment of saving |
| `DateTimeOriginal` | Camera | Moment of capture (local time, no zone) |
| `DateTimeDigitized` | Camera | When the image was digitized; on a phone usually equal to Original. It's a **timestamp**, not a duration |
| `DateTime` | Whoever last wrote the file | EXIF modification date |
| GPS (date and time) | GPS receiver | Always UTC. May exist **without coordinates** |
| `OffsetTime` | Camera | Local time zone offset (e.g. `-03:00`) |
| Modified / Created on disk | File system | On an evidence drive, "Created" is usually the **extraction/copy** date, not the photo's |

## Chrome: the history in tables

On a phone, Chrome lives under `com.android.chrome/app_chrome/Default/`. On a computer, in the profile folder. Same format either way (Chromium: Chrome, Edge, Brave).

| File / table | What it answers |
|---|---|
| `History` → `urls` | Each URL, title, `visit_count`, `typed_count`, `last_visit_time` |
| `History` → `visits` | Each visit: `visit_time`, `from_visit` (where it came from), `transition` |
| `transition` | Type in the low byte (link, typed, form...). High bits: client (`0x40000000`) or server (`0x80000000`) redirect, chain start/end |
| `keyword_search_terms` | Searched terms |
| `downloads` + `downloads_url_chains` | Name, folder, state, timestamps, and the **URL used to download** |
| `Favicons` | Per-page icons. Can survive after history is cleared |
| `Sessions/Session_*` | Open tabs at closing time (SNSS format). The number in the name is the file's **creation** time, not when it closed |
| `Local Storage`, `IndexedDB` | Data persisted per domain (a folder named after the site) |

- A "pass-through" page (such as a single sign-on) shows up as a redirect: it's the middle visit of the chain.
- A **favicon**'s source domain (e.g. a CDN) missing from the history doesn't mean the person visited that CDN, nor that anything was deleted. It's just a fact to record.

## ADB: talking to the live device

Requires USB debugging on and the device authorized. Each command runs on the **computer**; `>` redirects output to a file.

```powershell
adb devices
adb shell content query --uri content://com.android.contacts/data > contacts_dump.txt
adb shell "content query --uri content://sms/ --projection address:date:body" > sms_export.txt
adb shell content query --uri content://call_log/calls > calls.txt
adb shell dumpsys location > location_log.txt
adb shell dumpsys wifi > wifi.txt
adb shell dumpsys account
adb pull /sdcard/DCIM ./photos
```

- `adb devices` lists connected, authorized devices — the first check to run.
- `adb shell` runs a command **inside** the device. `content query` queries a *content provider* (Android's official door to read contacts, SMS, calls); `--uri` picks the provider, `--projection` picks the columns.
- `dumpsys` dumps a system service's state (location, Wi-Fi, accounts).
- `adb pull source destination` copies from the device to the computer — whole-folder extraction, logical level.
- This is **logical** extraction: it only sees what the system hands over. Deleted data and apps' internal databases need the deeper levels.

## How to reason: facts, not verdicts

- **Describe the fact** and say "consistent with" instead of "proves". Interpretation belongs to the case's context.
- **Absence is not proof.** An app, an SMS, or a page that doesn't show up may have been deleted, may live in another source, or may never have existed. Say which of those is possible.
- **Correlate** independent artifacts (SMS + Chrome + an installed app, for example). One source alone can mislead; two agreeing support each other.
- **Leave an inconsistency open** until another source resolves it. Don't invent an explanation.
- **Don't mix sources** (different extractions, different devices) or timestamps from different clocks.
- **Hash before touching anything**, work on a copy, keep `.db` + `-wal` + `-shm` together.
- **Spot-check** 2 or 3 rows of a script's output by hand in DB Browser. A script helps, but the examiner is accountable for the number.

> Golden rule: correlating artifacts defeats tampering with just one of them.

## Common pitfalls

- **"Proves" is a strong word.** Two artifacts agreeing are "consistent"; the report shouldn't claim more than the data shows.
- **Airplane mode.** At seizure, the right move is to *turn on* airplane mode (isolate from the network), not power the device off — powering off loses the AFU state.
- **`DateTimeDigitized`** is a timestamp, not a duration.
- **File date vs. photo date.** "Created" on the evidence drive is usually the extraction date. What speaks to the photo itself is the EXIF.
- **Contact counts** change with the query (`raw_contacts` vs. grouped contacts, deleted ones included or not). Check in DB Browser before writing down a number.
- **First installed app** only counts among **user** apps (`/data/app`). The "first" among system apps is just the firmware.
- **Chrome's `Session_` files:** the number in the name is the file's creation time, not when the session closed.
- **An "empty" database.** A `.db` opened without its `-wal` next to it can look like it has no recent data — check that all three files were copied together.

## Review quiz

<details><summary>What are the four extraction levels, and which one never touches the device?</summary>Logical, file system, physical, and cloud. Cloud never touches the device (and logical doesn't need root).</details>

<details><summary>What is BFU, and why avoid powering off a seized phone?</summary>BFU: powered on but not unlocked since boot, keys protected, almost nothing accessible. Powering off returns it to BFU; keeping it on and charged preserves AFU, where databases, messages and tokens are reachable.</details>

<details><summary>Why copy the .db together with its -wal and -shm?</summary>The WAL holds recent transactions not yet folded into the main file. Without it, the database can look empty or out of date.</details>

<details><summary>In mmssms.db, how do date and date_sent differ, and how do you tell a message was received?</summary><code>date</code> is when the device received it; <code>date_sent</code> is when the carrier sent it. <code>type</code> 1 = received, 2 = sent.</details>

<details><summary>What format is a 13-digit Unix number? And a 17-digit one?</summary>13 digits: Unix milliseconds (Android). 17 digits: WebKit/Chrome, microseconds since 1601.</details>

<details><summary>Two formats share 18 digits. Which ones, and how do you tell them apart?</summary>Windows FILETIME (100 ns since 1601) and Cocoa nanoseconds (iOS, since 2001). Context (the file's origin) decides; <code>convert_date.py</code> separates them by value range and shows the other reading.</details>

<details><summary>Why can the same contact show up as more than one raw_contacts row?</summary>Each account (phone, Google, a messaging app...) creates its own <code>raw_contact</code>. <code>contact_id</code> groups the ones that are the same person. Counting without grouping double-counts contacts and calls.</details>

<details><summary>How do you find the first and last app installed on Android?</summary>In <code>packages.xml</code>, the <code>it</code> field (hex, Unix ms), counting only user apps (<code>/data/app</code>) — system apps come from the firmware and mostly share the same date.</details>

<details><summary>Does a photo have GPS coordinates just because its EXIF has a GPS block?</summary>Not necessarily. The block may hold only date/time, with no latitude/longitude. You need to confirm coordinates are actually present.</details>

<details><summary>Is a photo's "Created" date on the evidence drive the date it was taken?</summary>Not necessarily — it's the file-system date on the drive holding the evidence (often the extraction/copy date). The actual capture time lives in the EXIF (<code>DateTimeOriginal</code>).</details>

<details><summary>App X doesn't appear in packages.xml. Does that prove it was never installed?</summary>No. Absence isn't proof: it may have been uninstalled, may live in another source, or the file may be partial or a different format (Android 12+ uses binary ABX).</details>

<details><summary>What does the number in a Chrome Session_ file name indicate?</summary>The session file's creation time (WebKit, UTC), not when it closed. To estimate closing time, use the file's original modification date.</details>

<details><summary>Where do SMS and contacts live on iOS, and what date format do they usually use?</summary><code>/private/var/mobile/Library/SMS/sms.db</code> and <code>AddressBook/AddressBook.sqlitedb</code>. Dates are usually Cocoa (seconds or nanoseconds since 2001).</details>
