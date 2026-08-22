const PORT = process.env.FACTORY_MULTISITE_PORT || '3000';

const SITES = {
  a: { host: `http://site-a.localhost:${PORT}`, theme: 'portal_light', name: 'Стенд A — каталог' },
  b: { host: `http://site-b.localhost:${PORT}`, theme: 'pulse', name: 'Стенд B — расписание' },
  c: { host: `http://site-c.localhost:${PORT}`, theme: 'editorial', name: 'Стенд C — редакция' },
};

const url = (key, path) => `${SITES[key].host}${path}`;

module.exports = { SITES, url, PORT };
