FROM python:3.10-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . 2>/dev/null || \
    pip install --no-cache-dir pandas numpy scikit-learn

# Copy source
COPY src/       ./src/
COPY configs/   ./configs/
COPY data/      ./data/
COPY scripts/   ./scripts/

# Create runtime dirs
RUN mkdir -p logs results/uat results/validation/approved results/validation/rejected

# Env
ENV PYTHONPATH="/app/src"
ENV PYTHONUNBUFFERED=1

# Ports: 8787 control plane, 8788 health check
EXPOSE 8787 8788

# Default: run health checker + control plane
CMD ["python", "-m", "monitoring.health_checker", "--port", "8788"]
