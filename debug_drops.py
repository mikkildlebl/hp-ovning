import sys; sys.path.insert(0, '.')
import extract_hp_questions as ex
from pathlib import Path
from collections import Counter

PASSAGE_SECTIONS = ex.PASSAGE_SECTIONS

def _is_droppable_debug(q):
    qt = q['question_type']
    has_ans  = bool(q.get('correct_answer'))
    has_opts = bool(q.get('options'))
    if qt in PASSAGE_SECTIONS and not has_opts:
        return 'LAS/ELF no opts'
    if not has_ans and not has_opts:
        return 'no ans + no opts'
    if any('.indd' in o for o in q.get('options', [])):
        return 'indd artifact'
    return None

all_pdfs  = sorted(Path('Gamla_HP').glob('*.pdf'))
exam_pdfs = [p for p in all_pdfs if 'provpass' in p.name.lower()
             and not any(e in p.name.lower() for e in ex.EXCLUDE_STEMS)]
facit_pdfs = [p for p in all_pdfs if 'facit' in p.name.lower()]

facit_lookup = {}
for p in facit_pdfs:
    facit_lookup.update(ex.parse_facit(p))

all_q = []
for path in exam_pdfs:
    meta = ex.parse_exam_filename(path)
    if meta is None:
        continue
    qs = ex.extract_questions(path, meta)
    date = meta['source_exam']
    pp   = meta['provpass']
    variant = meta.get('variant')
    for q in qs:
        qnum = q['question_number']
        ans = (facit_lookup.get((date, variant, pp, qnum))
               or facit_lookup.get((date, None, pp, qnum)))
        q['correct_answer'] = ans
    all_q.extend(qs)

deduped = ex.deduplicate(all_q)

drop_reasons = Counter()
seen = set()
for q in deduped:
    reason = _is_droppable_debug(q)
    if reason:
        qt = q['question_type']
        drop_reasons[(qt, reason)] += 1
        key = (qt, reason)
        if seen.count(key) if hasattr(seen, 'count') else key not in seen:
            if drop_reasons[key] <= 3:
                src = q['all_sources'][0]
                print(f"{qt} q{q['question_number']} [{src['exam']} pp{src['provpass']}] -> {reason}")
                print(f"  text: {repr(q['question_text'][:80])}")
                print(f"  opts: {q['options'][:2]}")
                print(f"  ans:  {q.get('correct_answer')}")

print()
for (qt, reason), cnt in sorted(drop_reasons.items()):
    print(f"  {qt} / {reason}: {cnt}")
