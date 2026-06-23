"""Debug passage and question extraction on hpvar2023p3 live HTML."""
import re

def strip_tags(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&[#a-zA-Z0-9]+;', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

with open('eddler_var2023p3.html', encoding='utf-8', errors='replace') as f:
    html = f.read()

ul_start = html.find('class="wp-education-examination-questions')
print(f"UL start: {ul_start}")

# 1. Check passage LI regex
print("\n--- Passage LI regex test ---")
passage_re = re.compile(
    r'<li\s+class="wp-education-examination-question"(?!\s*[^>]*\bid=)[^>]*>'
    r'.*?class="we-question-content-text">(.*?)</div>\s*</div>\s*</div>\s*</li>',
    re.DOTALL)
pm = list(passage_re.finditer(html))
print(f"Passage LI matches: {len(pm)}")
for m in pm[:3]:
    print(f"  pos={m.start()}, inner={m.group(1)[:80]}")

# 2. Why does it fail? Try simpler passage detection
print("\n--- Simple: h2 between UL and first question ---")
q_id_re = re.compile(r'id="wp-education-examination-question_(\d+)"')
first_q = q_id_re.search(html, ul_start)
if first_q:
    pre_q = html[ul_start:first_q.start()]
    h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', pre_q, re.DOTALL)
    paras = re.findall(r'<p[^>]*>(.*?)</p>', pre_q, re.DOTALL)
    print(f"  h2 tags before Q1: {[strip_tags(h) for h in h2s]}")
    print(f"  p tags before Q1: {len(paras)}")
    for p in paras[:3]:
        print(f"    {strip_tags(p)[:80]}")

# 3. Check question block regex on live HTML
print("\n--- Question regex test ---")
q_starts = {}
for m in q_id_re.finditer(html):
    if m.start() > ul_start:
        qid = m.group(1)
        if qid not in q_starts:
            q_starts[qid] = m.start()

print(f"Question IDs found: {len(q_starts)}")
for qid, pos in list(q_starts.items())[:2]:
    window = html[pos:pos + 50000]
    qt_m = re.search(r'class="question[^"]*"[^>]*>\s*<b>(.*?)</b>', window, re.DOTALL)
    opts = re.findall(r'for="dk-question_' + qid + r'-answer_(\d+)">(.*?)</label>', window, re.DOTALL)
    q_text = strip_tags(qt_m.group(1)) if qt_m else 'NOT FOUND'
    print(f"  {qid}: q_text={q_text[:60]!r}  opts={len(opts)}")
    if not qt_m:
        # Show what's near 'question' class
        idx = window.find('class="question')
        if idx >= 0:
            print(f"    question class found at offset {idx}: {window[idx:idx+200]}")
        else:
            print(f"    'class=\"question' NOT FOUND in window")
            # Check for we-question-content-text
            idx2 = window.find('we-question-content-text')
            if idx2 >= 0:
                print(f"    we-question-content-text at {idx2}: {window[idx2:idx2+300]}")
