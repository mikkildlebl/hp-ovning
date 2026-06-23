"""Test column-aware extraction on a few exams and show the resulting passage text."""
import json, sys
sys.path.insert(0, '.')
from extract_las import extract_las_passages, find_pdf

tests = [
    ('2019-04-06', 1),   # new format, 3 passages
    ('2013-10-26', 1),   # old format
    ('2022-03-12', 2),   # Stilla natt
]

for exam, pp in tests:
    pdf = find_pdf(exam, pp)
    if not pdf:
        print(f'MISSING: {exam} pp{pp}')
        continue
    passages = extract_las_passages(pdf)
    print(f'=== {exam} pp{pp}: {len(passages)} passages ===')
    for title, text in passages:
        print(f'  Title: {repr(title)}')
        print(f'  Text ({len(text)}b): {repr(text[:200])}')
        print()
