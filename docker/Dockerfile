FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock* ./
COPY packages ./packages

RUN uv sync --all-packages --frozen 2>/dev/null || uv sync --all-packages

COPY . .

ENV SLM_OLLAMA_BASE_URL=http://host.docker.internal:11434
ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["slm"]
CMD ["--help"]
