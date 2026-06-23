"""Fetch and parse ELF questions from eddler.se pages."""
import urllib.request, re, json

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode('utf-8', errors='replace')

url = 'https://eddler.se/lektioner/elf-engelsk-lasforstaelse-hpmaj2022p3/'
html = fetch(url)

# Save raw HTML to inspect
with open('eddler_raw.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Fetched {len(html)} chars")

# Look for question/answer structures
# Check for data attributes or answer indicators
answer_hints = re.findall(r'(?:correct|answer|facit|ratt)[^"\'<>]{0,100}', html, re.I)
print("Answer hints found:", len(answer_hints))
for h in answer_hints[:20]:
    print(" ", h[:120])

# Look for any A/B/C/D patterns
option_patterns = re.findall(r'[A-D]\)[^<\n]{10,80}', html)
print(f"\nOption-style patterns (A) B) etc): {len(option_patterns)}")
for p in option_patterns[:10]:
    print(" ", p[:80])
