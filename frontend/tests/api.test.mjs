import assert from 'node:assert/strict';
import test from 'node:test';
import { postJson } from '../src/api.js';
import { beginFlow, isActiveFlow } from '../src/requestFlow.js';

test('non-2xx HTTP response is not treated as data', async t => {
  t.mock.method(globalThis, 'fetch', async () => ({
    ok: false, status: 502, json: async () => ({ detail: 'private provider error' }),
  }));
  await assert.rejects(
    postJson('/api/menu', { cuisine: 'Italian' }),
    error => error.message.includes('HTTP 502') && !error.message.includes('private'),
  );
});

test('successful response must contain valid object payload', async t => {
  t.mock.method(globalThis, 'fetch', async () => ({
    ok: true, status: 200, json: async () => ({ detail: 'unexpected' }),
  }));
  await assert.rejects(postJson('/api/menu', {}), /invalid response/);
});

test('non-JSON response is an actionable error', async t => {
  t.mock.method(globalThis, 'fetch', async () => ({
    ok: true, status: 200, json: async () => { throw new SyntaxError('html'); },
  }));
  await assert.rejects(postJson('/api/menu', {}), /invalid response/);
});

test('network failure produces a retryable message', async t => {
  t.mock.method(globalThis, 'fetch', async () => { throw new TypeError('Failed to fetch'); });
  await assert.rejects(postJson('/api/menu', {}), /Cannot reach the server/);
});

test('timed-out requests abort and return safe timeout errors', async t => {
  t.mock.method(globalThis, 'fetch', (_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener('abort', () => {
      reject(Object.assign(new Error('Aborted'), { name: 'AbortError' }));
    }, { once: true });
  }));
  await assert.rejects(postJson('/api/menu', {}, { timeoutMs: 5 }), /timed out/);
});

test('changing requests aborts older request generations', async () => {
  const first = beginFlow({ id: 0, controller: null }, 'Italian');
  const second = beginFlow(first, 'Mexican');
  assert.equal(first.controller.signal.aborted, true);
  assert.equal(isActiveFlow(second, first), false);
  assert.equal(isActiveFlow(second, second), true);
  second.controller.abort();
  assert.equal(isActiveFlow(second, second), false);
});

test('successful payload is returned with bearer authorization', async t => {
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.headers.Authorization, 'Bearer demo-token');
    return { ok: true, status: 200, json: async () => ({ menu_options: [] }) };
  });
  assert.deepEqual(await postJson('/api/menu', {}, { token: 'demo-token' }), { menu_options: [] });
});
