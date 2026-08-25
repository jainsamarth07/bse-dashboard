# 🏛️ BSE India Result Analysis System — Documentation

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    BSE India API (bseindia.com)               │
└──────────────┬───────────────────────────┬───────────────────┘
               │                           │
    ┌──────────▼──────────┐     ┌──────────▼──────────────┐
    │  fetchMarketCap.py  │     │ integratedResult-       │
    │  (Run daily/weekly) │     │ AnalysisMongo.py        │
    │                     │     │ (Runs continuously)     │
    │ • Fetches ALL BSE   │     │                         │
    │   stocks & market   │     │ • Monitors new results  │
    │   cap data          │     │ • Filters by mcap >500Cr│
    │ • Stores in MongoDB │     │ • Downloads PDFs        │
    │ • Filters >₹500 Cr  │     │ • Analyzes via Groq AI  │
    └──────────┬──────────┘     │ • Stores in MongoDB     │
               │                │ • Sends to Telegram     │
               │                │ • Adds broker links     │
               │                └──────────┬──────────────┘
               │                           │
    ┌──────────▼───────────────────────────▼──────────────────┐
    │                   MongoDB (Docker)                       │
    │                                                          │
    │  ┌─────────────────┐  ┌──────────────────┐              │
    │  │   all_stocks    │  │ filtered_stocks   │              │
    │  │ (ALL BSE stocks)│──│ (mcap > ₹500 Cr)  │              │
    │  └─────────────────┘  └──────────────────┘              │
    │                                                          │
    │  ┌───────────────────┐  ┌──────────────────────┐        │
    │  │seen_announcements │  │ financial_results     │        │
    │  │(dedup tracking)   │  │ (parsed analysis data)│        │
    │  └───────────────────┘  └──────────────────────┘        │
    └──────────────────────────────────────────────────────────┘
               │
    ┌──────────▼──────────┐
    │   Mongo Express     │
    │   (Web Admin UI)    │
    │   localhost:8081    │
    └─────────────────────┘
```

---

## 📁 File Structure

```
BseIndiaApi/
├── docker-compose.yml              # Docker services (MongoDB + Mongo Express)
├── docker/
│   └── mongo-init.js               # DB initialization (collections + indexes)
│
├── src/
│   ├── db/                         # Database layer (NEW)
│   │   ├── __init__.py             # MongoDB connection manager
│   │   └── models.py              # Data models & CRUD operations
│   │
│   ├── fetchMarketCap.py           # Fetches market cap for all BSE stocks (NEW)
│   ├── integratedResultAnalysisMongo.py  # Main analysis script with MongoDB (NEW)
│   │
│   ├── integratedResultAnalysis.py       # Original Gemini script (UNCHANGED)
│   ├── integratedResultAnalysisGroq.py   # Groq script without MongoDB (UNCHANGED)
│   └── ...                               # Other existing files (UNCHANGED)
│
├── bse_results.db                  # Old SQLite DB (still used by old scripts)
└── SYSTEM_DOCS.md                  # This file
```

---

## 🐳 Docker Services

### MongoDB (`bse_mongodb`)
- **Image:** `mongo:7`
- **Port:** `27017`
- **Credentials:**
  - Admin: `bseadmin` / `***REMOVED_MONGO_ADMIN_PASSWORD***`
  - App user: `bse_app` / `***REMOVED_MONGO_APP_PASSWORD***`
- **Database:** `bse_india`
- **Data persisted at:** Docker volume `mongodb_data`

### Mongo Express (`bse_mongo_express`)
- **Image:** `mongo-express:latest`
- **Port:** `8081`
- **Web UI login:** `admin` / `admin`
- **URL:** [http://localhost:8081](http://localhost:8081)

---

## 💾 MongoDB Collections

### 1. `all_stocks`
**Purpose:** Stores market cap and metadata for ALL BSE-listed stocks.  
**Populated by:** `fetchMarketCap.py`  
**Indexes:** `scrip_code` (unique), `market_cap` (descending), `group`

| Field | Type | Example |
|-------|------|---------|
| scrip_code | string | "500325" |
| scrip_name | string | "RELIANCE" |
| company_name | string | "Reliance Industries Limited" |
| group | string | "A" |
| industry | string | "Refineries" |
| market_cap | float | 1720345.50 |
| face_value | string | "10.00" |
| isin | string | "INE002A01018" |
| segment | string | "Equity" |
| status | string | "Active" |
| updated_at | datetime | 2026-02-13T10:00:00Z |

### 2. `filtered_stocks`
**Purpose:** Subset of `all_stocks` where `market_cap > ₹500 Cr`.  
**Populated by:** `fetchMarketCap.py` (auto-filtered)  
**Used by:** `integratedResultAnalysisMongo.py` to decide which results to analyze.  
**Schema:** Same as `all_stocks`

### 3. `seen_announcements`
**Purpose:** Tracks which BSE announcements have been processed (deduplication).  
**Populated by:** `integratedResultAnalysisMongo.py`  
**Indexes:** `(scrip_code, news_date, subject)` (unique compound)

| Field | Type | Example |
|-------|------|---------|
| scrip_code | string | "500325" |
| news_date | string | "13/02/2026" |
| subject | string | "Financial Results for..." |
| created_at | datetime | 2026-02-13T10:05:00Z |

### 4. `financial_results`
**Purpose:** Stores the parsed financial analysis data extracted from result PDFs.  
**Populated by:** `integratedResultAnalysisMongo.py`  
**Indexes:** `(scrip_code, analyzed_at)`, `scrip_name`, `analyzed_at`

| Field | Type | Description |
|-------|------|-------------|
| scrip_code | string | BSE scrip code |
| scrip_name | string | Trading symbol |
| company_name | string | Full company name |
| market_cap | float | Market cap at time of analysis (₹ Cr) |
| news_date | string | Announcement date |
| subject | string | Announcement subject |
| pdf_link | string | URL to the original PDF |
| raw_analysis | string | Full text analysis from Groq AI |
| company_name_extracted | string | Company name parsed from analysis |
| unit | string | Reporting unit (crores/lakhs/millions) |
| growth | object | `{revenue: {qoq, yoy}, ebitda: {qoq, yoy}, net_profit: {qoq, yoy}}` |
| margins | object | `{ebitda_margin, net_profit_margin}` |
| ai_model | string | "llama-3.3-70b-versatile" |
| analyzed_at | datetime | Timestamp of analysis |

---

## 🚀 Setup & Usage

### Step 1: Start Docker Services
```bash
cd /Users/samarth/Desktop/BseIndiaApi
docker compose up -d
```
This starts MongoDB and Mongo Express. Wait ~10 seconds for initialization.

### Step 2: Install Python Dependencies
```bash
source venv/bin/activate
pip install pymongo groq
```

### Step 3: Fetch Market Cap Data
```bash
python src/fetchMarketCap.py
```
This fetches all BSE stocks and filters those with market cap > ₹500 Cr.  
**Run this periodically** (daily/weekly) to keep data fresh.

### Step 4: Start the Result Monitor
```bash
python src/integratedResultAnalysisMongo.py
```
This continuously monitors BSE for new results, analyzes them, and sends to Telegram.

### View Data in Mongo Express
Open [http://localhost:8081](http://localhost:8081) → Login with `admin` / `admin` → Browse `bse_india` database.

---

## 🔄 Data Flow

```
1. fetchMarketCap.py runs
   │
   ├── BSE API → Fetches all stocks across all groups
   ├── MongoDB: all_stocks → Stores everything
   └── MongoDB: filtered_stocks → Only stocks > ₹500 Cr

2. integratedResultAnalysisMongo.py runs (loop every 15s)
   │
   ├── BSE API → Fetches Result announcements
   ├── MongoDB: seen_announcements → Check if already processed
   ├── MongoDB: filtered_stocks → Check if stock is eligible (>₹500 Cr)
   │
   │   If eligible and new:
   ├── Download PDF from BSE
   ├── Extract text from PDF (PyMuPDF)
   ├── Send to Groq AI (Llama 3.3 70B) for analysis
   ├── Parse structured metrics from analysis
   ├── MongoDB: financial_results → Store analysis + metrics
   └── Telegram → Send analysis + broker links (Groww/Kite/Dhan)
```

---

## ⚙️ Configuration

All configuration is at the top of each script:

| Setting | Location | Value |
|---------|----------|-------|
| MongoDB host | `src/db/__init__.py` | `localhost:27017` |
| MongoDB creds | `src/db/__init__.py` | `bse_app:***REMOVED_MONGO_APP_PASSWORD***` |
| Telegram Bot Token | Script config | `***REMOVED_TELEGRAM_BOT_ID***:AAG...` |
| Telegram Chat ID | Script config | `***REMOVED_TELEGRAM_CHAT_ID***` |
| Groq API Key | Script config | `gsk_pY2h4...` |
| Market cap filter | `src/db/models.py` | `₹500 Cr` |
| Polling interval | Script `__main__` | `15 seconds` |

### Environment Variables (Optional)
You can override MongoDB settings via env vars:
```bash
export MONGO_HOST=localhost
export MONGO_PORT=27017
export MONGO_USER=bse_app
export MONGO_PASS=***REMOVED_MONGO_APP_PASSWORD***
export MONGO_DB=bse_india
```

---

## 🛑 Stopping

```bash
# Stop the analysis script
Ctrl+C

# Stop Docker services (data is preserved)
docker compose stop

# Stop AND delete data
docker compose down -v
```

---

## 📊 Querying Data (Examples)

Connect to MongoDB shell:
```bash
docker exec -it bse_mongodb mongosh -u bse_app -p ***REMOVED_MONGO_APP_PASSWORD*** --authenticationDatabase bse_india bse_india
```

```javascript
// Count all stocks
db.all_stocks.countDocuments()

// Count filtered stocks (>₹500 Cr)
db.filtered_stocks.countDocuments()

// Top 10 by market cap
db.filtered_stocks.find().sort({market_cap: -1}).limit(10)

// Latest 5 analysis results
db.financial_results.find().sort({analyzed_at: -1}).limit(5)

// Get all results for a specific company
db.financial_results.find({scrip_name: "RELIANCE"})

// Count analyzed results
db.financial_results.countDocuments()

// Find stocks in a specific industry
db.all_stocks.find({industry: "Refineries"})
```
