"""
Scrape extra ELF questions from hogskoleprovet.nu/elf/ and add them to hp_questions.json.
"""
import urllib.request, re, json, os, hashlib

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
JSON_PATH = r'C:\Users\Mikael\Documents\Claude code\HP\hp_questions.json'
TEXTS_DIR = r'C:\Users\Mikael\Documents\Claude code\HP\texts'
HP_TEXTS  = r'C:\Users\Mikael\Documents\Claude code\HP\hp_texts'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode('utf-8', errors='replace')

def strip_tags(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&#\d+;', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

# Known correct answers from hogskoleprovet.nu (verified via WebFetch)
CORRECT = {
    'Mozambique': 'C',
    'Kurlansky':  'A',
    'silver coin': 'B',
    'athletic': 'B',
    'crop protection': 'C',
}

def get_correct(question_text, choice_labels):
    """Map correct answer letter based on known answers."""
    q = question_text.lower()
    for kw, letter in CORRECT.items():
        if kw.lower() in q or any(kw.lower() in l.lower() for l in choice_labels):
            idx = ord(letter) - ord('A')
            if idx < len(choice_labels):
                return letter
    return ''

def scrape_hogskoleprovet_elf():
    html = fetch('https://www.hogskoleprovet.nu/elf/')

    blocks = html.split('class="quiz-question-text">')[1:]

    questions = []
    for block in blocks:
        body_end = block.find('class="quiz-choices"')
        if body_end < 0:
            continue
        body_html = block[:body_end]

        # The question is in the last <p>...</p> inside the body
        p_tags = re.findall(r'<p>(.*?)</p>', body_html, re.DOTALL)
        if not p_tags:
            continue
        question_html = p_tags[-1]
        question_text = strip_tags(question_html).strip()
        if not question_text.endswith('?'):
            continue

        # Passage text: everything before the last <p> tag
        last_p_pos = body_html.rfind('<p>')
        passage_html = body_html[:last_p_pos]
        passage_text = strip_tags(passage_html).strip()

        # Extract choices: radio input siblings labeled by their container text
        # Choices appear as list items after quiz-choices
        choices_block = block[body_end:]
        choice_matches = re.findall(r'<li[^>]*class="quiz-choice[^"]*"[^>]*>.*?<span[^>]*>(.*?)</span>', choices_block, re.DOTALL)
        if not choice_matches:
            # fallback: any text in label tags
            choice_matches = re.findall(r'<label[^>]*>\s*<input[^>]*>\s*(.*?)\s*</label>', choices_block, re.DOTALL)
            choice_matches = [strip_tags(c) for c in choice_matches]
        choice_matches = [strip_tags(c) for c in choice_matches if strip_tags(c)]

        options = []
        for i, c in enumerate(choice_matches[:4]):
            letter = chr(ord('A') + i)
            options.append(f"{letter} {c.strip()}")

        if not options or not passage_text:
            continue

        correct = get_correct(question_text, choice_matches)
        questions.append({
            'passage': passage_text,
            'question': question_text,
            'options': options,
            'correct': correct,
        })
        print(f"  Q: {question_text[:70]}")
        print(f"     Passage: {passage_text[:60]}...")
        print(f"     Opts: {options}  Correct: {correct}")

    return questions


def make_id(source, n):
    return hashlib.md5(f"{source}-{n}".encode()).hexdigest()[:12]


def save_passage(title, text):
    key = hashlib.md5(title.encode()).hexdigest()[:16] + '.txt'
    full = f'{title} {text}'.strip()
    for d in [TEXTS_DIR, HP_TEXTS]:
        path = os.path.join(d, key)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(full)
    return key, full


def main():
    print("Scraping hogskoleprovet.nu/elf/...")
    scraped = scrape_hogskoleprovet_elf()
    print(f"Found {len(scraped)} questions\n")

    with open(JSON_PATH, encoding='utf-8') as f:
        data = json.load(f)

    source = 'elf-hogskoleprovet-nu'
    # Remove any previously added (possibly broken) entries from this source
    before = len(data['questions'])
    data['questions'] = [q for q in data['questions'] if q.get('source_exam') != source]
    removed = before - len(data['questions'])
    if removed:
        print(f"Removed {removed} old entries from {source}")

    new_questions = []
    for i, q in enumerate(scraped, 1):
        qt = q['question'].strip()

        title = qt[:40]  # use question as passage title key
        fname, full_text = save_passage(title, q['passage'])

        entry = {
            'source_exam':     source,
            'provpass':        1,
            'question_type':   'ELF',
            'question_number': i,
            'question_text':   qt,
            'options':         q['options'],
            'correct_answer':  q['correct'],
            'id':              make_id(source, i),
            'passage_file':    fname,
            'passage_text':    full_text,
        }
        new_questions.append(entry)
        print(f"  Added Q{i}: {qt[:60]}")

    if new_questions:
        data['questions'].extend(new_questions)
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nAdded {len(new_questions)} ELF questions. Total: {len(data['questions'])}")
    else:
        print("No new questions to add.")


if __name__ == '__main__':
    main()
