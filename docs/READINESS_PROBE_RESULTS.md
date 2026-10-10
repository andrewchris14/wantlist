# Disposable readiness probe — October 10, 2026

The approved standalone no-D1 probe reached the disposable Worker successfully on its first scheduled request. This confirms routing at the time of this diagnostic; it does not establish the cause of the previous 1042 or prove the application release works.

## Admission and scope

Owner dashboard screenshots captured approximately 03:32 UTC showed October 10 daily D1 reads 4.36k, writes 3, Workers requests today 0, three databases and 35.03 MB storage. Conservative bounds were 4,370 reads, 3 writes, zero requests and 35,040,000 storage bytes. The retained Workers Free confirmation and owner statement that competing bulk jobs were absent were used. Freshness and all admission reserves passed. Remote preflight verified the fixed disposable Worker/D1 identity, isolated configuration and original release manifest before publication. No SQL, application HTTP request, migration, fixture reset or performance test was executed.

## Observed routing

Endpoint enable acknowledgment: 03:35:16.600 UTC. The only GET began at 03:35:21.600 UTC (+5 seconds), ending at 03:35:21.967 with HTTP 200, the exact expected harmless probe JSON, public nonce and both marker headers. URL: `https://wantlist-test-3c2-bc5991ba.andrewchris14.workers.dev/public/index?after=`. CF-Ray: `a482931a2a1fb103-LAX`; Server: `envoy`; Cache-Control: `no-store`. The second request and owner browser comparison were correctly skipped.

This confirms that the Codex request path could reach this standalone Worker with workers.dev enabled. The presence of Envoy alone does not prove interception caused the earlier error. Earlier immediate-enable propagation, different deployed code or transient intermediary behavior remain hypotheses; this result does not distinguish them conclusively.

## CPU and cleanup limitations

Three bounded analytics polls failed to establish attributable CPU. The controller stopped with `CPU_ANALYTICS_MISSING_OR_AMBIGUOUS`. Actual CPU remains unknown; missing analytics are not zero and no Free compatibility pass is claimed.

Cleanup verified endpoint disabled with previews disabled, and temporary private review-key removal. Original modules/settings restoration verification returned false. Full cleanup is **incomplete**: original module/settings equality and removal of the other temporary bindings are not established. The bounded cleanup routine attempted restoration after confirmed shutdown; its saved result does not distinguish a failed restore request from a subsequent equality mismatch or verification failure because exceptions were suppressed. No additional remote investigation or retry was attempted after this failed safety gate. A future separately reviewed cleanup-only check must identify the mismatch and verify full restoration before any further test. The ten-minute probe expiry is an additional guard, not a substitute for restoration verification.

Call counts: 15 control, 5 cleanup, one probe GET. SQL/application HTTP calls: zero. The probe contains no D1 access. Final account-wide usage reconciliation remains incomplete; initial screenshot headroom cannot establish final counters.

Sanitized machine evidence: [readiness-probe-20261010.json](evidence/readiness-probe-20261010.json). No credentials, private key, application data or rollback source are included. The endpoint remains disabled. Stop for owner review; do not run the performance protocol.
