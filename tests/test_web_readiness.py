"""Production readiness reflects whether uploads can survive a restart."""
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from viral_futbol.web import Handler


class ReadinessTests(unittest.TestCase):
    def test_missing_persistent_disk_is_not_publish_ready(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.dict(os.environ, {'YOUTUBE_ENABLED': 'true', 'NEWS_DB_PATH': '/data/viral.sqlite3'}), \
                 patch('production.queue.os.path.ismount', return_value=False):
                base = f'http://127.0.0.1:{server.server_port}'
                with urlopen(base + '/health') as response:
                    self.assertEqual(response.status, 200)
                for method in ('GET', 'HEAD'):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(base + '/ready', method=method))
                    self.assertEqual(error.exception.code, 503)
                    if method == 'GET':
                        self.assertEqual(json.load(error.exception)['status'], 'persistence_required')
        finally:
            server.shutdown()
            server.server_close()
            worker.join()
