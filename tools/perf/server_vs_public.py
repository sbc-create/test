#!/usr/bin/env python3
"""Серверное время против публичного TTFB на одних и тех же путях.

server_vs_public.py <домен> <порт upstream> <повторов> <out.json> <путь>...
Серверное время — первый байт ответа приложения напрямую (127.0.0.1:порт, Host
домена): без nginx, TLS и сети. Публичный TTFB — https://<домен><путь>: то,
что получает посетитель до первого байта (на этом хосте сеть ≈ 0). Это НЕ
время загрузки страницы: его меряет браузер (LCP, net-audit.js).
"""
import json, ssl, statistics as st, sys, time, http.client

домен, порт, n, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
пути = sys.argv[5:]


def ttfb(conn_factory, путь, host):
    c = conn_factory()
    t = time.perf_counter()
    c.request("GET", путь, headers={"Host": host, "User-Agent": "site-factory-perf-audit"})
    r = c.getresponse()
    r.read(1)
    первый = time.perf_counter() - t
    r.read()
    c.close()
    return round(первый * 1000), r.status


итог = {}
for путь in пути:
    s, p = [], []
    for _ in range(n):
        s.append(ttfb(lambda: http.client.HTTPConnection("127.0.0.1", порт, timeout=60), путь, домен))
        p.append(ttfb(lambda: http.client.HTTPSConnection(домен, 443, timeout=60, context=ssl.create_default_context()), путь, домен))
    sv = [x for x, _ in s]; pv = [x for x, _ in p]
    итог[путь] = {"server_ms": {"med": st.median(sv), "worst": max(sv), "n": n, "first": sv[0]},
                  "public_ttfb_ms": {"med": st.median(pv), "worst": max(pv), "n": n, "first": pv[0]},
                  "codes": sorted({c for _, c in s + p})}
    print(f"{путь:45s} сервер мед {итог[путь]['server_ms']['med']:6} худш {max(sv):6} | публ. TTFB мед {итог[путь]['public_ttfb_ms']['med']:6} худш {max(pv):6} | {итог[путь]['codes']}", flush=True)
json.dump(итог, open(out, "w"), ensure_ascii=False, indent=1)
