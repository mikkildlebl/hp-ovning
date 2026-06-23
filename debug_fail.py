"""Debug remaining validation failures — show raw fitz lines around the failing questions."""
import fitz, pdfplumber, re
from pathlib import Path

TARGET_FILE_QUESTIONS = [
    ("Gamla_HP/2013-10-26_provpass-3-kvant.pdf", [2, 10]),
    ("Gamla_HP/2015-03-28_provpass-2-kvant.pdf", [6]),
    ("Gamla_HP/2016-10-29_provpass-3-kvant.pdf", [7]),
    ("Gamla_HP/2018-10-21_provpass-2-kvant.pdf", [3]),
    ("Gamla_HP/2015-10-24_provpass-3-kvant.pdf", [1]),
]

def raw_lines(path):
    doc = fitz.open(str(path))
    lines = []
    for pg in doc:
        words = pg.get_text("words")
        if not words: continue
        ws = sorted(words, key=lambda w: (round(w[1]/4)*4, w[0]))
        cy, cw = None, []
        for w in ws:
            y = round(w[1]/4)*4
            if cy is None or abs(y-cy) > 4:
                if cw: lines.append(" ".join(cw))
                cw = [w[4]]; cy = y
            else: cw.append(w[4])
        if cw: lines.append(" ".join(cw))
    doc.close()
    return lines

def plumber_lines(path):
    result = []
    with pdfplumber.open(str(path)) as pdf:
        for pg in pdf.pages:
            result.extend((pg.extract_text() or "").splitlines())
    return result

BASE = Path(__file__).parent

for rel_path, qnums in TARGET_FILE_QUESTIONS:
    path = BASE / rel_path
    if not path.exists():
        print(f"MISSING: {rel_path}"); continue

    fl = raw_lines(path)
    pl = plumber_lines(path)
    winner = "pdfplumber" if len(pl) > len(fl) * 1.5 else "fitz"
    print(f"\n=== {path.name}  fitz={len(fl)} plumb={len(pl)}  winner={winner} ===")

    lines = pl if winner == "pdfplumber" else fl

    for qn in qnums:
        pat = re.compile(rf"^{qn}\.")
        for i, l in enumerate(lines):
            if pat.match(l.strip()):
                print(f"  --- q{qn} ---")
                for ll in lines[i:i+14]:
                    print(f"  {repr(ll)}")
                break
