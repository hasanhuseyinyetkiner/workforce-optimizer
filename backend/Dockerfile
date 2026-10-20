FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
  && uv sync --frozen --no-dev

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app
ENV HOST=0.0.0.0
ENV PORT=8103
ENV ALLOW_NETWORK_BIND=true

EXPOSE 8103
CMD ["python", "-m", "app.cli"]
