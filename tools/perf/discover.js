// Подбор сценариев по каждому домену: каталог/поиск, карточка фильма,
// страница сериала со списком серий. Только GET публичных страниц.
// node tools/perf/discover.js <out.json> <domain>...
const fs = require('fs');

const ЭПИЗОД = /\/(season[-/]\d+\/)?episode[-/](\d+)\/?$/;

async function get(url) {
  const r = await fetch(url, { redirect: 'follow', headers: { 'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36 site-factory-perf-audit' } });
  return { status: r.status, url: r.url, text: r.status === 200 ? await r.text() : '' };
}

// Подтверждённый поток: плейлист провайдера с publisher и Origin витрины —
// тот же запрос, что делает браузер посетителя. 204/пусто — потока нет.
async function поток(html, домен) {
  const m = html.match(/<video-player[^>]*>/);
  if (!m) return { ok: false, why: 'нет video-player' };
  const a = (имя) => ((m[0].match(new RegExp(`${имя}="([^"]*)"`)) || [])[1] || '');
  const pub = a('data-publisher-id'); const aggr = a('data-aggregator'); const id = a('data-title-id');
  if (!pub || !id) return { ok: false, why: 'нет publisher или id' };
  const r = await fetch(`https://plapi.cdnvideohub.com/api/v1/player/sv/playlist?pub=${pub}&aggr=${aggr}&id=${id}`,
    { headers: { origin: `https://${домен}`, referer: `https://${домен}/` } });
  if (r.status !== 200) return { ok: false, why: `плейлист ${r.status}`, pub };
  const j = await r.json().catch(() => null);
  const items = (j && j.items) || [];
  return { ok: items.length > 0, pub, aggr, id, items: items.length,
           eps: items.filter((x) => x.season === 1).map((x) => x.episode), why: items.length ? '' : 'пустой плейлист' };
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
  const карточки = все.filter((u) => /^\/(title|anime|film|serial|movie)\//.test(u) && !ЭПИЗОД.test(u)).slice(0, 120);
  for (const путь of карточки) {
    if (итог.film && итог.series) break;
    const p = await get(корень + путь);
    if (p.status !== 200) continue;
    const плеер = /<video-player[^>]*data-title-id="[^"]+"/.test(p.text);
    if (!плеер) continue;
    const серии = ссылки(p.text).filter((u) => ЭПИЗОД.test(u) && u.startsWith(путь.replace(/\/$/, '')));
    const нужен = (серии.length >= 2 && !итог.series) || (серии.length === 0 && !итог.film);
    if (!нужен) continue;
    const п = await поток(p.text, домен);
    if (!п.ok) { итог.notes.push(`${путь}: поток не подтверждён (${п.why})`); continue; }
    if (серии.length >= 2) {
      const номер = (u) => +((u.match(ЭПИЗОД) || [])[2] || 0);
      const упор = серии.map((u) => корень + u).sort((x, y) => номер(x) - номер(y));
      // Обе серии перехода обязаны быть в плейлисте провайдера.
      const есть = упор.filter((u) => п.eps.includes(номер(u)));
      if (есть.length < 2) { итог.notes.push(`${путь}: в плейлисте нет двух серий сезона 1`); continue; }
      итог.series = { url: корень + путь, episodes: есть.slice(0, 4), stream: п };
    } else итог.film = { url: корень + путь, stream: п };
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
