FROM python:3.13-slim

WORKDIR /app

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifest first for layer caching
COPY pyproject.toml .

# Install dependencies into /app/.venv (no editable install yet)
RUN uv venv .venv && \
    uv pip install --python .venv/bin/python -r pyproject.toml 2>/dev/null || \
    uv pip install --python .venv/bin/python .

# Copy application source
COPY src/ src/
COPY tests/ tests/

# Install the project itself (editable-style via src layout)
RUN uv pip install --python .venv/bin/python --no-deps -e .

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "crater"]
