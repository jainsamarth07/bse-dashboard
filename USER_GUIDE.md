# BSE Financial Dashboard — User Guide

> Everything you need to run, use, and extend the system.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Environment Setup (.env)](#2-environment-setup-env)
3. [All Docker Commands](#3-all-docker-commands)
4. [First-Time Data Population](#4-first-time-data-population)
5. [Web Dashboard — All Pages & Features](#5-web-dashboard--all-pages--features)
6. [REST API Reference](#6-rest-api-reference)
7. [WebSocket Real-Time Feed](#7-websocket-real-time-feed)
8. [Monitor Worker](#8-monitor-worker)
9. [Running Without Docker (Local Dev)](#9-running-without-docker-local-dev)
10. [Admin / Database UIs](#10-admin--database-uis)
11. [Common Troubleshooting](#11-common-troubleshooting)

---

## 1. Quick Start

```bash
# 1. Clone and enter the project
cd /Users/samarth/Desktop/BseIndiaApi

# 2. Create your environment file
cp .env.example .env      # then edit .env with your real keys

# 3. Build and start everything
docker compose up --build -d

# 4. Populate stock data (one-time, or run weekly)
docker exec bse_api python -m jobs.fetch_market_cap

# 5. Open the dashboard
open http://localhost:3000
```

Default login credentials (created on first signup):

| Field    | Value                |
|----------|----------------------|
| Email    | admin@example.com    |
| Password | admin123             |

> **Create your own account** — hit **Sign Up** on the login page. The first user is automatically an admin.

---

## 2. Environment Setup (.env)

Copy `.env.example` to `.env` and fill in the values:

```dotenv
# ── Postgres ────────────────────────────────────────────
PG_USER=bse_user
PG_PASS=bse_pass

# ── MongoDB ─────────────────────────────────────────────
MONGO_ADMIN_USER=bseadmin
MONGO_ADMIN_PASS=<choose-a-strong-password>
MONGO_APP_USER=bse_app
MONGO_APP_PASS=<choose-a-strong-password>

# ── JWT (change in production) ──────────────────────────
JWT_SECRET=changeme_in_production_to_a_long_random_string

# ── AI APIs ─────────────────────────────────────────────
GROQ_API_KEY=your_groq_api_key_here          # from console.groq.com
GEMINI_API_KEY=your_gemini_api_key_here      # from aistudio.google.com

# ── Telegram bot ────────────────────────────────────────
BOT_TOKEN=your_telegram_bot_token_here       # from @BotFather
CHAT_ID=your_telegram_chat_id_here           # group chat ID (negative for groups)

# ── Frontend URL (used by Next.js at build time) ─────────
API_URL=http://localhost:8000
```

---

## 3. All Docker Commands

### Start / Stop

| Command | What it does |
|---|---|
| `docker compose up --build -d` | Build images and start all services in background |
| `docker compose up -d` | Start without rebuilding (uses cached images) |
| `docker compose stop` | Stop containers, **keep all data** |
| `docker compose start` | Restart stopped containers |
| `docker compose restart api` | Restart a single service (e.g. `api`) |
| `docker compose down` | Stop and remove containers, **keep volumes** |
| `docker compose down -v` | ⚠️ Stop and **delete all data** (MongoDB + Postgres) |

### Admin UI (Mongo Express)

```bash
# Start the full stack including Mongo Express
docker compose --profile admin up -d

# Access at http://localhost:8081
# Username: admin / Password: admin
```

### Logs

```bash
docker compose logs -f              # tail all services
docker compose logs -f api          # only API logs
docker compose logs -f monitor      # only monitor worker logs
docker compose logs -f web          # only Next.js logs
docker logs bse_api --tail 50       # last 50 lines from API
```

### Container Status

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep bse
```

### Rebuild a Single Service

```bash
docker compose up --build -d api        # rebuild only the API
docker compose up --build -d monitor    # rebuild only the monitor
docker compose up --build -d web        # rebuild only the frontend
```

### Run One-Off Commands Inside a Container

```bash
# Fetch/refresh all market cap data
docker exec bse_api python -m jobs.fetch_market_cap

# Open a Python shell inside the API container
docker exec -it bse_api python

# Open a MongoDB shell
docker exec -it bse_mongodb mongosh -u bseadmin -p <your-mongo-admin-password>

# Open a Postgres shell
docker exec -it bse_postgres psql -U bse_user -d bse_web
```

### Prune / Reset

```bash
# Remove stale unused Docker networks (fixes "network not found" errors)
docker network prune -f

# Full reset: stop everything, delete volumes, rebuild from scratch
docker compose down -v
docker compose up --build -d
docker exec bse_api python -m jobs.fetch_market_cap
```

---

## 4. First-Time Data Population

After the stack is running, MongoDB starts empty. Run the market cap fetcher to seed data:

```bash
docker exec bse_api python -m jobs.fetch_market_cap
```

**What this does:**
- Connects to BSE India's API
- Fetches all ~4,800+ listed stocks across all 23 BSE groups (A, B, T, Z, etc.)
- Stores everything in `all_stocks` MongoDB collection
- Automatically filters stocks with **market cap ≥ ₹500 Crore** into `filtered_stocks`
- The monitor worker only analyzes results from `filtered_stocks`

**Expected output:**
```
✅ Upserted 4855 | Total in DB: 4855
✅ 1765 stocks qualify (market cap > 500 Cr)
```

> Run this weekly (or daily) to keep market cap data current.

---

## 5. Web Dashboard — All Pages & Features

Open **http://localhost:3000** in your browser.

### Authentication

- `/login` — Sign in with email + password
- `/login` → **Sign Up** tab — Create a new account
- JWT token is stored in `localStorage`; all API calls are authenticated automatically
- Clicking **Sign Out** in the navbar clears the token and redirects to `/login`

---

### Dashboard (`/`)

The home page showing a live overview:

| Section | Description |
|---|---|
| **Stats cards** | Total stocks tracked, results analyzed today, active monitor rules, pending notifications |
| **Recent Results** | Last 20 financial results analyzed by AI, with company name, market cap, growth rates |
| **Live Indicator** | Green dot showing WebSocket connection status |
| **Realtime updates** | New results appear instantly via WebSocket without page refresh |

---

### Stocks (`/stocks`)

Browse all 1,700+ high-cap BSE stocks:

| Feature | How to use |
|---|---|
| **Search** | Type company name or scrip code in the search box |
| **Sort** | Click any column header to sort ascending/descending |
| **Filter by group** | Use the Group dropdown (A, B, T, Z, etc.) |
| **Filter by industry** | Use the Industry dropdown |
| **Pagination** | Navigate pages using Previous/Next buttons |
| **Export CSV** | Click "Export CSV" to download the filtered list |
| **Stock detail** | Click any row to open the detail page |

#### Stock Detail Page (`/stocks/[scrip_code]`)

- Full OHLC price quote (live from BSE API)
- Price chart (weekly high/low)
- Corporate actions — dividends, bonus issues, splits
- All past financial results for this company
- Quick trade button

---

### Results (`/results`)

Browse all AI-analyzed financial results stored in MongoDB:

| Feature | How to use |
|---|---|
| **Revenue Growth** | Q/Q and Y/Y % shown with color coding (green = positive) |
| **EBITDA margin** | Displayed as % |
| **Net profit margin** | Displayed as % |
| **Filter by date** | Use the date range picker |
| **Filter by company** | Type in the search box |
| **View raw AI output** | Click a result row to expand the full AI analysis |
| **PDF link** | Click the PDF icon to open the original BSE filing |

---

### Trades (`/trades`)

Execute and track trades through connected broker accounts:

| Feature | How to use |
|---|---|
| **Place order** | Click "New Trade" → select broker, scrip, qty, buy/sell |
| **Paper mode** | Trades in paper mode are simulated — no real money |
| **Live mode** | Requires a verified broker API key; shows confirmation dialog |
| **Order history** | Table of all past trades with status (COMPLETE, PENDING, FAILED) |
| **LTP lookup** | Shows last traded price before placing order |

> **Paper vs Live**: A broker key defaults to **paper mode**. Switch to live in Settings → Broker Keys.

---

### BSE Tools (`/tools`)

Direct access to BSE India live data:

| Tool | Description |
|---|---|
| **Gainers** | Top gaining stocks by index (BSE500, Sensex, etc.) |
| **Losers** | Top losing stocks |
| **Result Calendar** | Upcoming result announcement schedule |
| **Announcements** | Latest BSE announcements (all categories) |
| **Quote lookup** | Enter a scrip code to get live OHLC |

---

### Settings (`/settings`)

Three tabs:

#### General Tab
- Change your display name
- Change your password
- Set notification preferences (Telegram on/off, email on/off)
- Set market cap threshold for alerts (default: ₹500 Cr)

#### Broker Keys Tab
- Add API keys for **Upstox**, **Angel One**, or a **Paper** (simulated) broker
- For each key: enter Client ID, Secret, and Access Token
- Toggle between **paper** and **live** mode per broker
- Delete a broker key
- Test connection status

#### Monitor Rules Tab
- Add rules to filter which companies the monitor analyses and alerts on
- **Rules are additive filters** — e.g. only alert if `market_cap > 5000` AND `group == A`
- Each rule has: Field, Operator, Value, and Enabled toggle
- Click **Reload Rules** to push new rules to the running monitor worker immediately

| Field | Supported operators | Example |
|---|---|---|
| `market_cap` | `>`, `>=`, `<`, `<=` | `> 5000` |
| `group` | `==`, `!=`, `in`, `not_in` | `== A` |
| `industry` | `contains`, `not_contains` | `contains Bank` |
| `scrip_name` | `==`, `!=`, `contains` | `contains HDFC` |

---

### Notifications

- Bell icon in the navbar shows unread notification count
- Click to open the notification drawer
- Notifications are generated by the monitor worker for every analyzed result
- They auto-expire after 7 days (MongoDB TTL index)

---

## 6. REST API Reference

Base URL: `http://localhost:8000`

All endpoints except `/health` and `/api/auth/*` require:
```
Authorization: Bearer <jwt_token>
```

### Auth

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create account `{email, password, name}` |
| `POST` | `/api/auth/login` | Get JWT `{email, password}` → `{access_token}` |
| `GET` | `/api/auth/me` | Get current user profile |

### Stocks

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/stocks/` | List filtered stocks. Params: `q`, `group`, `industry`, `page`, `per_page` |
| `GET` | `/api/stocks/{scrip_code}` | Single stock detail |
| `GET` | `/api/stocks/{scrip_code}/results` | All financial results for a stock |

### Results

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/results/` | All analyzed results. Params: `skip`, `limit`, `scrip_code` |
| `GET` | `/api/results/{id}` | Single result detail |

### BSE Live Data

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/bse/gainers` | Top gainers. Param: `index` (BSE500, SENSEX, etc.) |
| `GET` | `/api/bse/losers` | Top losers |
| `GET` | `/api/bse/quote/{scrip_code}` | Live OHLC quote |
| `GET` | `/api/bse/actions/{scrip_code}` | Corporate actions |
| `GET` | `/api/bse/announcements` | Recent announcements |
| `GET` | `/api/bse/result-calendar` | Result calendar |

### Brokers

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/brokers/` | List configured broker keys (secrets masked) |
| `POST` | `/api/brokers/` | Add broker key `{broker, client_id, secret, access_token, mode}` |
| `PATCH` | `/api/brokers/{id}` | Update a broker key |
| `DELETE` | `/api/brokers/{id}` | Delete a broker key |
| `GET` | `/api/brokers/{id}/test` | Test connectivity to broker API |

### Trades

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/trades/` | Trade history. Params: `broker`, `status`, `limit` |
| `POST` | `/api/trades/` | Place trade `{broker, scrip_code, qty, side, order_type}`. Add header `X-Trade-Confirm: yes` for live trades |
| `GET` | `/api/trades/{order_id}/status` | Order status |
| `GET` | `/api/trades/ltp/{scrip_code}` | Last traded price for a scrip |

### Monitor

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/monitor/rules` | List all monitor rules |
| `POST` | `/api/monitor/rules` | Create rule `{field, operator, value, enabled}` |
| `PATCH` | `/api/monitor/rules/{id}` | Update rule |
| `DELETE` | `/api/monitor/rules/{id}` | Delete rule |
| `POST` | `/api/monitor/reload` | Push current rules to the running worker |
| `GET` | `/api/monitor/status` | Worker status (last poll time, stocks processed, etc.) |

### Settings

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/settings/` | Get current user settings |
| `PATCH` | `/api/settings/` | Update settings `{notifications, market_cap_threshold, ...}` |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns `{"status": "ok"}` — no auth required |

### Interactive API Docs

FastAPI auto-generates interactive docs:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 7. WebSocket Real-Time Feed

Connect to receive live events (new results, notifications):

```
ws://localhost:8000/ws/updates?token=<jwt_token>
```

**Message format (JSON):**
```json
{
  "type": "new_result",
  "data": {
    "scrip_code": "500325",
    "scrip_name": "RELIANCE",
    "company_name": "Reliance Industries Ltd",
    "market_cap": 1823456.78,
    "growth": {
      "revenue": {"qoq": 3.2, "yoy": 7.8},
      "net_profit": {"qoq": -1.1, "yoy": 12.4}
    },
    "margins": {
      "ebitda_margin": 18.4,
      "net_profit_margin": 9.1
    },
    "analyzed_at": "2026-04-13T10:30:00Z"
  }
}
```

Other event types: `notification`, `monitor_status`, `ping`

---

## 8. Monitor Worker

The monitor runs as a separate Docker container (`bse_monitor`).

### How it works

1. Every **15 seconds**, fetches the latest BSE announcements
2. Includes all `"Result"` announcements, plus `"Board Meeting Outcome"` announcements
3. Cross-checks board outcomes against the BSE **result calendar** for that date/company (so results are not missed when subject text does not contain `result`)
4. Checks if the announcing company is in `filtered_stocks` (market cap ≥ ₹500 Cr)
5. Checks `seen_announcements` to skip duplicates
6. Downloads the result PDF from BSE
7. Extracts text using PyMuPDF
8. Sends to **Groq (Llama 3.3 70B)** for analysis; falls back to **Gemini** if rate-limited
9. Stores structured analysis in `financial_results` MongoDB collection
10. Pushes a WebSocket notification to all connected dashboard users
11. Sends a Telegram message to the configured group

### Monitor Rules

Rules filter which companies are analyzed. If **no rules** are set, all 1,700+ eligible stocks are monitored.

Rules are stored in MongoDB (`monitor_rules` collection) and can be managed from the dashboard at **Settings → Monitor Rules** or via the API.

### Telegram Notifications

Each analyzed result sends a message with:
- Company name + market cap
- Quarter being reported
- Revenue / EBITDA / Net Profit growth (Q/Q and Y/Y)
- EBITDA and net profit margins
- Direct trade links: [Groww](https://groww.in), [Kite (Zerodha)](https://kite.zerodha.com), [Dhan](https://dhan.co)

### Monitor Logs

```bash
docker compose logs -f monitor
```

Expected output when healthy:
```
✅ MongoDB connected
✅ Loaded 1765 stocks (market cap > ₹500 Cr)
📋 No monitor rules — processing all eligible stocks
🔍 Polling every 15s — press Ctrl-C to stop.
🔔 NEW RESULT: RELIANCE (500325) @ 13/04/2026
📄 PDF downloaded (245 KB)
🤖 Groq analysis complete
💾 Stored in MongoDB
📨 Telegram sent
```

---

## 9. Running Without Docker (Local Dev)

### Prerequisites

```bash
# Python 3.11+
python --version

# Node 18+
node --version

# MongoDB running locally
brew services start mongodb-community  # macOS

# Postgres running locally
brew services start postgresql@16
```

### Backend

```bash
cd /Users/samarth/Desktop/BseIndiaApi

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables (or use .env file)
export DATABASE_URL="postgresql://bse_user:bse_pass@localhost:5432/bse_web"
export MONGODB_URI="mongodb://localhost:27017/bse_india"
export JWT_SECRET="dev_secret_key"
export GROQ_API_KEY="gsk_..."
export GEMINI_API_KEY="AIzaSy..."
export BOT_TOKEN="..."
export CHAT_ID="..."

# Run API server (hot reload)
uvicorn api.main:app --reload --port 8000

# In another terminal: run monitor worker
python -m jobs.run_monitor

# Populate stock data
python -m jobs.fetch_market_cap
```

### Frontend

```bash
cd /Users/samarth/Desktop/BseIndiaApi/web

# Install dependencies
npm install

# Start dev server (hot reload, connects to localhost:8000)
npm run dev

# Type check
npx tsc --noEmit

# Production build
npm run build
npm start
```

---

## 10. Admin / Database UIs

### Mongo Express (web-based MongoDB admin)

```bash
# Start with the admin profile
docker compose --profile admin up -d
```

- URL: **http://localhost:8081**
- Username: `admin` / Password: `admin`
- Browse collections: `all_stocks`, `filtered_stocks`, `financial_results`, `seen_announcements`, `monitor_rules`, `notifications`

### FastAPI Interactive Docs

- **Swagger UI**: http://localhost:8000/docs — try any endpoint in the browser
- **ReDoc**: http://localhost:8000/redoc — clean documentation view

---

## 11. Common Troubleshooting

### "Cannot connect to Docker daemon"
```bash
open -a Docker   # start Docker Desktop on macOS
```

### Containers not starting / "network not found"
```bash
docker network prune -f
docker compose up -d
```

### UI shows 401 Unauthorized
- Your JWT has expired. Go to http://localhost:3000/login and sign in again.
- Or the token is missing — clear `localStorage` in browser DevTools and log in.

### Stocks page shows no data
```bash
# Re-populate stock data
docker exec bse_api python -m jobs.fetch_market_cap
```

### Monitor shows "No eligible stocks"
Same as above — run `fetch_market_cap` first.

### Monitor not logging anything
```bash
# Check the container is running
docker ps | grep monitor

# Check logs
docker compose logs -f monitor

# Restart if needed
docker compose restart monitor
```

### API 500 errors on stocks endpoint
- Usually caused by null fields in MongoDB documents.
- Rebuild the stock data: `docker exec bse_api python -m jobs.fetch_market_cap`

### TypeScript errors in VS Code (settings page)
- These are usually stale language server cache.
- Press `Cmd+Shift+P` → **TypeScript: Restart TS Server**

### Groq rate limit errors in monitor
- The monitor automatically falls back to Gemini when Groq is rate-limited.
- If both fail, check your API keys in `.env`.

### Lost all data after `docker compose down -v`
- The `-v` flag deletes Docker volumes (all MongoDB and Postgres data).
- Re-run `fetch_market_cap` to restore stock data.
- Financial results from the monitor cannot be recovered — they will rebuild over time as new BSE results come in.

### Telegram messages not arriving
1. Check `BOT_TOKEN` and `CHAT_ID` in `.env`
2. Make sure the bot has been added to the group/channel
3. For groups, the `CHAT_ID` must be negative (e.g. `***REMOVED_TELEGRAM_CHAT_ID***`)
4. Test manually:
```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>" \
  -d "text=Test message"
```

---

## Service Port Summary

| Service | URL | Notes |
|---|---|---|
| **Dashboard (Next.js)** | http://localhost:3000 | Main UI |
| **API (FastAPI)** | http://localhost:8000 | Backend REST API |
| **API Docs** | http://localhost:8000/docs | Swagger UI |
| **Mongo Express** | http://localhost:8081 | DB admin (profile: admin) |
| **MongoDB** | localhost:27017 | Direct connection |
| **Postgres** | localhost:5432 | Direct connection |
| **WebSocket** | ws://localhost:8000/ws/updates | Realtime feed |
