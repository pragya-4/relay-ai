import os, sqlite3, json, time, threading, logging
from contextlib import asynccontextmanager, closing
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

log = logging.getLogger('relay')
DEFAULT_PROMPT = 'You are a helpful, concise assistant.'

class Chat(BaseModel):
    session_id: str = Field(min_length=1,max_length=128)
    message: str = Field(min_length=1,max_length=4000)
    system_prompt: str | None = Field(default=None,max_length=8000)
    @field_validator('session_id','message',mode='before')
    @classmethod
    def trim(cls,v):
        return v.strip() if isinstance(v,str) else v

class Unavailable(Exception): pass

class Gateway:
    def __init__(self, keys, model):
        from litellm import Router
        from litellm.caching.caching import Cache
        self.cache = Cache(type="local", max_messages=None)
        self.keys = keys
        self.model = model
        # Each alias selects exactly one credential, including during simulation.
        deployments = [
            {
                "model_name": f"key_{index}",
                "litellm_params": {"model": model, "api_key": key, "timeout": 25},
                "model_info": {"id": f"relay-{index}"},
            }
            for index, key in enumerate(keys, start=1)
        ]
        self.router = Router(model_list=deployments, num_retries=0, timeout=25,
                             disable_cooldowns=True, cache_responses=False)
        self.locks = [threading.RLock() for _ in range(64)]

    def respond(self, messages, failures):
        args = dict(model=self.model, messages=messages)
        lock = self.locks[hash(json.dumps(args, sort_keys=True)) % len(self.locks)]
        with lock:
            if not failures:
                cached = self.cache.get_cache(**args)
                if cached is not None:
                    return self.unpack(cached), None, 0, True

            for attempts in range(len(self.keys)):
                key_id = f"key_{attempts + 1}"
                if "*" in failures or key_id in failures:
                    continue
                try:
                    result = self.router.completion(
                        model=key_id, messages=messages,
                        caching=False, max_retries=0,
                    )
                    data = result.model_dump()
                    parsed = self.unpack(data)
                except Exception as exc:
                    log.warning("provider %s failed (%s)", key_id, type(exc).__name__)
                    continue
                self.cache.add_cache(data, **args)
                return parsed, key_id, attempts, False
        raise Unavailable()

    def unpack(self, data):
        reply = data["choices"][0]["message"]["content"]
        usage = data["usage"]
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("empty completion")
        return reply, self.model, int(usage["prompt_tokens"]), int(usage["completion_tokens"])

def create_app(gateway=None, db_path=None):
    keys=list(dict.fromkeys(k.strip() for k in os.getenv('LLM_API_KEYS','').split(',')
                           if k.strip() and not k.strip().startswith('YOUR_')))
    model=os.getenv('LLM_MODEL','gemini/gemini-3.5-flash-lite')
    path=db_path or os.getenv('DATABASE_URL','sqlite:///./app.db').removeprefix('sqlite:///')
    simulate=os.getenv('ENABLE_FAILURE_SIMULATION','false').lower()=='true'
    locks=[threading.Lock() for _ in range(64)]
    def connect():
        c=sqlite3.connect(path,timeout=15); c.row_factory=sqlite3.Row; return c
    @asynccontextmanager
    async def lifespan(app):
        os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
        with closing(connect()) as c, c:
            c.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, prompt TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, metadata TEXT, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_messages ON messages(session_id,id);''')
        app.state.gateway=gateway or Gateway(keys,model)
        yield
    app=FastAPI(title='Relay AI',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in os.getenv('ALLOWED_ORIGINS','http://localhost:3000').split(',')],allow_methods=['GET','POST'],allow_headers=['Content-Type','X-Simulate-Failure'])
    @app.exception_handler(Exception)
    async def unexpected(request,exc):
        log.error('internal failure: %s',type(exc).__name__)
        return JSONResponse(status_code=500,content={'detail':'internal server error'})
    @app.get('/health')
    def health():
        with closing(connect()) as c: c.execute('SELECT 1').fetchone()
        n=len(app.state.gateway.keys)
        if len(set(app.state.gateway.keys)) < 2: raise HTTPException(503,'at least two provider keys required')
        return {'status':'ok','keys_configured':n,'cache_enabled':True}
    @app.get('/sessions/{session_id}/messages')
    def history(session_id:str):
        with closing(connect()) as c:
            if not c.execute('SELECT 1 FROM sessions WHERE id=?',(session_id,)).fetchone(): raise HTTPException(404,'session not found')
            rows=c.execute('SELECT role,content,metadata FROM messages WHERE session_id=? ORDER BY id',(session_id,)).fetchall()
        return {'session_id':session_id,'messages':[dict(role=r['role'],content=r['content'],**({'metadata':json.loads(r['metadata'])} if r['metadata'] else {})) for r in rows]}
    @app.post('/chat')
    def chat(body:Chat,x_simulate_failure:str|None=Header(default=None)):
        start=time.perf_counter(); failures={}
        if simulate and x_simulate_failure:
            for pair in x_simulate_failure.split(','):
                k,sep,v=pair.strip().partition('=')
                if not sep or (k!='*' and k not in [f'key_{i+1}' for i in range(len(app.state.gateway.keys))]) or v not in ('429','500','502','503'): raise HTTPException(422,'invalid failure simulation')
                failures[k]=int(v)
        with locks[hash(body.session_id)%len(locks)]:
            with closing(connect()) as c:
                session=c.execute('SELECT prompt FROM sessions WHERE id=?',(body.session_id,)).fetchone()
                rows=c.execute('SELECT role,content FROM messages WHERE session_id=? ORDER BY id',(body.session_id,)).fetchall()
            prompt=body.system_prompt if body.system_prompt is not None else (session['prompt'] if session else DEFAULT_PROMPT)
            messages=[{'role':'system','content':prompt}]+[dict(r) for r in rows]+[{'role':'user','content':body.message}]
            try: (reply,model_used,inp,out),kid,attempts,hit=app.state.gateway.respond(messages,failures)
            except Unavailable: raise HTTPException(503,'all providers unavailable')
            metadata=dict(resolution_source='LLM_CACHE' if hit else 'LIVE_INFERENCE',model=model_used,latency_ms=round((time.perf_counter()-start)*1000),input_tokens=inp,output_tokens=out,key_id=kid,fallback_attempts=attempts)
            now=datetime.now(timezone.utc).isoformat()
            with closing(connect()) as c,c:
                c.execute('INSERT INTO sessions(id,prompt) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET prompt=excluded.prompt',(body.session_id,prompt))
                c.executemany('INSERT INTO messages(session_id,role,content,metadata,created_at) VALUES(?,?,?,?,?)',[(body.session_id,'user',body.message,None,now),(body.session_id,'assistant',reply,json.dumps(metadata),now)])
            return dict(session_id=body.session_id,reply=reply,metadata=metadata)
    return app

app=create_app()
