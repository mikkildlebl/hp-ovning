"""
Extract LÄS passage texts from HP verbal PDFs and save them to the correct txt files.

Each PDF page contains:
  - A passage title (or continuation marker "LÄS")
  - Passage text
  - "Uppgifter" separator
  - Question text (two-column format)
  - Answer options

We extract the passage text by taking everything BEFORE "Uppgifter" on each page.
For multi-page passages (no Uppgifter on page), we concatenate.
"""
import json
import os
import re
import pdfplumber

JSON_PATH = r'C:\Users\Mikael\Documents\Claude code\HP\hp_questions.json'
TEXTS_DIR = r'C:\Users\Mikael\Documents\Claude code\HP\texts'
HP_TEXTS_DIR = r'C:\Users\Mikael\Documents\Claude code\HP\hp_texts'
PDF_DIR = r'C:\Users\Mikael\Documents\Claude code\HP\Gamla_HP'

STUB_SIZE = 600  # bytes


def find_pdf(exam, provpass):
    candidates = [
        f'{exam}_provpass-{provpass}-verb-utan-elf.pdf',
        f'{exam}_provpass-{provpass}-verb.pdf',
        f'{exam}_provpass-{provpass}-verb-v1.pdf',
    ]
    for name in candidates:
        path = os.path.join(PDF_DIR, name)
        if os.path.exists(path):
            return path
    return None


def extract_las_passages(pdf_path):
    """
    Extract LÄS passage texts from a verbal HP PDF.
    Returns list of (title, text) tuples, one per passage.

    HP PDFs use a two-column layout for passage text. We extract each column
    separately (left first, then right) so the text reads in the correct order.
    """
    # Patterns for section boundaries and headers
    LAS_START_RE = re.compile(
        r'DELPROV\s+L[ÄA]S|Svensk\s+l\S+sf\S+rst\S+else\s+[–\-]\s+L[ÄA]S',
        re.IGNORECASE
    )
    NON_TITLE_PATTERNS = re.compile(
        r'^(Uppgifter|ORD\s|Svarsh|MEK\s|ELF\s|\d+\.)',
        re.IGNORECASE
    )
    MEK_RE = re.compile(r'DELPROV\s+MEK|MEK\s+[–\-]\s+Mening', re.IGNORECASE)
    # Matches LÄS page headers to strip from column text
    LAS_HEADER_RE = re.compile(
        r'(?:Svensk\s+l\S+sf\S+rst\S+else\s+[–\-]\s+)?L[ÄA]S\s*\n?',
        re.IGNORECASE
    )
    # Also strip old-format section header
    DELPROV_RE = re.compile(
        r'DELPROV\s+L[ÄA]S[^\n]*\n?', re.IGNORECASE
    )

    def find_uppgifter_y(page):
        """Return the y-coordinate of 'Uppgifter' on this page, or None."""
        for w in page.extract_words():
            if w['text'].lower() == 'uppgifter':
                return w['top']
        return None

    def page_column_text(page, uppgifter_y=None):
        """Extract passage text in column order: left column then right column."""
        pw = page.width
        ph = uppgifter_y if uppgifter_y is not None else page.height
        mid = pw / 2

        left = (page.crop((0, 0, mid, ph)).extract_text() or '').strip()
        right = (page.crop((mid, 0, pw, ph)).extract_text() or '').strip()

        # Strip LÄS page headers from both columns
        left = LAS_HEADER_RE.sub('', left).strip()
        left = DELPROV_RE.sub('', left).strip()
        right = LAS_HEADER_RE.sub('', right).strip()
        right = DELPROV_RE.sub('', right).strip()

        parts = [p for p in [left, right] if p]
        return '\n'.join(parts)

    passages = []
    current_title = None
    current_text_parts = []
    in_las = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            full_text = page.extract_text() or ''
            has_las = bool(LAS_START_RE.search(full_text))
            has_mek = bool(MEK_RE.search(full_text))

            if has_las:
                in_las = True

            if has_mek:
                if current_title and current_text_parts:
                    text = ' '.join(current_text_parts)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) > 100:
                        passages.append((current_title, text))
                break

            if not in_las:
                continue

            uppgifter_y = find_uppgifter_y(page)
            passage_part = page_column_text(page, uppgifter_y)

            lines = [l.strip() for l in passage_part.split('\n') if l.strip()]
            if not lines:
                continue

            first_line = lines[0]

            is_title = (
                2 < len(first_line) <= 65 and
                first_line[0].isupper() and
                not re.match(r'^[A-E]\s+\S', first_line) and
                not re.match(r'^[A-E]\)', first_line) and
                not re.match(r'^\d+[\.\)]\s', first_line) and
                not first_line.startswith('–') and
                not first_line[0].islower() and
                not first_line[0].isdigit() and
                not NON_TITLE_PATTERNS.match(first_line)
            )

            if is_title:
                if current_title is not None and current_text_parts:
                    text = ' '.join(current_text_parts)
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) > 100:
                        passages.append((current_title, text))
                    current_text_parts = []
                current_title = first_line
                lines = lines[1:]

            current_text_parts.extend(lines)

    # Save the last passage if not already saved
    if current_title and current_text_parts:
        text = ' '.join(current_text_parts)
        text = re.sub(r'\s+', ' ', text).strip()
        if len(text) > 100:
            passages.append((current_title, text))

    # Filter out non-passage entries
    bad_titles = re.compile(
        r'^(Uppgifter|ORD\s*[\-–]|Svarsh|MEK\s*[\-–]|ELF\s*[\-–]|\d+\.)',
        re.IGNORECASE
    )
    passages = [
        (title, text) for title, text in passages
        if not bad_titles.match(title or '') and
        not (text or '').startswith('Uppgifter') and
        len(text or '') > 100
    ]

    return passages


def is_stub(filepath):
    if not os.path.exists(filepath):
        return True
    return os.path.getsize(filepath) < STUB_SIZE


def tokenize(text):
    return set(re.findall(r'\b\w{4,}\b', text.lower()))


def score_match(question_tokens, passage_text):
    passage_tokens = tokenize(passage_text)
    if not question_tokens or not passage_tokens:
        return 0
    return len(question_tokens & passage_tokens)


def find_matching_passage(questions, all_passages):
    """Match a list of questions to the best fitting passage using keyword overlap."""
    if not all_passages:
        return None, -1

    all_text = ' '.join(
        q.get('question_text', '') + ' ' + ' '.join(q.get('options', []))
        for q in questions
    )
    qtokens = tokenize(all_text)

    scores = [
        (score_match(qtokens, t + ' ' + txt), i)
        for i, (t, txt) in enumerate(all_passages)
    ]
    scores.sort(reverse=True)
    best_score, best_idx = scores[0]

    if best_score >= 2:
        return all_passages[best_idx], best_idx
    return all_passages[0], 0  # fallback to first passage


def get_ordered_groups(las_questions):
    """Return (passage_file, [questions]) list in question-number order."""
    groups = {}
    order = []
    for q in sorted(las_questions, key=lambda x: x['question_number']):
        pf = q['passage_file']
        if pf not in groups:
            groups[pf] = []
            order.append(pf)
        groups[pf].append(q)
    return [(pf, groups[pf]) for pf in order]


def process_exam_provpass(exam, provpass, las_questions, verbose=False, force_files=None):
    """Return dict passage_file -> text for stubs that can be filled.

    force_files: set of filenames that should be updated even if not stubs.
    """
    pdf_path = find_pdf(exam, provpass)
    if not pdf_path:
        print(f'  MISSING PDF: {exam} provpass {provpass}')
        return {}

    all_passages = extract_las_passages(pdf_path)
    if not all_passages:
        print(f'  NO PASSAGES: {os.path.basename(pdf_path)}')
        return {}

    if verbose:
        print(f'  {os.path.basename(pdf_path)}: {len(all_passages)} passages: {[p[0] for p in all_passages]}')

    groups = get_ordered_groups(las_questions)
    updates = {}
    force_files = force_files or set()

    for pf, questions in groups:
        path = os.path.join(TEXTS_DIR, pf)
        should_update = is_stub(path) or pf in force_files
        if not should_update:
            continue

        passage, idx = find_matching_passage(questions, all_passages)
        if passage:
            title, text = passage
            full_text = f'{title} {text}' if title else text
            full_text = full_text.strip()
            if len(full_text) > 100:
                updates[pf] = full_text

    return updates


def main():
    with open(JSON_PATH, encoding='utf-8') as f:
        data = json.load(f)

    # Group LÄS questions by (exam, provpass)
    exam_groups = {}
    for q in data['questions']:
        if q.get('question_type') != 'LAS' or not q.get('passage_file'):
            continue
        key = (q['source_exam'], q['provpass'])
        exam_groups.setdefault(key, []).append(q)

    # Re-extract ALL passage files with improved column-aware algorithm
    to_process = exam_groups
    all_passage_files = set(
        q['passage_file'] for q in data['questions']
        if q.get('question_type') == 'LAS' and q.get('passage_file')
    )

    print(f'Processing {len(to_process)} exam/provpass pairs ({len(all_passage_files)} passage files)...\n')

    all_updates = {}
    for (exam, provpass), questions in sorted(to_process.items()):
        updates = process_exam_provpass(exam, provpass, questions, verbose=True,
                                        force_files=all_passage_files)
        all_updates.update(updates)

    print(f'\nFound text for {len(all_updates)} files. Saving...')

    updated = 0
    too_short = 0
    for pf, text in all_updates.items():
        if len(text) < 100:
            too_short += 1
            continue
        for folder in [TEXTS_DIR, HP_TEXTS_DIR]:
            path = os.path.join(folder, pf)
            if os.path.exists(path):
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
        updated += 1

    print(f'Updated: {updated}  Too short to save: {too_short}')


def main_legacy():
    """Old main kept for reference — only processes stubs."""
    with open(JSON_PATH, encoding='utf-8') as f:
        data = json.load(f)

    exam_groups = {}
    for q in data['questions']:
        if q.get('question_type') != 'LAS' or not q.get('passage_file'):
            continue
        key = (q['source_exam'], q['provpass'])
        exam_groups.setdefault(key, []).append(q)

    to_process = {
        k: v for k, v in exam_groups.items()
        if any(is_stub(os.path.join(TEXTS_DIR, q['passage_file'])) for q in v)
    }

    BAD_FILES = {
        '887355acd033d2f5.txt',
        'ebe1cad17cdddb72.txt',
        # Audit-identified files starting mid-sentence
        '022480363ecedbfb.txt',
        '04b91250c3949ff8.txt',
        '0a8e24d1d5973802.txt',
        '1de9e9c935b4f85c.txt',
        '1eb42473a91e59d6.txt',
        '20f836492b85b75f.txt',
        '32bec7293a6ef9c4.txt',
        '335885997ce53026.txt',
        '35ed1e630ad05475.txt',
        '3bbe76f634d6a7bb.txt',
        '44d9f64c5f638068.txt',
        '4533b0edf15a9a48.txt',
        '5487c0809097a98b.txt',
        '59336324954c3054.txt',
        '5d4933536b1522c7.txt',
        '60d9b8cb9c69310c.txt',
        '615664b50bc2c7e4.txt',
        '708ea8a0771b627c.txt',
        '72bf0b2a4919d860.txt',
        '77aef97d56bef574.txt',
        '81c7fc53e829aaae.txt',
        '8696f02c992b95dc.txt',
        '8730b48cd318676b.txt',
        '89ad066a78d6e1f5.txt',
        '8cdb70fa3ab6a170.txt',
        '9630b6b10b28529c.txt',
        'b0c16dfb5413117d.txt',
        'b21e630ffafcb29f.txt',
        'b531b54fb391d26d.txt',
        'c6dee471a37a0807.txt',
        'c937989bf668bba2.txt',
        'd3449d3ed45aff1f.txt',
        'd40ea811812416c4.txt',
        'da1ee2ee7bdc061e.txt',
        'df986b11d2ea3299.txt',
        'e18e9a01dbaf7709.txt',
        'e2b108ace1510107.txt',
        'e32af15105ccdeca.txt',
        'e5de328dedcfa9f8.txt',
        'ee04cc921a47171f.txt',
        'ee2a1a76631bd946.txt',
        'f01f4f372748cea4.txt',
        'f434703363bdf954.txt',
        'f5ef9285b81ffc75.txt',
        'f748b10ab06b05a1.txt',
        'fadb04d1ce6ec95f.txt',
        'fec5b9afd13dedbf.txt',
    }

    print(f'Processing {len(to_process)} exam/provpass pairs with stubs...\n')

    all_updates = {}
    for (exam, provpass), questions in sorted(to_process.items()):
        # Include bad files that belong to this exam/provpass for forced re-extraction
        exam_bad = {pf for pf in BAD_FILES
                    if any(q['passage_file'] == pf for q in questions)}
        updates = process_exam_provpass(exam, provpass, questions, verbose=True,
                                        force_files=exam_bad)
        all_updates.update(updates)

    # Also force-reprocess any bad files from pairs that are no longer in to_process
    for pf in BAD_FILES:
        if pf not in all_updates:
            # Find which exam/provpass this belongs to
            for q in data['questions']:
                if q.get('passage_file') == pf:
                    key = (q['source_exam'], q['provpass'])
                    questions = exam_groups[key]
                    updates = process_exam_provpass(
                        key[0], key[1], questions, verbose=True, force_files={pf}
                    )
                    all_updates.update(updates)
                    break

    print(f'\nFound text for {len(all_updates)} stub files. Saving...')

    updated = 0
    too_short = 0
    for pf, text in all_updates.items():
        if len(text) < 100:
            too_short += 1
            continue
        for folder in [TEXTS_DIR, HP_TEXTS_DIR]:
            path = os.path.join(folder, pf)
            if os.path.exists(path) and (is_stub(path) or pf in BAD_FILES):
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
        updated += 1

    print(f'Updated: {updated}  Too short to save: {too_short}')

    # Report remaining stubs
    still_stubs = set(
        q['passage_file']
        for q in data['questions']
        if q.get('question_type') == 'LAS' and q.get('passage_file')
        and is_stub(os.path.join(TEXTS_DIR, q['passage_file']))
    )
    print(f'Remaining stubs after update: {len(still_stubs)}')
    for pf in sorted(still_stubs):
        print(f'  {pf}')


if __name__ == '__main__':
    main()
