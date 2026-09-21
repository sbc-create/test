/**
 * Community native rating widget — Yummy 1% public-write canary.
 *
 * Talks to the live gateway contract and nothing else:
 *   GET  /api/community/ratings/session                     identity + cohort + csrf
 *   GET  /api/community/ratings/titles/<subject>            native state
 *   POST /api/community/ratings/titles/<subject>/preview    {score}
 *   PUT  /api/community/ratings/titles/<subject>/vote       {score}
 *   POST /api/community/ratings/titles/<subject>/vote       {action:"retract"}
 *   POST /api/community/ratings/widget-event                {event:"rendered"}
 *
 * Deliberate properties:
 *  - No business logic is duplicated here. Every score, average, delta and
 *    absent-label string comes from the server; the widget only renders them.
 *  - The panel is position:fixed and is appended to <body> after the host page
 *    has hydrated, so it is outside the framework's DOM tree and outside
 *    document flow: it cannot shift layout or break the card, header or player.
 *  - Nothing renders unless the server says this visitor is in the cohort and
 *    writes are enabled. Kill switch or read-only removes the UI entirely.
 *  - A failed request never leaves an optimistic score on screen and never
 *    throws into the host page.
 */
(function (global) {
  "use strict";

  var API = "/api/community/ratings";
  var MOUNT_ID = "cr-widget-root";

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function json(res) {
    return res.json().catch(function () {
      return { status: res.status, error: "invalid response" };
    });
  }

  function CommunityRatingBlock(root, opts) {
    opts = opts || {};
    this.root = root;
    this.subjectId = opts.subjectId;
    this.apiBase = opts.apiBase || API;
    this.csrf = opts.csrf || "";
    this.space = opts.ratingSpaceId || "yummy";
    this.state = {
      phase: "loading", // loading | ready | error | readonly
      score: null,
      count: 0,
      absent: true,
      absentLabel: "Пока нет пользовательских оценок",
      myVote: null,
      preview: null,
      previewFor: null,
      busy: false,
      message: "",
      open: false
    };
  }

  /* ---------------------------------------------------------------- state */

  CommunityRatingBlock.prototype.applyPublic = function (body) {
    if (!body || body.status >= 400) {
      this.state.phase = "error";
      this.state.message = "Оценки временно недоступны";
      return;
    }
    this.state.phase = body.writes_ui_enabled === false ? "readonly" : "ready";
    this.state.count = Number(body.native_vote_count || 0);
    this.state.absent = !!body.native_absent || this.state.count === 0;
    // Absent is absent. A missing average is never rendered as 0.
    this.state.score = this.state.absent ? null : body.native_user_average;
    if (body.native_absent_label) this.state.absentLabel = body.native_absent_label;
    this.state.myVote = body.my_vote == null ? null : Number(body.my_vote);
  };

  CommunityRatingBlock.prototype.applyWrite = function (body) {
    if (!body || body.status >= 400) {
      this.state.message =
        (body && body.error) || "Не удалось сохранить оценку";
      // No optimistic keep: re-read authoritative state from the server.
      this.refresh();
      return;
    }
    this.state.message = "";
    this.state.myVote = body.my_vote == null ? null : Number(body.my_vote);
    this.state.count = Number(body.native_vote_count || 0);
    this.state.absent = !!body.native_absent || this.state.count === 0;
    this.state.score = this.state.absent ? null : body.after;
    this.state.preview = null;
    this.state.previewFor = null;
    this.render();
  };

  /* --------------------------------------------------------------- render */

  CommunityRatingBlock.prototype.scoreLine = function () {
    var s = this.state;
    if (s.absent) {
      return (
        '<span class="cr-score cr-score--absent">' +
        escapeHtml(s.absentLabel) +
        "</span>"
      );
    }
    return (
      '<span class="cr-score">' +
      escapeHtml(String(s.score)) +
      '</span><span class="cr-count"> · голосов: ' +
      escapeHtml(String(s.count)) +
      "</span>"
    );
  };

  CommunityRatingBlock.prototype.render = function () {
    var s = this.state;
    var html = "";

    var toggleLabel = s.open ? "Свернуть оценку" : "Оценить аниме";
    html +=
      '<button type="button" class="cr-toggle" aria-expanded="' +
      (s.open ? "true" : "false") +
      '" aria-controls="cr-panel" aria-label="' +
      escapeHtml(toggleLabel) +
      '">' +
      (s.open ? "×" : "★") +
      "</button>";

    html += '<div class="cr-panel" id="cr-panel" role="group" aria-label="Пользовательская оценка Yummy"' +
      (s.open ? "" : " hidden") + ">";

    html += '<div class="cr-head"><span class="cr-label">Оценка Yummy</span></div>';

    if (s.phase === "loading") {
      html += '<div class="cr-body" aria-live="polite">Загрузка…</div>';
    } else if (s.phase === "error") {
      html +=
        '<div class="cr-body cr-body--error" role="status">' +
        escapeHtml(s.message || "Оценки временно недоступны") +
        "</div>";
    } else {
      html += '<div class="cr-body"><div class="cr-current" aria-live="polite">' +
        this.scoreLine() + "</div>";

      if (s.phase === "readonly") {
        html +=
          '<p class="cr-readonly" role="status">Голосование сейчас недоступно</p>';
      } else {
        html += '<div class="cr-selector" role="radiogroup" aria-label="Выберите оценку от 1 до 10">';
        for (var i = 1; i <= 10; i++) {
          var mine = s.myVote === i;
          html +=
            '<button type="button" class="cr-score-btn' +
            (mine ? " is-mine" : "") +
            '" role="radio" aria-checked="' +
            (mine ? "true" : "false") +
            '" data-score="' +
            i +
            '" aria-label="Поставить оценку ' +
            i +
            ' из 10">' +
            i +
            "</button>";
        }
        html += "</div>";

        html +=
          '<p class="cr-preview" aria-live="polite">' +
          (s.preview ? escapeHtml(s.preview) : "") +
          "</p>";

        if (s.myVote != null) {
          html +=
            '<p class="cr-my">Ваша оценка: <strong>' +
            escapeHtml(String(s.myVote)) +
            "</strong></p>" +
            '<button type="button" class="cr-delete" aria-label="Удалить свою оценку">Удалить оценку</button>';
        }
      }

      if (s.message) {
        html +=
          '<p class="cr-status" role="status">' + escapeHtml(s.message) + "</p>";
      }
      html += "</div>";
    }

    html += "</div>";
    this.root.innerHTML = html;
    this._bind();
  };

  CommunityRatingBlock.prototype._bind = function () {
    var self = this;
    var toggle = this.root.querySelector(".cr-toggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        self.state.open = !self.state.open;
        self.render();
        if (self.state.open) {
          var first = self.root.querySelector(".cr-score-btn, .cr-toggle");
          if (first) first.focus();
        }
      });
    }
    var btns = this.root.querySelectorAll(".cr-score-btn");
    Array.prototype.forEach.call(btns, function (btn) {
      var score = Number(btn.getAttribute("data-score"));
      btn.addEventListener("mouseenter", function () {
        self.requestPreview(score);
      });
      btn.addEventListener("focus", function () {
        self.requestPreview(score);
      });
      btn.addEventListener("click", function () {
        self.submitVote(score);
      });
    });
    var del = this.root.querySelector(".cr-delete");
    if (del) {
      del.addEventListener("click", function () {
        self.retractVote();
      });
    }
  };

  /* ---------------------------------------------------------------- calls */

  CommunityRatingBlock.prototype._titleUrl = function (suffix) {
    return (
      this.apiBase +
      "/titles/" +
      encodeURIComponent(this.subjectId) +
      (suffix || "")
    );
  };

  CommunityRatingBlock.prototype._writeHeaders = function () {
    return {
      "Content-Type": "application/json",
      "X-CSRF-Token": this.csrf,
      "Idempotency-Key":
        "w-" + Date.now().toString(16) + "-" + Math.random().toString(16).slice(2)
    };
  };

  CommunityRatingBlock.prototype.refresh = function () {
    var self = this;
    return fetch(this._titleUrl(), { credentials: "same-origin" })
      .then(json)
      .then(function (body) {
        self.state.busy = false;
        self.applyPublic(body);
        self.render();
      })
      .catch(function () {
        self.state.busy = false;
        self.state.phase = "error";
        self.state.message = "Сеть недоступна";
        self.render();
      });
  };

  /** Preview is the server's own projection — the widget never computes it. */
  CommunityRatingBlock.prototype.requestPreview = function (score) {
    var self = this;
    if (self.state.previewFor === score || self.state.phase !== "ready") return;
    self.state.previewFor = score;
    fetch(this._titleUrl("/preview"), {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ score: score })
    })
      .then(json)
      .then(function (body) {
        if (!body || body.status >= 400) return;
        if (self.state.previewFor !== score) return;
        var after = body.after == null ? "—" : body.after;
        self.state.preview =
          "После вашей оценки " + score + ": " + after +
          (body.delta ? " (" + body.delta + ")" : "");
        var el = self.root.querySelector(".cr-preview");
        if (el) el.textContent = self.state.preview;
      })
      .catch(function () {
        /* preview is advisory only — silence is correct here */
      });
  };

  CommunityRatingBlock.prototype.submitVote = function (score) {
    var self = this;
    if (self.state.busy || self.state.phase !== "ready") return;
    self.state.busy = true;
    self.state.message = "Сохраняем…";
    self.render();
    fetch(this._titleUrl("/vote"), {
      method: "PUT",
      credentials: "same-origin",
      headers: this._writeHeaders(),
      body: JSON.stringify({ score: score })
    })
      .then(json)
      .then(function (body) {
        self.state.busy = false;
        self.applyWrite(body);
      })
      .catch(function () {
        self.state.busy = false;
        self.state.message = "Сеть недоступна — оценка не сохранена";
        self.render();
      });
  };

  CommunityRatingBlock.prototype.retractVote = function () {
    var self = this;
    if (self.state.busy || self.state.phase !== "ready") return;
    self.state.busy = true;
    self.state.message = "Удаляем…";
    self.render();
    fetch(this._titleUrl("/vote"), {
      method: "POST",
      credentials: "same-origin",
      headers: this._writeHeaders(),
      body: JSON.stringify({ action: "retract" })
    })
      .then(json)
      .then(function (body) {
        self.state.busy = false;
        self.applyWrite(body);
      })
      .catch(function () {
        self.state.busy = false;
        self.state.message = "Сеть недоступна";
        self.render();
      });
  };

  /* ----------------------------------------------------------------- boot */

  /**
   * Decide whether this visitor may see the widget at all.
   * The answer is the server's; the client only obeys it.
   */
  function eligible(session) {
    if (!session || session.status >= 400) return false;
    var f = session.flags || {};
    if (!Number(f.PUBLIC_WRITE_ENABLED)) return false;
    if (Number(f.KILL_SWITCH)) return false;
    var c = session.cohort || {};
    return c.eligible === true;
  }

  /**
   * The injected markup is a script and nothing else, so the widget brings its
   * own stylesheet — added to <head> only at mount time, once the host page has
   * hydrated and head mutation is no longer a hydration hazard.
   */
  function ensureStyles(base) {
    if (document.getElementById("cr-widget-style")) return;
    var link = document.createElement("link");
    link.id = "cr-widget-style";
    link.rel = "stylesheet";
    link.href = base + "community_rating.css";
    document.head.appendChild(link);
  }

  function mount(subjectId) {
    return fetch(API + "/session", { credentials: "same-origin" })
      .then(json)
      .then(function (session) {
        if (!eligible(session)) return null;

        ensureStyles("/assets/community/");
        var host = document.getElementById(MOUNT_ID);
        if (!host) {
          host = document.createElement("div");
          host.id = MOUNT_ID;
          // Appended to <body> after hydration and positioned out of flow:
          // no node inside the framework's tree, no layout shift.
          document.body.appendChild(host);
        }
        var block = new CommunityRatingBlock(host, {
          subjectId: subjectId,
          csrf: session.csrf_token || "",
          ratingSpaceId: "yummy"
        });
        block.render();
        block.refresh();

        // Tell the server the widget is actually on screen for this visitor.
        // Exposure counted by the injector alone would only mean "offered".
        fetch(API + "/widget-event", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ event: "rendered" })
        }).catch(function () {});

        return block;
      })
      .catch(function () {
        return null; /* never break the host page */
      });
  }

  function boot() {
    var tag = document.getElementById("cr-widget-loader");
    var subject = tag && tag.getAttribute("data-subject");
    if (!subject) return;
    var start = function () {
      try {
        mount(subject);
      } catch (e) {
        /* the host page must survive any widget failure */
      }
    };
    // Wait for load so hydration has finished before the DOM gains a node.
    if (document.readyState === "complete") {
      setTimeout(start, 0);
    } else {
      global.addEventListener("load", function () {
        setTimeout(start, 0);
      });
    }
  }

  global.CommunityRatingBlock = CommunityRatingBlock;
  global.CommunityRatingMount = mount;

  if (typeof document !== "undefined") boot();
})(typeof window !== "undefined" ? window : globalThis);
