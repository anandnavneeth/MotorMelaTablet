import http.client
import json
import threading
import unittest
from unittest.mock import patch
from bridge import Bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.server = Bridge(('127.0.0.1', 0))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self, path, body=None, **headers):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        c.request('GET' if body is None else 'POST', path, None if body is None else json.dumps(body), headers)
        r = c.getresponse()
        result = (r.status, r.getheader('Set-Cookie'), r.read())
        c.close()
        return result

    def test_pairing_required(self):
        self.assertEqual(self.request('/api', {'action': 'apply'})[0], 401)

    def test_pair_cookie_private(self):
        status, cookie, _ = self.request('/pair', {'pin': self.server.pin})
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly', cookie)
        self.assertIn('SameSite=Strict', cookie)

    def test_bad_pin_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.request('/pair', {'pin': 'invalid'})[0], 403)
        self.assertEqual(self.request('/pair', {'pin': self.server.pin})[0], 429)

    def test_cross_origin_rejected(self):
        self.assertEqual(self.request('/pair', {'pin': self.server.pin}, Origin='http://evil.example')[0], 403)

    def test_rebinding_rejected(self):
        self.assertEqual(self.request('/health', Host='evil.example')[0], 403)

    def test_paths_not_filesystem(self):
        self.assertEqual(self.request('/../bridge.py')[0], 404)

    def test_no_device_or_arbitrary_commands(self):
        _, cookie, _ = self.request('/pair', {'pin': self.server.pin})
        self.assertEqual(self.request('/api', {'action': 'enableFFB'}, Cookie=cookie)[0], 400)

    def test_disconnect_does_not_acknowledge_apply(self):
        _, cookie, _ = self.request('/pair', {'pin': self.server.pin})
        with patch('urllib.request.urlopen', side_effect=OSError('offline')):
            status, _, body = self.request('/api', {'action': 'apply'}, Cookie=cookie)
        self.assertEqual(status, 503)
        self.assertFalse(json.loads(body)['ok'])

    def test_nonfinite_rejected(self):
        self.assertEqual(self.request('/api', {'action': 'apply', 'value': float('nan')})[0], 400)

    def test_assets(self):
        for path in ['/', '/app.js', '/style.css']:
            self.assertEqual(self.request(path)[0], 200)


if __name__ == '__main__':
    unittest.main()
