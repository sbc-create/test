// Четыре сайта направления Lords на четырёх портах локального стенда.
const HOST = process.env.LORDS_HOST || '127.0.0.1';

const SITES = {
  'lords-01': { port: 8801, profile: 'lords-general', label: 'Lords General' },
  'lords-02': { port: 8802, profile: 'lords-new', label: 'Lords New' },
  'lords-03': { port: 8803, profile: 'lords-curated', label: 'Lords Curated' },
  'lords-04': { port: 8804, profile: 'lords-genre', label: 'Lords Genre' },
};

const base = (id) => `http://${HOST}:${SITES[id].port}`;
const url = (id, path) => `${base(id)}${path}`;

// Ширины из задания. 1440 — десктоп, 768 — планшет, 390 — телефон.
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 390, height: 844 },
];

module.exports = { SITES, base, url, VIEWPORTS, HOST };
