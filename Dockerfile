# ─── Base image ────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ─── Install system deps & headless Chrome ────────────────────────────────────
RUN apt-get update && apt-get install -y \
    wget gnupg2 unzip fonts-liberation \
    libxss1 libappindicator3-1 libatk-bridge2.0-0 libatk1.0-0 \
    libgbm-dev libgtk-3-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 \
    libxdamage1 libxrandr2 libasound2 xvfb \
  && rm -rf /var/lib/apt/lists/* \
  && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub \
       | apt-key add - \
  && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
  && apt-get update && apt-get install -y google-chrome-stable \
  && rm -rf /var/lib/apt/lists/*

# ─── App setup ─────────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# ─── Runtime ──────────────────────────────────────────────────────────────────
ENV PORT=10000
EXPOSE 10000
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]
