import pdfplumber, re, sys

pdf_path = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\Mikael\Documents\Claude code\HP\Gamla_HP\2019-04-06_provpass-1-verb-utan-elf.pdf'

with pdfplumber.open(pdf_path) as pdf:
    print(f'Pages: {len(pdf.pages)}\n')
    for i, page in enumerate(pdf.pages):
        t = page.extract_text() or ''
        if re.search(r'L[ÄA]S|MEK', t, re.IGNORECASE):
            print(f'=== PAGE {i+1} ===')
            print(t[:800])
            print()
