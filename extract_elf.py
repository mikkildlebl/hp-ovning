"""
Extract ELF questions from the official ELF example exam and add them to hp_questions.json.

The example exam (from studera.nu / hogskoleprovet.nu) is the only publicly available
ELF material — real exam ELF sections are not published due to copyright.

Structure of elf_hp2016.pdf:
  p0: "Prof Milgram's Experiment" passage
  p1: Questions 1-5
  p2: "To Err is Human" passage
  p3: Questions 6-10
  p4: Short texts (A Good Laugh, Scientific Progress, omega-3) + Q11
  p5: Questions 12-15 (Small Enterprises)
  p6: Gap-fill "Plagued by Cures" questions 16-20
"""
import re, json, os, hashlib
import fitz
import pdfplumber

PDF_PATH  = r'C:\Users\Mikael\Documents\Claude code\HP\Gamla_HP\elf_hp2016.pdf'
JSON_PATH = r'C:\Users\Mikael\Documents\Claude code\HP\hp_questions.json'
TEXTS_DIR = r'C:\Users\Mikael\Documents\Claude code\HP\texts'
HP_TEXTS  = r'C:\Users\Mikael\Documents\Claude code\HP\hp_texts'

FACIT = {
    1:'B', 2:'C', 3:'A', 4:'D', 5:'B',
    6:'C', 7:'D', 8:'A', 9:'C', 10:'A',
    11:'B', 12:'C', 13:'A', 14:'C', 15:'B',
    16:'D', 17:'A', 18:'D', 19:'C', 20:'D',
}

SOURCE_EXAM = 'elf-exempel'
PROVPASS    = 1

# Passage text pages (0-indexed) -> title
PASSAGE_PAGES = {
    0: "Prof Milgram's Experiment",
    2: "To Err is Human",
    4: "Short Texts",
    5: "Small Enterprises",
    6: "Plagued by Cures",
}

# Which questions belong to which passage title
PASSAGE_MAP = {
    "Prof Milgram's Experiment": list(range(1, 6)),    # Q1-5
    "To Err is Human":           list(range(6, 11)),   # Q6-10
    "Short Texts":               list(range(11, 14)),  # Q11-13
    "Small Enterprises":         list(range(14, 17)),  # Q14-16
    "Plagued by Cures":          list(range(17, 21)),  # Q17-20 (gap-fill)
}

Q_RE   = re.compile(r'^(\d{1,2})\.\s+(.*)')
OPT_RE = re.compile(r'^([A-D])\s{1,5}(\S.*)')
SKIP_RE = re.compile(r'^(–\s*\d+\s*–|PLEASE TURN|END OF ENGLISH|Questions?$)', re.I)


def column_lines(plumber_page):
    """Extract lines from a pdfplumber page in two-column order: left then right."""
    pw, ph = plumber_page.width, plumber_page.height
    mid = pw / 2
    left  = (plumber_page.crop((0, 0, mid, ph)).extract_text() or '').strip()
    right = (plumber_page.crop((mid, 0, pw, ph)).extract_text() or '').strip()
    combined = '\n'.join(p for p in [left, right] if p)
    return [l.strip() for l in combined.split('\n') if l.strip()]


def extract_passage_text(plumber_pdf, page_idx):
    lines = column_lines(plumber_pdf.pages[page_idx])
    parts = []
    for l in lines:
        if not l or SKIP_RE.match(l):
            continue
        parts.append(l)
    return ' '.join(parts)


GAP_FILL_RE = re.compile(r'^(\d{1,2})\.$')  # "17." alone on a line

def extract_questions(plumber_pdf):
    questions = []
    q_num = None
    q_text = []
    options = []

    def flush():
        nonlocal q_num, q_text, options
        if q_num is not None and q_text:
            questions.append({
                'num': q_num,
                'text': ' '.join(q_text).strip(),
                'options': list(options),
            })
        q_num = None
        q_text = []
        options = []

    # Pages 1-5: standard reading comprehension questions (Q1-16)
    for pi in [1, 3, 4, 5]:
        lines = column_lines(plumber_pdf.pages[pi])
        for line in lines:
            if not line or SKIP_RE.match(line):
                continue
            m = Q_RE.match(line)
            if m:
                flush()
                q_num = int(m.group(1))
                rest = m.group(2).strip()
                q_text = [rest] if rest else []
                continue
            mo = OPT_RE.match(line)
            if mo and q_num is not None:
                letter = mo.group(1)
                if not any(o.startswith(letter + ' ') for o in options):
                    options.append(f"{letter} {mo.group(2).strip()}")
                continue
            if q_num is not None and not options:
                q_text.append(line)
    flush()

    # Page 6: gap-fill (Q17-20) — hardcoded since it's a fixed sample exam
    # The passage "Plagued by Cures" has blanks; options extracted manually from PDF
    GAP_FILL_QS = [
        (17, "Thanks to extraordinary international _____ (including cease-fires in wars), polio is on the verge of going the same way as smallpox.",
         ["A efforts", "B research", "C conflicts", "D funding"]),
        (18, "_____ the triumph is by no means complete. Intervening in infections may have undesirable effects on the hosts.",
         ["A So", "B Consequently", "C Furthermore", "D Yet"]),
        (19, "As the incidence of childhood infections has fallen, chronic ailments like diabetes and asthma have become more _____.",
         ["A uncommon", "B harmless", "C frequent", "D deadly"]),
        (20, "Childhood _____ do indeed seem to reduce the probability of chronic disease—an idea known as the 'hygiene hypothesis'.",
         ["A experiences", "B vaccines", "C problems", "D infections"]),
    ]
    for num, text, opts in GAP_FILL_QS:
        questions.append({'num': num, 'text': text, 'options': opts})

    return questions


def make_id(source_exam, provpass, q_num):
    s = f"{source_exam}-{provpass}-{q_num}"
    return hashlib.md5(s.encode()).hexdigest()[:12]


def save_passage(title, text):
    key = hashlib.md5(title.encode()).hexdigest()[:16] + '.txt'
    full = f'{title} {text}'.strip()
    for d in [TEXTS_DIR, HP_TEXTS]:
        path = os.path.join(d, key)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(full)
    return key, full


def main():
    pdf = pdfplumber.open(PDF_PATH)

    # Extract passage texts
    passage_texts = {}
    for pi, title in PASSAGE_PAGES.items():
        text = extract_passage_text(pdf, pi)
        if text.startswith(title):
            text = text[len(title):].strip()
        passage_texts[title] = text

    # Extract questions
    qs = extract_questions(pdf)
    print(f"Extracted {len(qs)} questions")
    for q in qs:
        print(f"  {q['num']}. {q['text'][:60]}... opts={len(q['options'])}")

    # Save passages and build question records
    passage_files = {}
    for title in PASSAGE_MAP:
        text = passage_texts.get(title, '')
        if text:
            fname, full_text = save_passage(title, text)
            passage_files[title] = (fname, full_text)
            print(f"Saved passage: {title} -> {fname} ({len(full_text)} chars)")

    # Build question entries
    new_questions = []
    q_by_num = {q['num']: q for q in qs}

    for title, nums in PASSAGE_MAP.items():
        fname, full_text = passage_files.get(title, (None, ''))
        for n in nums:
            q = q_by_num.get(n)
            if not q:
                print(f"  WARNING: Q{n} not found in extraction")
                continue
            entry = {
                'source_exam':     SOURCE_EXAM,
                'provpass':        PROVPASS,
                'question_type':   'ELF',
                'question_number': n,
                'question_text':   q['text'],
                'options':         q['options'],
                'correct_answer':  FACIT.get(n, ''),
                'id':              make_id(SOURCE_EXAM, PROVPASS, n),
                'passage_file':    fname,
                'passage_text':    full_text,
            }
            new_questions.append(entry)

    print(f"\nBuilt {len(new_questions)} ELF question entries")

    # Load and update JSON
    with open(JSON_PATH, encoding='utf-8') as f:
        data = json.load(f)

    # Remove any existing ELF questions
    before = len(data['questions'])
    data['questions'] = [q for q in data['questions'] if q.get('question_type') != 'ELF']
    removed = before - len(data['questions'])
    if removed:
        print(f"Removed {removed} old ELF questions")

    data['questions'].extend(new_questions)
    print(f"Total questions: {len(data['questions'])}")

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("Saved hp_questions.json")


if __name__ == '__main__':
    main()
