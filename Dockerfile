FROM python:3.13-slim

# Prevent Python from writing .pyc files and enable unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system deps only if you actually need them (kept minimal here)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential \
#     && rm -rf /var/lib/apt/lists/*

# 1. Copy the pre-built distribution wheel into the container
COPY dist/*.whl .

# 2. Install the wheel file using pip
# (This automatically pulls down dependencies and sets up your 'vectorize' CLI)
RUN pip install --no-cache-dir *.whl

# Default command (override at runtime if needed)
ENTRYPOINT ["/bin/sh", "-c","exec vectorize embed -F \"$@\" >> /logs/vectorizer-$(date +%Y-%m-%dT%H-%M-%S).log 2>&1","--"]
