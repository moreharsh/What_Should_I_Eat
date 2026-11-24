import assert from 'node:assert/strict';
import test from 'node:test';
import { redisHeartbeatRows, validateAdminResponse, visibleAdminRecords } from '../src/adminView.js';

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

test('maintenance status stays separate from generic Redis key metadata', () => {
  const timestamp = '2026-11-24T01:26:57.386045+00:00';
  const maintenance = {
    key: 'maintenance:redis-heartbeat:last-updated-utc',
    last_updated_utc: timestamp,
  };
  assert.deepEqual(validateAdminResponse('maintenance', maintenance), maintenance);
  assert.equal(validateAdminResponse('maintenance', { ...maintenance, last_updated_utc: null }).last_updated_utc, null);
  assert.equal(redisHeartbeatRows({ ...maintenance, last_updated_utc: null }).length, 0);
  const [row] = redisHeartbeatRows(maintenance);
  assert.equal(row.key, maintenance.key);
  assert.match(row.last_updated_utc, /^2026-11-24T01:26:57/);
  assert.match(row.last_updated_eastern, /Nov 23, 2026/);
  assert.match(row.last_updated_eastern, /EST/);

  const previous = { tab: 'redis', source: 'events', data: redis };
  assert.equal(visibleAdminRecords(previous, 'maintenance', 'events'), null);
  const current = { tab: 'maintenance', source: 'events', data: maintenance };
  assert.deepEqual(visibleAdminRecords(current, 'maintenance', 'events'), maintenance);
  assert.equal(visibleAdminRecords(current, 'redis', 'events'), null);
});

test('reject invalid or unexpected heartbeat status payloads', () => {
  for (const data of [null, {}, { key: 'admin:session:token', last_updated_utc: '2026-11-24T01:26:57Z' },
    { key: 'maintenance:redis-heartbeat:last-updated-utc', last_updated_utc: 'not-a-timestamp' },
    { key: 'maintenance:redis-heartbeat:last-updated-utc', last_updated_utc: undefined }]) {
    assert.throws(() => validateAdminResponse('maintenance', data), /unexpected response/);
  }
});
