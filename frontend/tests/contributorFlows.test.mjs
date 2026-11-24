import assert from 'node:assert/strict';
import test from 'node:test';
import { postJson } from '../src/api.js';
import { beginFlow, isActiveFlow } from '../src/requestFlow.js';
import { recipeOrigin } from '../src/recipeUi.js';

test('menu selection sends cuisine and dietary restrictions to the API', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/menu');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), {
      cuisine: 'Italian', dietary_restrictions: ['vegan'],
    });
    assert.equal(options.headers.Authorization, undefined);
    return { ok: true, status: 200, json: async () => ({ menu_options: [] }) };
  });
  const result = await postJson('/api/menu', {
    cuisine: 'Italian', dietary_restrictions: ['vegan'],
  });
  assert.deepEqual(result, { menu_options: [] });
});

test('dashboard history is scoped to an authenticated request', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/menu-dashboard');
    assert.equal(options.headers.Authorization, 'Bearer example-session-token');
    assert.deepEqual(JSON.parse(options.body).dietary_restrictions, ['vegetarian']);
    return { ok: true, status: 200, json: async () => ({
      has_history: false, previously_tried: [], saved_favorites: [], viewed_recipes: [],
    }) };
  });
  const data = await postJson('/api/menu-dashboard', {
    cuisine: 'Indian', dietary_restrictions: ['vegetarian'],
  }, { token: 'example-session-token' });
  assert.equal(data.has_history, false);
  assert.deepEqual(data.saved_favorites, []);
});

test('an old cuisine request cannot overwrite the latest selection', () => {
  const italian = beginFlow({ id: 0, controller: null }, 'Italian');
  const thai = beginFlow(italian, 'Thai');
  assert.equal(italian.controller.signal.aborted, true);
  assert.equal(isActiveFlow(thai, italian), false);
  assert.equal(isActiveFlow(thai, thai), true);
});

test('recipe navigation preserves standalone options rather than switching to history', () => {
  const beforeRecipe = recipeOrigin('menu_options', 'cuisines');
  const backDestination = recipeOrigin('recipe', beforeRecipe);
  assert.equal(backDestination, 'menu_options');
  assert.notEqual(backDestination, 'dashboard');
});

test('login expiration is an actionable HTTP error without leaking details', async t => {
  t.mock.method(globalThis, 'fetch', async () => ({
    ok: false, status: 401, json: async () => ({ detail: 'hidden session content' }),
  }));
  await assert.rejects(
    postJson('/api/menu-dashboard', { cuisine: 'Italian' }, { token: 'expired' }),
    error => error.message.includes('Sign in again') && !error.message.includes('hidden'),
  );
});
