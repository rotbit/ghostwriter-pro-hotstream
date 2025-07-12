# Multi-stage build for GhostWriter Pro HotStream
FROM python:3.8-slim AS builder

# Set working directory
WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.8-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Create non-root user
RUN groupadd -r hotstream && useradd -r -g hotstream hotstream

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libxss1 \
    libasound2 \
    libxrandr2 \
    libatk1.0-0 \
    libdrm-dev \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libgtk-3-0 \
    curl \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libu2f-udev \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/hotstream/.local

# Copy application code
COPY . .

# Install application in development mode
RUN pip install -e .

# Install Playwright browsers
RUN python -m playwright install chromium

# Create necessary directories
RUN mkdir -p /app/output /app/logs /app/configs

# Set ownership
RUN chown -R hotstream:hotstream /app

# Switch to non-root user
USER hotstream

# Add local bin to PATH
ENV PATH=/home/hotstream/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import hotstream; print('OK')" || exit 1

# Expose port (if needed for web interface)
EXPOSE 8000

# Default command
CMD ["python", "-m", "hotstream.cli", "start"]