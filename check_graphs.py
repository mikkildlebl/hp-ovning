import json
with open('hp_questions.json', encoding='utf-8') as f:
    qs = json.load(f)['questions']
graphs = [q for q in qs if q.get('graph_question')]
print(f'XYZ graph questions: {len(graphs)}')
for q in graphs[:4]:
    src = q['all_sources'][0]
    num = q['question_number']
    exam = src['exam']
    ans = q['correct_answer']
    txt = q['question_text'][:70]
    img = q.get('diagram_image', '(none)')
    opts = q.get('options', [])
    print(f'  q{num} [{exam}] ans={ans}')
    print(f'    text: {repr(txt)}')
    print(f'    opts: {opts}')
    print(f'    img:  {img}')
