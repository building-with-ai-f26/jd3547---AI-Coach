# AGENTS.md — Coding Agent Operating Manual

> Give this file to your coding agent and check that it is using these instructions. Keep the stack, commands, and ground rules current.

## 1. Project Overview
- **What this repo builds:** AI Coach, a personal branding prototype. The first exercise turns career background and one reflection answer into a proposed theme the user can accept, edit, or reject.
- **Primary user & core workflow:** Professionals connecting their experiences into a clearer story. See the living PRD in `docs/index.html`. The local app is separate from that public Product Page.
- **Tech stack:** Python 3.9+ / Flask / plain HTML, CSS and JavaScript / OpenRouter (optional live mode). Session data is in memory; no database.

## 2. Commands
- **Install dependencies:** `python3 -m venv .venv`, then `.venv/bin/python -m pip install -r requirements.txt`
- **Run locally:** `.venv/bin/python app.py`; open `http://127.0.0.1:8787`. Bind only to loopback; do not enable debug mode with personal input.
- **Run deterministic tests:** `.venv/bin/python -m unittest discover -s tests -v`
- **Run model evals:** Not yet implemented. Current tests use stubs and validate the flow, provider failures and evidence checks; they do not establish coaching quality. A real API key and manual evaluation are still needed for live mode.
- **Prototype boundaries:** The sample is fixed and fictional. Never substitute it silently for a failed live request. Preserve exact user quotations and source attribution. Keep secrets server-side; never place personal input in cookies or browser storage.

## 3. Non-Negotiable Engineering Rules
1. **Plan before coding:** Before touching multiple files, propose a brief plan and wait for approval.
2. **Small batches:** Make small, focused changes that can be reviewed and explained by a human in a single Pull Request.
3. **Explainability:** Avoid unnecessary abstractions or dependencies. Help the human builder understand the main components, what changed, why it matters, what could break, and how it was checked.
4. **Verify changes:** Run relevant checks. For a reproducible logic bug, use a failing test to demonstrate the fix when practical. Record manual checks and known limitations; follow the selected Build 4 evaluation track.
5. **Zero secrets in code:** Never hardcode API keys, tokens, or credentials. Always read from environment variables (`.env`) and update `.env.example` when new variables are needed.
6. **Stop when looping:** If a fix fails twice in a row, stop, summarize what failed, and ask the human before trying a third approach.
