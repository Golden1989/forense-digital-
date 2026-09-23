🌐 [Ler em português](../hashes.md)

# Hashing a forensic image

## Two different things people call "the image hash"

For an `.E01` image (EnCase/EWF), there are **two possible hashes**, and they will **never match each other** — that's expected, not a bug:

| What you hash | What it proves | How to calculate |
|---|---|---|
| **Acquired content** (the disk's data, without the container) | "the data I'm analyzing is the same as the original disk" | `ewfverify` (below) |
| **The `.E01` file** itself (the container, with compression and metadata) | "this file hasn't changed since I received it" | `Get-FileHash` / `sha256sum` on the `.E01` |

The E01 format already stores, from acquisition time, the **MD5** and **SHA-1** hash of the content (not SHA-256 — it's an older format). To see that value:

```bash
# WSL — needs the ewf-tools package (sudo apt install ewf-tools)
ewfinfo image.E01
```

This shows the acquisition date, the tool used, and the stored hashes. To **recompute** the content hash and check whether it still matches (integrity), or to get a SHA-256 of the content (which the format doesn't store by default):

```bash
ewfverify -d sha256 image.E01
```

It rereads the whole image, compares it against the hash recorded at acquisition, and prints the extra SHA-256 at the end.

## Hashing the `.E01` file (the simplest option, with a caveat)

If the goal is just "prove this specific file wasn't altered," hashing the file itself is enough. Two ways, same result:

### PowerShell (Windows)

```powershell
Get-FileHash .\image.E01 -Algorithm SHA256 | Tee-Object -FilePath image.E01.sha256
```

### WSL (Ubuntu / Linux)

```bash
sha256sum image.E01 | tee image.E01.sha256
```

`Tee-Object` and `tee` do the same job: they **print the result to the screen and write it to a file** at the same time.

The value is identical in both terminals — only the appearance differs: PowerShell shows the hash in **uppercase** in a table; `sha256sum` shows `hash  filename` in **lowercase**. When comparing, ignore that case difference.

To verify later that the hash still matches:

```bash
sha256sum -c image.E01.sha256
```

## MD5, SHA-1, SHA-256, SHA-512 — what changes

The command is the same; only the algorithm changes:

| Algorithm | Hash length | PowerShell | WSL |
|---|---|---|---|
| **MD5** | 32 characters | `Get-FileHash file -Algorithm MD5` | `md5sum file` |
| **SHA-1** | 40 characters | `Get-FileHash file -Algorithm SHA1` | `sha1sum file` |
| **SHA-256** | 64 characters | `Get-FileHash file -Algorithm SHA256` | `sha256sum file` |
| **SHA-512** | 128 characters | `Get-FileHash file -Algorithm SHA512` | `sha512sum file` |

What actually changes between them:

- **MD5 and SHA-1** are older and have known collisions — it's been demonstrated that, with deliberate effort, two different files can be crafted with the same hash. Even so, they remain **the most used in forensics** for historical reasons: it's what the E01 format records at acquisition, it's the default in most forensic tools (Sleuth Kit, FTK, EnCase), and for detecting accidental corruption (not a deliberate attack) they're still perfectly reliable.
- **SHA-256** is the current recommended standard wherever the tool allows it — more collision-resistant, with no meaningful cost in computation time.
- **SHA-512** is the longest; used when extra margin is wanted, but it isn't standard in forensics.

To save any of these to a file, the ending is always the same:

```powershell
# PowerShell
Get-FileHash file -Algorithm MD5 | Tee-Object -FilePath file.md5
```

```bash
# WSL
md5sum file | tee file.md5
```

If several hashes are requested, that's a separate calculation per algorithm — there's no single command that computes all of them in one pass.
