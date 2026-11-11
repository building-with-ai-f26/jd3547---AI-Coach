"""Local-only Build 1 prototype. Session content stays in server memory."""

from copy import deepcopy
from io import BytesIO
import json
import os
from pathlib import Path
import secrets
import threading
import time

from dotenv import load_dotenv
from flask import Flask, Request, g, jsonify, make_response, render_template, request, send_from_directory

from coach import CoachError, LiveCoach, SAMPLE, SAMPLE_PROPOSAL, SAMPLE_QUESTION, SOURCE, SOURCE_IDS, valid_text
from documents import DocumentError, MAX_PDF_BYTES, MAX_PDF_PAGES, extract_pdf


MAX_CHARS = 6000
SESSION_TTL = 3600
COOKIE = "coach_session"


class MemoryUploadRequest(Request):
    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        # Werkzeug's default stream spills larger files to a temporary disk file.
        # The upload route's hard request cap makes an in-memory stream bounded.
        return BytesIO()


def create_app(config=None, coach=None):
    load_dotenv(Path(__file__).parent / ".env")
    app = Flask(__name__)
    app.request_class = MemoryUploadRequest
    app.config.update(
        MAX_CONTENT_LENGTH=40000,
        MAX_FORM_PARTS=2,
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
            upload = request.path == "/api/documents"
            if upload:
                request.max_content_length = MAX_PDF_BYTES + 65536
            expected_type = request.mimetype == "multipart/form-data" if upload else request.is_json
            if request.headers.get("X-Coach-Request") != "1" or not expected_type:
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
            "default-src 'self'; script-src 'self' https://us-assets.i.posthog.com; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self' https://us.i.posthog.com https://us-assets.i.posthog.com; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        if getattr(g, "new_sid", None):
            response.set_cookie(COOKIE, g.new_sid, httponly=True, samesite="Strict", max_age=SESSION_TTL)
        return response

    @app.errorhandler(413)
    def too_large(_error):
        if request.path == "/api/documents":
            return error("Choose one PDF no larger than 5 MB, or paste the relevant text instead.", 413)
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

    @app.get("/analytics/<filename>")
    def analytics_asset(filename):
        # Share exactly these two public files with GitHub Pages; never expose a
        # generic repository-file route or server configuration.
        if filename not in {"analytics.js", "analytics-config.js"}:
            return error("Not found.", 404)
        return send_from_directory(Path(__file__).parent / "docs" / "assets", filename)

    @app.get("/api/config")
    def configuration():
        # Establish the cookie before a slow model call so Start over can cancel it.
        with lock:
            if not session(create=True):
                return error("Too many sessions are open. Please restart the local server.", 503)
        return jsonify(live_ready=ready(), model=app.config["OPENROUTER_MODEL"] if ready() else None,
                       source=SOURCE, sample=SAMPLE, max_chars=MAX_CHARS,
                       document_limits={"max_bytes": MAX_PDF_BYTES, "max_pages": MAX_PDF_PAGES,
                                        "max_cards": 6})

    @app.post("/api/documents")
    def upload_document():
        if not ready():
            return error("Document review needs an API key in the local .env file. You can still use the fictional example.", 503)
        if set(request.files) != {"file"} or len(request.files.getlist("file")) != 1 or request.form:
            return error("Choose exactly one PDF file, or paste the relevant text instead.")
        uploaded = request.files["file"]
        name = (uploaded.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        name = "".join(character for character in name if character.isprintable())[:160]
        if not name.lower().endswith(".pdf"):
            return error("Choose a PDF file, or paste the relevant text instead.")
        data = uploaded.stream.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES:
            return error("Choose a PDF no larger than 5 MB, or paste the relevant text instead.", 413)
        with lock:
            # A cookie must already exist before a slow parse/model call so reset
            # can invalidate that call, including the first upload in a browser.
            if not session():
                return error("Please reload the workshop before uploading your PDF.", 409)
            ticket, failure = reserve()
        if failure:
            return failure
        try:
            pages = extract_pdf(data)
            page_count = len(pages)
            with lock:
                entry = sessions.get(ticket[0])
                if not entry or entry["operation"] != ticket[1] or entry["version"] != ticket[2]:
                    return error("This session was restarted. The upload was discarded.", 409)
            cards = generator.extract_experiences(pages, app.config)
        except DocumentError as exc:
            return finish(ticket, failure=exc, failure_status=400)
        except CoachError as exc:
            return finish(ticket, failure=exc)
        experience_cards = [dict(id=secrets.token_hex(12), title=card["title"], details=card["details"],
                                 evidence=deepcopy(card["evidence"])) for card in cards]
        state = dict(mode="live", stage="import_review", background=None, question=None, answer=None,
                     proposal=None, accepted=None, decision=None, source_ids=SOURCE_IDS,
                     document={"id": secrets.token_hex(12), "name": name,
                               "page_count": page_count, "warnings": []},
                     experience_cards=experience_cards, accepted_experiences=[])
        return finish(ticket, state)

    @app.post("/api/documents/review")
    def review_document():
        data = body()
        with lock:
            ticket, failure = reserve("import_review", data.get("version"))
            if failure:
                return failure
            state = ticket[3]
            supplied = data.get("cards")
            original = {card["id"]: card for card in state["experience_cards"]}
            if not isinstance(supplied, list) or not 1 <= len(supplied) <= 6 or len(supplied) != len(original):
                return finish(ticket, failure="Review every experience card before continuing.", failure_status=400)
            accepted = []
            seen = set()
            for card in supplied:
                if (not isinstance(card, dict) or set(card) != {"id", "include", "title", "details"}
                        or not isinstance(card["id"], str) or card["id"] not in original or card["id"] in seen
                        or type(card["include"]) is not bool
                        or not isinstance(card["title"], str) or len(card["title"]) > 120
                        or not isinstance(card["details"], str) or len(card["details"]) > 600
                        or (card["include"] and (not card["title"].strip() or not card["details"].strip()))):
                    return finish(ticket, failure="The card review was incomplete or changed. Please review the displayed cards again.", failure_status=400)
                seen.add(card["id"])
                if card["include"]:
                    approved = deepcopy(original[card["id"]])
                    approved.update(title=card["title"].strip(), details=card["details"].strip())
                    approved["user_edited"] = any(approved[field] != original[card["id"]][field]
                                                  for field in ("title", "details"))
                    accepted.append(approved)
            if not accepted:
                return finish(ticket, failure="Keep at least one experience, or use Start over to discard the upload.", failure_status=400)
            state.update(stage="imported", accepted_experiences=accepted, experience_cards=[])
            return finish(ticket, state)

    @app.post("/api/start")
    def start():
        data = body()
        mode = data.get("mode")
        if mode not in ("sample", "live"):
            return error("Choose the fictional example or the live exercise.")
        if mode == "live" and not ready():
            return error("Live coaching needs an API key in the local .env file. The fictional example is available now.", 503)
        if data.get("use_document") is True:
            if mode != "live":
                return error("Document experiences can only be used in live coaching.")
            with lock:
                ticket, failure = reserve("imported", data.get("version"))
            if failure:
                return failure
            imported = ticket[3]
            background = "\n\n".join(card["title"] + "\n" + card["details"]
                                      for card in imported["accepted_experiences"])
        else:
            imported = None
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
        if imported:
            state.update(document=imported["document"], accepted_experiences=imported["accepted_experiences"],
                         experience_cards=[])
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
            if state["stage"] == "import_review":
                return error("Review the experience cards before exporting. Unapproved cards are not exported.", 409)
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
