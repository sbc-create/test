/* food-daily, вариант C party-list: улучшения поверх серверного HTML; ключи fdc.*. Без этого файла рецепт,
   каталог, поиск и фильтры работают полностью. */
(function () {
  "use strict";
  document.documentElement.classList.add("js");

  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* приватный режим */ } }
  };
  var FAV = "fdc.fav.v1", LIST = "fdc.list.v1", PARTY = "fdc.party.v1", FRIDGE = "fdc.fridge.v1";

  function fmt(q) {
    if (q === null || isNaN(q)) return "";
    var whole = Math.floor(q), rest = Math.round((q - whole) * 100) / 100;
    var fr = { 0.25: "¼", 0.5: "½", 0.75: "¾", 0.33: "⅓", 0.67: "⅔" };
    if (fr[rest]) return (whole ? String(whole) : "") + fr[rest];
    if (Math.abs(q - Math.round(q)) < 0.05) return String(Math.round(q));
    return (q >= 10 ? Math.round(q) : Math.round(q * 10) / 10).toString().replace(".", ",");
  }
  function plural(n, a, b, c) { n = Math.abs(n) % 100; var m = n % 10; if (n > 10 && n < 20) return c; if (m > 1 && m < 5) return b; if (m === 1) return a; return c; }

  /* ---- счётчики в шапке ---- */
  function counts() {
    var f = store.get(FAV, []), l = store.get(LIST, []).filter(function (x) { return !x.done; });
    [["[data-fav-count]", f.length], ["[data-list-count]", l.length]].forEach(function (p) {
      var el = document.querySelector(p[0]); if (!el) return;
      el.textContent = p[1]; el.hidden = !p[1];
    });
  }

  /* ---- избранное ---- */
  function syncFav() {
    var f = store.get(FAV, []);
    document.querySelectorAll("[data-fav]").forEach(function (b) {
      var on = f.indexOf(b.getAttribute("data-fav")) >= 0;
      b.hidden = false; b.setAttribute("aria-pressed", on ? "true" : "false");
      var lab = b.querySelector("[data-fav-label]"); if (lab) lab.textContent = on ? "В избранном" : "В избранное";
    });
    counts();
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-fav]"); if (!b) return;
    e.preventDefault();
    var slug = b.getAttribute("data-fav"), f = store.get(FAV, []), i = f.indexOf(slug);
    if (i >= 0) f.splice(i, 1); else f.unshift(slug);
    store.set(FAV, f); syncFav();
    if (document.querySelector("[data-fav-page]")) renderFavPage();
  });

  function catalog() { var el = document.getElementById("catalog"); try { return el ? JSON.parse(el.textContent) : []; } catch (e) { return []; } }
  function renderFavPage() {
    var grid = document.querySelector("[data-fav-grid]"), empty = document.querySelector("[data-fav-empty]");
    var f = store.get(FAV, []), by = {}; catalog().forEach(function (r) { by[r.slug] = r; });
    grid.textContent = "";
    f.filter(function (s) { return by[s]; }).forEach(function (s) {
      var r = by[s], art = document.createElement("article"); art.className = "card";
      var a = document.createElement("a"); a.className = "card__link"; a.href = r.url;
      var h = document.createElement("h2"); h.className = "card__title"; h.textContent = r.title; a.appendChild(h);
      var meta = document.createElement("p"); meta.className = "card__meta"; meta.textContent = r.category + (r.time ? " · " + r.time : "");
      var b = document.createElement("button"); b.className = "fav"; b.type = "button"; b.setAttribute("data-fav", s); b.setAttribute("aria-pressed", "true");
      b.innerHTML = '<span class="sr">Убрать из избранного</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"/></svg>';
      art.appendChild(a); art.appendChild(meta); art.appendChild(b); grid.appendChild(art);
    });
    empty.hidden = grid.children.length > 0;
  }

  /* ---- порции ---- */
  var recipe = document.querySelector("[data-recipe]");
  var factor = 1;
  if (recipe) {
    var base = parseInt(recipe.getAttribute("data-servings"), 10) || 0;
    var ctrl = recipe.querySelector("[data-servings-control]");
    // выход не указан — пересчёт кратный от рецепта: ×½ … ×4
    var MULT = [0.5, 1, 1.5, 2, 3, 4], mi = 1;
    var cur = base;
    function rescale() {
      factor = base ? cur / base : MULT[mi];
      recipe.querySelector("[data-servings-out]").textContent = base ? cur : "×" + fmt(MULT[mi]);
      recipe.querySelector("[data-servings-word]").textContent = base ? plural(cur, "порция", "порции", "порций") : "от рецепта";
      recipe.querySelectorAll(".ing").forEach(function (li) {
        if (li.getAttribute("data-scalable") !== "1") return;
        var q = parseFloat(li.getAttribute("data-qty")), qm = parseFloat(li.getAttribute("data-qmax"));
        var txt = fmt(q * factor) + (isNaN(qm) ? "" : "–" + fmt(qm * factor));
        li.querySelector(".ing__amount").textContent = (txt + " " + li.getAttribute("data-unit")).trim();
      });
    }
    if (ctrl) {
      ctrl.hidden = false;
      ctrl.addEventListener("click", function (e) {
        var b = e.target.closest("[data-step]"); if (!b) return;
        var d = parseInt(b.getAttribute("data-step"), 10);
        if (base) cur = Math.min(40, Math.max(1, cur + d));
        else mi = Math.min(MULT.length - 1, Math.max(0, mi + d));
        rescale();
      });
      rescale();
    }
    var add = recipe.querySelector("[data-add-list]");
    if (add) {
      add.hidden = false;
      add.addEventListener("click", function () {
        var list = store.get(LIST, []), title = recipe.querySelector("h1").textContent.trim(), n = 0;
        recipe.querySelectorAll(".ing").forEach(function (li) {
          var name = li.getAttribute("data-name"), amount = li.querySelector(".ing__amount").textContent.trim();
          var exists = list.some(function (x) { return x.name === name && x.recipe === title && !x.done; });
          if (!exists) { list.push({ name: name, amount: amount, recipe: title, done: false }); n++; }
        });
        store.set(LIST, list); counts();
        add.textContent = n ? "Добавлено: " + n + " " + plural(n, "продукт", "продукта", "продуктов") : "Уже в списке";
      });
    }
    /* режим готовки */
    var cook = recipe.querySelector("[data-cook]"), open = recipe.querySelector("[data-cook-open]");
    var steps = Array.prototype.map.call(recipe.querySelectorAll(".step"), function (li) {
      var cue = li.querySelector(".cue");
      return { text: li.querySelector("p").textContent, cue: cue ? cue.textContent : "" };
    });
    var at = 0, opener = null;
    function show() {
      cook.querySelector("[data-cook-count]").textContent = "Шаг " + (at + 1) + " из " + steps.length;
      cook.querySelector("[data-cook-text]").textContent = steps[at].text;
      cook.querySelector("[data-cook-cue]").textContent = steps[at].cue;
      cook.querySelector("[data-cook-prev]").disabled = at === 0;
      cook.querySelector("[data-cook-next]").textContent = at === steps.length - 1 ? "Готово" : "Дальше →";
    }
    function close() { cook.hidden = true; document.body.style.overflow = ""; if (opener) opener.focus(); }
    if (cook && open && steps.length) {
      open.hidden = false;
      open.addEventListener("click", function () { opener = open; at = 0; cook.hidden = false; document.body.style.overflow = "hidden"; show(); cook.querySelector("[data-cook-next]").focus(); });
      cook.querySelector("[data-cook-close]").addEventListener("click", close);
      cook.querySelector("[data-cook-prev]").addEventListener("click", function () { if (at > 0) { at--; show(); } });
      cook.querySelector("[data-cook-next]").addEventListener("click", function () { if (at < steps.length - 1) { at++; show(); } else close(); });
      document.addEventListener("keydown", function (e) {
        if (cook.hidden) return;
        if (e.key === "Escape") close();
        else if (e.key === "ArrowRight") { if (at < steps.length - 1) { at++; show(); } }
        else if (e.key === "ArrowLeft") { if (at > 0) { at--; show(); } }
        else if (e.key === "Tab") { /* фокус не уходит из диалога */
          var f = cook.querySelectorAll("button:not([disabled])"), first = f[0], last = f[f.length - 1];
          if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
          else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        }
      });
    }
  }

  /* ---- список покупок ---- */
  function renderList() {
    var ul = document.querySelector("[data-list]"); if (!ul) return;
    var list = store.get(LIST, []);
    ul.textContent = "";
    list.forEach(function (x, i) {
      var li = document.createElement("li"), lab = document.createElement("label"), cb = document.createElement("input"), sp = document.createElement("span");
      cb.type = "checkbox"; cb.checked = !!x.done;
      cb.addEventListener("change", function () { var l = store.get(LIST, []); if (l[i]) { l[i].done = cb.checked; store.set(LIST, l); counts(); } });
      sp.textContent = x.name + (x.amount ? " — " + x.amount : "");
      var small = document.createElement("small"); small.textContent = x.recipe;
      lab.appendChild(cb); lab.appendChild(sp); li.appendChild(lab); li.appendChild(small); ul.appendChild(li);
    });
    document.querySelector("[data-list-empty]").hidden = list.length > 0;
    document.querySelector("[data-list-actions]").hidden = list.length === 0;
  }
  if (document.querySelector("[data-list-page]")) {
    renderList();
    document.querySelector("[data-list-clear]").addEventListener("click", function () { store.set(LIST, []); renderList(); counts(); });
    document.querySelector("[data-list-clear-done]").addEventListener("click", function () { store.set(LIST, store.get(LIST, []).filter(function (x) { return !x.done; })); renderList(); counts(); });
  }
  if (document.querySelector("[data-fav-page]")) renderFavPage();

  /* ---- фильтры: применяются при выборе, кнопка остаётся для работы без JS ---- */
  var ff = document.querySelector("[data-autosubmit]");
  if (ff) ff.addEventListener("change", function () { ff.submit(); });

  var pr = document.querySelector("[data-print]");
  if (pr) { pr.hidden = false; pr.addEventListener("click", function () { window.print(); }); }

  /* ---- на компанию: память выбора, счётчик, отметки купленного ---- */
  var qs = new URLSearchParams(location.search);
  if (location.pathname === "/na-kompaniyu/" && qs.getAll("r").length) store.set(PARTY, location.search);
  var lastParty = store.get(PARTY, "");
  if (lastParty) document.querySelectorAll("[data-p-link]").forEach(function (a) { a.href = "/na-kompaniyu/" + lastParty; });
  document.querySelectorAll("[data-p-form]").forEach(function (fm) {
    var boxes = fm.querySelectorAll("input[name=r]"), out = fm.querySelector("[data-p-count]");
    if (!qs.getAll("r").length && lastParty) { var lp = new URLSearchParams(lastParty); boxes.forEach(function (b) { b.checked = lp.getAll("r").indexOf(b.value) !== -1; }); if (lp.get("gosti")) fm.querySelector("#gosti").value = lp.get("gosti"); }
    var upd = function () { var n = 0; boxes.forEach(function (b) { if (b.checked) n++; }); out.textContent = n ? "Отмечено блюд: " + n : "Отметьте хотя бы одно блюдо"; return n; };
    fm.addEventListener("change", upd); upd();
    fm.addEventListener("submit", function (e) { if (!upd()) { e.preventDefault(); boxes[0].focus(); } });
  });
  var pl = document.querySelector("[data-plist]");
  if (pl) {
    var bkey = "fdc.bought." + location.search, got = store.get(bkey, []);
    pl.querySelectorAll("input").forEach(function (cb) {
      cb.checked = got.indexOf(cb.value) !== -1;
      cb.addEventListener("change", function () { var v = []; pl.querySelectorAll("input:checked").forEach(function (x) { v.push(x.value); }); store.set(bkey, v); });
    });
  }

  /* ---- подбор «что есть дома» (перенесено из B): помним выбор, считаем отмеченные, пустой выбор не отправляем ---- */
  document.querySelectorAll("[data-fridge-form]").forEach(function (f) {
    var boxes = f.querySelectorAll("input[name=est]"), hint = f.querySelector("[data-fridge-hint]");
    var fromUrl = new URLSearchParams(location.search).getAll("est");
    if (fromUrl.length) store.set(FRIDGE, fromUrl);
    else if (!document.querySelector(".match")) {
      var saved = store.get(FRIDGE, []);
      boxes.forEach(function (b) { b.checked = saved.indexOf(b.value) >= 0; });
    }
    var count = function () { var n = 0; boxes.forEach(function (b) { if (b.checked) n++; }); return n; };
    var upd = function () { var n = count(); if (hint) hint.textContent = n ? "Отмечено: " + n : "Отметьте хотя бы один продукт"; };
    f.addEventListener("change", upd); upd();
    f.addEventListener("submit", function (e) {
      if (!count()) { e.preventDefault(); if (hint) hint.textContent = "Отметьте хотя бы один продукт"; boxes[0].focus(); }
    });
    var find = f.querySelector("[data-fridge-find]"), none = f.querySelector("[data-fridge-none]");
    if (find) {
      find.hidden = false;
      find.querySelector("input").addEventListener("input", function () {
        var q = this.value.trim().toLowerCase().replace(/ё/g, "е"), shown = 0;
        f.querySelectorAll(".pick__group").forEach(function (g) {
          var n = 0;
          g.querySelectorAll(".pick__list li").forEach(function (li) {
            var words = li.textContent.toLowerCase().replace(/ё/g, "е").split(/[\s,]+/);  // по началу слова
            var hit = !q || words.some(function (w) { return w.indexOf(q) === 0; });
            li.hidden = !hit; if (hit) n++;
          });
          g.hidden = !n; shown += n;
        });
        if (none) none.hidden = shown > 0;
      });
    }
    document.querySelectorAll("[data-fridge-clear]").forEach(function (clr) {
      clr.addEventListener("click", function () { store.set(FRIDGE, []); });
    });
    document.querySelectorAll(".pchip").forEach(function (a) {  // убрать один продукт — запомнить остальные
      a.addEventListener("click", function () { store.set(FRIDGE, new URLSearchParams(a.search).getAll("est")); });
    });
  });

  syncFav();
})();
