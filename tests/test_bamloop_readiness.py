"""BAMLOOP must not report publish readiness on an ephemeral filesystem."""
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bamloop.service import Handler


class ReadinessTests(unittest.TestCase):
    def test_direct_mode_ready_without_disk(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.dict(os.environ, {'MEME_YOUTUBE_ENABLED':'true', 'PUBLISH_DIRECT_ENABLED':'true',
                                          'MEME_DB_PATH':'storage/test-bamloop.sqlite3'}):
                base=f'http://127.0.0.1:{server.server_port}'
                for method in ('GET','HEAD'):
                    with urlopen(Request(base+'/ready',method=method)) as response:
                        self.assertEqual(response.status,200)
        finally:
            server.shutdown(); server.server_close(); worker.join()

    def test_youtube_enabled_without_disk_has_unready_get_and_head(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with patch.dict(os.environ, {'MEME_YOUTUBE_ENABLED': 'true',
                                          'MEME_DB_PATH': '/data/bamloop.sqlite3'}), \
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
