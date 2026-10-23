# Dockerfile for Munshi: Autonomous AI Bookkeeper & Forensic Audit OS
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PORT=8000 \
    MUNSHI_DB_PATH=/app/data/munshi.db

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create secure non-root user and group
RUN groupadd -g 10001 munshi && \
    useradd -u 10001 -g munshi -s /bin/bash -m munshiuser

# Copy requirements and install python packages
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e .

# Copy application source code
COPY munshi ./munshi
COPY data ./data
COPY frontend ./frontend
COPY tests ./tests
COPY benchmark_results.json EVALUATION_REPORT.md README.md LICENSE ./

# Set permissions for non-root user
RUN mkdir -p /app/data && \
    chown -R munshiuser:munshi /app

# Run full pytest suite during image build verification
RUN pytest -v

# Switch to non-root execution
USER munshiuser

# Expose web and API port
EXPOSE 8000

# Health check verifies ledger integrity and API responsiveness
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default execution: start production FastAPI REST API & mounted React UI
CMD ["uvicorn", "munshi.api:app", "--host", "0.0.0.0", "--port", "8000"]
