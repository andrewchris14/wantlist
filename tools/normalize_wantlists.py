"""Rebuild Phase 2 from immutable DOCX; no dependencies, network, or checklists.

Explicit ranges remain expressions. HAVE payloads are never complemented.
Every nonempty source line is accounted for in the source ledger.
"""
import json
import re
from collections import Counter
from pathlib import Path

from import_docx import ROOT, extract, write_import
from source_corrections import DECISIONS, correct

LIST_TYPES = ('want_list', 'have_list', 'complete', 'uncertain', 'needs_review')
YEAR = re.compile(r'^(?:18|19|20)\d{2}(?:\s*[-–]\s*(?:\d{2,4}|\?))?\??')
YEAR_ANY = re.compile(r'\b(?:18|19|20)\d{2}(?:\s*[-–]\s*(?:\d{2,4}|\?))?\??')
DESIGNATION = re.compile(r'\b(HAVE|WANT)\s*(?:lists?)?\b', re.I)
BRANDS = sorted(['Unknown Manufacturer', 'John Player and Sons', 'Godfrey Phillips',
                 'Imperial Tobacco Company of Canada', 'W.D. and H.O. Wills',
                 'Upper Deck', 'Burger King', 'Grand Studio', 'Brooke Bond',
                 'Baseball Cards Magazine', 'Stadium Club', 'Historic Autographs',
                 'National Chicle', 'TCMA', 'Topps', 'Bowman', 'Fleer', 'Donruss',
                 'OPC', 'Kelloggs', "Kellogg's", 'Panini', 'Leaf', 'Carreras',
                 'Gallaher', 'Wills', 'Ardath', 'Linnett', 'Towne Club', 'Play-Rite',
                 'Ritz/Oreo', 'Just', 'Post', 'Pacific', 'Score', 'Sportflics',
                 'Churchman', "Ogden's", 'Park Drive', 'Cavanders', "Wright's",
                 'Nicolas Sarony', 'Goudey', 'Skybox', 'SP', 'S/P'], key=len, reverse=True)


def clean(s):
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()


def separator(s):
    """Ignore colons in title notes, prefixes, and URLs."""
    depth = 0
    for i, c in enumerate(s):
        if c == '(':
            depth += 1
        elif c == ')':
            depth = max(0, depth - 1)
        elif c == ':' and depth == 0:
            return i
    # Source 1951 Bowman has a missing closing parenthesis in the header.
    m = re.search(r'could use upgrade\s*:\s*(?=\d)', s, re.I)
    return m.end() - 1 if m else None


def heading_designations(title):
    """Designations outside title parentheses; never remove prose 'have'."""
    return [m for m in DESIGNATION.finditer(title)
            if title[:m.start()].count('(') <= title[:m.start()].count(')')
            and (m.group().strip().isupper() or 'list' in m.group().lower())]


def without_designations(title):
    for m in reversed(heading_designations(title)):
        title = title[:m.start()] + title[m.end():]
    return clean(title)


def comma_parts(s):
    out, part, depth = [], [], 0
    for c in s:
        depth += (c == '(') - (c == ')' and depth > 0)
        if c == ',' and depth == 0:
            if clean(''.join(part)):
                out.append(clean(''.join(part)))
            part = []
        else:
            part.append(c)
    if clean(''.join(part)):
        out.append(clean(''.join(part)))
    return out


def parse_items(payload, prefixes=()):
    """Conservative tokenization: do not turn note digits into card numbers."""
    numbers, names, ranges, notes = [], [], [], []
    notes.extend(re.findall(r'\(([^()]*)\)', payload))
    # Remove only an explicit request verb; keep all original wording elsewhere.
    payload = re.sub(r'^(?:Need|Missing)\s+(?=\d)', '', payload, flags=re.I)
    for part in comma_parts(payload):
        # Card numbers/IDs with optional parenthesized annotations, including
        # panels (9/10), suffixes (46A), and prefixes (MB-14).
        rest = part
        consumed = False
        while rest:
            m = re.match(r'(?P<id>(?:[A-Za-z]+-?)?\d+(?:[A-Za-z]+|(?:[/\-]\d+[A-Za-z]*)+)?)(?=$|[\s.(])', rest)
            if not m:
                break
            token = m['id']
            # A leading year in a prose phrase is not a card ID.
            tail = rest[m.end():].lstrip()
            if not consumed and len(token) == 4 and token.isdigit() and tail and tail[0].isalpha():
                break
            if re.fullmatch(r'\d+-\d+', token):
                ranges.append(token)
            else:
                numbers.append(token)
            consumed = True
            rest = tail
            if rest.startswith('('):
                end = rest.find(')')
                if end >= 0:
                    rest = rest[end + 1:].lstrip()
            rest = rest.lstrip('. ')
        if rest:
            if (prefixes and re.fullmatch(r'[A-Za-z]+(?:\s+[A-Za-z]+)*', rest)) or re.fullmatch(r'[A-Z]{1,3}(?:\s+[A-Z]{1,3})*', rest):
                numbers.extend(rest.split())
            elif consumed:
                notes.append(rest)
            elif not re.fullmatch(r'(?:none|none of these|complete|comp)[.!\s]*', rest, re.I):
                names.append(rest)
    return {'card_numbers': numbers, 'items': names, 'card_ranges': ranges,
            'notes': list(dict.fromkeys(notes))}


def category(title, section):
    t = title.lower()
    if section == 'bobbleheads': return 'bobbleheads'
    if section == 'autographs': return 'autographs'
    if section == 'player_interests': return 'player_interests'
    if section in ('vintage_tobacco', 'vintage_non_sport'): return 'tobacco_and_candy_cards'
    if section == 'football' or re.search(r'football|packers', t): return 'football_cards'
    for word, kind in [('postcard', 'postcards'), ('matchbook', 'matchbooks'),
                       ('playing card', 'playing_cards'), ('poster', 'posters'),
                       ('disc', 'discs'), ('disk', 'discs'), ('patch', 'patches'),
                       ('photo', 'photos'), ('stamp', 'stamps'), ('coin', 'coins'),
                       ('autograph', 'autograph_cards')]:
        if word in t: return kind
    # Match whole words/phrases, not fragments such as flags in Flagship,
    # jets in objects, or TV inside another word. Preserve meaningful plurals.
    if re.search(r'\b(?:star wars|star trek|superman|dukes of|hazzard|elvis|moonraker|rocky|wacky|kiss|bionic|jaws|battlestar|casper|yule|idiot|crazy|valentines?|fabian|zorro|westerns?|dogs|robin hood|crockett|presidents?|frontier|tv|movies?|lone ranger|hopalong|freedom|wild west|horrors|sky birds|indian gum|famous people|olympia|peppers|missiles|planes|jets|flags|the andy griffith|non-sport|bull durham)\b', t):
        return 'non_sport_cards'
    return 'baseball_cards' if section != 'other_collectibles' else 'other_collectibles'


def new_record(title, payload, refs, originals, section, inherited='want_list', correction_ids=()):
    explicit = heading_designations(title)
    mode = (explicit[-1][1].lower() + '_list') if explicit else inherited
    body_mode = re.match(r'^(HAVE|WANT) list\s*:\s*', payload, re.I)
    if body_mode: mode = body_mode[1].lower() + '_list'
    elif re.match(r'^Have\b', payload, re.I): mode = 'have_list'
    title_clean = without_designations(title).rstrip(': ')
    year_match = YEAR_ANY.search(title_clean)
    year = year_match.group() if year_match else None
    brand_title = YEAR.sub('', title_clean).lstrip(' (?)')
    brand = next((b for b in BRANDS if brand_title.lower().startswith(b.lower())), None)
    prefixes = re.findall(r'\b([A-Za-z][A-Za-z0-9]*-)\s*(?=\))', title)
    size = re.search(r'\((?:out of |of |set of )?(\d+)\)', title, re.I)
    primary_payload = payload
    if body_mode: primary_payload = payload[body_mode.end():]
    elif re.match(r'^Have\b', payload, re.I): primary_payload = re.sub(r'^Have\s+', '', payload, flags=re.I)
    mixed = []
    # Keep source-stated possible missing items separate from owned items.
    # Never calculate a missing-card complement.
    secondary = re.search(r'\(?\b(?:possible|likely) missing(?: \(could be more\))?\s*:', payload, re.I)
    if secondary:
        primary_payload = payload[:secondary.start()].rstrip(' .')
        mixed.append({'list_type': 'uncertain', 'source_list_type': 'want_list',
                      'description': payload[secondary.start():],
                      **parse_items(payload[secondary.end():].rstrip(') .'), prefixes)})
    inline = re.search(r'\b(Series \d+|High numbers?|Short\s*prints?|SP|Cardboard Cutout)\s+(HAVE|WANT)(?: list)?\s*:', primary_payload, re.I)
    if inline:
        mixed.append({'list_type': inline[2].lower() + '_list', 'label': inline[1],
                      'description': primary_payload[inline.start():],
                      **parse_items(primary_payload[inline.end():], prefixes)})
        primary_payload = primary_payload[:inline.start()].strip()
    sublists = []
    label_pattern = re.compile(r'\b(Short\s*prints?(?: \([^)]*\))?|CL|AL|NL)\s*:', re.I)
    labels = list(label_pattern.finditer(primary_payload))
    if labels:
        for index, label in enumerate(labels):
            end = labels[index + 1].start() if index + 1 < len(labels) else len(primary_payload)
            body = primary_payload[label.end():end].strip()
            sublists.append({'label': label[1], 'list_type': mode,
                             'description': body, **parse_items(body, prefixes)})
        primary_payload = primary_payload[:labels[0].start()].strip()
    parsed = parse_items(primary_payload, prefixes)
    uncertainty = []
    if re.search(r'believ|likely|purported|unconfirmed|possible missing|availability is unknown|complete\?', payload, re.I) or re.search(r'possibly complete|unconfirmed wantlist', title, re.I):
        uncertainty.append(payload)
    review = []
    list_type = mode
    positive_payload = re.sub(r'not seeking[^)]*', '', payload, flags=re.I)
    partial = bool(re.search(r'except|missing|seeking|need|shortprints', positive_payload, re.I))
    if uncertainty:
        list_type = 'uncertain'
    elif re.match(r'(?:boxed deck set |base set |all listed are )?(?:complete|comp)\b', payload, re.I) and not partial:
        list_type = 'complete'
    elif re.match(r'Missing\b', payload, re.I):
        list_type = 'want_list'
    if list_type == 'complete':
        parsed['card_numbers'] = []; parsed['items'] = []; parsed['card_ranges'] = []
        parsed['notes'].append(payload)
    elif partial and re.match(r'(?:boxed deck set |base set )?complete\b', payload, re.I):
        mixed.append({'list_type': 'complete', 'description': payload})
        list_type = 'want_list'
    # Parenthetical owned lists are separate from the primary wanted items.
    for m in re.finditer(r'\(Have\s+([^)]*)\)', payload, re.I):
        mixed.append({'list_type': 'have_list', **parse_items(m[1]), 'description': m.group()})
    if list_type == 'complete' and any(g['list_type'] == 'want_list' for g in mixed + sublists):
        list_type = 'want_list'
        mixed.insert(0, {'list_type': 'complete', 'description': primary_payload})
    if '5' in correction_ids:
        list_type = 'have_list'
        parsed = {'card_numbers': [], 'items': ['One example (Foul Strike|Ball)'],
                  'card_ranges': [], 'notes': [payload]}
    if '17' in correction_ids:
        parsed['items'] = ['Blue Border Griffey']
        mixed.append({'list_type': 'have_list', 'card_numbers': [],
                      'items': ['Red Border Griffey'], 'card_ranges': [],
                      'description': 'User-confirmed owned variant.'})
    suspicious = [n for n in parsed['card_numbers'] if n.isdigit() and len(n) >= 5]
    if suspicious:
        review.append('Unresolved joined-number token(s): ' + ', '.join(suspicious))
    if not payload.strip():
        review.append('Entry has no item list or completion/ownership statement.')
    if review:
        list_type = 'needs_review'
    return {'id': f"p{refs[0]['paragraph']:04d}-l{refs[0]['line']:03d}",
            'year': year, 'brand': brand, 'set_name': title_clean,
            'category': category(title_clean, section), 'section': section,
            'list_type': list_type, 'source_list_type': mode,
            **parsed, 'prefixes': prefixes, 'set_size': int(size[1]) if size else None,
            'uncertainty': uncertainty, 'mixed_lists': mixed, 'sublists': sublists,
            'source_refs': refs, 'source_wording': originals,
            'normalized_wording': clean(title + ': ' + payload),
            'payload': payload, 'corrections': list(correction_ids),
            'review_status': 'needs_review' if review else 'resolved' if correction_ids else 'accepted',
            'review_reasons': review}


def build(raw):
    records, ledger, context_notes = [], [], []
    section, group, last = 'baseball', None, None
    aggregate = None
    for p in raw['paragraphs']:
        for line_no, original in enumerate(p['text'].split('\n'), 1):
            if not original.strip(): continue
            ref = {'paragraph': p['paragraph'], 'line': line_no}
            s, corrections = correct(original)
            s = clean(s)
            # A quote in place of the colon after an explicit HAVE/WANT list
            # is a mechanical separator repair, not a checklist decision.
            s = re.sub(r'\b((?:HAVE|WANT) list)"\s*(?=\d)', r'\1: ', s, flags=re.I)
            entry = {'source_ref': ref, 'text': original, 'record_ids': [], 'role': None}
            ledger.append(entry)

            def metadata(role='context'):
                entry['role'] = role
                context_notes.append({'source_ref': ref, 'text': original, 'section': section})

            # Major document sections, identified by wording rather than offsets.
            transitions = {
                'Other stuff:': 'other_collectibles',
                'Vintage Tobacco Sets Featuring Actors and Actresses:': 'vintage_tobacco',
                'Other Vintage Non-Sport (or at least non-baseball) Cigarette or Candy Cards:': 'vintage_non_sport',
                'FOOTBALL WANTLIST (work in progress)': 'football',
                'UV Wantlist': 'baseball', 'Unknown Years:': 'unknown_years',
                'Brewers Bobblehead Wantlist': 'bobbleheads',
                'Milwaukee Baseball 8x10 Autographs': 'autographs',
                'Eau Claire Players': 'player_interests',
            }
            if s in transitions:
                section = transitions[s]; group = None; last = None; aggregate = None
                metadata('section'); continue
            if p['paragraph'] < 8 or not s.strip('_') or re.match(r'(?:Last Update:|Updated |Revised |WANT/HAVE LIST LAST UPDATED:)', s):
                metadata(); continue
            if s in ('Wantlists:', 'Milwaukee Brewers Bobblehead Wantlist', 'Milwaukee Baseball 8x10 HAVE list'):
                metadata('section'); continue
            if s == 'Eau Claire Express players:':
                aggregate = new_record('Eau Claire Express player cards', '', [ref], [original], 'player_interests')
                aggregate['list_type'] = 'want_list'; aggregate['review_reasons'] = []; aggregate['review_status'] = 'accepted'
                records.append(aggregate); last = aggregate
                entry['role'] = 'group'; entry['record_ids'] = [aggregate['id']]; continue
            if aggregate is not None and section == 'baseball' and not YEAR.match(s):
                aggregate['items'].append(s); aggregate['source_refs'].append(ref); aggregate['source_wording'].append(original)
                entry['role'] = 'item'; entry['record_ids'] = [aggregate['id']]; continue
            if YEAR.match(s): aggregate = None
            if section == 'autographs' or section == 'player_interests':
                if last is None:
                    mode = 'have_list' if section == 'autographs' else 'want_list'
                    last = new_record('Milwaukee Baseball 8x10 Autographs' if section == 'autographs' else 'Eau Claire player cards/photos/scans', s, [ref], [original], section, mode)
                    records.append(last)
                else:
                    last['source_refs'].append(ref); last['source_wording'].append(original)
                    last['items'].append(s)
                # Names with commas are one autograph item, not surname/initial split.
                if section == 'autographs' and len(last['source_refs']) == 1: last['items'] = [s]
                entry['role'] = 'item'; entry['record_ids'] = [last['id']]; continue
            if s.startswith(('http://', 'https://', '(Big shoutout', 'One additional "want":', 'I am interested in singles')):
                metadata(); continue
            if s == '*Exhibit cards:':
                group = {'title': 'Exhibit cards', 'mode': 'want_list', 'ref': ref, 'original': original}
                metadata('group'); continue
            s = s.lstrip('*')
            if s == ':':
                metadata('separator'); continue
            sep = separator(s)
            if section == 'bobbleheads' and re.fullmatch(r'\d{4}:', s):
                last = new_record(s[:4] + ' Milwaukee Brewers Bobbleheads', '', [ref], [original], section)
                records.append(last); group = None
                entry['role'] = 'group'; entry['record_ids'] = [last['id']]; continue
            if section == 'bobbleheads' and last is not None:
                last['source_refs'].append(ref); last['source_wording'].append(original)
                last['payload'] += ('\n' if last['payload'] else '') + s
                last['review_reasons'] = []; last['review_status'] = 'accepted'
                if s.lower() == 'complete': last['list_type'] = 'complete'
                else:
                    last['list_type'] = 'want_list'; last['items'].append(s)
                entry['role'] = 'item'; entry['record_ids'] = [last['id']]; continue
            dated = bool(YEAR.match(s)) and not re.fullmatch(r'\d{4}', s[:sep] if sep is not None else s)
            if group is not None and (re.match(r'^\d{4}(?:-\d{2,4})? (?:Style|PC Back Style)', s) or group['title'] == 'Exhibit cards'):
                dated = False
            if sep is None:
                if dated or re.search(r'\bHAVE lists?$', s, re.I):
                    group = {'title': s, 'mode': 'have_list' if re.search(r'\bHAVE\b', s, re.I) else 'want_list', 'ref': ref, 'original': original}
                    metadata('group'); continue
                if group is not None:
                    # A heading whose list starts on the following line.
                    last = new_record(group['title'], s, [group['ref'], ref],
                                      [group['original'], original], section, group['mode'])
                    records.append(last); entry['role'] = 'record'; entry['record_ids'] = [last['id']]
                    group = None
                    continue
                if original.lstrip().startswith('*'):
                    if last is not None and last['list_type'] == 'complete' and last['payload'].startswith('All listed are complete'):
                        last.setdefault('completed_sets', []).extend(comma_parts(s))
                        last['notes'].append(s); last['source_refs'].append(ref); last['source_wording'].append(original)
                        entry['role'] = 'note'; entry['record_ids'] = [last['id']]; continue
                    last = new_record(s, 'Wanted item', [ref], [original], section)
                    last['items'] = [s]; records.append(last)
                    entry['role'] = 'record'; entry['record_ids'] = [last['id']]; continue
                if last is not None:
                    # A list-only continuation extends the existing record; prose is a note.
                    last['source_refs'].append(ref); last['source_wording'].append(original)
                    if re.match(r'^\d+(?:[\s/,]|$)', s):
                        parts = parse_items(s, last['prefixes'])
                        for k in ('card_numbers', 'items', 'card_ranges', 'notes'): last[k].extend(parts[k])
                        last['payload'] += '\n' + s
                        entry['role'] = 'continuation'
                    else:
                        last['notes'].append(s); entry['role'] = 'note'
                    entry['record_ids'] = [last['id']]
                else: metadata()
                continue
            title, payload = s[:sep].rstrip(), s[sep + 1:].lstrip(': ')
            if not payload:
                group = {'title': title, 'mode': 'have_list' if re.search(r'\bHAVE\b', title, re.I) else 'want_list', 'ref': ref, 'original': original}
                metadata('group'); continue
            refs, originals = [ref], [original]
            inherited = 'want_list'
            if not dated and group is not None:
                # Parent HAVE designation must not override a child's WANT.
                parent_title = without_designations(group['title']).rstrip(': ')
                if parent_title.startswith('1995 JSW--'):
                    parent_title = '1995 JSW'
                title = parent_title + ' — ' + title
                inherited = group['mode']; refs.append(group['ref']); originals.append(group['original'])
            elif dated:
                group = None
            # Preserve implicit subtitled continuations under the last dated set.
            elif not dated and last and section not in ('vintage_tobacco', 'vintage_non_sport', 'other_collectibles', 'unknown_years'):
                title = last['set_name'] + ' — ' + title
                refs.append(last['source_refs'][0]); originals.append(last['source_wording'][0])
            last = new_record(title, payload, refs, originals, section, inherited, corrections)
            # Explicit incomplete exceptions override an inherited HAVE group.
            if re.match(r'Missing only', payload, re.I): last['source_list_type'] = 'want_list'
            records.append(last); entry['role'] = 'record'; entry['record_ids'] = [last['id']]
    # Aggregated records retain exact multiline wording and notes.
    for r in records:
        if len(r['source_refs']) > 1:
            r['notes'] = list(dict.fromkeys(r['notes']))
        r['review_status'] = 'needs_review' if r['review_reasons'] else r['review_status']
    # Make inherited group relationships explicit in the source ledger too.
    ref_map = {}
    for r in records:
        for ref in r['source_refs']:
            ref_map.setdefault((ref['paragraph'], ref['line']), []).append(r['id'])
    for e in ledger:
        ref = e['source_ref']
        e['record_ids'] = ref_map.get((ref['paragraph'], ref['line']), e['record_ids'])
    applied = sorted({c for r in records for c in r['corrections']}, key=lambda c: int(c.split('/')[0]))
    return {'schema_version': 1, 'source': {'path': raw['source_file'], 'sha256': raw['sha256']},
            'policy': {'have_lists_complemented': False, 'external_checklists_used': False,
                       'ranges_expanded': False, 'authority': 'Attached Word document plus user-confirmed decisions'},
            'correction_decisions': [{'decision': c, 'interpretation': DECISIONS[c]} for c in applied],
            'records': records, 'context_notes': context_notes, 'source_ledger': ledger}


def review_markdown(data):
    counts = Counter(r['list_type'] for r in data['records'])
    lines = ['# Phase 2 data review', '', f"Total normalized records: **{len(data['records'])}**", '',
             '| List type | Count |', '| --- | ---: |']
    lines += [f'| `{k}` | {counts[k]} |' for k in LIST_TYPES]
    lines += ['', '## Remaining human review', '']
    pending = [r for r in data['records'] if r['review_reasons']]
    if not pending: lines.append('No unresolved normalization ambiguities detected.')
    for r in pending:
        lines += [f"### {r['id']}: {r['set_name']}", '',
                  *[f'- {reason}' for reason in r['review_reasons']], '',
                  f"Source: {r['source_refs']}", '', f"> {r['source_wording'][0]}", '']
    lines += ['', '## Applied human-reviewed decisions', '']
    lines += [f"- **{c['decision']}**: {c['interpretation']}" for c in data['correction_decisions']]
    lines += ['', '## Preserved uncertainty (not unresolved parser errors)', '',
              '| Record | Source statement |', '| --- | --- |']
    for r in data['records']:
        if r['list_type'] == 'uncertain':
            statement = r['payload'].replace('|', '\\|').replace('\n', ' ')
            title = r['set_name'].replace('|', '\\|')
            lines.append(f"| `{r['id']}` {title} | {statement} |")
    lines += ['', '## Source fidelity and limitations', '',
              '- WANT items are wanted; HAVE items are owned. No HAVE complements or external checklists were generated.',
              '- Complete records have no listed cards/items. Upgrade and partial-completion wording remains in notes or mixed lists.',
              '- Uncertain claims remain uncertain. Ranges remain source expressions; no endpoints or checklist sizes are guessed.',
              '- Original DOCX, text, bold runs, and hyperlinks are retained. Paragraph/line references are one-based, including empty lines.',
              '- The merged 2012/1993 text is paragraph 639 in this DOCX (the earlier review called it 638); correction matches wording.',
              '- Football and baseball Topps records are separate, even when years and titles match.',
              '- Category/brand labels are conservative search metadata; exact titles and source wording remain authoritative.',
              '- Document context and broad collecting interests are retained in context_notes and the complete source ledger.',
              '- This is a rebuild; the previous temporary scripts/tests were unavailable. Validation checks are recreated in tests/.', '']
    return '\n'.join(lines)


def generate():
    raw = extract(); write_import(raw)
    data = build(raw)
    (ROOT / 'data/wantlists.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'data/DATA_REVIEW.md').write_text(review_markdown(data), encoding='utf-8')
    print(json.dumps({'records': len(data['records']), 'list_types': dict(Counter(r['list_type'] for r in data['records']))}, indent=2))
    return data


if __name__ == '__main__': generate()
