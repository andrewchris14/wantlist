"""Phase 2 source fidelity, human-decision, and reproduction regressions."""
import hashlib
import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from import_docx import EXPECTED_SHA256, SOURCE, extract
from normalize_wantlists import LIST_TYPES, build, new_record, review_markdown
from source_corrections import DECISIONS, correct


class Phase2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = extract()
        cls.data = build(cls.raw)
        cls.records = cls.data['records']

    def find(self, title):
        matches = [r for r in self.records if r['set_name'] == title]
        self.assertEqual(len(matches), 1, f'Expected one record: {title}')
        return matches[0]

    def by_decision(self, decision):
        matches = [r for r in self.records if decision in r['corrections']]
        self.assertEqual(len(matches), 1, decision)
        self.assertNotEqual(matches[0]['list_type'], 'needs_review')
        return matches[0]

    def test_immutable_source(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(), EXPECTED_SHA256)

    def test_valid_schema_and_unique_ids(self):
        self.assertGreater(len(self.records), 1000)
        self.assertEqual(len({r['id'] for r in self.records}), len(self.records))
        for r in self.records:
            with self.subTest(record=r['id']):
                self.assertIn(r['list_type'], LIST_TYPES)
                self.assertIn(r['source_list_type'], ('want_list', 'have_list'))
                self.assertTrue(r['set_name'])
                self.assertTrue(r['category'])
                for key in ('items', 'card_numbers', 'card_ranges', 'notes', 'uncertainty', 'mixed_lists', 'sublists'):
                    self.assertIsInstance(r[key], list)
                self.assertEqual(bool(r['review_reasons']), r['list_type'] == 'needs_review')

    def test_every_record_maps_to_original_source(self):
        lines = {(p['paragraph'], i): text for p in self.raw['paragraphs']
                 for i, text in enumerate(p['text'].split('\n'), 1)}
        for r in self.records:
            self.assertTrue(r['source_refs'])
            self.assertEqual(len(r['source_refs']), len(r['source_wording']))
            for ref, original in zip(r['source_refs'], r['source_wording']):
                self.assertEqual(lines[(ref['paragraph'], ref['line'])], original, r['id'])

    def test_every_nonempty_source_line_is_accounted_for(self):
        expected = {(p['paragraph'], i) for p in self.raw['paragraphs']
                    for i, text in enumerate(p['text'].split('\n'), 1) if text.strip()}
        actual = {(e['source_ref']['paragraph'], e['source_ref']['line']) for e in self.data['source_ledger']}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), len(self.data['source_ledger']))
        for entry in self.data['source_ledger']:
            self.assertIn(entry['role'], ('context', 'section', 'separator', 'group', 'record', 'item', 'note', 'continuation'))
            if entry['role'] == 'group': self.assertTrue(entry['record_ids'], entry['text'])

    def test_no_blank_items(self):
        for r in self.records:
            for group in [r] + r['mixed_lists'] + r['sublists']:
                for key in ('items', 'card_numbers', 'card_ranges'):
                    self.assertTrue(all(str(v).strip() for v in group.get(key, [])), r['id'])

    def test_complete_sets_have_no_generated_wants(self):
        for r in self.records:
            if r['list_type'] == 'complete':
                self.assertEqual(r['card_numbers'], [], r['id'])
                self.assertEqual(r['items'], [], r['id'])
                self.assertEqual(r['card_ranges'], [], r['id'])
                self.assertFalse(any(g['list_type'] == 'want_list' for g in r['mixed_lists'] + r['sublists']))
        self.assertEqual(self.find('1952 Topps')['list_type'], 'complete')

    def test_have_lists_not_complemented(self):
        self.assertFalse(self.data['policy']['have_lists_complemented'])
        for r in self.records:
            if r['source_list_type'] == 'have_list':
                self.assertIn(r['list_type'], ('have_list', 'complete', 'uncertain', 'needs_review'), r['id'])
            corrected_source = '\n'.join(correct(s)[0] for s in r['source_wording'])
            for group in [r] + r['mixed_lists'] + r['sublists']:
                if group.get('source_list_type', group['list_type']) == 'have_list':
                    for token in group.get('card_numbers', []) + group.get('card_ranges', []):
                        self.assertRegex(corrected_source, r'(?<![A-Za-z0-9])' + re.escape(token) + r'(?![A-Za-z0-9])', r['id'])
        self.assertEqual(self.find('2025 Topps Update')['card_numbers'], [])
        self.assertEqual(self.find('2025 Topps Update')['items'], [])

    def test_all_23_user_decisions_applied(self):
        self.assertEqual({c['decision'] for c in self.data['correction_decisions']}, set(DECISIONS))
        # 4/9 and 20/21 each share a single correction and record.
        for decision in DECISIONS: self.by_decision(decision)

    def test_joined_number_corrections(self):
        replacements = {'1': ('1218', ['12', '18']), '2': ('107114', ['107', '114']),
                        '13': ('4748', ['47', '48']), '16': ('4750', ['47', '50']),
                        '19': ('2024', ['20', '24']), '20/21': ('100104', ['100', '104']),
                        '23': ('8991', ['89', '91'])}
        for decision, (joined, split) in replacements.items():
            r = self.by_decision(decision)
            self.assertNotIn(joined, r['card_numbers'])
            index = r['card_numbers'].index(split[0])
            self.assertEqual(r['card_numbers'][index:index + 2], split)
        self.assertEqual(self.by_decision('1')['card_numbers'], ['9', '12', '18', '19'])
        self.assertEqual(self.by_decision('13')['card_numbers'], ['47', '48', '79', '87'])
        self.assertEqual(self.by_decision('2')['card_numbers'], '102 103 104 105 106 107 114 115 116 117 118 119 120 121 122 123 124 125'.split())

    def test_confirmed_comma_corrections(self):
        self.assertEqual(self.by_decision('6')['items'], ['Clarke', 'Johnson', 'Sproull', 'York'])
        self.assertEqual(self.by_decision('22')['items'], ["Williams '54B", "Williams '52 Topps", 'Ruth', "Mantle '56B", "Robinson '52B"])
        self.assertEqual(self.by_decision('3')['items'][:2], ['Aaron', 'Carew'])
        self.assertEqual(len(self.by_decision('3')['items']), 19)

    def test_2012_end_and_no_appended_1993_duplicate(self):
        r = self.by_decision('4/9')
        self.assertEqual(r['card_numbers'], '18 134 140 159 162 163 165 167 169 179 182 198 210 235 236 249 269 289 340 344 346 348 352 373 384 404 410 424'.split())
        origin = r['source_refs'][0]
        self.assertEqual([e['id'] for e in self.records if origin in e['source_refs']], [r['id']])
        football_1993 = [e for e in self.records if e['set_name'] == '1993 Topps' and e['category'] == 'football_cards']
        self.assertEqual(len(football_1993), 1)
        self.assertEqual(football_1993[0]['source_refs'][0]['paragraph'], 620)
        baseball_1993 = [e for e in self.records if e['set_name'] == '1993 Topps' and e['category'] == 'baseball_cards']
        self.assertEqual(len(baseball_1993), 1)
        self.assertEqual(baseball_1993[0]['list_type'], 'complete')

    def test_set_size_decisions(self):
        carreras = self.by_decision('7')
        self.assertEqual(carreras['set_size'], 54)
        self.assertEqual(carreras['card_numbers'], ['1', '6', '48', '53'])
        gallaher = self.by_decision('8')
        self.assertIsNone(gallaher['set_size'])
        self.assertEqual(gallaher['card_numbers'][-2:], ['49', '50'])

    def test_known_boundaries_and_ownership(self):
        costco = self.find('2025 Topps Flagship (Costco)')
        self.assertEqual(costco['list_type'], 'have_list')
        self.assertEqual(costco['card_numbers'][-1], '100')
        heritage = self.by_decision('10')
        self.assertEqual(heritage['list_type'], 'want_list')
        self.assertEqual(heritage['card_numbers'], '17 35 41 45 51 53 58 61 71 78 80 88 90 95 104 130 133 137 145 147 153 162 167 180 181 207 210 224 231 247 254 260 262 271 281 289 290 296 301 305 306 320 324 332 338 340 378 383 386'.split())
        self.assertEqual(self.find('2016 Topps Holiday')['card_numbers'], ['38', '42', '105', '119', '189'])
        for decision, token in [('12', 'MB-14'), ('14', 'MIL10')]:
            r = self.by_decision(decision)
            self.assertEqual(r['list_type'], 'have_list'); self.assertEqual(r['card_numbers'], [token])
        self.assertEqual(self.find('2008 Topps Kansas City Royals Team Set')['card_numbers'], ['KCR2', 'KCR7', 'KCR12'])
        constitution = self.by_decision('15')
        self.assertEqual(constitution['card_numbers'], ['DB', 'JBR', 'JI', 'PB', 'TF'])
        self.assertEqual(constitution['prefixes'], ['SCC-'])
        declaration = self.find('2006 Topps Chrome Declaration of Independence (SDC-)')
        self.assertEqual(declaration['card_numbers'], 'CC JM JP LH LM RTP SA SC TL'.split())
        self.assertEqual(self.find('2000 Just Just the Preview 2K (minor league)')['card_numbers'][-1], '100')
        self.assertEqual(self.by_decision('18')['card_numbers'], '103 104 108 110 111 113 114 115 118 123 124 128 130 134 135 136 143 147 148 150 151 154 155 158 161 163 166 168 169 171 173 179 182 186 190 192 195 196 199'.split())

    def test_holiday_complete_and_griffey_variant(self):
        holiday = self.by_decision('11')
        self.assertEqual(holiday['list_type'], 'complete'); self.assertEqual(holiday['card_numbers'], [])
        griffey = self.by_decision('17')
        self.assertEqual(griffey['items'], ['Blue Border Griffey'])
        self.assertEqual(griffey['mixed_lists'][0]['items'], ['Red Border Griffey'])
        self.assertEqual(griffey['mixed_lists'][0]['list_type'], 'have_list')

    def test_play_rite_note(self):
        r = self.by_decision('5')
        self.assertEqual(r['list_type'], 'have_list')
        self.assertIn('Foul Strike|Ball', r['notes'][0]); self.assertIn('Good enough.', r['notes'][0])
        self.assertIn(':)', r['notes'][0]); self.assertEqual(r['review_reasons'], [])

    def test_inherited_have_and_explicit_want(self):
        self.assertEqual(self.find('Brooke Bond Cards (various years--most if not all are 50 card sets) unless noted — Adventurers & Explorers')['list_type'], 'have_list')
        self.assertEqual(self.find('Brooke Bond Cards (various years--most if not all are 50 card sets) unless noted — The Sea-Our Other World')['list_type'], 'want_list')
        self.assertEqual(self.find('Carreras Cigarettes — Believe it or Not')['list_type'], 'want_list')
        self.assertEqual(self.find('1972-1973 TCMA Exhibit Reprints — 1921 Style')['list_type'], 'have_list')
        self.assertEqual(self.find('2020 Topps Archives')['list_type'], 'have_list')
        self.assertEqual(self.find('2020 Topps Archives')['card_numbers'], ['12', '15', '53', '168', '179', '191', '273', '284'])

    def test_mixed_lists_and_uncertainty(self):
        kiss = self.find('1978 Donruss KISS')
        self.assertEqual(kiss['card_numbers'], ['33'])
        self.assertEqual(kiss['mixed_lists'][0]['list_type'], 'have_list')
        self.assertEqual(kiss['mixed_lists'][0]['card_numbers'], ['77', '99'])
        jsw = self.find('1995 JSW — 33 Goudey Red Box')
        self.assertEqual(jsw['source_list_type'], 'have_list')
        self.assertEqual(jsw['mixed_lists'][0]['source_list_type'], 'want_list')
        self.assertEqual(jsw['mixed_lists'][0]['list_type'], 'uncertain')
        uncertain = self.find('1980 Unknown Manufacturer New York Yankees All-Time Greats')
        self.assertEqual(uncertain['list_type'], 'uncertain')
        self.assertTrue(uncertain['uncertainty'])

    def test_non_card_and_non_baseball_material_preserved(self):
        categories = Counter(r['category'] for r in self.records)
        for category in ('postcards', 'matchbooks', 'tobacco_and_candy_cards', 'bobbleheads', 'autographs', 'football_cards', 'playing_cards', 'posters', 'discs', 'player_interests'):
            self.assertGreater(categories[category], 0, category)
        autographs = [r for r in self.records if r['category'] == 'autographs']
        self.assertEqual(len(autographs), 1)
        self.assertEqual(autographs[0]['list_type'], 'have_list')
        self.assertIn('Aaron, H', autographs[0]['items']); self.assertIn('Yount, R', autographs[0]['items'])
        self.assertEqual(self.find('Gary Carter Testimonial Booklet')['list_type'], 'want_list')
        self.assertIn('11/30/48', next(r for r in self.records if r['set_name'].startswith('1981 Topps Scratch Offs'))['card_numbers'])

    def test_unresolved_number_detection(self):
        r = new_record('1997 Example', '100104', [{'paragraph': 1, 'line': 1}], ['1997 Example: 100104'], 'baseball')
        self.assertEqual(r['list_type'], 'needs_review')
        self.assertIn('100104', r['review_reasons'][0])

    def test_generated_files_match_reproducible_build(self):
        expected = json.dumps(self.data, ensure_ascii=False, indent=2) + '\n'
        self.assertEqual((ROOT / 'data/wantlists.json').read_text(), expected)
        self.assertEqual(json.dumps(build(extract()), ensure_ascii=False, indent=2) + '\n', expected)
        self.assertEqual((ROOT / 'data/DATA_REVIEW.md').read_text(), review_markdown(self.data))
        self.assertEqual(json.loads((ROOT / 'data/raw/paragraphs.json').read_text()), self.raw)


if __name__ == '__main__': unittest.main()
