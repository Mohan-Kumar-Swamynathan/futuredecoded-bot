FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir edge-tts

COPY . .

ENV PYTHONPATH=/app/src
ENV DATABASE_URL=sqlite:///database/futuredecoded.db

CMD ["python", "-m", "futuredecoded.main", "--daily", "--upload"]
