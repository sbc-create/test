"""Раздел админки «Приложение „Кинатека“»: главная, подборки, оформление.

Как и вся панель, раздел ничего не делает сам: формы превращаются в документ
черновика и уходят в Control API (`/api/v1/apps/kinateka/...`), а проверка,
публикация, откат и журнал — там. Каждая форма несёт версию черновика, с
которой страница была показана: если кто-то успел сохранить свою правку, API
ответит 409, и оператор увидит конфликт, а не тихую перезапись.

Решение владельца 2026-10-27: управление приложением — разделом этой админки.
"""
from __future__ import annotations

import datetime
import json
from typing import Any

from factory.site_engine.admin import ui_app

APP = "kinateka"
BASE = f"/admin/apps/{APP}"
API = f"/api/v1/apps/{APP}"
CHANNELS = ("sandbox", "production")


def _lines(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").replace("\r", "").split("\n") if line.strip()]


def _number(raw: str | None, default: float) -> float:
    try:
        return float(str(raw).replace(",", "."))
    except (TypeError, ValueError):
        return default


class AppSection:
    def __init__(self, admin) -> None:
        self.admin = admin

    # ---- чтение ------------------------------------------------------------

    def handle(self, session, method: str, rest: list[str], form: dict[str, str],
               flash, label: str, csrf: str):
        from factory.site_engine.admin.app import AdminResponse, _redirect

        if not rest:
            if method != "GET":
                return None
            r = self.admin._call("GET", API, session)
            if r.status != 200:
                return AdminResponse(status=r.status, html=ui_app.unavailable(r, label, csrf))
            return AdminResponse(status=200, html=ui_app.overview(
                r.body, flash=flash, session_label=label, csrf=csrf,
                can_write=self._can_write(session)))
        if rest[0] == "devices":
            return self._devices(session, method, rest[1:], form, label, csrf, flash)
        channel = rest[0]
        if channel not in CHANNELS:
            return None
        tail = rest[1:]
        if method == "GET" and not tail:
            r = self.admin._call("GET", f"{API}/channels/{channel}", session)
            if r.status != 200:
                return AdminResponse(status=r.status, html=ui_app.unavailable(r, label, csrf))
            return AdminResponse(status=200, html=ui_app.channel(
                r.body, flash=flash, session_label=label, csrf=csrf,
                can_write=self._can_write(session)))
        if method == "GET" and len(tail) == 2 and tail[0] == "collections":
            r = self.admin._call("GET", f"{API}/channels/{channel}", session)
            if r.status != 200:
                return AdminResponse(status=r.status, html=ui_app.unavailable(r, label, csrf))
            query = (form.get("q") or "").strip()
            found = None
            if len(query) >= 2:
                s = self.admin._call("GET", f"{API}/catalog", session, {"q": query})
                found = s.body.get("items", []) if s.status == 200 else []
            return AdminResponse(status=200, html=ui_app.collection(
                r.body, tail[1], flash=flash, session_label=label, csrf=csrf,
                can_write=self._can_write(session), query=query, found=found))
        if method != "POST":
            return None

        back = f"{BASE}/{channel}"
        if tail == ["publish"]:
            body = {"expectedVersion": form.get("draftVersion", ""),
                    "expectedRevision": self._int_or_none(form.get("expectedRevision")),
                    "comment": form.get("comment", "")}
            r = self.admin._call("POST", f"{API}/channels/{channel}/publish", session, body)
            session.flash = self.admin._flash_from(
                r, success=f"Опубликовано в {channel}: ревизия {r.body.get('revision')}.")
            return _redirect(back)
        if tail == ["rollback"]:
            body = {"toRevision": self._int_or_none(form.get("toRevision")),
                    "expectedRevision": self._int_or_none(form.get("expectedRevision")),
                    "comment": form.get("comment", "")}
            r = self.admin._call("POST", f"{API}/channels/{channel}/rollback", session, body)
            session.flash = self.admin._flash_from(
                r, success=f"Канал {channel} возвращён на ревизию {body['toRevision']}.")
            return _redirect(back)
        if tail == ["import"]:
            body = {"fromRevision": self._int_or_none(form.get("fromRevision")),
                    "expectedVersion": form.get("draftVersion", "")}
            r = self.admin._call("POST", f"{API}/channels/{channel}/import", session, body)
            session.flash = self.admin._flash_from(
                r, success=f"Ревизия {body['fromRevision']} скопирована в черновик {channel}. "
                           "Проверьте предпросмотр и опубликуйте отдельно.")
            return _redirect(back)

        # Остальное — правки черновика: прочитать, изменить, сохранить со сверкой.
        current = self.admin._call("GET", f"{API}/channels/{channel}", session)
        if current.status != 200:
            session.flash = self.admin._flash_from(current, success="")
            return _redirect(back)
        draft = json.loads(json.dumps(current.body.get("draft") or {}))
        if tail == ["artwork", "mark"] and not (form.get("imageUrl") or "").strip():
            # Отметка по contentId: картинка — нынешний постер тайтла в каталоге.
            cid = (form.get("contentId") or "").strip()
            s = self.admin._call("GET", f"{API}/catalog", session, {"q": cid}) if len(cid) >= 2 else None
            hit = next((t for t in (s.body.get("items", []) if s and s.status == 200 else [])
                        if t.get("contentId") == cid), None)
            form = {**form, "imageUrl": (hit or {}).get("posterUrl") or ""}
        try:
            target = self._apply(draft, tail, form)
        except ValueError as exc:
            session.flash = {"ok": False, "message": str(exc), "detail": None}
            return _redirect(back)
        r = self.admin._call("POST", f"{API}/channels/{channel}/draft", session,
                             {"draft": draft, "expectedVersion": form.get("draftVersion", "")})
        problems = (r.body or {}).get("problems") if r.status == 200 else None
        success = "Черновик сохранён." + (
            f" До публикации исправить: {len(problems)}." if problems else " Готов к публикации.")
        session.flash = self.admin._flash_from(r, success=success)
        return _redirect(f"{back}{target}")

    def _devices(self, session, method: str, tail: list[str], form: dict[str, str], label: str, csrf: str,
                 flash):
        """Устройства с доступом к каталогу; код из ответа API — только во вспышку, один раз."""
        from factory.site_engine.admin.app import AdminResponse, _redirect

        back = f"{BASE}/devices"
        if method == "GET" and not tail:
            r = self.admin._call("GET", f"{API}/devices", session)
            if r.status != 200:
                return AdminResponse(status=r.status, html=ui_app.unavailable(r, label, csrf))
            return AdminResponse(status=200, html=ui_app.devices(
                r.body, flash=flash, session_label=label, csrf=csrf, can_write=self._can_write(session)))
        if method != "POST":
            return None
        if tail == ["add"]:
            r = self.admin._call("POST", f"{API}/devices", session, {"name": form.get("name", "")})
        elif len(tail) == 2 and tail[1] in ("code", "revoke"):
            r = self.admin._call("POST", f"{API}/devices/{tail[0]}/{tail[1]}", session, {})
        else:
            return None
        if r.status == 200 and r.body.get("code"):
            session.flash = {"ok": True, "detail": None, "message":
                             f"Код для «{r.body.get('name')}»: {r.body['code']} — введите его в приложении "
                             f"до {r.body.get('codeExpiresAt')} (UTC). Код показывается один раз и действует "
                             "один раз."}
        else:
            flash_ = self.admin._flash_from(r, success=f"Доступ «{r.body.get('name')}» отозван.")
            flash_["detail"] = None if r.status == 200 else flash_["detail"]
            session.flash = flash_
        return _redirect(back)

    def _can_write(self, session) -> bool:
        return "app:write" in self.admin._scopes(session)

    @staticmethod
    def _int_or_none(raw: str | None) -> int | None:
        raw = (raw or "").strip()
        return int(raw) if raw.lstrip("-").isdigit() else None

    # ---- правки черновика ---------------------------------------------------

    def _apply(self, draft: dict[str, Any], tail: list[str], form: dict[str, str]) -> str:
        """Изменить черновик по форме; вернуть хвост адреса, куда вернуться."""
        home = draft.setdefault("home", {}).setdefault("blocks", [])
        collections = draft.setdefault("collections", [])
        if tail == ["appearance"]:
            draft["appearance"] = {
                "accent": (form.get("accent") or "").strip().upper(),
                "heroStyle": form.get("heroStyle") or "backdrop",
                "rowCardStyle": form.get("rowCardStyle") or "poster",
                "focusScale": round(_number(form.get("focusScale"), 1.08), 2),
            }
            return "#appearance"
        if tail == ["blocks"]:
            # Порядок задаётся числами: перестановка без скрипта и без
            # десятка отдельных запросов «выше/ниже».
            ordered = []
            for i, b in enumerate(home):
                bid = b.get("id")
                if form.get(f"delete_{bid}"):
                    continue
                b["visible"] = bool(form.get(f"visible_{bid}"))
                if f"title_{bid}" in form and b.get("kind") != "continue":
                    b["title"] = form[f"title_{bid}"].strip()
                if f"cardStyle_{bid}" in form and b.get("kind") == "collection":
                    b["cardStyle"] = form[f"cardStyle_{bid}"]
                if f"cover_{bid}" in form and b.get("kind") == "collection":
                    b["cover"] = form[f"cover_{bid}"].strip() or None
                ordered.append((_number(form.get(f"order_{bid}"), i + 1), i, b))
            home[:] = [b for _, _, b in sorted(ordered, key=lambda t: (t[0], t[1]))]
            return "#blocks"
        if tail == ["blocks", "add"]:
            kind = form.get("kind") or ""
            bid = (form.get("id") or "").strip()
            block: dict[str, Any] = {"id": bid, "kind": kind, "visible": True}
            if kind in ("hero", "collection"):
                block["collectionId"] = (form.get("collectionId") or "").strip()
            if kind == "genre":
                block["genre"] = (form.get("genre") or "").strip()
            if kind in ("collection", "recent", "genre"):
                block["title"] = (form.get("title") or "").strip()
            if kind == "collection":
                block["cardStyle"] = form.get("cardStyle") or "poster"
            home.append(block)
            return "#blocks"
        if tail == ["collections", "add"]:
            cid = (form.get("id") or "").strip()
            collections.append({"id": cid, "title": (form.get("title") or "").strip(),
                                "source": "", "checkedAt": "", "items": []})
            return f"/collections/{cid}"
        if len(tail) >= 2 and tail[0] == "collections":
            cid = tail[1]
            c = next((x for x in collections if x.get("id") == cid), None)
            if c is None:
                raise ValueError(f"подборки {cid} нет в черновике")
            if tail[2:] == ["delete"]:
                collections.remove(c)
                return "#collections"
            if tail[2:] == []:
                for key in ("title", "subtitle", "description", "source", "checkedAt", "validUntil",
                            "cover"):
                    if key in form:
                        value = form[key].strip()
                        if value:
                            c[key] = value
                        else:
                            c.pop(key, None)
                items = []
                for n, it in enumerate(c.get("items") or []):
                    key = it.get("contentId")
                    if form.get(f"remove_{key}"):
                        continue
                    for field in ("reason", "source", "checkedAt"):
                        if f"{field}_{key}" in form:
                            it[field] = form[f"{field}_{key}"].strip()
                    items.append((_number(form.get(f"order_{key}"), n + 1), n, it))
                c["items"] = [it for _, _, it in sorted(items, key=lambda t: (t[0], t[1]))]
                # Добавление: строка «contentId | причина | источник».
                for line in _lines(form.get("add", "")):
                    parts = [p.strip() for p in line.split("|")]
                    if any(x.get("contentId") == parts[0] for x in c["items"]):
                        continue
                    c["items"].append({"contentId": parts[0],
                                       "reason": parts[1] if len(parts) > 1 else "",
                                       "source": parts[2] if len(parts) > 2 else c.get("source", ""),
                                       "checkedAt": c.get("checkedAt", "")})
                return f"/collections/{cid}"
        if tail[:1] == ["artwork"]:
            # Пригодность изображения для общей витрины — отметка по конкретной
            # картинке, а не по тайтлу: сменится постер — отметка перестанет действовать.
            art = draft.setdefault("artwork", {})
            if not isinstance(art, dict) or not isinstance(art.setdefault("reviews", []), list):
                raise ValueError("Поле artwork черновика не по форме — поправьте его в «Документ черновика целиком».")
            reviews = art["reviews"]
            cid = (form.get("contentId") or "").strip()
            url = (form.get("imageUrl") or "").strip()
            if not cid or not url:
                raise ValueError("Нет такого тайтла в каталоге или у него нет постера.")
            reviews[:] = [r for r in reviews if not (isinstance(r, dict) and r.get("contentId") == cid
                                                     and r.get("imageUrl") == url)]
            if tail == ["artwork", "mark"]:
                verdict = form.get("verdict") or ""
                if verdict not in ("ok", "explicit"):
                    raise ValueError("Вердикт: «подходит» или «откровенная».")
                entry = {"contentId": cid, "imageUrl": url, "verdict": verdict,
                         "reviewedAt": datetime.datetime.now(datetime.timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ")}
                note = (form.get("note") or "").strip()
                if note:
                    entry["note"] = note[:140]
                reviews.append(entry)
            elif tail != ["artwork", "remove"]:
                raise ValueError("Нет такого действия.")
            return "#artwork"
        if tail == ["json"]:
            try:
                replacement = json.loads(form.get("document") or "")
            except json.JSONDecodeError as exc:
                raise ValueError(f"Документ не разобран как JSON: {exc.msg}, строка {exc.lineno}.") from exc
            if not isinstance(replacement, dict):
                raise ValueError("Документ — объект JSON.")
            draft.clear()
            draft.update(replacement)
            return "#json"
        raise ValueError("Нет такого действия.")
