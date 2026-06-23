import fitz, re
from pathlib import Path

for fname in Path("Gamla_HP").glob("2014-04-05_provpass*verb*.pdf"):
    doc = fitz.open(str(fname))
    lines = []
    for pg in doc:
        words = pg.get_text("words")
        if not words: continue
        cx = pg.rect.width / 2
        ql = [w for w in words if re.match(r"^\d+\.$", w[4]) and w[0] < cx]
        qr = [w for w in words if re.match(r"^\d+\.$", w[4]) and w[0] >= cx]
        def to_lines(ws):
            ws = sorted(ws, key=lambda w: (round(w[1]/4)*4, w[0]))
            ls, cy, cw = [], None, []
            for w in ws:
                y = round(w[1]/4)*4
                if cy is None or abs(y-cy) > 4:
                    if cw: ls.append(" ".join(cw))
                    cw = [w[4]]; cy = y
                else: cw.append(w[4])
            if cw: ls.append(" ".join(cw))
            return ls
        if ql and qr:
            qt = min(w[1] for w in ql+qr)
            above = [w for w in words if w[1] < qt-5]
            below = [w for w in words if w[1] >= qt-5]
            page_lines = to_lines(above) + to_lines([w for w in below if w[0]<cx]) + to_lines([w for w in below if w[0]>=cx])
        else:
            page_lines = to_lines(words)
        lines.extend(page_lines)
    doc.close()

    # Find q11 context
    for i, l in enumerate(lines):
        if re.match(r"^11\.", l.strip()):
            print(f"\n=== {fname.name} q11 ===")
            for ll in lines[i:i+15]:
                print(repr(ll))
            break
