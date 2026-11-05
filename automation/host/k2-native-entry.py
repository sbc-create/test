#!/usr/bin/python3 -I
"""Installed root-owned wrapper, packaged separately; never run from an artifact."""
import os
import json
import stat
from pathlib import Path
import sys

for name in list(os.environ):
    if name.startswith(('SITE_','CELL_','LORDS_','GIT_','PYTHON','FACTORY_','QWEN_','NOVA_')):os.environ.pop(name)
os.environ['PATH']='/usr/sbin:/usr/bin:/sbin:/bin'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
package=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(package))
metadata=package/'config/bridge-package.json'
mode=metadata.lstat()
if not stat.S_ISREG(mode.st_mode) or mode.st_uid!=0 or mode.st_mode & 0o222:
    raise PermissionError('Native package manifest must be root-owned and read-only')
from factory.cell.remote_package import verify
verify(package,json.loads(metadata.read_bytes()))
if Path(sys.argv[0]).name=='k2-native-worker':
    from factory.cell.remote_worker import main
    main(package/'config/bridge-profile.json',package/'config/bridge-package.json')
else:
    # Code stays under this immutable package root. Only these two explicit
    # links bind the existing canonical registry and its original repo root.
    canonical=Path('/usr/local/lib/site-factory-cell')
    for relative in ['config/site-cells.json','cell-install.json']:
        link=package/relative;target=canonical/relative
        if not link.is_symlink() or link.resolve()!=target.resolve() or link.lstat().st_uid!=0:
            raise PermissionError('Missing root-controlled canonical binding: '+relative)
        mode=target.stat()
        if not stat.S_ISREG(mode.st_mode) or mode.st_uid!=0 or mode.st_mode & 0o022:
            raise PermissionError('Unsafe canonical binding target: '+relative)
    if not Path(json.loads((canonical/'cell-install.json').read_bytes())['site_repos_root']).is_absolute():
        raise ValueError('Canonical original repository root must be absolute')
    from factory.cell.remote_gateway import serve
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);args=parser.parse_args()
    serve(args.request)
