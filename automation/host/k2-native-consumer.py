#!/usr/bin/python3 -I
"""Tiny CONTROL guard. Ordinary work uses ONLY the original installed modules."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ORIGINAL=Path('/usr/local/lib/site-factory-cell')
SITES={'lords-02','lords-03','lords-05','zona-01','zona-02','zona-03'}


def consume(queue,executor,registry,base,limit=10):
    directory=base/'requests'
    if not directory.is_dir():return []
    results=[]
    for path in sorted(directory.glob('*.json'),key=lambda p:p.stat().st_mtime)[:limit]:
        try:request=queue.разобрать(json.loads(path.read_text()))
        except (queue.RequestRejected,ValueError) as error:
            outcome={'request_id':path.stem,'status':'rejected','error':str(error)}
            queue.записать_атомарно(base/'results'/path.name,outcome);path.unlink();results.append(outcome);continue
        if request.operation=='activate' and request.site_id in SITES:
            cell=registry.resolve(request.site_id)
            if ((cell.runtime or {}).get('code_delivery') or {}).get('role')=='local-ssh-bridge':
                results.append({'request_id':request.request_id,'status':'waiting-bridge'});continue
        outcome=executor.выполнить(request,база=base,dry_run=False)
        if outcome.get('status') in {'busy','waiting-bridge','reconcile'}:
            results.append(outcome);continue
        queue.записать_атомарно(base/'results'/path.name,outcome);path.unlink();results.append(outcome)
    return results


def main():
    if os.geteuid()!=0 or len(sys.argv)!=1:raise PermissionError('Fixed root consumer invocation required')
    for name in list(os.environ):
        if name.startswith(('SITE_','CELL_','LORDS_','GIT_','PYTHON','FACTORY_','QWEN_','NOVA_')):os.environ.pop(name)
    os.environ['PATH']='/usr/sbin:/usr/bin:/sbin:/bin';os.environ['PYTHONDONTWRITEBYTECODE']='1'
    package=Path(__file__).resolve().parent.parent;metadata=package/'config/bridge-package.json'
    mode=metadata.stat()
    if mode.st_uid!=0 or mode.st_mode & 0o222:raise PermissionError('Untrusted guard manifest')
    expected=json.loads(metadata.read_bytes())['files']['bin/k2-native-consumer']
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=expected:raise PermissionError('Guard digest mismatch')
    registry_path=ORIGINAL/'config/site-cells.json'
    mode=registry_path.stat()
    if not stat.S_ISREG(mode.st_mode) or mode.st_uid!=0 or mode.st_mode & 0o022:raise PermissionError('Untrusted original canonical registry')
    sys.path.insert(0,str(ORIGINAL))
    from factory.cell import executor,queue,registry
    for module in [executor,queue,registry]:
        if not Path(module.__file__).resolve().is_relative_to(ORIGINAL):raise PermissionError('Consumer imported outside original installed native core')
    print(json.dumps(consume(queue,executor,registry,queue.БАЗА),ensure_ascii=False))


if __name__=='__main__':main()
