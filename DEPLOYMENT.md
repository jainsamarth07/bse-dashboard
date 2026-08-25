# Deployment, Security & Operations Guide

## Quick Start

```bash
# Start everything (MongoDB + Postgres + API + Monitor + Web)
docker compose up --build -d

# Also start Mongo Express admin UI (http://localhost:8081)
docker compose --profile admin up -d
```

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Next.js UI  │────▶│  FastAPI API  │────▶│   MongoDB    │
│  (port 3000) │     │  (port 8000) │     │   (Atlas)    │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────▼───────┐     ┌──────────────┐
                    │  PostgreSQL  │     │  BSE Monitor  │
                    │  (users/keys)│     │  (worker)     │
                    └──────────────┘     └──────────────┘
```

---

## Deployment Options

### Option A: Render.com (Recommended for MVP)

| Service         | Render Type      | Config                                   |
|-----------------|------------------|------------------------------------------|
| FastAPI API     | Web Service      | Docker, `Dockerfile.api`, port 8000      |
| Next.js UI      | Static Site / WS | Docker, `web/Dockerfile`, port 3000      |
| BSE Monitor     | Background Worker| Docker, `Dockerfile.api`, cmd: `python -m jobs.run_monitor` |
| PostgreSQL      | Managed Postgres | Free tier (256 MB) or Starter            |
| MongoDB         | External         | MongoDB Atlas (free M0 cluster)          |

**Steps:**
1. Create MongoDB Atlas free cluster → get connection string
2. Create Render Postgres → note `DATABASE_URL`
3. Create Render Web Service → point to repo, set `Dockerfile.api`
4. Set all env vars from `.env.example` on the Render dashboard
5. Create Render Background Worker → same repo, override start command
6. Create Render Static Site or Web Service for `web/`

### Option B: Google Cloud Run

```bash
# Build and push API image
gcloud builds submit --tag gcr.io/$PROJECT_ID/bse-api -f Dockerfile.api .

# Deploy API
gcloud run deploy bse-api \
  --image gcr.io/$PROJECT_ID/bse-api \
  --port 8000 \
  --set-env-vars "$(cat .env | tr '\n' ',')" \
  --allow-unauthenticated

# Build and push web image
gcloud builds submit --tag gcr.io/$PROJECT_ID/bse-web web/

# Deploy web
gcloud run deploy bse-web \
  --image gcr.io/$PROJECT_ID/bse-web \
  --port 3000 \
  --set-env-vars "NEXT_PUBLIC_API_URL=https://bse-api-xxxxx.run.app" \
  --allow-unauthenticated
```

For the monitor worker, use Cloud Run Jobs with a scheduler or an always-on Cloud Run service with `--min-instances=1`.

---

## Environment Variables Checklist

| Variable            | Required | Where         | Description                                    |
|---------------------|----------|---------------|------------------------------------------------|
| `MONGODB_URI`       | Yes      | API + Monitor | MongoDB Atlas connection string                |
| `DATABASE_URL`      | Yes      | API           | PostgreSQL connection string                   |
| `JWT_SECRET`        | Yes      | API           | 48+ char random string for JWT signing         |
| `ENCRYPTION_KEY`    | Yes      | API           | 64 hex chars (32 bytes) for AES-256-GCM        |
| `GROQ_API_KEY`      | Yes      | Monitor       | Groq API key                                   |
| `GEMINI_API_KEY`    | Yes      | Monitor       | Google Gemini API key (fallback)               |
| `BOT_TOKEN`         | Optional | Monitor       | Telegram bot token                             |
| `CHAT_ID`           | Optional | Monitor       | Telegram chat/group ID                         |
| `NEXT_PUBLIC_API_URL`| Yes     | Web           | Public URL of FastAPI server                   |
| `POLL_INTERVAL`     | Optional | Monitor       | BSE poll interval in seconds (default: 15)     |
| `MIN_MARKET_CAP`    | Optional | Monitor       | Min market cap filter in Cr (default: 500)     |

---

## Security Checklist

### Broker API Key Protection
- [ ] **AES-256-GCM encryption** at rest in Postgres (implemented in `api/crypto.py`)
- [ ] **Replace dev ENCRYPTION_KEY** — generate: `python -c "import os; print(os.urandom(32).hex())"`
- [ ] **KMS integration** for production — use AWS KMS / GCP KMS for envelope encryption
- [ ] **Masked display** in UI — only first 4 and last 3 chars visible
- [ ] **No key logging** — ensure API keys never appear in application logs
- [ ] **Key rotation support** — users can delete old keys and add new ones

### Authentication & Authorization
- [ ] **JWT tokens** with expiry (24h default) — change `JWT_EXPIRY_HOURS` for stricter
- [ ] **bcrypt password hashing** with salt
- [ ] **HTTPS everywhere** — Render and Cloud Run provide TLS by default
- [ ] **CORS restricted** — only allow your frontend domain in production
- [ ] **Rate limiting** — add `slowapi` middleware to FastAPI for brute-force protection

### Trade Safety
- [ ] **Paper mode by default** — all new broker keys start in paper mode
- [ ] **Connection verification required** before live trading
- [ ] **Audit trail** — every order (real + simulated) logged to `orders` table
- [ ] **Quantity limits** — consider adding max quantity per order in production
- [ ] **IP whitelisting** — some brokers support API key IP restrictions

### Infrastructure
- [ ] **No secrets in code** — all via env vars (✅ already separated)
- [ ] **Non-root Docker user** (✅ in Dockerfiles)
- [ ] **Read-only filesystem** where possible
- [ ] **Dependency scanning** — enable GitHub Dependabot
- [ ] **MongoDB Atlas IP whitelist** — restrict to your deployment IPs

---

## MongoDB `financial_results` Document (with ui_payload)

```json
{
  "scrip_code": "500325",
  "scrip_name": "RELIANCE",
  "company_name": "Reliance Industries Limited",
  "market_cap": 1725000.0,
  "news_date": "12/04/2026",
  "subject": "Financial Results for Dec 2025",
  "pdf_link": "https://www.bseindia.com/xml-data/corpfiling/AttachLive/example.pdf",
  "raw_analysis": "COMPANY NAME: Reliance Industries...",
  "company_name_extracted": "Reliance Industries Limited",
  "unit": "₹ Crores",
  "quarter": "Dec 2025",
  "growth": {
    "revenue": {"qoq": 4.2, "yoy": 7.1},
    "ebitda": {"qoq": 3.8, "yoy": 11.5},
    "net_profit": {"qoq": -2.1, "yoy": 7.3}
  },
  "absolute_numbers": {
    "revenue": {"latest": 259502, "previous": 249028, "sqly": 242234},
    "ebitda": {"latest": 47944, "previous": 46190, "sqly": 42999},
    "net_profit": {"latest": 18540, "previous": 18938, "sqly": 17280}
  },
  "margins": {"ebitda_margin": 18.5, "net_profit_margin": 7.1},
  "signal": "HOLD",
  "confidence": 62,
  "ai_model": "llama-3.3-70b-versatile",
  "analyzed_at": {"$date": "2026-04-12T09:30:00Z"}
}
```

---

## One-Week Roadmap

### Day 1-2: Prototype
- [ ] Set up MongoDB Atlas + Postgres (local Docker)
- [ ] Run `docker compose up --build -d` for local dev
- [ ] Test FastAPI endpoints with curl / Postman
- [ ] Run `python -m jobs.fetch_market_cap` to seed stock data
- [ ] Verify monitor produces `ui_payload` in financial_results

### Day 3-4: MVP Frontend
- [ ] `cd web && npm install && npm run dev`
- [ ] Verify Dashboard renders mock/real data
- [ ] Implement auth pages (login/signup)
- [ ] Implement broker key management page
- [ ] Test paper trade flow end-to-end

### Day 5: Broker Integration
- [ ] Obtain Upstox developer credentials → test OAuth flow
- [ ] Obtain Angel One SmartAPI credentials → test TOTP login
- [ ] Verify test-connection and LTP endpoints
- [ ] Paper trade → live trade toggle test

### Day 6: Deployment
- [ ] Deploy to Render / Cloud Run
- [ ] Configure env vars for production
- [ ] Enable HTTPS + CORS restrictions
- [ ] Load-test with wrk or k6

### Day 7: Polish & Hardening
- [ ] Add rate limiting (`slowapi`)
- [ ] Add structured logging (JSON logs)
- [ ] Security review (OWASP checklist)
- [ ] Write README with quickstart for contributors
- [ ] Tag v1.0.0 release

---

## API Endpoints Summary (OpenAPI)

### Auth
| Method | Path              | Auth  | Description              |
|--------|-------------------|-------|--------------------------|
| POST   | /api/auth/signup  | No    | Create account           |
| POST   | /api/auth/login   | No    | Login → JWT              |
| GET    | /api/auth/me      | JWT   | Current user info        |

### Results
| Method | Path                              | Auth  | Description                 |
|--------|-----------------------------------|-------|-----------------------------|
| GET    | /api/results/                     | No    | List analyses (filterable)  |
| GET    | /api/results/{scrip_code}/latest  | No    | Latest analysis for stock   |
| GET    | /api/results/{scrip_code}/history | No    | Historical analyses         |

### Stocks
| Method | Path                     | Auth  | Description               |
|--------|--------------------------|-------|---------------------------|
| GET    | /api/stocks/             | No    | List stocks (searchable)  |
| GET    | /api/stocks/{scrip_code} | No    | Single stock detail       |

### Brokers
| Method | Path                       | Auth | Description              |
|--------|----------------------------|------|--------------------------|
| GET    | /api/brokers/              | JWT  | List user's broker keys  |
| POST   | /api/brokers/              | JWT  | Add broker key           |
| DELETE | /api/brokers/{id}          | JWT  | Remove broker key        |
| POST   | /api/brokers/{id}/test     | JWT  | Test connection          |
| PATCH  | /api/brokers/{id}/mode     | JWT  | Toggle paper/live        |

### Trades
| Method | Path                    | Auth | Description           |
|--------|-------------------------|------|-----------------------|
| POST   | /api/trades/            | JWT  | Place order            |
| GET    | /api/trades/            | JWT  | List user's orders    |
| GET    | /api/trades/{order_id}  | JWT  | Order status           |
