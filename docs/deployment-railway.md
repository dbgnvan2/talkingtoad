---
status: current
last_reviewed: 2026-05-27
---
# TalkingToad Deployment — Railway (backend) + Vercel (frontend)

> Status: v2.3 deployment model. Previous Vercel-only setup is deprecated
> because Vercel's serverless functions freeze after sending the response,
> which kills the asyncio.BackgroundTasks the crawler relies on.

## Architecture

```
                                    +---------------------+
  user browser  ----------------->  | Vercel (frontend)   |
                                    | - React SPA          |
                                    | - Static assets      |
                                    +----------+----------+
                                               |
                                       /api/*  | rewrites to
                                               v
                                    +---------------------+
                                    | Railway (backend)   |
                                    | - FastAPI/uvicorn   |
                                    | - Long-lived process|
                                    | - SQLite or Upstash |
                                    | - Crawler tasks live|
                                    |   here, persistently|
                                    +---------------------+
                                               |
                                               | optional
                                               v
                                    +---------------------+
                                    | Upstash Redis or    |
                                    | Railway Postgres    |
                                    +---------------------+
```

Frontend on Vercel: cheap, fast CDN, perfect for the React SPA.

Backend on Railway: long-lived container, no cold starts, BackgroundTasks
work normally.

## One-time Railway setup

1. **Create the project.** From the Railway dashboard:
   - "New Project" → "Deploy from GitHub Repo" → pick your fork of
     dbgnvan2/talkingtoad.
   - Railway auto-detects the `Dockerfile` at the repo root and builds it.

2. **Set environment variables** (Settings → Variables). At a minimum:

   | Variable | Required | Example | Notes |
   |---|---|---|---|
   | `AUTH_TOKEN` | **yes** | `<long random string>` | Production fails to start without this (M0.8 P2 fail-closed). |
   | `ALLOWED_ORIGINS` | **yes** | `https://talkingtoad.vercel.app` | Comma-separated. **Must not be `*`** in production (M0.8 P3 fail-closed). |
   | `DATABASE_URL` | optional | `redis://...` | When set, uses Upstash; otherwise falls back to SQLite at `SQLITE_PATH`. |
   | `SQLITE_PATH` | optional | `/data/talkingtoad.db` | For SQLite mode; needs a Railway volume mounted at the parent path. |
   | `UPSTASH_REDIS_REST_URL` | optional | `https://...upstash.io` | If using Upstash directly instead of DATABASE_URL. |
   | `UPSTASH_REDIS_REST_TOKEN` | optional | `...` | Pair with above. |
   | `GEMINI_API_KEY` | optional | `AIza...` | For AI features. Either Gemini or OpenAI is required for AI features to work. |
   | `OPENAI_API_KEY` | optional | `sk-...` | OpenAI is preferred when both are set. |
   | `LOG_LEVEL` | optional | `INFO` | DEBUG / INFO / WARNING / ERROR. Default INFO. |
   | `CRAWLER_USER_AGENT` | optional | `NonprofitCrawler/2.3 (+url)` | Identification for sites you crawl. |
   | `MAX_PAGES_PER_CRAWL` | optional | `500` | Default 500. |
   | `RATE_LIMIT_ENABLED` | optional | `true` | Default true. Set false only for dev. |
   | `RAILWAY_ENVIRONMENT` | auto | `production` | Set by Railway itself. Triggers M0.8 production safety checks. |

3. **Add persistent storage** (if using SQLite):
   - Settings → Volumes → "Add Volume" → mount path `/data`.
   - Set `SQLITE_PATH=/data/talkingtoad.db`.
   - Skip this step if you use Upstash; Redis is external.

4. **Deploy and grab the public URL**. After the first successful deploy,
   Railway gives you a URL like `talkingtoad-api.up.railway.app`. That's
   your `BACKEND_HOST` for the Vercel rewrite.

5. **Smoke test**:
   ```bash
   curl https://YOUR-SERVICE.up.railway.app/api/health
   # -> {"status":"ok","version":"..."}
   ```

## One-time Vercel setup

The Vercel project just hosts the frontend SPA and rewrites `/api/*` to
Railway. From the Vercel dashboard:

1. **Project Settings → Environment Variables**:
   - `BACKEND_HOST` = `talkingtoad-api.up.railway.app` (no protocol, no path).
   - `VITE_API_BASE_URL` = `/api` (frontend uses relative URLs).

2. **Build settings** (Vercel auto-detects from `vercel.json`):
   - Build command: `cd frontend && npm install && npm run build`
   - Output directory: `frontend/dist`
   - The `rewrites` block in `vercel.json` proxies `/api/*` to
     `https://$BACKEND_HOST/api/*`.

3. **Deploy** by pushing to main. CORS on Railway must include the Vercel
   domain (`ALLOWED_ORIGINS=https://talkingtoad.vercel.app`).

## Local development

Local dev still uses uvicorn directly — Docker is for production:

```bash
# Backend (port 8000)
cd /Users/davemini/ProjectsMini1/TalkingToad
source venv/bin/activate
uvicorn api.main:app --reload --port 8000

# Frontend (port 5173, vite proxy points at :8000)
cd frontend && npm run dev
```

To test the container locally before pushing:

```bash
docker build -t talkingtoad-api .
docker run --rm -p 8000:8000 \
    -e AUTH_TOKEN=local-dev-token \
    -e ALLOWED_ORIGINS=http://localhost:5173 \
    -e SQLITE_PATH=/tmp/talkingtoad.db \
    talkingtoad-api

curl http://localhost:8000/api/health
```

## Production safety guarantees (M0.8)

The container refuses to start if:
- A production environment is detected (VERCEL=1, RAILWAY_ENVIRONMENT set,
  RENDER=true, or ENV=production) AND
- `AUTH_TOKEN` is empty, OR
- `ALLOWED_ORIGINS` contains `*`.

This is a deliberate fail-closed safeguard — see
`tests/test_production_safety.py` and `api/main.py::_assert_production_safe`.

## Cost expectations

Railway pricing as of v2.3 plan: ~$5/month minimum for the always-on
container. Usage-based after that — for a low-traffic deployment (a few
crawls per day) you can stay under $10/month. Heavy use scales linearly.
Vercel hobby tier covers the frontend at $0.

## Migrating from the Vercel-only deploy

The previous `vercel.json` ran the Python app as a serverless function.
Now:

1. Deploy the Railway backend per the steps above.
2. Update Vercel env: set `BACKEND_HOST` to your Railway domain.
3. Re-deploy the Vercel frontend.
4. Verify a fresh crawl actually completes (this used to silently fail
   on Vercel because of the BackgroundTasks freeze).
5. After confirming, delete the old Vercel Python build artifacts via
   the Vercel dashboard.

There is no automated migration script — both deploys run side-by-side
during cutover. Once the new Railway-backed Vercel deploy is healthy, the
old Vercel-only deploy is just turned off.
