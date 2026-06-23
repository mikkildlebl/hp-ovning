import pdfplumber, re

pdf_path = r'C:\Users\Mikael\Documents\Claude code\HP\Gamla_HP\2019-04-06_provpass-1-verb-utan-elf.pdf'

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[2]  # page 3
    t = page.extract_text() or ''

# Print first 200 chars as hex
print("First 200 chars as hex:")
for i, ch in enumerate(t[:200]):
    print(f"  [{i:3d}] U+{ord(ch):04X} {repr(ch)}")

print("\nFull first 3 lines:")
for line in t.split('\n')[:5]:
    print(repr(line))

# Test our regex
LAS_START_RE = re.compile(
    r'DELPROV\s+L[ÄA]S|Svensk\s+l[äa]sf[öo]rst[äa]else',
    re.IGNORECASE
)
print("\nRegex match:", LAS_START_RE.search(t))

# Try with a more permissive regex
permissive = re.compile(r'Svensk\s+l\S+f\S+rst\S+else', re.IGNORECASE)
print("Permissive match:", permissive.search(t))

# Try just checking if text contains 'Svensk'
print("Contains 'Svensk':", 'Svensk' in t)
print("Contains 'L' + some chars + 'S':", bool(re.search(r'L.S', t)))
