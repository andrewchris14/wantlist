"""Loopback-only actual-Worker browser test transport (no deployment/proxy product).

Chromium cannot use the cloud's egress proxy directly. Playwright intercepts the
approved staging origin and forwards requests through urllib. Browser URLs and
cookie origins remain the real HTTPS workers.dev origin. No credentials/logged
bodies/traces are persisted. This relay is a test harness, not a public service.
"""
import base64,json,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from .cloudflare import WORKER
ORIGIN='https://'+WORKER+'.andrewchris14.workers.dev'
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(b'Loopback staging test relay ready')
 def do_POST(self):
  try:
   body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   path=body['path']
   if not path.startswith('/') or path.startswith('//'):raise ValueError()
   headers={k:v for k,v in body['headers'].items() if k.lower() in ('cookie','origin','content-type')}
   headers['User-Agent']='Mozilla/5.0'
   req=urllib.request.Request(ORIGIN+path,headers=headers,method=body['method'],data=body.get('body').encode() if body.get('body') is not None else None)
   try:r=urllib.request.urlopen(req,timeout=45)
   except urllib.error.HTTPError as e:r=e
   with r:
    raw=r.read();response={'status':r.status,'headers':{k:v for k,v in r.headers.items() if k.lower() not in ('content-length','transfer-encoding','connection','content-encoding')},'body':base64.b64encode(raw).decode()}
   data=json.dumps(response).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError):return
  except Exception:
   try:
    self.send_response(502);self.end_headers();self.wfile.write(b'Upstream staging request failed; no sensitive details logged')
   except (BrokenPipeError,ConnectionResetError):pass
if __name__=='__main__':raise SystemExit('Remote browser relay disabled: use owner isolated local server; human-review staging is not a test target.')
