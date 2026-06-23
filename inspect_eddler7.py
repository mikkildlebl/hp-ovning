"""Look at passage LI structure in hpvar2023p3."""
import re

with open('eddler_var2023p3.html', encoding='utf-8', errors='replace') as f:
    html = f.read()

# Split the HTML into LI blocks to see passage vs question blocks
# Find start of the question list UL
ul_start = html.find('class="wp-education-examination-questions')
print(f"UL starts at: {ul_start}")

# Get positions of all question LIs and the surrounding area
q_positions = [(m.start(), m.group(1)) for m in re.finditer(
    r'<li\s[^>]*id="wp-education-examination-question_(\d+)"', html)]
print(f"Question positions: {[(p, qid) for p, qid in q_positions[:3]]}")

# What's between UL start and first question?
first_q_pos = q_positions[0][0]
between = html[ul_start:first_q_pos]
print(f"\nBetween UL and Q1 ({len(between)} chars):")
print(between[-2000:])  # last 2000 chars before first question
