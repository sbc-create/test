/* games-story (progress-tracker): единый трекер игры (клубники и стороны по главам), счётчики, плеер по нажатию, печать.
   Без JS поля трекера отключены, а числа источника видны. */
(function () {
  "use strict";
  var ns = document.body.getAttribute("data-ns") || "gst";
  function read(k, d) { try { var v = localStorage.getItem(ns + ":" + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } }
  function write(k, v) { try { localStorage.setItem(ns + ":" + k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function key(game) { return "tracker:" + game; }
  function stats(game) {
    var st = read(key(game), {}), red = 0, sides = 0;
    Object.keys(st).forEach(function (s) { red += st[s].red || 0; sides += (st[s].sides || []).length; });
    return { red: red, sides: sides };
  }
  function paintStats(scope, game) {
    var s = stats(game);
    scope.querySelectorAll("[data-stat=red]").forEach(function (e) { e.textContent = s.red; });
    scope.querySelectorAll("[data-stat=sides]").forEach(function (e) { e.textContent = s.sides; });
  }
  document.querySelectorAll(".dash[data-game]").forEach(function (d) { paintStats(d, d.getAttribute("data-game")); });
  document.querySelectorAll("table.trk[data-game]").forEach(function (t) {
    var game = t.getAttribute("data-game");
    t.querySelectorAll("tr[data-slug]").forEach(function (row) {
      var slug = row.getAttribute("data-slug"), max = +row.getAttribute("data-red");
      var inp = row.querySelector("[data-red-input]"), boxes = row.querySelectorAll("[data-side]");
      var st = read(key(game), {}), cur = st[slug] || { red: 0, sides: [] };
      if (inp) { inp.disabled = false; inp.value = cur.red || 0; }
      boxes.forEach(function (b) { b.disabled = false; b.checked = (cur.sides || []).indexOf(b.getAttribute("data-side")) !== -1; });
      function save() {
        var all = read(key(game), {}), v = inp ? Math.max(0, Math.min(max, parseInt(inp.value, 10) || 0)) : 0;
        if (inp) inp.value = v;
        var sides = []; boxes.forEach(function (b) { if (b.checked) sides.push(b.getAttribute("data-side")); });
        all[slug] = { red: v, sides: sides };
        write(key(game), all);
        paintStats(document, game);
        var r = document.querySelector("[data-tracker-reset]"); if (r) r.hidden = false;
      }
      if (inp) inp.addEventListener("change", save);
      boxes.forEach(function (b) { b.addEventListener("change", save); });
    });
    paintStats(document, game);
  });
  var reset = document.querySelector("[data-tracker-reset]");
  if (reset) {
    var game = document.querySelector("table.trk").getAttribute("data-game");
    reset.hidden = Object.keys(read(key(game), {})).length === 0;
    reset.addEventListener("click", function () { write(key(game), {}); location.reload(); });
  }
  document.querySelectorAll(".vid[data-vid]").forEach(function (f) {
    var b = f.querySelector("[data-play]"); b.hidden = false;
    b.addEventListener("click", function () {
      var i = document.createElement("iframe");
      i.src = "https://www.youtube-nocookie.com/embed/" + f.getAttribute("data-vid");
      i.title = f.querySelector("b").textContent; i.allow = "encrypted-media; picture-in-picture"; i.allowFullscreen = true;
      i.className = "vid__frame"; b.replaceWith(i);
    });
  });
  document.querySelectorAll("[data-print]").forEach(function (b) { b.hidden = false; b.addEventListener("click", function () { window.print(); }); });
})();
