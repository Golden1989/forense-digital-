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
python ferramentas/linha_do_tempo.py --sms mmssms.db --calls calllog.db --chrome History --packages packages.xml --fuso -5 --dia 2020-01-29
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

From `History` alone, both download attempts show up as **"cancelled"** in the `downloads` table — which, by itself, would suggest the app never made it onto the device this way. But `analisa_packages.py packages.xml --fuso -5` shows something else: the Magisk package itself is installed on the device, **1 minute and 4 seconds** after the last visit to the download page:

```
53  2020-01-29 11:35:03  com.topjohnwu.magisk  (installer: com.google.android.packageinstaller)
```

**Yes, confirmed — but only by cross-referencing two sources.** The installer is `com.google.android.packageinstaller`, not the Play Store (`com.android.vending`) — exactly what's expected of a manually downloaded and installed APK, and there's no later update (`atualizado_em` equals `instalado_em`). This is a good illustration of why a single artifact shouldn't close an answer: `History` only records what *Chrome* knows about the download (and here it shows "cancelled," possibly because the file was resumed or finished through a path `History` doesn't capture); `packages.xml` is what confirms the APK was actually installed.

### Question 3 — installed apps and sensitive permissions

`analisa_packages.py packages.xml --fuso -5` (without `--so-usuario`, to see the full ranking) shows several user apps granted the `SYSTEM_ALERT_WINDOW` permission (draw over other apps) — including messaging apps (`com.facebook.orca`, `com.viber.voip`) and the device's own dialer (`com.google.android.dialer`).

Running with `--so-usuario --fuso -5`, the list mixes two very different kinds of dates:

```
 1  2008-12-31 19:00:00  com.google.android.youtube  (installer: com.android.vending)   <-- FIRST
 2  2008-12-31 19:00:00  com.google.android.googlequicksearchbox  (installer: com.android.vending)
 ...
58  2020-01-29 12:02:47  com.discord  (installer: com.android.vending)
 ...
```

**Careful reading these dates: `2008-12-31`/`2009` is not a real install.** It's the default value Android itself writes into `packages.xml` when an app has no individual install date recorded (again, typically apps pre-installed by the manufacturer/Google, even ones that technically sit under `/data/app`) — it's just a timezone coincidence that, in UTC-5, that default value falls on 2008-12-31 at 7pm instead of already rolling over to 2009. Most of the 82 user apps carry that default date; it's the few with a real **2020-01-29** date (like `com.discord` above, or `com.topjohnwu.magisk` itself from question 2) that actually say something about what the user installed that day. Before claiming "the user installed N apps on day X," that default-date batch needs to be separated from apps genuinely installed later.

### Question 4 — timeline for 2020-01-29

`linha_do_tempo.py --packages packages.xml --dia 2020-01-29` merges Chrome, SMS, calls and app installs into a single sequence:

```
11:33:27  CHROME  visit      google.com/search?q=magisk
11:33:35  CHROME  visit      magiskmanager.com
11:33:59  CHROME  visit      magiskmanager.com/downloading-magisk-manager
11:35:03  APP     installed  com.topjohnwu.magisk  com.google.android.packageinstaller
12:02:47  APP     installed  com.discord  com.android.vending
   ... (30+ more messaging/social apps installed between 12:02 and 12:12)
13:20:45  SMS     received  ...233205525   [LINE verification code, redacted]
13:30:46  SMS     received  732873          [Telegram verification code, redacted]
13:31:36  SMS     received  ...437514985   [Signal verification code, redacted]
```

(The full numbers and verification codes were removed from this document — they have already expired and come from a public image, but they add nothing to the argument.)

**Two clearly distinct phases on the same day.** The first (11:33-11:35) is a direct, confirmed sequence: searching "magisk," browsing to the download page, and the package showing up installed 1 minute and 4 seconds later — this is question 2 playing out on the timeline. The second phase, almost half an hour later (12:02-13:32), is a batch install of 30+ messaging/social apps through the Play Store, followed by their matching verification SMS messages — a device-setup pattern, not ongoing use. Nothing in the artifacts causally ties this second phase to the "magisk" search: they're separate reads of the same timeline, and treating them as one would overstate what the data supports.

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

**Rooting-tool installation confirmed by cross-referencing two sources; the rest of the day's activity is normal device setup, with no demonstrated link to the rooting itself.**

Searching, browsing and installing Magisk form a direct, confirmed sequence between 11:33 and 11:35 on 2020-01-29: the search for the term (question 1), browsing to the official download page, and, 1 minute and 4 seconds after the last visit, the `com.topjohnwu.magisk` package showing up installed via `packageinstaller` (question 2). `History` alone showed the downloads as "cancelled" — only cross-referencing with `packages.xml` confirms the install, which is itself a methodological finding: no single source was enough.

The rest of the day is a separate activity: 30+ messaging/social apps installed through the Play Store between 12:02 and 12:12, followed by their matching verification SMS messages (questions 3 and 4). That pattern is typical of setting up a freshly activated device, and no artifact ties that phase to the "magisk" search made earlier. Keeping the two phases separate avoids the inflated reading of "the user installed N suspicious apps the same day as the rooting," when in practice most of it is normal setup.

**Recommendation:** confirm with the user why Magisk was installed — since company policy bans rooting, question 2's finding alone already supports opening an internal process — and dig further into the number `...195121037` (question 5), which doesn't fit the sign-up pattern of 2020-01-29.
