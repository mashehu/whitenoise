from __future__ import absolute_import, unicode_literals

import errno
import os
import shutil
import tempfile
from unittest import TestCase
from wsgiref.simple_server import demo_app

from .utils import TestServer, gzip_bytes

from whitenoise import WhiteNoise


# Update Py2 TestCase to support Py3 method names
if not hasattr(TestCase, 'assertRegex'):
    class Py3TestCase(TestCase):
        def assertRegex(self, *args, **kwargs):
            return self.assertRegexpMatches(*args, **kwargs)
    TestCase = Py3TestCase


JS_FILE = '/some/test.js'
GZIP_FILE = '/compress.css'
TEST_FILES = {
    JS_FILE: b'this is some javascript',
    GZIP_FILE: b'some css goes here'
}
TEST_FILES[GZIP_FILE + '.gz'] = gzip_bytes(TEST_FILES[GZIP_FILE])


class WhiteNoiseTest(TestCase):

    @classmethod
    def setUpClass(cls):
        # Make a temporary directory and copy in test files
        cls.tmp = tempfile.mkdtemp()
        for path, contents in TEST_FILES.items():
            path = os.path.join(cls.tmp, path.lstrip('/'))
            try:
                os.makedirs(os.path.dirname(path))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
            with open(path, 'wb') as f:
                f.write(contents)
        # Initialize test application
        cls.application = WhiteNoise(demo_app,
                root=cls.tmp, default_max_age = 1000)
        cls.server = TestServer(cls.application)
        super(WhiteNoiseTest, cls).setUpClass()

    @classmethod
    def tearDownClass(cls):
        super(WhiteNoiseTest, cls).tearDownClass()
        # Remove temporary directory
        shutil.rmtree(cls.tmp)

    def test_get_file(self):
        response = self.server.get(JS_FILE)
        self.assertEqual(response.content, TEST_FILES[JS_FILE])
        self.assertRegex(response.headers['Content-Type'], r'application/javascript\b')
        self.assertRegex(response.headers['Content-Type'], r'.*\bcharset="utf-8"')

    def test_get_not_accept_gzip(self):
        response = self.server.get(GZIP_FILE, headers={'Accept-Encoding': ''})
        self.assertEqual(response.content, TEST_FILES[GZIP_FILE])
        self.assertEqual(response.headers.get('Content-Encoding', ''), '')
        self.assertEqual(response.headers['Vary'], 'Accept-Encoding')

    def test_get_accept_gzip(self):
        response = self.server.get(GZIP_FILE)
        self.assertEqual(response.content, TEST_FILES[GZIP_FILE])
        self.assertEqual(response.headers['Content-Encoding'], 'gzip')
        self.assertEqual(response.headers['Vary'], 'Accept-Encoding')

    def test_not_modified(self):
        response = self.server.get(JS_FILE)
        last_mod = response.headers['Last-Modified']
        response = self.server.get(JS_FILE, headers={'If-Modified-Since': last_mod})
        self.assertEqual(response.status_code, 304)

    def test_max_age(self):
        response = self.server.get(JS_FILE)
        self.assertEqual(response.headers['Cache-Control'], 'public, max-age=1000')

    def test_other_requests_passed_through(self):
        response = self.server.get('/not/static')
        self.assertIn('Hello world!', response.text)

    def test_add_under_prefix(self):
        prefix = '/prefix'
        self.application.add_files(self.tmp, prefix=prefix)
        response = self.server.get(prefix + JS_FILE)
        self.assertEqual(response.content, TEST_FILES[JS_FILE])