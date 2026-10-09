# Jason's Windows backup and recovery guide

**Prepared for review — do not run it yet.** October 9, 2026 (America/Chicago).
No real export, Cloudflare operation or owner recovery has been performed.
The instructions below are for use **after owner review and approval**.

The goal is one verified, recoverable encrypted copy outside Cloudflare before
any destructive staging changes, archival or full historical import. Your own
computer or USB is acceptable. Google Drive is optional. Hosting stays on Free;
this workflow buys nothing and creates no recurring subscription.

## What you need

- Your Windows 10/11 computer, with **Device Encryption or BitLocker already on**.
  In Windows **Settings**, search for **Device encryption** and check its status.
  If unavailable or off, stop for advice; do not buy an upgrade for this workflow.
- An up-to-date **Microsoft Edge** or **Google Chrome** browser.
- One free installation of **Python 3.12 or newer**, from Python's official site.
  No terminal, Wrangler, Node, `pip` commands, extra packages or administrator
  permissions are needed. Python provides the local database restoration engine.
- Your existing `wantlist-public-key.json`, your encrypted private recovery-key
  file, and your recovery password. **Do not generate replacement keys.**
  Never send your private key, password, API token, or plaintext to Codex.
- A computer folder or USB drive you control. Keep your recovery key/password
  safe, preferably separately from the encrypted backup. Keep the receipt too.

A downloaded HTML page alone cannot safely do all of this: it has no SQLite
restoration engine and cannot prove that every table was recovered. The small
Python companion opens a local browser page and handles read-only D1 access and
memory-only SQLite checks. Encryption/password entry remain in the browser.
It does not install an extension, service, scheduled task or Cloudflare Worker.

## Download and open the local tool

Do these steps only after the workflow is approved.

1. If Python is not installed, open
   [Python's Windows download page](https://www.python.org/downloads/windows/).
   Under the latest supported Python release, choose **Windows installer (64-bit)**
   for a typical Intel/AMD computer. For an ARM computer, use its ARM64 installer.
   Open the downloaded installer and choose **Install Now** for your user account.
   Keep the normal file associations and standard library. **Add to PATH** is not
   needed. If Windows requires administrator access, cancel and seek help rather
   than installing for all users. Do not download an unofficial Python package.
2. Open [the Want List repository on `work`](https://github.com/andrewchris14/wantlist/tree/work).
   Confirm the branch selector says **work** and its latest commit matches the
   version approved in the review. If it has advanced, stop and request the
   reviewed download. Click the green **Code** button,
   then **Download ZIP**. These are application files, not database contents.
3. Open **File Explorer → Downloads**. Right-click the ZIP and select
   **Extract All… → Extract**. Keep the extracted files together. Do not run the
   app inside the ZIP or copy just one of its files.
4. Inside the extracted repository, open **tools → windows-backup**.
   Double-click **Start Want List Backup.pyw**. It opens a browser tab titled
   **Want List local backup and recovery**. No command-line window is required.
5. The address must start with **`http://127.0.0.1:`**, followed by a changing port
   number. This is your own computer, not a public website. Do not paste tokens
   or recovery materials into any other website. Do not double-click `backup.html`
   directly; the companion is needed for isolated restoration.
6. If your default browser is neither Edge nor Chrome, set Edge as the default
   browser in Windows **Settings → Apps → Default apps**, then launch again.
   If Windows asks whether Python may communicate on networks, **Cancel** that
   firewall prompt; this tool needs only your computer's loopback connection.
   If `.pyw` opens as text or Windows cannot find Python, stop for help. Do not
   paste its contents into a terminal or bypass security warnings.

The local tool ends when you click **Close and clear local tool**, or after
15 minutes without an operation. If it has expired, launch it again. It never
stores your token or recovery password in a settings file.

## Before creating a backup: quota and read-only access

**Do not do these Cloudflare steps now.** After review, wait until the reported
quota exhaustion has cleared and there is confirmed headroom. A quota reset
alone does not prove headroom: all D1 databases in the account share the limit.

1. Stop your own Want List edits, importers, tests and other D1 jobs for at least
   **30 minutes**. Do not change the website PIN or revoke sessions. If other
   applications are still generating heavy D1 traffic, stop this backup attempt;
   this tool cannot reserve their quota or pause them.
2. Sign in to Cloudflare in a separate normal browser tab. Select the correct
   account and confirm your plan is **Free**. Do not activate Paid.
3. Find the account's D1 usage/metrics page under **Storage & databases → D1**
   (navigation labels may vary). Obtain **account-wide rows read and rows written
   for the current UTC quota day**, across all databases. Use the cumulative
   daily totals or a custom UTC-midnight-to-now interval. **Last 24 hours**, one
   database, or your local calendar day is not the same measurement. If you
   cannot find clear account-wide UTC-day totals, stop and ask for help.
4. The local tool shows today's **UTC** quota date. Copy the fresh daily totals
   into its **rows read** and **rows written** boxes, using numbers only.
   Keep **Cloudflare sent a D1-limit notice for this UTC quota day** checked when
   that notice applies. Only uncheck it once a fresh quota day/headroom is verified.
   Do not uncheck it merely to get past a stopped export.
5. Create a separate, short-lived **read-only API token**. In Cloudflare click
   your profile/avatar → **My Profile → API Tokens → Create Token → Custom token
   → Get started**. Name it **Want List local backup**. Add exactly:

   - **Account → D1 → Read**
   - **Account → Account Analytics → Read**
6. Under **Account Resources**, choose **Include → Specific account → your account**.
   Do not select all accounts. Set an expiry for the next day, review the summary,
   and click **Create Token**. Do not use the Global API Key, an existing powerful
   deployment token, D1 Write, Workers Edit, billing or administrator permissions.
   If Cloudflare refuses these read-only permissions, **stop**. Do not broaden them.
7. Copy the token into the local tool's **Short-lived read-only API token** box.
   Find your **Account ID** in Cloudflare's account details/Workers account panel
   and copy it into **Cloudflare Account ID**. Account ID is not a login secret.
   After pasting the token, overwrite your clipboard by copying a harmless word.
   Never paste this token into chat.

Account Analytics Read is needed for the automatic **account-wide** quota check.
Cloudflare's account-scoped D1 Read permission can read other D1 databases in that
account; it is not a database-only token. The tool itself is fixed to the approved
`wantlist-staging` UUID and cannot select another database. If your account hosts
unrelated sensitive databases, review that permission tradeoff before proceeding.
The public API schema lists D1 Read as accepted for its query endpoint. This
specific owner's new read-only token has not yet been tested remotely.

## Create and save the encrypted backup

1. In **Create an encrypted staging backup**, click **Choose File** beside
   **Existing public encryption key** and select **wantlist-public-key.json**.
   Do not select your private recovery key in this section.
2. Recheck the source is **wantlist-staging**, the account ID and read-only token,
   the daily counters, and the limit-notice checkbox. Confirm the four statements
   about owner approval, Free plan, stopped jobs/edits, and your encrypted private PC.
3. Click **Create backup: check quota, verify and encrypt** once. Do not repeatedly
   click or retry a failed export. The page shows progress while it works.
4. The tool checks live account analytics before any SQL, verifies the staging
   database name and UUID, discovers all application tables, takes two complete
   matching read snapshots, and restores every row/schema object into a fresh
   local database in memory. It includes listings, notes/edits, Pending, removed
   rows, history, provenance, categories, receipts and hashed authentication state.
   It cannot retrieve Worker secrets such as the PIN, and does not change them.
5. It encrypts the verified snapshot using your **existing public key**. You need
   no recovery password or private key to create a backup.
6. Wait for **Encrypted backup ready to save**. Click **Save encrypted backup**.
   Save the filename ending in **`.ENCRYPTED.json`** to your chosen folder or USB.
   Click **Save checksum receipt** and save that receipt beside it.
7. If your browser saves automatically to **Downloads**, that is safe: the
   downloaded backup is already encrypted. In File Explorer move the encrypted
   backup and receipt to your chosen folder or USB. Alternatively, in Edge use
   **Settings → Downloads → Ask me what to do with each download** before saving.
   For Chrome use **Settings → Downloads → Ask where to save each file**.
8. The page and receipt show the filename, size and **SHA-256 checksum**. The
   receipt says **recovery has not yet been verified**; creating an encrypted file
   alone does not complete the backup requirement.

Quota policy: the tool reserves **1,250,000 reads** for the bounded operation plus
**1,000,000 reads** for telemetry lag/other activity. Thus observed daily reads
must be no more than **2,750,000** before starting, and daily writes below 100,000.
It uses the higher of your fresh dashboard reading and live analytics, checks
again between reads, and counts its own reported usage. Unknown/empty analytics,
missing accounting, a current limit notice or insufficient headroom means **stop**.
These are conservative safety margins, not an atomic Cloudflare quota reservation
or a guarantee against unrelated traffic. It cannot read a database after the
Free limit has blocked access.

Every snapshot uses one read-only SQL statement; the native D1 export job is not
used because it may temporarily make the database unavailable. There are no
remote INSERT/UPDATE/DELETE operations, Workers deployments or endpoint changes.

## Verify the actual saved file and test recovery

You can do this later, or with Wi-Fi disconnected. No API token is needed.

1. Launch **Start Want List Backup.pyw** again if you closed the tool. Skip the
   entire Create backup section; do not fill its Cloudflare fields.
2. Open your saved **checksum receipt** in Notepad: right-click → **Open with →
   Notepad**. Find **encrypted_sha256**. Copy the 64 letters/numbers inside the
   quotes; do not copy the quotes. Do not edit the receipt.
3. Under **Verify your saved copy and test recovery**, click **Choose File** for
   **Actual encrypted backup** and select the file **from its real saved location**
   on your computer or USB. For USB, safely eject/reinsert it first to check the
   stored copy, rather than a temporary browser download.
4. Paste the checksum into **Expected encrypted SHA-256 checksum**.
5. Choose your existing **wantlist-private-recovery-key.ENCRYPTED.json** and enter
   your recovery password. These stay in the local browser. Neither goes to
   Cloudflare, the Python companion, GitHub or Codex. Do not share them for help.
6. Click **Check saved copy, decrypt and test isolated restore**.
7. Only accept **Recovery succeeded for this saved copy**. It means:

   - The saved encrypted file matches the receipt's SHA-256.
   - The existing private recovery key/password decrypt it successfully.
   - Authenticated encryption and the plaintext checksum pass.
   - A fresh in-memory SQLite database reproduces every application row, schema,
     index, trigger/view, history, metadata, provenance and removed state.
   - Integrity and foreign-key checks pass; the live website is unchanged.
8. Click **Save recovery verification receipt**, and keep it with the encrypted
   file and original receipt. Click **Close and clear local tool**, then close
   the browser tab. Remove the short-lived backup API token from **My Profile →
   API Tokens** when finished, or let it expire. No website sessions are invalidated.

This successful test of your actual saved copy completes the **backup recovery
verification** for that snapshot. It does not authorize a historical import,
archival, destructive changes or live restoration. Send only the verification
status/checksum to request further owner review, never recovered plaintext.
If edits happen after the backup, it will not contain those newer edits: take and
verify a fresh approved backup before a later destructive operation.

Keep at least the verified encrypted copy outside Cloudflare and retain its
recovery materials. A second encrypted copy is sensible if convenient, but Drive
and a paid backup service are not requirements. Losing the private key/password
can make all copies unrecoverable.

## If anything stops

- **Quota/usage unavailable or insufficient:** do not retry or buy Paid. Wait for
  confirmed headroom and review. Do not substitute guessed counters.
- **Snapshot changed:** stop edits/jobs and seek review before another attempt.
- **Schema, row or size limit:** nothing is silently omitted. This reviewed tool
  supports 32 application tables, 100 schema-discovery rows, 40 columns per table,
  up to 300,000 emitted snapshot rows and a 128 MiB API/plaintext limit. Future
  schema growth or large history may need a reviewed adjustment; no partial copy
  is called a complete backup.
- **Checksum mismatch:** select the original retained file and its own receipt.
  Do not change the expected checksum to match a suspicious file.
- **Wrong key/password or restoration failure:** retain the encrypted file and
  report the short error message. For another approved attempt, select the recovery
  key again and re-enter the password; the tool clears them after each attempt.
  Do not send your files/password or export
  plaintext. Older backup formats require their original recovery procedure;
  this new memory-only restore format does not convert them automatically.
- **Windows/browser warning:** stop for help; do not disable antivirus or browser
  protections. Do not install an unofficial packaged executable.

The application deliberately never writes/downloads an unencrypted database.
Plaintext exists transiently in local RAM and on loopback between the browser and
companion during verification. Operating systems can page memory or make crash
or hibernation dumps, which is why an encrypted private Windows computer is
required. Python/browser memory cannot be promised to erase every copy instantly.
This protects against accidental plaintext exports; it is not protection against
malware, administrator access or a compromised browser. Use a trusted download
and private computer, and keep the original checksum receipt trustworthy.
