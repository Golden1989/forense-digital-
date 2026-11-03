# Fictional case: a rooted corporate phone?

> **This is different from the course's image.** The rest of this repository deliberately avoids any real case data (see why in the [README](../../README.en.md)), because the image used in the course is assessment material. This document is the opposite: it uses a **public image** that anyone can download and verify, created specifically to train the digital forensics community — it has no connection to the course or to any exam. The **company and the suspicion below are fictional**; the **device and the technical artifacts are real**.

## Data source

- **Image:** "Android 10 Image" — Google Pixel 3 (model G013A), Android 10.
- **Created by:** Joshua Hickman ([thebinaryhick.blog](https://thebinaryhick.blog)), donated to [Digital Corpora](https://digitalcorpora.org/corpora/cell-phones/android-10/), a public archive maintained for digital forensics research, education and training.
- **Download used:** the file-level extraction ("Non-Cellebrite Extraction"), no paid tool required.
- **Official documentation:** the image ships with a 36-page PDF describing, minute by minute, every action taken on the device while it was created (apps installed, messages, calls, browsing). The questions below were answered **using only the scripts in this repository**, without consulting that "answer key" — it's mentioned here only as provenance context for the image.
- All timestamps in the original image are UTC-5 (Eastern Standard Time); the commands below use `--fuso -5` to match the official documentation.

## Scenario (fictional)

The IT department at **Example Technology Inc.** found a "device not compliant" alert in the MDM app for a corporate Google Pixel 3. The suspicion: the employee may have rooted the device (against company security policy) to install apps outside the corporate store. The device was collected and an extraction was performed.

## Questions

1. Is there any sign the user searched for or tried to obtain a rooting tool on the device?
2. Was that tool actually downloaded? Did the download complete?
3. Which user apps were installed during the period, and do any of them hold sensitive permissions (camera, SMS, draw over other apps) worth attention?
4. Reconstruct the timeline for the first day of use after the suspected rooting (2020-01-29): what did the user do, in what order?
5. Are there any numbers in calls or SMS that aren't in the device's contact list?
6. Are there any contacts marked as deleted that should be preserved for the investigation?

## Methodology

Every command below was run with the scripts in [`ferramentas/`](../../ferramentas/) directly against the extracted files (Chrome's `History`, `Favicons`, `Cookies`; `mmssms.db`, `calllog.db`, `contacts2.db`; `packages.xml`), without modifying the originals:

```
python ferramentas/resumo_navegacao.py History --site magisk --fuso -5
python ferramentas/downloads_chrome.py History --fuso -5
python ferramentas/analisa_packages.py packages.xml --so-usuario --fuso -5
python ferramentas/linha_do_tempo.py --sms mmssms.db --calls calllog.db --chrome History --fuso -5 --dia 2020-01-29
python ferramentas/contatos_merge.py --contacts contacts2.db --calls calllog.db --sms mmssms.db --fuso -5
python ferramentas/favicons_fora_do_historico.py --favicons Favicons --history History --fuso -5
```

## Findings

### Question 1 — search for a rooting tool

`resumo_navegacao.py --site magisk` shows the very first activity of the period, a direct Google search:

```
first:  2020-01-29 11:33:27  https://www.google.com/search?q=magisk&oq=magisk...
middle: 2020-01-29 11:33:55  https://magiskmanager.com/#How_to_Download_Magisk_Manager...
last:   2020-02-14 16:58:15  https://magiskmanager.com/downloading-magisk-manager
```

**Yes.** There's an explicit search for the term "magisk" (a well-known rooting tool) at 11:33:27, immediately followed by browsing to `magiskmanager.com` and its download page, within the same minute.

### Question 2 — did the download complete?

`downloads_chrome.py` records two downloads of the file (via a redirect chain ending at a GitHub release asset), both with the same outcome:

```
1. [cancelled, 2143331 bytes, danger: not dangerous]
   downloaded from: https://magiskmanager.com/downloading-magisk-manager
   final URL:  https://github-production-release-asset-.../...  (3 URLs in the chain)
   start: 2020-01-31 21:11:22
2. [cancelled, 2143331 bytes, danger: not dangerous]
   downloaded from: https://magiskmanager.com/downloading-magisk-manager
   start: 2020-02-14 16:58:20
```

**Inconclusive from `History` alone.** Both download attempts show up as **"cancelled"** in the `downloads` table — which, at first glance, would suggest the app never made it onto the device this way. This is exactly the kind of finding that can't be closed with a single artifact: `History` records what *Chrome* knows about the download, not whether the APK was actually installed afterward (that would live in artifacts such as the system's package-install log, outside the scope of the current scripts). Worth flagging the caveat explicitly: a "cancelled download" is not the same as "tool never installed."

### Question 3 — installed apps and sensitive permissions

`analisa_packages.py packages.xml --fuso -5` (without `--so-usuario`, to see the full ranking) shows several user apps granted the `SYSTEM_ALERT_WINDOW` permission (draw over other apps) — including messaging apps (`com.facebook.orca`, `com.viber.voip`) and the device's own dialer (`com.google.android.dialer`).

Running with `--so-usuario --fuso -5`, it stands out that **most of the 82 user apps share the same install date** (2020-01-29, around 7pm UTC-5 — the device's activation time), rather than dates spread across the investigated period:

```
 1  2008-12-31 19:00:00  com.google.android.youtube  (installer: com.android.vending)   <-- FIRST
 2  2008-12-31 19:00:00  com.google.android.googlequicksearchbox  (installer: com.android.vending)
 ...
```

**Relevant finding, with a caveat.** This is exactly the warning already documented in the script itself: apps pushed during the initial Google account provisioning share the activation date, not the user's actual install/use date. Before claiming "the user installed N apps on day X," that initial batch needs to be separated from apps genuinely installed later (e.g., the instant-messaging apps, which `packages.xml` shows installed minutes later, already inside the window of interest).

### Question 4 — timeline for 2020-01-29

`linha_do_tempo.py --dia 2020-01-29` merges Chrome, SMS and calls into a single sequence:

```
11:33:27  CHROME  visit     google.com/search?q=magisk
11:33:35  CHROME  visit     magiskmanager.com
11:33:59  CHROME  visit     magiskmanager.com/downloading-magisk-manager
13:20:45  SMS     received  ...233205525   [LINE verification code, redacted]
13:30:46  SMS     received  732873          [Telegram verification code, redacted]
13:31:36  SMS     received  ...437514985   [Signal verification code, redacted]
```

(The full numbers and verification codes were removed from this document — they have already expired and come from a public image, but they add nothing to the argument.)

**Two separate activities on the same day, with no direct link between them:** the search and browsing to the rooting tool at 11:33, and a run of verification SMS messages (LINE, Telegram, Signal) at 13:20-13:32. Question 3 already showed that 2020-01-29 is the device's **activation** day — so these SMS messages and the matching app installs are exactly what's expected from a freshly activated phone, and nothing in the Chrome, SMS or `packages.xml` artifacts ties that sign-up sequence to the "magisk" search made hours earlier. The only direct evidence of interest in rooting, in this question, remains the browsing itself (question 1); the rest of the day's activity is consistent with normal use of a new device.

### Question 5 — numbers outside the address book

`contatos_merge.py` cross-references `contacts2.db` with `calllog.db`/`mmssms.db` and lists, at the end, the numbers that appear in calls or SMS but don't match any saved contact:

```
NUMBERS IN CALLS/SMS NOT IN THE ADDRESS BOOK: 16
  ...32665     SMS: 8 [received=8] first 2020-01-29 13:50:24 | last 2020-02-13 16:12:24
  ...195121037 calls: 2 [missed=1, voicemail=1] first 2020-02-12 10:37:29
  ...233205525 SMS: 1 [received=1] first 2020-01-29 13:20:45
```

**Yes, 16 numbers.** Most are short sender IDs (verification codes for the apps in question 4) — expected when signing up for several messengers the same day — but the number `...195121037`, with one missed call and one voicemail call several days later (02/12), doesn't fit that pattern and would be worth confirming with the device's user.

### Question 6 — deleted contacts

```
python ferramentas/contatos_merge.py --contacts contacts2.db --so-apagados
```

```
#raw6 Josh Hickman  [DELETED]   phone: +990841016803084  accounts: 858233690 (org.telegram.messenger)
#raw7 Josh Hickman  [DELETED]   phone: +990841016803084  accounts: 858233690 (org.telegram.messenger)
```

**Yes, 2 records** flagged as deleted (`deleted=1` in `raw_contacts`), both synced via Telegram. Since `contatos_merge.py` only reads what's still in the database, the recommendation here is to preserve the image unmodified — a record flagged as deleted in the contacts provider may still be fully recoverable through unallocated-SQLite-space analysis tools (outside the scope of the current scripts).

## Bonus: a caveat from the method itself

Running `favicons_fora_do_historico.py` on the same `History`, 13 pages show up with a saved favicon but **no matching visit** (ESPN, Wikipedia, eBay, Amazon, Facebook, YouTube...), all with the same icon-update time (11:33:09, a few seconds before the "magisk" search). This is **not** a sign of history clearing — it's the set of suggested/shortcut sites Chrome for Android preloads on first launch. It's a real-world example of the exact warning already in the script's own docstring: "a domain's absence from history doesn't prove the page was visited and then deleted."

## Conclusion (fictional)

**Sign of interest in rooting; installation not confirmed; the rest of the day's activity is consistent with normal device activation.**

The only finding that directly points to the case's suspicion is the explicit search and browsing session for a rooting tool (Magisk) on the morning of 2020-01-29 (question 1). The following two points weigh against closing the conclusion as "rooting confirmed":

1. `History` marks both Magisk Manager download attempts as "cancelled" (question 2) — without an additional source (a package-install log, for instance), it isn't possible to confirm whether rooting actually happened through this path.
2. The rest of the day's activity — most of the "installed" user apps (question 3) and the LINE/Telegram/Signal verification SMS messages (question 4) — coincides with the device's **activation** day, not with the rooting window itself. That activity has a simple alternative explanation (setting up a brand-new phone) that doesn't depend on the rooting hypothesis, and the artifacts show no direct link between it and the "magisk" search. Treating these two groups of evidence as one and the same would overstate what the data actually supports.

**Recommendation:** preserve the image, seek root confirmation through another path (e.g., an `su` binary, build properties, Magisk files on the filesystem) before asserting a policy violation, and dig further into the number `...195121037` (question 5), which doesn't fit the sign-up pattern of 2020-01-29.
