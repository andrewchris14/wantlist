# Owner setup: verified encrypted backup outside Cloudflare

The owner has retained the existing private recovery key and recovery password.
**Do not generate new keys or send recovery materials to Codex.**

Google Drive is **optional**, not a requirement. A securely retained encrypted
backup on the owner's computer or USB is acceptable. The gate is one outside-
Cloudflare copy whose actual saved file has been checksum-checked, decrypted and
restored successfully in isolation before destructive staging changes, archival
or full historical import. Hosting must remain $0/month on Cloudflare Free.

The new [Windows backup guide](WINDOWS_BACKUP_GUIDE.md) and
[technical review](WINDOWS_BACKUP_REVIEW.md) describe the prepared owner-run,
click-through workflow. It uses the existing key/envelope formats, creates no
plaintext database file, and tests restoration in RAM without changing the live
website. One free Python installation and an up-to-date Edge/Chrome browser are
needed; no terminal, Wrangler, extra packages or Drive connection.

**Prepared for owner review only.** No real export or remote Cloudflare operation
was performed while preparing it. Windows launch/file-association behavior and
actual read-only account permissions still need owner-side verification. Quota
headroom must be confirmed before any export; a current limit notice blocks it.
The previous backup remains undelivered and owner recovery remains unverified.

`tools/backup-recovery.html` remains available for the original recovery-file
format and legacy recovery procedure. Its old **Verify and recover backup**
button downloads plaintext; use the new Windows workflow for memory-only restore
of new backups. The new workflow supports the existing public key and protected
private key; it does not require making replacements.

If you choose Drive later, keep the folder Restricted and upload only ciphertext.
Download the actual Drive copy again and verify/decrypt/restore it just like a
local/USB copy. There is no requirement to connect Google to Codex.
