"""OFFLINE planning/guard primitives. No Cloudflare client, HTTP or live runner.

Import and local tests cannot read credentials, enable an endpoint or access D1.
A future operator must separately obtain owner approval and wire these guards to
reviewed transport. Dashboard data is evidence, never execution authorization.
"""
from datetime import datetime, timezone, timedelta
from math import isfinite
from uuid import UUID

WORKER = 'wantlist-test-3c2-bc5991ba'
DATABASE = '7cf1e9a2-f0b7-4d6b-bded-f5a3315c028c'
STAGING_DATABASE = '81f241d4-b17d-4cd4-802d-177f982cc5e1'
ORIGIN = 'https://' + WORKER + '.andrewchris14.workers.dev'
READ_LIMIT, WRITE_LIMIT, WORKER_REQUEST_LIMIT = 5_000_000, 100_000, 100_000
# Reserve 2.5m reads for one unexpectedly expensive canary, without permitting
# repeated expensive work; normal review reserve 100k plus 400k outside margin.
POST_MIGRATION_READ_HEADROOM = 3_000_000
POST_MIGRATION_WRITE_HEADROOM = 40_000
MIGRATION_READ_RESERVE, MIGRATION_WRITE_RESERVE = 100_000, 10_000
MAX_HTTP_REQUESTS, MAX_CONTROL_CALLS, CLEANUP_CONTROL_CALLS = 8, 40, 10
MAX_DIAGNOSTIC_READS, MAX_DIAGNOSTIC_WRITES = 20_000, 5_000
CPU_STOP_MS = 9.0  # Conservative stop, 1ms below the 10ms Free CPU ceiling.
MEASURED_SEQUENCE = (
    ('owner_open_diagnostic', 'owner_open', True),
    ('owner_open_raw', 'owner_open', False),
    ('maximum_save_diagnostic', 'maximum_save', True),
    ('large_undo_diagnostic', 'large_undo', True),
    ('maximum_save_raw', 'maximum_save', False),
    ('large_undo_raw', 'large_undo', False),
)

class StopReview(ValueError):
    """Fixed safe code only: do not propagate remote bodies or credentials."""

def stop(code):
    raise StopReview(code)

def utc(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError, TypeError):
        stop('INVALID_QUOTA_TIME')
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        stop('QUOTA_TIME_MUST_BE_UTC')
    return result

def integer(value):
    return type(value) is int and value >= 0

def verify_quota(snapshot, now, require_migration_bound=True):
    """Strict account-wide upper bounds; missing/stale/billing data fails closed."""
    if snapshot.get('workers_free_confirmed') is not True or snapshot.get('d1_free_confirmed') is not True:
        stop('FREE_BILLING_UNCONFIRMED')
    if snapshot.get('account_wide') is not True or snapshot.get('period_verified') is not True:
        stop('ACCOUNT_WIDE_PERIOD_UNCONFIRMED')
    if snapshot.get('competing_bulk_jobs_paused') is not True:
        stop('COMPETING_ACCOUNT_BULK_JOBS_UNCONFIRMED')
    if snapshot.get('source') not in ('owner-dashboard', 'verified-account-analytics'):
        stop('QUOTA_SOURCE_UNCONFIRMED')
    observed, start, end = map(utc, (snapshot.get('observed_at_utc'), snapshot.get('period_start_utc'), snapshot.get('period_end_utc')))
    if not start <= observed <= now < end or end - start != timedelta(days=1):
        stop('WRONG_ACCOUNTING_PERIOD')
    if now - observed > timedelta(minutes=5):
        stop('STALE_ACCOUNT_WIDE_QUOTA')
    if end - now < timedelta(minutes=15):
        stop('ACCOUNTING_PERIOD_ABOUT_TO_CHANGE')
    values = [snapshot.get(k) for k in ('rows_read_upper_bound', 'rows_written_upper_bound', 'worker_requests_upper_bound')]
    if not all(integer(v) for v in values):
        stop('MISSING_OR_INVALID_QUOTA_BOUNDS')
    reads, writes, requests = values
    storage, count, disposable_size = (snapshot.get(k) for k in ('storage_bytes_upper_bound', 'database_count', 'disposable_database_bytes_upper_bound'))
    if not all(integer(v) for v in (storage, count, disposable_size)):
        stop('STORAGE_OR_DATABASE_CAPACITY_UNKNOWN')
    if not 1 <= count <= 10 or storage > 5_000_000_000 - 20_000_000 or disposable_size > 500_000_000 - 20_000_000:
        stop('INSUFFICIENT_STORAGE_CAPACITY')
    migration_pending = snapshot.get('migration_pending')
    if type(migration_pending) is not bool:
        stop('MIGRATION_STATUS_UNKNOWN')
    if require_migration_bound and migration_pending and snapshot.get('migration_scan_bound_confirmed') is not True:
        stop('MIGRATION_SCAN_BOUND_UNCONFIRMED')
    read_reserve = POST_MIGRATION_READ_HEADROOM + (MIGRATION_READ_RESERVE if migration_pending else 0)
    write_reserve = POST_MIGRATION_WRITE_HEADROOM + (MIGRATION_WRITE_RESERVE if migration_pending else 0)
    if READ_LIMIT - reads < read_reserve or WRITE_LIMIT - writes < write_reserve or WORKER_REQUEST_LIMIT - requests < 1000:
        stop('INSUFFICIENT_ACCOUNT_WIDE_HEADROOM')
    return {'remaining_reads': READ_LIMIT - reads, 'remaining_writes': WRITE_LIMIT - writes,
            'remaining_worker_requests': WORKER_REQUEST_LIMIT - requests}

def verify_resources(resources, require_application=True):
    if resources.get('worker_name') != WORKER or resources.get('database_name') != WORKER or resources.get('database_id') != DATABASE:
        stop('DISPOSABLE_IDENTITY_MISMATCH')
    if resources.get('custom_domains') != [] or resources.get('routes') != []:
        stop('UNEXPECTED_PUBLIC_ROUTE')
    if resources.get('endpoint_enabled') is not False or resources.get('previews_enabled') is not False:
        stop('ENDPOINT_NOT_CONFIRMED_DISABLED')
    bindings = resources.get('bindings', [])
    if not isinstance(bindings, list) or any(not isinstance(b, dict) for b in bindings):
        stop('INVALID_BINDING_METADATA')
    if len({b.get('name') for b in bindings}) != len(bindings):
        stop('DUPLICATE_BINDING_NAMES')
    if any(b.get('type') not in ('plain_text', 'secret_text', 'd1') for b in bindings):
        stop('UNEXPECTED_RESOURCE_BINDING')
    dbs = [b for b in bindings if b.get('type') == 'd1']
    if len(dbs) != 1 or dbs[0].get('name') != 'DB' or dbs[0].get('id') != DATABASE:
        stop('DISPOSABLE_D1_BINDING_MISMATCH')
    for name in ('ISOLATED_TEST_STORAGE', 'STAGING_ONLY', 'STAGING_EDITOR'):
        if not any(b.get('name') == name and b.get('type') == 'plain_text' and b.get('text') == 'true' for b in bindings):
            stop('ISOLATION_MARKER_MISSING')
    if any(b.get('name') in ('PHASE34_MIGRATION_DIGEST', 'PHASE35_MAINTENANCE_DIGEST') for b in bindings):
        stop('MAINTENANCE_CAPABILITY_PRESENT')
    if require_application and resources.get('reviewed_code_and_schema_verified') is not True:
        stop('REVIEWED_CODE_OR_SCHEMA_UNVERIFIED')
    if require_application and resources.get('synthetic_fixture_verified') is not True:
        stop('SYNTHETIC_FIXTURE_UNVERIFIED')
    # usage_model=standard and a successful HTTP response prove neither plan.
    if resources.get('explicit_cpu_limit_ms') not in (None, 10):
        stop('UNEXPECTED_CPU_OVERRIDE')
    return True

def verify_review_release(resources, now):
    """Verify the disabled post-release configuration BEFORE enabling its URL."""
    verify_resources(resources)
    bindings = {b['name']: b for b in resources['bindings']}
    for name in ('MINIMAL_FREE_REVIEW', 'STAGING_METRICS'):
        if bindings.get(name, {}).get('type') != 'plain_text' or bindings[name].get('text') != 'true':
            stop('MINIMAL_REVIEW_GUARD_MISSING')
    if bindings.get('FREE_HTTP_REVIEW_KEY', {}).get('type') != 'secret_text':
        stop('TEMPORARY_REVIEW_KEY_UNVERIFIED')
    expiry = bindings.get('MINIMAL_FREE_REVIEW_UNTIL', {})
    if expiry.get('type') != 'plain_text' or not now < utc(expiry.get('text')) <= now + timedelta(minutes=10):
        stop('MINIMAL_REVIEW_LEASE_INVALID')
    if resources.get('main_module') != 'free-review-wrapper.mjs' or resources.get('release_module_digests_verified') is not True:
        stop('GUARDED_REVIEW_MODULES_UNVERIFIED')
    return True

def admit(snapshot, resources, now, owner_authorized=False):
    if owner_authorized is not True:
        stop('OWNER_REMOTE_AUTHORIZATION_REQUIRED')
    result = verify_quota(snapshot, now)
    verify_resources(resources)
    return result

FIXTURE_RECORD = 'synthetic-3c5-1-0000'
FIXTURE_GROUP = FIXTURE_RECORD + '-group'

def maximum_payload(owner, request_id):
    """In-memory synthetic-only draft; never choose historical/practice records."""
    try:
        if str(UUID(request_id)) != request_id:
            stop('INVALID_REQUEST_ID')
    except (ValueError, TypeError, AttributeError):
        stop('INVALID_REQUEST_ID')
    if owner.get('id') != FIXTURE_RECORD or owner.get('list_type') != 'want_list' or owner.get('deleted_at') is not None or not integer(owner.get('revision')) or owner['revision'] < 1:
        stop('WRONG_SYNTHETIC_RECORD')
    groups = owner.get('groups')
    if not isinstance(groups, list) or len(groups) != 1 or groups[0].get('id') != FIXTURE_GROUP or groups[0].get('list_type') != 'want_list':
        stop('WRONG_SYNTHETIC_GROUP')
    entries = groups[0].get('entries', [])
    if not isinstance(entries, list):
        stop('INVALID_SYNTHETIC_INVENTORY')
    live = [i for i in entries if i.get('deleted_at') is None]
    if len(live) != 526 or len({i.get('id') for i in live}) != 526 or any(i.get('state') != 'wanted' or i.get('actionable') != 1 or i.get('group_id') != FIXTURE_GROUP for i in live):
        stop('SYNTHETIC_BASELINE_MISMATCH')
    if {i.get('id') for i in live} != {FIXTURE_RECORD + '-item-' + str(n) for n in range(526)}:
        stop('NON_BASELINE_SYNTHETIC_ITEMS')
    return {'op': 'edit_session', 'request_id': request_id, 'record_id': FIXTURE_RECORD,
            'revision': owner['revision'], 'metadata': {'notes': ['Synthetic maximum combined Save']},
            'changes': [{'id': i['id'], 'state': 'pending', 'removed': False} for i in live[:500]],
            'additions': [{'group_id': FIXTURE_GROUP, 'field_key': 'items', 'state': 'wanted',
                           'value': ('Synthetic maximum ' + str(n).zfill(3) + ' ' + 'X' * 500)[:500]} for n in range(500)]}

def cpu_observation(sample, rows):
    """Reject aggregate/ambiguous or missing analytics; never guess actual CPU.

    Accept one singleton bucket in the request's start/end second, with no other
    requests/errors in that interval. Adaptive quantiles remain sampled evidence.
    """
    a, b = utc(sample.get('started')), utc(sample.get('ended'))
    if b < a or b - a > timedelta(seconds=45):
        stop('INVALID_HTTP_INTERVAL')
    lower, upper = a.replace(microsecond=0), b.replace(microsecond=0)
    matches = [r for r in rows if lower <= utc(r.get('dimensions', {}).get('datetime')) <= upper]
    if len(matches) != 1 or matches[0].get('sum', {}).get('requests') != 1:
        stop('CPU_ANALYTICS_MISSING_OR_AMBIGUOUS')
    row = matches[0]
    if row.get('sum', {}).get('errors') != 0 or row.get('dimensions', {}).get('status') != 'success':
        stop('WORKER_ERROR_OBSERVED')
    microseconds = row.get('quantiles', {}).get('cpuTimeP50')
    if type(microseconds) not in (int, float) or not isfinite(microseconds) or microseconds < 0:
        stop('CPU_MEASUREMENT_INVALID')
    return microseconds / 1000

class CallBudget:
    """Reserve cleanup calls separately; transport must call this before dispatch."""
    def __init__(self):
        self.counts = {'http': 0, 'control': 0, 'cleanup': 0}

    def before(self, kind):
        limits = {'http': MAX_HTTP_REQUESTS, 'control': MAX_CONTROL_CALLS, 'cleanup': CLEANUP_CONTROL_CALLS}
        if kind not in limits:
            stop('UNAPPROVED_CALL_KIND')
        if self.counts[kind] >= limits[kind]:
            stop('CALL_BUDGET_EXHAUSTED')
        self.counts[kind] += 1


class Measurements:
    """Offline acceptance ledger; no transport/retries, and failures stay latched."""
    def __init__(self):
        self.accepted = []
        self.diagnostic_reads = self.diagnostic_writes = 0
        self.projected_raw_reads = self.projected_raw_writes = 0
        self.diagnostic_costs = {}
        self.stopped = False
        self.failed_code = None

    def accept(self, sample, analytics):
        if self.stopped:
            stop('REVIEW_ALREADY_STOPPED')
        try:
            if len(self.accepted) >= len(MEASURED_SEQUENCE):
                stop('MEASURED_REQUEST_BUDGET_EXHAUSTED')
            label, operation, diagnostic = MEASURED_SEQUENCE[len(self.accepted)]
            if sample.get('label') != label or sample.get('diagnostic') is not diagnostic:
                stop('UNEXPECTED_REQUEST_SEQUENCE')
            if sample.get('status') != 200:
                stop('HTTP_OR_ROUTING_FAILURE')
            if diagnostic:
                reads, writes = sample.get('rows_read'), sample.get('rows_written')
                if sample.get('d1_complete') is not True or not integer(reads) or not integer(writes):
                    stop('D1_DIAGNOSTICS_MISSING')
                self.diagnostic_reads += reads
                self.diagnostic_writes += writes
                self.diagnostic_costs[operation] = (reads, writes)
                if reads > 12000 or writes > 3500 or self.diagnostic_reads > MAX_DIAGNOSTIC_READS or self.diagnostic_writes > MAX_DIAGNOSTIC_WRITES:
                    stop('DIAGNOSTIC_D1_STOP')
            else:
                reads, writes = self.diagnostic_costs[operation]
                # Unknown raw billed costs are explicitly projections, not data.
                self.projected_raw_reads += 2 * reads
                self.projected_raw_writes += 2 * writes
            cpu_ms = cpu_observation(sample, analytics)
            if cpu_ms >= CPU_STOP_MS:
                stop('CPU_SAFETY_STOP')
            observation = {'label': label, 'diagnostic': diagnostic, 'cpu_ms': cpu_ms}
            if diagnostic:
                observation.update(rows_read=reads, rows_written=writes)
            self.accepted.append(observation)
            return observation
        except StopReview as error:
            self.stopped = True
            self.failed_code = str(error)
            raise

def protected_scope(action, disable, verify_disabled, restore, remove_key, verify_restored, verified=False):
    """Callback seam for fault-injection tests, NOT a connected execution runner.

    Arm before enable. Even enable timeout/action exceptions enter cleanup.
    Disable confirmation must precede restoring modules; retain expiring guard
    if control-plane disable cannot be confirmed. All callback errors are redacted.
    The operator must also bind this scope to graceful signals; power loss cannot
    be handled by finally. A short Worker lease closes that SQL-access gap.
    """
    if verified is not True:
        stop('RESOURCES_NOT_VERIFIED')
    report = {'action_completed': False, 'disabled_verified': False,
              'modules_restored': False, 'temporary_key_removed': False,
              'restoration_verified': False, 'cleanup_complete': False}
    try:
        action()
        report['action_completed'] = True
    except Exception:
        report['action_stopped'] = True
    finally:
        for _ in range(2):
            try:
                disable()
                report['disabled_verified'] = verify_disabled() is True
            except Exception:
                pass
            if report['disabled_verified']:
                break
        if report['disabled_verified']:
            try:
                restore()
                report['modules_restored'] = True
            except Exception:
                pass
        try:
            remove_key()
            report['temporary_key_removed'] = True
        except Exception:
            pass
        if report['disabled_verified'] and report['modules_restored'] and report['temporary_key_removed']:
            try:
                report['restoration_verified'] = verify_restored() is True
            except Exception:
                pass
        report['cleanup_complete'] = report['disabled_verified'] and report['restoration_verified']
    return report
