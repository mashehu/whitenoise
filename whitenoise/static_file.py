from collections import namedtuple
from email.utils import parsedate
import re
from wsgiref.headers import Headers

from .http_status import HTTPStatus
from .utils import MissingFileError, stat_regular_file


Response = namedtuple('Response', ('status', 'headers', 'file'))

NOT_ALLOWED = Response(HTTPStatus.METHOD_NOT_ALLOWED,
                       (('Allow', 'GET, HEAD'),),
                       None)
NOT_MODIFIED = Response(HTTPStatus.NOT_MODIFIED, (), None)

ACCEPT_GZIP_RE = re.compile(r'\bgzip\b')
ACCEPT_BROTLI_RE = re.compile(r'\bbr\b')


class StaticFile(object):

    def __init__(self, path, headers):
        plain_file, gzip_file, brotli_file = get_alternatives(path, headers)
        self.plain_file = file_tuple(plain_file)
        self.gzip_file = file_tuple(gzip_file)
        self.brotli_file = file_tuple(brotli_file)
        self.last_modified = parsedate(headers['Last-Modified'])

    def get_response(self, method, request_headers):
        if method != 'GET' and method != 'HEAD':
            return NOT_ALLOWED
        elif self.file_not_modified(request_headers):
            return NOT_MODIFIED
        path, headers = self.get_path_and_headers(request_headers)
        if method != 'HEAD':
            file_handle = open(path, 'rb')
        else:
            file_handle = None
        return Response(HTTPStatus.OK, headers, file_handle)

    def get_path_and_headers(self, request_headers):
        accept_encoding = request_headers.get('HTTP_ACCEPT_ENCODING', '')
        if self.brotli_file and ACCEPT_BROTLI_RE.search(accept_encoding):
            return self.brotli_file
        if self.gzip_file and ACCEPT_GZIP_RE.search(accept_encoding):
            return self.gzip_file
        return self.plain_file

    def file_not_modified(self, request_headers):
        try:
            last_requested = request_headers['HTTP_IF_MODIFIED_SINCE']
        except KeyError:
            return False
        return parsedate(last_requested) >= self.last_modified


def get_alternatives(path, headers):
    gzip_file = get_alternative_encoding(path, headers, '.gz', 'gzip')
    brotli_file = get_alternative_encoding(path, headers, '.br', 'br')
    if gzip_file or brotli_file:
        headers['Vary'] = 'Accept-Encoding'
    plain_file = (path, headers)
    return plain_file, gzip_file, brotli_file


def get_alternative_encoding(path, headers, suffix, encoding):
    alt_path = path + suffix
    try:
        alt_size = stat_regular_file(alt_path).st_size
    except MissingFileError:
        return None
    alt_headers = Headers(headers.items())
    alt_headers['Vary'] = 'Accept-Encoding'
    alt_headers['Content-Encoding'] = encoding
    alt_headers['Content-Length'] = str(alt_size)
    return alt_path, alt_headers


def file_tuple(path_and_headers):
    if path_and_headers is None:
        return None
    else:
        path, headers = path_and_headers
        return path, tuple(headers.items())
