import pdfplumber, re

pdfs = [
    (r'C:\Users\Mikael\Documents\Claude code\HP\Gamla_HP\2019-04-06_provpass-1-verb-utan-elf.pdf', '2019 pp1'),
    (r'C:\Users\Mikael\Documents\Claude code\HP\Gamla_HP\2022-03-12_provpass-2-verb-utan-elf.pdf', '2022 pp2'),
    (r'C:\Users\Mikael\Documents\Claude code\HP\Gamla_HP\2025-04-05_provpass-2-verb-utan-elf.pdf', '2025 pp2'),
    (r'C:\Users\Mikael\Documents\Claude code\HP\Gamla_HP\2025-10-19_provpass-3-verb-utan-elf.pdf', '2025-10-19 pp3'),
]
for path, label in pdfs:
    print(f'\n=== {label} ===')
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ''
            lines = t.split('\n')
            first = lines[0][:80] if lines else ''
            second = lines[1][:80] if len(lines) > 1 else ''
            print(f'  Page {i+1}: "{first}" | "{second}"')
