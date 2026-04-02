# =============================================================================
# Stage 1 — builder
# Install all dependencies into an isolated venv so the runtime stage only
# needs to copy /opt/venv without any build tooling.
# =============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# gcc is required to compile bcrypt's C extension
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

# Create the virtual environment once and reuse it in the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# =============================================================================
# Stage 2 — runtime
# Minimal image: no compiler, no pip, no build cache.
# Runs as a non-root user with a read-only filesystem.
# =============================================================================
FROM python:3.12-slim AS runtime

# Create a non-root user/group (UID/GID 1001)
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home --shell /sbin/nologin appuser

WORKDIR /app

# Pull only the finished venv from the builder — no compiler lands here
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

# Copy application source (chowned to appuser so no root-owned files at runtime)
COPY --chown=appuser:appgroup app/    ./app/
COPY --chown=appuser:appgroup main.py ./

USER appuser

EXPOSE 8000

# Lightweight stdlib-only healthcheck — no extra binary needed
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c \
        "import urllib.request, sys; \
         r = urllib.request.urlopen('http://localhost:8000/health', timeout=5); \
         sys.exit(0 if r.status == 200 else 1)"

# --no-access-log  : suppress uvicorn's own access lines (our middleware does it)
# --proxy-headers  : trust X-Forwarded-* from the ingress
# --forwarded-allow-ips : accept forwarded headers from any upstream (restrict in prod)
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-access-log", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
