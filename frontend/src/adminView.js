// Pure validation and view selection for asynchronous admin dashboard responses.
// Store each response with the tab it belongs to; never render users data as Redis rows.
export function validateAdminResponse(tab, data) {
  const field = tab === 'users' ? 'users' : tab === 'redis' ? 'keys' : tab === 'databricks' ? 'rows' : null;
  if (!field || !data || !Array.isArray(data[field])) {
    throw new Error('The admin API returned an unexpected response. Please refresh or check Render logs.');
  }
  return data;
}

export function visibleAdminRecords(records, tab, source) {
  if (!records || records.tab !== tab || (tab === 'databricks' && records.source !== source)) {
    return null;
  }
  return records.data;
}
