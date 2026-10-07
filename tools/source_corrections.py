"""User-confirmed interpretations. Match wording, never unstable paragraph offsets."""
import re

DECISIONS = {
    '1': '1978 Burger King Tigers: 1218 → 12 18 (HAVE).',
    '2': '1976 Linnett Superstars Individual Cards: 107114 → 107 114.',
    '3': '1976 Towne Club Discs: remove accidental empty comma item.',
    '4/9': '2012 Topps ends at 424; discard appended duplicate 1993 heading/list.',
    '5': '1962 Play-Rite Roger Maris: owned example and Good enough note are valid.',
    '6': '1943 Grand Studio Milwaukee Brewers: remove accidental empty comma item.',
    '7': 'Carreras Film Stars 1937: set size 54, preserve HAVE 53.',
    '8': 'Gallaher Red Back 1934: total set size unknown, retain WANT 49 and 50.',
    '10': '2025 Topps Heritage: separate WANT record after Costco HAVE list.',
    '11': '2019 Topps Holiday (HW-): user-defined Complete, no wanted items.',
    '12': '2016 Milwaukee Brewers Team Set: listL → list:, separate HAVE MB-14.',
    '13': '2009 Bowman Chrome Prospects: 4748 → 47 48 (HAVE).',
    '14': '2008 Milwaukee Brewers Team Set: listL → list:, separate HAVE MIL10.',
    '15': '2006 Constitution SCC-: quote → colon, separate HAVE record.',
    '16': '2004 Upper Deck Power Up: 4750 → 47 50.',
    '17': '2001 Ritz/Oreo: WANT Blue Border Griffey, HAVE Red Border Griffey.',
    '18': '2000 Just Just Imagine: restore colon, separate WANT record.',
    '19': '1998 Fleer Sports Illustrated Opening Day: 2024 → 20 24.',
    '20/21': '1997 Leaf: 100104 → 100 104; one correction.',
    '22': '1988 Baseball Cards Magazine Replicards: remove empty comma item.',
    '23': '1987 Fleer Mini: 8991 → 89 91 (HAVE).',
}


def correct(text):
    s = text.replace('\xa0', ' ').strip()
    ids = []
    splits = [
        ('1', '1978 Burger King Tigers', '1218', '12 18'),
        ('2', '1976 Linnett Superstars Individual Cards', '107114', '107 114'),
        ('13', '2009 Bowman Chrome Prospects', '4748', '47 48'),
        ('16', '2004 Upper Deck Power Up', '4750', '47 50'),
        ('19', '1998 Fleer Sports Illustrated Opening Day', '2024', '20 24'),
        ('20/21', '1997 Leaf:', '100104', '100 104'),
        ('23', '1987 Fleer Mini HAVE list', '8991', '89 91'),
    ]
    for key, heading, old, new in splits:
        if s.startswith(heading) and re.search(r'\b' + old + r'\b', s):
            s = re.sub(r'\b' + old + r'\b', new, s)
            ids.append(key)
    for key, heading in [('3', '1976 Towne Club Discs'),
                         ('6', '1943 Grand Studio Milwaukee Brewers'),
                         ('22', '1988 Baseball Cards Magazine Replicards')]:
        if s.startswith(heading):
            s = re.sub(r',\s*,', ',', s)
            ids.append(key)
    if s.startswith('2012 Topps WANT list:') and '1993 Topps WANT list:' in s:
        s = s.split('1993 Topps WANT list:')[0].rstrip()
        ids.append('4/9')
    if s.startswith('1962 Play-Rite Roger Maris:'):
        ids.append('5')
    if s.startswith('Carreras Film Stars 1937'):
        s = s.replace('(50)', '(54)')
        ids.append('7')
    if s.startswith('Gallaher Champions of Screen and Stage (Red Back) 1934'):
        s = s.replace('(48)', '').strip()
        ids.append('8')
    if s.startswith('2025 Topps Heritage '):
        s = s.replace('2025 Topps Heritage ', '2025 Topps Heritage: ', 1)
        ids.append('10')
    if s.startswith('2019 Topps Holiday (HW-)'):
        s = s.split(':', 1)[0] + ': Complete'
        ids.append('11')
    for key, heading in [('12', '2016 Topps Milwaukee Brewers Team Set'),
                         ('14', '2008 Topps Milwaukee Brewers Team Set')]:
        if s.startswith(heading):
            s = s.replace('listL', 'list:')
            ids.append(key)
    if s.startswith('2006 Topps Chrome United States Constitution'):
        s = s.replace('(SCC-)"', '(SCC-):')
        ids.append('15')
    if s.startswith('2001 Ritz/Oreo (Fleer):'):
        s = '2001 Ritz/Oreo (Fleer): Blue Border Griffey (Red Border Griffey already owned)'
        ids.append('17')
    if s.startswith('2000 Just Just Imagine (minor league) '):
        s = s.replace('(minor league) ', '(minor league): ', 1)
        ids.append('18')
    return s, ids
