"""Disposable LOCAL owner-operation reference, not a remote API or editor.

actor is a trusted local test/operator argument. A future API MUST derive owner
authorization from a validated session, never from a client-provided actor.
"""
import json
import uuid

from .storage import dumps, now


def authorize(actor):
    if actor != 'owner':
        raise PermissionError('Owner authorization required')


def validate_metadata(metadata, required_name=False):
    allowed = {'year', 'brand', 'set_name', 'category', 'section', 'notes', 'prefixes', 'uncertainty', 'set_size'}
    if not isinstance(metadata, dict) or set(metadata) - allowed:
        raise ValueError('Only live editable metadata may change; no fabricated provenance')
    for key in ('year', 'brand', 'set_name', 'category', 'section'):
        if key in metadata and metadata[key] is not None and not isinstance(metadata[key], str):
            raise ValueError(f'{key} must be text or unknown')
    if required_name or 'set_name' in metadata:
        if not isinstance(metadata.get('set_name'), str) or not metadata['set_name'].strip():
            raise ValueError('Set name is required')
    for key in ('notes', 'prefixes', 'uncertainty'):
        if key in metadata and (not isinstance(metadata[key], list) or any(not isinstance(v, str) for v in metadata[key])):
            raise ValueError(f'{key} must contain text entries')
    if metadata.get('set_size') is not None and (type(metadata['set_size']) is not int or metadata['set_size'] < 1):
        raise ValueError('Set size must be a positive integer or unknown')


def bump(db, record_id, revision):
    if db.execute('UPDATE records SET revision=revision+1,updated_at=? WHERE id=? AND revision=? AND deleted_at IS NULL',
                  (now(), record_id, revision)).rowcount != 1:
        raise ValueError('Revision conflict or deleted record')


def history(db, rid, action, before, after, item_id=None):
    db.execute('INSERT INTO change_history VALUES (?,?,?,?,?,?,?,?)',
               (str(uuid.uuid4()), rid, item_id, 'owner', action, dumps(before), dumps(after), now()))


def get_record(db, rid, include_deleted=False):
    row = db.execute('SELECT * FROM records WHERE id=?', (rid,)).fetchone()
    if not row or (row['deleted_at'] and not include_deleted):
        return None
    record = json.loads(row['content_json'])
    record.update(list_type=row['list_type'], revision=row['revision'], deleted_at=row['deleted_at'], groups=[])
    for group in db.execute('SELECT * FROM record_groups WHERE record_id=? ORDER BY kind,position', (rid,)):
        body = dict(group)
        body['entries'] = [dict(i) for i in db.execute('SELECT * FROM items WHERE group_id=? ORDER BY field_key,position', (group['id'],))
                           if include_deleted or not i['deleted_at']]
        record['groups'].append(body)
    return record


def record_summaries(db):
    # Fetch once, then owner set-search runs in browser memory, like public search.
    return [dict(r) for r in db.execute("SELECT id,revision,list_type,json_extract(content_json,'$.year') AS year,json_extract(content_json,'$.brand') AS brand,json_extract(content_json,'$.set_name') AS set_name,json_extract(content_json,'$.category') AS category FROM records WHERE deleted_at IS NULL ORDER BY id")]


def find_item(db, rid, value):
    return [dict(r) for r in db.execute('SELECT i.*,g.record_id FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=? AND i.value=? AND i.deleted_at IS NULL', (rid, value))]


def recent_changes(db, rid=None, limit=20):
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError('History page size must be 1–100')
    if rid is None:
        return [dict(r) for r in db.execute('SELECT * FROM change_history ORDER BY created_at DESC,id DESC LIMIT ?', (limit,))]
    return [dict(r) for r in db.execute('SELECT * FROM change_history WHERE record_id=? ORDER BY created_at DESC,id DESC LIMIT ?', (rid, limit))]


def _group(db, rid, state):
    mode = {'wanted': 'want_list', 'owned': 'have_list'}[state]
    groups = db.execute('SELECT * FROM record_groups WHERE record_id=? ORDER BY kind,position', (rid,)).fetchall()
    group = next((g for g in groups if g['list_type'] == mode), None)
    if group:
        return group['id']
    pos = max((g['position'] for g in groups if g['kind'] == 'mixed'), default=-1) + 1
    gid = f'owner-group-{uuid.uuid4()}'
    db.execute('INSERT INTO record_groups VALUES (?,?,?,?,?,?,?)',
               (gid, rid, 'mixed', pos, mode, dumps({'list_type': mode}), dumps(['card_numbers', 'items', 'card_ranges'])))
    return gid


def _insert(db, gid, values, state, field_key):
    if state not in ('wanted', 'owned') or field_key not in ('card_numbers', 'items'):
        raise ValueError('New values require explicit numbered/named identity and Wanted/Owned choice')
    if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in values):
        raise ValueError('Enter nonempty text identifiers (maximum 500 characters)')
    values = [v.strip() for v in values]
    if len(values) != len(set(values)):
        raise ValueError('Duplicate entries in this operation')
    pos = db.execute('SELECT COALESCE(MAX(position),-1) FROM items WHERE group_id=? AND field_key=?', (gid, field_key)).fetchone()[0] + 1
    # Bounded indexed duplicate probes, not one round-trip per card. Keep
    # bindings conservative while the actual D1 binding limits remain a gate.
    for offset in range(0, len(values), 20):
        chunk = values[offset:offset + 20]
        if db.execute(f"SELECT id FROM items WHERE group_id=? AND value IN ({','.join('?' for _ in chunk)}) AND deleted_at IS NULL LIMIT 1", (gid, *chunk)).fetchone():
            raise ValueError('Item already exists in this group')
    created, rows = [], []
    for value in values:
        iid = f'owner-item-{uuid.uuid4()}'
        rows.append((iid, gid, field_key, pos, value, state))
        created.append({'id': iid, 'value': value, 'state': state, 'field_key': field_key})
        pos += 1
    for offset in range(0, len(rows), 10):
        chunk = rows[offset:offset + 10]
        db.execute('INSERT INTO items VALUES ' + ','.join('(?,?,?,?,?,?,1,NULL,NULL,NULL,NULL)' for _ in chunk),
                   [value for row in chunk for value in row])
    return created


def create_record(db, metadata, *, wanted=None, owned=None, wanted_names=None, owned_names=None,
                  list_type='want_list', actor):
    authorize(actor)
    validate_metadata(metadata, required_name=True)
    if list_type == 'complete' and (wanted or wanted_names):
        raise ValueError('Complete records cannot have wanted cards')
    rid, stamp = f'owner-record-{uuid.uuid4()}', now()
    content = {'id': rid, 'creation_origin': 'owner', **metadata}
    content.setdefault('notes', []); content.setdefault('uncertainty', []); content.setdefault('prefixes', [])
    with db:
        db.execute('INSERT INTO records VALUES (?,NULL,?,?,1,?,?,NULL)', (rid, list_type, dumps(content), stamp, stamp))
        gid = f'owner-group-{uuid.uuid4()}'
        mode = 'have_list' if list_type == 'have_list' else 'want_list'
        db.execute('INSERT INTO record_groups VALUES (?,?,?,0,?,?,?)',
                   (gid, rid, 'primary', mode, '{}', dumps(['card_numbers', 'items', 'card_ranges'])))
        added = []
        for values, state, field in ((wanted, 'wanted', 'card_numbers'), (owned, 'owned', 'card_numbers'),
                                     (wanted_names, 'wanted', 'items'), (owned_names, 'owned', 'items')):
            if values:
                added += _insert(db, _group(db, rid, state), values, state, field)
        history(db, rid, 'create_record', {}, {'metadata': content, 'list_type': list_type, 'items': added})
    return rid


def add_cards(db, rid, values, *, state='wanted', field_key='card_numbers', group_id=None, expected_revision, actor):
    authorize(actor)
    if state not in ('wanted', 'owned'):
        raise ValueError('Add as Wanted/Owned, then use the explicit Pending transition')
    with db:
        row = db.execute('SELECT list_type FROM records WHERE id=? AND deleted_at IS NULL', (rid,)).fetchone()
        if not row:
            raise ValueError('Record not found')
        if row[0] == 'complete' and state == 'wanted':
            raise ValueError('Unmark Complete before adding wanted cards')
        bump(db, rid, expected_revision)
        gid = group_id or _group(db, rid, state)
        group = db.execute('SELECT record_id,list_type FROM record_groups WHERE id=?', (gid,)).fetchone()
        if not group or group['record_id'] != rid or group['list_type'] != {'wanted': 'want_list', 'owned': 'have_list'}.get(state):
            raise ValueError('Group ownership/state does not match')
        added = _insert(db, gid, values, state, field_key)
        history(db, rid, 'add_cards', {}, {'items': added})
    return added


def add_group(db, rid, label, *, list_type, expected_revision, actor):
    authorize(actor)
    if list_type not in ('want_list', 'have_list') or not isinstance(label, str) or not label.strip():
        raise ValueError('A labeled WANT/HAVE sublist is required')
    with db:
        bump(db, rid, expected_revision)
        pos = db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM record_groups WHERE record_id=? AND kind='sublist'", (rid,)).fetchone()[0]
        gid = f'owner-group-{uuid.uuid4()}'
        db.execute('INSERT INTO record_groups VALUES (?,?,?,?,?,?,?)',
                   (gid, rid, 'sublist', pos, list_type, dumps({'label': label, 'list_type': list_type}), dumps(['card_numbers', 'items', 'card_ranges'])))
        history(db, rid, 'add_group', {}, {'id': gid, 'label': label, 'list_type': list_type})
    return gid


def edit_record(db, rid, changes, *, list_type=None, expected_revision, actor):
    authorize(actor)
    validate_metadata(changes)
    with db:
        row = db.execute('SELECT * FROM records WHERE id=? AND deleted_at IS NULL', (rid,)).fetchone()
        if not row:
            raise ValueError('Record not found')
        mode = list_type or row['list_type']
        if mode == 'complete' and db.execute("SELECT i.id FROM record_groups g JOIN items i ON i.group_id=g.id WHERE g.record_id=? AND i.deleted_at IS NULL AND (i.state IN ('wanted','pending') OR (i.actionable=0 AND g.list_type='want_list')) LIMIT 1", (rid,)).fetchone():
            raise ValueError('Resolve wanted/pending items before marking Complete')
        content = json.loads(row['content_json'])
        before = {'list_type': row['list_type'], 'fields': {k: content.get(k) for k in changes}}
        content.update(changes)
        if db.execute('UPDATE records SET content_json=?,list_type=?,revision=revision+1,updated_at=? WHERE id=? AND revision=? AND deleted_at IS NULL',
                      (dumps(content), mode, now(), rid, expected_revision)).rowcount != 1:
            raise ValueError('Revision conflict or deleted record')
        history(db, rid, 'edit_record', before, {'list_type': mode, 'fields': changes})


def delete_or_restore_item(db, iid, *, restore=False, expected_revision, actor):
    authorize(actor)
    with db:
        row = db.execute('SELECT i.*,g.record_id FROM items i JOIN record_groups g ON g.id=i.group_id WHERE i.id=?', (iid,)).fetchone()
        if not row or bool(row['deleted_at']) != restore:
            raise ValueError('Item not found or wrong deletion state')
        if restore:
            if db.execute('SELECT id FROM items WHERE group_id=? AND value=? AND deleted_at IS NULL AND id != ? LIMIT 1', (row['group_id'], row['value'], iid)).fetchone():
                raise ValueError('An active duplicate already exists')
            mode = db.execute('SELECT list_type FROM records WHERE id=?', (row['record_id'],)).fetchone()[0]
            if mode == 'complete' and row['state'] in ('wanted', 'pending'):
                raise ValueError('Unmark Complete before restoring a needed item')
        bump(db, row['record_id'], expected_revision)
        db.execute('UPDATE items SET deleted_at=? WHERE id=?', (None if restore else now(), iid))
        after = dict(db.execute('SELECT * FROM items WHERE id=?', (iid,)).fetchone())
        history(db, row['record_id'], 'restore_item' if restore else 'soft_delete_item', dict(row), after, iid)
