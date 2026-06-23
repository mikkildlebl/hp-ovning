"""
Scrape ELF questions from eddler.se lesson pages and add to hp_questions.json.
Each page has 10 ELF questions with passages, options, and correct answers embedded in HTML.
"""
import urllib.request, re, json, os, hashlib, time

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
    s = re.sub(r'&#8220;', '“', s)
    s = re.sub(r'&#8221;', '”', s)
    s = re.sub(r'&#8211;', '–', s)
    s = re.sub(r'&#8230;', '...', s)
    s = re.sub(r'&#\d+;', '', s)
    s = re.sub(r'&[a-z]+;', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def extract_correct_answers(html):
    """Return {question_id_str: 'A'/'B'/'C'/'D'} from lessonData JS blob."""
    pairs = re.findall(r'"id":(\d+),"customData":\{"correctAnswer":"answer_(\d)"', html)
    return {qid: chr(ord('A') + int(n) - 1) for qid, n in pairs}

def parse_page_html(html):
    """
    Extract interleaved passage and question blocks.

    Passages: <li class="wp-education-examination-question"> with NO id,
              containing we-question-content-text > h2 + p tags.
    Questions: <li id="wp-education-examination-question_ID">
               Question text in <b>...</b> inside class="question..."
               Options in <label for="dk-question_ID-answer_N">TEXT</label>

    Strategy for questions: use each question's unique ID to find and extract
    its block with a large window (avoids nested-LI slicing problem).
    Strategy for passages: look for passage LIs between question LIs by position.
    """
    ul_start = html.find('class="wp-education-examination-questions')
    if ul_start < 0:
        return []

    # --- Collect question positions and data ---
    q_starts = {}  # qid -> start position in html
    for m in re.finditer(r'<li\s[^>]*id="wp-education-examination-question_(\d+)"', html):
        if m.start() > ul_start:
            q_starts[m.group(1)] = m.start()

    questions = {}
    for qid, pos in q_starts.items():
        window = html[pos:pos + 50000]  # large enough for full question block

        # Format A: <div class="question ..."><b>TEXT</b></div>
        qt_m = re.search(r'class="question[^"]*"[^>]*>\s*<b>(.*?)</b>', window, re.DOTALL)
        if not qt_m:
            # Format B: we-question-content-text'><p><strong>TEXT</strong></p>
            qt_m = re.search(r"we-question-content-text['\"][^>]*>\s*<p[^>]*>\s*<strong>(.*?)</strong>", window, re.DOTALL)
        q_text = strip_tags(qt_m.group(1)) if qt_m else ''

        opt_re = re.compile(r'for="dk-question_' + qid + r'-answer_(\d+)">(.*?)</label>', re.DOTALL)
        options = []
        for n_str, opt_html in sorted(opt_re.findall(window), key=lambda x: int(x[0])):
            options.append(f"{chr(ord('A') + int(n_str) - 1)} {strip_tags(opt_html)}")

        # Filter out passage titles mismatched as questions (too short, no "?")
        is_valid = q_text and options and (q_text.endswith('?') or len(q_text) >= 40)
        if is_valid:
            questions[qid] = {'id': qid, 'text': q_text, 'options': options, 'pos': pos}

    # --- Collect passage positions ---
    # Method 1: dedicated passage LIs (no question id) with we-question-content-text
    passages = []
    seen_passage_pos = set()
    for m in re.finditer(
            r'<li\s+class="wp-education-examination-question"(?!\s*[^>]*\bid=)[^>]*>'
            r'.*?class="we-question-content-text"[^>]*>(.*?)</div>\s*</div>\s*</div>\s*</li>',
            html, re.DOTALL):
        if m.start() < ul_start:
            continue
        inner = m.group(1)
        title_m = re.search(r'<h[12][^>]*>(.*?)</h[12]>', inner, re.DOTALL)
        title = strip_tags(title_m.group(1)) if title_m else ''
        paras = re.findall(r'<p[^>]*>(.*?)</p>', inner, re.DOTALL)
        passage = ' '.join(strip_tags(p) for p in paras if strip_tags(p))
        if passage:
            passages.append({'title': title, 'text': passage, 'pos': m.start()})
            seen_passage_pos.add(m.start())

    # Method 2: fallback — find h2+p blocks between question LI positions
    if not passages:
        q_pos_sorted = sorted(q_starts.values())
        boundaries = [ul_start] + q_pos_sorted
        for i, seg_start in enumerate(boundaries[:-1]):
            seg_end = boundaries[i + 1]
            seg = html[seg_start:seg_end]
            h2s = re.findall(r'<h[12][^>]*>(.*?)</h[12]>', seg, re.DOTALL)
            paras = re.findall(r'<p[^>]*>(.*?)</p>', seg, re.DOTALL)
            paras = [strip_tags(p) for p in paras if len(strip_tags(p)) > 40]
            if paras:
                title = strip_tags(h2s[0]) if h2s else ''
                passage = ' '.join(paras)
                passages.append({'title': title, 'text': passage, 'pos': seg_start})

    # --- Merge: assign each question to the most recent preceding passage ---
    # Sort questions by position
    sorted_qs = sorted(questions.values(), key=lambda q: q['pos'])
    sorted_ps = sorted(passages, key=lambda p: p['pos'])

    items = []
    p_idx = 0
    last_passage = {'title': '', 'text': ''}
    for q in sorted_qs:
        # Advance through passages that come before this question
        while p_idx < len(sorted_ps) and sorted_ps[p_idx]['pos'] < q['pos']:
            last_passage = sorted_ps[p_idx]
            items.append({'type': 'passage', **last_passage})
            p_idx += 1
        items.append({'type': 'question', **q, 'passage': last_passage})

    return items

def make_id(source, n):
    return hashlib.md5(f"eddler-{source}-{n}".encode()).hexdigest()[:12]

def save_passage(title, text):
    key = hashlib.md5((title + text[:80]).encode()).hexdigest()[:16] + '.txt'
    full = (title + '\n\n' + text).strip() if title else text.strip()
    for d in [TEXTS_DIR, HP_TEXTS]:
        with open(os.path.join(d, key), 'w', encoding='utf-8') as f:
            f.write(full)
    return key, full

def scrape_page(source_id, provpass, slug):
    url = f'https://eddler.se/lektioner/{slug}/'
    html = fetch(url)

    correct_map = extract_correct_answers(html)
    items = parse_page_html(html)

    n_passages = sum(1 for i in items if i['type'] == 'passage')
    n_questions = sum(1 for i in items if i['type'] == 'question')
    print(f"  correct_map: {len(correct_map)}  passages: {n_passages}  questions: {n_questions}")

    results = []
    q_num = 0
    for item in items:
        if item['type'] == 'question':
            q_num += 1
            p = item['passage']
            results.append({
                'source':        source_id,
                'provpass':      provpass,
                'num':           q_num,
                'passage_title': p['title'],
                'passage_text':  p['text'],
                'question':      item['text'],
                'options':       item['options'],
                'correct':       correct_map.get(item['id'], ''),
            })
    return results

def main():
    with open(JSON_PATH, encoding='utf-8') as f:
        data = json.load(f)

    # Remove previously scraped eddler entries
    before = len(data['questions'])
    data['questions'] = [q for q in data['questions']
                         if not q.get('source_exam', '').startswith('eddler-')]
    removed = before - len(data['questions'])
    if removed:
        print(f"Removed {removed} old eddler entries\n")

    all_new = []
    for source_id, provpass, slug in PAGES:
        print(f"Scraping {source_id} (pass {provpass})...")
        try:
            qs = scrape_page(source_id, provpass, slug)
            for q in qs:
                print(f"    Q{q['num']}: {q['question'][:55]}  [{q['correct']}]")
            all_new.extend(qs)
            time.sleep(1)
        except Exception as e:
            print(f"  ERROR: {e}")

    print(f"\nBuilding {len(all_new)} new entries...")
    passage_cache = {}
    new_entries = []
    global_n = 0

    for q in all_new:
        global_n += 1
        cache_key = (q['source'], q['passage_title'])
        if cache_key not in passage_cache:
            fname, full = save_passage(q['passage_title'], q['passage_text'])
            passage_cache[cache_key] = (fname, full)
        fname, full = passage_cache[cache_key]

        new_entries.append({
            'source_exam':     f"eddler-{q['source']}",
            'provpass':        q['provpass'],
            'question_type':   'ELF',
            'question_number': q['num'],
            'question_text':   q['question'],
            'options':         q['options'],
            'correct_answer':  q['correct'],
            'id':              make_id(q['source'], global_n),
            'passage_file':    fname,
            'passage_text':    full,
        })

    data['questions'].extend(new_entries)
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    elf_total = sum(1 for q in data['questions'] if q.get('question_type') == 'ELF')
    print(f"Done. Total questions: {len(data['questions'])}  ELF total: {elf_total}")

if __name__ == '__main__':
    main()
