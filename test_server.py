"""Run: python -m unittest -v (uses only a temporary local server and database)."""
import http.client
import json
import tempfile
import threading
import unittest

from cryptography.hazmat.primitives.asymmetric import ec
from crypto_utils import jwk
from server import DemoServer, public_origin


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.origin = 'https://demo-8000.app.github.dev'
        cls.server = DemoServer(('127.0.0.1', 0), cls.temp.name, cls.origin)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.worker.join()
        cls.server.server_close()
        cls.temp.cleanup()

    def call(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        extra = {} if headers is None else headers.copy()
        if isinstance(body, dict):
            body = json.dumps(body)
            extra.setdefault('Content-Type', 'application/json')
        connection.request(method, path, body=body, headers=extra)
        response = connection.getresponse()
        status, meta, data = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return status, meta, data

    def test_codespaces_origin_and_validation(self):
        self.assertEqual(public_origin(8000, env={'CODESPACE_NAME': 'quiet-tree'}),
                         'https://quiet-tree-8000.app.github.dev')
        self.assertEqual(public_origin(9000, env={'PUBLIC_ORIGIN': 'https://demo.example/'}), 'https://demo.example')
        self.assertEqual(public_origin(8000, env={}), 'http://127.0.0.1:8000')
        for bad in ['http://demo.example', 'https://demo.example/path', 'https://u:p@demo.example',
                    'https://demo.example?query', 'https://demo.example:wrong']:
            with self.subTest(origin=bad), self.assertRaises(ValueError):
                public_origin(8000, bad)

    def test_static_config_and_private_files(self):
        for path in ['/', '/app.js', '/style.css', '/health', '/api/mdoc/config']:
            with self.subTest(path=path):
                status, headers, data = self.call('GET', path)
                self.assertEqual(status, 200)
                self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                self.assertTrue(data)
        status, _, data = self.call('GET', '/api/mdoc/config')
        self.assertEqual(json.loads(data)['origin'], self.origin)
        for path in ['/data/mdoc/IACA.key', '/../mdoc.py', '/.env', '/lab', '/dev-ca.cer']:
            self.assertEqual(self.call('GET', path)[0], 404)

    def test_https_proxy_origin_and_native_client(self):
        status, _, data = self.call('POST', '/api/mdoc/request', {'origin': self.origin},
                                    {'Origin': self.origin, 'Host': 'internal:8000', 'X-Forwarded-Proto': 'http'})
        self.assertEqual(status, 200, data)
        self.assertEqual(json.loads(data)['protocol'], 'org-iso-mdoc')
        key = ec.generate_private_key(ec.SECP256R1())
        self.assertEqual(self.call('POST', '/api/mdoc/issue', {'holder_jwk': jwk(key)})[0], 200)
        status, _, _ = self.call('POST', '/api/mdoc/request', {'origin': self.origin},
                                 {'Origin': 'https://evil.example', 'X-Forwarded-Host': 'demo-8000.app.github.dev'})
        self.assertEqual(status, 400)

    def test_invalid_inputs_and_unknown_api(self):
        for body in ['{broken', '[]']:
            self.assertEqual(self.call('POST', '/api/mdoc/request', body, {'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(self.call('POST', '/api/mdoc/request', '{}', {'Content-Type': 'text/plain'})[0], 400)
        self.assertEqual(self.call('POST', '/api/mdoc/request', '{}', {'Content-Length': '131073'})[0], 400)
        self.assertEqual(self.call('POST', '/api/missing', {})[0], 404)
        self.assertEqual(self.call('POST', '/api/mdoc/issue', {'holder_jwk': {'kty': 'EC', 'crv': 'P-256'}})[0], 400)

    def test_tunnel_origin_requires_browser_token_and_same_origin_metadata(self):
        _, _, data = self.call('GET', '/api/mdoc/config')
        token = json.loads(data)['browser_request_token']
        self.assertIsInstance(token, str)  # Preserve the native client's string-only config.
        local = f'http://localhost:{self.server.server_port}'
        headers = {'Origin': local, 'Sec-Fetch-Site': 'same-origin', 'X-VDC-Browser-Token': token}
        status, _, data = self.call('POST', '/api/mdoc/request', {'origin': self.origin}, headers)
        self.assertEqual(status, 200, data)
        self.assertEqual(json.loads(data)['protocol'], 'org-iso-mdoc')
        for scheme in ('http', 'https'):
            for host in ('localhost', '127.0.0.1', '[::1]'):
                allowed = dict(headers, Origin=f'{scheme}://{host}:{self.server.server_port}')
                with self.subTest(origin=allowed['Origin']):
                    self.assertEqual(self.call('POST', '/api/mdoc/request', {'origin': self.origin}, allowed)[0], 200)
                for change in [{'X-VDC-Browser-Token': ''}, {'X-VDC-Browser-Token': 'wrong'},
                               {'Sec-Fetch-Site': ''}, {'Sec-Fetch-Site': 'cross-site'}, {'Sec-Fetch-Site': 'same-site'},
                               {'Origin': 'null'}, {'Origin': 'https://evil.example'},
                               {'Origin': f'{scheme}://localhost:1'}]:
                    with self.subTest(origin=allowed['Origin'], change=change):
                        invalid = dict(allowed, **change, **{'X-Forwarded-Host': 'demo-8000.app.github.dev'})
                        self.assertEqual(self.call('POST', '/api/mdoc/request', {'origin': self.origin}, invalid)[0], 400)
        # The JSON protocol origin stays bound to the public website even through the tunnel.
        self.assertEqual(self.call('POST', '/api/mdoc/request', {'origin': local}, headers)[0], 400)


if __name__ == '__main__':
    unittest.main(verbosity=2)
