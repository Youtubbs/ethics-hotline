# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

WORKDIR /build

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir --prefix=/install .


FROM python:3.11-slim AS runtime

RUN useradd --system --create-home --uid 1001 appuser

ENV PYTHONUNBUFFERED=1 \
    FLASK_APP=ethics_hotline.app:create_app

COPY --from=builder /install /usr/local

WORKDIR /app
COPY . .

USER appuser

EXPOSE 8000

ENTRYPOINT ["python", "entrypoint.py"]
