"""T345 приёмка на стенде: число в подписи пункта = числу записей в выдаче по этому пункту; выдача того же вида."""
import html, importlib.util, json, re, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
R = Path("/home/claude/wt-portable-site-cell-01/var/site-repos/zonafilm-cc")
spec = importlib.util.spec_from_file_location("gfc", R / "checks/genre_facet_counts.py"); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
SEL = r'<select[^>]*aria-label="Фильтр по жанру"[^>]*>(.*?)</select>'
def txt(b): return b if isinstance(b, str) else b.decode()
tmp = Path(tempfile.mkdtemp(prefix="facetcount-")); d = tmp / "data"; d.mkdir()
for f in g.ДАННЫЕ.iterdir():
    (d / f.name).symlink_to(f) if f.is_dir() or f.stat().st_size > (4 << 20) else shutil.copyfile(f, d / f.name)
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
p = subprocess.Popen([sys.executable, "run.py", "--port", str(port), "--data-dir", str(d)], cwd=R, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
out = {"sample_html": None, "rows": []}
try:
    for _ in range(240):
        try:
            if g.взять(port, "/healthz")[0] == 200: break
        except OSError: pass
        time.sleep(1)
    for sec in ("/movies/", "/series/", "/animation/"):
        h = txt(g.взять(port, sec)[1]); m = re.search(SEL, h, re.S)
        for v, t in re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)', m.group(1))[1:]:
            v = html.unescape(v); t = re.sub(r"\s+", " ", html.unescape(t)).strip()
            n = re.search(r"\((\d+)\)\s*$", t)
            st, b = g.взять(port, v.replace(" ", "%20"))[:2]; b = txt(b)
            main = b[b.find("<main"):b.find("</main>")]
            tot = re.findall(r"Результаты по фильтрам:\s*(\d+)", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", main)))
            robots = re.findall(r'<meta name="robots" content="([^"]+)"', b)
            if out["sample_html"] is None: out["sample_html"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", main))[:1500]
            out["rows"].append({"sec": sec, "label": t, "url": v, "label_n": int(n.group(1)) if n else None, "status": st,
                                "page_totals": [int(re.sub(r"\D", "", x)) for x in tot[:3]], "robots": robots[:1],
                                "cards": len(set(re.findall(r'href="/title/([^/"]+)/"', main)))})
    json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False, indent=1)
finally:
    p.terminate(); p.wait(20); shutil.rmtree(tmp, ignore_errors=True)
