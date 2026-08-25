# ── Stage 1: build deps ───────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps for PyMuPDF (libmupdf) and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy only installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/    app/
COPY jobs/   jobs/

# Non-root user for security
RUN useradd -r -u 1001 appuser
USER appuser

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Default command: run the monitor
CMD ["python", "-m", "jobs.run_monitor"]
