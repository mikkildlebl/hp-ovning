"""Inspect the raw eddler HTML structure to understand question/answer locations."""
import re

with open('eddler_raw.html', encoding='utf-8', errors='replace') as f:
    html = f.read()

# 1. Print full lessonData block
m = re.search(r'window\.lessonData\s*=\s*\{(.*?)\};', html, re.DOTALL)
if m:
    block = m.group(1)
    print("=== lessonData (first 3000 chars) ===")
    print(block[:3000])
    print()

# 2. Look for question-specific data — dkResetQuestion blocks
resets = re.findall(r'window\.(dkResetQuestion_\d+)\s*=\s*function\(\)\s*\{(.*?)\}', html, re.DOTALL)
print(f"dkResetQuestion functions: {len(resets)}")
for name, body in resets[:3]:
    print(f"  {name}: {body.strip()[:100]}")

# 3. Look for correct-answer attributes in HTML
correct_attrs = re.findall(r'correct-answer=["\']([A-D])["\']', html)
print(f"\ncorrect-answer attributes: {correct_attrs}")

# 4. Look for data-correct or data-answer
data_attrs = re.findall(r'data-(?:correct|answer)[^=]*=["\']([^"\']+)["\']', html, re.I)
print(f"data-correct/answer: {data_attrs[:20]}")

# 5. Find question blocks — look for divs with question IDs
q_divs = re.findall(r'id="question[_-](\d+)"[^>]*>(.*?)</div>', html, re.DOTALL)
print(f"\nQuestion divs by id: {len(q_divs)}")

# 6. Look for passage text around "quiz" or "passage" class
passage_blocks = re.findall(r'class="[^"]*passage[^"]*"[^>]*>(.*?)</(?:div|p|section)>', html, re.DOTALL)
print(f"Passage-class blocks: {len(passage_blocks)}")
for p in passage_blocks[:2]:
    print(f"  {p[:200]}")

# 7. Find any JSON-like structures with "correct" key
json_bits = re.findall(r'\{[^{}]{0,200}["\']correct["\']\s*:[^{}]{0,100}\}', html)
print(f"\nJSON bits with 'correct': {len(json_bits)}")
for j in json_bits[:5]:
    print(f"  {j[:150]}")

# 8. Look for lessonData.questions
q_in_lesson = re.search(r'["\']questions["\']\s*:\s*(\[.*?\]|\{.*?\})', html, re.DOTALL)
if q_in_lesson:
    print(f"\nquestions in lessonData: {q_in_lesson.group(1)[:500]}")

# 9. Print all unique class names on the page
classes = set(re.findall(r'class="([^"]+)"', html))
interesting = [c for c in classes if any(kw in c.lower() for kw in ['question','answer','passage','option','choice','correct','text','content'])]
print(f"\nInteresting CSS classes: {sorted(interesting)[:40]}")

# 10. Print a 2000-char window around "correct"
idx = html.find('"correct"')
if idx < 0:
    idx = html.find("'correct'")
if idx >= 0:
    print(f"\n=== Around 'correct' (idx {idx}) ===")
    print(html[max(0,idx-300):idx+500])
