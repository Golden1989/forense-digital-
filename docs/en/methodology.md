🌐 [Ler em português](../metodologia.md)

# Where to start with an image

When you're handed an image "in the dark," with no context, it's because in real forensics **nobody hands you a pre-chewed case**. You get a disk and a vague question — and it's up to you to turn that into hypotheses, examinations, findings and answers.

> The questions and scenario used as examples in this file are **fictional**, written only to illustrate the method — they're not from any real exam or case.

## The chain of reasoning

Every examination you run needs to serve answering a question:

```
Facts → Objective → Questions → Material → Methodology → Findings → Discussion (nexus) → Answers
```

The **image's name** is often the first clue. `image_company` → corporate case (data leak, fraud, misuse, unauthorized access). A person's name → personal case. It proves nothing, but it already raises the hypotheses that guide the search.

## Define the questions first

If the prompt doesn't give you the questions, derive them from the scenario. Example for a corporate case:

| # | Question |
|---|---|
| 1 | Is there evidence of **copying/transferring company data** out (USB, cloud, personal email, upload)? |
| 2 | **Which files** were accessed or copied, and how relevant are they (confidential, client data, financial, source code)? |
| 3 | Can you identify **when** it happened and **which user** did it? |
| 4 | Is there evidence of **hiding or destroying** evidence (deletion, wiping, encryption, renaming)? |
| 5 | Is there **communication** (email, chat) related to the event? |
| 6 | Was the device used for **unauthorized access** to systems or accounts? |

Adjust after looking at the image — but start with a draft, because it's what points the rest of the work.

## When reading the case, take notes on

Before opening the image, read the case story pen in hand. Each item below becomes a search term, a date filter, or a category to check later:

- **Names, nicknames and companies mentioned** — all of them, including nicknames and company-only names. They become text searches and help find senders/recipients.
- **Dates and the timeframe of the event** — defines the time window: filter creation, modification and access dates by it.
- **Amounts and keywords** — in corruption cases, for example, money tends to show up disguised. Worth testing terms like "commission," "allowance," "coffee money," "favor," "consulting fee," "fee," besides "bribe" and "payment." These are just examples: the case story may use different terms.
- **Likely file types** — spreadsheets, emails, documents, images. Tells you which categories to check first.

## The order of operations

Never start by clicking a random file. Go from the big picture to the detail:

1. **Preservation — before opening anything.** Confirm the image's hash (see [`hashes.md`](hashes.md)). From here on, work only on the image, never the original.
2. **Lay of the land.** Before looking for a crime, understand the machine: operating system and version, computer name, timezone (defines whether dates are local or UTC), OS install date, last shutdown, user accounts (how many, names, which is the suspect's, last logon), partitions (does the size match? is there unpartitioned space?).
3. **The time window.** Every case has a period of interest. Sometimes it's given; sometimes you **infer** it: the last week of work, the date of a resignation, a spike of unusual activity. Once the window is set, almost everything gets filtered by it.
4. **Artifact-by-artifact sweep, guided by the questions.** Now, artifact by artifact — each block answers a question (table below).
5. **Timeline.** Gather everything with a date and order it. You want the **sequence**: *USB plugged in 2:02 PM → "Clients" folder opened 2:03 PM → spreadsheet copied 2:05 PM → `backup.rar` created 2:09 PM → 3 files moved to the Recycle Bin 2:11 PM → USB removed 2:12 PM*. That's not five loose findings — it's a story with temporal nexus and authorship.
6. **Correlation.** One artifact alone is weak ("there was a USB drive"). Three in the same minute are strong. Always ask: what else happened at that timestamp?

## The artifact sweep — detail of step 4

| What to check | Answers | Where to look |
|---|---|---|
| Connected USB devices (make, serial, first/last connection) | did data leave via USB? | Windows Registry (`USBSTOR`, `MountedDevices`, `setupapi`) |
| Recent files / LNK / Jump Lists / shellbags | what was opened, and from where | User recent-activity artifacts |
| Program execution (Prefetch, Amcache, SRUM, UserAssist) | ran WinRAR? CCleaner? a cloud client? | Windows Registry, Prefetch folder |
| Browser (history, downloads, searches, uploads) | uploaded to Drive / WeTransfer? webmail? | Browsing history |
| Email and chat | communication about the event | Mailboxes, messaging apps |
| Files of interest (Desktop, Documents, Downloads, temp) | which files, how relevant | User profile folders |
| Archives (zip / rar / 7z) | bundling for exfiltration | Anywhere, but note creation dates |
| Recycle Bin + deleted + carved | attempted to destroy? | Deleted and signature-recovered items |
| Cloud folders (OneDrive, Google Drive, Dropbox) | sync to the outside | User profile |
| Anti-forensics (CCleaner, Eraser, BleachBit, VeraCrypt) | concealment | Installed programs, execution history |

## What makes a file "suspicious"

- **Location:** Desktop, Downloads, Documents, `Temp`, root of a USB drive, hidden folders, `AppData` (where the browser and chat apps store data).
- **Name:** "confidential," "salaries," "clients," "passwords," "copy of," "backup," "personal," the company's name, a competitor's name.
- **Extension ≠ content:** forensic tools flag signature mismatches — a `.txt` that's actually a `.jpg`, a `.jpg` that's actually a `.rar`. A classic sign of something hidden.
- **Large archives** created close to the time window.
- **Timestamps** clustered in the period of interest, or inconsistent (created after modified, access "in the future," metadata changed with no content change = possible *timestomping*).
- **Deleted / carved / in the Recycle Bin / in unallocated space.**
- **Encrypted or password-protected.**
- **Orphan** (no parent folder) — came from unallocated space.
- **Accounts, scheduled tasks or startup entries** created recently.

## The golden rule

Everything you search for has to answer a question. Found something that answers none of them? Either it's context, or you've just discovered a new question.

## Report skeleton (structure, no content filled in)

| Section | What goes there |
|---|---|
| **Preamble** | Date and place of the examination, who requested it, your name as examiner |
| **Background / Summary of facts** | The case scenario |
| **Objectives and Questions** | The questions the examination needs to answer |
| **Material description** | Image type, size, filename, hash and integrity-verification result |
| **Chain of custody** | How the evidence was received; hash at acquisition vs. at verification |
| **Methodology** | Tools used and the steps followed |
| **Relevant findings** | Objective list — each finding with name, path, hash, dates, status (active/deleted/carved) and why it's relevant |
| **Discussion** | Where you argue the nexus: timeline, correlation between findings, date consistency |
| **Answers to the questions** | Each question: YES / NO / PARTIALLY / INCONCLUSIVE, always pointing to the finding that supports the answer |
| **Closing** | Number of pages, place, date, signature |

A rule that always applies: **never answer a question without pointing to the evidence.** A bare "yes" doesn't count; "yes, per items 3 and 5 of the Findings" does.
