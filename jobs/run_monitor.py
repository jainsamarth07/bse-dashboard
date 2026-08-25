"""
Monitor entry point.

Usage
-----
    python -m jobs.run_monitor
or
    python jobs/run_monitor.py

Override the poll interval via env var:
    POLL_INTERVAL=30 python -m jobs.run_monitor
"""

from app.config import Config
from app.core.monitor import run

if __name__ == "__main__":
    run(interval=Config.POLL_INTERVAL)
