# What Should I Eat?

A full-stack recipe discovery application. Pick a cuisine and dietary preferences, get five AI-curated dishes, open a structured recipe with optional media, and keep separate **viewed**, **saved**, and **tried** collections. An optional read-only administrator interface shows profile activity, Redis metadata, and Databricks events.

**Live app:** https://what-should-i-eat-mu.vercel.app/  
**Admin UI:** https://what-should-i-eat-mu.vercel.app/admin

> **Demo identity warning:** Recipe profiles use usernames **without passwords**. Anyone who enters the same username can access that profile's saved and tried dishes. Do not use this as private or production user authentication.

## How it works

```text
React / Vite frontend (Vercel)
    |
    v
FastAPI endpoints (Render) ---------------------> Redis
    |                                              | recipe:v2:* cache
    | POST /api/menu                               | profile:username:v1:*
    |   -> Gemini Flash -> Gemini Flash Lite       | profile:session:* (TTL)
    |   -> five validated choices                  | user:* viewed/saved/tried sets
    |
    | POST /api/recipe
    |   -> Redis variant-cache lookup
    |   -> on miss: parallel LangGraph branches
    |        Chef: Gemini Flash -> Flash Lite -> optional Ollama
    |        Media: optional YouTube / Spoonacular
    |   -> recipe schema + dietary checks -> Redis cache
    |
    | FastAPI background analytics ----------------> Databricks SQL / Delta
    |                                                  default.user_clicks
    |                                                  default.app_user_events
    |
    + /api/admin/* -> authenticated, read-only admin view
```

The recipe cache is keyed by dish, cuisine, and normalized dietary restrictions. Viewing a recipe does **not** automatically mark it as saved or tried. Analytics logging is best effort and does not serve live recipe history. The administrator's Redis inspector exposes limited metadata, not session tokens or raw values.

### Tech stack

- **Frontend:** React 19, Vite, Tailwind CSS 4, Lucide icons.
- **Backend:** Python 3.11+, FastAPI, LangGraph, Google Gemini, optional Ollama.
- **Data:** Redis for active profiles/history/cache; Databricks SQL and Delta tables for analytics.
- **Media:** optional YouTube Data API and Spoonacular search; fallback media may be shown when the integrations are unavailable.
- **Deployment:** Vercel frontend; Render backend. The repository also contains a Power BI dashboard file.

## Repository layout

| Path | Purpose |
| --- | --- |
| `frontend/src/App.jsx` | Cuisine selection, recipe details, and profile history |
| `frontend/src/AdminDashboard.jsx` | Read-only administrator experience at `/admin` |
| `frontend/src/api.js` | API errors, abort signals, and request timeouts |
| `frontend/tests/` | Mocked frontend and navigation regression tests |
| `backend/main.py` | FastAPI HTTP endpoints and request contracts |
| `backend/agents.py`, `backend/recipe_workflow.py` | Gemini prompts, retries, and parallel recipe agent graph |
| `backend/ollama_fallback.py` | Optional asynchronous local-model adapter |
| `backend/recipe_cache.py`, `backend/user_sessions.py` | Dietary cache keys and demo profile sessions |
| `backend/data_layer.py` | Redis access and optional Databricks writes |
| `backend/admin_api.py` | Protected read-only operations endpoints |
| `backend/tests/` | Mocked API, history, analytics and orchestration tests |
| `.github/workflows/` | Pull-request quality, build and regression checks |

**Maintenance note:** `backend/database.py` and older exploratory scripts are legacy utilities and are **not** the live API's source of truth. The production data access path is `backend/data_layer.py`.

## Local setup

Prerequisites: **Python 3.11** (the same version used by CI), **Node.js 22**, npm, a reachable Redis server, and a Gemini API key for live generation.

### 1. Clone and configure the backend

```bash
git clone https://github.com/moreharsh/What_Should_I_Eat.git
cd What_Should_I_Eat

cp backend/.env.example backend/.env
# Fill in GEMINI_API_KEY and REDIS_URL in backend/.env
```

On Windows PowerShell, use `Copy-Item backend/.env.example backend/.env`.

The example file lists all server-side settings but contains **no real credentials**. Never commit the populated `backend/.env`.

### 2. Run FastAPI

```bash
cd backend
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1

python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The API is served at `http://127.0.0.1:8000`. For health verification: `curl http://127.0.0.1:8000/api/health`. Starting FastAPI does not perform an end-to-end Gemini/Redis/Databricks readiness check: verify those services independently.

### 3. Run the React frontend

In another terminal from the repository root:

```bash
cp frontend/.env.example frontend/.env.local
cd frontend
npm ci
npm run dev
```

On Windows PowerShell, use `Copy-Item frontend/.env.example frontend/.env.local`.

Open the URL printed by Vite (normally `http://localhost:5173`). `VITE_API_URL` must point to your FastAPI server. Only use `VITE_*` for **public browser-visible** settings; never place API keys, admin passwords, or database credentials there.

### Optional integrations

- **Databricks:** Leave its variables empty to skip analytics writes. With credentials configured, the SQL warehouse must be running and the service identity must be able to create/read/write `default.user_clicks` and `default.app_user_events`. The connected SQL warehouse's default catalog must resolve `default` to the intended schema; verify with `SELECT current_catalog(), current_schema();`. See `backend/sql/create_app_user_events.sql`.
- **YouTube / Spoonacular:** Optional media enrichment; recipes can be returned if media requests fail.
- **Ollama:** Optional **recipe** fallback only, activated by both `OLLAMA_BASE_URL` and `OLLAMA_MODEL`. It does not replace Gemini's five-option menu generation. See [Ollama configuration](backend/OLLAMA_FALLBACK.md).
- **Admin dashboard:** Set a server-side `ADMIN_PASSWORD` of at least 16 characters to activate `/admin`; the username is the fixed value `admin`. See [Admin dashboard](backend/ADMIN_DASHBOARD.md).

**Mock-only development:** There is no built-in fake-model runtime mode for the live website. The automated tests mock Gemini, Redis, Databricks and/or network calls and can run without cloud accounts. A real local frontend-to-backend demo still needs a Redis server and Gemini (or the appropriate previously cached data).

## API examples

The application uses JSON request bodies. Except where noted, profile-specific endpoints require an `Authorization: Bearer <token>` header. Replace `<token>` with the `token` returned by `POST /api/session`.

### Check health (no session)

```http
GET /api/health
```

Example response: `{"Health_status_code":200,"Health_status":"Active"}`.

### Create/restore a demo profile

```http
POST /api/session
Content-Type: application/json

{"username":"home_chef"}
```

Returns `user_id`, `username` and `token`. Usernames accept 3–24 letters, digits or underscores. `GET /api/session` checks the current bearer token; `DELETE /api/session` revokes it. Anyone can reuse a username, so **this is not secure login**.

### Generate five menu suggestions (no session required)

```http
POST /api/menu
Content-Type: application/json

{"cuisine":"Indian","dietary_restrictions":["vegetarian"]}
```

Example response shape (shortened):

```json
{
  "menu_options": [
    {"dish_name":"Palak Paneer","teaser":"Spinach and paneer","primary_protein":"Paneer"}
  ]
}
```

**The real successful response contains exactly five distinct options**, not the single abbreviated example above. Invalid/duplicate AI outputs produce a controlled HTTP 502.

### Open a recipe (session required)

```http
POST /api/recipe
Authorization: Bearer <token>
Content-Type: application/json

{"selected_dish":"Palak Paneer","cuisine":"Indian","dietary_restrictions":["vegetarian"]}
```

Example response shape:

```json
{
  "recipe_details": {
    "dish_name":"Palak Paneer",
    "prep_time":"15 minutes",
    "cook_time":"25 minutes",
    "servings":"4",
    "ingredients":["spinach","paneer"],
    "instructions":["Prepare the spinach.","Cook the sauce and add paneer."],
    "chef_pro_tip":"Adjust seasoning before serving."
  },
  "media_links": {"image_url":"https://example.com/food.jpg","youtube_embed_url":"https://www.youtube.com/embed/example"},
  "is_saved":false,
  "is_tried":false
}
```

Illustrative values only; the real recipe must satisfy the backend schema and dietary checks. `media_links` may be `null` if external media is unavailable.

### Fetch viewed, saved, and tried history (session required)

```http
POST /api/menu-dashboard
Authorization: Bearer <token>
Content-Type: application/json

{"cuisine":"Indian","dietary_restrictions":["vegetarian"]}
```

Response keys: `has_history`, `previously_tried`, `saved_favorites`, `viewed_recipes`. Each history entry includes dish, variant restrictions, preparation time, difficulty, teaser, and the three action flags. Histories are filtered by **cuisine and the exact normalized dietary variant**.

### Save or mark tried (session required)

```http
POST /api/recipe-action
Authorization: Bearer <token>
Content-Type: application/json

{"selected_dish":"Palak Paneer","cuisine":"Indian","dietary_restrictions":["vegetarian"],"action":"saved","active":true}
```

The `action` is `saved` or `tried`. Set `active: false` to undo. Open the recipe first so the selected variant exists in Redis. Response: `{"action":"saved","active":true}`.

See [Admin dashboard](backend/ADMIN_DASHBOARD.md) for the separate `/api/admin/*` routes.

## Tests and quality gates

The existing GitHub Actions workflows run on every pull request and on pushes to `main`.

```bash
# Mocked backend tests (no paid API credentials or live Redis required)
cd backend
python -m pip install 'fastapi>=0.110' 'httpx2>=0.1' 'pydantic>=2' 'langgraph>=1.0,<2'
python -m unittest discover -s tests -v

# Frontend tests, lint, type-check and production build
cd ../frontend
npm ci
node --test tests/*.test.mjs
npm run lint
npx --yes --package typescript@5.9.3 tsc --project jsconfig.json
npm run build
```

Quality workflows also run Python syntax/lint checks, Git whitespace/conflict-marker checks and CSpell. See [quality checks](.github/QUALITY_CHECKS.md). Real services are **not** called in CI.

## Troubleshooting

| Problem | Check |
| --- | --- |
| `REDIS_URL` not set / backend import error | Set `REDIS_URL` in `backend/.env` before starting FastAPI; Redis is required by profile/cache routes |
| Frontend cannot reach backend | Verify both dev servers and `VITE_API_URL=http://localhost:8000`; inspect browser Network tab |
| Gemini 502 | Confirm server-side `GEMINI_API_KEY`, model availability, quota and backend logs; Ollama is optional for recipes only |
| Admin login 503 | Configure a 16+ character `ADMIN_PASSWORD` on backend, then restart |
| Databricks 503 / table not found | Start the SQL warehouse, verify HTTP Path/catalog permissions and create required tables in the correct catalog/schema |
| Profile appears to belong to someone else | Username-only demo profiles are shared by anyone entering the username; use unique test names, do not store private data |
| Media image/video missing | Optional API keys, provider quota and network responses; recipe text should remain available |

## Security and limitations

- **No passwords for recipe profiles:** do not use for sensitive personal data. Replace with managed authentication before real user onboarding.
- The admin view uses a single shared password, not full role-based access control or SSO.
- Redis cache and profile records currently have no general retention policy; demo session tokens expire, but not all profile/history records do.
- Generated recipes are **not verified for allergens, ingredient labels, cross-contact or dietary safety**. Check ingredients independently.
- The Ollama fallback requires a network-reachable service; a laptop's `localhost` is not reachable from Render.
- Admin and recipe analytics can be unavailable when the Databricks SQL warehouse is stopped. Analytics is best effort.
- Never commit `.env` files with credentials or paste bearer tokens into issue reports. Rotate any accidentally exposed key. Only intentionally public settings go in the frontend.
