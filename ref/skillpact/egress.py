"""Egress allowlist for `network: true` test cases (spec 0.8.x erratum, s10).

The case still runs without a network interface of its own (bubblewrap --unshare-net). Its only way out is an HTTP proxy
on 127.0.0.1 inside the sandbox, which relays to a Unix socket bound in from the host. On the host, outside the sandbox,
`EgressProxy` accepts CONNECT and absolute-form HTTP requests only for hosts the contract declares, and records every host
asked for. Programs that ignore the proxy variables get no network at all (fail closed)."""
from __future__ import annotations
import os, select, socket, socketserver, sys, threading
from pathlib import Path
from urllib.parse import urlsplit

IN_SANDBOX_PORT = 18080
RELAY_NAME = "skillpact-egress"   # file name of the in-sandbox relay (a launcher for the exec audit)
PROXY_VARS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")

RELAY = r'''
import os, socket, sys, threading
sock_path, port, argv = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); srv.bind(("127.0.0.1", port)); srv.listen(64)
def pump(a, b):
    try:
        while True:
            d = a.recv(65536)
            if not d: break
            b.sendall(d)
    except OSError: pass
    finally:
        for s in (a, b):
            try: s.shutdown(socket.SHUT_RDWR)
            except OSError: pass
def serve():
    while True:
        c, _ = srv.accept(); u = socket.socket(socket.AF_UNIX)
        try: u.connect(sock_path)
        except OSError: c.close(); continue
        threading.Thread(target=pump, args=(c, u), daemon=True).start(); threading.Thread(target=pump, args=(u, c), daemon=True).start()
if os.fork() == 0:
    os.setsid(); serve()
srv.close(); os.execvp(argv[0], argv)
'''


def allowed(host: str, scope, level: str) -> bool:
    from . import core
    if level == "any": return True
    return any(core.glob_match(host, p, "host") for p in scope)


def _upstream():
    """The host's own proxy (e.g. a corporate or agent proxy), used for non-local hosts."""
    u = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if not u: return None
    s = urlsplit(u if "://" in u else "http://" + u)
    return (s.hostname, s.port or 80) if s.hostname else None


def _connect(host, port):
    from . import core
    up = None if core.is_local_host(host) else _upstream()
    if not up: return socket.create_connection((host, port), timeout=30)
    s = socket.create_connection(up, timeout=30)
    s.sendall(f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n".encode())
    head = b""
    while b"\r\n\r\n" not in head:
        d = s.recv(4096)
        if not d: raise OSError("upstream proxy closed")
        head += d
    if b" 200" not in head.split(b"\r\n", 1)[0]: raise OSError("upstream proxy refused CONNECT")
    return s


def _pump(a, b):
    try:
        while True:
            r, _, _ = select.select([a, b], [], [], 300)
            if not r: return
            for s in r:
                d = s.recv(65536)
                if not d: return
                (b if s is a else a).sendall(d)
    except OSError: return


class EgressProxy:
    """Host side. `allowed_hosts` / `denied_hosts` list every host a case asked for."""
    def __init__(self, scope, level, sock_path):
        self.scope, self.level, self.allowed_hosts, self.denied_hosts = list(scope), level, [], []
        proxy = self
        class H(socketserver.BaseRequestHandler):
            def handle(self):
                c = self.request; head = b""
                while b"\r\n\r\n" not in head and len(head) < 65536:
                    d = c.recv(4096)
                    if not d: return
                    head += d
                line = head.split(b"\r\n", 1)[0].decode("latin-1")
                parts = line.split(" ")
                if len(parts) != 3: c.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n"); return
                method, target, ver = parts
                if method == "CONNECT":
                    host, _, port = target.rpartition(":"); host = host.strip("[]"); port = int(port or 443); rest = b""
                else:
                    u = urlsplit(target)
                    if u.scheme != "http" or not u.hostname: c.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n"); return
                    host, port = u.hostname, u.port or 80
                    path = (u.path or "/") + (("?" + u.query) if u.query else "")
                    rest = head.replace(line.encode("latin-1"), f"{method} {path} {ver}".encode("latin-1"), 1)
                if not allowed(host, proxy.scope, proxy.level):
                    if host not in proxy.denied_hosts: proxy.denied_hosts.append(host)
                    c.sendall(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n"); return
                if host not in proxy.allowed_hosts: proxy.allowed_hosts.append(host)
                try: s = _connect(host, port)
                except OSError: c.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n"); return
                if method == "CONNECT": c.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
                else: s.sendall(rest)
                _pump(c, s); s.close()
        class S(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True
        self.server = S(str(sock_path), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown(); self.server.server_close()


class Egress:
    """One case: a host-side proxy, the relay script and the directory bound into the sandbox."""
    MOUNT = "/run/skillpact-egress"

    def __init__(self, scope, level):
        import tempfile
        self.dir = Path(tempfile.mkdtemp(prefix="sp-egress-"))
        self.proxy = EgressProxy(scope, level, self.dir / "proxy.sock")
        relay = self.dir / RELAY_NAME
        relay.write_text(f"#!{sys.executable}\n" + RELAY); relay.chmod(0o755)

    def bwrap_args(self):
        return ["--bind", str(self.dir), self.MOUNT]

    def wrap(self, cmd):
        return [f"{self.MOUNT}/{RELAY_NAME}", f"{self.MOUNT}/proxy.sock", str(IN_SANDBOX_PORT)] + cmd

    def env(self):
        u = f"http://127.0.0.1:{IN_SANDBOX_PORT}"
        return {**{v: u for v in PROXY_VARS}, "NO_PROXY": "", "no_proxy": ""}

    def keep(self):
        """Interpreter locations the relay needs inside the sandbox (re-exposed if under a masked root)."""
        return [sys.base_prefix, os.path.dirname(os.path.realpath(sys.executable))]

    def close(self):
        import shutil
        self.proxy.close(); shutil.rmtree(self.dir, ignore_errors=True)
