import json

with open('hp_questions.json', encoding='utf-8') as f:
    qs = json.load(f)['questions']

# Show the actual q11 [2014-04-05] that has the validation issue
for q in qs:
    if (q['question_type'] == 'LAS'
            and q['question_number'] == 11
            and any(s['exam'] == '2014-04-05' for s in q['all_sources'])
            and q.get('validation_issues')):
        print("question_text:", q['question_text'][:100])
        print("options:", q['options'])
        print("answer:", q['correct_answer'])
        print("issues:", q['validation_issues'])
        print()
