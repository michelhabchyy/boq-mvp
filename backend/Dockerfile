# Backend (FastAPI) container.
# Build context: the backend/ folder.  docker build -t boq-api .
#
# Python 3.14 is new; python:3.14-slim pulls prebuilt manylinux wheels for all
# deps. If a wheel is ever missing and pip tries to compile, either add
# build tooling (uncomment the apt line) or change the base to python:3.13-slim.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
COPY sample_data ./sample_data

# Config comes from environment variables (DATABASE_URL, AUTH_SECRET, keys, etc.)
# — no .env file is copied into the image.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
