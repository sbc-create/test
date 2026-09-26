"""Реальное выполнение activate.sh любого выделенного сайта: успех и откат."""
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path


def health_server(port):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'ok')

        def log_message(self, *a):
            pass
    s = http.server.HTTPServer(('127.0.0.1', port), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def sandbox(tmp: Path, repo: Path, site_id: str, port: int):
    shared = tmp/'shared'
    old_root = tmp/'old'
    root = tmp/'srv'
    units = tmp/'units'
    binx = tmp/'bin'
    journal = tmp/'systemctl.log'
    for d in ((old_root/'data'), (old_root/'current'/'site'), shared, units, binx):
        d.mkdir(parents=True, exist_ok=True)
    # Каталог песочницы обязан быть НАСТОЯЩИМ снимком: пусковой скрипт
    # проверяет его разбором, и заглушка '{}' отказом оборачивалась в отказ
    # сценария. Пустой список items — это «показывать нечего», а не «битый
    # снимок», и именно на нём сценарий активации и должен проходить.
    (shared/f'{site_id}-catalog.json').write_text(
        json.dumps({'revision': 'sandbox', 'items': []}), encoding='utf-8')
    for name in (f'{site_id}-details.json', f'template-manifest-{site_id}.json'):
        (shared/name).write_text('{}', encoding='utf-8')
    # PUB берётся из конфигурации самого сайта: фиксированное значение
    # заваливало бы проверку у другого семейства, и падал бы тест, а не скрипт.
    cfg = json.loads((repo/'config'/'site.json').read_text(encoding='utf-8'))
    pub = cfg.get('publisher_id_expected') or '10238'
    (shared/f'player-{site_id}.json').write_text(
        json.dumps({'publisher_id': pub}), encoding='utf-8')
    (old_root/'data'/'animedia-community.json').write_text(
        json.dumps({'c': 'ЖИВАЯ ЗАПИСЬ'}, ensure_ascii=False), encoding='utf-8')
    (old_root/'current'/'site'/'index.html').write_text('<html></html>', encoding='utf-8')
    (binx/'systemctl').write_text(
        '#!/usr/bin/env bash\n'
        f'echo "$@" >> "{journal}"\n'
        '[ "$1" = "is-active" ] && [ "$2" = "--quiet" ] && exit 3\n'
        'exit 0\n', encoding='utf-8')
    (binx/'useradd').write_text('#!/usr/bin/env bash\nexit 0\n', encoding='utf-8')
    for f in binx.iterdir():
        os.chmod(f, 0o755)
    env = dict(os.environ)
    env.update({
        'SITE_ROOT': str(root), 'SITE_SHARED': str(shared), 'SITE_OLD_ROOT': str(old_root),
        'SITE_REQUIRE_ROOT': '0', 'SITE_SYSTEMCTL': str(binx/'systemctl'),
        'SITE_USERADD': str(binx/'useradd'), 'SITE_UNIT_DIR': str(units),
        'SITE_INSTALL_OWNER': '0', 'SITE_RUN_AS': '', 'SITE_ACCOUNT': 'nobody',
        'SITE_SKIP_CHECKS': '1', 'SITE_PORT': str(port), 'SITE_HEALTH_TRIES': '3',
    })
    return env, root, old_root, journal


def snapshot(d: Path):
    # journal заглушки systemctl не считается изменением песочницы: его пишет
    # сама заглушка в ответ на read-only запрос is-active, который скрипт
    # обязан делать и в сухом прогоне.
    return {str(p.relative_to(d)): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(d.rglob('*'))
            if p.is_file() and p.name != 'systemctl.log'}


def build_artifact(repo: Path, out: Path) -> Path:
    """Активация ставит только проверенный артефакт, поэтому его надо собрать.

    Раньше сценарий запускал activate.sh без артефакта и тем самым проверял
    установку из рабочего каталога — то есть ровно тот путь, который больше
    не разрешён.
    """
    subprocess.run([sys.executable, str(repo/'tools'/'build_release.py'),
                    '--output', str(out)], check=True, capture_output=True,
                   cwd=str(repo))
    return next(out.glob('*.tar.gz'))


def run(repo: Path, site_id: str, port: int):
    итог = {}
    # Артефакт собирается ОДИН раз и ВНЕ песочницы: сборка внутрь неё
    # добавляла бы файлы после снимка, и сухой прогон выглядел бы
    # изменяющим песочницу, хотя он её не трогает.
    with tempfile.TemporaryDirectory() as dist:
        art = build_artifact(repo, Path(dist))
        # сухой прогон
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            env, *_ = sandbox(tmp, repo, site_id, port)
            before = snapshot(tmp)
            r = subprocess.run(['bash', str(repo/'deploy'/'activate.sh'),
                                '--dry-run', '--artifact', str(art)],
                               capture_output=True, text=True, env=env, cwd=str(repo))
            итог['dry_run'] = {'код': r.returncode,
                               'дошёл': 'сухой прогон завершён' in r.stdout,
                               'песочница не менялась': before == snapshot(tmp)}
            if r.returncode != 0:
                итог['dry_run']['stderr'] = r.stderr[-300:]
        # успех
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            srv = health_server(port)
            env, root, old_root, journal = sandbox(Path(tmp), repo, site_id, port)
            r = subprocess.run(['bash', str(repo/'deploy'/'activate.sh'),
                                '--artifact', str(art)],
                               capture_output=True, text=True, env=env, cwd=str(repo))
            srv.shutdown()
            j = journal.read_text() if journal.exists() else ''
            итог['успех'] = {
                'код': r.returncode, 'ГОТОВО': 'ГОТОВО' in r.stdout,
                'старая остановлена раньше новой': (
                    'stop ' in j and 'enable --now' in j
                    and j.index('stop ') < j.index('enable --now')),
            }
            if r.returncode != 0:
                итог['успех']['stderr'] = r.stderr[-300:]
        # откат
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            env, root, old_root, journal = sandbox(Path(tmp), repo, site_id, port + 1)
            r = subprocess.run(['bash', str(repo/'deploy'/'activate.sh'),
                                '--artifact', str(art)],
                               capture_output=True, text=True, env=env, cwd=str(repo))
            j = journal.read_text() if journal.exists() else ''
            итог['откат'] = {
                'код не 0': r.returncode != 0,
                'сообщил': 'откатываюсь' in r.stderr,
                'прежняя возвращена': 'enable --now' in j and j.count('enable --now') >= 2,
                'исходные данные целы': 'ЖИВАЯ ЗАПИСЬ' in (
                    old_root/'data'/'animedia-community.json').read_text(encoding='utf-8'),
            }
    return итог


if __name__ == '__main__':
    repo = Path(__file__).resolve().parent.parent
    site_id = json.loads((repo/'config'/'site.json')
                        .read_text(encoding='utf-8'))['site_id']
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9801
    res = run(repo, site_id, port)
    ok = True
    for фаза, поля in res.items():
        print(f'  {фаза}:', поля)
        for k, v in поля.items():
            if k in ('код', 'stderr'):
                continue
            ok &= bool(v)
        if фаза != 'откат' and поля.get('код', 0) != 0:
            ok = False
    print('  ИТОГ:', 'PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)
