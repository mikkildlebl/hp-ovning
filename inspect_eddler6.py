"""Inspect hpvar2023p3 for passage text structure and hpmaj2022p3 UL bug."""
import re

# 1. Check hpvar2023p3 for passage text
with open('eddler_var2023p3.html', encoding='utf-8', errors='replace') as f:
    html23 = f.read()

print("=== hpvar2023p3 ===")
q_ids = re.findall(r'id="wp-education-examination-question_(\d+)"', html23)
print(f"Question IDs: {q_ids}")

# What's before the first question?
first_q_idx = html23.find(f'id="wp-education-examination-question_{q_ids[0]}"')
pre = html23[max(0, first_q_idx - 3000):first_q_idx]

# Look for any passage-like content
print("\nLooking for text content before first question...")
# Strip all tags and show non-empty text
text_chunks = re.findall(r'>([A-Z][^<]{80,})', pre)
for c in text_chunks[:5]:
    print(f"  {c[:120]}")

# Check for dk-text-card or similar passage container classes
text_cards = re.findall(r'class="([^"]*(?:text|passage|card|content)[^"]*)"', pre, re.I)
print(f"\nPassage-related classes before Q1: {set(text_cards)}")

# Look for w3-container OR dk-text anywhere in full html
w3 = len(re.findall(r'class="w3-container"', html23))
dk_text = len(re.findall(r'class="[^"]*dk-text[^"]*"', html23))
print(f"\nw3-container: {w3}, dk-text classes: {dk_text}")

# 2. Check hpmaj2022p3 UL parsing bug
print("\n\n=== hpmaj2022p3 UL parsing ===")
with open('eddler_raw.html', encoding='utf-8', errors='replace') as f:
    html22 = f.read()

ul_m = re.search(r'class="wp-education-examination-questions[^"]*"[^>]*>(.*?)</ul>', html22, re.DOTALL)
if ul_m:
    content = ul_m.group(1)
    q_ids_in_ul = re.findall(r'id="wp-education-examination-question_(\d+)"', content)
    print(f"Questions found in UL content: {len(q_ids_in_ul)} -> {q_ids_in_ul}")
    print(f"UL content length: {len(content)} chars")
    # The first </ul> is closing the answer list of the first question
    first_ul_end = html22.find('</ul>', ul_m.start())
    print(f"First </ul> after UL start: {first_ul_end - ul_m.start()} chars in")
else:
    print("UL not found!")

# Count all question LI IDs in full html22
all_qids = re.findall(r'id="wp-education-examination-question_(\d+)"', html22)
print(f"\nAll question IDs in full html: {all_qids}")
