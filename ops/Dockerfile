FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright (optional - only if using dynamic scraping)
# Uncomment if you implement Playwright-based scrapers
# RUN pip install --no-cache-dir playwright && \
#     playwright install chromium && \
#     playwright install-deps chromium

# Copy application code
COPY app/ ./app/
COPY configs/ ./configs/
COPY migrations/ ./migrations/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "-m", "app.main"]
