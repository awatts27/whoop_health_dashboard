# WHOOP Health Dashboard

A full-stack personal health dashboard: WHOOP API → Supabase → FastAPI → React.

```
whoop-health/
├── .github/workflows/etl.yml          # Nightly ETL cron
├── backend/
│   ├── main.py                        # FastAPI entry point
│   ├── db.py                          # SQLAlchemy engine + session
│   ├── requirements.txt
│   ├── .env.example
│   ├── routers/
│   │   ├── sleep.py
│   │   ├── recovery.py
│   │   ├── workouts.py
│   │   ├── cycles.py
│   │   ├── journal.py
│   │   └── summary.py
│   └── etl/
│       ├── whoop_client.py            # WHOOP API v2 OAuth2 client
│       ├── transform.py               # Normalize + derive fields
│       ├── run_etl.py                 # Fetch → transform → upsert
│       └── materialize_daily_summary.py
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── .env.example
│   └── src/
│       ├── main.jsx
│       ├── index.css
│       ├── api.js
│       └── pages/Dashboard.jsx
├── schema.sql
└── README.md
```

---

## 1. Supabase setup

1. Create a project at [supabase.com](https://supabase.com).
2. Open **SQL Editor** and run the full contents of `schema.sql`.
3. Copy your **connection string** from *Project Settings → Database → Connection string (URI)*. It looks like:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres
   ```
   This becomes `DATABASE_URL`.

---

## 2. WHOOP API app registration

1. Go to [developer.whoop.com](https://developer.whoop.com) and create an application.
2. Set a redirect URI (e.g. `http://localhost:8000/oauth/callback` for local dev).
3. Copy **Client ID** and **Client Secret** → `WHOOP_CLIENT_ID`, `WHOOP_CLIENT_SECRET`.
4. Complete the OAuth2 Authorization Code flow once to get your initial
   `access_token` and `refresh_token`. The ETL will refresh them automatically
   on each run.

Required scopes: `read:recovery`, `read:sleep`, `read:workout`, `read:cycles`, `read:body_measurement`.

---

## 3. Backend — local dev

```bash
cd backend
cp .env.example .env        # fill in all values
pip install -r requirements.txt
uvicorn main:app --reload
```

API docs available at `http://localhost:8000/docs`.

### Run ETL manually

```bash
cd backend/etl
python run_etl.py                           # fetch + upsert yesterday
python materialize_daily_summary.py         # materialize yesterday
python materialize_daily_summary.py 2024-12-01  # backfill a specific date
```

---

## 4. Frontend — local dev

```bash
cd frontend
cp .env.example .env        # set VITE_API_URL and VITE_API_TOKEN
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## 5. GitHub Actions — nightly ETL

Add the following **Repository Secrets** (*Settings → Secrets and variables → Actions*):

| Secret | Value |
|---|---|
| `WHOOP_CLIENT_ID` | Your WHOOP client ID |
| `WHOOP_CLIENT_SECRET` | Your WHOOP client secret |
| `WHOOP_ACCESS_TOKEN` | Current access token |
| `WHOOP_REFRESH_TOKEN` | Current refresh token |
| `DATABASE_URL` | Supabase connection string |

The workflow (`.github/workflows/etl.yml`) runs at **08:00 UTC** daily and can
also be triggered manually via *Actions → Nightly WHOOP ETL → Run workflow*
with an optional `target_date` override.

---

## 6. Deploy

### Backend → Render

1. Create a new **Web Service** pointing to the `backend/` directory.
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables from `backend/.env.example` in the Render dashboard.

### Frontend → Vercel

1. Import the repo and set **Root Directory** to `frontend/`.
2. Framework preset: **Vite**.
3. Add environment variables:
   - `VITE_API_URL` → your Render backend URL (e.g. `https://your-api.onrender.com`)
   - `VITE_API_TOKEN` → must match `API_SECRET` on the backend

---

## Key design notes

- **Idempotent upserts** — all ETL writes use `ON CONFLICT (date) DO UPDATE`, safe to re-run.
- **Token refresh** — `WhoopClient` transparently refreshes OAuth2 tokens on 401 and propagates them back to `os.environ`.
- **strain_to_recovery_ratio** is the primary fatigue signal; flagged automatically when > 1.0 for 3+ of the last 7 days.
- **Sleep staging** (SWS, REM, light) is used for trend detection only. Labels in the UI reflect this explicitly.
- All secrets via environment variables — nothing hardcoded.
