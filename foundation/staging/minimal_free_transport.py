"""Connected transport, constructed ONLY after explicit CLI admission.

Fixed disposable identity; inherited proxy/TLS; redirects forbidden; bounded reads
and socket/overall deadlines. No network operation happens at import time.
"""
import json, os, re, time, urllib.error, urllib.request, secrets
from datetime import timedelta
from email.parser import BytesParser
from email.policy import default
from .minimal_free_plan import WORKER, DATABASE, ORIGIN, StopReview, utc
from .minimal_free_release import digest

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise StopReview('REDIRECT_FORBIDDEN')

OPTIONS=('compatibility_date','compatibility_flags','limits','observability','logpush')
def options(settings):return {k:settings[k] for k in OPTIONS if settings.get(k) is not None}

class LiveTransport:
    def __init__(self,before):
        self.before=before;self.cookie=None;self.key=None
        self.account=os.environ['CLOUDFLARE_ACCOUNT_ID']
        if not re.fullmatch(r'[a-f0-9]{32}',self.account):raise StopReview('ACCOUNT_ID_INVALID')
        self.token=os.environ['CLOUDFLARE_API_TOKEN']
        self.opener=urllib.request.build_opener(NoRedirect())
        self.api_root='https://api.cloudflare.com/client/v4/accounts/'+self.account
    def request(self,url,method='GET',body=None,headers=None,kind='control'):
        self.before(kind)
        started=time.monotonic();req=urllib.request.Request(url,method=method,data=body,headers=headers or {})
        try:
            response=self.opener.open(req,timeout=10)
        except urllib.error.HTTPError as error:
            response=error
        except StopReview:raise
        except Exception:raise StopReview('NETWORK_RESULT_UNKNOWN') from None
        try:
            with response:
                chunks=[];size=0
                while True:
                    remaining=30-(time.monotonic()-started)
                    if remaining<=0:raise StopReview('HTTP_TOTAL_TIMEOUT')
                    sock=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
                    if sock is not None:sock.settimeout(min(10,remaining))
                    chunk=response.read1(65536)
                    if time.monotonic()-started>30:raise StopReview('HTTP_TOTAL_TIMEOUT')
                    if not chunk:break
                    size+=len(chunk)
                    if size>4_000_000:raise StopReview('RESPONSE_SIZE_STOP')
                    chunks.append(chunk)
                return response.status,dict(response.headers),b''.join(chunks)
        except StopReview:raise
        except Exception:raise StopReview('NETWORK_RESULT_UNKNOWN') from None
    def api(self,path,method='GET',payload=None,raw=None,content_type=None,kind='control',global_path=False):
        script='/workers/scripts/'+WORKER
        allowed={('/workers/domains','GET'),('/d1/database/'+DATABASE,'GET'),('/d1/database/'+DATABASE+'/query','POST'),
                 (script+'/settings','GET'),(script+'/subdomain','GET'),(script+'/subdomain','POST'),(script+'/content/v2','GET'),
                 (script,'PUT'),(script+'/secrets/FREE_HTTP_REVIEW_KEY','DELETE'),('/zones?per_page=50','GET'),('/graphql','POST')}
        zone_route=global_path and method=='GET' and re.fullmatch(r'/zones/[a-f0-9]{32}/workers/routes',path)
        if (path,method) not in allowed and not zone_route:raise StopReview('TRANSPORT_TARGET_FORBIDDEN')
        url=('https://api.cloudflare.com/client/v4' if global_path else self.api_root)+path
        headers={'Authorization':'Bearer '+self.token,'User-Agent':'Wantlist minimal Free review'}
        data=raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
        if data is not None:headers['Content-Type']=content_type or 'application/json'
        status,returned,body=self.request(url,method,data,headers,kind)
        if status==404 and path.endswith('/secrets/FREE_HTTP_REVIEW_KEY') and method=='DELETE':return {}
        if status!=200:raise StopReview('API_HTTP_'+str(status))
        if path.endswith('/content/v2'):return returned,body
        try:r=json.loads(body)
        except Exception:raise StopReview('API_RESULT_UNKNOWN') from None
        if path=='/graphql':
            if r.get('errors'):raise StopReview('ANALYTICS_UNAVAILABLE')
            return r
        if r.get('success') is not True:raise StopReview('API_RESULT_UNKNOWN')
        if isinstance(r.get('result'),list) and (r.get('result_info',{}).get('total_count',len(r['result']))>len(r['result']) or r.get('result_info',{}).get('total_pages',1)>1):raise StopReview('PAGINATED_INVENTORY_STOP')
        return r['result']
    def metadata(self):
        settings=self.api('/workers/scripts/'+WORKER+'/settings');endpoint=self.api('/workers/scripts/'+WORKER+'/subdomain')
        db=self.api('/d1/database/'+DATABASE);domains=self.api('/workers/domains')
        zones=self.api('/zones?per_page=50',global_path=True)
        # Some API responses put pagination outside result; never silently accept
        # an incomplete 50-zone page. More than two zones exceeds this canary cap.
        if not isinstance(zones,list) or len(zones)>2:raise StopReview('ZONE_INVENTORY_STOP')
        routes=[]
        for zone in zones:routes.extend(self.api('/zones/'+zone['id']+'/workers/routes',global_path=True))
        domains=domains if isinstance(domains,list) else domains.get('domains',[])
        return {'worker_name':WORKER,'database_id':db.get('uuid'),'database_name':db.get('name'),
                'bindings':settings.get('bindings',[]),'release_options':options(settings),'database_bytes':db.get('file_size'),'endpoint_enabled':endpoint.get('enabled'),'previews_enabled':endpoint.get('previews_enabled'),
                'custom_domains':[d['hostname'] for d in domains if d.get('service')==WORKER],
                'routes':[r.get('pattern') for r in routes if r.get('script')==WORKER],
                'explicit_cpu_limit_ms':settings.get('limits',{}).get('cpu_ms') if settings.get('limits') else None}
    def release_metadata(self,resources):
        settings=self.api('/workers/scripts/'+WORKER+'/settings');endpoint=self.api('/workers/scripts/'+WORKER+'/subdomain')
        return {**resources,'explicit_cpu_limit_ms':settings.get('limits',{}).get('cpu_ms') if settings.get('limits') else None,'bindings':settings.get('bindings',[]),'endpoint_enabled':endpoint.get('enabled'),'previews_enabled':endpoint.get('previews_enabled')}
    def modules(self,kind='control'):
        headers,body=self.api('/workers/scripts/'+WORKER+'/content/v2',kind=kind)
        content_type=next((v for k,v in headers.items() if k.lower()=='content-type'),'')
        if 'multipart/' not in content_type:raise StopReview('MODULE_SNAPSHOT_UNKNOWN')
        msg=BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
        modules={}
        for part in msg.walk():
            name=part.get_filename() or part.get_param('name',header='content-disposition')
            if name and name.endswith(('.js','.mjs')):
                if '/' in name or name in modules:raise StopReview('MODULE_SNAPSHOT_UNKNOWN')
                modules[name]=part.get_payload(decode=True).decode('utf-8')
        if 'worker.mjs' not in modules:raise StopReview('MODULE_SNAPSHOT_UNKNOWN')
        return modules
    def sql(self,sql,params=()):
        results=self.api('/d1/database/'+DATABASE+'/query','POST',{'sql':sql,'params':list(params)})
        if not isinstance(results,list) or not results or any(r.get('success') is not True for r in results):raise StopReview('D1_RESULT_UNKNOWN')
        return results
    def publish(self,modules,main,bindings,kind='control',release_options=None):
        dbs=[b for b in bindings if b.get('type')=='d1']
        if len(dbs)!=1 or dbs[0].get('name')!='DB' or dbs[0].get('id')!=DATABASE:raise StopReview('RESTORE_BINDING_MISMATCH')
        boundary='----wantlist'+secrets.token_hex(12)
        metadata={**(release_options or {'compatibility_date':'2026-10-01'}),'main_module':main,'bindings':bindings}
        pieces=[]
        for name,filename,body,mime in [('metadata',None,json.dumps(metadata),'application/json')]+[(k,k,v,'application/javascript+module') for k,v in modules.items()]:
            disposition='form-data; name="'+name+'"'+('; filename="'+filename+'"' if filename else '')
            pieces.append(('--'+boundary+'\r\nContent-Disposition: '+disposition+'\r\nContent-Type: '+mime+'\r\n\r\n'+body+'\r\n').encode())
        raw=b''.join(pieces)+('--'+boundary+'--\r\n').encode()
        return self.api('/workers/scripts/'+WORKER,'PUT',raw=raw,content_type='multipart/form-data; boundary='+boundary,kind=kind)
    def endpoint(self,enabled,kind='control'):
        return self.api('/workers/scripts/'+WORKER+'/subdomain','POST',{'enabled':enabled,'previews_enabled':False},kind=kind)
    def disabled(self):
        r=self.api('/workers/scripts/'+WORKER+'/subdomain',kind='cleanup')
        return r.get('enabled') is False and r.get('previews_enabled') is False
    def remove_key(self):return self.api('/workers/scripts/'+WORKER+'/secrets/FREE_HTTP_REVIEW_KEY','DELETE',kind='cleanup')
    def restored(self,original):
        settings=self.api('/workers/scripts/'+WORKER+'/settings',kind='cleanup')
        names={b.get('name') for b in settings.get('bindings',[])}
        def safe(bindings):return sorted(({**b,'type':'inherit'} if b.get('type')=='secret_text' else b for b in bindings),key=lambda b:b['name'])
        return options(settings)==original['options'] and safe(settings.get('bindings',[]))==safe(original['bindings']) and self.disabled() and not names.intersection({'MINIMAL_FREE_REVIEW','MINIMAL_FREE_REVIEW_UNTIL','FREE_HTTP_REVIEW_KEY'}) and self.modules(kind='cleanup')==original['modules']
    def http(self,path,body=None,diagnostic=False):
        if path not in ('/public/index?after=','/test/free-review-login','/owner/record?id=synthetic-3c5-1-0000','/action'):raise StopReview('HTTP_TARGET_FORBIDDEN')
        headers={'X-Free-Review-Key':self.key,'X-Staging-Metrics':'on' if diagnostic else 'off','User-Agent':'Wantlist minimal Free review'}
        if self.cookie:headers['Cookie']=self.cookie
        if body is not None:headers.update({'Content-Type':'application/json','Origin':ORIGIN})
        status,returned,raw=self.request(ORIGIN+path,'POST' if body is not None else 'GET',json.dumps(body).encode() if body is not None else None,headers,'http')
        lower={k.lower():v for k,v in returned.items()}
        if 'set-cookie' in lower:self.cookie=lower['set-cookie'].split(';')[0]
        try:data=json.loads(raw)
        except Exception:data=None
        safe={'status':status,'response_bytes':len(raw),'response_sha256':digest(raw),
              'headers':{k:lower.get(k) for k in ('cf-ray','server','content-type')},'diagnostic':diagnostic}
        if path.startswith('/public/index?'):safe['public_index_url']=ORIGIN+path
        if diagnostic:
            safe['d1_complete']=lower.get('x-staging-d1-complete')=='true'
            try:safe.update(rows_read=int(lower['x-staging-d1-reads']),rows_written=int(lower['x-staging-d1-writes']))
            except (KeyError,ValueError):safe['d1_complete']=False
        return safe,data
    def analytics(self,sample):
        a=utc(sample['started']).replace(second=0,microsecond=0);b=utc(sample['ended']).replace(second=0,microsecond=0)+timedelta(minutes=1)
        query='query($account:String!){viewer{accounts(filter:{accountTag:$account}){workersInvocationsAdaptive(limit:1000,filter:{scriptName:'+json.dumps(WORKER)+',datetime_geq:'+json.dumps(a.isoformat())+',datetime_leq:'+json.dumps(b.isoformat())+'}){dimensions{datetime status} quantiles{cpuTimeP50 cpuTimeP99} sum{requests errors}}}}}'
        r=self.api('/graphql','POST',{'query':query,'variables':{'account':self.account}},global_path=True)
        try:return r['data']['viewer']['accounts'][0]['workersInvocationsAdaptive']
        except Exception:raise StopReview('ANALYTICS_UNAVAILABLE') from None
