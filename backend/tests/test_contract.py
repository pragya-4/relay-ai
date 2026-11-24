import pytest
from fastapi.testclient import TestClient
from main import create_app, Unavailable

class ProviderDouble:
    """Deterministic test double; no real inference or LiteLLM verification."""
    keys=['test1','test2']
    def __init__(self): self.cache={}; self.last=None
    def respond(self,messages,failures):
        import json
        self.last=messages
        key=json.dumps(messages,sort_keys=True)
        if not failures and key in self.cache: return self.cache[key],None,0,True
        for i in range(1,3):
            if '*' in failures or f'key_{i}' in failures: continue
            data=('answer: '+messages[-1]['content'],'test/model',sum(len(x['content'].split()) for x in messages),3)
            self.cache[key]=data
            return data,f'key_{i}',i-1,False
        raise Unavailable()
@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_FAILURE_SIMULATION','true')
    p=ProviderDouble(); app=create_app(p,str(tmp_path/'test.db'))
    with TestClient(app) as c: yield c,p

def chat(c,s='one',m='hello',header=None,**kw):
    return c.post('/chat',json=dict(session_id=s,message=m,**kw),headers={'X-Simulate-Failure':header} if header else {})
def test_health(setup):
    c,_=setup; assert c.get('/health').json()=={'status':'ok','keys_configured':2,'cache_enabled':True}
@pytest.mark.parametrize('payload',[{}, {'session_id':'x','message':''},{'session_id':'x','message':'  '},{'session_id':'','message':'hello'},{'session_id':'x'*129,'message':'hi'},{'session_id':'x','message':'a'*4001},{'session_id':1,'message':'hi'},{'session_id':'x','message':None}])
def test_validation(setup,payload):
    c,_=setup; r=c.post('/chat',json=payload); assert r.status_code==422 and 'detail' in r.json()
def test_malformed(setup):
    c,_=setup; assert c.post('/chat',content='{',headers={'Content-Type':'application/json'}).status_code==422
@pytest.mark.parametrize('header',['key_1=429','key_1=500','key_1=502','key_1=503'])
def test_fallback_contract(setup,header):
    c,_=setup; r=chat(c,header=header); assert r.status_code==200; m=r.json()['metadata']; assert (m['key_id'],m['fallback_attempts'],m['resolution_source'])==('key_2',1,'LIVE_INFERENCE')
@pytest.mark.parametrize('header',['*=429','key_1=429,key_2=500'])
def test_all_fail(setup,header):
    c,_=setup; r=chat(c,header=header); assert r.status_code==503 and r.json()=={'detail':'all providers unavailable'}; assert c.get('/sessions/one/messages').status_code==404
@pytest.mark.parametrize('header',['key_3=429','key_1=401','broken'])
def test_bad_header(setup,header):
    c,_=setup; assert chat(c,header=header).status_code==422

def test_cache_contract(setup):
    c,_=setup; a=chat(c).json(); b=chat(c,s='two').json(); assert a['reply']==b['reply']; assert b['metadata']['resolution_source']=='LLM_CACHE'; assert b['metadata']['key_id'] is None; assert a['metadata']['input_tokens']==b['metadata']['input_tokens']
def test_different_message(setup):
    c,_=setup; chat(c); assert chat(c,s='two',m='different').json()['metadata']['resolution_source']=='LIVE_INFERENCE'
def test_context(setup):
    c,p=setup; chat(c,m='first'); chat(c,m='second'); assert [m['content'] for m in p.last[1:]]==['first','answer: first','second']
def test_history(setup):
    c,_=setup; a=chat(c).json(); rows=c.get('/sessions/one/messages').json()['messages']; assert rows==[{'role':'user','content':'hello'},{'role':'assistant','content':a['reply'],'metadata':a['metadata']}]
def test_isolation(setup):
    c,p=setup; chat(c,m='private'); chat(c,s='two'); assert len(p.last)==2

def test_prompt_persistence(setup):
    c,p=setup; chat(c,system_prompt='Be terse'); chat(c,m='next'); assert p.last[0]['content']=='Be terse'
def test_different_prompt(setup):
    c,_=setup; chat(c,system_prompt='a'); assert chat(c,s='two',system_prompt='b').json()['metadata']['resolution_source']=='LIVE_INFERENCE'
def test_failure_preserves_history(setup):
    c,_=setup; chat(c); before=c.get('/sessions/one/messages').json(); chat(c,header='*=429'); assert c.get('/sessions/one/messages').json()==before

def test_unknown(setup):
    c,_=setup; assert c.get('/sessions/unknown/messages').json()=={'detail':'session not found'}
def test_simulation_bypasses_cache(setup):
    c,_=setup; chat(c); assert chat(c,s='two',header='*=429').status_code==503

def test_trim(setup):
    c,_=setup; assert chat(c,m='  hello  ').json()['reply']=='answer: hello'
def test_restart(tmp_path):
    path=str(tmp_path/'persistent.db')
    with TestClient(create_app(ProviderDouble(),path)) as c: chat(c)
    with TestClient(create_app(ProviderDouble(),path)) as c: assert len(c.get('/sessions/one/messages').json()['messages'])==2

def test_switch_disabled(tmp_path,monkeypatch):
    monkeypatch.setenv('ENABLE_FAILURE_SIMULATION','false')
    with TestClient(create_app(ProviderDouble(),str(tmp_path/'off.db'))) as c: assert chat(c,header='*=429').status_code==200
