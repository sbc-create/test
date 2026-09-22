/* Блок оценок animedia.icu — только отправка собственной оценки.
 *
 * Всё, что можно показать разметкой, уже отдал сервер: сводная оценка,
 * источники, средняя зрителей. Скрипт нужен ровно для того, чего
 * разметкой не сделать, и его отсутствие или падение не должно ничего
 * убирать со страницы.
 *
 * Сеть недоступна — контрол выключается с объяснением, а показанные
 * оценки остаются. Молча исчезнувший блок хуже честной строки «сейчас
 * не получилось».
 */
(function () {
  "use strict";

  function init(root) {
    var api = root.getAttribute("data-api");
    var space = root.getAttribute("data-space");
    var subject = root.getAttribute("data-subject");
    var vote = root.querySelector('[data-role="vote"]');
    if (!vote) return; // запись выключена — показываем только чтение

    var buttons = Array.prototype.slice.call(root.querySelectorAll(".ur-star"));
    var myEl = root.querySelector('[data-role="my-score"]');
    var statusEl = root.querySelector('[data-role="status"]');
    var retractEl = root.querySelector('[data-role="retract"]');
    var avgEl = root.querySelector('[data-role="community-average"]');
    var votesEl = root.querySelector('[data-role="community-votes"]');
    var busy = false;
    var current = null;

    function say(text) { if (statusEl) statusEl.textContent = text || ""; }

    function paint(score) {
      current = score;
      buttons.forEach(function (b) {
        var value = Number(b.getAttribute("data-score"));
        var chosen = score !== null && value === score;
        b.setAttribute("aria-checked", chosen ? "true" : "false");
        b.classList.toggle("is-chosen", chosen);
        // Ровно один элемент группы участвует в переходе по Tab —
        // иначе десять кнопок подряд превращают клавиатурный обход
        // карточки в десять лишних нажатий.
        b.tabIndex = chosen || (score === null && value === 1) ? 0 : -1;
      });
      if (myEl) myEl.textContent = score === null ? "Вы ещё не оценили" : "Ваша оценка: " + score + " из 10";
      if (retractEl) retractEl.hidden = score === null;
    }

    function applyAggregate(aggregate) {
      if (!aggregate) return;
      if (avgEl) {
        avgEl.textContent = aggregate.vote_count > 0 ? aggregate.average : "Пока нет оценок";
      }
      if (votesEl) {
        votesEl.textContent = aggregate.vote_count > 0 ? aggregate.vote_count + " голосов" : "";
      }
    }

    function idempotencyKey(action, score) {
      // Ключ детерминирован: повторная отправка того же намерения не
      // создаёт второй голос, даже если ответ на первую потерялся.
      return [space, subject, action, score === null ? "none" : score].join(":");
    }

    function send(method, body, key) {
      if (busy) return;
      busy = true;
      say("Сохраняем…");
      var token = document.querySelector('meta[name="csrf-token"]');
      return fetch(api + "/vote", {
        method: method,
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": key,
          "X-CSRF-Token": token ? token.content : ""
        },
        body: JSON.stringify(body)
      }).then(function (response) {
        if (response.status === 401 || response.status === 403) {
          say("Оценки сейчас доступны не всем — ваша оценка не сохранена.");
          return null;
        }
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      }).then(function (data) {
        if (!data) return;
        paint(data.your_score === undefined ? null : data.your_score);
        applyAggregate(data.aggregate);
        say(data.your_score === null ? "Оценка убрана." : "Оценка сохранена.");
      }).catch(function () {
        say("Сейчас не получилось сохранить оценку. Показанные оценки не изменились.");
      }).then(function () { busy = false; });
    }

    buttons.forEach(function (button) {
      button.addEventListener("click", function () {
        var score = Number(button.getAttribute("data-score"));
        send("PUT", { space: space, subject_id: subject, score: score },
             idempotencyKey("put", score));
      });
      button.addEventListener("keydown", function (event) {
        var index = buttons.indexOf(button);
        var next = null;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") next = index + 1;
        if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = index - 1;
        if (next === null) return;
        event.preventDefault();
        var target = buttons[(next + buttons.length) % buttons.length];
        target.tabIndex = 0;
        target.focus();
      });
    });

    if (retractEl) {
      retractEl.addEventListener("click", function () {
        send("DELETE", { space: space, subject_id: subject }, idempotencyKey("delete", current));
      });
    }

    // Текущая оценка запрашивается после отрисовки: страница не ждёт её,
    // и её отсутствие ничего не ломает.
    fetch(api + "/me?space=" + encodeURIComponent(space) + "&subject_id=" + encodeURIComponent(subject),
          { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) { paint(null); return; }
        paint(data.your_score === undefined ? null : data.your_score);
        applyAggregate(data.aggregate);
      })
      .catch(function () { paint(null); });
  }

  function boot() {
    Array.prototype.slice.call(document.querySelectorAll("[data-unified-ratings]")).forEach(init);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
