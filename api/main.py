"""
FastAPI application entry point.

Run locally:
    uvicorn api.main:app --reload --port 8000

Production:
    gunicorn api.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import init_postgres, close_postgres, init_pg_sync
from api.routes import auth, results, brokers, trades, stocks
from api.routes import bse_tools, monitor_rules, settings, ws, estimates


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    await init_postgres()
    init_pg_sync()
    yield
    await close_postgres()


app = FastAPI(
    title="BSE Result Analyser API",
    version="2.0.0",
    description="Financial result analysis, broker integration, and trade execution",
    lifespan=lifespan,
    redirect_slashes=False,
)

# ── CORS (restrict in production) ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        "https://*.onrender.com",
    ],
    # Matches any Cloudflare tunnel URL (trycloudflare.com = anonymous tunnels)
    allow_origin_regex=r"https://.*\.(trycloudflare\.com|cloudflareaccess\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Route mounts ──────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(results.router, prefix="/api/results", tags=["Results"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["Stocks"])
app.include_router(brokers.router, prefix="/api/brokers", tags=["Brokers"])
app.include_router(trades.router, prefix="/api/trades", tags=["Trades"])
app.include_router(bse_tools.router, prefix="/api/bse", tags=["BSE Tools"])
app.include_router(monitor_rules.router, prefix="/api/monitor", tags=["Monitor"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(estimates.router, prefix="/api/estimates", tags=["Estimates"])
app.include_router(ws.router, tags=["WebSocket"])


@app.get("/health")
async def health():
    return {"status": "ok"}
