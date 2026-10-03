# syntax=docker/dockerfile:1
FROM python:3.13-slim

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Generate deterministic baseline dataset and initialize warehouse
RUN python scripts/generate_dataset.py --num-assets 5000 --seed 42 && \
    python scripts/simulate_annotations.py --count 25000 --seed 42 && \
    python scripts/run_pipeline.py

# Expose Streamlit dashboard (8501) and Workstation API (8000)
EXPOSE 8501
EXPOSE 8000

# Healthcheck for Streamlit
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default: Launch Streamlit Executive Dashboard
CMD ["streamlit", "run", "app/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
