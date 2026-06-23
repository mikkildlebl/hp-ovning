"""
Clean up hp_questions.json:
1. Remove soft hyphens (U+00AD) from all text fields — PDF extraction artifact
2. Remove questions with the placeholder passage file (empty passage)
3. Remove Unicode replacement chars (U+FFFD) — from bad encoding during scraping
4. Strip leading/trailing whitespace from all text fields
5. Report what was changed
"""
import json, re

JSON_PATH = r'C:\Users\Mikael\Documents\Claude code\HP\hp_questions.json'
PLACEHOLDER_FILE = 'd41d8cd98f00b204.txt'  # MD5 of empty string

def clean_text(s):
    if not isinstance(s, str):
        return s
    # Remove soft hyphens (U+00AD) — join word fragments
    s = s.replace('­', '')
    # Remove Unicode replacement characters (U+FFFD) from bad encoding
    s = s.replace('�', '')
    # Normalize whitespace (collapse multiple spaces, strip ends)
    s = re.sub(r'  +', ' ', s)
    s = s.strip()
    return s

def clean_question(q):
    changed = False
    fields = ['question_text', 'passage_text', 'passage_file', 'source_exam',
              'correct_answer', 'id']
    for f in fields:
        if f in q and isinstance(q[f], str):
            cleaned = clean_text(q[f])
            if cleaned != q[f]:
                q[f] = cleaned
                changed = True
    if 'options' in q and isinstance(q['options'], list):
        new_opts = [clean_text(o) for o in q['options']]
        if new_opts != q['options']:
            q['options'] = new_opts
            changed = True
    return changed

with open(JSON_PATH, encoding='utf-8') as f:
    data = json.load(f)

original_count = len(data['questions'])
print(f"Loaded {original_count} questions")

# Step 1: Remove placeholder-passage questions
placeholder_qs = [q for q in data['questions'] if q.get('passage_file') == PLACEHOLDER_FILE]
print(f"\nRemoving {len(placeholder_qs)} questions with empty placeholder passage:")
for q in placeholder_qs:
    print(f"  [{q.get('source_exam')}] {q.get('question_text', '')[:60]}")

data['questions'] = [q for q in data['questions'] if q.get('passage_file') != PLACEHOLDER_FILE]

# Step 2: Clean text fields on remaining questions
soft_hyphen_fixed = 0
replacement_char_fixed = 0
whitespace_fixed = 0

for q in data['questions']:
    orig = json.dumps(q, ensure_ascii=False)

    # Count before cleaning
    had_sh = '­' in orig
    had_rc = '�' in orig

    if clean_question(q):
        after = json.dumps(q, ensure_ascii=False)
        if had_sh and '­' not in after:
            soft_hyphen_fixed += 1
        if had_rc and '�' not in after:
            replacement_char_fixed += 1
        if not had_sh and not had_rc:
            whitespace_fixed += 1

print(f"\nText cleaning:")
print(f"  Soft hyphens removed: {soft_hyphen_fixed} questions")
print(f"  Replacement chars removed: {replacement_char_fixed} questions")
print(f"  Other whitespace fixed: {whitespace_fixed} questions")

# Step 3: Verify option format sanity — flag any option not starting with A-E
bad_opts = []
for q in data['questions']:
    for opt in (q.get('options') or []):
        if opt and opt.strip() and opt.strip()[0] not in 'ABCDE':
            bad_opts.append((q['id'], opt[:50]))
if bad_opts:
    print(f"\nOptions with unexpected first character ({len(bad_opts)}):")
    for qid, opt in bad_opts[:10]:
        print(f"  {qid}: {opt!r}")
else:
    print(f"\nOption format check: all OK")

# Step 4: Verify correct_answer
bad_answers = [(q['id'], q.get('correct_answer')) for q in data['questions']
               if q.get('correct_answer') not in ('A','B','C','D','E','')]
if bad_answers:
    print(f"\nBad correct_answer values ({len(bad_answers)}):")
    for qid, ans in bad_answers[:10]:
        print(f"  {qid}: {ans!r}")
else:
    print("correct_answer check: all OK")

# Save
final_count = len(data['questions'])
print(f"\nFinal count: {final_count} (removed {original_count - final_count})")

with open(JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("Saved hp_questions.json")
