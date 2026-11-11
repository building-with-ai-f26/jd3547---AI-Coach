# AGENTS.md — Coding Agent Operating Manual

> Give this file to your coding agent and check that it is using these instructions. Keep the stack, commands, and ground rules current.

## 1. Project Overview
- **What this repo builds:** AI Coach, a personal branding prototype. Users paste career background or upload one résumé/CV PDF, review extracted experience cards, and add only approved cards to the landscape. One reflection answer then leads to a proposed theme they can accept, edit, or reject.
- **Primary user & core workflow:** Professionals connecting their experiences into a clearer story. See the living PRD in `docs/index.html`. The local app is separate from that public Product Page.
- **Tech stack:** Python 3.9+ / Flask / pypdf / plain HTML, CSS and JavaScript / OpenRouter (optional live mode) / PostHog usage events and masked replay. Exercise data is in memory; no database.

## 2. Commands
- **Working folder:** Jason's checkout is `~/Desktop/jd3547---AI-Coach`; run commands from the project root. Beginner instructions are in `README.md`.
- **Install dependencies:** On first setup, `python3 -m venv .venv`; reuse a working existing environment. Then `.venv/bin/python -m pip install -r requirements.txt`. Python 3.9+ is required; the local PDF reader uses POSIX resource limits.
- **Private configuration:** Use `cp -n .env.example .env` to create a missing `.env` without replacing existing settings. Read configuration names from `.env.example`; do not print or paste secret `.env` values. `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` enable optional live mode. Sample mode works without them.
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
| `documents.py` | Memory-only PDF extraction in a bounded subprocess; no original PDF saved. |
| `content/method.json` | Reviewed article source, adaptation, attribution, and coverage limits. |
| `templates/app.html`, `static/app.js`, `static/app.css` | Local browser interface. |
| `static/dictation.js`, `tests/dictation.test.js` | Optional browser speech-to-text for live reflections; bounded, editable, no audio persistence. Run focused checks with `node tests/dictation.test.js`. |
| `docs/index.html` | Public Product Page, living PRD, and honest weekly log; separate from the local application. |
| `docs/assets/analytics-config.js`, `docs/assets/analytics.js` | Shared public PostHog configuration and event/privacy logic; Flask serves the same files under `/analytics/`. |
| `tests/test_app.py`, `tests/test_coach.py`, `tests/test_documents.py` | Deterministic tests using fictional inputs and mocked providers. |
| `tests/test_analytics.py`, `tests/analytics.test.js` | Analytics asset/privacy checks and optional JavaScript allowlist checks. |
| `.env.example`, `.gitignore` | Placeholder settings and exclusions for secrets/dependencies. Never overwrite a user's `.env`. |
| `README.md`, `AGENTS.md`, `CLAUDE.md` | Human setup instructions, agent operating rules, and Claude Code's pointer to these rules. |

PDF import accepts one selectable-text PDF up to 5 MB, 10 pages, and 30,000 extracted characters, producing at most six cards. The user reviews those cards before they enter the landscape. Preserve page/quote evidence and mark edits; use only approved titles/descriptions in subsequent coaching requests. Unreviewed import cards cannot be exported. Do not weaken source, identifier, version, or same-origin checks to accommodate a provider failure.

Session content is held only in the Flask process. The session cookie lasts one hour; server records inactive for over an hour are removed on a subsequent session request. Reset clears the current exercise and server shutdown clears all sessions. Browser refresh does not restore an exercise. Exports are local records, not resumable sessions, and may include a pending theme clearly marked as a proposal. Neither reset nor shutdown deletes downloaded files or data already sent to external providers.

Keep personal documents, exports, and screenshots outside the public repository; `.gitignore` does not automatically exclude every private document. Do not log prompts, document text, filenames, answers, accepted wording, or provider responses containing personal material.

Dictation uses the browser's SpeechRecognition service, which may process audio remotely. Keep the disclosure visible before microphone use. Preserve earlier text, invalidate late callbacks after cancellation/reset, enforce the 60-second limit, and require transcript review and explicit submission. Interim speech must remain inside an analytics-blocked element. Do not claim microphone accuracy from mocked recognition tests.

## 5. Analytics boundaries and verification

The public PostHog ingestion token in `docs/assets/analytics-config.js` is intentionally browser-visible. It is not a personal PostHog API key or an OpenRouter secret. Never put either secret there. The shared helper is enabled by configuration, honors Do Not Track/Global Privacy Control, and supports disabling collection with `enabled: false`.

Keep analytics events and properties inside the helper's allowlists: fixed action/stage/mode categories and small card counts only. Preserve URL/referrer sanitization. Never send personal text, filenames, evidence, theme wording, free-form errors, or private documents as event properties. Do not enable identification, person profiles, autocapture, console capture, or network payload capture. Replay must continue masking text/inputs and blocking all personal containers and images. Review new UI surfaces for replay exposure before adding them.

The SDK is configured for in-memory identifiers; exercise cookies and server state are separate. PostHog is an external recipient. Do not claim that local reset removes remote events, or invent remote retention/deletion guarantees.

Use `?analytics_test=build2-nov11` for the dated builder-check marker; it is a fixed allowlisted marker, not arbitrary query-string capture. Verify actual events for `app_surface` values `local_app` and `product_page`, and inspect a masked replay using fictional input. The private dashboard is https://us.posthog.com/project/697808/dashboard/2337055. Record what was observed in the Build 2 log; deterministic tests and configured settings alone do not establish event receipt, replay masking, user adoption, or coaching value.
