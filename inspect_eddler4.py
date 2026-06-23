"""Find question text, options and passage in eddler HTML."""
import re

with open('eddler_raw.html', encoding='utf-8', errors='replace') as f:
    html = f.read()

def strip_tags(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&[a-z#0-9]+;', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

# 1. Search for "What is argued" to find where question text appears
idx = html.find('What is argued')
print(f"'What is argued' found at index: {idx}")
if idx >= 0:
    print(html[max(0,idx-300):idx+500])
print()

# 2. Search for "Short-term business" (option A text)
idx2 = html.find('Short-term business')
print(f"'Short-term business' at: {idx2}")
if idx2 >= 0:
    print(html[max(0,idx2-300):idx2+800])
print()

# 3. Search for answer_1, answer_2 HTML patterns
ans_html = re.findall(r'answer_[1-4][^"\']{0,200}', html)
print(f"\nanswer_N patterns in HTML: {len(ans_html)}")
for a in ans_html[:5]:
    print(f"  {a[:150]}")
