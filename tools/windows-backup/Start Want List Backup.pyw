"""Double-click on Windows. No startup Cloudflare requests, credential files or logs."""
import base64
import hmac
import json
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from core import Cloudflare, Stop, MAX_BYTES, backup, restore_verify

ASSETS = {'/': ('backup.html','text/html; charset=utf-8'),
          '/backup.js': ('backup.js','text/javascript; charset=utf-8'),
          '/crypto.js': ('crypto.js','text/javascript; charset=utf-8')}

class Server(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def send(self, status, raw, kind='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Cross-Origin-Opener-Policy','same-origin')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(raw)
    def host_ok(self):
        return self.headers.get('Host') == self.server.host
    def do_GET(self):
        if not self.host_ok() or self.path not in ASSETS:
            self.send(404,b'{}'); return
        name, kind = ASSETS[self.path]
        self.send(200,(Path(__file__).parent/name).read_bytes(),kind)
    def do_POST(self):
        if (not self.host_ok() or self.headers.get('Origin') != self.server.origin or
            not hmac.compare_digest(self.headers.get('X-WantList-Local',''),self.server.capability) or
            self.headers.get('Content-Type') != 'application/json'):
            self.send(403,b'{"error":"Local request refused."}'); return
        self.server.last_activity=time.monotonic()
        if self.path == '/close':
            self.send(200,b'{}');threading.Thread(target=self.server.shutdown,daemon=True).start();return
        if self.path not in ('/backup','/restore'):
            self.send(404,b'{}');return
        if not self.server.operation_lock.acquire(blocking=False):
            self.send(409,b'{"error":"An operation is already running. Do not start another."}');return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length <= MAX_BYTES*2:
                raise Stop('File/request exceeds the reviewed memory limit.')
            data=json.loads(self.rfile.read(length))
            if self.path == '/backup':
                client=Cloudflare(data.get('account'),data.get('token'))
                try:
                    raw,report=backup(client,data.get('approvals',{}))
                finally:
                    client.token='';data['token']=''
                output={'plaintext_b64':base64.b64encode(raw).decode(),'report':report}
            else:
                raw=base64.b64decode(data.get('plaintext_b64',''),validate=True)
                if len(raw)>MAX_BYTES:raise Stop('Snapshot exceeds reviewed restoration limits.')
                output={'report':restore_verify(json.loads(raw))}
            self.send(200,json.dumps(output,separators=(',',':')).encode())
        except Stop as error:
            self.send(409,json.dumps({'error':str(error)}).encode())
        except Exception:
            self.send(409,b'{"error":"Operation stopped. No data or credentials logged. No retry performed."}')
        finally:
            self.server.operation_lock.release()

def main():
    with Server(('127.0.0.1',0),Handler) as server:
        server.host='127.0.0.1:'+str(server.server_port)
        server.origin='http://'+server.host
        server.capability=secrets.token_urlsafe(32)
        server.operation_lock=threading.Lock()
        server.last_activity=time.monotonic()
        def expire():
            while True:
                time.sleep(30)
                if not server.operation_lock.locked() and time.monotonic()-server.last_activity>900:
                    server.shutdown();return
        threading.Thread(target=expire,daemon=True).start()
        webbrowser.open(server.origin+'/#'+server.capability)
        server.serve_forever()

if __name__=='__main__':
    try:main()
    except Exception:
        try:
            from tkinter import messagebox
            messagebox.showerror('Want List Backup','Could not open the local backup tool. Check Python is installed and all extracted files are together. No Cloudflare request was made at startup.')
        except Exception:pass
