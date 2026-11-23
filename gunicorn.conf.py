"""Render serves one process because session state and rate limits are in memory."""
import os

bind = "0.0.0.0:" + os.environ.get("PORT", "10000")
workers = 1
worker_class = "gthread"
threads = 4
timeout = 120
graceful_timeout = 120
keepalive = 5
# Request URLs, query strings, bodies, cookies, and client IPs are not logged.
accesslog = None
errorlog = "-"
loglevel = "warning"
capture_output = False
# Scheme trust is handled in production.py only when Render is configured.
forwarded_allow_ips = ""
secure_scheme_headers = {}
