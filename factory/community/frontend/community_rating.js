/**
 * Community native rating widget (Animedia / Yummy).
 * Shadow-ready: does not mount on production until owner activation.
 * No optimistic score keep on write failure.
 */
(function (global) {
  "use strict";

  function roundHalfUp(n, places) {
    var f = Math.pow(10, places);
    return (Math.sign(n) * Math.round(Math.abs(n) * f + Number.EPSILON)) / f;
  }

  function CommunityRatingBlock(root, opts) {
    this.root = root;
    this.opts = opts || {};
    this.space = opts.ratingSpaceId || "animedia";
    this.subjectId = opts.subjectId;
    this.apiBase = opts.apiBase || "/api/community/ratings";
    this.state = {
      score: null,
      count: 0,
      myVote: null,
      absent: true,
      previews: {},
      busy: false,
      error: null,
    };
  }

  CommunityRatingBlock.prototype.render = function () {
    var s = this.state;
    var label =
      this.space === "yummy" ? "Оценка Yummy" : "Оценка Animedia";
    var scoreHtml = s.absent
      ? '<span class="cr-score cr-score--absent" aria-live="polite">Пока нет оценок</span>'
      : '<span class="cr-score" aria-live="polite">' +
        escapeHtml(String(s.score)) +
        "</span>";
    var my =
      s.myVote == null
        ? ""
        : '<span class="cr-my">Ваша оценка: ' + s.myVote + "</span>";
    var tooltip =
      this.space === "yummy"
        ? '<button type="button" class="cr-info" aria-label="О расчёте" title="Расчётная оценка: голоса пользователей Yummy и версионируемая база Animedia/Shikimori">ⓘ</button>'
        : "";
    var buttons = "";
    for (var i = 1; i <= 10; i++) {
      buttons +=
        '<button type="button" class="cr-score-btn" data-score="' +
        i +
        '" aria-label="Оценить на ' +
        i +
        '" style="min-width:44px;min-height:44px">' +
        i +
        "</button>";
    }
    this.root.innerHTML =
      '<div class="cr-block" data-space="' +
      escapeHtml(this.space) +
      '">' +
      '<div class="cr-external" data-role="external-badges"></div>' +
      '<div class="cr-native">' +
      '<span class="cr-label">' +
      label +
      "</span>" +
      tooltip +
      scoreHtml +
      '<span class="cr-count">(' +
      s.count +
      ")</span>" +
      my +
      '<span class="cr-preview" aria-live="polite"></span>' +
      "</div>" +
      '<div class="cr-selector" role="group" aria-label="Выбор оценки">' +
      buttons +
      "</div>" +
      (s.myVote != null
        ? '<button type="button" class="cr-delete" style="min-width:44px;min-height:44px">Удалить оценку</button>'
        : "") +
      '<div class="cr-status" role="status"></div>' +
      "</div>";
    this._bind();
  };

  CommunityRatingBlock.prototype._bind = function () {
    var self = this;
    var btns = this.root.querySelectorAll(".cr-score-btn");
    btns.forEach(function (btn) {
      btn.addEventListener("mouseenter", function () {
        self._showPreview(Number(btn.getAttribute("data-score")));
      });
      btn.addEventListener("focus", function () {
        self._showPreview(Number(btn.getAttribute("data-score")));
      });
      btn.addEventListener("click", function () {
        self.submitVote(Number(btn.getAttribute("data-score")));
      });
    });
    var del = this.root.querySelector(".cr-delete");
    if (del) {
      del.addEventListener("click", function () {
        self.deleteVote();
      });
    }
  };

  CommunityRatingBlock.prototype._showPreview = function (score) {
    var p = this.state.previews[String(score)];
    var el = this.root.querySelector(".cr-preview");
    if (!el || !p) return;
    el.textContent =
      "После голосования: " +
      (p.after || "—") +
      (p.delta ? " · Изменение: " + p.delta : "");
  };

  CommunityRatingBlock.prototype.applyServer = function (payload) {
    if (!payload || payload.status >= 400) {
      this.state.error = (payload && payload.error) || "Ошибка";
      var st = this.root.querySelector(".cr-status");
      if (st) st.textContent = this.state.error + " — повторите";
      return;
    }
    this.state.error = null;
    this.state.myVote = payload.my_vote;
    this.state.count = payload.native_vote_count;
    this.state.absent = !!payload.native_absent || this.state.count === 0;
    this.state.score = payload.after || payload.native_user_average || payload.public_brand_score;
    this.render();
  };

  CommunityRatingBlock.prototype.submitVote = function (score) {
    var self = this;
    if (self.state.busy) return;
    self.state.busy = true;
    var key = "idem-" + Date.now() + "-" + Math.random().toString(16).slice(2);
    fetch(this.apiBase + "/vote", {
      method: "PUT",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": key,
        "X-CSRF-Token": this.opts.csrf || "",
      },
      body: JSON.stringify({
        rating_space_id: this.space,
        subject_id: this.subjectId,
        score: score,
      }),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (body) {
        self.state.busy = false;
        self.applyServer(body);
      })
      .catch(function () {
        self.state.busy = false;
        var st = self.root.querySelector(".cr-status");
        if (st) st.textContent = "Сеть недоступна — оценка не сохранена";
        /* do not keep optimistic score */
      });
  };

  CommunityRatingBlock.prototype.deleteVote = function () {
    var self = this;
    if (self.state.busy) return;
    self.state.busy = true;
    var key = "idem-del-" + Date.now();
    fetch(this.apiBase + "/vote", {
      method: "DELETE",
      credentials: "same-origin",
      headers: {
        "Idempotency-Key": key,
        "X-CSRF-Token": this.opts.csrf || "",
      },
      body: JSON.stringify({
        rating_space_id: this.space,
        subject_id: this.subjectId,
      }),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (body) {
        self.state.busy = false;
        self.applyServer(body);
      })
      .catch(function () {
        self.state.busy = false;
      });
  };

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  global.CommunityRatingBlock = CommunityRatingBlock;
})(typeof window !== "undefined" ? window : globalThis);
