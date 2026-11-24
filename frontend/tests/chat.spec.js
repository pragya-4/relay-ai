import { test, expect } from '@playwright/test';

const metadata = {
  resolution_source: 'LIVE_INFERENCE',
  model: 'gemini/gemini-3.5-flash-lite',
  latency_ms: 123,
  input_tokens: 17,
  output_tokens: 4,
  key_id: 'key_1',
  fallback_attempts: 0,
};

async function mockHealth(page) {
  await page.route('**/health', route => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ status: 'ok', keys_configured: 2, cache_enabled: true }),
  }));
}

test('sends a message, clears input, and renders each response metadata field', async ({ page }) => {
  await mockHealth(page);
  await page.route('**/chat', async route => {
    const body = route.request().postDataJSON();
    expect(body.message).toBe('Hello Relay');
    expect(body.session_id).toBeTruthy();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ session_id: body.session_id, reply: 'Hello there.', metadata }),
    });
  });

  await page.goto('/');
  const input = page.getByTestId('chat-input');
  await input.fill('Hello Relay');
  await page.getByTestId('send-button').click();

  await expect(input).toHaveValue('');
  const reply = page.getByTestId('assistant-message');
  await expect(reply).toContainText('Hello there.');
  await expect(reply.getByTestId('meta-source')).toHaveText('LIVE_INFERENCE');
  await expect(reply.getByTestId('meta-model')).toHaveText(metadata.model);
  await expect(reply.getByTestId('meta-latency')).toHaveText('123 ms');
  await expect(reply.getByTestId('meta-input-tokens')).toHaveText('17');
  await expect(reply.getByTestId('meta-output-tokens')).toHaveText('4');
});

test('shows a readable provider error and retries the same message', async ({ page }) => {
  await mockHealth(page);
  let attempts = 0;
  await page.route('**/chat', async route => {
    attempts += 1;
    if (attempts === 1) {
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'all providers unavailable' }) });
      return;
    }
    const body = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ session_id: body.session_id, reply: 'Recovered.', metadata }),
    });
  });

  await page.goto('/');
  const input = page.getByTestId('chat-input');
  await input.fill('Retry me');
  await page.getByTestId('send-button').click();
  await expect(page.getByRole('alert')).toContainText('all providers unavailable');
  await expect(input).toHaveValue('Retry me');
  await page.getByTestId('send-button').click();
  await expect(page.getByTestId('assistant-message')).toContainText('Recovered.');
  expect(attempts).toBe(2);
});

test('starts a fresh session after a page reload', async ({ page }) => {
  await mockHealth(page);
  const sessions = [];
  await page.route('**/chat', async route => {
    const body = route.request().postDataJSON();
    sessions.push(body.session_id);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ session_id: body.session_id, reply: 'OK', metadata }),
    });
  });

  await page.goto('/');
  await page.getByTestId('chat-input').fill('First');
  await page.getByTestId('send-button').click();
  await expect(page.getByTestId('assistant-message')).toBeVisible();
  await page.reload();
  await page.getByTestId('chat-input').fill('Second');
  await page.getByTestId('send-button').click();
  await expect(page.getByTestId('assistant-message')).toBeVisible();
  expect(sessions).toHaveLength(2);
  expect(sessions[0]).not.toBe(sessions[1]);
});

test('sends a failure simulation header for only one request', async ({ page }) => {
  await mockHealth(page);
  const headers = [];
  await page.route('**/chat', async route => {
    headers.push(route.request().headers()['x-simulate-failure'] || null);
    const body = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ session_id: body.session_id, reply: 'OK', metadata }),
    });
  });

  await page.goto('/');
  await page.getByRole('combobox').selectOption('key_1=429');
  await page.getByTestId('chat-input').fill('Simulated request');
  await page.getByTestId('send-button').click();
  await expect(page.getByTestId('assistant-message')).toBeVisible();
  await expect(page.getByRole('combobox')).toHaveValue('');
  await page.getByTestId('chat-input').fill('Normal request');
  await page.getByTestId('send-button').click();
  await expect(page.getByTestId('assistant-message')).toHaveCount(2);

  expect(headers).toEqual(['key_1=429', null]);
});
