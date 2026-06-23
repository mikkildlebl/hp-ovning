"""Find the full question+options+passage HTML structure on eddler."""
import re

with open('eddler_raw.html', encoding='utf-8', errors='replace') as f:
    html = f.read()

# Find the first question LI block — from its start to the next question LI
q_li_re = re.compile(r'<li\s[^>]*id="wp-education-examination-question_(\d+)"', re.DOTALL)
matches = list(q_li_re.finditer(html))
print(f"Found {len(matches)} question LI elements")

# Print the block between first and second question (to see full first question)
if len(matches) >= 2:
    start = matches[0].start()
    end = matches[1].start()
    print(f"\n=== First question block ({end-start} chars) ===")
    print(html[start:end])
    print()

# Now find passage blocks — they appear to be in separate divs/cards before questions
# Let's look at what's just before the first question LI
pre_start = max(0, matches[0].start() - 3000)
print(f"\n=== 3000 chars before first question ===")
print(html[pre_start:matches[0].start()])
