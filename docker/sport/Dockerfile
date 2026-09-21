# syntax=docker/dockerfile:1

FROM python:3.14.6-slim-trixie@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid 10001 apigroup \
    && useradd --create-home --uid 10001 --gid apigroup apiuser

COPY pyproject.toml ./
COPY --chown=apiuser:apigroup app/__init__.py ./app/__init__.py
COPY --chown=apiuser:apigroup app/core ./app/core
COPY --chown=apiuser:apigroup app/sport ./app/sport

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install .

LABEL org.opencontainers.image.description="Sport API for api.dalae37.com" \
      org.opencontainers.image.licenses="BSD-3-Clause" \
      org.opencontainers.image.source="https://github.com/DaLae37/api.dalae37.com"

USER apiuser

# HTTPS is terminated by the reverse proxy; this container receives HTTP traffic.
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:80/healthz', timeout=2)"]

CMD ["uvicorn", "app.sport.main:app", "--host", "0.0.0.0", "--port", "80"]
