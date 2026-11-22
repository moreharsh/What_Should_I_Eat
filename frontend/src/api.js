// Shared JSON POST helper: safe errors, bounded waits and abort handling.
export async function postJson(url, payload, { token = '', signal, timeoutMs = 100000 } = {}) {
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  else signal?.addEventListener('abort', onAbort, { once: true });
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error('Your session expired. Sign in again.');
      if (response.status === 429) throw new Error('The service is busy. Please retry shortly.');
      throw new Error(`Request failed (HTTP ${response.status}). Please retry.`);
    }
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error('Server returned an invalid response. Please retry.');
    }
    if (!data || typeof data !== 'object' || Array.isArray(data) || 'detail' in data) {
      throw new Error('Server returned an invalid response. Please retry.');
    }
    return data;
  } catch (error) {
    if (timedOut) throw new Error('Request timed out. Please retry.');
    if (signal?.aborted) throw error;
    if (error instanceof TypeError) throw new Error('Cannot reach the server. Check your connection and retry.');
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onAbort);
  }
}
