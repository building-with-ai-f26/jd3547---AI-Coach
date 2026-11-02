"""Local-only Build 1 prototype. Session content stays in server memory."""

from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import threading
import time

from dotenv import load_dotenv
from flask import Flask, g, jsonify, make_response, render_template, request

from coach import CoachError, LiveCoach, SAMPLE, SAMPLE_PROPOSAL, SAMPLE_QUESTION, SOURCE, SOURCE_IDS, valid_text


MAX_CHARS = 6000
SESSION_TTL = 3600
COOKIE = "coach_session"


def create_app(config=None, coach=None):
    load_dotenv(Path(__file__).parent / ".env")
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=40000,
        TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"],
        OPENROUTER_API_KEY=os.getenv("OPENROUTER_API_KEY", ""),
        OPENROUTER_MODEL=os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.6"),
    )
    if config:
        app.config.update(config)
    generator = coach or LiveCoach()
    sessions = {}
    lock = threading.RLock()

    def ready():
        key = app.config["OPENROUTER_API_KEY"].strip()
        return bool(key and "replace" not in key.lower() and app.config["OPENROUTER_MODEL"].strip())

    def error(message, status=400):
        return jsonify(error=message), status

    @app.before_request
    def protect_request():
        if request.method == "POST":
            if request.headers.get("X-Coach-Request") != "1" or not request.is_json:
                return error("Please use the app to submit this request.", 403)
            origin = request.headers.get("Origin")
            if origin and origin != request.host_url.rstrip("/"):
                return error("This request came from a different website.", 403)
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                return error("This request came from a different website.", 403)
        g.sid = request.cookies.get(COOKIE)

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if getattr(g, "new_sid", None):
            response.set_cookie(COOKIE, g.new_sid, httponly=True, samesite="Strict", max_age=SESSION_TTL)
        return response

    @app.errorhandler(413)
    def too_large(_error):
        return error("That text is too long. Please use a shorter example.", 413)

    @app.errorhandler(400)
    def malformed(_error):
        return error("The request could not be read. Please try again.")

    def body():
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}

    def session(create=False):
        # Caller holds lock. Cookies contain an opaque identifier, never personal text.
        now = time.monotonic()
        for sid in list(sessions):
            if now - sessions[sid]["touched"] > SESSION_TTL:
                del sessions[sid]
        entry = sessions.get(g.sid)
        if entry is None and create:
            if len(sessions) >= 100:
                return None
            g.sid = g.new_sid = secrets.token_urlsafe(32)
            entry = {"state": None, "version": 0, "operation": None, "touched": now}
            sessions[g.sid] = entry
        if entry:
            entry["touched"] = now
        return entry

    def reserve(stage=None, version=None):
        # Caller holds lock. An operation ID prevents a delayed model response from
        # restoring content after Start over, or a double click from paying twice.
        entry = session(create=stage is None)
        if not entry:
            return None, error("This session expired. Please start again.", 409)
        if entry["operation"]:
            return None, error("A request is already running. Please wait.", 409)
        if stage is not None:
            state = entry["state"]
            if not state or state["stage"] != stage or type(version) is not int or version != entry["version"]:
                return None, error("This step has already changed. Please start again if needed.", 409)
        entry["operation"] = secrets.token_hex(16)
        return (g.sid, entry["operation"], entry["version"], deepcopy(entry["state"])), None

    def finish(ticket, state=None, failure=None, failure_status=502):
        sid, operation, version, _ = ticket
        with lock:
            entry = sessions.get(sid)
            if not entry or entry["operation"] != operation or entry["version"] != version:
                return error("This session was restarted. The old response was discarded.", 409)
            entry["operation"] = None
            if failure:
                return error(str(failure), failure_status)
            entry["version"] += 1
            state["version"] = entry["version"]
            entry["state"] = state
            return jsonify(deepcopy(state))

    @app.get("/")
    def index():
        return render_template("app.html")

    @app.get("/api/config")
    def configuration():
        # Establish the cookie before a slow model call so Start over can cancel it.
        with lock:
            if not session(create=True):
                return error("Too many sessions are open. Please restart the local server.", 503)
        return jsonify(live_ready=ready(), model=app.config["OPENROUTER_MODEL"] if ready() else None,
                       source=SOURCE, sample=SAMPLE, max_chars=MAX_CHARS)

    @app.post("/api/start")
    def start():
        data = body()
        mode = data.get("mode")
        if mode not in ("sample", "live"):
            return error("Choose the fictional example or the live exercise.")
        if mode == "live" and not ready():
            return error("Live coaching needs an API key in the local .env file. The fictional example is available now.", 503)
        background = SAMPLE["background"] if mode == "sample" else data.get("background")
        if not valid_text(background, MAX_CHARS):
            return error("Add some background, up to 6,000 characters.")
        with lock:
            ticket, failure = reserve()
        if failure:
            return failure
        try:
            question = SAMPLE_QUESTION if mode == "sample" else generator.question(background, app.config)
        except CoachError as exc:
            return finish(ticket, failure=exc)
        state = dict(mode=mode, stage="question", background=background, question=question,
                     answer=None, proposal=None, accepted=None, decision=None, source_ids=SOURCE_IDS)
        return finish(ticket, state)

    @app.post("/api/answer")
    def answer():
        data = body()
        with lock:
            ticket, failure = reserve("question", data.get("version"))
        if failure:
            return failure
        state = ticket[3]
        answer_text = SAMPLE["answer"] if state["mode"] == "sample" else data.get("answer")
        if not valid_text(answer_text, MAX_CHARS):
            return finish(ticket, failure="Add your answer, up to 6,000 characters.", failure_status=400)
        try:
            proposal = deepcopy(SAMPLE_PROPOSAL) if state["mode"] == "sample" else generator.propose(
                state["background"], state["question"], answer_text, app.config)
        except CoachError as exc:
            return finish(ticket, failure=exc)
        state.update(answer=answer_text, proposal=proposal, stage="review")
        return finish(ticket, state)

    @app.post("/api/review")
    def review():
        data = body()
        decision = data.get("decision")
        if decision not in ("accept", "edit", "reject"):
            return error("Choose accept, edit or reject.")
        if decision == "edit" and (not valid_text(data.get("theme"), 160) or not valid_text(data.get("statement"), 600)):
            return error("Add a theme (up to 160 characters) and a statement (up to 600).")
        with lock:
            ticket, failure = reserve("review", data.get("version"))
            if failure:
                return failure
            state = ticket[3]
            accepted = deepcopy(state["proposal"]) if decision != "reject" else None
            if decision == "edit":
                accepted.update(theme=data["theme"].strip(), statement=data["statement"].strip())
            state.update(stage="complete", accepted=accepted, decision=decision, proposal=None)
            return finish(ticket, state)

    @app.post("/api/reset")
    def reset():
        with lock:
            if g.sid in sessions:
                del sessions[g.sid]
            session(create=True)
        return jsonify(ok=True)

    @app.get("/api/export")
    def export():
        with lock:
            entry = session()
            if not entry or not entry["state"]:
                return error("There is no exercise to export yet.")
            state = deepcopy(entry["state"])
        payload = {
            "format": "ai-coach-exercise-v1", "fictional_sample": state["mode"] == "sample",
            "note": "Fictional walkthrough; no AI call was made." if state["mode"] == "sample" else "AI-generated interpretations need your review.",
            "exercise": state, "sources": [SOURCE],
        }
        response = make_response(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        response.headers["Content-Disposition"] = 'attachment; filename="ai-coach-exercise.json"'
        return response

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8787, debug=False)
