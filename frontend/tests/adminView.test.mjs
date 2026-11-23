import assert from 'node:assert/strict';
import test from 'node:test';
import { validateAdminResponse, visibleAdminRecords } from '../src/adminView.js';

const users = { users: [{ username: 'chef' }], limit: 100 };
const redis = { keys: [{ key: 'recipe:v2:example' }], limit: 100 };
const events = { rows: [{ event_type: 'viewed' }], limit: 75 };

test('switching from users to Redis cannot render previous response as keys', () => {
  const previous = { tab: 'users', source: 'events', data: users };
  assert.equal(visibleAdminRecords(previous, 'redis', 'events'), null);
  assert.deepEqual(visibleAdminRecords(previous, 'users', 'events'), users);
});

test('switching from Redis to Databricks cannot render key metadata as rows', () => {
  const previous = { tab: 'redis', source: 'events', data: redis };
  assert.equal(visibleAdminRecords(previous, 'databricks', 'events'), null);
});

test('changing Databricks event source ignores the previous source response', () => {
  const previous = { tab: 'databricks', source: 'events', data: events };
  assert.equal(visibleAdminRecords(previous, 'databricks', 'clicks'), null);
});

test('newest tab response can display without breaking on empty results', () => {
  assert.deepEqual(validateAdminResponse('redis', { keys: [] }), { keys: [] });
  assert.deepEqual(validateAdminResponse('databricks', { rows: [] }), { rows: [] });
  assert.deepEqual(visibleAdminRecords({ tab: 'redis', data: redis }, 'redis', 'events'), redis);
});

test('unexpected or missing data reports a recoverable error instead of TypeError', () => {
  for (const [tab, payload] of [
    ['users', redis],
    ['redis', users],
    ['databricks', redis],
    ['redis', {}],
    ['databricks', null],
    ['users', { users: null }],
  ]) {
    assert.throws(() => validateAdminResponse(tab, payload), /unexpected response/);
  }
});
