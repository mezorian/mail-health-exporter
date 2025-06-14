#!/usr/bin/env python3
"""
Mail Health Exporter - A Prometheus-based email monitoring system.

This module provides comprehensive email server monitoring by testing mail sending,
receiving, and spam score evaluation. It exposes metrics via a Prometheus endpoint
for integration with monitoring systems.
"""

import smtplib
import imaplib
import email
import time
import logging
import threading
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import sys
from datetime import datetime, timedelta
from typing import Optional, Union

import requests
import re
from bs4 import BeautifulSoup


# ===== METRICS AND PROMETHEUS CLASSES =====

class MetricsStore:
    """
    Thread-safe storage for Prometheus metrics.

    This class maintains counters and gauges for various email health metrics
    and provides thread-safe access to update and retrieve them in Prometheus format.

    Attributes
    ----------
    lock : threading.Lock
        Thread synchronization lock for safe metric updates
    metrics : dict
        Dictionary containing all metric names and their current values
    """

    def __init__(self):
        """
        Initialize the metrics store with default values.

        Sets up all mail health metrics including counters for send/receive operations,
        gauges for service status, and timestamps for monitoring freshness.
        """
        self.lock = threading.Lock()
        self.metrics = {
            'mail_health_exporter__send_internal_to_external_success_total': 0,
            'mail_health_exporter__send_internal_to_external_failures_total': 0,
            'mail_health_exporter__receive_internal_to_external_success_total': 0,
            'mail_health_exporter__receive_internal_to_external_failures_total': 0,
            'mail_health_exporter__send_external_to_internal_success_total': 0,
            'mail_health_exporter__send_external_to_internal_failures_total': 0,
            'mail_health_exporter__receive_external_to_internal_success_total': 0,
            'mail_health_exporter__receive_external_to_internal_failures_total': 0,
            'mail_health_exporter__sending_mails_working': 1,
            'mail_health_exporter__receiving_mails_working': 1,
            'mail_health_exporter__roundtrip_duration_seconds': 0,
            'mail_health_exporter__last_send_receive_check_timestamp': time.time(),
            'mail_health_exporter__spam_score': 0,
            'mail_health_exporter__last_spam_score_check_timestamp': time.time()
        }

    def increment(self, metric_name: str) -> None:
        """
        Thread-safely increment a counter metric by 1.

        Parameters
        ----------
        metric_name : str
            Name of the metric to increment
        """
        with self.lock:
            self.metrics[metric_name] += 1

    def set_value(self, metric_name: str, value: Union[int, float]) -> None:
        """
        Thread-safely set a metric to a specific value.

        Parameters
        ----------
        metric_name : str
            Name of the metric to update
        value : Union[int, float]
            New value to set for the metric
        """
        with self.lock:
            self.metrics[metric_name] = value

    def get_prometheus_format(self) -> str:
        """
        Generate Prometheus-formatted metrics output.

        Returns
        -------
        str
            Complete Prometheus metrics output with HELP and TYPE declarations
        """
        with self.lock:
            output = []

            output.append(
                '# HELP mail_health_exporter__send_internal_to_external_success_total Total successful mail sends from internal to external')
            output.append('# TYPE mail_health_exporter__send_internal_to_external_success_total counter')
            output.append(
                f'mail_health_exporter__send_internal_to_external_success_total {self.metrics["mail_health_exporter__send_internal_to_external_success_total"]}')

            output.append(
                '# HELP mail_health_exporter__send_internal_to_external_failures_total Total failed mail sends from internal to external')
            output.append('# TYPE mail_health_exporter__send_internal_to_external_failures_total counter')
            output.append(
                f'mail_health_exporter__send_internal_to_external_failures_total {self.metrics["mail_health_exporter__send_internal_to_external_failures_total"]}')

            output.append(
                '# HELP mail_health_exporter__receive_internal_to_external_success_total Total successful mail receivs from internal to external')
            output.append('# TYPE mail_health_exporter__receive_internal_to_external_success_total counter')
            output.append(
                f'mail_health_exporter__receive_internal_to_external_success_total {self.metrics["mail_health_exporter__receive_internal_to_external_success_total"]}')

            output.append(
                '# HELP mail_health_exporter__receive_internal_to_external_failures_total Total failed mail receivs from internal to external')
            output.append('# TYPE mail_health_exporter__receive_internal_to_external_failures_total counter')
            output.append(
                f'mail_health_exporter__receive_internal_to_external_failures_total {self.metrics["mail_health_exporter__receive_internal_to_external_failures_total"]}')

            output.append(
                '# HELP mail_health_exporter__send_external_to_internal_success_total Total successful mail sends from external to internal')
            output.append('# TYPE mail_health_exporter__send_external_to_internal_success_total counter')
            output.append(
                f'mail_health_exporter__send_external_to_internal_success_total {self.metrics["mail_health_exporter__send_external_to_internal_success_total"]}')

            output.append(
                '# HELP mail_health_exporter__send_external_to_internal_failures_total Total failed mail sends from external to internal')
            output.append('# TYPE mail_health_exporter__send_external_to_internal_failures_total counter')
            output.append(
                f'mail_health_exporter__send_external_to_internal_failures_total {self.metrics["mail_health_exporter__send_external_to_internal_failures_total"]}')

            output.append(
                '# HELP mail_health_exporter__receive_external_to_internal_success_total Total successful mail receivs from external to internal')
            output.append('# TYPE mail_health_exporter__receive_external_to_internal_success_total counter')
            output.append(
                f'mail_health_exporter__receive_external_to_internal_success_total {self.metrics["mail_health_exporter__receive_external_to_internal_success_total"]}')

            output.append(
                '# HELP mail_health_exporter__receive_external_to_internal_failures_total Total failed mail receivs from external to internal')
            output.append('# TYPE mail_health_exporter__receive_external_to_internal_failures_total counter')
            output.append(
                f'mail_health_exporter__receive_external_to_internal_failures_total {self.metrics["mail_health_exporter__receive_external_to_internal_failures_total"]}')

            output.append(
                '# HELP mail_health_exporter__sending_mails_working Status whether the server is able to send mails or not')
            output.append('# TYPE mail_health_exporter__sending_mails_working gauge')
            output.append(
                f'mail_health_exporter__sending_mails_working {self.metrics["mail_health_exporter__sending_mails_working"]}')

            output.append(
                '# HELP mail_health_exporter__receiving_mails_working Status whether the server is able to receive mails or not')
            output.append('# TYPE mail_health_exporter__receiving_mails_working gauge')
            output.append(
                f'mail_health_exporter__receiving_mails_working {self.metrics["mail_health_exporter__receiving_mails_working"]}')

            output.append(
                '# HELP mail_health_exporter__roundtrip_duration_seconds Duration of last full internal->external->internal mail roundtrip')
            output.append('# TYPE mail_health_exporter__roundtrip_duration_seconds gauge')
            output.append(
                f'mail_health_exporter__roundtrip_duration_seconds {self.metrics["mail_health_exporter__roundtrip_duration_seconds"]}')

            output.append(
                '# HELP mail_health_exporter__last_send_receive_check_timestamp Timestamp of last send-receive check')
            output.append('# TYPE mail_health_exporter__last_send_receive_check_timestamp gauge')
            output.append(
                f'mail_health_exporter__last_send_receive_check_timestamp {self.metrics["mail_health_exporter__last_send_receive_check_timestamp"]}')

            output.append('# HELP mail_health_exporter__spam_score Spam score of send mails')
            output.append('# TYPE mail_health_exporter__spam_score gauge')
            output.append(f'mail_health_exporter__spam_score {self.metrics["mail_health_exporter__spam_score"]}')

            output.append(
                '# HELP mail_health_exporter__last_spam_score_check_timestamp Timestamp of last spam-score check')
            output.append('# TYPE mail_health_exporter__last_spam_score_check_timestamp gauge')
            output.append(
                f'mail_health_exporter__last_spam_score_check_timestamp {self.metrics["mail_health_exporter__last_spam_score_check_timestamp"]}')

            return '\n'.join(output)

    def get_status_data(self) -> dict:
        """
        Get current metrics data for the status page.

        Returns
        -------
        dict
            Dictionary containing sendingWorks, receivingWorks, and spamScore values
        """
        with self.lock:
            return {
                'sendingWorks': bool(self.metrics['mail_health_exporter__sending_mails_working']),
                'receivingWorks': bool(self.metrics['mail_health_exporter__receiving_mails_working']),
                'spamScore': int(self.metrics['mail_health_exporter__spam_score']),
                'sendingWorksLastUpdated': float(self.metrics['mail_health_exporter__last_send_receive_check_timestamp']),
                'receivingWorksLastUpdated': float(
                    self.metrics['mail_health_exporter__last_send_receive_check_timestamp']),
                'spamScoreLastUpdated': float(
                    self.metrics['mail_health_exporter__last_spam_score_check_timestamp'])
            }


class HTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for Prometheus metrics endpoint and status page.

    Handles GET requests to /metrics endpoint and /status endpoint, returns 404 for others.

    Attributes
    ----------
    metrics_store : MetricsStore
        Reference to the metrics storage instance
    status_html : str
        The HTML content for the status page
    """

    def __init__(self, request, client_address, server, metrics_store: MetricsStore = None, status_html_template: str = "Put your html here"):
        """
        Initialize the HTTP request handler.

        Parameters
        ----------
        request : socket
            The request socket
        client_address : tuple
            Client address information
        server : HTTPServer
            The HTTP server instance
        metrics_store : MetricsStore, optional
            Reference to metrics storage, by default None
        status_html_template : str, optional
            HTML content for status page, by default "Put your html here"
            This variable describes the template html.
            Each Get-request will use this template and update it according
            current values in the metrics store
        """
        self.metrics_store = metrics_store
        self.status_html_template = status_html_template
        super().__init__(request, client_address, server)

    def do_GET(self) -> None:
        """
        Handle GET requests.

        Serves Prometheus metrics on /metrics endpoint, status page on /status endpoint,
        returns 404 for all other paths.
        """
        if self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(self.metrics_store.get_prometheus_format().encode('utf-8'))
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self._get_updated_status_html().encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        """
        Override default HTTP server logging to suppress log messages.

        Parameters
        ----------
        format : str
            Log format string (ignored)
        *args
            Log arguments (ignored)
        """
        # Suppress default HTTP server logging
        pass

    def _get_updated_status_html(self) -> str:
        """
        Update the HTML template with current metrics data.

        Replaces the mailServerData JavaScript object in the HTML template
        with current values from the metrics store.

        Returns
        -------
        str
            Updated HTML content with current metrics data
        """
        status_data = self.metrics_store.get_status_data()

        # Create the replacement JavaScript object
        replacement_js = f"""let mailServerData = {{
    sendingWorks: {str(status_data['sendingWorks']).lower()},
    receivingWorks: {str(status_data['receivingWorks']).lower()},
    spamScore: {status_data['spamScore']},
    lastUpdated: {{
                sending: {status_data['sendingWorksLastUpdated']},
                receiving: {status_data['receivingWorksLastUpdated']},
                spam: {status_data['spamScoreLastUpdated']}
            }}
}};"""

        # Use regex to replace the existing mailServerData object
        pattern = r'let\s+mailServerData\s*=\s*\{(?:[^{}]*(?:\{[^{}]*\})*)*\};'
        updated_html = re.sub(pattern, replacement_js, self.status_html_template, flags=re.MULTILINE | re.DOTALL)

        return updated_html

# ===== MAIN APPLICATION CLASS =====

class MailHealthExporter:
    """
    Main application class for monitoring email server health.

    This class orchestrates email testing by sending test messages between
    internal and external mail servers, checking for delivery, and monitoring
    spam scores. It exposes metrics via a Prometheus HTTP endpoint.

    Attributes
    ----------
    metrics : MetricsStore
        Metrics storage instance
    logger : logging.Logger
        Application logger
    running : bool
        Service running state flag
    status_html_template : str
        HTML template for the status page
    status_html_file : str
        Path to the status HTML file
    internal_smtp_server : str
        Internal SMTP server hostname
    internal_smtp_port : int
        Internal SMTP server port
    internal_smtp_use_tls : bool
        Whether to use TLS for internal SMTP
    internal_imap_server : str
        Internal IMAP server hostname
    internal_imap_port : int
        Internal IMAP server port
    internal_imap_use_ssl : bool
        Whether to use SSL for internal IMAP
    internal_email_address : str
        Internal email account address
    internal_email_password : str
        Internal email account password
    external_smtp_server : str
        External SMTP server hostname
    external_smtp_port : int
        External SMTP server port
    external_smtp_use_tls : bool
        Whether to use TLS for external SMTP
    external_imap_server : str
        External IMAP server hostname
    external_imap_port : int
        External IMAP server port
    external_imap_use_ssl : bool
        Whether to use SSL for external IMAP
    external_email_address : str
        External email account address
    external_email_password : str
        External email account password
    spam_score_test_email_address : str
        Email address for spam score testing
    spam_score_test_url : str
        URL for retrieving spam test results
    last_spam_score_check_timestamp : datetime
        Timestamp of last spam score check
    check_interval : int
        Interval between health checks in seconds
    timeout_seconds : int
        Timeout for email operations in seconds
    metrics_port : int
        Port for Prometheus metrics server
    """

    def __init__(self):
        """
        Initialize the Mail Health Exporter.

        Loads configuration from environment variables and Docker secrets,
        validates required parameters, and sets up logging.

        Raises
        ------
        ValueError
            If required environment variables or secrets are missing
        """
        self.metrics = MetricsStore()
        self.logger = self._setup_logging()
        self.running = False
        self.status_html_template = ""
        
        # Status HTML file configuration
        self.status_html_file = os.getenv('STATUS_HTML_FILE', 'status.html')

        # Internal mail server configuration
        self.internal_smtp_server = os.getenv('INTERNAL_SMTP_SERVER')
        self.internal_smtp_port = int(os.getenv('INTERNAL_SMTP_PORT', '465'))
        self.internal_smtp_use_tls = os.getenv('INTERNAL_SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')
        self.internal_imap_server = os.getenv('INTERNAL_IMAP_SERVER')
        self.internal_imap_port = int(os.getenv('INTERNAL_IMAP_PORT', '993'))
        self.internal_imap_use_ssl = os.getenv('INTERNAL_IMAP_USE_SSL', 'true').lower() in ('true', '1', 'yes')
        self.internal_email_address = os.getenv('INTERNAL_EMAIL_ADDRESS')
        self.internal_email_password = self._read_password_from_docker_secret('internal_email_password')

        # External mail server configuration
        self.external_smtp_server = os.getenv('EXTERNAL_SMTP_SERVER')
        self.external_smtp_port = int(os.getenv('EXTERNAL_SMTP_PORT', '465'))
        self.external_smtp_use_tls = os.getenv('EXTERNAL_SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')
        self.external_imap_server = os.getenv('EXTERNAL_IMAP_SERVER')
        self.external_imap_port = int(os.getenv('EXTERNAL_IMAP_PORT', '993'))
        self.external_imap_use_ssl = os.getenv('EXTERNAL_IMAP_USE_SSL', 'true').lower() in ('true', '1', 'yes')
        self.external_email_address = os.getenv('EXTERNAL_EMAIL_ADDRESS')
        self.external_email_password = self._read_password_from_docker_secret('external_email_password')

        # Spam score test configuration
        self.spam_score_test_email_address = os.getenv('SPAM_SCORE_TEST_EMAIL_ADDRESS')
        self.spam_score_test_url = os.getenv('SPAM_SCORE_TEST_URL')
        self.last_spam_score_check_timestamp = datetime.now() - timedelta(hours=24)

        # Test configuration
        self.check_interval = int(os.getenv('CHECK_INTERVAL_SECONDS', '300'))
        self.timeout_seconds = int(os.getenv('TIMEOUT_SECONDS', '60'))

        # Prometheus configuration
        self.metrics_port = int(os.getenv('HTTP_PORT', '9091'))

        # Validate required environment variables
        required_vars = [
            'INTERNAL_SMTP_SERVER', 'INTERNAL_IMAP_SERVER',
            'INTERNAL_EMAIL_ADDRESS',
            'EXTERNAL_SMTP_SERVER', 'EXTERNAL_IMAP_SERVER',
            'EXTERNAL_EMAIL_ADDRESS',
            'SPAM_SCORE_TEST_EMAIL_ADDRESS', 'SPAM_SCORE_TEST_URL'
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        # Validate required secrets
        if not self.internal_email_password:
            raise ValueError("Missing required secret: internal_email_password")
        if not self.external_email_password:
            raise ValueError("Missing required secret: external_email_password")

        # Load status HTML template
        self._load_status_html_template()

    # ===== CONFIGURATION AND SETUP METHODS =====

    def _load_status_html_template(self) -> None:
        """
        Load the HTML template for the status page from file.

        Reads the HTML file specified in STATUS_HTML_FILE environment variable
        (defaults to 'status.html') and stores it as a template for serving
        at the /status endpoint.

        Raises
        ------
        FileNotFoundError
            If the status HTML file cannot be found
        """
        try:
            with open(self.status_html_file, 'r', encoding='utf-8') as f:
                self.status_html_template = f.read()
            self.logger.info(f'Successfully loaded status HTML template from {self.status_html_file}')
        except FileNotFoundError:
            self.logger.error(f'Status HTML file not found: {self.status_html_file}')
            raise
        except Exception as e:
            self.logger.error(f'Error loading status HTML template: {e}')
            raise

    def _read_password_from_docker_secret(self, secret_name: str) -> Optional[str]:
        """
        Read password from Docker secret or environment variable.

        Attempts to read from Docker secrets first (/run/secrets/), then falls
        back to environment variables for development environments.

        Parameters
        ----------
        secret_name : str
            Name of the secret/environment variable to read

        Returns
        -------
        Optional[str]
            The secret value if found, None otherwise
        """
        # Try Docker secret first (for Portainer production)
        secret_path = f"/run/secrets/{secret_name}"
        if os.path.exists(secret_path):
            with open(secret_path, 'r') as f:
                return f.read().strip()

        # Fall back to environment variable (for development)
        env_name = secret_name.upper()
        env_value = os.getenv(env_name)
        if env_value:
            return env_value

        return None

    def _setup_logging(self) -> logging.Logger:
        """
        Set up logging optimized for Docker containers.

        Logs INFO+ to stdout and ERROR+ to stderr for proper container log handling.
        File logging is completely disabled for container compatibility.

        Returns
        -------
        logging.Logger
            Configured logger instance for the application
        """
        # Clear any existing handlers to avoid duplicates
        logging.getLogger().handlers.clear()

        # Create formatters
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Set up stdout handler for INFO and above
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(logging.INFO)
        stdout_handler.setFormatter(formatter)

        # Set up stderr handler for ERROR and above
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.ERROR)
        stderr_handler.setFormatter(formatter)

        # Configure root logger
        root_logger = logging.getLogger()
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        root_logger.setLevel(getattr(logging, log_level, logging.INFO))

        # Add handlers
        root_logger.addHandler(stdout_handler)
        root_logger.addHandler(stderr_handler)

        # Return application-specific logger
        return logging.getLogger('mail-health-exporter')

    # ===== EMAIL SENDING AND RECEIVING METHODS =====

    def send_test_email(self, from_address: str, to_address: str, unique_id: str) -> bool:
        """
        Send a test email with unique identifier.

        Sends a test email using the appropriate SMTP server based on the sender
        address. Updates metrics based on success/failure.

        Parameters
        ----------
        from_address : str
            Sender email address (must be internal or external address)
        to_address : str
            Recipient email address
        unique_id : str
            Unique identifier for tracking the test email

        Returns
        -------
        bool
            True if email was sent successfully, False otherwise
        """
        success = True

        try:
            if (from_address == self.internal_email_address):
                email_address = self.internal_email_address
                email_password = self.internal_email_password
                smtp_server = self.internal_smtp_server
                smtp_port = self.internal_smtp_port
                use_tls = self.internal_smtp_use_tls
            elif (from_address == self.external_email_address):
                email_address = self.external_email_address
                email_password = self.external_email_password
                smtp_server = self.external_smtp_server
                smtp_port = self.external_smtp_port
                use_tls = self.external_smtp_use_tls
            else:
                self.logger.error("Function send_test_email failed: from_address '{}' was neither internal address "
                                  "'{}' nor external address '{}'".format(from_address, self.internal_email_address,
                                                                          self.external_email_address))
                success = False

            if success:
                msg = MIMEMultipart()
                msg['From'] = from_address
                msg['To'] = to_address
                msg['Subject'] = f'Mail Health Exporter - {unique_id}'
                msg['Date'] = formatdate(localtime=True)
                msg['Message-ID'] = make_msgid()
                msg['X-Mailer'] = 'Python SMTP Client'

                body = f"""
                This is an automated test email from the mail health exporter service.

                Test ID: {unique_id}
                Timestamp: {datetime.now().isoformat()}

                This email should be automatically processed and deleted.
                """

                msg.attach(MIMEText(body, 'plain'))

                # For SSL/TLS servers (usually port 465)
                if use_tls and smtp_port == 465:
                    server = smtplib.SMTP_SSL(smtp_server, smtp_port)
                else:
                    # For STARTTLS servers (usually port 587) or plain SMTP (port 25)
                    server = smtplib.SMTP(smtp_server, smtp_port)
                    if use_tls:
                        server.starttls()

                server.login(email_address, email_password)
                server.send_message(msg)
                server.quit()

                self.logger.info(f'Successfully sent test email with ID: {unique_id}')
                success = True

        except Exception as e:
            self.logger.error(f'Failed to send test email: {e}')
            success = False

        if success:
            self.metrics.set_value('mail_health_exporter__sending_mails_working', 1)

            if (from_address == self.internal_email_address):
                self.metrics.increment('mail_health_exporter__send_internal_to_external_success_total')
            else:
                self.metrics.increment('mail_health_exporter__send_external_to_internal_success_total')
        else:
            self.metrics.set_value('mail_health_exporter__sending_mails_working', 0)

            if (from_address == self.internal_email_address):
                self.metrics.increment('mail_health_exporter__send_internal_to_external_failures_total')
            else:
                self.metrics.increment('mail_health_exporter__send_external_to_internal_failures_total')

        return success

    def check_inbox_for_test_email(self, from_address: str, to_address: str, unique_id: str,
                                   max_wait_time: int = 300) -> bool:
        """
        Check for and delete a test email from an inbox.

        Polls the specified inbox for a test email with the given unique ID,
        deletes it when found, and updates metrics accordingly.

        Parameters
        ----------
        from_address : str
            Expected sender address of the test email
        to_address : str
            Recipient address (determines which inbox to check)
        unique_id : str
            Unique identifier to search for in email subjects
        max_wait_time : int, optional
            Maximum time to wait for email in seconds, by default 300

        Returns
        -------
        bool
            True if email was found and deleted successfully, False otherwise
        """
        success = True

        if (to_address == self.internal_email_address):
            email_address = self.internal_email_address
            email_password = self.internal_email_password
            imap_server = self.internal_imap_server
            imap_port = self.internal_imap_port
            imap_use_ssl = self.internal_imap_use_ssl
        elif (to_address == self.external_email_address):
            email_address = self.external_email_address
            email_password = self.external_email_password
            imap_server = self.external_imap_server
            imap_port = self.external_imap_port
            imap_use_ssl = self.external_imap_use_ssl
        else:
            self.logger.error(
                "Function check_inbox_for_test_email failed: to_address '{}' was neither from internal server "
                "'{}' nor external server '{}'".format(to_address, self.internal_email_address,
                                                       self.external_email_address))
            success = False

        if success:
            """Check for the test email in the inbox"""
            start_time = time.time()

            success = False
            while (not success) and (time.time() - start_time < max_wait_time):
                try:
                    if imap_use_ssl:
                        mail = imaplib.IMAP4_SSL(imap_server, imap_port)
                    else:
                        mail = imaplib.IMAP4(imap_server, imap_port)

                    mail.login(email_address, email_password)
                    mail.select('inbox')

                    # Search for emails from the last hour with our unique ID
                    search_criteria = f'(FROM "{from_address}" SUBJECT "Mail Health Exporter - {unique_id}")'
                    result, data = mail.search(None, search_criteria)

                    if result == 'OK' and data[0]:
                        email_ids = data[0].split()

                        for email_id in email_ids:
                            result, email_data = mail.fetch(email_id, '(RFC822)')
                            if result == 'OK':
                                email_message = email.message_from_bytes(email_data[0][1])
                                subject = email_message['Subject']

                                if unique_id in subject:
                                    # Delete the test email
                                    mail.store(email_id, '+FLAGS', '\\Deleted')
                                    mail.expunge()

                                    success = True
                                    break  # leave for-loop

                    mail.close()
                    mail.logout()

                except Exception as e:
                    self.logger.error(f'Error checking for test email: {e}')
                    time.sleep(10)  # Wait before retrying
                    continue

                time.sleep(10)  # Check every 10 seconds

            if success:
                self.logger.info(f'Successfully received and deleted test email: {unique_id}')
                self.metrics.set_value('mail_health_exporter__receiving_mails_working', 1)

                if (from_address == self.internal_email_address):
                    self.metrics.increment('mail_health_exporter__receive_internal_to_external_success_total')
                else:
                    self.metrics.increment('mail_health_exporter__receive_external_to_internal_success_total')
            else:
                self.logger.error(f'Test email not found within {max_wait_time} seconds: {unique_id}')
                self.metrics.set_value('mail_health_exporter__receiving_mails_working', 0)

                if (from_address == self.internal_email_address):
                    self.metrics.increment('mail_health_exporter__receive_internal_to_external_failures_total')
                else:
                    self.metrics.increment('mail_health_exporter__receive_external_to_internal_failures_total')

            return success

    # ===== SPAM SCORE MONITORING METHODS =====

    def extract_mail_tester_score(self, url: str) -> int:
        """
        Extract spam score from a mail-tester.com URL.

        Fetches the webpage and parses the spam score from the 'Your lovely total: X/10'
        text pattern.

        Parameters
        ----------
        url : str
            The mail-tester.com URL to scrape for spam score

        Returns
        -------
        int
            The extracted spam score (0-10), or 0 if extraction failed
        """
        score = 0
        try:
            # Send GET request to the URL
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            # Parse the HTML content
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for the exact text pattern using regex
            text_content = soup.get_text()
            pattern_full_score_text = r'Your lovely total:\s*(\d+(?:\.\d+)?/\d+)'
            match_full_score_text = re.search(pattern_full_score_text, text_content, re.IGNORECASE)

            if match_full_score_text:
                match_score_value = re.search(r'\d+', match_full_score_text.group(1))
                score = int(match_score_value.group())
                self.logger.info(f"Successfully parsed score: {score}")

        except requests.RequestException as e:
            self.logger.error(f"Error fetching URL: {e}")
        except Exception as e:
            self.logger.error(f"Error parsing content: {e}")

        return score

    # ===== MAIL HEALTH CHECK MAIN METHODS =====

    def run_mail_send_receive_test(self):
        """
        Run a complete mail roundtrip test between internal and external servers.

        This method performs bidirectional email testing by:
        1. Sending a test email from internal to external server
        2. Checking if the email was received in the external mailbox
        3. Deleting the received email from the external mailbox
        4. Sending a test email from external to internal server
        5. Checking if the email was received in the internal mailbox
        6. Deleting the received email from the internal mailbox
        7. Recording the total roundtrip duration as a metric


        The test uses a unique identifier to track individual test messages
        and measures the complete roundtrip time for monitoring purposes.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        unique_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        self.logger.info(f'Starting mail test (Internal -> External) with ID: {unique_id}')
        # Send test email from internal to external
        self.send_test_email(self.internal_email_address, self.external_email_address, unique_id)
        # Wait and check for if mail was received in external mailbox
        self.check_inbox_for_test_email(self.internal_email_address, self.external_email_address, unique_id,
                                        self.timeout_seconds)

        self.logger.info(f'Starting mail test (External -> Internal) with ID: {unique_id}')
        # Send test email from internal to external
        self.send_test_email(self.external_email_address, self.internal_email_address, unique_id)
        # Wait and check for if mail was received in external mailbox
        self.check_inbox_for_test_email(self.external_email_address, self.internal_email_address, unique_id,
                                        self.timeout_seconds)

        duration = time.time() - start_time
        self.metrics.set_value('mail_health_exporter__roundtrip_duration_seconds', duration)
        self.logger.info(f'Mail test completed in {duration:.2f} seconds')

    def run_mail_spam_score_test(self):
        """
        Run spam score test by sending email to a spam testing service.

        This method performs spam score testing with rate limiting:
        1. Checks if at least 6 hours have passed since the last spam test
        2. If enough time has passed, sends a test email to spam testing service
        3. Retrieves and records the spam score from the testing service
        4. Updates the last check timestamp

        The 6-hour rate limit prevents excessive API calls to the spam testing
        service while ensuring regular monitoring of email deliverability.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        current_time = datetime.now()

        # If the function hasn't run for at least 6 hours
        if (current_time - self.last_spam_score_check_timestamp).total_seconds() >= 6 * 60 * 60:
            self.last_spam_score_check_timestamp = current_time

            unique_id = str(uuid.uuid4())[:8]
            self.logger.info(f'Starting spam score test with ID: {unique_id}')

            self.logger.info(f'Sending email to spam score test from {self.internal_email_address} to '
                             f'{self.spam_score_test_email_address}')
            self.send_test_email(self.internal_email_address, self.spam_score_test_email_address, unique_id)

            self.logger.info(f'Retrieving spam score from url {self.spam_score_test_url}')
            spam_score = self.extract_mail_tester_score(self.spam_score_test_url)

            self.metrics.set_value('mail_health_exporter__spam_score', spam_score)

        else:
            self.logger.info("Spam score test doesn't need to run yet.")

    # ===== MISC METHODS =====

    def start_prometheus_server(self):
        """
        Start the Prometheus metrics HTTP server in a separate thread.

        This method initializes and starts an HTTP server that serves Prometheus
        metrics on the configured port. The server runs in a daemon thread to
        allow the main application to continue running while metrics are served.

        The server uses a custom handler factory that provides access to the
        metrics store for serving current metric values to Prometheus scrapers.

        Parameters
        ----------
        None

        Returns
        -------
        server : HTTPServer
            The started HTTP server instance for serving Prometheus metrics

        Notes
        -----
        The server is bound to '0.0.0.0' to accept connections from any interface.
        The daemon thread ensures the server shuts down when the main process exits.
        """

        # Create a handler factory that includes the metrics store
        def handler_factory(request, client_address, server):
            return HTTPHandler(request, client_address, server, self.metrics, self.status_html_template)

        server = HTTPServer(('0.0.0.0', self.metrics_port), handler_factory)

        def serve_forever():
            self.logger.info(f'Prometheus metrics server started on port {self.metrics_port}')
            server.serve_forever()

        thread = threading.Thread(target=serve_forever, daemon=True)
        thread.start()
        return server

    def run(self):
        """
        Main service loop for the Mail Health Exporter.

        This method implements the primary service loop that:
        1. Starts the Prometheus metrics server
        2. Continuously runs mail health checks at configured intervals
        3. Handles graceful shutdown on interruption
        4. Provides error recovery for unexpected exceptions

        The loop runs until the service is stopped via interrupt signal or
        by setting the running flag to False. Each iteration performs both
        send/receive tests and spam score tests.

        Parameters
        ----------
        None

        Returns
        -------
        None

        Raises
        ------
        KeyboardInterrupt
            Handled gracefully to allow clean shutdown
        Exception
            Caught and logged, service continues with 30-second delay
        """
        self.running = True
        self.logger.info('Mail Health Exporter service starting...')

        # Start Prometheus metrics server
        prometheus_server = self.start_prometheus_server()

        while self.running:
            try:
                # Run send, receive test
                self.run_mail_send_receive_test()

                # Run spam score test
                self.run_mail_spam_score_test()

                self.metrics.set_value('last_check_timestamp', time.time())

                self.logger.info(f'Waiting {self.check_interval} seconds until next check...')
                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                self.logger.info('Received interrupt signal, shutting down...')
                self.running = False
            except Exception as e:
                self.logger.error(f'Unexpected error in main loop: {e}')
                time.sleep(30)  # Wait before retrying

    def stop(self):
        """
        Stop the Mail Health Exporter service gracefully.

        This method provides a clean way to stop the service by setting
        the running flag to False, which will cause the main service loop
        to exit on its next iteration.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.running = False

def main():
    """
    Main entry point for the Mail Health Exporter application.

    This function creates a MailHealthExporter instance and starts the
    health check service. It handles any fatal errors that occur during
    initialization or execution by logging them and exiting with an
    error code.

    Parameters
    ----------
    None

    Returns
    -------
    None

    Raises
    ------
    SystemExit
        Called with exit code 1 if a fatal error occurs
    """
    mail_health_exporter = MailHealthExporter()

    try:
        mail_health_exporter.run()
    except Exception as e:
        mail_health_exporter.logger.error(f'Fatal error: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()
