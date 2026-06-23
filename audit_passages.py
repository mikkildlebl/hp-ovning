"""
Audit all LAS passage files to find ones that look like they have wrong content:
- starts mid-sentence (lowercase, dash, etc.)
- starts with answer option fragments (A, B, C, D pattern)
- very short even if above stub threshold
"""
import json, os, re

with open(r'C:\Users\Mikael\Documents\Claude code\HP\hp_questions.json', encoding='utf-8') as f:
    data = json.load(f)

texts_dir = r'C:\Users\Mikael\Documents\Claude code\HP\texts'

# Collect all unique passage files and the questions that reference them
passage_info = {}
for q in data['questions']:
    if q.get('question_type') != 'LAS' or not q.get('passage_file'):
        continue
    pf = q['passage_file']
    if pf not in passage_info:
        passage_info[pf] = {'questions': [], 'exam': q['source_exam'], 'provpass': q['provpass']}
    passage_info[pf]['questions'].append(q)

print(f'Total unique passage files: {len(passage_info)}\n')

bad_files = []
for pf, info in sorted(passage_info.items()):
    path = os.path.join(texts_dir, pf)
    if not os.path.exists(path):
        bad_files.append((pf, 'MISSING', '', info))
        continue
    size = os.path.getsize(path)
    content = open(path, encoding='utf-8').read()
    first_char = content[0] if content else ''
    first_line = content.split('\n')[0][:80] if content else ''

    issues = []
    if size < 600:
        issues.append(f'STUB({size}b)')
    if first_char.islower() or first_char in ('–', '-', '»', '•'):
        issues.append('STARTS-LOWER')
    if re.match(r'^[A-E]\s+\S', content):
        issues.append('STARTS-OPTION')
    if re.match(r'^\d+\.', content):
        issues.append('STARTS-NUMBER')
    if content.startswith('Uppgifter'):
        issues.append('UPPGIFTER')

    if issues:
        bad_files.append((pf, ' '.join(issues), first_line, info))

print(f'Files with potential issues: {len(bad_files)}')
for pf, issue, first_line, info in bad_files:
    exam = info['exam']
    pp = info['provpass']
    qnums = sorted(set(q['question_number'] for q in info['questions']))
    print(f'\n  {pf} [{issue}]')
    print(f'    Exam: {exam} pp{pp}, q{qnums}')
    print(f'    Content: {repr(first_line[:70])}')
