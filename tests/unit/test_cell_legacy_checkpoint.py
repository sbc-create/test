import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from factory.cell import legacy_checkpoint as policy, privileged, rollback_state

@pytest.fixture
def env(tmp_path, monkeypatch):
    releases = tmp_path / 'releases'; releases.mkdir()
    old = releases / policy.OLD[:12]; new = releases / policy.NEW[:12]
    for folder, commit in [(old, policy.OLD), (new, policy.NEW)]:
        folder.mkdir(); (folder / 'config').mkdir(); (folder / 'src').mkdir()
        (folder / 'release-manifest.json').write_text(json.dumps({
            'site_id': policy.SITE, 'commit': commit, 'digest': policy.DIGESTS[commit],
            'release': commit[:12], 'installed_by': 'cell-executor',
            'live_build_id': commit[:12] + '-' + policy.SITE}))
    (tmp_path / 'current').symlink_to(old); (tmp_path / 'candidate').symlink_to(new)
    manifest = {'site_repo_commit': policy.OLD, 'site_repo_dirty': False,
                'build_id': policy.OLD[:12] + '-' + policy.SITE}
    (old / 'config/template-manifest.json').write_text(json.dumps(manifest))
    code = {'src/lords-frontend.py': b'fixture core', 'src/lords05-frontend.py': b'fixture entry'}
    for name, raw in code.items(): (old / name).write_bytes(raw)
    monkeypatch.setattr(policy, 'OLD_CODE', {n: hashlib.sha256(b).hexdigest() for n,b in code.items()})
    unit = {'ActiveState': 'active', 'MainPID': '123', 'InvocationID': 'fixture'}
    monkeypatch.setattr(policy, 'unit_state', lambda name: dict(unit))
    runtime = dict(manifest, catalog_revision='rev', details_catalog_revision='rev',
                   catalog_built_at='date', details_catalog_built_at='date',
                   catalog_details_skew=False, details_coverage=72246)
    monkeypatch.setattr(policy, 'runtime_version', lambda port: dict(runtime))
    platform = privileged.Площадка(policy.SITE, 'nobody', tmp_path, tmp_path/'app', tmp_path/'data',
                                  'fixture.service', None, 9113)
    calls = []
    def verify(site, **kwargs):
        calls.append(kwargs)
        commit = policy.OLD if kwargs['порт'] == platform.port else policy.NEW
        return {'ok': True, 'build_id': commit[:12] + '-' + site}
    return SimpleNamespace(platform=platform, old=old, new=new, runtime=runtime,
                           unit=unit, calls=calls, verify=verify)

def test_exact_transition_uses_home_and_runtime_not_old_health(env):
    verdict, fence = policy.primary(env.platform, env.verify)
    assert verdict['ok'] and callable(fence)
    assert env.calls[0]['маршруты'] == ('/',)
    assert env.calls[0]['ожидаемый_build'] == policy.OLD[:12] + '-' + policy.SITE
    assert verdict['primary_checkpoint_proof']['candidate_health_required']
    fence()

@pytest.mark.parametrize('field,value', [
    ('site_repo_commit', 'a'*40), ('site_repo_dirty', True), ('build_id', 'wrong'),
    ('details_catalog_revision', 'different'), ('catalog_revision', ''),
    ('details_catalog_built_at', 'different'), ('catalog_built_at', ''),
    ('catalog_details_skew', True), ('details_coverage', 0), ('details_coverage', True)])
def test_runtime_drift_fails_closed(env, field, value):
    env.runtime[field] = value
    with pytest.raises(ValueError): policy.primary(env.platform, env.verify)

@pytest.mark.parametrize('mutation', ['old_digest', 'new_digest', 'code', 'manifest', 'candidate_link'])
def test_files_and_candidate_are_bound(env, mutation):
    if mutation.endswith('digest'):
        p = (env.old if mutation == 'old_digest' else env.new) / 'release-manifest.json'
        data = json.loads(p.read_text()); data['digest'] = 'sha256:' + '0'*64; p.write_text(json.dumps(data))
    elif mutation == 'code': (env.old/'src/lords-frontend.py').write_text('changed')
    elif mutation == 'manifest': (env.old/'config/template-manifest.json').write_text('{}')
    else:
        env.platform.candidate.unlink(); env.platform.candidate.symlink_to(env.old)
    with pytest.raises(ValueError): policy.primary(env.platform, env.verify)

@pytest.mark.parametrize('mutation', ['pid', 'invocation', 'current', 'code', 'provenance'])
def test_fence_rejects_changes_after_http(env, mutation):
    _, fence = policy.primary(env.platform, env.verify)
    if mutation == 'pid': env.unit['MainPID'] = '456'
    elif mutation == 'invocation': env.unit['InvocationID'] = 'changed'
    elif mutation == 'current':
        env.platform.current.unlink(); env.platform.current.symlink_to(env.new)
    elif mutation == 'code': (env.old/'src/lords-frontend.py').write_text('changed')
    else: (env.new/'release-manifest.json').write_text('{}')
    with pytest.raises(ValueError): fence()

def test_other_site_keeps_default_health(env):
    env.platform.site_id = 'zona-01'
    _, fence = policy.primary(env.platform, env.verify)
    assert fence is None and 'маршруты' not in env.calls[0]

def test_home_identity_failure_cannot_be_overridden_by_version(env):
    with pytest.raises(ValueError): policy.primary(env.platform, lambda *a,**kw: {'ok':False})

@pytest.mark.parametrize('candidate_result', ['success', 'failed', 'wrong_build', 'old_process_changed'])
def test_checkpoint_integration_preserves_candidate_health_and_rollback(env, monkeypatch, candidate_result):
    monkeypatch.setattr(privileged, '_нужен_root', lambda: None)
    monkeypatch.setattr(privileged.Площадка, 'из_реестра', lambda *a,**kw: env.platform)
    monkeypatch.setattr(privileged, '_объявление_обработчика', lambda *a: {})
    captures = []
    monkeypatch.setattr(rollback_state, 'capture', lambda *a,**kw: captures.append(kw) or {'checkpoint':'fixture'})
    def verify(site, **kwargs):
        result = env.verify(site, **kwargs)
        if kwargs['порт'] == env.platform.port:
            assert kwargs.get('маршруты') == ('/',), 'legacy primary must not invoke unbounded health'
        if kwargs['порт'] == env.platform.candidate_port:
            assert 'маршруты' not in kwargs  # Default home + /healthz remains mandatory.
            if candidate_result == 'failed': result['ok'] = False
            elif candidate_result == 'wrong_build': result['build_id'] = 'wrong'
            elif candidate_result == 'old_process_changed': env.unit['MainPID'] = '456'
        return result
    monkeypatch.setattr(privileged, 'verify', verify)
    if candidate_result == 'success':
        result = privileged.capture_release_state(policy.SITE)
        assert len(captures) == 1 and result['primary_checkpoint_proof']['old_commit'] == policy.OLD
    else:
        with pytest.raises((ValueError, privileged.PrivilegedRefused)):
            privileged.capture_release_state(policy.SITE)
        assert not captures


@pytest.mark.parametrize('mode', ['valid', 'redirect', 'oversize', 'array'])
def test_runtime_transport_is_bounded_and_refuses_redirects(mode):
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.error import HTTPError
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            if mode == 'redirect':
                self.send_response(302); self.send_header('Location', '/must-not-follow'); self.end_headers(); return
            body = b'{"ok":true}' if mode == 'valid' else (b'[]' if mode == 'array' else b' ' * 262145)
            self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        def log_message(self, *args): pass
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever); thread.start()
    try:
        if mode == 'valid': assert policy.runtime_version(server.server_port) == {'ok': True}
        else:
            with pytest.raises((ValueError, HTTPError)):
                policy.runtime_version(server.server_port)
        assert calls == ['/__template_version']
    finally:
        server.shutdown(); thread.join(); server.server_close()

@pytest.mark.parametrize('checkpoint', [False, True])
def test_rollback_uses_bounded_old_identity_and_preserves_full_candidate_health(env, monkeypatch, tmp_path, checkpoint):
    from subprocess import CompletedProcess
    monkeypatch.setattr(privileged, '_нужен_root', lambda: None)
    monkeypatch.setattr(privileged.Площадка, 'из_реестра', lambda *a,**kw: env.platform)
    state = tmp_path/'state'; state.mkdir(); monkeypatch.setattr(rollback_state, 'STATE_ROOT', state)
    if checkpoint:
        (state/(policy.SITE+'.json')).write_text(json.dumps({
            'site_id':policy.SITE, 'old_current':str(env.old), 'new_current':str(env.new),
            'old_build_id':policy.OLD[:12]+'-'+policy.SITE, 'new_build_id':policy.NEW[:12]+'-'+policy.SITE}))
    actions = []
    monkeypatch.setattr(privileged, '_systemctl', lambda *a,**kw: actions.append(('unit',a)) or CompletedProcess(a,0,''))
    monkeypatch.setattr(privileged, 'switch_route', lambda *a,**kw: actions.append(('route',a[1])))
    monkeypatch.setattr(privileged.subprocess, 'run', lambda *a,**kw: CompletedProcess(a,0,''))
    monkeypatch.setattr(privileged.time, 'sleep', lambda n: None)
    def ready(port, **kwargs):
        assert port == env.platform.candidate_port, 'legacy health readiness must not run'
        actions.append(('candidate_health_ready',port)); return {'ready':True}
    monkeypatch.setattr(privileged, 'готов', ready)
    def verify(site, **kwargs):
        if kwargs['порт'] == env.platform.port: assert kwargs.get('маршруты') == ('/',)
        else: assert 'маршруты' not in kwargs
        return env.verify(site, **kwargs)
    monkeypatch.setattr(privileged, 'verify', verify)
    def restore(*args, **kwargs):
        if not checkpoint:return None
        verdict=kwargs['wait_ready'](policy.OLD[:12]+'-'+policy.SITE)
        assert verdict['ok']; actions.append(('restored_after_old_identity',))
        return {'restored_current':str(env.old)}
    monkeypatch.setattr(rollback_state, 'restore', restore)
    result=privileged.rollback(policy.SITE,dry_run=False,предел=0)
    assert result['ready']['ready'] and result['verify']['ok']
    assert ('unit',('stop',env.platform.candidate_unit)) in actions
    if checkpoint:
        assert ('candidate_health_ready',env.platform.candidate_port) in actions
        assert ('restored_after_old_identity',) in actions
    assert env.unit['MainPID']=='123'


def test_rollback_identity_failure_does_not_route_or_stop_candidate(env, monkeypatch, tmp_path):
    from subprocess import CompletedProcess
    monkeypatch.setattr(privileged, '_нужен_root', lambda:None)
    monkeypatch.setattr(privileged.Площадка, 'из_реестра', lambda *a,**kw:env.platform)
    monkeypatch.setattr(rollback_state, 'STATE_ROOT', tmp_path/'absent')
    monkeypatch.setattr(rollback_state, 'restore', lambda *a,**kw:None)
    actions=[]
    monkeypatch.setattr(privileged,'_systemctl',lambda *a,**kw:actions.append(a) or CompletedProcess(a,0,''))
    monkeypatch.setattr(privileged,'switch_route',lambda *a,**kw:pytest.fail('must not switch route'))
    monkeypatch.setattr(privileged,'готов',lambda *a,**kw:pytest.fail('must not probe legacy health'))
    monkeypatch.setattr(privileged,'verify',env.verify)
    env.runtime['site_repo_commit']='a'*40
    with pytest.raises(TimeoutError):privileged.rollback(policy.SITE,dry_run=False,предел=0)
    assert all(a[0] not in ('stop','restart') for a in actions)
