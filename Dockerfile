FROM python:3.11-slim

# Create mail-health-exporter user for security
RUN useradd --create-home --shell /bin/bash mail-health-exporter

# Update package list and install the required packages
RUN apt-get update && apt-get install -y \
    htop \
    tree \
    nano \
    sl \
    curl \
    telnet \
    # Clean up the package cache to reduce the image size
    && rm -rf /var/lib/apt/lists/*

# Install Python packages directly
RUN pip install --no-cache-dir \
    requests \
    beautifulsoup4

# Create app directory
WORKDIR /etc/mail-health-exporter

# Copy application files
COPY mail_health_exporter.py .
COPY status.html .
RUN chown -R mail-health-exporter:mail-health-exporter /etc/mail-health-exporter

# Switch to non-root user
USER mail-health-exporter

# Expose prometheus port
EXPOSE 9091

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9091/metrics')" || exit 1

# Run the application directly
CMD ["python", "mail_health_exporter.py"]
