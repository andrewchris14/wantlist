# Probe runner prepared — awaiting fresh screenshots

All local preparation is complete. The owner has approved the [probe-only diagnostic](READINESS_404_INVESTIGATION.md); **no Cloudflare operation occurred during this preparation**. The five-minute snapshot requirement remains unchanged. Old screenshots were not reused or assigned a new timestamp.

## Ready to execute after fresh evidence

`foundation/staging/readiness_runner.py` is a dedicated probe controller, not the six-invocation performance runner. It verifies the reviewed 1,492-byte probe source SHA-256 `34a1a8c3283104489bb0049bf10a3d202bd109e9e8bb132c9880eff70f22557b` and the original restored 13-module release/options against [the committed manifest](evidence/readiness-probe-release-manifest.json). A changed original release stops preflight; it is not adopted silently.

The dedicated `readiness_transport.py` rejects SQL and all application HTTP requests, Cookie use and oversized HTTP responses (64 KiB). Only the exact index URL is allowed. API metadata is fixed to the disposable identity. Schema/fixture checks are intentionally inapplicable to this standalone no-D1 module; the application guard's default still requires them for application testing.

The independent supervisor:

- Starts in a separate process/session before publication and must complete a health handshake before any upload/enablement.
- Publishes a heartbeat; a dead/unhealthy supervisor stops parent dispatch.
- Handles parent death, a stalled parent heartbeat or lease expiration using only bounded cleanup APIs.
- Serializes parent network dispatch with supervisor cleanup using a private lock. An enable request cannot race cleanup and leave the original application re-enabled after restoration.
- Preserves supervisor takeover/completion checkpoints; the parent cannot overwrite them or dispatch more requests afterward.
- Uses two disable attempts, verified shutdown before restoration, removal of the private key, and exact original modules/settings/binding verification. Full binding equality proves all four temporary bindings, including the public nonce, are removed. Cleanup gets ten reserved calls and remains possible after quota evidence expires.
- Reports incomplete shutdown/restoration rather than claiming success; keeps the no-D1 lease guard if disablement is unconfirmed. Supervisor failure before publication results in no deployment or enablement.

The controller executes at most two GETs, scheduled at +5 and +30 seconds after enable acknowledgment; there is no readiness retry loop. A marked first success skips the second. Slow responses that miss the second slot cause a stop, not a delayed extra request. Unexpected/ambiguous responses or a failed safety gate stop with cleanup.

Only two known 1042 results can offer one owner-browser comparison. The CLI immediately emits the exact public URL/nonce and cutoff; it waits **at most 60 seconds**, shortened further for screenshot freshness, authorization or lease expiry. The operator asks the owner immediately to open the supplied `view-source:` URL once (source view avoids normal page asset loading), never asks for a private header key, and supplies only validated harmless probe JSON (or `{"skip":true}`) in ignored `work/<session>/browser-result.json`. If no reply arrives, shutdown proceeds. The public body can establish a matching probe response; browser HTTP status/CPU are not independently verified from pasted JSON and are labeled accordingly.

A marker-bearing Codex response gets at most three CPU-analytics polls, 15 seconds apart; ≥9 ms or missing/ambiguous/error CPU stops. Both 1042 results may have no attributable target Worker CPU; that remains unknown. No routing outcome launches the performance test. Normal calls cap at 40, cleanup at ten, Codex GETs at two, optional owner GET at one. Ten-second socket timeout, thirty-second response deadline, ten-minute nonrenewable lease, 35-second lease margin and strict account-wide admission reserves are retained.

## Validation completed locally

**82 targeted Python tests passed**, including 30 new controller/transport/supervisor cases and the existing guard/adapter/evidence cases. Four Node probe cases passed. Coverage includes independent-process parent-death cleanup, handshake/health, stalled heartbeat/expiry, interruption/ambiguous upload or enable, request loss, fixed timing, missed slots, stale evidence during waiting, CPU stops, browser response/timeout/skip, wrong guard/DB, failed shutdown/restore/key removal, cleanup-lock exclusion, takeover preservation, nonce removal and SQL/application rejection.

No network is opened by import, `--help` or default invocation. Only the separately authorized `--run` path with complete current quota evidence constructs the transport. No tests create a real Cloudflare client; the independent-process test injects a fake cleanup transport.

## Exact next steps for the operator

The only owner input still needed is **fresh D1 Daily and Workers Requests today screenshots**, showing account-wide counters, database count/storage and the current UTC quota day, with capture time/timezone. The existing Workers Free confirmation and probe-only authorization are retained. The owner has reconfirmed no competing bulk jobs.

1. Interpret the new screenshots immediately, using conservative upper bounds for rounded values. Write the verified values/time into ignored `work/readiness-quota.json`; never refresh a timestamp without a new observation. Admission requires 3.1m read / 50k write / 1,000-request headroom, storage headroom and the current verified UTC window. The template contains **null** values, not old observations.
2. Record the existing owner authorization in ignored `work/readiness-authorization.json`, including the reviewed source digest and a short future authorization expiration. Template switches default false; the recorded approval permits setting the exact probe-only switches. No new authorization is needed for this wiring; any changed scope still requires review.
3. With the existing supported per-command network permission/proxy/TLS path, invoke immediately:

```sh
python -m foundation.staging.readiness_runner --run \
  --authorization work/readiness-authorization.json \
  --quota work/readiness-quota.json \
  --session work/readiness-session-NEW
```

No package rebuild, importer, migration, SQL or further broad local test phase is needed. The new private session path must not already exist. The controller performs all fresh remote identity/configuration checks before mutation and stops if any fails. Keep status updates while the command is running, and handle an optional browser event promptly rather than waiting on a long tool call.

Afterward review safe report/call counts/CPU/routing evidence and verified cleanup. Account-wide post-run reconciliation remains incomplete until fresh evidence establishes it; unknown analytics never becomes zero. Publish sanitized evidence only. Stop for owner review before any further test.
