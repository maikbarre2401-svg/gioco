#!/usr/bin/env python3
"""OJO DE DEUS - server locale con proxy integrato (Mac / Linux / Windows con Python).

Uso:  python3 ojo-server.py      (nella cartella di index.html)
Apre http://localhost:8765: video YouTube, notizie, aerei e borse senza blocchi CORS.
Il proxy inoltra SOLO verso i siti usati da OJO.
"""
import http.server, os, socketserver, sys, urllib.error, urllib.parse, urllib.request, webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
ALLOW = {
    'api.adsb.lol', 'api.airplanes.live', 'opendata.adsb.fi', 'opensky-network.org', 'api.adsbdb.com', 'api.planespotters.net',
    'celestrak.org', 'api.wheretheiss.at', 'earthquake.usgs.gov', 'eonet.gsfc.nasa.gov', 'firms.modaps.eosdis.nasa.gov',
    'services.swpc.noaa.gov', 'api.rainviewer.com', 'api.gdeltproject.org', 'query1.finance.yahoo.com', 'stooq.com',
    'api.coingecko.com', 'api.binance.com', 'api.frankfurter.dev', 'api.frankfurter.app', 'ipwho.is', 'ipapi.co',
    'feeds.bbci.co.uk', 'www.aljazeera.com', 'www.ansa.it', 'www.rainews.it', 'rss.dw.com', 'www.theguardian.com',
    'www.france24.com', 'rss.nytimes.com', 'feeds.npr.org', 'feeds.skynews.com', 'www.defensenews.com', 'www.timesofisrael.com',
}
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def send(self, code, body, ctype):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == '/ojo-ping':
            return self.send(200, b'{"ojo":"local-proxy","v":1}', 'application/json')
        if u.path == '/ojo-proxy':
            target = urllib.parse.parse_qs(u.query).get('url', [''])[0]
            t = urllib.parse.urlparse(target)
            if t.scheme != 'https' or t.hostname not in ALLOW:
                return self.send(403, 'host non consentito'.encode(), 'text/plain; charset=utf-8')
            try:
                req = urllib.request.Request(target, headers={'User-Agent': UA, 'Accept': '*/*'})
                with urllib.request.urlopen(req, timeout=45) as r:
                    return self.send(r.status, r.read(), r.headers.get('Content-Type', 'application/octet-stream'))
            except urllib.error.HTTPError as e:
                return self.send(e.code, e.read(), e.headers.get('Content-Type', 'text/plain'))
            except Exception as e:  # rete, SSL, timeout
                return self.send(502, ('errore proxy: %s' % e).encode(), 'text/plain; charset=utf-8')
        return super().do_GET()

    def log_message(self, *args):
        pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    if not os.path.exists(os.path.join(ROOT, 'index.html')):
        sys.exit('ERRORE: metti ojo-server.py nella stessa cartella di index.html')
    for port in range(8765, 8781):
        try:
            srv = Server(('127.0.0.1', port), Handler)
            break
        except OSError:
            continue
    else:
        sys.exit('ERRORE: nessuna porta libera tra 8765 e 8780')
    url = 'http://localhost:%d/' % port
    print('\n  OJO DE DEUS attivo su %s\n  Proxy integrato attivo. Ctrl+C per fermare.\n' % url)
    webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
