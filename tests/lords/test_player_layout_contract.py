"""Release-blocking: small centered player must never ship.

Validates source contract marker, CSS specificity vs global iframe{height:auto},
client full-bleed normalizer (MutationObserver + ResizeObserver), and the
artifact gate script used by deploy.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ИСХОДНИК = pathlib.Path(__file__).resolve().parents[2] / "automation" / "host" / "lords-frontend.py"
GATE = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "gate_lords_player_layout.py"
CONTRACT = 'data-player-layout-contract="full-bleed-v1"'


def _текст() -> str:
    return ИСХОДНИК.read_text(encoding="utf-8")


def _client() -> str:
    m = re.search(r'СКРИПТ_ПЛЕЕРА_КЛИЕНТ = """(.*?)"""', _текст(), re.S)
    assert m
    return m.group(1)


class TestPlayerLayoutContractSource:
    def test_contract_marker_on_shells(self):
        t = _текст()
        # SSR shells for Lords + Zona families all carry the marker.
        assert t.count('data-player data-player-layout-contract="full-bleed-v1"') >= 5
        assert 'class="pl__frame" data-player data-player-layout-contract="full-bleed-v1"' in t

    def test_css_beats_global_iframe_height_auto(self):
        t = _текст()
        assert "img,video,iframe,svg{max-width:100%;height:auto;display:block}" in t
        assert '[data-player-layout-contract="full-bleed-v1"] iframe' in t
        assert "height:100% !important" in t
        assert "max-width:none !important" in t
        css = t[t.index("/* Плеер: полоса вкладок"):t.index("/* Сезоны и серии.")]
        head = css.split("[data-player-state]")[0]
        assert "place-items:center" not in head

    def test_no_fixed_640_in_player_chain(self):
        css = _текст()[_текст().index("/* Плеер: полоса вкладок"): _текст().index("/* Сезоны и серии.")]
        assert "640px" not in css
        assert "360px" not in css

    def test_client_normalizer_idempotent_and_async(self):
        s = _client()
        assert "fitPlayerTree" in s
        assert "ensureLayoutObserver" in s
        assert "MutationObserver" in s
        assert "ResizeObserver" in s
        assert "__fullBleedBound" in s
        assert "busy" in s
        assert "childList:true" in s
        assert "max-width" in s and "none" in s
        assert s.count("querySelector('[data-player]')") == 1
        assert "data-player-layout-contract" in s


class TestPlayerLayoutArtifactGate:
    def test_gate_script_passes_current_source(self):
        proc = subprocess.run(
            [sys.executable, str(GATE), "--artifact", str(ИСХОДНИК)],
            capture_output=True, text=True, check=False,
        )
        assert proc.returncode == 0, proc.stderr or proc.stdout
        assert "GATE_PASS" in proc.stdout

    def test_gate_rejects_artifact_without_contract(self, tmp_path):
        bad = tmp_path / "lords-frontend.py"
        bad.write_text("print('no contract')\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(GATE), "--artifact", str(bad)],
            capture_output=True, text=True, check=False,
        )
        assert proc.returncode == 1
        assert "GATE_FAIL" in (proc.stderr + proc.stdout)
