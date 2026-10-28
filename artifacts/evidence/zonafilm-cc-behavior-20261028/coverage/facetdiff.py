"""Какие пункты стенда (T345) отсутствуют среди 34 живых непустых пунктов /movies/ и 31+... /series/."""
import html, importlib.util, json, re, shutil, socket, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path
R = Path("/home/claude/wt-portable-site-cell-01/var/site-repos/zonafilm-cc")
spec = importlib.util.spec_from_file_location("gfc", R / "checks/genre_facet_counts.py"); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
SEL = r'<select[^>]*aria-label="Фильтр по жанру"[^>]*>(.*?)</select>'
def opts(h):
    m = re.search(SEL, h, re.S)
    return [(html.unescape(v), re.sub(r"\s+", " ", html.unescape(t)).strip()) for v, t in re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)', m.group(1))][1:]
def gv(v): return re.search(r"genre=([^&]+)", v).group(1)
tmp = Path(tempfile.mkdtemp(prefix="facetdiff-")); d = tmp / "data"; d.mkdir()
for f in g.ДАННЫЕ.iterdir():
    (d / f.name).symlink_to(f) if f.is_dir() or f.stat().st_size > (4 << 20) else shutil.copyfile(f, d / f.name)
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
p = subprocess.Popen([sys.executable, "run.py", "--port", str(port), "--data-dir", str(d)], cwd=R, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
live = json.load(open(sys.argv[1]))
try:
    for _ in range(240):
        try:
            if g.взять(port, "/healthz")[0] == 200: break
        except OSError: pass
        time.sleep(1)
    out = {}
    for sec in ("/movies/", "/series/"):
        r = g.взять(port, sec); st = {gv(v): t for v, t in opts(r[1] if isinstance(r[1], str) else r[1].decode())}
        lh = urllib.request.urlopen(urllib.request.Request("https://zonafilm.cc" + sec, headers={"User-Agent": "Mozilla/5.0 factory-seo-acceptance"}), timeout=60).read().decode()
        lo = {gv(v): t for v, t in opts(lh)}; bad = {gv(b[1]) for b in live[sec]["bad"]}
        good = set(lo) - bad
        out[sec] = {"stand": len(st), "live_good": len(good), "stand_not_live_good": {k: st[k] for k in set(st) - good},
                    "live_good_not_stand": {k: lo[k] for k in good - set(st)}}
        print(sec, out[sec])
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
finally:
    p.terminate(); p.wait(20); shutil.rmtree(tmp, ignore_errors=True)
