#!/usr/bin/env python3
"""Read installed bindings; stage a bootstrap proposal only. Never installs/reloads."""
import argparse
import hashlib
import json
from pathlib import Path
import stat

CANONICAL=Path('/usr/local/lib/site-factory-cell')
TASK=Path('/home/claude/k2-episode-repair-20261105')


def trusted(path):
    mode=path.stat()
    if not stat.S_ISREG(mode.st_mode) or mode.st_uid!=0 or mode.st_mode & 0o022:
        raise PermissionError('Existing canonical binding must be root-owned and not writable by others')
    return json.loads(path.read_bytes())


def prepare(manifest,package_id,output):
    if len(package_id)!=64 or any(c not in '0123456789abcdef' for c in package_id):raise ValueError('Exact package identity required')
    output=Path(output).absolute()
    if not output.is_relative_to(TASK/'remote-release-core/var'):raise ValueError('Output must stay in the isolated core worktree var directory')
    registry=trusted(CANONICAL/'config/site-cells.json');installed=trusted(CANONICAL/'cell-install.json')
    if not Path(installed['site_repos_root']).is_absolute():raise ValueError('Original repository root must be absolute')
    proposed=[]
    for site in manifest['sites']:
        matches=[c for c in registry['cells'] if c['domain']==site['domain']]
        if len(matches)!=1:raise ValueError('Canonical site identity missing/ambiguous')
        cell=matches[0];source=Path(site['worktree'])
        if source!=TASK/site['domain'] or source.resolve()!=source:raise ValueError('Source is not the exact isolated task worktree')
        if cell['repo']['remote'].rstrip('/').removesuffix('.git')!=site['identity']['origin'].rstrip('/').removesuffix('.git'):raise ValueError('Canonical origin differs')
        proposed.append({'site_id':cell['site_id'],'domain':cell['domain'],'expected_commit':site['commit'],
            'unchanged_canonical_repo':cell['repo'],'runtime':{'code_delivery':{'source_path':str(source)}}})
    package=CANONICAL/'bridge-packages'/package_id
    plan={'status':'STAGED_ONLY_NOT_INSTALLED','package_root':str(package),'canonical_registry_sha256':hashlib.sha256((CANONICAL/'config/site-cells.json').read_bytes()).hexdigest(),
          'original_repo_root':installed['site_repos_root'],'links':[{'link':str(package/name),'target':str(CANONICAL/name),'owner':'root:root'} for name in ['config/site-cells.json','cell-install.json']],
          'source_bindings':proposed,'order':['Review exact package and this proposal','Install package into NEW immutable versioned directory; do not overwrite installed core','Create and verify the two explicit canonical links','MAIN installs its independently reviewed minimal skip-only patch in ORIGINAL installed consumer batch first; ordinary original modules/invocation remain unchanged','Only then main-owned registry writer may enable remote role/profile/source_path metadata','Only then enqueue or dispatch remote requests'],
          'production_writes_performed':False,'canonical_repo_fields_modified':False}
    output.mkdir(parents=True,exist_ok=True)
    (output/'binding-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(plan,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--package-id',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    prepare(json.loads(a.manifest.read_bytes()),a.package_id,a.output)
