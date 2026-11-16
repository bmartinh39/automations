FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=0 \
    GRADIO_ANALYTICS_ENABLED=False

WORKDIR /app

# Cache dependency installation separately from application changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-cache

RUN useradd --create-home --uid 10001 app

COPY app.py context.py tools.py styles.py linkedin.pdf summary.txt ./

USER app

EXPOSE 7860

CMD ["/app/.venv/bin/python", "app.py"]
