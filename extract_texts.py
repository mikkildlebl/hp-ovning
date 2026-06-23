"""
Re-extract LAS passage texts from the verbal HP PDFs.
Saves them to HP/texts/ using the same MD5-hash naming as the original extractor,
so hp_questions.json passage_file references resolve correctly.
"""
import re, hashlib, os
from pathlib import Path
import fitz

BASE      = Path(__file__).resolve().parent
INPUT_DIR = BASE / "Gamla_HP"
TEXTS_DIR = BASE / "texts"
TEXTS_DIR.mkdir(exist_ok=True)

# Load expected passage filenames from JSON so we can verify matches
import json
data = json.load(open(BASE / "hp_questions.json", encoding="utf-8"))
expected = {q["passage_file"] for q in data["questions"] if q.get("passage_file")}
print(f"Expected passage files in JSON: {len(expected)}")

# ── Text extraction helpers (mirror the extractor) ────────────────────────────

def page_lines(page):
    words = page.get_text("words")
    if not words:
        return []
    words = sorted(words, key=lambda w: (round(w[1] / 4) * 4, w[0]))
    lines, cy, cw = [], None, []
    for w in words:
        y = round(w[1] / 4) * 4
        if cy is None or abs(y - cy) > 4:
            if cw:
                lines.append(" ".join(cw))
            cw = [w[4]]
            cy = y
        else:
            cw.append(w[4])
    if cw:
        lines.append(" ".join(cw))
    return lines

SECTION_RE = re.compile(
    r"^(DELPROV\s+)?(LÄS|LAS|ORD|MEK|ELF|XYZ|KVA|NOG|DTK)\b", re.I
)
Q_RE   = re.compile(r"^(\d{1,2})\.\s+\S")
SKIP_RE = re.compile(
    r"^([–\-]\s*\d+\s*[–\-]"
    r"|Uppgifter$|Tillr|Börja inte|Svarsh|Provtiden"
    r"|Fyll|Följ|Du (får|måste)|På nästa|Prov\s+Antal"
    r"|Antal uppgifter|Högskoleprov|Provpass \d"
    r"|Kvantitativ|Verbal|Rekommenderad|Detta provh)",
    re.I,
)

def save_passage(text):
    name = hashlib.md5(text.encode()).hexdigest()[:16] + ".txt"
    path = TEXTS_DIR / name
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return name

def extract_passages_from_pdf(pdf_path):
    """Yield passage texts found in a verbal PDF."""
    doc = fitz.open(str(pdf_path))
    in_las = False
    passage_buf = []
    passages = []

    def commit():
        nonlocal passage_buf
        text = " ".join(passage_buf).strip()
        passage_buf = []
        if len(text) > 80:  # ignore tiny fragments
            passages.append(text)

    for page in doc:
        lines = page_lines(page)
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if SKIP_RE.match(line):
                continue

            m = SECTION_RE.match(line)
            if m:
                sec = m.group(2).upper().replace("LÄS", "LAS")
                commit()
                in_las = (sec in ("LAS", "ELF"))
                continue

            if Q_RE.match(line):
                # Question starts → commit buffered passage
                commit()
                continue

            if in_las:
                passage_buf.append(line)

    commit()
    doc.close()
    return passages

# ── Main ──────────────────────────────────────────────────────────────────────

verbal_pdfs = sorted(INPUT_DIR.glob("*verb*.pdf"))
print(f"Verbal PDFs found: {len(verbal_pdfs)}")

saved = 0
matched = 0

for pdf_path in verbal_pdfs:
    passages = extract_passages_from_pdf(pdf_path)
    for text in passages:
        name = save_passage(text)
        saved += 1
        if name in expected:
            matched += 1

print(f"\nPassages extracted: {saved}")
print(f"Matched expected filenames: {matched} / {len(expected)}")
missing = expected - {f.name for f in TEXTS_DIR.iterdir()}
print(f"Still missing: {len(missing)}")
if missing:
    print("Sample missing:", list(missing)[:5])
