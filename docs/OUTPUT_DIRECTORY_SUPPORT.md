# Support report: downloadable output directory is read-only

Reported October 9, 2026 (America/Chicago). Repository: `andrewchris14/wantlist`.

Two separate Codex tasks could not create their designated downloadable-output
directories:

1. `/codex/browser/projectless/0002-phase-3c-4-complete-outstanding-import-readiness/output`
2. `/codex/browser/projectless/0003-files-mentioned-by-the-user-uploaded-file-pointe/output`

The first failure is recorded in `docs/MANUAL_BACKUP_HANDOFF.md` as a read-only
filesystem; supported additional filesystem permission did not resolve it. The
second task reproduced the failure before attempting a backup. Its exact error:

```text
mkdir: cannot create directory ‘/codex’: Read-only file system
```

The second task's advertised permission profile included write access to the
projectless task directory, but the filesystem still rejected creation of
`/codex`. `/workspace` was usable for repository work. This indicates a mismatch
between the advertised output location and the executor's writable filesystem;
an agent-level permission grant alone did not establish a usable output mount.
The precise platform/mount cause has not been diagnosed.

Support should repair or provision the writable output filesystem at the
designated path in the execution environment and ensure files written there are
exposed as downloadable chat attachments. Verify both an innocuous test-file
write and an actual attachment download. Alternatively, provide a supported
writable output location and update the task's designated attachment path.
Changing Cloudflare networking does not repair this local filesystem issue.

Backup delivery retries are paused at the owner's request. No backup, credential,
private key, recovery password, authentication value or database contents are
included in this report. GitHub, public links and unapproved transfers must not
be used as substitute backup-delivery channels.
