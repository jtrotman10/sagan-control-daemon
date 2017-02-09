import os
from codecs import decode
from http.server import HTTPServer, SimpleHTTPRequestHandler

import sys
from urllib.parse import parse_qs

from os.path import isfile


def preprocess_file(file, context):
    with open(file, 'r') as f:
        source = f.read()
    return source.format(**context).encode()

_context = {
    'ssid': '',
    'psk': '',
    'pairing_code': '',
}

_state = 'awaiting_config'


class Handler(SimpleHTTPRequestHandler):
    def render(self, path):
        global _context
        content = b''
        status = 404
        if isfile(path):
            content = preprocess_file(path, _context)
            status = 200

        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        global _state
        path = self.path
        if path == '/':
            path = '/index.html'

        if path == '/configuring.html':
            if _state == 'posted_configuration':
                _state = 'confirmed'
            else:
                self.send_response(303)
                self.send_header('Location', '/')
                self.end_headers()
                return

        if path == '/':
            _state = 'awaiting_config'

        if len(path) > 5 and path[-5:] == '.html':
            self.render(path[1:])
        else:
            super(Handler, self).do_GET()

    def do_POST(self):
        global _context
        content_length = self.headers.get('content-length', '0')
        post_body = self.rfile.read(int(content_length))
        config_values = parse_qs(post_body)
        _context.update({decode(k): decode(v[0]) for k, v in config_values.items()})

        self.send_response(303)
        self.send_header('Location', '/configuring.html')
        self.end_headers()

        print(_context['pairing_code'])
        print(_context['ssid'])
        print(_context['psk'])
        print('\n')
        sys.stdout.flush()

        global _state
        _state = 'received_config'


def main():
    os.chdir('content')
    server = HTTPServer((sys.argv[1], int(sys.argv[2])), Handler)
    server.serve_forever()


if __name__ == '__main__':
    main()
