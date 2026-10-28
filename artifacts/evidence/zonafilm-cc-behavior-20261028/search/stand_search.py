"""Стенд витрины на коммите argv[1] (копия git archive, копия снимка) и searchcheck_base.py по argv[2] → argv[3]."""
import importlib.util, os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
R = Path("/home/claude/wt-portable-site-cell-01/var/site-repos/zonafilm-cc"); S = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gfc", R / "checks/genre_facet_counts.py"); g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
tmp = Path(tempfile.mkdtemp(prefix="standsearch-")); tree = tmp / "zonafilm-cc"; tree.mkdir(); d = tmp / "data"; d.mkdir()
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
    r = subprocess.run([sys.executable, str(S / "searchcheck_base.py"), str(S.parent), sys.argv[2], sys.argv[3]], env={**os.environ, "ZCC_BASE": f"http://127.0.0.1:{port}"}, capture_output=True, text=True)
    print(r.stdout[-600:], r.stderr[-1500:])
finally:
    p.terminate(); p.wait(20); shutil.rmtree(tmp, ignore_errors=True)
