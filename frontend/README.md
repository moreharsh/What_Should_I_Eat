# React frontend

This is the Vite/React application for **What Should I Eat?**

For the full architecture, API reference, secrets guidance, backend setup, and
troubleshooting, see the [root README](../ReadMe.md).

## Run locally

Requires Node.js 22 and a running backend on port 8000.

```bash
cp .env.example .env.local
npm ci
npm run dev
```

Windows PowerShell: `Copy-Item .env.example .env.local`.

Set `VITE_API_URL=http://localhost:8000` in `.env.local`. The Vite server
prints its URL (usually http://localhost:5173). The recipe UI is at `/` and
the read-only administrator interface is at `/admin`; the latter requires
a separately configured backend `ADMIN_PASSWORD`.

## Test and build

```bash
node --test tests/*.test.mjs
npm run lint
npx --yes --package typescript@5.9.3 tsc --project jsconfig.json
npm run build
```

The tests use built-in Node assertions and mocked HTTP responses; they do
not require live Gemini, Databricks or Redis credentials.

## Security

All `VITE_*` values are embedded into browser code. Put **only** the public
backend URL in these variables. Do not expose Gemini keys, Redis connection
strings, Databricks credentials, profile bearer tokens, or the admin password.
