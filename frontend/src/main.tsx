import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

type ResolutionSource = 'LIVE_INFERENCE' | 'LLM_CACHE';
type Metadata = {
  resolution_source: ResolutionSource;
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  key_id: string | null;
  fallback_attempts: number;
};
type Message =
  | { role: 'user'; content: string }
  | { role: 'assistant'; content: string; metadata: Metadata };
type ChatResponse = { session_id: string; reply: string; metadata: Metadata };

const base = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '');
const newId = (): string => globalThis.crypto?.randomUUID?.() || `s-${Date.now()}-${Math.random().toString(36).slice(2)}`;

function App() {
  const [sid, setSid] = useState<string>(newId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [prompt, setPrompt] = useState('');
  const [failure, setFailure] = useState('');
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState('Checking');
  const [error, setError] = useState('');
  const bottom = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let active = true;
    const check = (): void => {
      fetch(`${base}/health`)
        .then(response => {
          if (!response.ok) throw new Error('Backend unavailable');
          return response.json() as Promise<{ keys_configured: number }>;
        })
        .then(data => { if (active) setHealth(`${data.keys_configured} keys configured`); })
        .catch(() => { if (active) setHealth('Backend unavailable'); });
    };
    check();
    const timer = window.setInterval(check, 30_000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, busy, error]);

  function reset(): void {
    if (busy) return;
    setSid(newId());
    setPrompt('');
    setMessages([]);
    setError('');
    setInput('');
    setFailure('');
  }

  async function send(event?: FormEvent<HTMLFormElement>): Promise<void> {
    event?.preventDefault();
    const message = input.trim();
    if (!message || busy) return;
    const simulation = failure;
    setBusy(true);
    setInput('');
    setFailure('');
    setError('');
    setMessages(current => [...current, { role: 'user', content: message }]);
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (simulation) headers['X-Simulate-Failure'] = simulation;
      const body: { session_id: string; message: string; system_prompt?: string } = { session_id: sid, message };
      if (prompt.trim()) body.system_prompt = prompt;
      const response = await fetch(`${base}/chat`, {
        method: 'POST', headers, body: JSON.stringify(body), signal: AbortSignal.timeout(90_000),
      });
      const data = await response.json() as ChatResponse | { detail?: unknown };
      if (!response.ok) {
        const detail = 'detail' in data && typeof data.detail === 'string' ? data.detail : 'Invalid request. Check your message.';
        throw new Error(detail);
      }
      if (!('reply' in data) || !data.reply.trim()) throw new Error('The backend returned an empty reply. Please retry.');
      setMessages(current => [...current, { role: 'assistant', content: data.reply, metadata: data.metadata }]);
    } catch (caught: unknown) {
      setMessages(current => current.slice(0, -1));
      const reason = caught instanceof Error ? caught.message : 'Unexpected error';
      setError(reason === 'Failed to fetch' ? 'Cannot reach the backend. Please retry.' : reason);
      setInput(message);
    } finally {
      setBusy(false);
    }
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  const replies = messages.filter((message): message is Extract<Message, { role: 'assistant' }> => message.role === 'assistant');
  const hits = replies.filter(message => message.metadata.resolution_source === 'LLM_CACHE').length;

  return <div className="shell">
    <aside>
      <div className="brand"><div className="logo">R<span>↗</span></div><div>relay<span className="accent">.</span><small>LLM GATEWAY / 01</small></div></div>
      <button className="new" onClick={reset} disabled={busy}>＋ New conversation</button>
      <div className="side-section">
        <label>SESSION</label><code>{sid.slice(0, 18)}…</code>
        <label>SYSTEM INSTRUCTION</label>
        <textarea data-testid="system-prompt-input" value={prompt} onChange={event => setPrompt(event.target.value)} placeholder="Default assistant behavior" disabled={busy} />
        <label>RESILIENCE LAB</label>
        <select value={failure} onChange={event => setFailure(event.target.value)} disabled={busy}>
          <option value="">Normal inference</option>
          <option value="key_1=429">Key 1 · rate limit</option>
          <option value="key_1=500">Key 1 · server error</option>
          <option value="*=429">All keys unavailable</option>
        </select>
        <p>Simulate a provider failure for the next request. Simulation bypasses cached reads.</p>
      </div>
      <div className="side-section stats">
        <label>SESSION TELEMETRY</label>
        <div><span>Responses</span><b>{replies.length}</b></div>
        <div><span>Cache hits</span><b>{hits}</b></div>
        <div><span>Failovers</span><b>{replies.filter(message => message.metadata.fallback_attempts > 0).length}</b></div>
      </div>
      <div className="foot">FASTAPI · LITELLM · SQLITE</div>
    </aside>
    <main>
      <header>
        <div><span className="eyebrow">INTELLIGENCE INFRASTRUCTURE</span><h1>Conversation workspace</h1></div>
        <span className="status"><i className={health.includes('configured') ? 'online' : ''} />{health}</span>
      </header>
      <section className="thread" aria-live="polite">
        {!messages.length && !busy && <div className="welcome">
          <div className="mark">↗</div><span className="eyebrow">BUILT FOR RESILIENCE</span>
          <h2>Ask anything.<br />Stay connected.</h2>
          <p>Context-aware conversations with transparent inference, automatic key failover and intelligent response caching.</p>
          <div className="suggestions">{['What is the capital of France?', 'Explain API rate limiting in simple terms.', 'What is a database transaction?'].map(suggestion =>
            <button key={suggestion} onClick={() => setInput(suggestion)}>{suggestion} <span>↗</span></button>,
          )}</div>
        </div>}
        {messages.map((message, index) => message.role === 'user'
          ? <div className="user" key={index}>{message.content}</div>
          : <article className="assistant" data-testid="assistant-message" key={index}>
            <div className="reply-head"><span className="mini">R</span> Relay AI</div>
            <div className="reply">{message.content}</div>
            <div className="meta">
              <div className="source" data-testid="meta-source">{message.metadata.resolution_source}</div>
              <div data-testid="meta-model">{message.metadata.model}</div>
              <div><small>LATENCY</small><b data-testid="meta-latency">{message.metadata.latency_ms} ms</b></div>
              <div><small>INPUT</small><b data-testid="meta-input-tokens">{message.metadata.input_tokens}</b></div>
              <div><small>OUTPUT</small><b data-testid="meta-output-tokens">{message.metadata.output_tokens}</b></div>
              <div><small>PROVIDER</small><b>{message.metadata.key_id || 'Cache'}</b></div>
              <div><small>FALLBACKS</small><b>{message.metadata.fallback_attempts}</b></div>
            </div>
          </article>)}
        {busy && <div className="pending">Resolving response…</div>}
        {error && <div className="error" role="alert">{error} — edit or retry below.</div>}
        <div ref={bottom} />
      </section>
      <form onSubmit={event => { void send(event); }}>
        <div className="composer">
          <textarea data-testid="chat-input" aria-label="Message" placeholder="Send a message to Relay…" value={input} maxLength={4000} onChange={event => setInput(event.target.value)} onKeyDown={handleInputKeyDown} />
          <button data-testid="send-button" type="submit" disabled={busy || !input.trim()} aria-label="Send message">↑</button>
        </div>
        <div className="hint">Enter to send · Shift + Enter for a new line <span>{input.length}/4000</span></div>
      </form>
    </main>
  </div>;
}

createRoot(document.getElementById('root')!).render(<App />);
