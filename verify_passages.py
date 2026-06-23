import json, os

with open(r'C:\Users\Mikael\Documents\Claude code\HP\hp_questions.json', encoding='utf-8') as f:
    data = json.load(f)

texts_dir = r'C:\Users\Mikael\Documents\Claude code\HP\texts'

check_pairs = [
    ('2019-04-06', 1),
    ('2022-03-12', 2),
    ('2025-04-05', 2),
    ('2021-10-24', 2),
    ('2024-10-20', 3),
]

for exam, pp in check_pairs:
    las_qs = [q for q in data['questions']
              if q['source_exam'] == exam and q['provpass'] == pp
              and q['question_type'] == 'LAS']
    las_qs.sort(key=lambda x: x['question_number'])
    print(f'=== {exam} pp{pp} ===')
    seen = set()
    for q in las_qs:
        pf = q['passage_file']
        if pf in seen:
            continue
        seen.add(pf)
        path = os.path.join(texts_dir, pf)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        content = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
        qnum = q['question_number']
        print(f'  q{qnum:2d} {pf} ({size}b): {repr(content[:100])}')
    print()
