"""Find HTML structure for one question block on eddler."""
import re

with open('eddler_raw.html', encoding='utf-8', errors='replace') as f:
    html = f.read()

# Extract questions dict from lessonData
m = re.search(r'"questions"\s*:\s*(\{".*?(?:\}\})+)', html, re.DOTALL)
if m:
    # Get the correct answers from the questions JSON
    # Find each ID and its correctAnswer
    answers = re.findall(r'"(\d+)"\s*:\s*\{"id":\d+,"customData":\{"correctAnswer":"(answer_\d+)"', m.group(1))
    print("Correct answers by ID:")
    for qid, ans in answers:
        letter = chr(ord('A') + int(ans.split('_')[1]) - 1)
        print(f"  {qid}: {ans} -> {letter}")
    print()

# Find the HTML blocks for each question
# Look for patterns around question IDs
qid_sample = answers[0][0] if answers else '4868029'
idx = html.find(qid_sample)
print(f"First occurrence of ID {qid_sample} at index {idx}")
# Print surrounding HTML
start = max(0, idx - 500)
end = min(len(html), idx + 3000)
print(html[start:end])
