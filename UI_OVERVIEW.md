# UI Overview — BSE Result Analyser

This document describes every page and component in the current frontend (`web/`), what it looks like, how it works, and honest notes on what could be improved. Use this as a reference when redesigning.

---

## Design System (Current)

| Property | Value |
|---|---|
| Framework | Next.js 15 (App Router) |
| Styling | Tailwind CSS v3 |
| Icons | Lucide React |
| Data fetching | TanStack Query (React Query v5) |
| Background | `#0f172a` (slate-900) — used everywhere |
| Card background | `#1e293b` (slate-800) |
| Borders | `slate-700` |
| Primary text | `slate-100` / white |
| Secondary text | `slate-400 / slate-500` |
| Accent | `blue-500 / blue-600` |
| Font | System UI stack (ui-sans-serif → Segoe UI → Roboto → Arial) |
| Layout | Max-width `7xl` (80rem), centred, `px-6` padding |

Everything is **dark-only**. No light mode exists.

---

## Global Shell

### `AppShell.tsx`

Wraps every authenticated page. Does:
- Auth guard: checks `localStorage` for `bse_token`, redirects to `/login` if missing
- Opens the WebSocket connection (`useRealtimeUpdates`)
- On `new_result` WS event: invalidates the results query and shows a toast
- Renders `<Navbar>` above `<main>`

**Layout structure:**
```
min-h-screen bg-[#0f172a]
  └── <Navbar> (sticky, top-0)
  └── <main> (no padding — each page adds its own)
```

There is **no sidebar**. Navigation is entirely in the top navbar.

---

### `Navbar.tsx`

Sticky top bar. Contains:
- Left: 📊 logo + "BSE Result Analyser" text (links to `/`)
- Centre: Nav links — Dashboard · Stocks · Trades · BSE Tools · Settings
  - Active link: `bg-slate-700/60 text-white`
  - Inactive: `text-slate-400 hover:bg-slate-800`
  - Icons collapse on small screens (`hidden sm:inline`)
- Right: `LiveIndicator` (green/grey dot) + "Sign out" button

**Pain points:**
- No results count or notification bell — no quick way to know if new data arrived without watching the live dot
- No breadcrumb or page title in the navbar
- Logo is just an emoji + text — no real brand identity
- On mobile the text labels disappear, leaving icon-only nav with no tooltips

---

## Pages

---

### `/login` — Login / Sign Up

**Layout:** Centred card on dark background.

```
bg-[#0f172a] full screen
  └── max-w-md centred column
        ├── Logo (emoji + title + subtitle)
        └── rounded-2xl card (bg-[#1e293b] p-8)
              ├── Toggle: Sign In | Create Account
              ├── Form fields (email, password, [name for signup])
              ├── Error message (red text)
              └── Submit button (blue, full width)
```

**How it works:**
- Two modes toggled by the tab strip: `login` / `signup`
- Calls `/api/auth/login` or `/api/auth/register`, stores token in `localStorage`
- Already logged in → immediately redirects to `/`

**Pain points:**
- Form has no "show/hide password" toggle
- No "forgot password" link
- Error message is plain red text, no styled alert box
- Very minimal styling — functional but plain

---

### `/` — Dashboard

**Layout:** Full-width content area, `mx-auto max-w-7xl px-6 py-6` (AppShell adds no padding).

```
<AppShell>
  <Dashboard>
    ├── Filter bar (search input + signal pills + result count)
    └── Card grid (1 col → 2 col → 3 col on xl)
          └── <ResultCard> × N
    └── <Pagination>
    └── <TradeModal> (dialog, rendered conditionally)
```

**Filter bar:**
- Text input: searches company name or scrip code
- Signal pills: ALL | BUY | SELL | HOLD | NEUTRAL (blue when active)
- Result count right-aligned ("42 results")

**Pagination:** Previous / Next buttons + "Page X of Y" text. Simple, no page number list.

**Loading state:** Centred spinning ring (`border-blue-500 border-t-transparent`).

**Empty state:** Plain centred text "No results found. The monitor may not have processed any announcements yet."

**Pain points:**
- No summary stats anywhere (total analyzed today, biggest beat, worst miss, etc.)
- No date range filter on dashboard
- No sort options (e.g. "sort by net profit growth")
- Cards are uniform grid — no way to spotlight top performers
- Pagination is bare-bones; no "go to page" input or page number buttons
- No export button

---

### `ResultCard.tsx` — The core UI component

Every result is displayed as a card. Structure:

```
rounded-xl border-slate-700 bg-[#1e293b] p-5 shadow-lg
  ├── Header row
  │     ├── Left: company_name (lg semibold white)
  │     │         scrip_code · quarter · unit · ₹X Cr (sm slate-400)
  │     │         🕐 analyzed timestamp (xs slate-500)
  │     └── Right: Signal badge (BUY/SELL/HOLD/NEUTRAL) + confidence %
  │
  ├── Growth summary (3-column grid)
  │     REVENUE | EBITDA | NET PROFIT
  │     Each tile: label (xs uppercase slate-500)
  │                YoY % (lg bold, green if +, red if −)
  │                "YoY · QoQ X%" (xs slate-500)
  │                [Verdict badge if estimate exists: BEAT/MISS/IN_LINE + pct_diff]
  │
  ├── Absolute numbers table (xs font)
  │     Columns: Metric | Latest | [Estimate if available] | Prev Q | SQLY
  │     Rows: Revenue · EBITDA · Net Profit
  │
  ├── Margins row (2 boxes side by side)
  │     EBITDA Margin % | Net Profit Margin %
  │
  └── Footer: Trade buttons (Buy / Sell, small, text-only)
```

**Colours:**
- Signal badges: green=BUY, red=SELL, amber=HOLD, slate=NEUTRAL
- Verdict badges: emerald=BEAT, red=MISS, slate=IN_LINE
- Growth numbers: green if ≥ 0, red if < 0

**Pain points:**
- Card is very information-dense — hard to scan at a glance
- The absolute numbers table is tiny (`text-xs`) and hard to read
- Margins are shown in small boxes that look identical to each other
- No visual separator between sections
- The "Trade" buttons are small and easy to miss
- No expand/collapse — no way to see the raw AI analysis text without navigating away
- Company name can be very long and wraps awkwardly
- Confidence % is shown next to the signal badge but means little without context

---

### `/stocks` — Stocks Browser

**Layout:**
```
<AppShell>
  ├── Header: Building2 icon + "Stocks" title + Export CSV button
  ├── Filter row: search input (Ctrl+K focuses) + Group dropdown
  ├── Total count label
  └── <DataTable>
        └── columns: Scrip Code | Company | Group | Industry | Market Cap | Face Value
  └── <Pagination>
```

**How it works:**
- Debounced search (300 ms) hits `/api/stocks/`
- Clicking a row navigates to `/stocks/[scrip_code]`
- Export CSV downloads the current filtered set

**Pain points:**
- No industry filter dropdown (only group)
- No sort on table columns
- No market cap range slider/filter
- The table has no sticky header on scroll
- "Export CSV" button has no visual feedback while downloading

---

### `/stocks/[scrip_code]` — Stock Detail

**Layout:**
```
<AppShell>
  ├── Back button + company name heading
  ├── Quote card: OHLC + 52-week high/low
  ├── Corporate actions table (dividends, bonus, splits)
  └── Past financial results (list of ResultCards)
```

**Pain points:**
- No price chart / sparkline
- Corporate actions table is unstyled (plain)
- Past results are full-size ResultCards stacked vertically — very long page

---

### `/trades` — Trades

**Layout:**
```
<AppShell>
  ├── "New Trade" button → opens <TradeModal>
  ├── Filter: broker dropdown + status dropdown
  └── <DataTable>
        columns: Date | Scrip | Broker | Side | Qty | Price | Status
```

**TradeModal:**
- Dialog with fields: broker selector, scrip code input, buy/sell toggle, quantity, order type (market/limit), limit price
- "Paper trade" mode shows a warning banner
- Confirm button sends to `/api/trades/`

**Pain points:**
- No LTP (last traded price) shown automatically in the modal — user has to remember or look up manually (there's an API but it requires a separate action)
- No P&L or portfolio summary
- No trade filtering by scrip code

---

### `/tools` — BSE Toolbox

**Layout:**
```
<AppShell>
  ├── Wrench icon + "BSE Toolbox" heading
  ├── Tab strip: Gainers | Losers | Result Calendar | Quote Lookup | Corp Actions | Estimates
  └── Tab content panel
```

**Gainers / Losers panel:**
- Index dropdown (BSE500, SENSEX, etc.)
- Table: Rank | Scrip | Company | Price | Change | Change %

**Result Calendar:**
- Table: Date | Scrip Code | Company | Purpose

**Quote Lookup:**
- Scrip code input + "Get Quote" button
- Shows: Open, High, Low, Close, Volume, 52W High, 52W Low

**Corp Actions:**
- Scrip code input + table of dividends, splits, bonus

**Estimates tab:**
- Status bar: "X estimates loaded" + "Clear All" button
- Upload zone: drag-and-drop or click to browse (`.xlsx` only)
- Column layout description (informational text)

**Pain points:**
- Gainers/Losers have no quick-trade button
- No search in Result Calendar
- Estimates tab shows no preview of what was imported (no company list)
- The tab strip wraps on mobile (too many tabs)

---

### `/settings` — Settings

**Layout:**
```
<AppShell>
  └── max-w-5xl centred
        ├── Settings icon + "Settings" heading
        ├── Tab strip: General | Broker Keys | Monitor Rules
        └── Tab content
```

**General tab:**
- Change display name
- Change password
- Toggle notifications (Telegram on/off)
- Market cap threshold input

**Broker Keys tab:**
- List of connected brokers (client ID shown, secret masked)
- "Add Key" form: broker type, client ID, secret, access token, paper/live toggle
- Test connection + Delete buttons per key

**Monitor Rules tab:**
- Table of rules (Field · Operator · Value · Enabled toggle · Delete)
- "Add Rule" form: field dropdown, operator dropdown, value input
- "Reload Rules" button pushes rules to the running monitor

**Pain points:**
- General tab and Broker tab forms give no visual confirmation on save (just clears + re-fetches)
- Paper/live toggle is a small checkbox — easy to miss
- No explanation of what monitor rules do inline (requires reading the docs)

---

## Shared Components

| Component | What it does | Pain points |
|---|---|---|
| `DataTable.tsx` | Generic sortable table with loading state | No sticky header, no column resize, no row hover highlight |
| `Pagination.tsx` | Prev/Next + "Page X of Y" | No page number buttons, no "per page" selector |
| `SignalBadge.tsx` | Coloured pill for BUY/SELL/HOLD/NEUTRAL | — |
| `LiveIndicator.tsx` | Green/grey dot + "Live"/"Offline" label | Easy to miss in the navbar |
| `Toast.tsx` | Bottom-right notification (4 types: success/error/info/warning) | Disappears quickly, no way to dismiss manually |
| `ConfirmModal.tsx` | Generic "Are you sure?" dialog | — |
| `TradeModal.tsx` | Full trade placement dialog | No LTP auto-fetch, no order preview |

---

## What's Missing from the UI

Things that exist in the backend/API but aren't surfaced in the UI:

1. **Notification bell** — backend generates notifications on every result, but there's no bell/drawer in the UI
2. **Raw AI analysis text** — stored in the DB, not accessible in the current dashboard (only on detail page if it exists)
3. **Sector/Industry filter** on the dashboard
4. **Date range filter** on the dashboard
5. **Scrip detail page from dashboard** — clicking a result card doesn't navigate anywhere
6. **Monitor status** — `/api/monitor/status` exists but nothing in the UI shows last poll time or worker health
7. **Summary stats** — no "X results today", "X BUY signals", etc.

---

## Quick Reference: File → Page/Component Map

```
web/src/
├── app/
│   ├── page.tsx                    → / (Dashboard)
│   ├── layout.tsx                  → Root HTML shell (fonts, metadata)
│   ├── globals.css                 → Tailwind base + CSS variables
│   ├── login/page.tsx              → /login
│   ├── stocks/page.tsx             → /stocks
│   ├── stocks/[scrip_code]/page.tsx → /stocks/:scrip_code
│   ├── trades/page.tsx             → /trades
│   ├── tools/page.tsx              → /tools
│   └── settings/
│       ├── page.tsx                → /settings (tab shell)
│       ├── GeneralTab.tsx          → General settings form
│       ├── BrokersTab.tsx          → Broker key management
│       └── MonitorTab.tsx          → Monitor rules CRUD
│
├── components/
│   ├── AppShell.tsx                → Auth guard + WS + Navbar wrapper
│   ├── Navbar.tsx                  → Top navigation bar
│   ├── Dashboard.tsx               → Results grid + filters
│   ├── ResultCard.tsx              → Individual result card (main data tile)
│   ├── DataTable.tsx               → Generic table component
│   ├── Pagination.tsx              → Prev/Next pagination
│   ├── SignalBadge.tsx             → BUY/SELL/HOLD/NEUTRAL pill
│   ├── LiveIndicator.tsx           → WS connection dot
│   ├── Toast.tsx                   → Toast notifications
│   ├── ConfirmModal.tsx            → Confirmation dialog
│   ├── TradeModal.tsx              → Trade placement dialog
│   └── Providers.tsx               → React Query + other context providers
│
├── hooks/
│   ├── useDebouncedValue.ts        → Debounce hook (used in search inputs)
│   ├── useKeyboardShortcuts.ts     → Ctrl+K etc.
│   └── useRealtimeUpdates.ts       → WebSocket connection manager
│
└── lib/
    ├── api.ts                      → All fetch/axios calls to FastAPI
    ├── types.ts                    → TypeScript interfaces
    ├── format.ts                   → Number/date formatting helpers
    └── csv.ts                      → CSV export helper
```
