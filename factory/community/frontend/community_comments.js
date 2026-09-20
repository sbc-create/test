/**
 * Community comments widget — dark / staging preview.
 * Hidden from public unless COMMENTS_PUBLIC_READ_ENABLED=1.
 * Admin preview mounts with data-admin-preview="1".
 * Reuses yummy_cr_vid identity cookie; does not mint a second cookie.
 * Never renders Qwen labels/reasoning to end users.
 * SEO rendering stays off (no SSR comment bodies from this widget).
 */
(function (global) {
  "use strict";

  var MAX_LEN = 3000;
  var PUBLIC_VISIBLE = {
    PUBLISHED_UNREVIEWED: 1,
    VISIBLE_QWEN_APPROVED: 1,
    VISIBLE_SPOILER_COLLAPSED: 1,
    PUBLISHED: 1,
  };
  var HIDDEN_STATUSES = {
    HIDDEN_QWEN_HIGH_CONFIDENCE: 1,
    HIDDEN_BY_ADMIN: 1,
    HELD_FOR_REVIEW: 1,
    QUARANTINED: 1,
    REJECTED: 1,
    PREFLIGHT_REJECTED: 1,
  };
  var DELETED_STATUSES = {
    DELETED_BY_AUTHOR: 1,
    DELETED_BY_ADMIN: 1,
    DELETED_BY_USER: 1,
    REMOVED_BY_MODERATOR: 1,
  };
  var DEGRADED = { PENDING_MODERATION_DEGRADED: 1, PENDING: 1 };

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
    this.replyTo = null;
    this.state = {
      phase: "loading",
      comments: [],
      error: null,
      rateLimited: false,
      submitting: false,
      charCount: 0,
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
    var self = this;
    var body = "";
    if (s.phase === "loading") {
      body =
        '<p class="cc-status" role="status" aria-live="polite">Загрузка комментариев…</p>';
    } else if (s.phase === "error") {
      body =
        '<p class="cc-status cc-status--error" role="alert">' +
        escapeHtml(s.error || "Ошибка загрузки") +
        "</p>";
    } else if (s.rateLimited) {
      body =
        '<p class="cc-status cc-status--rate" role="status">Слишком много попыток. Подождите.</p>';
    } else if (!s.comments.length) {
      body =
        '<p class="cc-status cc-status--empty" role="status">Пока нет комментариев</p>';
    } else {
      body =
        '<ul class="cc-list" role="list">' +
        s.comments.map(function (c) {
          return renderItem(c, self);
        }).join("") +
        "</ul>";
    }

    var replyHint = this.replyTo
      ? '<p class="cc-reply-hint">Ответ на комментарий · <button type="button" class="cc-link" data-cc-cancel-reply>Отмена</button></p>'
      : "";

    var form =
      '<form class="cc-form" novalidate>' +
      '<label class="cc-label" for="cc-body">Ваш комментарий</label>' +
      '<textarea id="cc-body" name="body" class="cc-textarea" maxlength="' +
      MAX_LEN +
      '" rows="4" required placeholder="Напишите мнение о произведении…"></textarea>' +
      '<div class="cc-form-meta"><span class="cc-counter" data-cc-counter>0 / ' +
      MAX_LEN +
      '</span>' +
      '<label class="cc-spoiler"><input type="checkbox" name="spoiler" /> Содержит спойлер</label></div>' +
      replyHint +
      '<div class="cc-actions">' +
      '<button type="submit" class="cc-submit" style="min-width:44px;min-height:44px"' +
      (s.submitting ? " disabled" : "") +
      ">" +
      (s.submitting ? "Отправка…" : "Отправить") +
      "</button></div>" +
      (s.error && s.phase !== "error"
        ? '<p class="cc-status cc-status--error" role="alert">' +
          escapeHtml(s.error) +
          "</p>"
        : "") +
      "</form>";

    this.root.innerHTML =
      '<section class="cc-block" aria-label="Комментарии">' +
      '<h2 class="cc-title">Комментарии</h2>' +
      (this.adminPreview
        ? '<p class="cc-banner" role="status">Режим предпросмотра (публикация выключена)</p>'
        : "") +
      body +
      form +
      "</section>";

    var formEl = this.root.querySelector(".cc-form");
    var ta = this.root.querySelector("#cc-body");
    var counter = this.root.querySelector("[data-cc-counter]");
    if (ta && counter) {
      ta.addEventListener("input", function () {
        counter.textContent = ta.value.length + " / " + MAX_LEN;
      });
    }
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
    this.root.querySelectorAll("[data-cc-reply]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        self.replyTo = btn.getAttribute("data-cc-reply");
        self.render();
      });
    });
    this.root.querySelectorAll("[data-cc-cancel-reply]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        self.replyTo = null;
        self.render();
      });
    });
    this.root.querySelectorAll("[data-cc-delete]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        self.onDelete(btn.getAttribute("data-cc-delete"));
      });
    });
    this.root.querySelectorAll("[data-cc-report]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        self.onReport(btn.getAttribute("data-cc-report"));
      });
    });
    this.root.querySelectorAll("[data-cc-edit]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        self.onEdit(btn.getAttribute("data-cc-edit"));
      });
    });
    this.root.querySelectorAll("[data-cc-more]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        self.loadMore();
      });
    });
  };

  function authorLabel(c) {
    if (c.author && c.author.display_name) return c.author.display_name;
    if (c.display_name) return c.display_name;
    return "Гость";
  }

  function renderItem(c, self) {
    var status = c.status || "PUBLISHED_UNREVIEWED";
    var cls =
      "cc-item cc-item--" + String(status).toLowerCase().replace(/_/g, "-");
    if (c.edited_at) cls += " cc-item--edited";
    var author = escapeHtml(authorLabel(c));
    var meta = author;
    if (c.edited_at) meta += " · изменено";

    var content;
    if (DELETED_STATUSES[status]) {
      content = '<p class="cc-deleted">Комментарий удалён</p>';
    } else if (DEGRADED[status] && status === "PENDING_MODERATION_DEGRADED") {
      content =
        '<p class="cc-pending" role="status">На проверке — комментарий появится после модерации</p>';
    } else if (HIDDEN_STATUSES[status] && !self.adminPreview) {
      content =
        '<p class="cc-hidden" role="status">Комментарий скрыт модерацией</p>';
    } else if (
      status === "VISIBLE_SPOILER_COLLAPSED" ||
      c.spoiler_collapsed ||
      c.spoiler
    ) {
      content =
        '<button type="button" class="cc-spoiler-btn" data-spoiler-toggle aria-expanded="false" style="min-width:44px;min-height:44px">Показать спойлер</button>' +
        '<div class="cc-spoiler-body" hidden><p class="cc-body">' +
        escapeHtml(c.body || "") +
        "</p></div>";
    } else if (PUBLIC_VISIBLE[status] || self.adminPreview) {
      content = '<p class="cc-body">' + escapeHtml(c.body || "") + "</p>";
    } else {
      content =
        '<p class="cc-hidden" role="status">Комментарий скрыт модерацией</p>';
    }

    var reply = c.parent_comment_id
      ? '<p class="cc-reply-to">Ответ</p>'
      : "";
    var actions =
      '<div class="cc-item-actions">' +
      (!c.parent_comment_id
        ? '<button type="button" class="cc-link" data-cc-reply="' +
          escapeHtml(c.comment_id || "") +
          '" style="min-width:44px;min-height:44px">Ответить</button>'
        : "") +
      (c.is_own
        ? '<button type="button" class="cc-link" data-cc-edit="' +
          escapeHtml(c.comment_id || "") +
          '" style="min-width:44px;min-height:44px">Изменить</button>' +
          '<button type="button" class="cc-link" data-cc-delete="' +
          escapeHtml(c.comment_id || "") +
          '" style="min-width:44px;min-height:44px">Удалить</button>'
        : '<button type="button" class="cc-link" data-cc-report="' +
          escapeHtml(c.comment_id || "") +
          '" style="min-width:44px;min-height:44px">Пожаловаться</button>') +
      "</div>";

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
      actions +
      "</li>"
    );
  }

  CommunityCommentsBlock.prototype.load = function () {
    var self = this;
    this.state.phase = "loading";
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
          self.state.phase = "rate-limited";
          self.render();
          return null;
        }
        if (!r.ok) throw new Error("load failed");
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        self.state.comments = data.comments || [];
        self.state.phase = self.state.comments.length ? "published" : "empty";
        self.state.error = null;
        self.render();
      })
      .catch(function (err) {
        self.state.phase = "error";
        self.state.error = (err && err.message) || "error";
        self.render();
      });
  };

  CommunityCommentsBlock.prototype.loadMore = function () {
    this.load();
  };

  CommunityCommentsBlock.prototype.onSubmit = function (form) {
    var self = this;
    var ta = form.querySelector("#cc-body");
    var spoiler = !!(form.querySelector('[name="spoiler"]') || {}).checked;
    var body = (ta && ta.value) || "";
    if (!body.trim()) {
      this.state.error = "Напишите текст комментария";
      this.render();
      return;
    }
    this.state.submitting = true;
    this.state.error = null;
    this.render();
    var payload = {
      site_space: this.space,
      title_id: this.titleId,
      body: body,
      spoiler: spoiler,
    };
    if (this.replyTo) payload.parent_comment_id = this.replyTo;
    fetch(this.apiBase, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        self.state.submitting = false;
        if (r.status === 429) {
          self.state.rateLimited = true;
          self.render();
          return null;
        }
        if (r.status === 403) {
          self.state.phase = "error";
          self.state.error = "Запись отключена (dark mode)";
          self.render();
          return null;
        }
        if (!r.ok) throw new Error("submit failed");
        return r.json();
      })
      .then(function (data) {
        if (!data) return;
        self.replyTo = null;
        self.load();
      })
      .catch(function (err) {
        self.state.submitting = false;
        self.state.phase = "error";
        self.state.error = (err && err.message) || "error";
        self.render();
      });
  };

  CommunityCommentsBlock.prototype.onDelete = function (commentId) {
    var self = this;
    fetch(this.apiBase + "/" + encodeURIComponent(commentId), {
      method: "DELETE",
      credentials: "same-origin",
    })
      .then(function (r) {
        if (!r.ok) throw new Error("delete failed");
        self.load();
      })
      .catch(function (err) {
        self.state.error = (err && err.message) || "error";
        self.render();
      });
  };

  CommunityCommentsBlock.prototype.onReport = function (commentId) {
    var self = this;
    fetch(this.apiBase + "/" + encodeURIComponent(commentId) + "/report", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason_code: "OTHER" }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error("report failed");
        self.state.error = null;
        alert("Жалоба отправлена");
      })
      .catch(function (err) {
        self.state.error = (err && err.message) || "error";
        self.render();
      });
  };

  CommunityCommentsBlock.prototype.onEdit = function (commentId) {
    var self = this;
    var next = window.prompt("Новый текст комментария");
    if (next == null) return;
    fetch(this.apiBase + "/" + encodeURIComponent(commentId), {
      method: "PATCH",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: next }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error("edit failed");
        self.load();
      })
      .catch(function (err) {
        self.state.error = (err && err.message) || "error";
        self.render();
      });
  };

  global.CommunityCommentsBlock = CommunityCommentsBlock;
})(typeof window !== "undefined" ? window : globalThis);
