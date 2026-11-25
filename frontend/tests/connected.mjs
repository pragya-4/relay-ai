// Run explicitly against the deployed UI after confirming the provider's free tier.
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { chromium } from 'playwright';

const url = process.argv[2];
if (!url) throw new Error('Pass the frontend URL as the first argument');
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
try {
  const page = await browser.newPage();
  page.setDefaultTimeout(90000);
  const pageErrors = [];
  const apiOrigins = new Set();
  page.on('pageerror', error => pageErrors.push(error.name));
  page.on('request', request => {
    const target = new URL(request.url());
    if (['/chat', '/health'].includes(target.pathname)) apiOrigins.add(target.origin);
  });
  await page.goto(url);
  await page.getByText(/\d+ keys configured/).waitFor();
  const input = page.getByTestId('chat-input');
  const question = 'Give one word for sunlight. Verification ' + randomUUID();
  async function send(text) {
    await input.fill(text);
    const response = page.waitForResponse(r => new URL(r.url()).pathname === '/chat' && r.request().method() === 'POST');
    await page.getByTestId('send-button').click();
    const result = await response;
    return { status: result.status(), body: await result.json(), session: result.request().postDataJSON().session_id };
  }
  const live = await send(question);
  assert.equal(live.status, 200);
  assert.equal(live.body.metadata.resolution_source, 'LIVE_INFERENCE');
  await page.getByTestId('assistant-message').waitFor();
  assert.equal(await input.inputValue(), '');
  await page.reload();
  const hit = await send(question);
  assert.notEqual(hit.session, live.session);
  assert.equal(hit.body.reply, live.body.reply);
  assert.equal(hit.body.metadata.resolution_source, 'LLM_CACHE');
  assert.equal(hit.body.metadata.key_id, null);
  assert.equal(hit.body.metadata.fallback_attempts, 0);
  assert.ok(hit.body.metadata.latency_ms < live.body.metadata.latency_ms);
  const reply = page.getByTestId('assistant-message');
  await reply.waitFor();
  for (const [id, expected] of Object.entries({
    'meta-source': 'LLM_CACHE', 'meta-model': live.body.metadata.model,
    'meta-input-tokens': String(live.body.metadata.input_tokens),
    'meta-output-tokens': String(live.body.metadata.output_tokens),
    'meta-latency': hit.body.metadata.latency_ms + ' ms',
  })) assert.equal(await reply.getByTestId(id).innerText(), expected);
  assert.equal(hit.body.metadata.input_tokens, live.body.metadata.input_tokens);
  assert.equal(hit.body.metadata.output_tokens, live.body.metadata.output_tokens);
  await page.getByRole('combobox').selectOption('key_1=429');
  const limited = await send('Name one constellation.');
  assert.equal(limited.status, 200);
  assert.ok(limited.body.reply.trim());
  assert.equal(limited.body.metadata.key_id, 'key_2');
  assert.equal(limited.body.metadata.fallback_attempts, 1);
  await page.getByRole('combobox').selectOption('key_1=500');
  const fallback = await send('One short greeting.');
  assert.equal(fallback.status, 200);
  assert.equal(fallback.body.metadata.key_id, 'key_2');
  assert.equal(fallback.body.metadata.fallback_attempts, 1);
  await page.getByRole('combobox').selectOption('*=429');
  const failure = await send('Retry this message.');
  assert.equal(failure.status, 503);
  await page.getByRole('alert').waitFor();
  assert.equal(await input.inputValue(), 'Retry this message.');
  const marker = 'cedar-' + randomUUID().slice(0, 8);
  const recovery = await send('Remember this exact code for the next turn: ' + marker);
  assert.equal(recovery.status, 200);
  const recall = await send('What exact code did I ask you to remember?');
  assert.equal(recall.status, 200);
  assert.ok(recall.body.reply.includes(marker));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await page.getByTestId('system-prompt-input').waitFor();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  const mobile = await send('Say hello. Mobile check ' + randomUUID());
  assert.equal(mobile.status, 200);
  await page.getByTestId('meta-output-tokens').waitFor();
  assert.deepEqual(pageErrors, []);
  if (process.env.EXPECTED_API_ORIGIN) {
    assert.deepEqual([...apiOrigins], [process.env.EXPECTED_API_ORIGIN]);
  }
  console.log('PASS desktop and mobile: live, cache, tokens, latency, reload, 429/500 failover, 503, recovery and recall');
  console.log(JSON.stringify({ apiOrigins: [...apiOrigins], live: live.body.metadata, cache: hit.body.metadata }));
} finally {
  await browser.close();
}
