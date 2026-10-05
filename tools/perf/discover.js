// Подбор сценариев по каждому домену: каталог/поиск, карточка фильма,
// страница сериала со списком серий. Только GET публичных страниц.
// node tools/perf/discover.js <out.json> <domain>...
const fs = require('fs');

const ЭПИЗОД = /\/(season[-/]\d+\/)?episode[-/](\d+)\/?$/;

async function get(url) {
  const r = await fetch(url, { redirect: 'follow', headers: { 'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 site-factory-perf-audit' } });
  return { status: r.status, url: r.url, text: r.status === 200 ? await r.text() : '' };
}

function ссылки(html) {
  return [...new Set([...html.matchAll(/href="(\/[^"#?]*)"/g)].map((m) => m[1]))];
}

async function разведать(домен) {
  const корень = `https://${домен}`;
  const итог = { domain: домен, home: `${корень}/`, catalog: null, film: null, series: null, notes: [] };
  const h = await get(итог.home);
  if (h.status !== 200) { итог.notes.push(`home ${h.status}`); return итог; }
  const все = ссылки(h.text);
  const каталог = все.find((u) => /^\/(catalog|anime|search|series|movies|filmy|katalog)\/?$/.test(u))
    || все.find((u) => /catalog|search|katalog/.test(u));
  итог.catalog = каталог ? корень + каталог : null;
  const карточки = все.filter((u) => /^\/(title|anime|film|serial|movie)\//.test(u) && !ЭПИЗОД.test(u)).slice(0, 40);
  for (const путь of карточки) {
    if (итог.film && итог.series) break;
    const p = await get(корень + путь);
    if (p.status !== 200) continue;
    const плеер = /<video-player[^>]*data-title-id="[^"]+"/.test(p.text);
    if (!плеер) continue;
    const серии = ссылки(p.text).filter((u) => ЭПИЗОД.test(u) && u.startsWith(путь.replace(/\/$/, '')));
    if (серии.length >= 2 && !итог.series) итог.series = { url: корень + путь, episodes: серии.slice(0, 4).map((u) => корень + u) };
    else if (серии.length === 0 && !итог.film) итог.film = { url: корень + путь };
  }
  if (!итог.film) итог.notes.push('фильм с плеером среди первых 40 карточек главной не найден');
  if (!итог.series) итог.notes.push('сериал со списком серий среди первых 40 карточек главной не найден');
  return итог;
}

(async () => {
  const [out, ...домены] = process.argv.slice(2);
  const итог = [];
  for (const д of домены) {
    try { итог.push(await разведать(д)); } catch (e) { итог.push({ domain: д, error: String(e).slice(0, 200) }); }
    console.log(JSON.stringify(итог[итог.length - 1]));
  }
  fs.writeFileSync(out, JSON.stringify(итог, null, 1));
})();
