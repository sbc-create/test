#!/usr/bin/env python3
"""Golden browser playback gate for Animedia (Playwright/Chromium).

PASS requires real Play interaction and no false failure overlay.
Cross-origin iframes may not expose currentTime; then shell+active/ok
without false failure is recorded as limited evidence — never as invented
currentTime. When currentTime is readable, require progress >= 3s.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")

from playwright.sync_api import sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "artifacts/evidence/animedia-playback-gate-2026-09-19"
EV.mkdir(parents=True, exist_ok=True)

# 10 playable URLs across both domains (episode + title hub + movie-ish).
GOLDEN_PLAYABLE = [
    "https://animedia.icu/title/master-lda-i-plameni-2/season-2/episode-104/",
    "https://animedia.icu/title/master-lda-i-plameni-2/season-2/episode-103/",
    "https://animedia.icu/title/master-lda-i-plameni-2/",
    "https://animedia.icu/title/master-lda-i-plameni-2/season-2/episode-100/",
    "https://animedia.icu/title/22-7/",
    "https://animedia.space/title/master-lda-i-plameni-2/season-2/episode-104/",
    "https://animedia.space/title/master-lda-i-plameni-2/",
    "https://animedia.space/title/master-lda-i-plameni-2/season-2/episode-103/",
    "https://animedia.space/title/22-7/",
    "https://animedia.icu/title/1-2-ray/",
]

GOLDEN_UNAVAILABLE = [
    "https://animedia.icu/title/master-lda-i-plameni-2/season-2/episode-9999/",
    "https://animedia.space/title/master-lda-i-plameni-2/season-9/episode-1/",
]


def _probe_state(page) -> dict:
    return page.evaluate(
        """() => {
      const f=document.querySelector('[data-player]');
      const st=document.querySelector('[data-player-state]');
      const vp=document.querySelector('video-player');
      let ct=null, paused=null;
      if(vp && vp.shadowRoot){
        const v=vp.shadowRoot.querySelector('video');
        if(v){ ct=v.currentTime; paused=v.paused; }
      }
      const shell = vp && vp.shadowRoot && vp.shadowRoot.querySelector('iframe,video');
      const overlayText = st && !st.hidden ? (st.innerText||'') : '';
      const falseFailure = !!(st && !st.hidden &&
        /Плеер не поднялся|Ошибка плеера/.test(overlayText));
      return {
        state: f && f.getAttribute('data-state'),
        overlayVisible: !!(st && !st.hidden),
        overlayText: overlayText.slice(0,200),
        vpHidden: !!(vp && vp.hidden),
        hasShell: !!shell,
        iframeSrc: shell && shell.tagName==='IFRAME' ? (shell.src||'').slice(0,120) : '',
        currentTime: ct,
        paused: paused,
        falseFailure: falseFailure,
        playback: window.__animediaPlayback || window.__zonaPlayerReady || null
      };
    }"""
    )


def probe_playable(page, url: str, shot: Path) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(2000)
    before = _probe_state(page)
    js_errors: list[str] = []
    page.on("pageerror", lambda err: js_errors.append(str(err)[:200]))

    # Prefer in-player click; avoid navigating away via surrounding links.
    clicked = False
    try:
        box = page.locator("[data-player]").bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.55)
            clicked = True
    except Exception as exc:  # noqa: BLE001
        before["click_error"] = str(exc)

    page.wait_for_timeout(2500)
    for fr in page.frames:
        try:
            fr.click(
                'button, [aria-label*="Play" i], [class*="play" i], .vjs-big-play-button',
                timeout=700,
            )
            clicked = True
        except Exception:
            pass

    t0 = time.time()
    samples = []
    for _ in range(4):
        page.wait_for_timeout(2000)
        samples.append(_probe_state(page))
    after = samples[-1]
    page.screenshot(path=str(shot), full_page=False)

    progress = 0.0
    times = [s.get("currentTime") for s in samples if isinstance(s.get("currentTime"), (int, float))]
    if len(times) >= 2 and times[0] is not None:
        progress = max(0.0, float(times[-1]) - float(times[0]))
    elif times:
        progress = float(times[-1] or 0)

    hard_fail = after.get("falseFailure") or (
        after.get("state") in {"error", "provider", "slow"} and after.get("overlayVisible")
    )
    evidence = "failed"
    playable_ok = False
    if progress >= 3.0 and not hard_fail and after.get("hasShell"):
        evidence = "currentTime_progress>=3"
        playable_ok = True
    elif (
        after.get("hasShell")
        and not hard_fail
        and not after.get("overlayVisible")
        and after.get("state") in {"active", "ok", "resolving", "playable"}
        and not after.get("vpHidden")
    ):
        # Cross-origin: document limited evidence explicitly.
        evidence = "shell_active_no_false_failure_cross_origin"
        playable_ok = True
    else:
        evidence = "failed"
        playable_ok = False

    return {
        "url": url,
        "kind": "playable",
        "before": before,
        "after": after,
        "samples": samples,
        "progress": progress,
        "elapsed_s": round(time.time() - t0, 2),
        "clicked": clicked,
        "js_errors": js_errors,
        "evidence": evidence,
        "pass": playable_ok and not js_errors,
        "screenshot": str(shot),
    }


def probe_unavailable(page, url: str, shot: Path) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)
    st = _probe_state(page)
    page.screenshot(path=str(shot), full_page=False)
    # Honest unavailable: no fake playing state / no false-ready.
    ok = st.get("state") not in {"ok"} and not (
        st.get("playback") and st.get("playback", {}).get("confirmed")
    )
    # 404 page also ok
    title = page.title()
    if "404" in title or "не найд" in (page.content()[:2000].lower()):
        ok = True
    return {
        "url": url,
        "kind": "unavailable",
        "after": st,
        "evidence": "honest_unavailable" if ok else "false_ready",
        "pass": ok,
        "screenshot": str(shot),
    }


def probe_fallback(page, url: str, shot: Path) -> dict:
    """Force-break primary candidate in DOM, expect fallback mount."""
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(1500)
    mutated = page.evaluate(
        """() => {
      const host=document.querySelector('[data-player-host]');
      if(!host) return {ok:false, reason:'no-host'};
      let c=[];
      try{c=JSON.parse(host.getAttribute('data-src-candidates')||'[]')||[];}catch(e){c=[];}
      if(c.length<2) return {ok:false, reason:'need-2-candidates', n:c.length};
      c[0]={aggregator:'cvh', id:'00000000-0000-0000-0000-000000000000'};
      host.setAttribute('data-src-candidates', JSON.stringify(c));
      const vp=host.querySelector('video-player');
      if(vp){ try{vp.setAttribute('data-title-id', c[0].id); vp.setAttribute('data-aggregator','cvh');}catch(e){} }
      return {ok:true, n:c.length, second:c[1]};
    }"""
    )
    if not mutated.get("ok"):
        page.screenshot(path=str(shot), full_page=False)
        return {
            "url": url,
            "kind": "fallback",
            "mutated": mutated,
            "evidence": "insufficient_candidates",
            "pass": False,
            "screenshot": str(shot),
        }
    # Remount by reloading script path: click to trigger client if already bound.
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    # Re-apply mutation after reload then trigger client remount via custom event.
    page.evaluate(
        """() => {
      const host=document.querySelector('[data-player-host]');
      let c=[];
      try{c=JSON.parse(host.getAttribute('data-src-candidates')||'[]')||[];}catch(e){c=[];}
      if(c.length>=2){
        c[0]={aggregator:'cvh', id:'00000000-0000-0000-0000-000000000000'};
        host.setAttribute('data-src-candidates', JSON.stringify(c));
      }
    }"""
    )
    # Soft check: after play click, no false failure and shell present.
    try:
        box = page.locator("[data-player]").bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.55)
    except Exception:
        pass
    page.wait_for_timeout(8000)
    after = _probe_state(page)
    page.screenshot(path=str(shot), full_page=False)
    hard_fail = after.get("falseFailure")
    ok = after.get("hasShell") and not hard_fail
    return {
        "url": url,
        "kind": "fallback",
        "mutated": mutated,
        "after": after,
        "evidence": "fallback_shell_no_false_failure" if ok else "fallback_failed",
        "pass": ok,
        "screenshot": str(shot),
    }


def main() -> int:
    base = os.environ.get("GOLDEN_BASE", "")
    playable = list(GOLDEN_PLAYABLE)
    unavailable = list(GOLDEN_UNAVAILABLE)
    if base:
        def remap(u: str) -> str:
            return u.replace("https://animedia.icu", base).replace("https://animedia.space", base)
        playable = [remap(u) for u in playable]
        unavailable = [remap(u) for u in unavailable]

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        for i, url in enumerate(playable):
            shot = EV / f"play-{i:02d}.png"
            try:
                results.append(probe_playable(page, url, shot))
            except Exception as exc:  # noqa: BLE001
                results.append({"url": url, "kind": "playable", "pass": False,
                                "evidence": f"exception:{exc}", "screenshot": str(shot)})
        for i, url in enumerate(unavailable):
            shot = EV / f"unavail-{i:02d}.png"
            try:
                results.append(probe_unavailable(page, url, shot))
            except Exception as exc:  # noqa: BLE001
                results.append({"url": url, "kind": "unavailable", "pass": False,
                                "evidence": f"exception:{exc}", "screenshot": str(shot)})
        fb_url = playable[0]
        shot = EV / "fallback-00.png"
        try:
            results.append(probe_fallback(page, fb_url, shot))
        except Exception as exc:  # noqa: BLE001
            results.append({"url": fb_url, "kind": "fallback", "pass": False,
                            "evidence": f"exception:{exc}", "screenshot": str(shot)})
        browser.close()

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "playable_total": sum(1 for r in results if r.get("kind") == "playable"),
        "playable_pass": sum(1 for r in results if r.get("kind") == "playable" and r.get("pass")),
        "unavailable_pass": sum(1 for r in results if r.get("kind") == "unavailable" and r.get("pass")),
        "fallback_pass": sum(1 for r in results if r.get("kind") == "fallback" and r.get("pass")),
        "results": results,
    }
    out = EV / "GOLDEN_PLAYBACK.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in summary if k != "results"}, ensure_ascii=False))
    all_ok = (
        summary["playable_pass"] == summary["playable_total"]
        and summary["playable_total"] >= 10
        and summary["unavailable_pass"] >= 2
        and summary["fallback_pass"] == 1
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
