# Build 3: November 22 and 23

Due Monday, November 23, 2026, 12:00 PM America/New_York. Beginner lane. The app is live; Icerynk submission and an actual classmate phone check are pending.

## Sunday, November 22 — opening-line refinement

- Added an initial introduction and up to three environment/audience filters. The existing Body of Work workshop develops evidence, followed by context-specific opening drafts and explicit keep/edit/omit review.
- Kept inferred public-example guidance separate from the unverified Brand Snap method and private Slim guide. Public research did not establish Gottlieb's exact Brand Snap steps.
- Verification: 12 introduction-engine checks and 26 workshop/route checks passed. Browser walkthrough covered fixed fictional mode, two situations, keep/omit, and export. One live AI request with fictional volunteer-guide input returned two drafts; the edited kept version appeared in the export and the omitted version did not. JavaScript syntax and diff whitespace checks passed.
- Pushed meaningful work in `1f74d77`, including the existing November 17 skipped-answer evidence fix. Deployment remained for the second day; these checks did not establish outside-user benefit.

## Monday, November 23 — public deployment

- Production work `5348778` and preparation/documentation revisions `ec1b778` and `b83f1cb` were pushed. Added Gunicorn/Render configuration, shared paid-route limits, anonymous-session flood controls, secure cookies/trusted hosts, patched dependencies, hosted analytics URL sanitization, PRD v3, and Shipping/SECURITY documentation.
- Preparation checks: 62 relevant Python checks and 12 analytics safeguards passed. An isolated production server rejected attempts 21–30 across the five paid routes with 429; no model calls were made. The final audit of 17 installed runtime packages found zero known advisories and no skipped packages.
- [Public workshop](https://jd3547-ai-coach.onrender.com/workshop) and [quick exercise](https://jd3547-ai-coach.onrender.com/) went live at 8:20 AM New York time (13:20 UTC) on revision `b83f1cb`. Render Free service `srv-dc23qp5g1s2s73ersen0`, deploy `dep-dc23qplg1s2s73ersgd0`; Python 3.12.16, one Gunicorn worker/four threads, automatic deploys off.
- The owner explicitly authorized moving the API key and reviewed guide into Render's private configuration; done. The $100 monthly OpenRouter key cap was saved and the current-key API verified `limit: 100` and `limit_reset: monthly`. No credits were purchased for the cap change.
- Live availability/headers: `/health` and `/api/config` returned 200; the session cookie carried Secure, HttpOnly, and SameSite=Strict; HSTS was `max-age=31536000`. Values of keys and cookies are omitted.

## Live checks and evidence

- A live AI workshop with fictional input completed seven answers, kept six landscape additions, generated an opening draft, edited and kept the line, and downloaded an export. The downloaded JSON contained the edited line. At a 390 × 844 browser viewport, there was no horizontal overflow. This is not an actual classmate phone test.
- At 13:29:54 UTC, the live audit scanned 11 public resources, all returning 200, with no secret-pattern or exact local-key matches. Thirty invalid empty `/api/start` requests produced 18 × 400 and 12 × 429 with Retry-After. Two earlier workflow calls had consumed two of the 20 attempts. The audit itself made no provider calls.
- Separate cookie-free and forged X-Forwarded-For probes returned 429 with Retry-After. The CF-Connecting-IP spoof returned 403: denied, but the rejecting layer was not established. It is not an application quota pass or proof of proxy rewriting. The harness report labels that distinction and retains the raw statuses. [Security screenshot](../docs/assets/build3-security-nov23.png) · [redacted recorded results](../docs/assets/build3-security-results.json) · [SECURITY.md](../SECURITY.md).
- PostHog received pageviews and `workshop_progress` from the new public origin. The observed replay showed `[hidden]` text and blocked personal containers. Replay and workflow screenshots remain private. This is builder verification with fictional material, not outside-user evidence.

## Costs, time, and learning

- Approximately $0.129 in project-key API usage for November 17–23: approximately $0.103 shown before deployment plus $0.026442 from the live workflow check. The provider API reported cumulative key usage of $0.236655 at 13:31 UTC on November 23. These figures exclude coding-agent subscriptions; Render uses the free tier. A single fictional test does not establish average cost per user.
- Jason reports approximately **2 hours** for Build 3.
- Learning: **“I need to refine the user experience.”**

## Remaining work and limits

- Submit the live URL, repository, Beginner lane, SECURITY.md link, and security-test screenshot in Icerynk. Submission is pending; append the observed receipt after it succeeds.
- Have a classmate complete the workflow on an actual phone. The browser-width check does not substitute for that result.
- The CF-Connecting-IP denial's rejecting layer remains unverified. Memory-only sessions and counters reset on server sleep/restart; exports are records, not resumable sessions.
- The November 17 live workshop demo succeeded after the skipped-answer evidence fix; guessed demo answers were labeled unconfirmed. Neither that demo nor this deployment establishes coaching usefulness or superiority over ordinary prompting. The comparison pilot remains future work.
