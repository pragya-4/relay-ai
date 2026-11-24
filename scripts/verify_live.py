"""Run against real deployed backend: python scripts/verify_live.py https://..."""
import json, sys, uuid, urllib.request, urllib.error
base=sys.argv[1].rstrip('/')
def call(path,body=None,header=None):
    h={'Content-Type':'application/json'}
    if header: h['X-Simulate-Failure']=header
    req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
    try:
        with urllib.request.urlopen(req,timeout=120) as r: return r.status,json.load(r)
    except urllib.error.HTTPError as e: return e.code,json.load(e)
def check(ok,detail):
    if not ok: raise AssertionError(detail)
    print('PASS',detail)
def send(s,m,h=None):return call('/chat',{'session_id':s,'message':m},h)
run=uuid.uuid4().hex[:10]; a,b,c,d,e,f,g=[run+x for x in 'abcdefg']; prompt='Reply briefly: What is the capital of France? Verification '+run
status,health=call('/health'); check(status==200 and health['keys_configured']>=2 and health['cache_enabled'],'health')
s,x=send(a,prompt); check(s==200 and x['metadata']['resolution_source']=='LIVE_INFERENCE','live inference')
s,y=send(b,prompt); check(s==200 and y['reply']==x['reply'] and y['metadata']['resolution_source']=='LLM_CACHE' and y['metadata']['key_id'] is None,'identical cache hit')
check(y['metadata']['latency_ms']<x['metadata']['latency_ms'],'cache latency lower')
check(all(y['metadata'][k]==x['metadata'][k] for k in ['input_tokens','output_tokens']),'cached token usage')
s,z=send(c,'Say hello '+run,'key_1=429'); check(s==200 and z['metadata']['key_id']=='key_2' and z['metadata']['fallback_attempts']==1,'429 failover')
s,z=send(d,'Say goodbye '+run,'key_1=500'); check(s==200 and z['metadata']['key_id']=='key_2','500 failover')
s,z=send(f,'Key 1 independent verification '+run,'key_2=429'); check(s==200 and z['metadata']['key_id']=='key_1' and z['metadata']['fallback_attempts']==0,'key 1 independently generates')
s,z=send(g,'Key 2 independent verification '+run,'key_1=429'); check(s==200 and z['metadata']['key_id']=='key_2' and z['metadata']['fallback_attempts']==1,'key 2 independently generates')
s,z=send(e,'test','*=429'); check(s==503 and z=={'detail':'all providers unavailable'},'all providers fail')
check(call('/sessions/'+e+'/messages')[0]==404,'failed request not persisted')
check(call('/sessions/'+a+'/messages')[1]['messages'][1]['content']==x['reply'],'stored history')
check(send(a,'   ')[0]==422,'validation')
print('Live inference:',x['metadata'],'\nCache:',y['metadata'])

marker = 'indigo-' + run
s, remembered = send(a, 'Remember this exact code for my next message: '+marker)
check(s == 200 and remembered['metadata']['resolution_source'] == 'LIVE_INFERENCE', 'new turn uses inference')
s, recalled = send(a, 'What exact code did I ask you to remember?')
check(s == 200 and marker in recalled['reply'], 'multiturn recall')
for response in (x, y, recalled):
    meta = response['metadata']
    check(all(type(meta[k]) is int and meta[k] > 0 for k in ('input_tokens','output_tokens')), 'positive per-request tokens')
check(y['metadata']['fallback_attempts'] == 0, 'cache hit skips fallback')
before = call('/sessions/'+a+'/messages')[1]['messages']
check([v['role'] for v in before] == ['user','assistant'] * 3, 'ordered messages without system prompt')
check(send(a, 'should fail', '*=429')[0] == 503 and send(a, 'x'*4001)[0] == 422, 'errors in existing session')
check(call('/sessions/'+a+'/messages')[1]['messages'] == before, 'failed requests preserve prior history')
