"""Small, bounded safeguards for one Render process; no persistent user tracking.

The in-memory windows and sessions reset when the process restarts. They do not
replace an OpenRouter key spending cap. Do not add workers or instances without
moving BOTH stores to a shared service.
"""
from collections import deque
import hashlib
import hmac
import ipaddress
import math
import os
import re
import secrets
import threading
import time

from werkzeug.middleware.proxy_fix import ProxyFix

# These are the real endpoints: start asks a question and answer makes a proposal.
PAID_PATHS = frozenset({"/api/documents", "/api/start", "/api/answer",
                        "/api/workshop/synthesize", "/api/workshop/introductions",
                        "/api/studio/documents", "/api/studio/generate"})
LIMIT_DEFAULTS = {
    "AI_REQUEST_LIMIT": 20, "AI_GLOBAL_LIMIT": 100,
    "API_REQUEST_LIMIT": 120, "API_GLOBAL_LIMIT": 600,
    "SESSION_CREATION_LIMIT": 10, "SESSION_GLOBAL_LIMIT": 60,
}


def environment_config(environ=None):
    env = os.environ if environ is None else environ
    render = env.get("RENDER", "").lower() == "true"
    production = render or env.get("APP_ENV", "").lower() == "production"
    hosts = [host.strip() for host in env.get("TRUSTED_HOSTS", "").split(",") if host.strip()]
    render_host = env.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_host:
        hosts.append(render_host)
    if not production:
        hosts.extend(["localhost", "127.0.0.1", "[::1]"])
    return dict(LIMIT_DEFAULTS, PRODUCTION=production,
                RENDER_PROXY=bool(render and render_host), RATE_LIMIT_ENABLED=production,
                TRUSTED_HOSTS=list(dict.fromkeys(hosts)), SESSION_COOKIE_SECURE=production)


def install(app):
    if app.config["PRODUCTION"]:
        hosts = app.config.get("TRUSTED_HOSTS")
        if not isinstance(hosts, list) or not hosts:
            raise ValueError("Production needs RENDER_EXTERNAL_HOSTNAME or explicit TRUSTED_HOSTS.")
        # Flask allows a leading dot for any subdomain. This app only allows exact
        # hostnames; a wildcard or URL is a deployment configuration error.
        for host in hosts:
            if (not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host)
                    or ".." in host or len(host) > 253):
                raise ValueError("TRUSTED_HOSTS must contain exact hostnames, without URLs or wildcards.")
        app.config.update(SESSION_COOKIE_SECURE=True, RATE_LIMIT_ENABLED=True, DEBUG=False)
    if app.config["RENDER_PROXY"]:
        if not app.config["PRODUCTION"]:
            raise ValueError("Render proxy trust requires production mode.")
        # Only Render's final forwarded scheme is used. Never trust XFF, forwarded
        # host/port, or prefixes. Public Render ingress is behind Cloudflare:
        # https://render.com/articles/how-render-handles-ddos-attacks
        # https://render.com/articles/how-to-proxy-analytics-through-your-own-domain
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=0, x_proto=1, x_host=0, x_port=0, x_prefix=0)
    for name, maximum in LIMIT_DEFAULTS.items():
        value = app.config[name]
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(name + " must be a positive integer no higher than its safety default.")
    return RequestLimits(app.config)


def client_address(request, render_proxy):
    # Render forwards Cloudflare's overwritten single-address header. Do not read
    # the first XFF element: an attacker can prepend arbitrary values to it.
    # https://developers.cloudflare.com/fundamentals/reference/http-headers/
    value = request.headers.get("CF-Connecting-IP", "") if render_proxy else request.remote_addr
    try:
        address = ipaddress.ip_address(value or "")
        if getattr(address, "ipv4_mapped", None):
            address = address.ipv4_mapped
        return str(address)
    except ValueError:
        # Missing or malformed trusted metadata shares one conservative bucket.
        # Never fall back to attacker-controlled forwarding headers.
        return "unidentified"


class RateLimitExceeded(Exception):
    def __init__(self, retry_after):
        super().__init__("Too many requests. Please wait before trying again.")
        self.retry_after = max(1, math.ceil(retry_after))


class RequestLimits:
    """Thread-safe sliding windows with bounded keys and timestamps; no logging."""
    def __init__(self, config, clock=None, max_keys=4096):
        self.enabled = config["RATE_LIMIT_ENABLED"]
        self.config = {key: config[key] for key in LIMIT_DEFAULTS}
        self.clock = clock or time.monotonic
        self.max_keys = max_keys
        self._buckets = {}
        self._lock = threading.Lock()
        self._salt = secrets.token_bytes(32)

    def identity(self, address):
        # Keep only process-local opaque identifiers rather than raw visitor IPs.
        return hmac.new(self._salt, address.encode("utf-8"), hashlib.sha256).hexdigest()

    def admit(self, rules):
        if not self.enabled:
            return
        now = self.clock()
        with self._lock:
            for key, (window, events) in list(self._buckets.items()):
                while events and events[0] <= now - window:
                    events.popleft()
                if not events:
                    del self._buckets[key]
            waits = []
            for scope, identity, limit, window in rules:
                current = self._buckets.get((scope, identity))
                if current and len(current[1]) >= limit:
                    waits.append(current[1][0] + window - now)
            if waits:
                raise RateLimitExceeded(max(waits))
            missing = {(scope, identity) for scope, identity, _, _ in rules} - self._buckets.keys()
            if len(self._buckets) + len(missing) > self.max_keys:
                raise RateLimitExceeded(60)
            for scope, identity, _, window in rules:
                _, events = self._buckets.setdefault((scope, identity), (window, deque()))
                events.append(now)

    def api(self, ip):
        self.admit([("api-ip", ip, self.config["API_REQUEST_LIMIT"], 60),
                    ("api-global", "all", self.config["API_GLOBAL_LIMIT"], 60)])

    def paid(self, ip, quota_id=None):
        rules = [("paid-ip", ip, self.config["AI_REQUEST_LIMIT"], 3600),
                 ("paid-global", "all", self.config["AI_GLOBAL_LIMIT"], 3600)]
        if quota_id:
            rules.append(("paid-session", quota_id, self.config["AI_REQUEST_LIMIT"], 3600))
        self.admit(rules)

    def first_paid_session(self, quota_id):
        self.admit([("paid-session", quota_id, self.config["AI_REQUEST_LIMIT"], 3600)])

    def session_creation(self, ip):
        self.admit([("session-ip", ip, self.config["SESSION_CREATION_LIMIT"], 3600),
                    ("session-global", "all", self.config["SESSION_GLOBAL_LIMIT"], 3600)])
