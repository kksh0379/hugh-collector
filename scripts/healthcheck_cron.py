"""Render daily job: signed wake-up, start and wait for persisted results."""
import json
import os
import time
import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def main():
    origin=os.environ.get('HEALTHCHECK_ORIGIN','https://hscope.onrender.com').rstrip('/')
    key=Ed25519PrivateKey.from_private_bytes(bytes.fromhex(os.environ['HEALTHCHECK_SIGNING_KEY']))
    client=requests.Session()
    def call(data):
        for attempt in range(6):
            body=json.dumps(data,separators=(',',':')).encode()
            timestamp=str(int(time.time()))
            headers={'Content-Type':'application/json','X-Health-Timestamp':timestamp,
                'X-Health-Signature':key.sign(timestamp.encode()+b'\n'+body).hex()}
            try:
                response=client.post(origin+'/api/admin/healthchecks/cron',data=body,headers=headers,timeout=(10,60))
                if response.status_code in (200,202): return response.json()
                if response.status_code in (401,403): raise RuntimeError('Health-check signature rejected')
            except requests.RequestException:
                pass
            if attempt<5: time.sleep(10)
        raise RuntimeError('Health-check service unavailable after retries')
    started=call({'action':'start'})
    run_id=started['id']
    print('Daily health check accepted: '+run_id,flush=True)
    deadline=time.monotonic()+1500
    while time.monotonic()<deadline:
        state=call({'action':'status','id':run_id}).get('report')
        if not state: raise RuntimeError('Health-check result missing')
        if state['status']!='running':
            print(json.dumps({'status':state['status'],'duration_ms':state['duration_ms'],
                'counts':state.get('counts',{}),'id':run_id},ensure_ascii=False),flush=True)
            return 1 if state['status'] in ('failed','interrupted') else 0
        time.sleep(10)
    raise RuntimeError('Health check exceeded 25-minute execution limit')


if __name__=='__main__': raise SystemExit(main())
