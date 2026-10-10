"""Probe-only transport: SQL and all application HTTP operations are forbidden."""
from .minimal_free_transport import LiveTransport
from .minimal_free_plan import StopReview

class ProbeTransport(LiveTransport):
    def request(self,url,method='GET',body=None,headers=None,kind='control'):
        self.response_limit=65536 if kind=='http' else 4_000_000
        # Serialize parent dispatch with supervisor cleanup: a late enable PUT
        # must never race restoration of the original unguarded application.
        directory=getattr(self,'operation_lock',None)
        if directory is not None and kind!='cleanup':
            from .minimal_free_runner import cleanup_lock
            with cleanup_lock(directory):return super().request(url,method,body,headers,kind)
        return super().request(url,method,body,headers,kind)

    def api(self,path,method='GET',*args,**kwargs):
        if method=='POST' and path.endswith('/query'):
            raise StopReview('PROBE_SQL_FORBIDDEN')
        return super().api(path,method,*args,**kwargs)

    def sql(self,*args,**kwargs):
        raise StopReview('PROBE_SQL_FORBIDDEN')

    def http(self,path='/public/index?after=',body=None,diagnostic=False):
        if path!='/public/index?after=' or body is not None or diagnostic or self.cookie:
            raise StopReview('PROBE_APPLICATION_REQUEST_FORBIDDEN')
        sample,data=super().http(path)
        if self.cookie:raise StopReview('PROBE_UNEXPECTED_COOKIE')
        return sample,data
