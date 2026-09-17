# Build from the repo root:  docker build -f docker/api.Dockerfile -t rag-api .
FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Dependencies first so they cache independently of source changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# uv.lock/pyproject.toml are only bind-mounted above (present for that RUN alone),
# so the project-install sync below needs its own real copies in the image.
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    FASTEMBED_CACHE_PATH=/opt/fastembed_cache

# Baked at build time, not on first request: bge-small is 70 MB, and the retriever
# already assumes it is warm (see analyst/embedding.py). Keeps container start cold-free
# and means the deploy target never needs outbound internet to serve a query.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5')"

RUN useradd --create-home --uid 1000 app \
    && chown -R app:app /opt/fastembed_cache
USER app

EXPOSE 8400
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8400/health', timeout=3)"

CMD ["uvicorn", "analyst.api:app", "--host", "0.0.0.0", "--port", "8400"]
