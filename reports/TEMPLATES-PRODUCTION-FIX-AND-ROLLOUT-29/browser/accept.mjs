// Публичная браузерная приёмка, версия 2.
//
// В версии 1 «битыми» считались изображения, которые просто ещё не догрузились:
// у них loading="lazy", и на момент замера naturalWidth был 0. Признак подмены
// очевиден задним числом — число «битых» падало с ростом ширины окна (54 при
// 390 px, 34 при 1440), а заглушек не было ни одной; curl по тем же адресам
// отдавал настоящий webp с кодом 200. Здесь замер ждёт, пока изображения
// действительно завершатся.
import { chromium, firefox } from "playwright";

const WIDTHS = [390, 768, 1440];
const SITES = [
  ["yummyani.biz", ["/", "/catalog", "/catalog/anime-updates", "/catalog/announcement"]],
  ["yummyani.org", ["/", "/catalog", "/catalog/anime-updates"]],
  ["yummyani.site", ["/", "/catalog", "/catalog/anime-updates"]],
  ["lordfilm47.space", ["/", "/catalog/", "/genres/", "/countries/"]],
  ["lordserial33.biz", ["/", "/catalog/", "/genres/"]],
  ["1lordserials1.online", ["/", "/catalog/", "/genres/"]],
];

const results = [];

async function settleImages(page) {
  // Снять ленивую загрузку и дождаться КАЖДОГО изображения (или его отказа).
  return page.evaluate(async () => {
    const imgs = [...document.images];
    for (const i of imgs) {
      i.loading = "eager";
      if (!i.src && i.dataset.src) i.src = i.dataset.src;
    }
    await Promise.all(
      imgs.map(
        (i) =>
          new Promise((done) => {
            if (i.complete) return done();
            const fin = () => done();
            i.addEventListener("load", fin, { once: true });
            i.addEventListener("error", fin, { once: true });
            setTimeout(fin, 20000);
          }),
      ),
    );
  });
}

async function checkPage(page, url) {
  const consoleErrors = [];
  const onErr = (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 140)); };
  page.on("console", onErr);
  let status = 0;
  try {
    const resp = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });
    status = resp ? resp.status() : 0;
    await page.evaluate(async () => {
      await new Promise((done) => {
        let y = 0;
        const step = () => {
          y += window.innerHeight;
          window.scrollTo(0, y);
          if (y < document.body.scrollHeight) setTimeout(step, 70);
          else { window.scrollTo(0, 0); setTimeout(done, 300); }
        };
        step();
      });
    });
    await settleImages(page);
    await page.waitForTimeout(400);
  } catch (e) {
    page.off("console", onErr);
    return { url, status, error: String(e).slice(0, 120) };
  }
  const info = await page.evaluate(() => {
    const vis = [...document.images].filter((i) => {
      const r = i.getBoundingClientRect();
      const s = getComputedStyle(i);
      return r.width > 8 && r.height > 8 && s.visibility !== "hidden" && s.display !== "none";
    });
    return {
      imgVisible: vis.length,
      broken: vis.filter((i) => i.naturalWidth === 0).map((i) => (i.currentSrc || i.src || "").slice(-64)),
      placeholders: vis.filter((i) => /poster/.test(i.currentSrc || "") && /\.svg/.test(i.currentSrc || "")).length,
      noAlt: vis.filter((i) => i.getAttribute("alt") === null).length,
      overflowX: document.documentElement.scrollWidth > window.innerWidth + 2,
      zeroMinutes: (document.body.innerText.match(/\b0\s*мин/g) || []).length,
      focusable: document.querySelectorAll("a[href], button, input, [tabindex]:not([tabindex=\"-1\"])").length,
    };
  });
  page.off("console", onErr);
  return { url, status, ...info, consoleErrors: consoleErrors.slice(0, 3) };
}

for (const [engineName, engine] of [["chromium", chromium], ["firefox", firefox]]) {
  const browser = await engine.launch();
  for (const width of WIDTHS) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 }, ignoreHTTPSErrors: true });
    const page = await ctx.newPage();
    for (const [host, paths] of SITES) {
      for (const p of paths) {
        const r = await checkPage(page, `https://${host}${p}`);
        results.push({ engine: engineName, width, host, path: p, ...r });
        const bad = (r.broken?.length || 0) + (r.placeholders || 0);
        const fail = r.status !== 200 || bad > 0 || r.overflowX || r.error;
        console.log(
          `${engineName.padEnd(8)} ${String(width).padEnd(5)} ${host.padEnd(21)} ${p.padEnd(24)} ` +
          `http=${r.status} vis=${r.imgVisible ?? "-"} broken=${r.broken?.length ?? "-"} ` +
          `ph=${r.placeholders ?? "-"} ovf=${r.overflowX ?? "-"} 0min=${r.zeroMinutes ?? "-"}` +
          (fail ? "  <-- FAIL" : ""),
        );
        if (r.broken?.length) console.log("      broken:", r.broken.slice(0, 3).join(" | "));
        if (r.error) console.log("      error:", r.error);
      }
    }
    await ctx.close();
  }
  await browser.close();
}

const fails = results.filter((r) => r.status !== 200 || r.error || (r.broken?.length || 0) > 0 || (r.placeholders || 0) > 0 || r.overflowX);
console.log("\n==== SUMMARY v2 ====");
console.log("checks:", results.length, "failures:", fails.length);
console.log("visible images checked:", results.reduce((a, r) => a + (r.imgVisible || 0), 0));
console.log("broken:", results.reduce((a, r) => a + (r.broken?.length || 0), 0));
console.log("poster placeholders:", results.reduce((a, r) => a + (r.placeholders || 0), 0));
console.log("images without alt:", results.reduce((a, r) => a + (r.noAlt || 0), 0));
console.log("\"0 минут\":", results.reduce((a, r) => a + (r.zeroMinutes || 0), 0));
console.log("horizontal overflow pages:", results.filter((r) => r.overflowX).length);
for (const f of fails) console.log("FAIL:", f.engine, f.width, f.host + f.path, "http=" + f.status, "broken=" + (f.broken?.length || 0), "ph=" + (f.placeholders || 0), "ovf=" + f.overflowX, f.error || "");
