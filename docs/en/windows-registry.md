🌐 [Ler em português](../registro-windows.md)

# Windows Registry — forensic artifacts

## The concept of an artifact

A digital artifact is a trace that the system or a program leaves behind, letting you reconstruct what the user did. One artifact alone rarely proves everything — the strength of forensic work is in **correlating** several. Prefetch tells you *what* ran; UserAssist and `NTUSER.DAT` help tell you *who*.

## Hives — the Registry's building blocks

The Registry is Windows' configuration database. Each file in it is a *hive*.

| Hive | Scope | What it stores |
|---|---|---|
| **SAM** | Machine | Local accounts, SIDs, password hashes |
| **SYSTEM** | Machine | Hardware, drivers, USBSTOR (USB drives), ComputerName, TimeZoneInformation, MountedDevices, Services |
| **SOFTWARE** | Machine | Installed programs, Run, Uninstall, Windows version, App Paths |
| **SECURITY** | Machine | Policies and auditing |
| **NTUSER.DAT** | User | UserAssist, RecentDocs, RunMRU, TypedPaths, Run, MountPoints2 |

- Machine hives: `C:\Windows\System32\config`. `NTUSER.DAT`: `C:\Users\<username>\`.
- A question about a **specific person** → `NTUSER.DAT`. About the **machine** → SYSTEM/SOFTWARE.
- Programs run through the UI → `NTUSER.DAT` (UserAssist). USB drives connected → SYSTEM (USBSTOR); `MountPoints2` links the volume to the user.
- Tool: **Registry Explorer** (Eric Zimmerman), opens hives offline. Needs the .NET 9 Desktop Runtime: `winget install Microsoft.DotNet.DesktopRuntime.9`.

## Anti-forensics

- A regular user can edit their own `NTUSER.DAT`; SYSTEM requires administrator rights.
- Wiping the trace in one place usually isn't enough: the same fact tends to show up in more than one hive, and in Prefetch and the Event Log too.
- Deleted registry values are sometimes recoverable, depending on the tool.
- **Golden rule:** correlating artifacts defeats an attempt to tamper with just one.

## Prefetch

One `.pf` file per executed program, in `C:\Windows\Prefetch`. Records the executable's name, how many times it ran, the last run time, recent run times, and the files/folders it referenced.

- **Doesn't prove who ran it**, nor **what the program did**.
- Survives the program being uninstalled.
- The filename's suffix is a hash of the executable's path **and** its command line — that's why the same program can have several `.pf` files (parameters like `/prefetch:N` produce different files).
- Run count isn't the same as user-initiated opens: services and updaters generate `.pf` files too.
- The `EnablePrefetcher` value (`...\Memory Management\PrefetchParameters`) controls what gets generated (off / applications only / boot only / both) — the exact numbers vary across sources, **check the official Microsoft documentation before citing this in a report**.

### PECmd — syntax

```powershell
& "<path>\PECmd.exe" -d "<folder with the .pf files>"
```

- `&` runs the program by its full path, when it isn't on PATH.
- `-d <folder>` analyzes a whole folder; `-f <file>` a single `.pf`.
- `--csv <folder>` / `--json <folder>` export results; `--csvf <name>` sets the CSV's filename.
- Times come out in UTC — the report needs to state the timezone used.
- `Keywords: temp, tmp` only flags paths containing those words. It's a search filter, not a malware detector.
- "Created on" = when the `.pf` file was copied to the examiner's machine. "Last run" = the actual recorded execution.

## UserAssist

Lists, within each user's profile, the programs **that person** opened through the graphical interface (Explorer, desktop, Start menu). Stores how many times and when the last one was.

```
ROOT\Software\Microsoft\Windows\CurrentVersion\Explorer\UserAssist\{GUID}\Count
```

- Lives in **NTUSER.DAT** — so it ties the action to a specific user (Prefetch doesn't).
- Names are **ROT13**-encoded (each letter shifted 13 positions). Tools like Registry Explorer decode it automatically.
- Command-line-only execution usually doesn't show up here.

**Useful correlation:** Prefetch (what ran) + UserAssist (who opened it, how many times) + RunMRU (what was typed). Three sources, one story.

## RunMRU

The last commands typed into the Run box (`Win+R`). Stores the exact text.

```
ROOT\Software\Microsoft\Windows\CurrentVersion\Explorer\RunMRU
```

- *MRU* = Most Recently Used. Position 0 is the most recent.
- Windows writes the text with a trailing `\1` marker; analysis tools usually show it without that.
- The date ("Opened On") only exists for position 0, since it comes from the key's own last-write time.
- Something typed inside an already-open `cmd` window won't show up here or in UserAssist.

## RecentDocs

Files and folders **this user** opened, organized by extension (one subkey per file type, plus a `Folder` subkey).

```
ROOT\Software\Microsoft\Windows\CurrentVersion\Explorer\RecentDocs
```

- Proves the file was **opened**, not that it was **copied**. The name stays in the list even if the file is later deleted.
- Combined with USBSTOR (SYSTEM), it builds a USB-drive narrative: SYSTEM says when it connected, RecentDocs says what was opened in that window of time.
- A timestamp is only recorded for position 0 of each subkey.

## Tracking USB devices: USBSTOR, MountedDevices, MountPoints2

- **USBSTOR** (SYSTEM hive, `ROOT\ControlSet001\Enum\USBSTOR`): manufacturer, model, firmware, **serial number**, and the *First Installed*, *Last Connected* and *Last Removed* dates (UTC). Doesn't store capacity or copied files.
  - An empty *Last Removed* means the time wasn't recorded — not that the device stayed plugged in.
  - A serial with `&` in the second position means the device has no serial of its own; Windows generated one. It doesn't uniquely identify the physical device.
- USBSTOR alone **doesn't say which user** or **which drive letter**.
- **MountPoints2** (`NTUSER.DAT`): links a volume to a user session.
- **MountedDevices** (SYSTEM, `ROOT\MountedDevices`): links the volume's GUID to a serial number and a drive letter — this is the key that closes the loop between a device and a letter.
- Drive letters get **reassigned** over time — only trust a letter together with the device's serial number.

## Event Log

`.evtx` files in `winevt\Logs`. Tools: Event Viewer (`eventvwr.msc`) and EvtxECmd.

| Log | ID | Meaning |
|---|---|---|
| Security | 4624 | Successful logon |
| Security | 4625 | Failed logon |
| Security | 4634 / 4647 | Logoff |
| Security | 4648 | Logon using explicit credentials |
| Security | 4672 | Special privileges assigned to the logon (normal for admin accounts) |
| Security | 4800 / 4801 | Workstation locked / unlocked |
| System | 6005 / 6006 | Event log service started / stopped (power on/off) |
| System | 6008 | Unexpected shutdown |
| System | 1074 | Shutdown initiated by the user |
| Security | 1102 | Audit log cleared (records who cleared it) |
| Security | 4688 | Process created (only exists if process-creation auditing is enabled — off by default) |
| Security | 4797 | A blank password was queried for an account (routine, common at logon) |
| Security | 5379 | Credentials read from Credential Manager (routine, common at logon) |
| System | 104 | Log cleared |

- Logs have a default maximum size (Security tends to sit around 20 MB); once full, the oldest events may get overwritten (*rollover*). Check the first event's date before assuming an older period is still there.
- The file stores times in **UTC**; Event Viewer shows them in the analysis machine's configured timezone.
- **4672** isn't privilege escalation — it's "special privileges assigned to the new logon," normal for administrative accounts. For **4624**, what matters is the **Logon Type**: 2 = interactive (keyboard), 3 = network, 5 = service, 7 = unlock, 10 = remote (RDP), 11 = cached interactive.
- **4719** (system audit policy change) is different from **4907** (audit setting change on a specific object, like a file or folder) — don't confuse the two.
- A normal shutdown leaves 1074 + 6006. An abrupt shutdown (power loss) leaves 6008, and on the next boot a Kernel-Power 41.
- Clearing a log leaves a trace: 1102 (Security) and 104 (System). The tool used to clear it (Event Viewer or `wevtutil`) also leaves a trace — worth checking UserAssist and Prefetch for it.

## Other artifacts

- **TypedPaths** (`NTUSER.DAT`, `...\Explorer\TypedPaths`): paths **typed** into Explorer's address bar. Typing a path shows the person knew the exact location; by itself, it isn't an attempt to hide a trace.
- **Windows Search** (`Windows.edb`, ESE format, opened with ESEDatabaseView): a metadata catalog (name, path, size, dates, content snippets), separate from the filesystem — an index row can outlive the original file being deleted or overwritten. Carving recovers **content** from disk; the index shows the **record** that a file existed — two different things.
  - Most relevant tables: `MSysObjects` (schema only), `SystemIndex_PropertyStore` (one row per indexed item, with dates and properties), `SystemIndex_Gthr` (collected items), `SystemIndex_GthrPth` (folder hierarchy). The `SystemIndex_1_DATA_*` and `SystemIndex_1_OCC_*` tables are internal full-text-index parts — usually safe to ignore.
  - Values in raw viewers appear **little-endian**. Dates are usually **FILETIME** (100 ns ticks since 1601-01-01 UTC) — to convert by hand, reverse the byte order before interpreting the hex.
- **Recent Files**: `.lnk` shortcuts in `AppData\Roaming\Microsoft\Windows\Recent`. Same idea as the `NTUSER.DAT` `RecentDocs` key.
- **KAPE**: *Targets* (`.tkape`) define what to collect; *Modules* (`.mkape`) run tools and produce CSV/JSON. `gkape` is the GUI and needs administrator rights. KAPE collects — the examiner is the one who draws conclusions.

## Commands used

| Command | What it's for |
|---|---|
| `Get-FileHash -Algorithm SHA256 "<path>"` | Computes the SHA-256 hash |
| `Set-Alias 7z "C:\Program Files\7-Zip\7z.exe"` | Creates the `7z` shortcut for this PowerShell session |
| `7z l "<zip>"` | Lists the contents without extracting |
| `7z x "<zip>" -o"<destination>"` | Extracts (no space between `-o` and the path) |
| `Copy-Item "<source>" "<destination>" -Recurse` | Copies whole folders |
| `explorer "<path>"` | Opens the folder in Explorer |

## Common pitfalls

- **Prefetch** proves the executable ran, but not who ran it or what it did. Saying it "proves nothing" is an overstatement.
- **UserAssist** records programs opened through the **UI** (Explorer, Start menu, `Win+R`). Anything run *inside* an already-open terminal won't show up there.
- **RunMRU** is the **Run box** (`Win+R`), not terminal history. A command typed inside an already-open `cmd` lives elsewhere (PowerShell's own history file, Event Log with command-line auditing enabled).
- **RecentDocs** shows a file was **opened**, not **transferred**. A drive letter is a clue, not a conclusion — letters get reassigned; the reliable link between a letter and a device comes from `MountedDevices` and `MountPoints2`.
- Common tool terminology: "Run Counter" = times executed; "Focus Time" = time the window held focus.

## Review quiz

<details><summary>Why doesn't the hash change if I rename the file?</summary>The hash is computed only over the content. Name and date are left out.</details>

<details><summary>Which hive answers "which USB drives have been connected?" and which answers "what did THIS user execute?"</summary>USB drives: SYSTEM (USBSTOR). A specific user: NTUSER.DAT (UserAssist).</details>

<details><summary>Does Prefetch prove who ran a program? Why or why not?</summary>No. It shows which executable ran, how many times, and when, but not the user. Services generate <code>.pf</code> files too.</details>

<details><summary>Why can the same program have several .pf files with different suffixes?</summary>The suffix is a hash of the path and the command line. Different parameters at run time produce different files.</details>

<details><summary>What does a filter like "Keywords: temp, tmp" mean in a Prefetch tool?</summary>It's a warning that some referenced path contains those words — a search filter, not proof of malware.</details>

<details><summary>Which ID indicates a failed logon? And an unexpected shutdown?</summary>Failed logon: 4625 (Security). Unexpected shutdown: 6008 (System).</details>

<details><summary>The user erased their own trace in NTUSER.DAT. How can the action still be proven?</summary>By correlating other sources: USBSTOR in SYSTEM (requires admin to edit), the Event Log, deleted registry values that are sometimes recoverable, and other recent-file artifacts.</details>

<details><summary>Does a program run only from the command prompt show up in UserAssist?</summary>Generally not. UserAssist records launches through the graphical interface. Prefetch records the execution regardless of how it happened; RunMRU stores what was typed into Win+R.</details>
