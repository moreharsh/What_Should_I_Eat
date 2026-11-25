import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/App.jsx', import.meta.url), 'utf8');

test('registered profile UX includes sign up, sign in, recovery and logout', () => {
  assert.match(app, /\/api\/auth\/register/);
  assert.match(app, /\/api\/auth\/login/);
  assert.match(app, /\/api\/auth\/recover/);
  assert.match(app, /\/api\/session/);
  assert.match(app, /type="password"/);
  assert.match(app, /autoComplete="username"/);
  assert.match(app, /recoveryCode/);
  assert.match(app, /Keep my recipes/);
  assert.match(app, /setUpgrading\(true\)/);
});

test('account switch clears credentials and UI state', () => {
  assert.match(app, /setPasswordInput\(''\)/);
  assert.match(app, /setRecoveryInput\(''\)/);
  assert.match(app, /setRecoveryCode\(''\)/);
  assert.match(app, /setToken\(''\)/);
  assert.match(app, /setProfile\(null\)/);
  assert.match(app, /menuFlowRef\.current\.controller\?\.abort\(\)/);
  assert.match(app, /recipeFlowRef\.current\.controller\?\.abort\(\)/);
});
