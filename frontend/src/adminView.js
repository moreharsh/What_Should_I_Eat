// Pure validation and view selection for asynchronous admin dashboard responses.
// Store each response with the tab it belongs to; never render users data as Redis rows.
export function validateAdminResponse(tab, data) {
  if (tab === 'maintenance') {
    if (!data || data.key !== 'maintenance:redis-heartbeat:last-updated-utc' ||
        (data.last_updated_utc !== null &&
         (typeof data.last_updated_utc !== 'string' ||
          !Number.isFinite(Date.parse(data.last_updated_utc))))) {
      throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
    }
    return data;
  }
  if (tab === 'popularity') {
    const validRows = rows => Array.isArray(rows) && rows.length <= 10 &&
      rows.every(item => typeof item.label === 'string' &&
        item.label.length <= 120 && Number.isSafeInteger(item.count) && item.count >= 0);
    if (!data || ![7, 30, 90].includes(data.days) || data.timezone !== 'UTC' ||
        data.dish_metric !== 'recipe_open_events' ||
        data.cuisine_metric !== 'recipe_view_events' ||
        !validRows(data.top_dishes) || !validRows(data.top_cuisines)) {
      throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
    }
    return data;
  }
  if (tab === 'activity') {
    const events = ['profile_created', 'viewed', 'saved', 'unsaved', 'tried', 'untried'];
    const validDate = value => typeof value === 'string' &&
      /^\d{4}-\d{2}-\d{2}$/.test(value) &&
      !Number.isNaN(Date.parse(value + 'T00:00:00Z'));
    if (!data || ![7, 30, 90].includes(data.days) || data.timezone !== 'UTC' ||
        data.metric !== 'logged_event_count' ||
        data.distinct_metric !== 'daily_distinct_profile_uuids' ||
        !Array.isArray(data.events) || data.events.join(',') !== events.join(',') ||
        !Array.isArray(data.rows) || data.rows.length !== data.days * events.length) {
      throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
    }
    const seen = new Set();
    const dates = new Set();
    for (const row of data.rows) {
      const key = row.date + ':' + row.event_type;
      if (!validDate(row.date) || !events.includes(row.event_type) || seen.has(key) ||
          !Number.isSafeInteger(row.count) || row.count < 0 ||
          !Number.isSafeInteger(row.distinct_profiles) ||
          row.distinct_profiles < 0 || row.distinct_profiles > row.count) {
        throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
      }
      seen.add(key);
      dates.add(row.date);
    }
    if (dates.size !== data.days || [...dates].some(date =>
        events.some(event => !seen.has(date + ':' + event)))) {
      throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
    }
    return data;
  }
  if (tab === 'engagement') {
    const events = ['viewed', 'saved', 'unsaved', 'tried', 'untried'];
    const validCount = number => Number.isSafeInteger(number) && number >= 0;
    const validRatio = value => value === null ||
      (typeof value === 'number' && Number.isFinite(value) && value >= 0);
    if (!data || ![7, 30, 90].includes(data.days) || data.timezone !== 'UTC' ||
        data.metric !== 'logged_action_events' ||
        data.distinct_metric !== 'distinct_profile_uuids_per_action' ||
        !Array.isArray(data.rows) || data.rows.length !== events.length ||
        data.rows.some((row, index) => row.event_type !== events[index] ||
          !validCount(row.count) || !validCount(row.distinct_profiles) ||
          row.distinct_profiles > row.count)) {
      throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
    }
    const counts = Object.fromEntries(data.rows.map(row => [row.event_type, row.count]));
    const summary = data.summary;
    const ratio = value => counts.viewed ? Math.round(value / counts.viewed * 10000) / 100 : null;
    if (!summary || summary.ratio_denominator_event !== 'viewed' ||
        summary.ratio_denominator_count !== counts.viewed ||
        !validRatio(summary.save_to_view_action_percent) ||
        !validRatio(summary.tried_to_view_action_percent) ||
        summary.save_to_view_action_percent !== ratio(counts.saved) ||
        summary.tried_to_view_action_percent !== ratio(counts.tried) ||
        summary.net_save_actions !== counts.saved - counts.unsaved ||
        summary.net_tried_actions !== counts.tried - counts.untried) {
      throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
    }
    return data;
  }
  const field = tab === 'users' ? 'users' : tab === 'redis' ? 'keys' : tab === 'databricks' ? 'rows' : null;
  if (!field || !data || !Array.isArray(data[field])) {
    throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
  }
  return data;
}

export function visibleAdminRecords(records, tab, source) {
  if (!records || records.tab !== tab || ((tab === 'databricks' || tab === 'popularity' || tab === 'activity' || tab === 'engagement') && records.source !== source)) {
    return null;
  }
  return records.data;
}

/** Format one fixed maintenance key in a separate read-only operational table.
 * @param {{ key: string, last_updated_utc: string | null }} data
 */
export function redisHeartbeatRows(data) {
  const timestamp = data.last_updated_utc;
  if (timestamp === null) return [];
  const date = new Date(timestamp);
  return [{
    key: data.key,
    last_updated_utc: date.toISOString().replace('.000Z', 'Z'),
    last_updated_eastern: new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      year: 'numeric', month: 'short', day: 'numeric',
      hour: 'numeric', minute: '2-digit', second: '2-digit',
      timeZoneName: 'short',
    }).format(date),
  }];
}

/** Validate an aggregate-only warehouse coverage report, never raw events. */
export function validateAnalyticsQuality(data) {
  const validCount = n => Number.isSafeInteger(n) && n >= 0;
  const validTime = value => value === null ||
    (typeof value === 'string' && /^\\d{4}-\\d{2}-\\d{2}T/.test(value) &&
      value.endsWith('Z') && Number.isFinite(Date.parse(value)));
  if (!data || ![7, 30, 90].includes(data.days) || data.timezone !== 'UTC' ||
      data.window !== 'utc_calendar_days_including_today' ||
      !validCount(data.profile_event_count) || !validCount(data.recipe_click_count) ||
      !validCount(data.recipe_open_event_count) ||
      !validCount(data.legacy_or_missing_profile_id_events) ||
      data.legacy_or_missing_profile_id_events > data.profile_event_count ||
      data.recipe_open_event_count > data.recipe_click_count ||
      !validTime(data.latest_profile_event_utc) ||
      !validTime(data.latest_recipe_click_utc)) {
    throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
  }
  return data;
}
