#!/usr/bin/env python3
"""Bounded, no-provider-call checks against an explicitly supplied deployment.

Example: python scripts/check_live_security.py --url https://your-app.example
The 30 rate-limit probes deliberately send invalid empty JSON, not 30 AI requests.
Run against a deployment you control. The probe temporarily consumes its quota.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from dotenv import dotenv_values
import httpx


MAX_BYTES = 2 * 1024 * 1024
MAX_ASSETS = 32
KEY_PATTERNS = {
    "supabase_secret": re.compile(rb"\bsb_secret_[A-Za-z0-9_-]{20,}"),
    "service_role_marker": re.compile(rb"\bservice_role\b"),
    "stripe_live_secret": re.compile(rb"\bsk_live_[A-Za-z0-9_-]{20,}"),
    "openrouter_key": re.compile(rb"\bsk-or-v1-[A-Za-z0-9_-]{24,}"),
    "anthropic_key": re.compile(rb"\bsk-ant-[A-Za-z0-9_-]{24,}"),
    "openai_key": re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}"),
    "github_token": re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9]{25,}|github_pat_[A-Za-z0-9_]{25,})"),
    "aws_access_key": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "private_key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
}


def origin_argument(value):
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == "https" and parsed.hostname and not parsed.username
                 and not parsed.password and parsed.path in ("", "/")
                 and not parsed.query and not parsed.fragment)
        parsed.port  # Reject malformed ports before any request.
    except ValueError:
        valid = False
    if not valid:
        raise argparse.ArgumentTypeError("Use an HTTPS origin only, without credentials, a path, or a query.")
    return urlunsplit(("https", parsed.netloc.lower(), "", "", ""))


def local_secret():
    """Read only for an in-memory comparison; never serialize the value."""
    path = Path(__file__).resolve().parents[1] / ".env"
    if not path.is_file():
        return None, "unavailable"
    try:
        value = dotenv_values(path, interpolate=False).get("OPENROUTER_API_KEY")
    except (OSError, UnicodeError):
        return None, "unreadable"
    if not value or len(value) < 20 or any(word in value.lower() for word in ("replace", "placeholder", "example")):
        return None, "unavailable"
    return value.encode("utf-8"), "performed"


class AssetLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.links.add(attrs["src"])
        if tag == "link" and attrs.get("href"):
            rel = attrs.get("rel", "").lower().split()
            if "stylesheet" in rel or "modulepreload" in rel or attrs.get("as") in ("script", "style"):
                self.links.add(attrs["href"])


def scan_resource(client, url, secret):
    # Asset paths normally contain filenames only, but never echo a credential
    # even if a broken page accidentally embeds one in a resource URL.
    safe_url = url.encode("utf-8")
    for pattern in KEY_PATTERNS.values():
        safe_url = pattern.sub(b"[redacted]", safe_url)
    if secret:
        safe_url = safe_url.replace(secret, b"[redacted]")
    result = {"url": safe_url.decode("utf-8"), "status": None, "secret_patterns": []}
    chunks, size = [], 0
    try:
        with client.stream("GET", url) as response:
            result["status"] = response.status_code
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    result["error"] = "response_size_limit"
                    break
                chunks.append(chunk)
    except httpx.HTTPError:
        result["error"] = "request_failed"
    content = b"".join(chunks)
    result["bytes_scanned"] = len(content)
    result["secret_patterns"] = [name for name, pattern in KEY_PATTERNS.items() if pattern.search(content)]
    if secret and secret in content:
        result["secret_patterns"].append("exact_local_api_secret")
    result["passed"] = result["status"] == 200 and not result.get("error") and not result["secret_patterns"]
    return result, content


def retry_after(value):
    """Report only a validated duration/date type, never an arbitrary header."""
    if not value:
        return None
    if re.fullmatch(r"[0-9]{1,8}", value.strip()):
        return {"seconds": int(value.strip())}
    try:
        if parsedate_to_datetime(value).tzinfo is not None:
            return {"http_date": True}
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def invalid_start(client, origin, extra_headers=None):
    headers = {"X-Coach-Request": "1", "Origin": origin}
    headers.update(extra_headers or {})
    try:
        # Streaming avoids retaining any error body. Empty JSON has no valid mode
        # or background, so the start route must reject it before a provider call.
        with client.stream("POST", origin + "/api/start", headers=headers, json={}) as response:
            return {"status": response.status_code, "retry_after": retry_after(response.headers.get("Retry-After"))}
    except httpx.HTTPError:
        return {"status": None, "retry_after": None, "error": "request_failed"}


def check(origin):
    secret, comparison = local_secret()
    report = {
        "format": "ai-coach-live-security-v1",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "origin": origin,
        "scope": "Public HTML and referenced same-origin scripts/styles; invalid-body rate-limit and forwarded-header probes. No paid AI calls or personal input.",
        "limitations": "Pattern checks cannot prove absence of every secret. This does not test session isolation, semantic prompt safety, or provider spending limits.",
    }
    assets, discovered = [], set()
    with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False,
                      headers={"User-Agent": "AI-Coach-Build3-Security-Check"}) as client:
        for path in ("/", "/workshop"):
            result, content = scan_resource(client, origin + path, secret)
            assets.append(result)
            if result["status"] == 200 and not result.get("error"):
                parser = AssetLinks()
                parser.feed(content.decode("utf-8", errors="replace"))
                for link in parser.links:
                    try:
                        parsed = urlsplit(urljoin(origin + path, link))
                    except ValueError:
                        result["error"] = "invalid_asset_url"
                        result["passed"] = False
                        continue
                    # No external requests, redirects, query strings or fragments.
                    if parsed.scheme == "https" and parsed.netloc.lower() == urlsplit(origin).netloc:
                        discovered.add(origin + parsed.path)
        too_many = len(discovered) > MAX_ASSETS
        for url in sorted(discovered)[:MAX_ASSETS]:
            result, _ = scan_resource(client, url, secret)
            assets.append(result)
        # Establish one fresh anonymous browser cookie before the POST sequence;
        # also check that the public configuration does not expose the API key.
        for config_path in ("/api/config", "/api/workshop/config"):
            config, _ = scan_resource(client, origin + config_path, secret)
            assets.append(config)
        report["secret_scan"] = {"exact_local_secret_comparison": comparison, "resources": assets,
                                 "asset_limit_exceeded": too_many,
                                 "passed": not too_many and comparison == "performed" and all(item["passed"] for item in assets)}
        attempts = [invalid_start(client, origin) for _ in range(30)]
        limited = lambda item: item["status"] == 429 and item["retry_after"] is not None
        report["rate_limit"] = {
            "url": origin + "/api/start", "attempt_count": 30,
            "request_kind": "Invalid empty JSON counted before provider execution; these are not 30 paid requests.",
            "responses": attempts,
            "status_counts": dict(Counter(str(item["status"]) for item in attempts)),
            "passed": any(limited(item) for item in attempts)
                      and all(item["status"] in (400, 429) for item in attempts),
        }
        probes = []
        for label, headers in (("cookies_dropped", {}),
                               ("forwarded_for", {"X-Forwarded-For": "198.51.100.73"}),
                               ("connecting_ip", {"CF-Connecting-IP": "203.0.113.94"})):
            # Do not reuse the original session: its quota could otherwise hide
            # an IP quota bypass. Every probe starts with an empty cookie jar.
            with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False,
                              headers={"User-Agent": "AI-Coach-Build3-Security-Check"}) as probe_client:
                result = invalid_start(probe_client, origin, headers)
            probes.append(dict(result, probe=label, fresh_cookie_free_client=True, passed=limited(result)))
        report["forwarded_header_bypass"] = {
            "design": "Three separate clients with no cookies or previous session, after the primary 30-request quota probe: no spoof header, forwarded-for spoof, and connecting-IP spoof.",
            "responses": probes,
            "passed": report["rate_limit"]["passed"] and all(item["passed"] for item in probes),
        }
    report["passed"] = all(report[key]["passed"] for key in ("secret_scan", "rate_limit", "forwarded_header_bypass"))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, type=origin_argument, help="HTTPS origin of your deployed app")
    parser.add_argument("--output", type=Path, help="Optional absolute JSON report path (outside the public repository is preferred)")
    args = parser.parse_args()
    if args.output is not None and not args.output.is_absolute():
        parser.error("--output must be an absolute path")
    report = check(args.url)
    serialized = json.dumps(report, indent=2) + "\n"
    if args.output is not None:
        try:
            args.output.write_text(serialized, encoding="utf-8")
        except OSError:
            parser.exit(2, "Could not write the report to the requested output path.\n")
    print(serialized, end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
