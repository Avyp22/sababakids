# SababaKids 🧭

Find kid- & family-friendly **activities and events near you in Israel** within a chosen radius — by city/address or GPS. Places come live from **Google Places**; events combine a **national ticketing aggregator (Leaan)**, the **Modi'in municipal board**, and curated picks.

## Tech stack
- **Frontend**: React (CRA + CRACO) · Tailwind · shadcn/ui · Leaflet maps
- **Backend**: FastAPI · MongoDB (Motor) · httpx
- **Data**: Google Places (New) + Geocoding · leaan.co.il · modiin.muni.il

## Repository layout
```
frontend/    React app (this is what Netlify builds)
backend/     FastAPI app (host separately — Netlify cannot run it)
netlify.toml Netlify build config (base=frontend)
```

---

## ⚠️ Important: Netlify hosts the FRONTEND only
Netlify serves static sites. This project also needs the **FastAPI backend + MongoDB**
running somewhere (Emergent Deploy, Render, Railway, Fly.io, a VPS, etc.).
Deploy the backend first, then point the frontend at it.

## Deploy the frontend on Netlify
1. Push this repo to GitHub (already at `Avyp22/sababakids`).
2. In Netlify → **Add new site → Import an existing project** → pick this repo.
3. Build settings are auto-detected from `netlify.toml`:
   - Base directory: `frontend`
   - Build command: `yarn build`
   - Publish directory: `frontend/build`
4. Add an environment variable in **Site settings → Environment variables**:
   - `REACT_APP_BACKEND_URL` = the public URL of your deployed backend (no trailing slash)
5. Deploy. The included `_redirects` / `netlify.toml` rule handles SPA routing.

## Deploy the backend (example: any container/VM host)
```bash
cd backend
pip install -r requirements.txt
# set env vars (see backend/.env.example): MONGO_URL, DB_NAME, CORS_ORIGINS, GOOGLE_MAPS_API_KEY
uvicorn server:app --host 0.0.0.0 --port 8001
```
- Set `CORS_ORIGINS` to your Netlify site URL (e.g. `https://sababakids.netlify.app`).
- All API routes are served under the `/api` prefix.
- Provide a MongoDB connection string (e.g. MongoDB Atlas) in `MONGO_URL`.

## Local development
```bash
# backend
cd backend && pip install -r requirements.txt && uvicorn server:app --reload --port 8001
# frontend
cd frontend && yarn install && yarn start
```
Create `frontend/.env` with `REACT_APP_BACKEND_URL=http://localhost:8001`.

## Environment variables
| Where | Key | Purpose |
|------|-----|---------|
| frontend | `REACT_APP_BACKEND_URL` | Base URL of the backend API |
| backend | `MONGO_URL` | MongoDB connection string |
| backend | `DB_NAME` | Database name |
| backend | `CORS_ORIGINS` | Comma-separated allowed origins |
| backend | `GOOGLE_MAPS_API_KEY` | Google Places (New) + Geocoding API key |

> Secrets are **not** committed. Copy `*.env.example` files to `.env` and fill in your values.
