// Small static server for the harness, the tests and the README media.
const { createReadStream, statSync } = require('node:fs');
const { createServer } = require('node:http');
const { extname, join, normalize, sep } = require('node:path');

const ROOT = join(__dirname, '..');
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.png': 'image/png',
  '.gif': 'image/gif',
};

function serve(port = 8766) {
  const server = createServer((request, response) => {
    const { pathname } = new URL(request.url, 'http://localhost');
    const path = normalize(join(ROOT, decodeURIComponent(pathname)));
    try {
      if (!path.startsWith(ROOT + sep) || !statSync(path).isFile()) throw new Error('Not a file');
    } catch (_err) {
      response.writeHead(404).end('Not found');
      return;
    }
    response.writeHead(200, { 'Content-Type': TYPES[extname(path)] || 'application/octet-stream' });
    createReadStream(path).pipe(response);
  });
  return new Promise((resolve) => {
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

if (require.main === module) {
  const port = Number(process.argv[2]) || 8766;
  serve(port).then(() => console.log(`Harness: http://127.0.0.1:${port}/dev/harness.html`));
}

module.exports = { serve };
