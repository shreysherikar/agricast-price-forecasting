# Production Deployment Guide: Free Cloud Stack

This guide provides exact click-by-click instructions for deploying the Monthly Price Forecasting & Decision Support System on free cloud hosting.

---

## Architecture Overview

```text
               +----------------------------------+
               |         Vercel (Frontend)        |
               |  Next.js 14 Dashboard & Report   |
               +-----------------+----------------+
                                 |
         +-----------------------+-----------------------+
         |                                               |
         v                                               v
+-------------------------------+             +---------------------------+
| Render Web Service 2 (Gateway)|             | Render Web Service 1 (API)|
| Dockerfile.django             |             | Dockerfile.api            |
| Django REST + SQLite Fallback |             | FastAPI + Inference Engine|
+---------------+---------------+             +-------------+-------------+
                |                                           ^
                +-------------------------------------------+
                     FASTAPI_BASE_URL (Internal HTTP)
                                 ^
                                 | (Ping every 5 min)
                    +------------+------------+
                    |       UptimeRobot       |
                    | (Keeps instances awake) |
                    +-------------------------+
```

---

## Deployment Step 1: Render Web Service 1 (FastAPI Backend)

1. Log into your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> **Web Service**.
3. Select **Build and deploy from a Git repository** -> choose your project repository.
4. Fill in the service configuration:
   - **Name**: `forecasting-api` (or a unique name like `forecasting-api-<yourname>`)
   - **Region**: Choose closest to you (e.g., Oregon, Frankfurt, Singapore)
   - **Branch**: `main`
   - **Runtime**: **Docker**
   - **Dockerfile Path**: `Dockerfile.api`
   - **Instance Type**: **Free**
5. Expand **Advanced** -> **Health Check Path**:
   - Set to: `/health`
6. Under **Environment Variables**, add:
   - `FORECAST_API_KEY`: Generate a secure random key using Python:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(50))"
     ```
   - `CORS_ORIGINS`: Set initially to `*` (tighten in Step 5 after Vercel deployment)
   - `PYTHONUNBUFFERED`: `1`
7. Click **Create Web Service**.
8. Wait for the build and deployment to finish. Copy your public service URL:
   - Example: `https://forecasting-api-xxxx.onrender.com`

---

## Deployment Step 2: Render Web Service 2 (Django Gateway)

1. In Render Dashboard, click **New +** -> **Web Service**.
2. Select the same Git repository.
3. Fill in the service configuration:
   - **Name**: `forecasting-gateway` (or `forecasting-gateway-<yourname>`)
   - **Region**: Same region as Service 1
   - **Branch**: `main`
   - **Runtime**: **Docker**
   - **Dockerfile Path**: `Dockerfile.django`
   - **Instance Type**: **Free**
4. Expand **Advanced** -> **Health Check Path**:
   - Set to: `/api/health/`
5. Under **Environment Variables**, add:
   - `DJANGO_DEBUG`: `False`
   - `DJANGO_SECRET_KEY`: Generate a secure random key using Python:
     ```bash
     python -c "import secrets; print(secrets.token_urlsafe(50))"
     ```
   - `FASTAPI_BASE_URL`: The full URL of Service 1 from Step 1 (e.g. `https://forecasting-api-xxxx.onrender.com`)
   - `DJANGO_ALLOWED_HOSTS`: The hostname of this service (e.g. `forecasting-gateway-xxxx.onrender.com`)
   - `CORS_ALLOWED_ORIGINS`: Set initially to `*` or leave blank until Vercel is ready
   - `CORS_ALLOW_ALL`: `True` (temporary during initial setup; tighten in Step 5)
   - `FASTAPI_TIMEOUT_SECONDS`: `3.0`
   - `FASTAPI_CACHE_TTL_SECONDS`: `86400`
   *(Note: No Postgres is required. Standalone SQLite database is created and seeded automatically at startup with `python manage.py migrate && python manage.py load_forecast`).*
6. Click **Create Web Service**.
7. Wait for deployment to finish. Verify `/api/health/` returns `{"status":"HEALTHY","service":"django_gateway","database_connected":true}`.
8. Copy your gateway public URL:
   - Example: `https://forecasting-gateway-xxxx.onrender.com`

---

## Deployment Step 3: Vercel (Next.js Decision Support Dashboard)

1. Log into your [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** -> **Project**.
3. Import your GitHub repository.
4. In the **Configure Project** screen:
   - **Project Name**: `forecasting-dashboard`
   - **Framework Preset**: `Next.js`
   - **Root Directory**: Click Edit, select `frontend_next`, and click **Continue**.
5. Expand **Environment Variables** and add:
   - `NEXT_PUBLIC_API_URL`: `<Service 2 Gateway URL>/api/forecast/latest/`
     - Example: `https://forecasting-gateway-xxxx.onrender.com/api/forecast/latest/`
   - `NEXT_PUBLIC_FASTAPI_URL`: `<Service 1 FastAPI URL>`
     - Example: `https://forecasting-api-xxxx.onrender.com`
6. Click **Deploy**.
7. Wait 60-90 seconds. Once completed, copy the live Vercel URL:
   - Example: `https://forecasting-dashboard-xxxx.vercel.app`
8. **Mobile APK Configuration Update**: After getting your live gateway URL, update `mobile_app/eas.json` under `build.preview.env.EXPO_PUBLIC_API_URL` (replacing the placeholder `https://REPLACE-WITH-GATEWAY-HOST.onrender.com/...` with your real Render gateway URL) before building the APK via `npx eas build -p android --profile preview`.

---

## Deployment Step 4: UptimeRobot (Free Anti-Cold-Start Keep-Alive)

> [!WARNING]
> **Free Tier Instance Hours Budget Warning**:  
> Render's free tier provides approximately **750 free instance hours per month** across all web services on the account. Two services kept awake 24/7 (744 hours each = ~1,488 hours) will exhaust this monthly allowance by mid-month, causing services to be suspended until the next billing cycle.  
> **Recommendations**:  
> 1. Ping **ONLY** the Django Gateway service (`/api/health/`), which communicates with FastAPI on demand.  
> 2. Or **skip keep-alive entirely** and rely on the Next.js frontend's built-in resilient static fallback banner (*"Live backend is waking up (free hosting). Showing the saved forecast."*) while the free backend cold-starts (~50 seconds).  
> 3. Check Render's current free-tier resource allocation and terms at [render.com/docs/free](https://render.com/docs/free).

If you choose to use UptimeRobot for keep-alive monitoring:
1. Sign up or log into [UptimeRobot](https://uptimerobot.com).
2. Click **Add New Monitor**:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Forecasting Django Gateway Health`
   - **URL (or IP)**: `https://forecasting-gateway-xxxx.onrender.com/api/health/`
   - **Monitoring Interval**: `5 minutes`
   - Click **Create Monitor**.
3. (Optional, if sufficient free hours remain) Add Monitor for FastAPI:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Forecasting FastAPI Inference Health`
   - **URL (or IP)**: `https://forecasting-api-xxxx.onrender.com/health`
   - **Monitoring Interval**: `5 minutes`

---

## Deployment Step 5: Tighten Security (CORS & Allowed Hosts)

Now that all three public URLs are active, lock down origins:

1. **Render Service 1 (FastAPI)**:
   - Go to **Environment**.
   - Change `CORS_ORIGINS` to: `https://<your-vercel-domain>.vercel.app`
   - Click **Save Changes**. Service will automatically redeploy.

2. **Render Service 2 (Django Gateway)**:
   - Go to **Environment**.
   - Change `CORS_ALLOW_ALL` to: `False`
   - Change `CORS_ALLOWED_ORIGINS` to: `https://<your-vercel-domain>.vercel.app`
   - Ensure `DJANGO_ALLOWED_HOSTS` includes `<your-gateway-hostname>.onrender.com`
   - Click **Save Changes**.

---

## Deployment Step 6: External Live Verification

Once deployed, verify endpoints using `curl`:

```bash
# 1. FastAPI Health
curl -s https://<api-url>/health
# Expected: {"status":"HEALTHY","version":"1.0.0", ...}

# 2. FastAPI Interactive Docs
curl -s -I https://<api-url>/docs
# Expected: HTTP/2 200

# 3. Django Gateway Live Forecast
curl -s https://<gateway-url>/api/forecast/latest/
# Expected: "source":"fastapi_live","stale":false with 12 points

# 4. Next.js Dashboard & HTML Report
curl -s -I https://<vercel-url>/
# Expected: HTTP/2 200
curl -s -I https://<vercel-url>/report.html
# Expected: HTTP/2 200
```

---

## Note on Submission State & Future Deployment

In accordance with strict submission verification rules, the notebook and repository document **local-only verification**:
- The multi-container Docker Compose stack has been executed and verified locally (see `docs/docker_verification.md`).
- Cloud deployment (Render/Vercel) and the EAS Android APK build have **not** been executed.

If you subsequently deploy the services to Render and Vercel and verify all endpoints live, you may optionally update the notebook markdown statements (cells 126, 127, and 138) by hand to record the public cloud URLs and external verification timestamps.
