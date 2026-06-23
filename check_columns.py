"""Check column structure and test column-aware extraction."""
import pdfplumber, re

LAS_HEADER_RE = re.compile(
    r'^(Svensk\s+l.+?L[ÄA]S|L[ÄA]S)\s*$',
    re.IGNORECASE | re.MULTILINE
)

def find_uppgifter_y(page):
    for w in page.extract_words():
        if w['text'].lower() == 'uppgifter':
            return w['top']
    return None

def extract_column_text(page, uppgifter_y=None):
    w = page.width
    h = uppgifter_y if uppgifter_y else page.height
    mid = w / 2
    left = (page.crop((0, 0, mid, h)).extract_text() or '').strip()
    right = (page.crop((mid, 0, w, h)).extract_text() or '').strip()
    left = LAS_HEADER_RE.sub('', left).strip()
    right = LAS_HEADER_RE.sub('', right).strip()
    parts = [p for p in [left, right] if p]
    return '\n'.join(parts)


print('=== WORD POSITIONS ON PAGE 4 (Ett sluttande plan?) ===')
with pdfplumber.open(r'Gamla_HP\2019-04-06_provpass-1-verb-utan-elf.pdf') as pdf:
    page = pdf.pages[3]
    words = page.extract_words()
    print(f'Page width: {page.width:.1f}')
    for w in words[:50]:
        side = 'L' if w['x0'] < page.width/2 else 'R'
        print(f'  [{side}] x0={w["x0"]:6.1f} top={w["top"]:6.1f} {repr(w["text"])}')

print()
print('=== FULL COLUMN-AWARE EXTRACTION: Pages 3-5 ===')
with pdfplumber.open(r'Gamla_HP\2019-04-06_provpass-1-verb-utan-elf.pdf') as pdf:
    for i in [2, 3, 4]:
        page = pdf.pages[i]
        uy = find_uppgifter_y(page)
        text = extract_column_text(page, uy)
        print(f'--- Page {i+1} (uppgifter_y={uy}) ---')
        print(text[:1200])
        print()
