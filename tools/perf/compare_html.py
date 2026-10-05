#!/usr/bin/env python3
"""Сравнить ответы двух копий витрины по набору адресов (до/после правки).

compare_html.py <host> <порт_до> <порт_после> <файл_адресов> [повторов]
Сравнивается тело ответа после удаления меток времени и идентификатора
выпуска — они различаются по построению. Печатает время ответа обеих копий.
"""
import re, sys, time, urllib.request

host, до, после, файл = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
повторов = int(sys.argv[5]) if len(sys.argv) > 5 else 1
ШУМ = [re.compile(p) for p in (
    r'content="[^"]*-(?:lords|zona)-\d\d"', r'data-build-id="[^"]*"', r'[\w.-]+-(?:lords|zona)-\d\d\b',
    r'site-factory-template-revision" content="[^"]*"', r'site-factory-build-id" (?:content="[^"]*"|~)',
    r'site-factory-artifact-sha256" content="[^"]*"',r'"generated_at":\s*"[^"]*"', r'data-generated-at="[^"]*"',
    r'live_build_id[^,}]*', r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ')]


def взять(порт, путь):
    t = time.perf_counter()
    з = urllib.request.Request(f"http://127.0.0.1:{порт}{путь}", headers={"Host": host})
    try:
        with urllib.request.urlopen(з, timeout=60) as r:
            тело, код = r.read(), r.status
    except urllib.error.HTTPError as e:
        тело, код = e.read(), e.code
    return код, тело, time.perf_counter() - t


def чисто(б):
    т = б.decode("utf-8", "replace")
    for p in ШУМ:
        т = p.sub("~", т)
    return т


расхождений = 0
for путь in [l.strip() for l in open(файл) if l.strip() and not l.startswith("#")]:
    for i in range(повторов):
        к1, б1, т1 = взять(до, путь)
        к2, б2, т2 = взять(после, путь)
        same = к1 == к2 and чисто(б1) == чисто(б2)
        расхождений += 0 if same else 1
        print(f"{'OK ' if same else 'DIFF'} {к1}/{к2} до={т1*1000:7.0f}мс после={т2*1000:7.0f}мс {путь}")
        if not same and i == 0:
            а, б = чисто(б1), чисто(б2)
            n = next((k for k in range(min(len(а), len(б))) if а[k] != б[k]), min(len(а), len(б)))
            print(f"     первое отличие @{n}: до=…{а[max(0,n-80):n+80]!r}\n     после=…{б[max(0,n-80):n+80]!r}")
print(f"расхождений: {расхождений}")
sys.exit(1 if расхождений else 0)
