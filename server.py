"""One-process Apple mdoc demo. Codespaces terminates public HTTPS for us."""
import argparse
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature, InvalidTag
from mdoc import MDocLab

ROOT = Path(__file__).resolve().parent
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}


def public_origin(port, explicit=None, env=None):
    env = os.environ if env is None else env
    origin = explicit or env.get('PUBLIC_ORIGIN')
    if not origin and env.get('CODESPACE_NAME'):
        domain = env.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', 'app.github.dev')
        origin = f"https://{env['CODESPACE_NAME']}-{port}.{domain}"
    origin = (origin or f'http://127.0.0.1:{port}').rstrip('/')
    parsed = urlsplit(origin)
    if (parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username
            or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('PUBLIC_ORIGIN 必须是完整来源，如 https://name-8000.app.github.dev，不带路径')
    if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('公网来源必须使用 HTTPS；只有本机回环地址可使用 HTTP')
    _ = parsed.port  # Reject malformed ports before starting the service.
    return origin


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data, origin):
        directory = Path(data)
        directory.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(directory / 'lab.sqlite', check_same_thread=False)
        self.lab = MDocLab(directory, self.db, origin)
        self.browser_token = secrets.token_urlsafe(32)
        # ponytail: one demo process; use transactional storage if scaling to multiple workers.
        self.lock = threading.Lock()
        super().__init__(address, Handler)

    def server_close(self):
        super().server_close()
        self.db.close()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *_):
        pass  # Never log capability IDs, credential bodies or private keys.

    def respond(self, code, data, content_type='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
        self.send_response(code)
        for key, value in {
            'Content-Type': content_type,
            'Content-Length': str(len(data)),
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'Permissions-Policy': 'digital-credentials-get=(self)',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        }.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/health':
            return self.respond(200, {'ok': True})
        if path == '/api/mdoc/config':
            with self.server.lock:
                return self.respond(200, dict(self.server.lab.config(), browser_request_token=self.server.browser_token))
        if path in ASSETS:
            name, kind = ASSETS[path]
            return self.respond(200, (ROOT / 'static' / name).read_bytes(), kind)
        self.respond(404, {'error': '接口不存在'})

    def do_POST(self):
        routes = {
            '/api/mdoc/issue': self.server.lab.issue,
            '/api/mdoc/request': self.server.lab.request,
            '/api/mdoc/verify': self.server.lab.verify,
            '/api/mdoc/revoke': self.server.lab.revoke,
        }
        action = routes.get(urlsplit(self.path).path)
        if action is None:
            return self.respond(404, {'error': '接口不存在'})
        try:
            # Dev tunnels may rewrite Origin to the local listening address. Accept that
            # alias only with a same-origin browser token; never trust X-Forwarded-*.
            # Native URLSession requests need no Origin header.
            origin = self.headers.get('Origin')
            if origin and origin != self.server.lab.origin:
                aliases = {f'http://{host}:{self.server.server_port}' for host in ('localhost', '127.0.0.1', '[::1]')}
                token = self.headers.get('X-VDC-Browser-Token', '')
                tunnel_browser = (origin in aliases
                                  and self.headers.get('Sec-Fetch-Site') == 'same-origin'
                                  and hmac.compare_digest(token, self.server.browser_token))
                if not tunnel_browser:
                    raise ValueError(f'请求来源不受信任：收到 {origin}，网站配置为 {self.server.lab.origin}。请使用配置地址并刷新网页后重试')
            if self.headers.get_content_type() != 'application/json':
                raise ValueError('需要 application/json')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 131072:
                raise ValueError('请求为空或超过 128 KB')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('请求必须是 JSON 对象')
            with self.server.lock:
                result = action(body)
            self.respond(200, result)
        except InvalidTag:
            self.respond(400, {'error': 'HPKE 解密失败：响应或网站会话不匹配'})
        except InvalidSignature:
            self.respond(400, {'error': '文档或设备签名无效'})
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.respond(400, {'error': str(error) or '请求格式错误'})
        except Exception:
            logging.exception('Demo request failed')
            self.respond(500, {'error': '服务异常，请检查服务端日志'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8000')))
    parser.add_argument('--origin', help='覆盖自动发现的公网 HTTPS 来源')
    parser.add_argument('--data', default=str(ROOT / 'data'))
    args = parser.parse_args()
    origin = public_origin(args.port, args.origin)
    server = DemoServer((args.host, args.port), args.data, origin)
    config = server.lab.config()
    print(f"本地监听：http://127.0.0.1:{args.port}\n公开地址：{origin}", flush=True)
    print(f"发行根指纹：{config['issuer_fingerprint']}\nReader 根指纹：{config['reader_fingerprint']}", flush=True)
    print('仅使用固定虚构资料。Codespaces PORTS 中将 8000 设为 Public，内部协议保留 HTTP。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
