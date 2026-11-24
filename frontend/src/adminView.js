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
  const field = tab === 'users' ? 'users' : tab === 'redis' ? 'keys' : tab === 'databricks' ? 'rows' : null;
  if (!field || !data || !Array.isArray(data[field])) {
    throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
  }
  return data;
}

export function visibleAdminRecords(records, tab, source) {
  if (!records || records.tab !== tab || ((tab === 'databricks' || tab === 'popularity') && records.source !== source)) {
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
