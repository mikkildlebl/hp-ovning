"""Find passage text blocks in eddler HTML."""
import re

with open('eddler_raw.html', encoding='utf-8', errors='replace') as f:
    html = f.read()

def strip_tags(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&[#a-zA-Z0-9]+;', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

# The passage text is somewhere before question LIs
# Let's find the section containing the first question
first_q = html.find('id="wp-education-examination-question_4868029"')
print(f"First question at: {first_q}")

# Print 5000 chars before first question to find passage
pre = html[max(0, first_q-5000):first_q]
print("=== 5000 chars before first question ===")
print(pre)
