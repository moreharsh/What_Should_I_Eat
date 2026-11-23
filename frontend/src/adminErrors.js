// Translate only allowlisted backend errors into actionable, non-sensitive UI messages.
export function adminErrorMessage(status, detail) {
  if (status === 401) return 'Invalid credentials or expired admin session.';
  if (status === 429) return 'Too many login attempts. Try again later.';
  if (status === 503) {
    if (detail === 'Databricks is not configured') {
      return 'Databricks credentials are missing on Render. Configure DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH and DATABRICKS_PERSONAL_ACCESS_TOKEN, then redeploy.';
    }
    if (detail === 'Analytics temporarily unavailable') {
      return 'Databricks query failed. Check Render logs for "Admin read-only Databricks query failed" and verify the SQL warehouse is running and the configured identity can read the analytics tables.';
    }
    if (detail === 'Admin access is not configured') {
      return 'Admin login is disabled: set ADMIN_PASSWORD on the Render backend.';
    }
    return 'The admin service is temporarily unavailable. Check Render logs.';
  }
  return `Admin request failed (HTTP ${status}).`;
}
