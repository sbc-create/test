/**
 * A minimal static server for the widget harness.
 *
 * It exists because `file://` is not a usable origin for this suite: browsers
 * refuse `fetch` from it outright, which made the first run's "empty state"
 * test pass for entirely the wrong reason — the request failed, the error path
 * left the empty message visible, and the assertion could not tell the two
 * apart. A real http origin makes the network mocks meaningful and the CORS,
 * credential and abort paths real.
 *
 * It serves only files under the repository root, resolves symlinks and
 * refuses anything that escapes that root. It binds to loopback. It is a test
 * fixture and has no place in a deployment.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..', '..');
const PORT = Number(process.env.CP_HARNESS_PORT || 8787);

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
};

const server = http.createServer((req, res) => {
  const requested = decodeURIComponent((req.url || '/').split('?')[0]);
  const resolved = path.resolve(ROOT, '.' + requested);

  // Path traversal: resolve first, then check containment. Checking the raw
  // string for '..' catches the obvious case and misses the encoded one.
  if (resolved !== ROOT && !resolved.startsWith(ROOT + path.sep)) {
    res.writeHead(403).end('forbidden');
    return;
  }

  fs.readFile(resolved, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain' }).end('not found');
      return;
    }
    res.writeHead(200, {
      'Content-Type': TYPES[path.extname(resolved)] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    res.end(data);
  });
});

server.listen(PORT, '127.0.0.1', () => {
  process.stdout.write(`comments harness on http://127.0.0.1:${PORT}\n`);
});
