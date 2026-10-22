import http from "node:http"; import fs from "node:fs"; import path from "node:path";
const root = path.resolve("dist"); const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".woff": "font/woff", ".xml": "application/xml", ".txt": "text/plain" };
http.createServer((req, res) => {
  let u = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (!u.startsWith("/skillpact/")) { res.writeHead(u === "/skillpact" ? 301 : 404, { Location: "/skillpact/" }); return res.end(); }
  let p = path.join(root, u.slice("/skillpact/".length)); if (!p.startsWith(root)) { res.writeHead(403); return res.end(); }
  if (fs.existsSync(p) && fs.statSync(p).isDirectory()) { if (!u.endsWith("/")) { res.writeHead(301, { Location: u + "/" }); return res.end(); } p = path.join(p, "index.html"); }
  if (!fs.existsSync(p)) { res.writeHead(404, { "content-type": "text/html" }); return res.end(fs.existsSync(path.join(root, "404.html")) ? fs.readFileSync(path.join(root, "404.html")) : "404"); }
  res.writeHead(200, { "content-type": types[path.extname(p)] || "application/octet-stream" }); fs.createReadStream(p).pipe(res);
}).listen(process.env.PORT || 4173, () => console.log("http://localhost:" + (process.env.PORT || 4173) + "/skillpact/"));
