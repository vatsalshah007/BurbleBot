# syntax=docker/dockerfile:1
#
# Target platform: linux/arm64 (Raspberry Pi 5)
# Base image version must match the pinned playwright==1.61.0 in requirements.txt
FROM --platform=linux/arm64 mcr.microsoft.com/playwright/python:v1.61.0-jammy

WORKDIR /app

# Install Python dependencies first (layer-cached until requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY main.py .
COPY app/ ./app/

# .env.example for documentation — actual .env is injected at runtime
COPY .env.example .

# Run as non-root user for defence-in-depth
# (the playwright base image includes a non-root 'pwuser')
USER pwuser

CMD ["python", "main.py"]