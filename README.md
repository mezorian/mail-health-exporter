# mail-health-exporter
A simple prometheus exporter that reports about the health of your mail-server!

The health-check is a 2 steps process:

1. Do a send-receive check
2. Check the spam-score of sent messages

For a more detailed explanation what each step is doing see below

After each health-check the program will export its results in two formats:
- **Prometheus metrics** at http://localhost:9091/metrics for monitoring systems
- **Web dashboard** at http://localhost:9091/status showing a human-readable status page

The health-check is performed every 5 minutes, the spam-score check only every 8 hours.

## Monitoring Endpoints

The service provides two HTTP endpoints:

- **`/metrics`** - Prometheus exposition format for scraping by monitoring systems
- **`/status`** - Web dashboard displaying:
  - Whether the mail-server is able to send messages
  - Whether the mail-server is able to receive messages
  - Current spam-score of sent messages by the server

## Quick Start

### Prerequisites

- Docker and Docker Compose (Option 1) or Portainer (Option 2) installed
- Email accounts configured for monitoring on both internal and external servers

## Deployment Options

### Option 1: Docker Compose with Environment Variables

This approach stores passwords directly in environment variables (simpler but less secure).

#### 1. Prepare the Configuration

Copy `docker-compose.template.yml` to `docker-compose.yml`:

```bash
cp docker-compose.template.yml docker-compose.yml
```

#### 2. Edit the Configuration

Open `docker-compose.yml` and make the following changes:

1. **Remove the secrets section** (lines 4-8):
   ```yaml
   # COMMENT/DISABLE THESE LINES:
   secrets:
     internal_email_password:
       external: true
     external_email_password:
       external: true
   ```

2. **Remove secrets from the service** (lines 18-21):
   ```yaml
   # COMMENT/DISABLE THESE LINES:
   secrets:
     - internal_email_password
     - external_email_password
   ```

3. **Uncomment and configure the password environment variables**:
   ```yaml
   - INTERNAL_EMAIL_PASSWORD=your_internal_email_password_here
   - EXTERNAL_EMAIL_PASSWORD=your_external_email_password_here
   ```

4. **Update all configuration values**:
   ```yaml
   # Internal mail server
   - INTERNAL_SMTP_SERVER=your-internal-server.com
   - INTERNAL_EMAIL_ADDRESS=monitoring@your-internal-server.com
   
   # External mail server (example with Gmail)
   - EXTERNAL_SMTP_SERVER=smtp.gmail.com
   - EXTERNAL_EMAIL_ADDRESS=your-external-email@gmail.com
   
   # Spam score testing
   - SPAM_SCORE_TEST_EMAIL_ADDRESS=test-YOUR_UNIQUE_ID@srv1.mail-tester.com
   - SPAM_SCORE_TEST_URL=https://www.mail-tester.com/test-YOUR_UNIQUE_ID
   ```

#### 3. Deploy

```bash
docker-compose up -d
```

#### 4. Verify Deployment

Check that the service is running:
```bash
docker-compose ps
docker-compose logs mail-health-exporter
```

Access the monitoring interfaces:
- **Metrics**: `http://localhost:9091/metrics`
- **Status Dashboard**: `http://localhost:9091/status`

---

### Option 2: Portainer with Docker Secrets

This approach uses Docker secrets for secure password management.

#### 1. Create Docker Secrets

In Portainer, navigate to **Secrets** and create two new secrets:

1. **Secret Name**: `internal_email_password`
   - **Secret**: Your internal email password

2. **Secret Name**: `external_email_password`
   - **Secret**: Your external email password

#### 2. Create the Stack

1. Go to **Stacks** in Portainer
2. Click **Add stack**
3. Name your stack (e.g., `mail-health-exporter`)
4. Paste the contents of `docker-compose.template.yml`
5. **Configure the environment variables** in the stack configuration:

#### 3. Deploy the Stack

Click **Deploy the stack**

#### 4. Verify Deployment

1. Check the stack status in Portainer
2. View container logs
3. Access the monitoring interfaces:
   - **Metrics**: `http://localhost:9091/metrics`
   - **Status Dashboard**: `http://localhost:9091/status`

## Password Configuration

**With Docker Secrets** (recommended):
- Passwords are read from `/run/secrets/internal_email_password` and `/run/secrets/external_email_password`
- Secrets must be named exactly `internal_email_password` and `external_email_password`

**With Environment Variables** (simpler):
- Set `INTERNAL_EMAIL_PASSWORD` and `EXTERNAL_EMAIL_PASSWORD` environment variables
- Remove the secrets section from docker-compose.yml

## Troubleshooting

### Common Issues

1. **Authentication Failures**:
   - Verify email credentials
   - Check if 2FA is enabled (use app passwords for Gmail)
   - Ensure IMAP/SMTP access is enabled

2. **Connection Issues**:
   - Verify server hostnames and ports
   - Check firewall rules
   - Confirm TLS/SSL settings

3. **Container Won't Start**:
   - Check Docker logs: `docker-compose logs mail-health-exporter`
   - Verify all required environment variables are set
   - Ensure secrets are properly created (if using Docker secrets)

4. **Web Interface Issues**:
   - Verify port 9091 is accessible
   - Check firewall rules for HTTP access
   - Ensure the service is healthy using `docker-compose ps`

### Logs

View container logs:
```bash
# Docker Compose
docker-compose logs -f mail-health-exporter

# Portainer
# View logs through the Portainer web interface
```

### Health Check

The container includes a health check that verifies the metrics endpoint is accessible:
```bash
docker-compose ps  # Shows health status
```

You can also manually verify both endpoints are working:
```bash
# Check metrics endpoint
curl http://localhost:9091/metrics

# Check status dashboard (returns HTML)
curl http://localhost:9091/status
```

## Security Considerations

- **Use Docker Secrets** when possible for production deployments
- **Restrict network access** to the monitoring ports (9091) - consider using a reverse proxy
- **Use dedicated monitoring email accounts** with minimal privileges
- **Regularly rotate passwords** used for monitoring
- **Monitor the monitoring service** - set up alerts for when this service fails
- **Secure the web dashboard** - consider adding authentication if exposing publicly

# What is the Health-Check doing? 


