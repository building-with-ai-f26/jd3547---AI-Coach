"""Shared analytics delivery and private-DOM boundaries. No external requests."""
from html.parser import HTMLParser
from pathlib import Path
import unittest
from unittest.mock import patch

from app import create_app


class PrivateElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.private_ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        private = "data-analytics-private" in attrs or any(item[1] for item in self.stack)
        if private and attrs.get("id"):
            self.private_ids.add(attrs["id"])
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, private))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        with patch("app.load_dotenv"), patch.dict("app.os.environ", {}, clear=True):
            self.app = create_app({"TESTING": True, "OPENROUTER_API_KEY": ""})
        self.client = self.app.test_client()

    def test_only_exact_public_analytics_assets_are_served(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ("analytics.js", "analytics-config.js"):
            response = self.client.get("/analytics/" + filename)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, (root / "docs" / "assets" / filename).read_bytes())
            response.close()
        for path in ("/analytics/.env", "/analytics/app.py", "/analytics/../.env", "/analytics/prototype-nov-02.jpg"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_app_loads_shared_scripts_without_waiting_for_third_party(self):
        response = self.client.get("/")
        html = response.get_data(as_text=True)
        self.assertLess(html.index("/analytics/analytics-config.js"), html.index("/analytics/analytics.js"))
        self.assertLess(html.index("/analytics/analytics.js"), html.index("/static/app.js"))
        self.assertIn('defer data-analytics-surface="local_app"', html)
        policy = response.headers["Content-Security-Policy"]
        self.assertIn("https://us-assets.i.posthog.com", policy)
        self.assertIn("https://us.i.posthog.com", policy)
        self.assertNotIn("unsafe-inline", policy)
        self.assertNotIn("unsafe-eval", policy)
        self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")

    def test_every_personal_text_area_is_inside_an_explicit_replay_block(self):
        parser = PrivateElements()
        parser.feed(self.client.get("/").get_data(as_text=True))
        for element in ("document-file", "document-file-status", "background", "answer", "coaching-question",
                        "document-review-name", "document-review-cards", "proposal-theme", "proposal-statement",
                        "evidence-list", "edit-theme", "edit-statement", "review-background", "review-question",
                        "review-answer", "landscape-document-name", "landscape-experience-list", "landscape-theme",
                        "landscape-statement", "error-text"):
            self.assertIn(element, parser.private_ids, element)
