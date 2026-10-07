# Phase 3B.2 staging checkpoint: stopped at password verification

On 2026-10-07, staging resumed from approved commit
`8c8010bf3d825214331185397849f64e5306b481`. No production cutover occurred.

## Actual Cloudflare evidence

- The restricted API token verified active. The owner manually verified Workers
  Free ($0, 100,000 requests/day, 10 ms CPU/request) and D1 Free (5 million
  reads/day, 100,000 writes/day, 5 GB total, 10 databases), without payment details.
- Billing/subscription API verification was unavailable to this token (403).
  Account settings alone do not establish the billing plan. No paid setting was enabled.
- Created only the staging Worker `wantlist-staging-3b2-probe`, using
  `foundation/staging/password-probe.mjs` and the unchanged foundation `auth.js`.
  It had no D1 binding, owner credential, dataset, production route, or custom domain.
- A disposable server-side secret protected the probe. Its local access file is
  ignored under `foundation/.local/`; it must never be committed or published.
- A real POST to the staging workers.dev endpoint returned the preserved result
  in `foundation/staging/password-probe-result.json`:

  `NotSupportedError: Pbkdf2 failed: iteration counts above 100000 are not supported (requested 600000).`

- This is a Workers runtime compatibility failure for the approved 600,000-iteration
  PBKDF2-SHA256 verifier. It is not a measured CPU overrun, and does not prove all
  secure authentication alternatives impossible. The work factor was not lowered.
- After recording the result, workers.dev access was disabled, with previews disabled.
  The staging Worker remains in the account; its public endpoint is disabled.
- The D1 database list was empty before and after this experiment. No database,
  schema application, import, or paid feature was created.

The user's explicit stop condition applies: password verification must work securely
on Workers Free. Review a secure authentication alternative before resuming staging.
Do not silently substitute a weaker verifier or begin the editor.

## Deferred actual-infrastructure verification

D1 schema/atomic edits/index plans/metering, resumable quota-aware import,
incremental publication, remembered sessions and login throttling on Workers,
future-set lifecycle on D1, actual D1 export/restore, and infrastructure failure
tests were **not performed** after this stop condition. No full or subset import
occurred. Previous SQLite/Node results remain local evidence only.

The prior estimate of roughly 260,000 indexed initialization writes is still a
planning estimate, not measured D1 import billing. If ordinary Free writes apply,
the complete import needs at least three daily allowances with safety margin;
actual import metering must be established before importing. Per-edit publication
must remain incremental, never a full 66,000–75,000-row snapshot per save.
Neither design was activated here. Public search remains client-side.

Remembered sessions remain designed for 90 days, regular sessions for an absolute
8-hour lifetime, with HttpOnly/Secure/SameSite cookies, hashed tokens, revocation,
and password-reset invalidation. These passed local tests, not deployed login tests.
Local portable JSON/CSV/SQL restore and public sanitization tests passed; no actual
D1 export capability is claimed by this checkpoint.

## Regression results and preservation

- `python tools/validate_wantlists.py`: 21 passed.
- `npm run test:foundation`: 34 Python + 15 Node tests passed.
- `npm test`: 36 passed.
- `npm run test:browser`: 16 desktop/mobile tests passed; its configured web server
  runs `npm run build` before preview, and that production build succeeded.
- Existing source/data/site/configuration files are unchanged. The Phase 3A public
  loader still uses the committed `data/wantlists.json`, independent of this Worker.
- Word source, raw import, Phase 2 normalization/corrections, reviewed baseline,
  and the existing backup archive were retained. No missing-card inference was added.

Only this report, the isolated probe source, and its non-sensitive runtime result
were added. No editor, production deployment, D1 migration, or Phase 3B.3 work began.
