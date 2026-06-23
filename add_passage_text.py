"""Add passage_text field to all LAS questions in hp_questions.json."""
import json, os

JSON_PATH = r'C:\Users\Mikael\Documents\Claude code\HP\hp_questions.json'
TEXTS_DIR = r'C:\Users\Mikael\Documents\Claude code\HP\texts'

with open(JSON_PATH, encoding='utf-8') as f:
    data = json.load(f)

# Cache passage file contents
cache = {}
def get_text(pf):
    if pf not in cache:
        path = os.path.join(TEXTS_DIR, pf)
        cache[pf] = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
    return cache[pf]

updated = 0
missing = 0
for q in data['questions']:
    if q.get('question_type') != 'LAS':
        continue
    pf = q.get('passage_file')
    if not pf:
        continue
    text = get_text(pf)
    if text:
        q['passage_text'] = text
        updated += 1
    else:
        missing += 1

print(f'Updated: {updated}  Missing text: {missing}')

with open(JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Saved hp_questions.json')
