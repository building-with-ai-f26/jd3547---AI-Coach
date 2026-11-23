# AGENTS.md — Coding Agent Operating Manual

> Give this file to your coding agent and check that it is using these instructions. Keep the stack, commands, and ground rules current.

## 1. Project Overview
- **What this repo builds:** AI Coach, a personal branding prototype. The quick exercise uses pasted background or approved résumé/CV cards to propose one theme. The separate `/workshop` flow adapts selected Body of Work exercises through roots, ingredients, and contribution questions, then individual accept/edit/reject review of typed landscape records.
- **Primary user & core workflow:** Professionals connecting their experiences into a clearer story. See the living PRD in `docs/index.html`. The local app is separate from that public Product Page.
- **Tech stack:** Python 3.12.16 / Flask / Gunicorn / pypdf / plain HTML, CSS and JavaScript / OpenRouter (optional live mode) / PostHog usage events and masked replay. Exercise data is in memory; no database.

## 2. Commands
- **Working folder:** Jason's checkout is `~/Desktop/jd3547---AI-Coach`; run commands from the project root. Beginner instructions are in `README.md`.
- **Install dependencies:** On first setup, `python3.12 -m venv .venv`; reuse an existing environment only if it uses Python 3.12 or newer. Then `.venv/bin/python -m pip install -r requirements.txt`. Python 3.12.16 is the verified deployment target; use Python 3.12+ for a new local environment; the local PDF reader uses POSIX resource limits.
- **Private configuration:** Use `cp -n .env.example .env` to create a missing `.env` without replacing existing settings. Read configuration names from `.env.example`; do not print or paste secret `.env` values. `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` enable optional live mode. Sample mode works without them.
- **Private workshop guide:** The server loads `~/.config/ai-coach/body-of-work-v1.json`, or the absolute `BODY_OF_WORK_SOURCE_PATH` override, once on startup. This reviewed, versioned guide is separate from the full book and public source metadata. A fresh clone does not include it. Missing/invalid guides disable personal workshop mode; the fixed fictional walkthrough remains available. Never copy the guide, full book, or detailed extraction into the public repository, session JSON, browser configuration, or exports.
- **Run locally:** `.venv/bin/python app.py`; open `http://127.0.0.1:8787`. Bind only to loopback; do not enable debug mode with personal input.
- **Stop/restart:** Control+C in the server's Terminal, then rerun the start command and refresh the browser. Restart after Python or `.env` changes. Explain that stopping clears in-memory exercises; export first if the user wants a copy.
- **Run deterministic tests:** `.venv/bin/python -m unittest discover -s tests -v`
- **Optional analytics JavaScript checks:** `node tests/analytics.test.js` if Node is available; uses built-in modules and no SDK/network. Node is not required to run the application.
- **Run model evals:** No repeatable live-model evaluation suite is implemented. Deterministic tests use stubs and validate flow, provider failures, PDF limits, and evidence checks; they do not establish coaching quality. Record any live checks separately, including their scope and costs; never infer verified live behavior from passing stub tests.
- **Prototype boundaries:** The sample is fixed and fictional. Never substitute it silently for a failed live request. Preserve exact user quotations and source attribution. Keep secrets server-side; never place personal input in cookies or browser storage. PDF imports are one document per exercise, memory-only, with bounded parsing; reject unreadable pages instead of silently omitting them. Only reviewed experience cards enter the landscape or downstream coaching. Test with fictional documents and keep private uploads/exports out of the repository.

## 3. Non-Negotiable Engineering Rules
1. **Plan before coding:** Before touching multiple files, propose a brief plan and wait for approval.
2. **Small batches:** Make small, focused changes that can be reviewed and explained by a human in a single Pull Request.
3. **Explainability:** Avoid unnecessary abstractions or dependencies. Help the human builder understand the main components, what changed, why it matters, what could break, and how it was checked.
4. **Verify changes:** Run relevant checks. For a reproducible logic bug, use a failing test to demonstrate the fix when practical. Record manual checks and known limitations; follow the selected Build 4 evaluation track.
5. **Zero secrets in code:** Never hardcode API keys, tokens, or credentials. Always read from environment variables (`.env`) and update `.env.example` when new variables are needed.
6. **Stop when looping:** If a fix fails twice in a row, stop, summarize what failed, and ask the human before trying a third approach.

## 4. Files and boundaries

| File / folder | Responsibility |
| --- | --- |
| `app.py` | Flask routes, opaque session cookies, state/version checks, document review, and exports. |
| `coach.py` | OpenRouter transport, experience extraction, question/proposal validation, and the fixed fictional sample. |
| `workshop.py` | Seven fixed book-informed prompts, typed state, bounded synthesis, evidence/source validation, revision, review, and export. |
| `introductions.py` | Separate presentation context, bounded AI introduction generation from reviewed material, and explicit keep/edit/omit review. |
| `documents.py` | Memory-only PDF extraction in a bounded subprocess; no original PDF saved. |
| `content/method.json` | Reviewed article source, adaptation, attribution, and coverage limits. |
| `templates/app.html`, `static/app.js`, `static/app.css` | Local browser interface. |
| `templates/workshop.html`, `static/workshop.js`, `static/workshop.css` | Book workshop interface, step recovery, and per-item review. |
| `static/dictation.js`, `tests/dictation.test.js` | Optional browser speech-to-text for live reflections; bounded, editable, no audio persistence. Run focused checks with `node tests/dictation.test.js`. |
| `docs/index.html` | Public Product Page, living PRD, and honest weekly log; separate from the local application. |
| `docs/assets/analytics-config.js`, `docs/assets/analytics.js` | Shared public PostHog configuration and event/privacy logic; Flask serves the same files under `/analytics/`. |
| `tests/test_app.py`, `tests/test_coach.py`, `tests/test_documents.py` | Deterministic tests using fictional inputs and mocked providers. |
| `tests/test_workshop.py` | Workshop transition and grounding checks with fictional data and mocked synthesis. |
| `tests/test_analytics.py`, `tests/analytics.test.js` | Analytics asset/privacy checks and optional JavaScript allowlist checks. |
| `.env.example`, `.gitignore` | Placeholder settings and exclusions for secrets/dependencies. Never overwrite a user's `.env`. |
| `README.md`, `AGENTS.md`, `CLAUDE.md` | Human setup instructions, agent operating rules, and Claude Code's pointer to these rules. |

PDF import accepts one selectable-text PDF up to 5 MB, 10 pages, and 30,000 extracted characters, producing at most six cards. The user reviews those cards before they enter the landscape. Preserve page/quote evidence and mark edits; use only approved titles/descriptions in subsequent coaching requests. Unreviewed import cards cannot be exported. Do not weaken source, identifier, version, or same-origin checks to accommodate a provider failure.

Session content is held only in the Flask process. The session cookie lasts one hour; server records inactive for over an hour are removed on a subsequent session request. Reset clears the current exercise and server shutdown clears all sessions. The quick exercise does not restore on refresh; `/api/workshop/state` restores submitted workshop steps while the server session survives. Unsaved typing is not recovered. Exports are local records, not resumable sessions, and distinguish pending proposals from accepted results. Neither reset nor shutdown deletes downloaded files or data already sent to external providers.

The book workshop uses server-owned steps and one optional synthesis request per explicit attempt. Keeping the user's own words makes no model call. Do not silently substitute fictional text after a live failure. Keep roots, current ingredients, desired ingredients, directions, and themes distinct. Evidence references point to approved experiences or submitted reflections; method references describe the exercise, not facts about the person. Allow skipped/unresolved answers. Review must cover every proposal. Rejecting excludes its wording from accepted records and exports; editing is user-authored and does not prove the old evidence supports the new wording. Revising a step clears that answer, later answers, and downstream results after an explicit UI warning; earlier answers remain. Preserve version/operation guards so delayed responses cannot restore superseded work.

Keep personal documents, exports, and screenshots outside the public repository; `.gitignore` does not automatically exclude every private document. Do not log prompts, document text, filenames, answers, accepted wording, or provider responses containing personal material.

Dictation uses the browser's SpeechRecognition service, which may process audio remotely. Keep the disclosure visible before microphone use. Preserve earlier text, invalidate late callbacks after cancellation/reset, enforce the 60-second limit, and require transcript review and explicit submission. Interim speech must remain inside an analytics-blocked element. Do not claim microphone accuracy from mocked recognition tests.

## 5. Analytics boundaries and verification

The public PostHog ingestion token in `docs/assets/analytics-config.js` is intentionally browser-visible. It is not a personal PostHog API key or an OpenRouter secret. Never put either secret there. The shared helper is enabled by configuration, honors Do Not Track/Global Privacy Control, and supports disabling collection with `enabled: false`.

Keep analytics events and properties inside the helper's allowlists: fixed action/stage/mode categories and small card counts only. Preserve URL/referrer sanitization. Never send personal text, filenames, evidence, theme wording, free-form errors, or private documents as event properties. Do not enable identification, person profiles, autocapture, console capture, or network payload capture. Replay must continue masking text/inputs and blocking all personal containers and images. Review new UI surfaces for replay exposure before adding them.

The SDK is configured for in-memory identifiers; exercise cookies and server state are separate. PostHog is an external recipient. Do not claim that local reset removes remote events, or invent remote retention/deletion guarantees.

Use `?analytics_test=build2-nov11` for the dated builder-check marker; it is a fixed allowlisted marker, not arbitrary query-string capture. Verify actual events for `app_surface` values `local_app` and `product_page`, and inspect a masked replay using fictional input. The private dashboard is https://us.posthog.com/project/697808/dashboard/2337055. Record what was observed in the Build 2 log; deterministic tests and configured settings alone do not establish event receipt, replay masking, user adoption, or coaching value.


## 6. Opening-line rules and Build 3 handoff

- Keep introduction context separate from personal evidence. Audience, desired impression, tone, and aspirations do not establish credentials, results, clients, or expertise. Never attribute the app-authored exercise to the exact Brand Snap method without a verified source.
- The original introduction is a starting draft; only reviewed experience summaries and landscape records provide citable evidence to this generation step. Do not send the private book guide, raw PDFs, or unreviewed reflections to the introduction request. Reset and expiry clear this state; exports do not restore a session.
- A generation creates drafts. Keep/edit/omit review is explicit; edited text retains original evidence for comparison without claiming the edit is verified. Revising source reflections clears dependent introduction drafts and kept versions.
- Real mistake rule (November 17): generated workshop records cited answers of the wrong kind after questions were skipped. Derive generation rules from the validator's available evidence mapping, omit unsupported kinds, and never disable evidence checks to make a model response pass.
- Focused checks for this feature: `.venv/bin/python -B -m unittest discover -s tests -p 'test_introductions.py'` and the relevant workshop/route checks. Mocked provider tests do not prove live model quality.

### Shipping — Render, Beginner lane

1. Review the intended diff, run checks appropriate to changed behavior, and commit/push to the class repository. Keep the source guide, `.env`, private inputs, and exports outside Git. Use the exact pushed revision for deployment; no backdated commits.
2. Create one **Free Python Web Service** on Render from `https://github.com/building-with-ai-f26/jd3547---AI-Coach`, branch `main`. Build: `pip install -r requirements.txt`. Start: `gunicorn --config gunicorn.conf.py app:app`. Health check: `/health`. `.python-version` pins Python 3.12.16. `render.yaml` records these settings. Disable automatic deploys so later documentation pushes do not silently clear active sessions.
3. Keep **one instance and one Gunicorn worker** (four threads). Session state and rate-limit counters live in that process; extra workers or instances would split them. Never expose the Flask development server or enable debug mode.
4. Set `APP_ENV=production`; Render supplies `RENDER=true` and `RENDER_EXTERNAL_HOSTNAME`. Exact trusted hosts are required. Keep `OPENROUTER_API_KEY` private in Render's environment, and `OPENROUTER_MODEL=anthropic/claude-sonnet-4.6`. Add the reviewed guide as a private secret file named `body-of-work-v1.json`; set `BODY_OF_WORK_SOURCE_PATH=/etc/secrets/body-of-work-v1.json`. Obtain authorization before moving those secrets or source material to a new host. Never put their contents in deployment logs, screenshots, Git, or client assets.
5. Verify the approved **monthly** OpenRouter key budget before enabling public AI. Per-IP and per-session limits permit up to 20 AI-capable route attempts per hour across all five endpoints; a global backstop permits 100. Invalid and sample attempts also count. `/api/start` may make one bounded internal retry, so attempt limits are not a dollar cap. API flood and session-creation limits also apply. The server uses Secure/HttpOnly/SameSite cookies and exact host/origin checks.
6. After a manual deploy succeeds, verify `/health`, a complete mobile-width core workflow, session isolation, PostHog event receipt and a masked replay with fictional inputs. Before the rate-limit audit, finish any paid workflow check from the same network. Run `scripts/check_live_security.py --url <verified-https-origin> --output <private-report.json>`; it scans public assets and makes 30 invalid-body requests to the actual AI route without buying 30 model responses, then checks spoofed forwarding headers. Save a screenshot of the real results. A verified application quota response must be 429 with Retry-After, not merely a validation failure. Run forwarding-header probes in separate cookie-free clients. Record a 403 denial separately: it does not establish which layer rejected the request or prove the application quota held.
7. Run `pip-audit` against the resolved production environment, fix high-severity findings, and finish the agent review in `SECURITY.md`. Keep any remaining limits explicit. No database/buckets/backups are needed for this memory-only version; revisit this if storage is added.
8. Update the verified app URL, PRD v3, Build 3 log, actual spend/hours, and this document's deployment record. Push the second actual build day's work and submit the live URL, repository, Beginner lane, SECURITY.md link, and security-test screenshot in Icerynk. Re-read the assignment if requirements change.

**Deployment record — November 23, 2026:**

- Live workshop: https://jd3547-ai-coach.onrender.com/workshop; quick exercise: https://jd3547-ai-coach.onrender.com/. Render Free service `srv-dc23qp5g1s2s73ersen0`, deployment `dep-dc23qplg1s2s73ersgd0`, revision `b83f1cb`, live at 8:20 AM America/New_York (13:20 UTC). Python 3.12.16; one worker/four threads; automatic deploys off.
- The owner explicitly authorized provisioning the API key and reviewed method guide privately on Render; both are configured. The $100 monthly key cap was saved and verified. No credits were purchased as part of this cap change.
- Observed `/health` 200 and `/api/config` 200. The session cookie had Secure, HttpOnly, and SameSite=Strict; HSTS had `max-age=31536000`. No cookie or key values are recorded.
- Live AI workflow with fictional inputs completed seven answers, six kept landscape additions, an edited/kept opening line, and an export whose JSON contained that edit. The 390 × 844 browser viewport had no horizontal overflow. An actual classmate phone test remains pending.
- At 13:29:54 UTC, the live audit scanned 11 public resources, all HTTP 200, with no key-pattern or exact local-key matches. Thirty invalid empty `/api/start` requests returned 18 × 400 and 12 × 429 with Retry-After; two earlier workflow requests had already consumed two of the 20 allowed attempts. The audit itself made no provider calls. Separate cookie-free and X-Forwarded-For probes returned 429; the CF-Connecting-IP spoof returned 403, a denial with rejecting layer unverified, not an application quota pass.
- PostHog received pageviews and `workshop_progress` from the public origin. The observed replay masked text as `[hidden]` and blocked personal containers. See [SECURITY.md](./SECURITY.md), [live audit results](./docs/assets/build3-security-results.json), and the Build 3 log for evidence. The 62 Python/12 analytics checks and clean 17-package production dependency audit were completed before deployment; they were not rerun for these documentation updates.
- Meaningful work was pushed November 22 (`1f74d77`) and November 23 (`5348778`), followed by documentation/deployment-preparation revisions `ec1b778` and `b83f1cb`. Icerynk Build 3 submission was observed successfully as Attempt 1 on November 23, 2026 at 8:51 AM New York time; the instructor can see it. It includes the live workshop, repository, SECURITY.md and Product Page links, Beginner lane, the 130 KB security screenshot attachment, 2 hours, and the recorded learning.

**Recovery:** keep the previous successful revision available in Render's deployment history. Roll back to that revision if a deployment fails its checks; confirm health and the core flow afterward. A restart, rollback, deploy, or free-service sleep clears active sessions and local counters. Export active work before a planned restart. The provider cap remains independent of process restarts.

### Ask me first

Get explicit authorization before deleting user data, making destructive database changes, changing secrets or access permissions, buying services or committing to new charges, or expanding a spending cap. Existing task-specific authorization still applies. Never publish personal demo inputs, exports, private screenshots, or source-book material. Explain and export active workshop work before a restart that would clear it.
