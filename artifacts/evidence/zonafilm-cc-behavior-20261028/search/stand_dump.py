"""Стенд на коммите argv[1]; для запросов argv[2:] — текст <main> (без тегов) и порядок /title/ ссылок по блокам."""
import importlib.util, re, shutil, socket, subprocess, sys, tempfile, time, urllib.parse, html
from pathlib import Path
R = Path("/home/claude/wt-portable-site-cell-01/var/site-repos/zonafilm-cc")
spec = importlib.util.spec_from_file_location("gfc", R / "checks/genre_facet_counts.py"); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
tmp = Path(tempfile.mkdtemp(prefix="standdump-")); tree = tmp / "zonafilm-cc"; tree.mkdir(); d = tmp / "data"; d.mkdir()
a = subprocess.run(["git", "archive", sys.argv[1]], cwd=R, capture_output=True, check=True); subprocess.run(["tar", "-x", "-C", str(tree)], input=a.stdout, check=True)
for f in g.ДАННЫЕ.iterdir():
    (d / f.name).symlink_to(f) if f.is_dir() or f.stat().st_size > (4 << 20) else shutil.copyfile(f, d / f.name)
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
p = subprocess.Popen([sys.executable, "run.py", "--port", str(port), "--data-dir", str(d)], cwd=tree, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(240):
        try:
            if g.взять(port, "/healthz")[0] == 200: break
        except OSError: pass
        time.sleep(1)
    for q in sys.argv[2:]:
        st, b = g.взять(port, "/search/?q=" + urllib.parse.quote(q))[:2]; b = b if isinstance(b, str) else b.decode()
        main = b[b.find("<main"):b.find("</main>")]
        t = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", main)))
        print("=====", q, st); print(t[:1400])
finally:
    p.terminate(); p.wait(20); shutil.rmtree(tmp, ignore_errors=True)
