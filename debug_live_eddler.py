"""Compare live fetch vs saved HTML for eddler hpvar2023p3."""
import urllib.request, re

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode('utf-8', errors='replace')

url = 'https://eddler.se/lektioner/elf-engelsk-lasforstaelse-hpvar2023p3/'
html = fetch(url)

with open('eddler_var2023p3.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"Fetched {len(html)} chars")

# How many question LIs?
q_lis = re.findall(r'id="wp-education-examination-question_(\d+)"', html)
print(f"Question LI IDs: {q_lis}")

# How many w3-container blocks (passages)?
w3 = re.findall(r'class="w3-container"', html)
print(f"w3-container blocks: {len(w3)}")

# Check the UL
ul = re.search(r'class="wp-education-examination-questions[^"]*"[^>]*>', html)
print(f"UL found: {bool(ul)}")
if ul:
    print(f"  UL tag: {ul.group()}")

# Check correct answers
ans = re.findall(r'"(\d+)"\s*:\s*\{"id":\d+,"customData":\{"correctAnswer":"(answer_\d+)"', html)
print(f"Correct answers: {ans}")

# Check if page has isFreeLesson
free = re.search(r'"isFreeLesson"\s*:\s*(true|false)', html)
print(f"isFreeLesson: {free.group(1) if free else 'not found'}")

# Print 500 chars around "Premium" gate if any
prem = html.find('badge-premium')
if prem >= 0:
    print(f"\nPremium gate found at {prem}:")
    print(html[max(0,prem-100):prem+200])
