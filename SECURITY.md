# Build 3 security review

Review date: November 23, 2026. Beginner lane. **AI app with no database and no sign-in.**

The app keeps short-lived exercises in server memory. It does not provide durable saved accounts or file storage. Uploaded PDFs are parsed in memory; downloaded exports belong to the visitor. The public GitHub Pages Product Page is separate from the Python application.

## Review and fixes

- **Secret scan:** scanned 47 tracked files and 108 reachable historical blobs at `1f74d77` for provider credentials, AWS keys, private-key blocks, and long literal secret assignments. No secret matches; `.env` is not tracked. Public PostHog ingestion tokens are intentionally public. Placeholder strings and audit search patterns are not live credentials. A final scan of 54 current tracked/new files also checked for an exact match to the configured private app key and found none. A pattern scan does not prove the absence of every secret.
- **Dependencies:** the initial audit identified CVE-2026-28684 in python-dotenv 1.2.1 and CVE-2026-63374/CVE-2026-64847 in anyio 4.12.1. The affected dotenv writers and AnyIO async/process-pool functions are not used here, but the deployment pins were updated to python-dotenv 1.2.2 and anyio 4.14.2. A proposed 21-package closure including Gunicorn 27.0.1 returned zero known advisories. The final isolated Python 3.12.16 environment audit covered 17 exact runtime packages with zero known advisories and no skipped packages; pip installation tooling was excluded.
- **Agent review:** inspected request handling, state access, PDF isolation, provider transport, generated-output review, and browser rendering. Identified missing paid-route limits, insecure-for-HTTPS cookie configuration, development-only serving, and anonymous session-slot exhaustion. Implemented production fixes and passed 62 relevant Python checks, including 17 production-security cases; 12 analytics safeguards also passed. An isolated Gunicorn check returned 429 with Retry-After after 20 invalid attempts across the five paid routes, with no provider requests. This is local production-runtime evidence, not a deployed-site result.
- **Existing boundaries retained:** opaque session cookies, same-origin POST restrictions, explicit version/operation checks, no secrets in client configuration, bounded PDF parsing, fixed provider endpoint, quotation checks, and explicit human review of generated claims. HTML is rendered through text-safe DOM operations.
- **Source library:** the reviewed Body of Work guide must be a private hosting secret file. Neither the full book nor detailed extraction belongs in the repository, public assets, browser state, or exports.

## Deployment controls and evidence

- Production host, exact deployment revision, secure-cookie and proxy behavior: pending.
- Limits implemented and checked: 20 AI-capable attempts/hour per IP and session across all five routes; 100/hour global. API flood: 120/min/IP and 600/min global. New sessions: 10/hour/IP and 60/hour global. Reset rotates cookies while preserving the session allowance; IP allowance survives cookie removal. Health checks allocate no session and do not consume visitor quotas. Public proxy-header behavior is still pending live verification.
- Provider monthly spending cap: owner-approved $100 per month, saved in OpenRouter on November 23 and verified through the current-key API (`limit: 100`, `limit_reset: monthly`). Resets on the first of each month at midnight UTC. This changes the cap only; no credits were purchased.
- Live source/asset key scan and 30-request rate-limit test: pending deployment. The test uses empty invalid request bodies so it exercises the real paid endpoint and limiter without purchasing 30 model responses; this is not a live model throughput test.
- Separate visitor cookies and state isolation, invalid host/origin checks, cookie-reset resistance, and production configuration were covered by focused tests. Public Render forwarding-header behavior remains pending deployment verification. The resolved production dependency audit passed as above.
- Live PostHog events and masked replay: pending deployment verification.

## Remaining limits

- Sessions and rate-limit counters are process-local. A single worker/instance is required. Restarts, deployments, or a free host sleeping erase progress and reset local quotas. Exports are records, not resumable sessions. A provider-enforced monthly cap is the separate spending backstop.
- IP-based limits may group people behind the same network and do not stop a distributed attacker. The global limit reduces exposure but can temporarily deny legitimate requests. Public use remains a small class prototype.
- Inputs and reviewed material requested for AI processing are sent to OpenRouter and the configured model provider. The app cannot promise deletion from those providers. Optional browser dictation may use a separate remote speech service.
- Source-quotation validation does not prove a model's interpretation or an edited introduction is true. Users must review every result.
- No database, object-storage buckets, database backup, or account-to-account database policies apply to this implementation. Adding durable storage or accounts requires a new access-control review.

Deployment and live checks must be completed before claiming this review finished.
