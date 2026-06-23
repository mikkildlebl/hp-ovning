import json
from collections import defaultdict

with open('hp_questions.json', encoding='utf-8') as f:
    data = json.load(f)

qs = data['questions']
bad_ans = defaultdict(list)
no_opts = defaultdict(list)

for q in qs:
    qt = q['question_type']
    for iss in q.get('validation_issues', []):
        if 'not found in options' in iss:
            bad_ans[qt].append(q)
        if 'no options' in iss:
            no_opts[qt].append(q)

print('=== Answer not in options ===')
for k, v in sorted(bad_ans.items()):
    print(f'  {k}: {len(v)}')
    for q in v[:5]:
        src = q['all_sources'][0]
        opts = ' || '.join(q['options'][:5])
        num = q['question_number']
        exam = src['exam']
        ans = q['correct_answer']
        print(f'    q{num} [{exam}] ans={ans}: {repr(opts[:90])}')

print()
print('=== Missing options ===')
for k, v in sorted(no_opts.items()):
    print(f'  {k}: {len(v)}')
    for q in v[:4]:
        src = q['all_sources'][0]
        num = q['question_number']
        exam = src['exam']
        txt = q['question_text'][:80]
        print(f'    q{num} [{exam}] text: {repr(txt)}')
