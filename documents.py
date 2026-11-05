"""Bounded PDF text extraction. Uploaded bytes never leave memory or go to disk."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys


MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 10
MAX_DOCUMENT_CHARS = 30000
MAX_STREAM_BYTES = 2 * 1024 * 1024
PARSER_TIMEOUT = 8
FALLBACK = "Please paste the relevant text instead, or upload a shorter PDF with selectable text."


class DocumentError(Exception):
    """An upload problem safe to display without PDF contents or parser details."""


def extract_pdf(data):
    """Parse in a short-lived process so malformed/compressed PDFs cannot hang Flask."""
    if not isinstance(data, bytes) or not data or len(data) > MAX_PDF_BYTES:
        raise DocumentError("Choose one nonempty PDF no larger than 5 MB. " + FALLBACK)
    if not data.startswith(b"%PDF-"):
        raise DocumentError("This file does not look like a PDF. " + FALLBACK)
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker"],
            input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=PARSER_TIMEOUT, check=False,
            # The parser does not need application credentials or the user's environment.
            env={"PATH": os.defpath},
        )
    except subprocess.TimeoutExpired:
        raise DocumentError("This PDF took too long to read safely. " + FALLBACK) from None
    except OSError:
        raise DocumentError("The PDF reader could not start. " + FALLBACK) from None
    if result.returncode != 0 or len(result.stdout) > 250000:
        raise DocumentError("This PDF could not be read within the size or processing limits. " + FALLBACK)
    try:
        payload = json.loads(result.stdout)
        if isinstance(payload, dict) and set(payload) == {"error"}:
            raise DocumentError(payload["error"])
        pages = payload["pages"]
        if not isinstance(pages, list) or not 1 <= len(pages) <= MAX_PDF_PAGES:
            raise ValueError("Invalid pages")
        for number, page in enumerate(pages, 1):
            if (not isinstance(page, dict) or set(page) != {"page", "text"}
                    or type(page["page"]) is not int or page["page"] != number
                    or not isinstance(page["text"], str) or not page["text"].strip()):
                raise ValueError("Invalid page")
        if sum(len(page["text"]) for page in pages) > MAX_DOCUMENT_CHARS:
            raise ValueError("Too much text")
        return pages
    except (ValueError, KeyError, TypeError):
        raise DocumentError("This PDF could not be read reliably. " + FALLBACK) from None


def _extract_in_worker(data):
    from pypdf import PdfReader, filters

    # Reject excessive expansion before parsing page drawing instructions.
    filters.ZLIB_MAX_OUTPUT_LENGTH = MAX_STREAM_BYTES
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise DocumentError("Password-protected or encrypted PDFs are not supported. " + FALLBACK)
    count = len(reader.pages)
    if not 1 <= count <= MAX_PDF_PAGES:
        raise DocumentError("Choose a PDF with 1–10 pages. " + FALLBACK)
    pages = []
    total = 0
    for number, page in enumerate(reader.pages, 1):
        contents = page.get_contents()
        if contents is None or len(contents.get_data()) > MAX_STREAM_BYTES:
            raise DocumentError("Page %d has no readable text or is too complex to process. " % number + FALLBACK)
        text = (page.extract_text() or "").strip()
        # Do not silently drop a scanned, blank, or visibly garbled page.
        bad_chars = sum(character == "\ufffd" or (ord(character) < 32 and character not in "\n\r\t")
                        for character in text)
        if len(text) < 20 or sum(character.isalnum() for character in text) < 10 or bad_chars > len(text) * .02:
            raise DocumentError("Page %d does not contain enough readable text. Scanned or partly unreadable PDFs are not supported. " % number + FALLBACK)
        total += len(text)
        if total > MAX_DOCUMENT_CHARS:
            raise DocumentError("This PDF contains more than 30,000 characters. " + FALLBACK)
        pages.append({"page": number, "text": text})
    return pages


def _worker():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        # macOS and Linux both provide RLIMIT_AS; failures still retain the wall
        # timeout, CPU cap, stream expansion cap, and document size limits.
        try:
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        except (ValueError, OSError):
            pass
        data = sys.stdin.buffer.read(MAX_PDF_BYTES + 1)
        if len(data) > MAX_PDF_BYTES:
            raise DocumentError("Choose a PDF no larger than 5 MB. " + FALLBACK)
        payload = {"pages": _extract_in_worker(data)}
    except DocumentError as exc:
        payload = {"error": str(exc)}
    except Exception:
        payload = {"error": "This PDF is damaged, unsupported, or too complex to read safely. " + FALLBACK}
    sys.stdout.write(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__" and sys.argv[1:] == ["--worker"]:
    _worker()
