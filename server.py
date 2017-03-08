import os
from codecs import decode
from http.server import HTTPServer, SimpleHTTPRequestHandler

import sys
from urllib.parse import parse_qs
from json import dumps

from os.path import isfile


def preprocess_file(file, context):
    with open(file, 'r') as f:
        source = f.read()
    return source.format(json=dumps(context)).encode()

_context = {
    'paired': '0',
    'ssid': '',
    'psk': '',
    'device_id': '',
    'pairing_code': '',
    'name': '',
    'error': '',
    'networks': ''
}


class Handler(SimpleHTTPRequestHandler):
    def render(self, path):
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
        path = self.path

        if path == '/config':
            self.render_config()
        elif path == '/logs':
            self.render_logs()
        else:
            super(Handler, self).do_GET()

    def render_config(self):
        content = dumps(_context).encode()
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def render_logs(self):
        content = open('/opt/sagan-control-daemon/log.txt').read()
        self.send_response(200)
        self.send_header("Content-type", "text")
        self.send_header("Content-Length", len(content))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        content_length = self.headers.get('content-length', '0')
        post_body = self.rfile.read(int(content_length))
        config_values = parse_qs(post_body)
        config_values = ({decode(k): decode(v[0]) for k, v in config_values.items()})
        _context.update(config_values)

        self.send_response(201)
        self.end_headers()

        print(_context['pairing_code'])
        print(_context['ssid'])
        print(_context['psk'])
        print(_context['name'])
        print('')
        sys.stdout.flush()


def main():
    i = 3
    while i < len(sys.argv):
        try:
            key = sys.argv[i]
            value = sys.argv[i + 1]
        except KeyError:
            exit(1)
            return
        _context[key] = value
        i += 2

    os.chdir('content')
    server = HTTPServer((sys.argv[1], int(sys.argv[2])), Handler)
    server.serve_forever()


if __name__ == '__main__':
    main()
