# Owner setup: private encrypted Google Drive backups

This setup does not purchase Cloudflare services or import/clean up the collection.
No Drive connection or upload has been made.

## Create and keep your recovery files

1. Open [the recovery page in GitHub](https://github.com/andrewchris14/wantlist/blob/work/tools/backup-recovery.html).
   Use **Download raw file** above the code. Save `backup-recovery.html` on your
   own computer, then double-click it to open in an up-to-date browser.
2. Enter a strong recovery password, at least 16 characters. Keep it in your
   password manager. This password protects your private recovery key; it is not
   the website PIN, your Google password or a new login credential.
3. Select **Generate recovery files**. Then use the two separate download buttons.
4. Keep `wantlist-private-recovery-key.ENCRYPTED.json` on a secure USB or another
   owner-controlled location outside GitHub and this agent workspace, separate
   from the Drive backups. Keep a second safe copy. Do not send this file or its
   password to the agent. Keep the downloaded setup page for future recovery.
5. Share **only** `wantlist-public-key.json` with the backup operator. It cannot
   decrypt a backup. The private recovery key stays on your own computer/storage.

The page performs cryptography locally and has a policy forbidding network
connections. The operator's encryption tool refuses private keys. Losing the
private recovery file and/or its password can make backup recovery impossible.

## Choose and authorize the Drive destination

Create a folder in your personal Google Drive, such as **Want List Private Backups**.
Keep its sharing setting **Restricted**; do not make it public or enable an
anyone-with-link permission. Identify that folder for the operator.

Authorize a Google Drive connection and explicitly approve uploading encrypted
backups to that exact folder. Connection availability is not assumed. If the
connection cannot upload/download files, the operator can provide ciphertext for
you to upload/download manually; that does not require terminal commands.

Only encrypted database files belong in the Drive backup folder. Do not upload
plaintext database exports or the private recovery key there. The backups include
sensitive hashed session/authentication state, even though they contain no PIN
secret; encryption is mandatory.

## Verify a durable copy before approving cleanup/import

The operator creates a fresh consistent backup, proves local restoration, then
encrypts it using your public key. After upload, download the Drive copy again.
The operator compares its ciphertext checksum with the original.

Use **Recover an encrypted backup** on the local recovery page. Select your
password-protected recovery-key file and the downloaded encrypted backup, enter
the password, and confirm the recovered file will remain private. A successful
recovery verifies authenticated encryption and the plaintext checksum.

The resulting `wantlist-recovered-backup.PRIVATE.json` is sensitive. Store it
privately and share it only through an approved private recovery channel with
the authorized operator. Never put it in GitHub or a public link. The operator
must demonstrate an isolated database restore and compare records, history,
removed state, categories, metadata, provenance and import receipts. Do not
replace the live database or newer owner edits as part of this check.

**The durable-backup gate remains incomplete until a Drive copy has been
retrieved, decrypted and restored successfully.** No owner key/public key,
authorized folder or durable copy has been provided yet. Cloudflare's native
backup/Time Travel recovery has not been tested.
