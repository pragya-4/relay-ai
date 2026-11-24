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
  console.log('PASS connected browser: live, cache, lower cache latency, per-reply metadata, reload, failover and readable 503');
} finally {
  await browser.close();
}
