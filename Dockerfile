# Use slim Python image
FROM python:3.11-slim

# Install system deps for headless Chrome and utilities
RUN apt-get update && \
    apt-get install -y wget gnupg unzip fonts-liberation \
        libxss1 libappindicator3-1 libatk-bridge2.0-0 libatk1.0-0 \
        libgbm-dev libgtk-3-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 \
        libxdamage1 libxrandr2 libasound2 xvfb && \
    rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub \
      | apt-key add - \
 && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
      > /etc/apt/sources.list.d/google-chrome.list \
 && apt-get update \
 && apt-get install -y google-chrome-stable \
 && rm -rf /var/lib/apt/lists/*

# Install matching ChromeDriver
RUN CHROME_BIN=$(which google-chrome-stable || which google-chrome) \
 && echo "Using Chrome binary: $CHROME_BIN" \
 && MAJOR=$($CHROME_BIN --version | awk '{print $3}' | cut -d. -f1) \
 && echo "Detected Chrome major version: $MAJOR" \
 && LATEST=$(wget -qO- "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$MAJOR") \
 && echo "Downloading ChromeDriver version: $LATEST" \
 && wget -O /tmp/chromedriver.zip \
       "https://chromedriver.storage.googleapis.com/${LATEST}/chromedriver_linux64.zip" \
 && unzip /tmp/chromedriver.zip -d /usr/local/bin \
 && rm /tmp/chromedriver.zip

# Set working directory
WORKDIR /app

# Copy dependencies and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose port
ENV PORT 10000

# Start the app
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]
