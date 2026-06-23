"""
Parse ELF questions from eddler.se lesson pages.
Extracts lessonData JSON embedded in page JS.
"""
import urllib.request, re, json, os, hashlib

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
JSON_PATH = r'C:\Users\Mikael\Documents\Claude code\HP\hp_questions.json'
TEXTS_DIR = r'C:\Users\Mikael\Documents\Claude code\HP\texts'
HP_TEXTS  = r'C:\Users\Mikael\Documents\Claude code\HP\hp_texts'

PAGES = [
    ('hpvar2025p2',  2, 'elf-engelsk-lasforstaelse-hpvar2025p2'),
    ('hphost2023p3', 3, 'elf-engelsk-lasforstaelse-hphost2023p3'),
    ('hpvar2023p3',  3, 'elf-engelsk-lasforstaelse-hpvar2023p3'),
    ('hpvar2023p5',  5, 'elf-engelsk-lasforstaelse-hpvar2023p5'),
    ('hphost2016p4', 4, 'elf-engelsk-lasforstaelse-hphost2016p4'),
    ('hpmars2022p4', 4, 'elf-engelsk-lasforstaelse-hpmars2022p4'),
    ('hphost2022p2', 2, 'elf-engelsk-lasforstaelse-hphost2022p2'),
    ('hpmaj2022p3',  3, 'elf-engelsk-lasforstaelse-hpmaj2022p3'),
    ('hpmaj2021p1',  1, 'elf-engelsk-lasforstaelse-hpmaj2021p1'),
    ('hpvar2019p4',  4, 'elf-engelsk-lasforstaelse-hpvar2019p4'),
    ('hpvar2017p3',  3, 'elf-engelsk-lasforstaelse-hpvar2017p3'),
]

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', errors='replace')

def strip_tags(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&amp;', '&', s)
    s = re.sub(r'&lt;', '<', s)
    s = re.sub(r'&gt;', '>', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&#8217;', "'", s)
    s = re.sub(r'&#8220;|&#8221;', '"', s)
    s = re.sub(r'&#8230;', '...', s)
    s = re.sub(r'&#\d+;', '', s)
    s = re.sub(r'&[a-z]+;', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def extract_lesson_data(html):
    """Find and parse the lessonData JS object embedded in the page."""
    # Try to find the lessonData assignment
    m = re.search(r'var\s+lessonData\s*=\s*(\{.*?\});\s*(?:var|function|</script>)', html, re.DOTALL)
    if not m:
        # Try alternative: lessonData = {...}
        m = re.search(r'lessonData\s*=\s*(\{.*?\n\})', html, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
    return None

def extract_questions_from_html(html, source_exam, provpass):
    """
    Fallback: parse questions directly from HTML if lessonData not found.
    Eddler uses quiz blocks with question text, options, and correct-answer attributes.
    """
    questions = []

    # Look for correct-answer data attributes
    # Pattern: data-correct-answer="A" or correct-answer="B"
    blocks = re.split(r'class="[^"]*question[^"]*"', html)

    # Try looking for quiz items with correct answer markers
    # Each question block has: passage, question stem, A/B/C/D options, correct answer
    # Structure varies by site version

    # Look for wp quiz or similar structures
    quiz_items = re.findall(
        r'data-correct[^=]*=[\'"](.*?)[\'"].*?<(?:p|div)[^>]*class="[^"]*(?:question|stem)[^"]*"[^>]*>(.*?)</(?:p|div)>',
        html, re.DOTALL | re.I
    )
    print(f"  quiz_items found: {len(quiz_items)}")

    return questions

def make_id(source, provpass, n):
    s = f"eddler-{source}-{provpass}-{n}"
    return hashlib.md5(s.encode()).hexdigest()[:12]

def save_passage(title, text):
    key = hashlib.md5((title + text[:50]).encode()).hexdigest()[:16] + '.txt'
    full = f'{title}\n\n{text}'.strip()
    for d in [TEXTS_DIR, HP_TEXTS]:
        path = os.path.join(d, key)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(full)
    return key, full

def parse_page(source_id, provpass, slug):
    url = f'https://eddler.se/lektioner/{slug}/'
    print(f"\nFetching {url}")
    html = fetch(url)

    # First try to find lessonData JSON
    lesson = extract_lesson_data(html)
    if lesson:
        print(f"  Found lessonData with keys: {list(lesson.keys())[:10]}")
        return lesson, html

    # If not found, look for JSON-like data in script tags
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for i, s in enumerate(scripts):
        if 'questions' in s and ('correct' in s or 'answer' in s):
            print(f"  Interesting script #{i} (len={len(s)}): {s[:200]}")

    return None, html

def extract_from_lessondata(lesson, source_id, provpass):
    """Extract questions if lessonData structure is known."""
    questions_raw = lesson.get('questions', [])
    if isinstance(questions_raw, dict):
        questions_raw = list(questions_raw.values())

    results = []
    for q in questions_raw:
        if not isinstance(q, dict):
            continue
        qt = strip_tags(q.get('question', '') or q.get('text', '') or '')
        if not qt:
            continue
        opts_raw = q.get('options', q.get('answers', q.get('choices', [])))
        correct = q.get('correct', q.get('correctAnswer', q.get('correct_answer', '')))
        passage = strip_tags(q.get('passage', '') or q.get('context', '') or '')
        results.append({
            'question': qt,
            'options': opts_raw,
            'correct': str(correct),
            'passage': passage,
        })
    return results

def scrape_all():
    all_new = []
    for source_id, provpass, slug in PAGES:
        lesson, html = parse_page(source_id, provpass, slug)

        if lesson:
            qs = extract_from_lessondata(lesson, source_id, provpass)
            print(f"  lessonData path: {len(qs)} questions")
        else:
            print(f"  No lessonData found — trying HTML extraction")
            # Dump first 3000 chars of interesting script content
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
            for s in scripts:
                if len(s) > 500 and ('question' in s.lower() or 'passage' in s.lower()):
                    print(f"  Script snippet: {s[:400]}")
                    break
            qs = []

        for i, q in enumerate(qs, 1):
            all_new.append({
                'source': source_id,
                'provpass': provpass,
                'num': i,
                **q,
            })

    return all_new

if __name__ == '__main__':
    results = scrape_all()
    print(f"\nTotal questions found: {len(results)}")
    for r in results[:5]:
        print(f"  [{r['source']}] Q{r['num']}: {r['question'][:60]}")
        print(f"    passage: {r['passage'][:60]}")
        print(f"    correct: {r['correct']}")
