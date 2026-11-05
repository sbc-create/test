#!/usr/bin/env python3
"""Freeze a clean exact native source into a review-only package; never installs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile


def build(repo,output,commit):
    repo=Path(repo).resolve();output=Path(output).resolve()
    def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
    if git('rev-parse','HEAD')!=commit or git('status','--porcelain'):
        raise ValueError('Package requires a clean exact committed source')
    paths=git('ls-files','factory').splitlines()
    files={name:(repo/name).read_bytes() for name in paths if name.endswith('.py')}
    entry=(repo/'automation/host/k2-native-entry.py').read_bytes()
    files.update({'bin/k2-native-worker':entry,'bin/k2-native-gateway':entry})
    hashes={name:hashlib.sha256(data).hexdigest() for name,data in files.items()}
    package_id=hashlib.sha256(json.dumps(hashes,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    metadata={'schema':'k2.native-bridge/1','source_commit':commit,'package_sha256':package_id,'files':hashes}
    files['config/bridge-package.json']=(json.dumps(metadata,sort_keys=True,indent=2)+'\n').encode()
    output.mkdir(parents=True,exist_ok=True)
    artifact=output/('native-bridge-'+commit+'.tar.gz')
    with artifact.open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w') as archive:
        for name,data in sorted(files.items()):
            item=tarfile.TarInfo(name);item.size=len(data);item.mode=0o555 if name.startswith('bin/') else 0o444
            archive.addfile(item,io.BytesIO(data))
    result={'artifact':str(artifact),'artifact_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
            'bytes':artifact.stat().st_size,'package_sha256':package_id,'source_commit':commit,
            'installation_performed':False,'required_external_config':'config/bridge-profile.json (root-owned read-only exact one-site profile)',
            'requires_independent_review':True}
    (output/'native-bridge-artifact.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repo',required=True);parser.add_argument('--output',required=True);parser.add_argument('--commit',required=True)
    args=parser.parse_args();build(args.repo,args.output,args.commit)
