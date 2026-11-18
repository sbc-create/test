"""Bounded identity proof for one known memory-unsafe legacy transition.

The legacy health route parses the complete sidecar on every probe. During
blue/green overlap that parse exhausts this 2 GiB host. This exact migration
uses real home/build and runtime/pair responses instead; candidate health and
immutable rollback capture remain mandatory. Unknown releases get no waiver.
"""
from pathlib import Path
import hashlib
import json
import stat
import subprocess
import urllib.request

SITE = 'lords-05'
OLD = 'bf7be03ef974876d2a2f385d0471d0804156de20'
NEW = '50e8b789804bc10eaec6a0742d1ff5a4f0652abc'
DIGESTS = {
    OLD: 'sha256:5ac7326ad0720f14c505a88c0ac42309989ecc374eee956b704cb21cc83cf230',
    NEW: 'sha256:bc61ef82ea058bdb3235a336bf511e06cc2bffbedb1457d7bbba2c451caa407f',
}
OLD_CODE = {
    'src/lords-frontend.py': 'f687ad403c6d7ac79af717c0ae450bcea20a5ab269ed7fb119f269b99e69a40c',
    'src/lords05-frontend.py': '8d42d87946a19f083e10b08ac90aca5a362a3f66b5cf15280c582599e1b82e4e',
}


def require(ok, message):
    if not ok:
        raise ValueError('Legacy checkpoint refused: ' + message)


def bounded_json(path):
    require(stat.S_ISREG(path.lstat().st_mode), 'metadata is not a regular file')
    with path.open('rb') as stream:
        raw = stream.read(65537)
    require(len(raw) <= 65536, 'metadata size')
    value = json.loads(raw)
    require(isinstance(value, dict), 'metadata shape')
    return value, hashlib.sha256(raw).hexdigest()


def sha(path):
    require(stat.S_ISREG(path.lstat().st_mode), 'code is not a regular file')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def provenance(release, commit):
    value, digest = bounded_json(release / 'release-manifest.json')
    expected = {'site_id': SITE, 'commit': commit, 'digest': DIGESTS[commit],
                'release': commit[:12], 'installed_by': 'cell-executor',
                'live_build_id': commit[:12] + '-' + SITE}
    require(all(value.get(k) == v for k, v in expected.items()), 'installed provenance differs')
    return digest


def unit_state(unit):
    raw = subprocess.check_output(
        ['systemctl', 'show', unit, '-p', 'ActiveState', '-p', 'MainPID', '-p', 'InvocationID'],
        text=True, timeout=10)
    value = dict(line.split('=', 1) for line in raw.splitlines())
    require(value.get('ActiveState') == 'active', 'old unit not active')
    require(value.get('MainPID', '').isdigit() and int(value['MainPID']) > 0, 'old PID missing')
    require(bool(value.get('InvocationID')), 'old invocation missing')
    return value


def runtime_version(port):
    url = f'http://127.0.0.1:{port}/__template_version'
    request = urllib.request.Request(url, headers={'Host': 'lordserials22.info'})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=10) as response:
        require(response.status == 200 and response.url == url, 'runtime response or redirect')
        raw = response.read(262145)
    require(len(raw) <= 262144, 'runtime response size')
    value = json.loads(raw)
    require(isinstance(value, dict), 'runtime response shape')
    return value


def validate_runtime(live, build):
    require(live.get('site_repo_commit') == OLD and live.get('site_repo_dirty') is False
            and live.get('build_id') == build, 'runtime release differs')
    require(live.get('catalog_revision') and
            live.get('catalog_revision') == live.get('details_catalog_revision'), 'runtime revision skew')
    require(live.get('catalog_built_at') and
            live.get('catalog_built_at') == live.get('details_catalog_built_at'), 'runtime date skew')
    require(live.get('catalog_details_skew') is False and
            type(live.get('details_coverage')) is int and live['details_coverage'] > 0, 'runtime pair not admitted')


def primary(site, verify, path=None):
    """Return (HTTP verdict, optional immutable-state recheck callback)."""
    old = site.current.resolve()
    if site.site_id != SITE or old.name != OLD[:12]:
        return verify(site.site_id, порт=site.port, path=path), None
    # A known unsafe old release never falls back to its expensive route on
    # malformed/missing migration evidence. All failures stay before switch.
    require(old == site.releases.resolve() / OLD[:12], 'old release location')
    new = site.candidate.resolve()
    require(new == site.releases.resolve() / NEW[:12], 'unapproved migration candidate')
    before = (provenance(old, OLD), provenance(new, NEW), unit_state(site.unit))
    require({name: sha(old / name) for name in OLD_CODE} == OLD_CODE, 'legacy code differs')
    manifest, manifest_digest = bounded_json(old / 'config/template-manifest.json')
    require(manifest.get('site_repo_commit') == OLD and manifest.get('site_repo_dirty') is False,
            'legacy template provenance differs')
    build = OLD[:12] + '-' + SITE
    require(manifest.get('build_id') == build, 'legacy template build differs')
    verdict = verify(site.site_id, порт=site.port, path=path,
                     ожидаемый_build=build, маршруты=('/',))
    require(verdict.get('ok') is True and verdict.get('build_id') == build, 'old home build differs')
    live = runtime_version(site.port)
    validate_runtime(live, build)

    def recheck():
        require(site.current.resolve() == old and site.candidate.resolve() == new, 'release links changed')
        require((provenance(old, OLD), provenance(new, NEW), unit_state(site.unit)) == before,
                'provenance or process changed')
        require(bounded_json(old / 'config/template-manifest.json')[1] == manifest_digest,
                'legacy template changed')
        require({name: sha(old / name) for name in OLD_CODE} == OLD_CODE, 'legacy code changed')

    recheck()
    verdict['primary_checkpoint_proof'] = {
        'kind': 'exact_legacy_migration_home_runtime_pair_identity',
        'old_commit': OLD, 'new_commit': NEW, 'unit': before[2],
        'catalog_revision': live['catalog_revision'], 'details_coverage': live['details_coverage'],
        'legacy_health_probed': False, 'candidate_health_required': True,
    }
    return verdict, recheck
