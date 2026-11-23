import assert from 'node:assert/strict';
import test from 'node:test';
import { adminErrorMessage } from '../src/adminErrors.js';

test('missing Databricks settings are actionable without leaking secrets', () => {
  const message = adminErrorMessage(503, 'Databricks is not configured');
  assert.match(message, /DATABRICKS_SERVER_HOSTNAME/);
  assert.match(message, /DATABRICKS_HTTP_PATH/);
  assert.match(message, /DATABRICKS_PERSONAL_ACCESS_TOKEN/);
});

test('unavailable SQL warehouse message points to Render logs and permissions', () => {
  const message = adminErrorMessage(503, 'Analytics temporarily unavailable');
  assert.match(message, /Databricks query failed/);
  assert.match(message, /Render logs/);
});

test('unknown backend details are not printed or trusted', () => {
  const privateValue = 'secret: redacted provider token';
  assert.doesNotMatch(adminErrorMessage(503, privateValue), /secret|token/);
  assert.doesNotMatch(adminErrorMessage(500, privateValue), /secret|token/);
});

test('authentication errors retain distinct messages', () => {
  assert.match(adminErrorMessage(401), /expired admin session/);
  assert.match(adminErrorMessage(429), /Too many login attempts/);
});
