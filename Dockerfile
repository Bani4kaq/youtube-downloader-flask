FROM python:3.11-slim

# ffmpeg is the whole reason we're using a Dockerfile instead of Render's
# plain Python environment, this guarantees it's installed and on PATH.
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render injects $PORT at runtime; shell form lets that env var expand.
CMD gunicorn -b 0.0.0.0:$PORT app:app
