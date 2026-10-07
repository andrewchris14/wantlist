"""Lossless text/run import of the authoritative DOCX; Python standard library only."""
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/raw/Wantlists 10-5-26.docx'
EXPECTED_SHA256 = '75d968d267b9ee551e3d45343d7ce8966e7ee81f82ff26a62eac5a7239e3cda7'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def extract():
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError('Authoritative document checksum changed; review before importing.')
    with zipfile.ZipFile(SOURCE) as z:
        doc = ET.fromstring(z.read('word/document.xml'))
        rels = ET.fromstring(z.read('word/_rels/document.xml.rels'))
    targets = {e.attrib['Id']: e.attrib['Target'] for e in rels}
    paragraphs = []
    # Include body paragraphs in order, including any paragraphs inside tables.
    for i, p in enumerate(doc.find(W + 'body').iter(W + 'p'), 1):
        pieces = []
        for e in p.iter():
            if e.tag == W + 't':
                pieces.append(e.text or '')
            elif e.tag in (W + 'br', W + 'cr'):
                pieces.append('\n')
            elif e.tag == W + 'tab':
                pieces.append('\t')
        runs = []
        for run in p.iter(W + 'r'):
            text = ''.join(e.text or '' for e in run.iter(W + 't'))
            props = run.find(W + 'rPr')
            bold_prop = props.find(W + 'b') if props is not None else None
            bold = bold_prop is not None and bold_prop.get(W + 'val', '1') not in ('0', 'false', 'off')
            if text:
                runs.append({'text': text, 'bold': bold})
        links = [{'text': ''.join(e.text or '' for e in h.iter(W + 't')),
                  'target': targets.get(h.get(R + 'id'))}
                 for h in p.iter(W + 'hyperlink')]
        paragraphs.append({'paragraph': i, 'text': ''.join(pieces),
                           'runs': runs, 'hyperlinks': links})
    return {'source_file': str(SOURCE.relative_to(ROOT)), 'sha256': digest,
            'paragraphs': paragraphs}


def write_import(raw):
    path = ROOT / 'data/raw/paragraphs.json'
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    raw = extract()
    write_import(raw)
    print(f"Imported {len(raw['paragraphs'])} paragraphs; source SHA-256 verified.")
