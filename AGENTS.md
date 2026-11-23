# AGENTS.md — Coding Agent Operating Manual

> Give this file to your coding agent and check that it is using these instructions. Keep the stack, commands, and ground rules current.

## 1. Project Overview
- **What this repo builds:** AI Coach, a personal branding prototype. The quick exercise uses pasted background or approved résumé/CV cards to propose one theme. The separate `/workshop` flow adapts selected Body of Work exercises through roots, ingredients, and contribution questions, then individual accept/edit/reject review of typed landscape records.
- **Primary user & core workflow:** Professionals connecting their experiences into a clearer story. See the living PRD in `docs/index.html`. The local app is separate from that public Product Page.
- **Tech stack:** Python 3.9+ / Flask / pypdf / plain HTML, CSS and JavaScript / OpenRouter (optional live mode) / PostHog usage events and masked replay. Exercise data is in memory; no database.

## 2. Commands
- **Working folder:** Jason's checkout is `~/Desktop/jd3547---AI-Coach`; run commands from the project root. Beginner instructions are in `README.md`.
- **Install dependencies:** On first setup, `python3 -m venv .venv`; reuse a working existing environment. Then `.venv/bin/python -m pip install -r requirements.txt`. Python 3.9+ is required; the local PDF reader uses POSIX resource limits.
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

### Shipping — Build 3 plan, not yet deployed

The current assignment requires the Python app to be public by November 23 at noon. Follow the Beginner lane. The GitHub Pages Product Page is not the Python app's deployment.

1. Finish and review local changes; commit real work on each actual build day. Do not alter dates to manufacture separate workdays.
2. Before public deployment, configure production host/port, a production WSGI server, session isolation, and bounded rate limits on every paid route, including `/api/workshop/introductions`.
3. Configure hosting secrets separately from Git. The private reviewed Body of Work guide must be provisioned privately on the host, never in public assets, repository, browser state, or exports.
4. Apply an approved provider spending cap; audit dependencies and source for secrets; perform the assignment's appropriate live access/rate-limit test and write `SECURITY.md` with evidence and remaining issues.
5. Verify a complete phone workflow and masked PostHog events/replay on the public app. Record the actual production URL, commands, deployment settings, and results here after deployment.
6. Update PRD v3/build log and submit the live URL, repository, lane, SECURITY.md link, and security-test screenshot. Check the live Icerynk assignment if requirements change.

### Ask me first

Get explicit authorization before deleting user data, making destructive database changes, changing secrets or access permissions, buying services or committing to new charges, or expanding a spending cap. Existing task-specific authorization still applies. Never publish personal demo inputs, exports, private screenshots, or source-book material. Explain and export active workshop work before a restart that would clear it.
