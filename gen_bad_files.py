import json
with open('hp_questions.json', encoding='utf-8') as f:
    data = json.load(f)
pfs = sorted(set(q['passage_file'] for q in data['questions'] if q.get('question_type')=='LAS' and q.get('passage_file')))
print(f'# {len(pfs)} files')
for p in pfs:
    print(f"        {repr(p)},")
