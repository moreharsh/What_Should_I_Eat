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

test('popularity payload validates windows, bounded counts and tab isolation', () => {
  const data = {
    days: 30,
    timezone: 'UTC',
    dish_metric: 'recipe_open_events',
    cuisine_metric: 'recipe_view_events',
    top_dishes: [{ label: 'Dal', count: 8 }],
    top_cuisines: [{ label: 'Indian', count: 5 }],
  };
  assert.deepEqual(validateAdminResponse('popularity', data), data);
  assert.deepEqual(validateAdminResponse('popularity', { ...data, top_dishes: [] }).top_dishes, []);
  const old = { tab: 'popularity', source: '30', data };
  assert.equal(visibleAdminRecords(old, 'popularity', '7'), null);
  assert.equal(visibleAdminRecords(old, 'redis', '30'), null);
  assert.deepEqual(visibleAdminRecords(old, 'popularity', '30'), data);
  for (const bad of [
    { ...data, days: 31 },
    { ...data, timezone: 'local' },
    { ...data, top_dishes: [{ label: 'Dal', count: -1 }] },
    { ...data, top_dishes: [{ label: 'Dal', count: 2.2 }] },
    { ...data, top_cuisines: new Array(11).fill({ label: 'x', count: 1 }) },
    { ...data, dish_metric: 'unique_people' },
    null,
  ]) assert.throws(() => validateAdminResponse('popularity', bad), /unexpected response/);
});


test('daily activity validates zero-filled dates, counts and tab-window isolation', () => {
  const events = ['profile_created', 'viewed', 'saved', 'unsaved', 'tried', 'untried'];
  const dates = ['2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21',
    '2026-11-22', '2026-11-23', '2026-11-24'];
  const rows = dates.flatMap(date => events.map(event_type => ({
    date, event_type, count: date === '2026-11-24' && event_type === 'viewed' ? 4 : 0,
    distinct_profiles: date === '2026-11-24' && event_type === 'viewed' ? 2 : 0,
  })));
  const data = {
    days: 7, timezone: 'UTC', events, rows,
    metric: 'logged_event_count', distinct_metric: 'daily_distinct_profile_uuids',
  };
  assert.deepEqual(validateAdminResponse('activity', data), data);
  const previous = { tab: 'activity', source: '7', data };
  assert.equal(visibleAdminRecords(previous, 'activity', '30'), null);
  assert.equal(visibleAdminRecords(previous, 'popularity', '7'), null);
  assert.deepEqual(visibleAdminRecords(previous, 'activity', '7'), data);
  for (const bad of [
    { ...data, days: 8 },
    { ...data, rows: rows.slice(1) },
    { ...data, rows: [...rows.slice(1), rows[1]] },
    { ...data, rows: rows.map((r, i) => i === 0 ? { ...r, count: -1 } : r) },
    { ...data, rows: rows.map((r, i) => i === 0 ? { ...r, count: 0, distinct_profiles: 1 } : r) },
    { ...data, timezone: 'Eastern' },
    { ...data, events: events.slice(1) },
  ]) assert.throws(() => validateAdminResponse('activity', bad), /unexpected response/);
});
