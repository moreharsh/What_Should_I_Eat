import { useCallback, useEffect, useRef, useState } from 'react';
import { redisHeartbeatRows, validateAdminResponse, visibleAdminRecords } from './adminView.js';
import { adminErrorMessage } from './adminErrors.js';
import { Activity, ArrowLeft, Clock3, Database, HardDrive, LockKeyhole, LogOut, RefreshCcw, ShieldCheck, Users } from 'lucide-react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const SESSION_KEY = 'recipe_admin_session';

/** @param {string} path
 * @param {{token?: string, method?: string, body?: object}} [options]
 */
async function adminRequest(path, { token = '', method = 'GET', body } = {}) {
  let response;
  try {
    response = await fetch(`${API}/api/admin${path}`, {
      method,
      headers: {
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    throw new Error('Admin API is unreachable. Check the backend deployment.');
  }
  if (!response.ok) {
    // The backend supplies short, safe error envelopes. Never render raw
    // exceptions or unrecognized server-provided detail in the browser.
    const payload = await response.json().catch(() => null);
    throw new Error(adminErrorMessage(response.status, payload?.detail));
  }
  return response.json();
}

function Table({ rows = [], columns }) {
  if (!Array.isArray(rows) || !rows.length) return <p className="rounded-xl bg-slate-50 p-5 text-sm text-slate-500">No records available in this view.</p>;
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="w-full min-w-[650px] text-left text-xs">
        <thead className="bg-slate-100 text-slate-600"><tr>
          {columns.map(col => <th key={col} className="px-3 py-3 font-semibold">{col.replaceAll('_', ' ')}</th>)}
        </tr></thead>
        <tbody>{rows.map((row, index) => <tr key={index} className="border-t border-slate-100">
          {columns.map(col => <td key={col} className="max-w-[250px] break-words px-3 py-3 align-top text-slate-700">
            {typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col] ?? '—')}
          </td>)}
        </tr>)}</tbody>
      </table>
    </div>
  );
}

function RecipeList({ label, items = [] }) {
  return <div className="space-y-2">
    <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">{label} ({items.length})</h4>
    {items.length ? <div className="flex flex-wrap gap-2">{items.map((recipe, index) =>
      <span key={index} title={[recipe.cuisine, ...(recipe.dietary_restrictions || [])].join(' · ')}
        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700">
        {recipe.dish_name} <span className="text-slate-400">· {recipe.cuisine}</span>
      </span>
    )}</div> : <p className="text-xs text-slate-400">None</p>}
  </div>;
}

export default function AdminDashboard() {
  const [token, setToken] = useState(() => sessionStorage.getItem(SESSION_KEY) || '');
  const [verified, setVerified] = useState(false);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);
  const [activeTab, setActiveTab] = useState('users');
  const [source, setSource] = useState('events');
  const [records, setRecords] = useState(null);
  const requestIdRef = useRef(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const clearSession = useCallback(() => {
    requestIdRef.current += 1;
    sessionStorage.removeItem(SESSION_KEY);
    setToken('');
    setVerified(false);
    setRecords(null);
    setPassword('');
  }, []);

  useEffect(() => {
    if (!token) return;
    let alive = true;
    adminRequest('/session', { token }).then(() => {
      if (alive) setVerified(true);
    }).catch(() => {
      if (alive) clearSession();
    });
    return () => { alive = false; };
  }, [token, clearSession]);

  const login = async event => {
    event.preventDefault();
    if (loggingIn) return;
    setError('');
    setLoggingIn(true);
    try {
      const data = await adminRequest('/login', {
        method: 'POST', body: { username, password },
      });
      sessionStorage.setItem(SESSION_KEY, data.token);
      setToken(data.token);
      setVerified(true);
      setPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in.');
    } finally {
      setLoggingIn(false);
    }
  };

  const logout = async () => {
    if (token) adminRequest('/logout', { token, method: 'POST' }).catch(() => {});
    clearSession();
  };

  const loadTab = useCallback(async () => {
    if (!token || !verified) return;
    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError('');
    setRecords(null);
    try {
      const path = activeTab === 'databricks' ? `/databricks?table=${source}`
        : activeTab === 'maintenance' ? '/redis-heartbeat' : `/${activeTab}`;
      const response = await adminRequest(path, { token });
      if (requestId !== requestIdRef.current) return;
      const data = validateAdminResponse(activeTab, response);
      setRecords({ tab: activeTab, source, data });
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      const message = err instanceof Error ? err.message : 'Unable to read admin data.';
      setError(message);
      if (message.includes('expired admin session')) clearSession();
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }, [token, verified, activeTab, source, clearSession]);

  useEffect(() => {
    let active = true;
    // Start the initial fetch asynchronously so effects do not synchronously
    // enqueue loading-state updates. The cleanup also guards a queued fetch.
    Promise.resolve().then(() => {
      if (active) void loadTab();
    });
    return () => {
      active = false;
      requestIdRef.current += 1;
    };
  }, [loadTab]);

  // Tab buttons update immediately, before effects can clear the previous
  // response. Never try to render that previous response under a new tab.
  const visibleRecords = visibleAdminRecords(records, activeTab, source);

  if (!verified) {
    return <div className="mx-auto max-w-md px-4 py-16">
      <a className="mb-6 inline-flex items-center gap-2 text-sm text-indigo-600" href="/"><ArrowLeft size={16}/> Recipe website</a>
      <div className="rounded-3xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-5 flex items-center gap-3"><LockKeyhole className="text-indigo-600" size={28}/>
          <div><h1 className="text-xl font-bold">Admin access</h1><p className="text-xs text-slate-500">Private, read-only operations dashboard</p></div>
        </div>
        {token ? <p role="status" className="text-sm text-slate-500">Checking admin session…</p> :
          <form onSubmit={login} className="space-y-4">
            <label className="block text-sm font-semibold">Admin username
              <input autoComplete="username" required value={username} onChange={e => setUsername(e.target.value)}
                className="mt-2 w-full rounded-lg border border-slate-300 p-3"/>
            </label>
            <label className="block text-sm font-semibold">Admin password
              <input type="password" autoComplete="current-password" required value={password}
                onChange={e => setPassword(e.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 p-3"/>
            </label>
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            <button disabled={loggingIn} className="w-full rounded-lg bg-indigo-600 p-3 font-bold text-white disabled:opacity-60">
              {loggingIn ? 'Signing in…' : 'Sign in to dashboard'}
            </button>
          </form>}
      </div>
    </div>;
  }

  const tabs = [
    { id: 'users', label: 'Users & selections', icon: Users },
    { id: 'redis', label: 'Redis inspector', icon: HardDrive },
    { id: 'maintenance', label: 'Redis maintenance', icon: Clock3 },
    { id: 'databricks', label: 'Databricks events', icon: Database },
  ];

  return <div className="mx-auto max-w-6xl space-y-6 px-4 py-8">
    <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 pb-5">
      <ShieldCheck size={30} className="text-indigo-600"/>
      <div><h1 className="text-2xl font-black">Recipe Admin</h1>
        <p className="text-xs text-slate-500">Read-only overview · Authenticated admin session</p></div>
      <div className="ml-auto flex gap-2"><a href="/" className="rounded-lg border border-slate-200 px-3 py-2 text-sm">View site</a>
        <button onClick={logout} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm">
          <LogOut size={15}/> Sign out
        </button></div>
    </header>
    <nav aria-label="Admin sections" className="flex flex-wrap gap-2">{tabs.map(tab => {
      const Icon = tab.icon;
      return <button key={tab.id} onClick={() => setActiveTab(tab.id)}
        aria-current={activeTab === tab.id ? 'page' : undefined}
        className={`flex items-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold ${activeTab === tab.id ? 'bg-indigo-600 text-white' : 'border border-slate-200 bg-white text-slate-600'}`}>
        <Icon size={16}/>{tab.label}
      </button>;
    })}</nav>
    <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Activity size={18} className="text-indigo-600"/>
        <h2 className="text-lg font-bold">{tabs.find(tab => tab.id === activeTab)?.label}</h2>
        {activeTab === 'databricks' && <select aria-label="Databricks table" value={source} onChange={e => setSource(e.target.value)}
          className="rounded-lg border border-slate-200 px-3 py-2 text-sm">
          <option value="events">Profile activity (app_user_events)</option>
          <option value="clicks">Recipe interactions (user_clicks)</option>
        </select>}
        <button onClick={loadTab} disabled={loading} className="ml-auto flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm disabled:opacity-50">
          <RefreshCcw size={15}/> Refresh
        </button>
      </div>
      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {loading && <p role="status" className="text-sm text-slate-500">Loading admin data…</p>}
      {!loading && visibleRecords && activeTab === 'users' && <>
        <p className="text-xs text-slate-500">Showing up to {visibleRecords.limit} registered usernames. Details represent the currently cached recipe variants.</p>
        <div className="grid gap-4">{visibleRecords.users.map(user =>
          <article key={user.user_id} className="space-y-4 rounded-xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-bold">@{user.username}</h3>
              <span className="text-xs text-slate-500">
                {user.counts.viewed} viewed · {user.counts.saved} saved · {user.counts.tried} tried
              </span>
            </div>
            <p className="break-all font-mono text-[11px] text-slate-400">{user.user_id}</p>
            <RecipeList label="Viewed" items={user.viewed}/>
            <RecipeList label="Saved" items={user.saved}/>
            <RecipeList label="Tried" items={user.tried}/>
          </article>)}</div>
        {!visibleRecords.users.length && <p className="text-sm text-slate-500">No registered user profiles found.</p>}
      </>}
      {!loading && visibleRecords && activeTab === 'redis' && <>
        <p className="text-xs text-slate-500">{visibleRecords.note} Maximum {visibleRecords.limit} keys per request.</p>
        <Table rows={visibleRecords.keys} columns={['key', 'type', 'size', 'ttl_seconds']}/>
      </>}
      {!loading && visibleRecords && activeTab === 'maintenance' && <>
        <p className="text-xs text-slate-500">
          Last successful heartbeat write, kept separate from recipe and profile keys.
          This view only reads the timestamp; it does not trigger another heartbeat.
        </p>
        {visibleRecords.last_updated_utc === null
          ? <p role="status" className="rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
              No heartbeat has been recorded yet.
            </p>
          : <Table rows={redisHeartbeatRows(visibleRecords)}
              columns={['key', 'last_updated_utc', 'last_updated_eastern']}/>}
        <p className="text-xs text-slate-500">
          A recent timestamp confirms a Redis write, not that every scheduled job will succeed.
          Check GitHub Actions for upcoming run results.
        </p>
      </>}
      {!loading && visibleRecords && activeTab === 'databricks' && <>
        <p className="text-xs text-slate-500">Most recent {visibleRecords.limit} entries, with sensitive recipe payloads and credentials excluded.</p>
        <Table rows={visibleRecords.rows} columns={source === 'events'
          ? ['event_at', 'username', 'event_type', 'dish_name', 'cuisine', 'dietary_restrictions', 'user_id']
          : ['timestamp', 'user_id', 'dish_name', 'cuisine', 'tracking_context']}/>
      </>}
    </section>
  </div>;
}
