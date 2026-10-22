"""T300 (MOD-111 ред. 2), признак 2 на zonafilm.space: после изменения каталога дата в индексе
сдвигается ровно у тех частей, чьи байты изменились; новые адреса дописываются в хвост; адреса не
переезжают между частями; удалённые — вычеркнуты, а не сдвигают нарезку.

python3 automation/local/t300_criterion2.py <каталог снимка «до»> [домен=zonafilm.space]
Только GET к домену. Код 0 — признак выполнен; 1 — нарушен; 2 — не различающий (байты не менялись) или не измерено.
"""
import hashlib, json, re, sys, urllib.request

PRE = sys.argv[1]
D = sys.argv[2] if len(sys.argv) > 2 else "zonafilm.space"
UA = {"User-Agent": "sf-seo-audit/1.0"}

def get(u):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()

def index(b):
    return dict(re.findall(rb"<loc>https://[^/]+/([^<]+)</loc>\s*(?:<lastmod>([^<]+)</lastmod>)?", b))

try:
    old_idx_b = open(f"{PRE}/sitemap.xml", "rb").read(); new_idx_b = get(f"https://{D}/sitemap.xml")
except Exception as e:  # noqa: BLE001
    print("НЕ ИЗМЕРЕНО:", e); sys.exit(2)
oi, ni = index(old_idx_b), index(new_idx_b)
parts = sorted(set(oi) | set(ni), key=lambda p: int(re.findall(rb"\d+", p)[0]) if re.findall(rb"\d+", p) else 0)
res = {"domain": D, "parts": {}, "violations": []}
old_urls, new_urls = {}, {}
for p in parts:
    name = p.decode()
    try: ob = open(f"{PRE}/{name}", "rb").read()
    except OSError: ob = b""
    nb = get(f"https://{D}/{name}") if p in ni else b""
    changed = hashlib.sha256(ob).digest() != hashlib.sha256(nb).digest()
    olm, nlm = (oi.get(p) or b"").decode(), (ni.get(p) or b"").decode()
    ou = re.findall(rb"<loc>([^<]+)</loc>", ob); nu = re.findall(rb"<loc>([^<]+)</loc>", nb)
    old_urls[name], new_urls[name] = ou, nu
    res["parts"][name] = {"bytes_changed": changed, "lastmod_before": olm, "lastmod_after": nlm, "urls_before": len(ou), "urls_after": len(nu)}
    if changed and olm == nlm and ob:
        res["violations"].append(f"{name}: байты изменились, а дата в индексе прежняя ({olm})")
    if not changed and olm != nlm:
        res["violations"].append(f"{name}: байты те же, а дата сдвинулась {olm} → {nlm}")
# стабильная нарезка: адрес из части i не оказывается в другой части
where_new = {u: n for n, us in new_urls.items() for u in us}
moved = [(u.decode(), n, where_new[u]) for n, us in old_urls.items() for u in us if u in where_new and where_new[u] != n]
removed = [u.decode() for n, us in old_urls.items() for u in us if u not in where_new]
all_old = {x for xs in old_urls.values() for x in xs}
added = {n: [u for u in us if u not in all_old] for n, us in new_urls.items()}
last = parts[-1].decode() if parts else None
added_not_tail = {n: len(v) for n, v in added.items() if v and n != last}
# порядок прежних адресов внутри части сохраняется (новые — в конец)
for n, us in old_urls.items():
    so, sn = set(us), set(new_urls.get(n, []))
    keep = [u for u in new_urls.get(n, []) if u in so]
    pref = [u for u in us if u in sn]
    if keep != pref:
        res["violations"].append(f"{n}: прежние адреса переставлены")
    tail_ok = new_urls.get(n, [])[:len(keep)] == keep
    if not tail_ok and n == last:
        res["violations"].append(f"{n}: новые адреса не в хвосте части")
if moved: res["violations"].append(f"адреса переехали между частями: {len(moved)}, напр. {moved[:3]}")
if added_not_tail: res["violations"].append(f"новые адреса не в последней части: {added_not_tail}")
res.update({"moved": len(moved), "removed": len(removed), "added": {n: len(v) for n, v in added.items()}, "removed_sample": removed[:5]})
any_changed = any(v["bytes_changed"] for v in res["parts"].values())
print(json.dumps(res, ensure_ascii=False, indent=1))
if not any_changed:
    print("НЕ РАЗЛИЧАЮЩИЙ: байты частей не менялись"); sys.exit(2)
print("ПРИЗНАК 2:", "нарушен" if res["violations"] else "выполнен"); sys.exit(1 if res["violations"] else 0)
