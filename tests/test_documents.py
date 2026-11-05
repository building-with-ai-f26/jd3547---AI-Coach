"""Real PDF parsing checks using generated fictional documents, never personal files."""

from io import BytesIO
import subprocess
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from documents import (DocumentError, MAX_DOCUMENT_CHARS, MAX_PDF_BYTES,
                       MAX_STREAM_BYTES, extract_pdf)


FICTIONAL_EXPERIENCES = [
    {"title": "Research and data review", "details": "Reviewed survey data for a student research project and documented gaps for the team.",
     "evidence": {"page": 1, "text": "Reviewed survey data for a student research project and documented gaps for the team."}},
    {"title": "Volunteer onboarding", "details": "Created a volunteer onboarding guide after asking new members what they needed to get started.",
     "evidence": {"page": 1, "text": "Created a volunteer onboarding guide after asking new members what they needed to get started."}},
    {"title": "Student hackathon", "details": "Coordinated a student hackathon team and organized its ideas into a small demonstration.",
     "evidence": {"page": 2, "text": "Coordinated a student hackathon team and organized its ideas into a small demonstration."}},
]


def make_pdf(pages, encrypted=False, raw_stream=None, compressed=False):
    """Build small text PDFs without a graphical PDF dependency; None means blank."""
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        if text is None and raw_stream is None:
            continue
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
            DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        if raw_stream is None:
            lines = ["BT /F1 11 Tf 36 756 Td"]
            for line in text.splitlines():
                safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                lines.append("(" + safe + ") Tj 0 -18 Td")
            lines.append("ET")
            content = "\n".join(lines).encode("ascii")
        else:
            content = raw_stream
        stream.set_data(content)
        if compressed:
            stream = stream.flate_encode()
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("fictional-test-password")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def fictional_cv_pdf():
    """Two-page fictional CV suitable for tests and the browser demonstration."""
    return make_pdf([
        "FICTIONAL SAMPLE CV - DEMONSTRATION ONLY\nNo real person's information is included.\n\n"
        "Student Research Project\n" + FICTIONAL_EXPERIENCES[0]["details"] + "\n\n"
        "Community Volunteer Group\n" + FICTIONAL_EXPERIENCES[1]["details"],
        "FICTIONAL SAMPLE CV - PAGE 2\n\nStudent Hackathon\n" + FICTIONAL_EXPERIENCES[2]["details"]
        + "\n\nThis document contains invented experience for software testing.",
    ])


class DocumentTests(unittest.TestCase):
    def test_two_page_fictional_document_preserves_page_numbers_and_exact_text(self):
        pages = extract_pdf(fictional_cv_pdf())
        self.assertEqual([page["page"] for page in pages], [1, 2])
        for experience in FICTIONAL_EXPERIENCES:
            evidence = experience["evidence"]
            self.assertIn(evidence["text"], pages[evidence["page"] - 1]["text"])
        self.assertIn("FICTIONAL", pages[0]["text"])

    def test_non_pdf_empty_and_oversized_files_fail_before_subprocess(self):
        with patch("documents.subprocess.run") as runner:
            for data in (b"", b"not a PDF", b"%PDF-" + b"x" * MAX_PDF_BYTES):
                with self.subTest(length=len(data)), self.assertRaises(DocumentError):
                    extract_pdf(data)
            runner.assert_not_called()

    def test_corrupt_pdf_has_actionable_safe_error(self):
        with self.assertRaises(DocumentError) as caught:
            extract_pdf(b"%PDF-1.7\nsensitive broken contents")
        self.assertIn("paste", str(caught.exception))
        self.assertNotIn("sensitive", str(caught.exception))

    def test_encrypted_pdf_is_rejected_without_password_prompt(self):
        with self.assertRaises(DocumentError) as caught:
            extract_pdf(make_pdf(["A fictional document containing readable career text."], encrypted=True))
        self.assertIn("encrypted", str(caught.exception))

    def test_page_limit_is_enforced_before_any_page_is_omitted(self):
        with self.assertRaises(DocumentError) as caught:
            extract_pdf(make_pdf(["Fictional career experience is described on this page."] * 11))
        self.assertIn("1–10 pages", str(caught.exception))

    def test_image_only_or_partly_unreadable_document_is_not_silently_imported(self):
        for pages, expected_page in (([None], 1), (["Fictional experience with a useful readable description.", None], 2)):
            with self.subTest(pages=pages), self.assertRaises(DocumentError) as caught:
                extract_pdf(make_pdf(pages))
            self.assertIn("Page %d" % expected_page, str(caught.exception))
            self.assertIn("paste", str(caught.exception))

    def test_extracted_character_limit_rejects_whole_document(self):
        with self.assertRaises(DocumentError) as caught:
            extract_pdf(make_pdf(["Fictional " + "a" * MAX_DOCUMENT_CHARS]))
        self.assertIn("30,000", str(caught.exception))

    def test_highly_compressed_content_stream_is_rejected(self):
        document = make_pdf(["unused"], raw_stream=b" " * (MAX_STREAM_BYTES + 1), compressed=True)
        self.assertLess(len(document), MAX_PDF_BYTES)
        with self.assertRaises(DocumentError):
            extract_pdf(document)

    def test_parser_timeout_is_safe_and_gives_paste_fallback(self):
        with patch("documents.subprocess.run", side_effect=subprocess.TimeoutExpired("parser", 8)):
            with self.assertRaises(DocumentError) as caught:
                extract_pdf(b"%PDF-1.7\n")
        self.assertIn("too long", str(caught.exception))
        self.assertIn("paste", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
