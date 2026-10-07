"""Technical recovery person's temporary staging-only preview switch.
Never changes the production site, billing plans, baseline or import state.
"""
import argparse
from .cloudflare import WORKER,PROBE,endpoint
from .runner import deploy_staging,Client
if __name__=='__main__':
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
 g.add_argument('--enable',action='store_true');g.add_argument('--disable',action='store_true');a=p.parse_args()
 if a.enable:
  v=deploy_staging(editor=True,instrumented=False);Client().wait_ready(v)
  print('Temporary STAGING ONLY preview: https://'+WORKER+'.andrewchris14.workers.dev')
  print('Use the disposable staging access code through the login form. Disable again after review.')
 else:
  endpoint(WORKER,False);endpoint(PROBE,False);print('Both staging endpoints and previews disabled')
