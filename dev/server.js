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
  '.webm': 'video/webm',
};

function serve(port = 8766) {
  const server = createServer((request, response) => {
    const { pathname } = new URL(request.url, 'http://localhost');
    const path = normalize(join(ROOT, decodeURIComponent(pathname)));
    let size;
    try {
      const file = statSync(path);
      if (!path.startsWith(ROOT + sep) || !file.isFile()) throw new Error('Not a file');
      size = file.size;
    } catch (_err) {
      response.writeHead(404).end('Not found');
      return;
    }
    const headers = { 'Content-Type': TYPES[extname(path)] || 'application/octet-stream', 'Accept-Ranges': 'bytes' };
    // Safari only plays a video it can ask for in parts.
    const range = /^bytes=(\d+)-(\d*)$/.exec(request.headers.range || '');
    if (!range) {
      response.writeHead(200, { ...headers, 'Content-Length': size });
      createReadStream(path).pipe(response);
      return;
    }
    const start = Number(range[1]);
    const end = Math.min(range[2] ? Number(range[2]) : size - 1, size - 1);
    if (start > end) {
      response.writeHead(416, { 'Content-Range': `bytes */${size}` }).end();
      return;
    }
    response.writeHead(206, { ...headers, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Content-Length': end - start + 1 });
    createReadStream(path, { start, end }).pipe(response);
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
