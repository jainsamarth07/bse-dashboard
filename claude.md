# BSE India API - Project Documentation

## 📋 Project Overview

**BseIndiaApi** is a comprehensive Python-based system for monitoring, analyzing, and tracking financial results from the Bombay Stock Exchange (BSE). The project combines web scraping, AI-powered PDF analysis, database management, and real-time notifications to provide automated financial insights for high-market-cap BSE-listed companies.

### Key Features
- 📡 Unofficial BSE API wrapper for fetching stock data, announcements, and financial results
- 💾 MongoDB-based storage for stocks, filtered results, and financial analysis
- 🤖 AI-powered analysis using Groq (Llama 3.3 70B) and Gemini with PDF extraction
- 📨 Real-time Telegram notifications with trading platform links
- 🔍 Continuous monitoring of BSE announcements with deduplication
- 📊 Financial metrics extraction (revenue, EBITDA, net profit, margins, growth rates)
- 🐳 Docker-based MongoDB infrastructure with Mongo Express web UI

---

## 🏗️ Architecture

```
BSE India API Server
├── BSE API Scraping Layer (bse/ folder)
├── MongoDB Connection Layer (src/db/)
├── Data Processing Layer (src/ main scripts)
├── AI Analysis Engine (Groq + Gemini)
├── Telegram Notification System
└── Docker Infrastructure (MongoDB + Mongo Express)
```

---

## 📁 Project Structure & Key Components

### **1. Core BSE API Module** (`src/bse/`)

The foundation for all data fetching from BSE India's unofficial API.

#### **BSE.py**
- **Purpose**: Main API wrapper for interacting with BSE India's data endpoints
- **Usage Pattern**: Context manager for safe session handling
- **Key Methods**:
  - `getScripCode(symbol)` - Get BSE scrip code from ticker symbol
  - `announcements(page_no)` - Fetch paginated announcements
  - `listSecurities(group)` - Get all securities in a BSE group
  - `gainers(by, name)` - Get top gainers by index or segment
  - `losers(by, name)` - Get top losers by index or segment
  - `quote(scripcode)` - Get OHLC quote for a security
  - `actions(scripcode)` - Get corporate actions (dividends, bonus, splits)
  - `resultCalendar()` - Get result announcement calendar

#### **constants.py**
- Enum-based constants for BSE indices and security groups
- Supported indices: `BSE500`, `SENSEX`, `NEXT50`, etc.

---

### **2. Database Layer** (`src/db/`)

Abstraction layer for all MongoDB operations with connection pooling.

#### **__init__.py** - MongoDB Connection Manager
- **`get_client()`** - Returns singleton MongoDB client with connection pooling
  - Max pool size: 10
  - Min pool size: 2
  - Server selection timeout: 5000ms
- **`get_db()`** - Returns `bse_india` database instance
- **`get_collection(name)`** - Gets specific collection by name
- **`mongo_session()`** - Context manager for database transactions
- **`ping()`** - Tests MongoDB connectivity (returns bool)
- **`close()`** - Gracefully closes all connections

**Collections Managed**:
- `all_stocks` - All BSE listed stocks with market cap
- `filtered_stocks` - Stocks with market cap > ₹500 Cr
- `seen_announcements` - Tracks processed announcements (prevents duplicates)
- `financial_results` - Parsed financial analysis data

#### **models.py** - Data Models & CRUD Operations

**StockStore** Class
```python
# Document Schema:
{
    scrip_code: str,        # BSE scrip code (e.g., "500325")
    scrip_name: str,        # Trading symbol (e.g., "RELIANCE")
    company_name: str,      # Full company name
    group: str,             # BSE group (A, B, T, etc.)
    industry: str,          # Industry category
    market_cap: float,      # Market cap in Crores (₹)
    face_value: str,        # Face value
    isin: str,              # ISIN number
    segment: str,           # Segment (Equity, etc.)
    status: str,            # Active/Suspended/Delisted
    updated_at: datetime    # Last update timestamp
}

# Methods:
- upsert(stock_data) - Insert or update a single stock
- bulk_upsert(stocks) - Bulk insert/update multiple stocks
- get_all() - Get all stocks sorted by market cap (descending)
- count() - Get total count of stocks in collection
```

**FilteredStockStore** Class
```python
# Stores only stocks with market_cap > ₹500 Crores
# Schema: Same as StockStore
# Used by: Analysis scripts to determine which results to analyze

# Methods:
- refresh_from_all_stocks() - Rebuild filtered collection from all_stocks
- get_by_scrip_code(code) - Find stock by scrip code
- get_all() - Get all filtered stocks (sorted by market cap descending)
- count() - Get total count of filtered stocks
```

**SeenAnnouncementStore** Class
```python
# Deduplication tracking for announcements
# Document Schema:
{
    scrip_code: str,        # BSE scrip code
    news_date: str,         # Announcement date (e.g., "13/02/2026")
    subject: str,           # Announcement subject
    created_at: datetime    # Timestamp when first seen
}
# Unique Index: (scrip_code, news_date, subject) - prevents duplicates

# Methods:
- mark_seen(scrip_code, news_date, subject) - Record as processed
- is_seen(scrip_code, news_date, subject) - Check if already processed
- get_all() - Get all seen announcements
```

**FinancialResultStore** Class
```python
# Stores parsed financial analysis from result PDFs
# Document Schema:
{
    scrip_code: str,                # BSE scrip code
    scrip_name: str,                # Trading symbol
    company_name: str,              # Company name
    market_cap: float,              # Market cap at time of analysis
    news_date: str,                 # BSE announcement date
    subject: str,                   # Announcement subject
    pdf_link: str,                  # URL to original PDF
    raw_analysis: str,              # Full text from AI analysis
    company_name_extracted: str,    # Company name from PDF
    unit: str,                      # Reporting unit (crores/lakhs/millions)
    growth: {
        revenue: {qoq: float, yoy: float},
        ebitda: {qoq: float, yoy: float},
        net_profit: {qoq: float, yoy: float}
    },
    margins: {
        ebitda_margin: float,
        net_profit_margin: float
    },
    ai_model: str,                  # "llama-3.3-70b-versatile" or "gemini-2.5-flash"
    analyzed_at: datetime           # Analysis timestamp
}
# Indexes: (scrip_code, analyzed_at), scrip_name, analyzed_at

# Methods:
- insert(result_data) - Store analysis results
- get_by_scrip_code(code) - Get all results for a security
- get_latest_by_scrip(code) - Get most recent analysis
- get_all() - Get all financial results
```

---

### **3. Main Data Processing Scripts** (`src/`)

#### **fetchMarketCap.py**
**Purpose**: Fetches market cap data for ALL BSE stocks and populates MongoDB

**Functionality**:
1. Iterates through all 23 BSE stock groups (A, B, E, F, FC, GC, I, IF, IP, M, MS, MT, P, R, T, TS, W, X, XD, XT, Y, Z, ZP, ZY)
2. Calls `bse.listSecurities(group)` for each group
3. Normalizes and deduplicates by scrip code
4. Stores all stocks in `all_stocks` collection via `StockStore.bulk_upsert()`
5. Auto-filters market cap > ₹500 Cr into `filtered_stocks` via `FilteredStockStore.refresh_from_all_stocks()`
6. Prints detailed summary with top 10 stocks by market cap

**Key Functions**:
- `fetch_all_stocks()` → `list[dict]` - Fetches and normalizes all BSE stocks
- `main()` - Orchestration: fetch → store → filter → summarize

**Run**: `python src/fetchMarketCap.py` (typically once daily)

---

#### **integratedResultAnalysisMongo.py**
**Purpose**: Main monitoring & analysis engine - watches for new results, analyzes with AI, sends to Telegram

**Workflow**:
1. ✅ Validates MongoDB connectivity via `ping()`
2. 🔄 Every 15 seconds, fetches all today's announcements from BSE API
3. 🔍 Filters for "Result" announcements only
4. 🏢 Checks if announcing company exists in `filtered_stocks` (market cap > ₹500 Cr)
5. 📥 Downloads result PDF from BSE link
6. 📄 Extracts text from PDF using PyMuPDF (fitz)
7. 🤖 Sends to Groq AI (Llama 3.3 70B) for financial analysis (with fallback to Gemini)
8. 💾 Stores raw analysis in MongoDB `financial_results` collection
9. 📊 Parses AI response to extract structured data (growth %, margins, etc.)
10. 📨 Sends formatted Telegram message with:
    - Company name, market cap, quarter
    - Revenue/EBITDA/Net Profit growth rates (Q/Q and Y/Y)
    - Margins (EBITDA and Net Profit)
    - Links to trade on Groww, Kite, and Dhan
11. 🗑️ Marks announcement as seen in `seen_announcements` to prevent reprocessing

**Key Functions**:
- `fetch_announcements()` - Fetch today's announcements from BSE
- `filter_results(announcements)` - Find "Result" announcements only
- `download_pdf(url, company)` - Download PDF to temp file
- `extract_pdf_text(pdf_path)` - Extract text using PyMuPDF
- `analyze_with_groq(text, company)` - Send to Groq AI
- `analyze_with_gemini(text, company)` - Fallback to Gemini (when Groq rate limited)
- `parse_ai_response(raw_analysis)` - Extract structured JSON from AI response
- `send_telegram_message(message_text)` - Send formatted message to Telegram group
- `store_in_mongodb(result_data)` - Store full analysis in `financial_results`
- `get_trading_links(company)` - Generate Groww/Kite/Dhan trading links
- `main()` - Main loop: fetch → filter → analyze → store → notify

**Configuration**:
- Groq API Key: `***REMOVED_GROQ_API_KEY***`
- Groq Model: `llama-3.3-70b-versatile`
- Gemini API Key: `***REMOVED_GEMINI_API_KEY***`
- Gemini Model: `gemini-2.5-flash`
- Telegram Bot Token: `***REMOVED_TELEGRAM_BOT_TOKEN***`
- Telegram Chat ID: `***REMOVED_TELEGRAM_CHAT_ID***`

**Run**: `python src/integratedResultAnalysisMongo.py` (runs continuously)

---

#### **integratedResultAnalysis.py**
**Purpose**: Original version using Google Gemini API (without MongoDB)
- Similar to integratedResultAnalysisMongo.py but stores results to local SQLite DB
- Uses `gemini-pro-vision` for PDF analysis
- Sends to Telegram

---

#### **integratedResultAnalysisGroq.py**
**Purpose**: Version using Groq API (without MongoDB)
- Similar workflow but without MongoDB persistence
- Uses Groq's Llama 3.3 70B model
- Sends to Telegram

---

#### **watch_bse.py**
**Purpose**: Lightweight announcement watcher without analysis

**Functionality**:
1. Polls BSE for new announcements every 10 seconds
2. Tracks latest announcement ID in `latest.json`
3. Prints new announcements to console with:
   - Company name (ScripName)
   - Announcement headline
   - Timestamp
   - BSE link
4. No database, no AI analysis - purely informational

**Key Functions**:
- `load_latest()` - Load last-seen announcement ID from JSON
- `save_latest(id)` - Save new announcement ID
- Main loop - Polls BSE every 10 seconds

**Run**: `python watch_bse.py` (runs continuously)

---

#### **getAllAnnoucements.py**
**Purpose**: Utility to fetch all BSE announcements with pagination

**Functionality**:
- `fetch_all_announcements()` - Fetches all announcements using `bse.announcements(page_no)`
- Handles pagination via `ROWCNT` field
- `monitor_announcements(interval=15)` - Continuous monitor that:
  - Fetches all announcements every N seconds
  - Tracks seen announcements using (scrip_code, date, subject) tuple
  - Prints new announcements with links

**Run**: `python src/getAllAnnoucements.py`

---

#### **getResultAnnouncements.py**
**Purpose**: Filter to show only "Result" category announcements

- Fetches all announcements
- Filters for result-related subjects
- Displays with timestamps and links

---

#### **updatesOnTelegramAll.py** & **updatesOnTelegramResult.py**
**Purpose**: Send announcements to Telegram

- updatesOnTelegramAll.py: Sends all announcements to Telegram
- updatesOnTelegramResult.py: Sends only result announcements to Telegram

---

### **4. Analysis Module** (`analysis/`)

High-performance cloud-ready version of the main system.

#### **monitor.py**
**Purpose**: Cloud-ready monitoring system (Railway/Render deployment)

**Features**:
- Same core functionality as `src/integratedResultAnalysisMongo.py`
- Uses `analysis/config.py` for centralized configuration
- Uses `analysis/db.py` for MongoDB connection (same as src/db/)
- Uses `analysis/models.py` for data models
- Environmental variable support via `.env`
- Optimized for Railway/Render deployment

#### **config.py**
**Purpose**: Centralized configuration management

**Configuration Parameters**:
- GROQ_API_KEY - Groq API credentials
- GEMINI_API_KEY - Google Gemini API credentials
- GROQ_MODEL - Groq model name
- GEMINI_MODEL - Gemini model name
- BOT_TOKEN - Telegram bot token
- CHAT_ID - Telegram chat/group ID
- MONGO_* - MongoDB credentials and connection params
- LOG_LEVEL - Logging verbosity

#### **db.py**
**Purpose**: MongoDB connection management (analysis version)
- Identical to `src/db/__init__.py`
- Reusable connection pooling and client management

#### **models.py**
**Purpose**: Database models (analysis version)
- Identical to `src/db/models.py`
- All CRUD operations for MongoDB collections

#### **fetch_market_cap.py**
**Purpose**: Cloud-compatible version of fetchMarketCap.py
- Same functionality as `src/fetchMarketCap.py`
- Optimized for scheduled execution on Railway/Render

#### **requirements.txt**
**Purpose**: Python dependencies for analysis module

**Key Dependencies**:
- `pymongo` - MongoDB driver with async support
- `groq` - Groq API client
- `google-generativeai` - Google Generative AI (Gemini)
- `requests` - HTTP client library
- `pymupdf` (fitz) - PDF text extraction
- `python-dotenv` - Environment variable management
- `pillow` - Image processing (for PDF images)
- `mthrottle` - Request rate limiting

---

### **5. Docker Configuration** (`docker/`)

#### **docker-compose.yml**
**Purpose**: Multi-service orchestration

**Services**:
1. **MongoDB** (`bse_mongodb`)
   - Image: `mongo:7`
   - Port: 27017
   - Users: `bseadmin`/`***REMOVED_MONGO_ADMIN_PASSWORD***` (admin), `bse_app`/`***REMOVED_MONGO_APP_PASSWORD***` (app user)
   - Database: `bse_india`
   - Volume: `mongodb_data` (persistent storage)

2. **Mongo Express** (`bse_mongo_express`)
   - Image: `mongo-express:latest`
   - Port: 8081
   - URL: http://localhost:8081
   - Web UI for database administration

#### **mongo-init.js**
**Purpose**: MongoDB initialization script

**Initialization Steps**:
1. Creates `bse_india` database
2. Creates application user `bse_app` with read-write permissions
3. Creates collections:
   - `all_stocks` with indexes on `scrip_code` (unique), `market_cap` (desc), `group`
   - `filtered_stocks` with indexes on `scrip_code`, `market_cap`
   - `seen_announcements` with compound unique index on (scrip_code, news_date, subject)
   - `financial_results` with indexes on (scrip_code, analyzed_at), scrip_name, analyzed_at

---

### **6. Documentation** (`docs/`)

Sphinx-based documentation generation
- `conf.py` - Sphinx configuration
- `source/index.rst` - Main documentation index
- `source/usage.rst` - Usage guide
- `source/Constants.rst` - API constants documentation

---

### **7. Test Suite** (`tests/`)

Unit and integration tests
- `test_symbol_parser.py` - Tests for symbol/scrip code parsing
- `Dockerfile` - Test environment

---

## 🚀 Deployment & Configuration

### Docker Deployment
```bash
# Start MongoDB and Mongo Express
docker compose up -d

# Verify connection
curl http://localhost:8081  # Mongo Express UI

# Check logs
docker compose logs -f
```

### Initial Setup
```bash
# 1. Fetch market cap data (run once or weekly)
python src/fetchMarketCap.py

# 2. Start monitoring (run continuously)
python src/integratedResultAnalysisMongo.py
```

### Environment Variables
```bash
# MongoDB
MONGO_HOST=localhost
MONGO_PORT=27017
MONGO_USER=bse_app
MONGO_PASS=***REMOVED_MONGO_APP_PASSWORD***
MONGO_DB=bse_india

# AI Services
GROQ_API_KEY=<your-groq-key>
GEMINI_API_KEY=<your-gemini-key>

# Telegram
BOT_TOKEN=<your-bot-token>
CHAT_ID=<your-chat-id>
```

### Cloud Deployment (Railway/Render)
- Use `analysis/` module (cloud-ready)
- Set environment variables in platform UI
- Use `docker-compose.yml` or managed MongoDB service
- Deploy with cron/scheduler:
  - `fetch_market_cap.py` - Daily or weekly
  - `monitor.py` - Continuous (background worker)

---

## 📊 Data Flow

### Stock Market Data
```
BSE API → fetchMarketCap.py → all_stocks (MongoDB)
                            ↓
                        filtered_stocks (MongoDB)
```

### Result Analysis
```
BSE API announcements
    ↓
Filter "Result" announcements
    ↓
Check filtered_stocks (market cap > ₹500 Cr)
    ↓
Download PDF from BSE
    ↓
Extract text (PyMuPDF)
    ↓
AI Analysis (Groq/Gemini)
    ↓
Parse response → Extract metrics
    ↓
Store in financial_results (MongoDB)
    ↓
Send to Telegram with trading links
    ↓
Mark in seen_announcements (prevent duplicate)
```

---

## 🔑 Key Algorithms & Logic

### Financial Analysis Parsing
The AI analysis extracts:
1. **Company Name & Unit** - From PDF letterhead or title
2. **Periods** - Auto-detects latest quarter (L.Q.), previous quarter (P.Q.), and same quarter last year (S.Q.L.Y.)
3. **Metrics** - Revenue, EBITDA, Net Profit (consolidated preferred, fallback to standalone)
4. **Calculations**:
   - `Q/Q Growth % = ((L.Q. - P.Q.) / |P.Q.|) × 100`
   - `Y/Y Growth % = ((L.Q. - S.Q.L.Y.) / |S.Q.L.Y.|) × 100`
   - `EBITDA Margin % = (EBITDA / Revenue) × 100`
   - `Net Profit Margin % = (Net Profit / Revenue) × 100`

### Deduplication Strategy
- Uses compound index: `(scrip_code, news_date, subject)`
- Marks announcements as seen before processing
- Prevents re-analysis of same announcement across restarts

### Rate Limiting
- 0.5s delay between BSE API group fetches
- 15-second polling interval for announcements
- Groq/Gemini API handles rate limiting internally

---

## 📦 Dependencies Summary

**Core**:
- `bse` - Local BSE API wrapper (v3.1.0)
- `pymongo` - MongoDB driver
- `requests` - HTTP requests

**AI/LLM**:
- `groq` - Groq API client
- `google-generativeai` - Google Gemini API

**PDF Processing**:
- `pymupdf` (fitz) - PDF text extraction
- `pillow` - Image handling

**Utilities**:
- `python-dotenv` - Environment variables
- `mthrottle` - Request throttling

**Documentation**:
- `sphinx` - Documentation generation
- `furo` - Sphinx theme

---

## 🎯 Use Cases

1. **Institutional Investors** - Track high-cap company results automatically
2. **Trading Platforms** - Aggregate financial data with market cap filtering
3. **Financial Analysts** - Auto-extract key metrics from result PDFs
4. **Investment Alerts** - Real-time Telegram notifications for significant results
5. **Data Science** - Historical financial data for ML models
6. **Portfolio Management** - Monitor results for portfolio holdings

---

## 🔒 Security Considerations

- MongoDB credentials in docker-compose (for local dev only)
- API keys in environment variables (not hardcoded in production)
- Telegram bot token secured via environment
- PDF downloads to temp files (auto-cleaned)
- Database connection pooling with timeouts

---

## 📝 Notes

- All timestamps stored as UTC in MongoDB
- Market cap in Indian Rupees (₹) Crores
- Financial metrics in reporting unit (Crores/Lakhs/Millions) as per PDF
- BSE groups updated as per latest exchange classification
- AI models can be switched (Groq/Gemini) based on availability and cost

