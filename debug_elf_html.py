import urllib.request, re
ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
req = urllib.request.Request('https://www.hogskoleprovet.nu/elf/', headers={'User-Agent': ua})
with urllib.request.urlopen(req, timeout=15) as r:
    html = r.read().decode('utf-8', errors='replace')

blocks = html.split('class="quiz-question-text">')
print("Found", len(blocks)-1, "blocks")
for i, b in enumerate(blocks[1:], 1):
    print(f"--- BLOCK {i} ---")
    print(b[:1000])
    print()
