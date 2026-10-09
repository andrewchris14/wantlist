# Manual private backup handoff

Repository: `andrewchris14/wantlist`; branch: `work`.
Preparation baseline: `92e10886c048a6d21184e05dc4508c030e577897`.
Owner selected manual Google Drive upload/download. No Google account connection
or upload was performed. This report contains only safe operational metadata.

## Prepared backup

- Encrypted backup creation completed at **2026-10-09T17:17:07.590131+00:00**
  (**October 9, 2026, 12:17:07 PM America/Chicago**). This is the completion
  timestamp; the two sequential snapshot reads occurred immediately before it.
- Source Worker: `wantlist-staging`, identified by its `STAGING_ONLY=true` marker
  and D1 binding. Source database name: **wantlist-staging**.
- Source database UUID: `81f241d4-b17d-4cd4-802d-177f982cc5e1`.
  The name was verified through the Cloudflare API. No production database was used.
- Schema: **18 application tables, 4 explicit indexes, 4 triggers, 0 views**.
  SQLite internal objects were excluded; all application tables were included.
- Ciphertext size: **11,067,422 bytes**.
- Encrypted-file SHA-256:
  `171c0f13997a8e4c703263eec29cd0e9f9e56532a1f549b5a4e76912f494bc23`.

| Snapshot count | Rows |
|---|---:|
| Categories | 7 |
| Stored records, including removed state | 268 |
| Record groups | 369 |
| Items, including removed state | 5,639 |
| Provenance | 65 |
| Change history | 2,239 |
| Public record projections | 268 |
| Mutation receipts | 2,200 |

These are staging snapshot counts, not the full historical source/import totals.
No database rows, authentication information, key material or secrets are included
in this report. The encrypted backup includes the private disaster-recovery state;
that does not authorize publication or plaintext transfer.

## Verification performed

1. Two complete sequential read-only reads of application schema, tables and
   explicit schema objects matched exactly. No remote INSERT, UPDATE, DELETE,
   migration, endpoint toggle or deployment was performed.
2. Snapshot restoration into isolated in-memory SQLite reproduced every table
   row exactly. `PRAGMA integrity_check` returned `ok`; `foreign_key_check`
   returned no violations. Explicit indexes/triggers/views matched exactly.
3. Loading the alphabetically ordered tables with foreign keys enforced during
   insertion initially failed because child tables preceded parent tables. The
   final isolated restore loaded rows before enabling foreign keys, then checked
   every foreign key, integrity, exact row content and schema object. This changed
   only the local restoration procedure, never staging or backup contents.
4. The owner's supplied JWK was validated as RSA-4096 public-only, with encryption
   usage and no private RSA fields. No private key/password/PIN was requested.
5. The verified snapshot was encrypted using the reviewed envelope implementation:
   fresh AES-256-GCM key/nonce, RSA-OAEP-SHA256 key wrapping, authenticated metadata
   and plaintext checksum. Plaintext remained in memory; no plaintext export was
   saved by this preparation. Ciphertext is permission-restricted in ignored work
   storage and is not committed.
6. During handoff preparation the ciphertext SHA-256 was reverified. A further
   complete read-only schema/data read matched the plaintext checksum embedded in
   the encrypted file. Thus the metadata/counts above describe that encrypted
   snapshot, rather than an unrelated later snapshot.

This demonstrates snapshot restoration before encryption. Owner-side decryption
of the actual ciphertext has not occurred and is not claimed.

## Connectivity diagnosis and disposable CPU testing

Current runtime observations report enforced restricted HTTP policy and ready
Cloudflare credentials. The default command sandbox denied socket access to the
configured proxy (`Operation not permitted`), producing curl exit 7. The supported
per-command network permission successfully reached Cloudflare through the same
inherited proxy. No proxy variables, TLS verification or hostname policy changed.
The earlier report of a proxy-service outage was incomplete: a service outage was
not established. No Codex settings change or fresh environment is needed for
Cloudflare access on that basis.

The exact disposable hostname
`wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev` is reachable and again returned
HTTP 404 during this handoff. Phase 3C.3 documented its endpoint as disabled; this
404 is consistent with that state, not proof of working application routes.

**Disposable Worker CPU testing can now proceed using supported per-command
network permission**, provided it re-enables only the disposable endpoint and
verifies its disposable D1 binding first. It must leave human-review staging and
production untouched, use a bounded Free budget, measure actual Cloudflare CPU
and errors for each required operation, and disable the disposable endpoint after
testing. This handoff did not enable it or run CPU tests. The 10 ms Free gate,
earlier CPU outliers, full-collection HTTP tests, maximum combined Save and Undo
remain unverified. Network access alone is not a Free-plan pass.

## Delivery issue and next task

The designated chat output directory
`/codex/browser/projectless/0002-phase-3c-4-complete-outstanding-import-readiness/output`
could not be created: **read-only filesystem**. The supported additional
filesystem permission did not resolve that filesystem/mount limitation. No
working downloadable attachment was produced. Ciphertext remains only in
temporary ignored workspace storage; it is not a durable backup.

**No secure transfer of this encrypted file into a fresh task has been established.
If the next task cannot securely access and reverify this exact ciphertext, it must
repeat the fresh read-only staging snapshot, isolated restoration and encryption
using the owner's public key. Do not substitute an old temporary snapshot or
generate a new owner private key.** The owner may reattach only the same public
key in a fresh task with working downloadable outputs. Never commit ciphertext,
plaintext database exports, authentication information, secrets or private keys.

## Remaining owner actions and durable recovery gate

1. Obtain a task with working file outputs or have the output-directory problem
   repaired. Operator provides only encrypted backup and its SHA-256 checksum.
2. Manually upload ciphertext to **Want List Private Backups**, with sharing
   **Restricted**, then download the actual Drive copy.
3. Operator compares the downloaded ciphertext's checksum against the original.
4. Owner uses the local recovery HTML, retained private recovery-key file and
   password on their own computer. Neither private key nor password is shared.
5. Complete exact restoration of the recovered database on the owner's computer
   or separately approved private isolated storage. Verify all application tables,
   history, removed state, provenance and schema objects. Do not replace live data
   or send plaintext through GitHub/public links.

**Durable backup status: INCOMPLETE.** No Drive copy, download, owner decryption or
restoration of the durable copy has been demonstrated. No Paid activation,
historical import, 202-record practice archival, staging-record modification or
production deployment occurred. Stop for owner review.
