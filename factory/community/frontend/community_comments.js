/**
 * Community comments widget — dark mode.
 * Hidden from public unless COMMENTS_PUBLIC_READ_ENABLED=1.
 * Admin preview mounts with data-admin-preview="1".
 * Reuses yummy_cr_vid identity cookie; does not mint a second cookie.
 */
(function (global) {
  "use strict";

  var STATES = {
    empty: "empty",
    loading: "loading",
    error: "error",
    pending: "pending",
    quarantined: "quarantined",
    published: "published",
    edited: "edited",
    deleted: "deleted",
    spoiler: "spoiler",
    rateLimited: "rate-limited",
  };

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function CommunityCommentsBlock(root, opts) {
    this.root = root;
    this.opts = opts || {};
    this.space = opts.siteSpace || "yummy";
    this.titleId = opts.titleId || "";
    this.apiBase = opts.apiBase || "/api/community/comments";
    this.adminPreview = !!opts.adminPreview;
    this.publicRead = !!opts.publicRead;
    this.state = {
      phase: STATES.loading,
      comments: [],
      error: null,
      rateLimited: false,
    };
  }

  CommunityCommentsBlock.prototype.mount = function () {
    if (!this.publicRead && !this.adminPreview) {
      this.root.hidden = true;
      this.root.setAttribute("data-comments-dark", "1");
      this.root.innerHTML = "";
      return;
    }
    this.root.hidden = false;
    this.root.setAttribute("data-comments-dark", this.publicRead ? "0" : "1");
    this.render();
    this.load();
  };

  CommunityCommentsBlock.prototype.render = function () {
    var s = this.state;
    var body = "";
    if (s.phase === STATES.loading) {
      body =
        '<p class="cc-status" role="status" aria-live="polite">Загрузка комментариев…</p>';
    } else if (s.phase === STATES.error) {
      body =
        '<p class="cc-status cc-status--error" role="alert">' +
        escapeHtml(s.error || "Ошибка загрузки") +
        "</p>";
    } else if (s.rateLimited) {
      body =
        '<p class="cc-status cc-status--rate" role="status">Слишком много попыток. Подождите минуту.</p>';
    } else if (!s.comments.length) {
      body =
        '<p class="cc-status cc-status--empty" role="status">Пока нет комментариев</p>';
    } else {
      body = '<ul class="cc-list" role="list">' + s.comments.map(renderItem).join("") + "</ul>";
    }

    var form = this.adminPreview
      ? '<form class="cc-form" aria-label="Новый комментарий (admin preview)">' +
        '<label class="cc-label" for="cc-body">Комментарий</label>' +
        '<textarea id="cc-body" class="cc-input" maxlength="4000" rows="3" required></textarea>' +
        '<label class="cc-spoiler"><input type="checkbox" name="spoiler" /> Спойлер</label>' +
        '<button type="submit" class="cc-submit" style="min-width:44px;min-height:44px">Отправить</button>' +
        "</form>"
      : "";

    this.root.innerHTML =
      '<section class="cc-block" data-space="' +
      escapeHtml(this.space) +
      '" aria-label="Комментарии">' +
      "<h2 class=\"cc-title\">Комментарии</h2>" +
      (this.adminPreview
        ? '<p class="cc-banner" role="note">Admin preview — не публичный режим</p>'
        : "") +
      body +
      form +
      "</section>";

    var self = this;
    var formEl = this.root.querySelector(".cc-form");
    if (formEl) {
      formEl.addEventListener("submit", function (ev) {
        ev.preventDefault();
        self.onSubmit(formEl);
      });
    }
    this.root.querySelectorAll("[data-spoiler-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var panel = btn.parentElement.querySelector(".cc-spoiler-body");
        if (!panel) return;
        var open = panel.hasAttribute("hidden");
        if (open) panel.removeAttribute("hidden");
        else panel.setAttribute("hidden", "");
        btn.setAttribute("aria-expanded", open ? "true" : "false");
      });
    });
  };

  function renderItem(c) {
    var status = c.status || "PENDING";
    var cls = "cc-item cc-item--" + String(status).toLowerCase().replace(/_/g, "-");
    if (c.edited_at) cls += " cc-item--edited";
    var meta = escapeHtml(status);
    if (c.edited_at) meta += " · изменено";
    var content;
    if (status === "DELETED_BY_USER" || status === "REMOVED_BY_MODERATOR") {
      content = '<p class="cc-deleted">Комментарий удалён</p>';
    } else if (c.spoiler) {
      content =
        '<button type="button" class="cc-spoiler-btn" data-spoiler-toggle aria-expanded="false" style="min-width:44px;min-height:44px">Показать спойлер</button>' +
        '<div class="cc-spoiler-body" hidden><p class="cc-body">' +
        escapeHtml(c.body || "") +
        "</p></div>";
    } else {
      content = '<p class="cc-body">' + escapeHtml(c.body || "") + "</p>";
    }
    var reply =
      c.parent_comment_id
        ? '<p class="cc-reply-to">Ответ</p>'
        : "";
    return (
      '<li class="' +
      cls +
      '" data-comment-id="' +
      escapeHtml(c.comment_id || "") +
      '">' +
      reply +
      '<div class="cc-meta">' +
      meta +
      "</div>" +
      content +
      "</li>"
    );
  }

  CommunityCommentsBlock.prototype.load = function () {
    var self = this;
    this.state.phase = STATES.loading;
    this.render();
    var url =
      this.apiBase +
      "?site_space=" +
      encodeURIComponent(this.space) +
      "&title_id=" +
      encodeURIComponent(this.titleId) +
      (this.adminPreview ? "&admin_preview=1" : "");
    fetch(url, { credentials: "same-origin" })
      .then(function (r) {
        if (r.status === 429) {
          self.state.rateLimited = true;
          self.state.phase = STATES.rateLimited;
          self.render();
          return null;
        }
        if (!r.ok) throw new Error("load failed");
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        self.state.comments = data.comments || [];
        self.state.phase = self.state.comments.length ? STATES.published : STATES.empty;
        self.state.error = null;
        self.render();
      })
      .catch(function (err) {
        self.state.phase = STATES.error;
        self.state.error = (err && err.message) || "error";
        self.render();
      });
  };

  CommunityCommentsBlock.prototype.onSubmit = function (form) {
    var self = this;
    var ta = form.querySelector("#cc-body");
    var spoiler = !!(form.querySelector('[name="spoiler"]') || {}).checked;
    var body = (ta && ta.value) || "";
    fetch(this.apiBase, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        site_space: this.space,
        title_id: this.titleId,
        body: body,
        spoiler: spoiler,
      }),
    })
      .then(function (r) {
        if (r.status === 429) {
          self.state.rateLimited = true;
          self.render();
          return null;
        }
        if (r.status === 403) {
          self.state.phase = STATES.error;
          self.state.error = "Запись отключена (dark mode)";
          self.render();
          return null;
        }
        if (!r.ok) throw new Error("submit failed");
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        self.load();
      })
      .catch(function (err) {
        self.state.phase = STATES.error;
        self.state.error = (err && err.message) || "error";
        self.render();
      });
  };

  global.CommunityCommentsBlock = CommunityCommentsBlock;
})(typeof window !== "undefined" ? window : globalThis);
