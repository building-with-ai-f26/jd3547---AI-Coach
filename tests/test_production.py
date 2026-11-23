"""Production boundaries with fictional inputs; transport is disabled throughout."""
from concurrent.futures import ThreadPoolExecutor
import unittest
from unittest.mock import patch

from app import COOKIE, create_app
import production


HOST = "coach.example"
BASE = "https://" + HOST
IP = "198.51.100.10"


class ProductionTests(unittest.TestCase):
    def setUp(self):
        network = patch("coach.httpx.post", side_effect=AssertionError("No provider access in security tests"))
        self.network = network.start()
        self.addCleanup(network.stop)
        self.app = self.make_app()
        self.client = self.app.test_client()

    def make_app(self, **overrides):
        config = dict(TESTING=True, PRODUCTION=True, RENDER_PROXY=True, TRUSTED_HOSTS=[HOST],
                      OPENROUTER_API_KEY="", OPENROUTER_MODEL="test/model",
                      BODY_OF_WORK_SOURCE_PATH="/nonexistent/fictional-guide.json")
        config.update(overrides)
        return create_app(config)

    def get(self, path, client=None, ip=IP, headers=None):
        sent = {"X-Forwarded-Proto": "https", "CF-Connecting-IP": ip}
        sent.update(headers or {})
        return (client or self.client).get(path, base_url=BASE, headers=sent)

    def post(self, path, data=None, client=None, ip=IP, headers=None):
        sent = {"X-Coach-Request": "1", "Origin": BASE, "X-Forwarded-Proto": "https", "CF-Connecting-IP": ip}
        sent.update(headers or {})
        return (client or self.client).post(path, json={} if data is None else data, base_url=BASE, headers=sent)

    def test_twenty_shared_attempts_then_429_across_every_paid_route_without_calls(self):
        paths = sorted(production.PAID_PATHS)
        statuses = [self.post(paths[index % len(paths)]).status_code for index in range(30)]
        self.assertTrue(all(code != 429 for code in statuses[:20]), statuses)
        self.assertEqual(statuses[20:], [429] * 10)
        for path in paths:
            blocked = self.post(path)
            self.assertEqual(blocked.status_code, 429, path)
            self.assertTrue(1 <= int(blocked.headers["Retry-After"]) <= 3600)
        self.network.assert_not_called()

    def test_rate_limit_precedes_json_origin_and_payload_validation(self):
        self.app = self.make_app(AI_REQUEST_LIMIT=1)
        self.client = self.app.test_client()
        first = self.client.post("/api/start", data="invalid", base_url=BASE,
                                 headers={"CF-Connecting-IP": IP})
        self.assertEqual(first.status_code, 403)
        blocked = self.post("/api/answer", headers={"Origin": "https://attacker.example"})
        self.assertEqual(blocked.status_code, 429)
        self.network.assert_not_called()

    def test_cookie_deletion_and_reset_cannot_clear_hourly_allowance(self):
        self.assertEqual(self.get("/api/config").status_code, 200)
        original_cookie = self.client.get_cookie(COOKIE, domain=HOST).value
        for _ in range(20):
            self.assertEqual(self.post("/api/start").status_code, 400)
        self.assertEqual(self.post("/api/reset").status_code, 200)
        self.assertNotEqual(self.client.get_cookie(COOKIE, domain=HOST).value, original_cookie)
        # A new IP still has the same session allowance after an explicit reset.
        self.assertEqual(self.post("/api/start", ip="198.51.100.11").status_code, 429)
        # A discarded cookie still has the same IP allowance.
        fresh = self.app.test_client()
        self.assertEqual(self.post("/api/start", client=fresh).status_code, 429)

    def test_first_paid_request_also_counts_toward_new_session(self):
        self.app = self.make_app(AI_REQUEST_LIMIT=1)
        self.client = self.app.test_client()
        first = self.post("/api/start", {"mode": "sample"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.post("/api/start", {"mode": "sample"}, ip="198.51.100.11").status_code, 429)
        self.network.assert_not_called()

    def test_session_state_is_isolated_between_clients(self):
        first = self.post("/api/start", {"mode": "sample"})
        self.assertEqual(first.status_code, 200)
        other = self.app.test_client()
        self.assertEqual(self.get("/api/export", client=other, ip="198.51.100.11").status_code, 400)
        self.assertEqual(self.post("/api/answer", {"version": first.json["version"]},
                                   client=other, ip="198.51.100.11").status_code, 409)
        self.assertEqual(self.get("/api/export").json["exercise"]["stage"], "question")

    def test_global_paid_budget_covers_distinct_clients(self):
        self.app = self.make_app(AI_GLOBAL_LIMIT=2)
        self.client = self.app.test_client()
        for index in range(2):
            self.assertEqual(self.post("/api/start", ip="198.51.100." + str(index + 1)).status_code, 400)
        self.assertEqual(self.post("/api/answer", ip="198.51.100.3").status_code, 429)

    def test_general_api_limit_includes_reads_and_unknown_routes(self):
        self.app = self.make_app(API_REQUEST_LIMIT=3)
        self.client = self.app.test_client()
        for _ in range(3):
            self.assertEqual(self.get("/api/unknown").status_code, 404)
        limited = self.get("/api/workshop/state")
        self.assertEqual(limited.status_code, 429)
        self.assertTrue(1 <= int(limited.headers["Retry-After"]) <= 60)
        self.assertEqual(self.get("/health").status_code, 200)

    def test_session_creation_gets_are_limited_but_existing_session_remains(self):
        self.app = self.make_app(SESSION_CREATION_LIMIT=2)
        self.client = self.app.test_client()
        self.assertEqual(self.get("/api/config").status_code, 200)
        other = self.app.test_client()
        self.assertEqual(self.get("/api/workshop/state", client=other).status_code, 200)
        third = self.app.test_client()
        self.assertEqual(self.get("/api/workshop/config", client=third).status_code, 429)
        self.assertIsNone(third.get_cookie(COOKIE, domain=HOST))
        self.assertEqual(self.get("/api/config").status_code, 200)
        self.assertEqual(self.post("/api/reset").status_code, 200)

    def test_global_session_creation_cap_preserves_memory_capacity(self):
        self.app = self.make_app(SESSION_GLOBAL_LIMIT=2)
        self.client = self.app.test_client()
        for index in range(2):
            client = self.app.test_client()
            self.assertEqual(self.get("/api/config", client=client, ip="198.51.100." + str(index + 1)).status_code, 200)
        third = self.app.test_client()
        self.assertEqual(self.get("/api/config", client=third, ip="198.51.100.3").status_code, 429)

    def test_forged_xff_cannot_change_render_client_limit(self):
        self.app = self.make_app(AI_REQUEST_LIMIT=1)
        self.client = self.app.test_client()
        self.assertEqual(self.post("/api/start", headers={"X-Forwarded-For": "192.0.2.1, 10.0.0.1"}).status_code, 400)
        self.assertEqual(self.post("/api/start", headers={"X-Forwarded-For": "192.0.2.99, 10.0.0.2"}).status_code, 429)
        other = self.app.test_client()
        self.assertEqual(self.post("/api/start", client=other, ip="198.51.100.11").status_code, 400)

    def test_missing_or_malformed_render_identity_shares_conservative_bucket(self):
        self.app = self.make_app(AI_REQUEST_LIMIT=1)
        self.client = self.app.test_client()
        self.assertEqual(self.post("/api/start", ip="", headers={"X-Forwarded-For": "192.0.2.1"}).status_code, 400)
        self.assertEqual(self.post("/api/start", ip="not-an-ip", headers={"X-Forwarded-For": "192.0.2.99"}).status_code, 429)

    def test_secure_cookie_host_and_headers(self):
        response = self.get("/api/config")
        cookie = response.headers["Set-Cookie"]
        for attribute in ("Secure", "HttpOnly", "SameSite=Strict", "Max-Age=3600"):
            self.assertIn(attribute, cookie)
        self.assertEqual(response.headers["Strict-Transport-Security"], "max-age=31536000")
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertEqual(self.client.get("/health", base_url="https://attacker.example").status_code, 400)
        self.assertEqual(self.get("/health", headers={"X-Forwarded-Host": "attacker.example"}).status_code, 200)
        self.assertNotIn("Strict-Transport-Security", self.get("/health", headers={"X-Forwarded-Proto": "http"}).headers)

    def test_local_mode_ignores_all_proxy_headers(self):
        local = create_app({"TESTING": True, "OPENROUTER_API_KEY": "", "BODY_OF_WORK_SOURCE_PATH": "/nonexistent"})
        client = local.test_client()
        response = client.get("/api/config", headers={"X-Forwarded-Proto": "https", "CF-Connecting-IP": IP})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Secure;", response.headers["Set-Cookie"])
        self.assertNotIn("Strict-Transport-Security", response.headers)
        denied = client.post("/api/start", json={"mode": "sample"}, headers={
            "X-Coach-Request": "1", "Origin": "https://localhost", "X-Forwarded-Proto": "https"})
        self.assertEqual(denied.status_code, 403)

    def test_missing_key_fails_closed_and_health_does_not_allocate_cookie(self):
        response = self.get("/health")
        self.assertEqual(response.json, {"status": "ok"})
        self.assertNotIn("Set-Cookie", response.headers)
        self.assertFalse(self.get("/api/config").json["live_ready"])
        self.assertEqual(self.post("/api/start", {"mode": "live", "background": "Fictional input."}).status_code, 503)
        self.network.assert_not_called()

    def test_production_configuration_requires_exact_hosts_and_safe_limits(self):
        config = production.environment_config({"RENDER": "true", "RENDER_EXTERNAL_HOSTNAME": "my-app.onrender.com",
                                                "TRUSTED_HOSTS": "coach.example"})
        self.assertEqual(config["TRUSTED_HOSTS"], ["coach.example", "my-app.onrender.com"])
        self.assertTrue(config["RENDER_PROXY"])
        for overrides in ({"TRUSTED_HOSTS": []}, {"TRUSTED_HOSTS": [".example.com"]},
                          {"TRUSTED_HOSTS": ["https://example.com"]}, {"AI_REQUEST_LIMIT": 21}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.make_app(**overrides)


class LimiterTests(unittest.TestCase):
    def test_sliding_window_expiry_and_bounded_keys(self):
        now = [100.0]
        config = dict(production.LIMIT_DEFAULTS, RATE_LIMIT_ENABLED=True)
        limiter = production.RequestLimits(config, clock=lambda: now[0], max_keys=2)
        rule = [("test", "one", 1, 60)]
        limiter.admit(rule)
        with self.assertRaises(production.RateLimitExceeded) as error:
            limiter.admit(rule)
        self.assertEqual(error.exception.retry_after, 60)
        limiter.admit([("test", "two", 1, 60)])
        with self.assertRaises(production.RateLimitExceeded):
            limiter.admit([("test", "three", 1, 60)])
        self.assertEqual(len(limiter._buckets), 2)
        now[0] = 160.0
        limiter.admit(rule)
        self.assertEqual(len(limiter._buckets), 1)
        self.assertNotIn("198.51.100.10", limiter.identity("198.51.100.10"))

    def test_concurrent_attempts_cannot_exceed_quota(self):
        limiter = production.RequestLimits(dict(production.LIMIT_DEFAULTS, RATE_LIMIT_ENABLED=True))
        def attempt(_):
            try:
                limiter.paid("same-client", "same-session")
                return True
            except production.RateLimitExceeded:
                return False
        with ThreadPoolExecutor(max_workers=4) as pool:
            accepted = list(pool.map(attempt, range(30)))
        self.assertEqual(sum(accepted), 20)


if __name__ == "__main__":
    unittest.main()
