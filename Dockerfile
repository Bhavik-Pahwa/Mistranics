FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications for layer caching
COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements-hardware.txt /app/backend/requirements-hardware.txt
COPY ML/requirements.txt /app/ML/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir \
    -r /app/backend/requirements.txt \
    -r /app/backend/requirements-hardware.txt \
    -r /app/ML/requirements.txt

# Copy source trees and simulation web assets
COPY backend/ /app/backend/
COPY ML/ /app/ML/
COPY Simulator.html /app/Simulator.html

# Ensure examples path compatibility
RUN ln -s /app/backend/examples /app/examples || true

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

