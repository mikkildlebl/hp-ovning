"""
Render DTK diagram pages from PDFs into the images/ folder.
Reads diagram_image filenames from hp_questions.json, finds the source PDF
in Gamla_HP/, and renders the referenced page at 150 DPI.
"""
import json, re, sys
from pathlib import Path
import fitz  # PyMuPDF

BASE = Path(__file__).parent
GAMLA = BASE / "Gamla_HP"
OUT   = BASE / "images"
OUT.mkdir(exist_ok=True)

data = json.load(open(BASE / "hp_questions.json", encoding="utf-8"))
qs   = data["questions"]

imgs = {q["diagram_image"] for q in qs if q.get("diagram_image")}
print(f"{len(imgs)} unique diagram images to extract")

PAT = re.compile(r"(\d{4}-\d{2}-\d{2})_provpass-(\d+)-kvant(?:-v(\d+))?_p(\d+)\.png")

done = 0
skipped = 0
errors = []

for img_name in sorted(imgs):
    out_path = OUT / img_name
    if out_path.exists():
        skipped += 1
        continue

    m = PAT.match(img_name)
    if not m:
        errors.append(f"Can't parse: {img_name}")
        continue

    exam, pp, variant, page_str = m.groups()
    page_idx = int(page_str) - 1  # 0-based

    if variant:
        pdf_name = f"{exam}_provpass-{pp}-kvant-v{variant}.pdf"
    else:
        pdf_name = f"{exam}_provpass-{pp}-kvant.pdf"

    pdf_path = GAMLA / pdf_name
    if not pdf_path.exists():
        errors.append(f"PDF not found: {pdf_name}")
        continue

    try:
        doc  = fitz.open(str(pdf_path))
        page = doc[page_idx]
        mat  = fitz.Matrix(150 / 72, 150 / 72)  # 150 DPI
        pix  = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        pix.save(str(out_path))
        doc.close()
        done += 1
        print(f"  ✓ {img_name}")
    except Exception as e:
        errors.append(f"{img_name}: {e}")

print(f"\nDone: {done} extracted, {skipped} already existed")
if errors:
    print(f"Errors ({len(errors)}):")
    for e in errors:
        print(" ", e)
