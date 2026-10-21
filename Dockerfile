# Dockerfile for Munshi: Autonomous AI Bookkeeper & Forensic Audit OS
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

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

# Run full pytest suite during image build verification
RUN pytest -v

# Expose web dashboard port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/index.html || exit 1

# Default execution: serve interactive web dashboard
CMD ["python", "-m", "munshi.cli", "web", "--port", "8000", "--no-browser"]
