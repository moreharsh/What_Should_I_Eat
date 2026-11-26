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

test('one-click guest creates isolated session without a name or password input', () => {
  assert.match(app, /Continue as Guest/);
  assert.match(app, /onClick={continueAsGuest}/);
  assert.match(app, /fetchJson\('\/api\/guest-session', \{\}, true\)/);
  assert.match(app, /data\.username !== 'Guest User'/);
  assert.match(app, /data\.account_type !== 'guest'/);
  assert.match(app, /setProfile\(\{ username: 'Guest User'/);
  assert.match(app, /setUsernameInput\(''\)/);
  assert.match(app, /setPasswordInput\(''\)/);
  assert.match(app, /Exit Guest/);
  assert.match(app, /setUsernameInput\(profile\.username === 'Guest User' \? '' : profile\.username\)/);
  assert.doesNotMatch(app, /authMode === 'temporary'/);
  assert.match(app, /Guest history is temporary/);
});
