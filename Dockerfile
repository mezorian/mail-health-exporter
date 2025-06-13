FROM python:3.11-slim

# Create mail-health-exporter user for security
RUN useradd --create-home --shell /bin/bash mail-health-exporter

# Install Python packages directly
RUN pip install --no-cache-dir \
    requests \
    beautifulsoup4

# Create app directory
WORKDIR /etc/mail-health-exporter

# Copy application files
COPY mail_health_exporter.py .
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
