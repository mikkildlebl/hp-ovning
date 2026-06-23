import urllib.request, re

ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
pages = [
    ('2012-04', 'https://www.studera.nu/hogskoleprov/fpn/facit-provfragor-och-normering-varen-2012/'),
    ('2011-10', 'https://www.studera.nu/hogskoleprov/fpn/facit-provfragor-och-normering-hosten-2011/'),
    ('2011-04', 'https://www.studera.nu/hogskoleprov/fpn/facit-provfragor-och-normering-varen-2011/'),
    ('2010-10', 'https://www.studera.nu/hogskoleprov/fpn/facit-provfragor-och-normering-hosten-2010/'),
    ('2010-04', 'https://www.studera.nu/hogskoleprov/fpn/facit-provfragor-och-normering-varen-2010/'),
]
for year, url in pages:
    req = urllib.request.Request(url, headers={'User-Agent': ua})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            content = r.read().decode('utf-8', errors='replace')
            pdfs = re.findall(r'href="([^"]*\.pdf)"', content)
            print(f'{year}: {pdfs}')
    except Exception as e:
        print(f'{year}: ERROR {e}')
