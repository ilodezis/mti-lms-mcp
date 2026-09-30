import base64
import hashlib
import json
import os
import re
import unittest
import urllib.parse
from starlette.testclient import TestClient

import server

CALLBACK = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")


class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["MCP_CLIENT_SECRET"] = "test-client-secret"
        cls.app = server.create_app(token="test-secret-token", transport="http")
        cls.client_ctx = TestClient(cls.app, base_url="http://127.0.0.1:8030")
        cls.client = cls.client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_ctx.__exit__(None, None, None)

    def test_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "lms-mcp")
        self.assertEqual(data.get("version"), "4.0.3")

    def test_root(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("status"), "ok")

    def test_cors_options(self):
        res = self.client.options("/mcp")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("access-control-allow-origin"), "*")

    def test_unauthorized(self):
        res = self.client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        self.assertEqual(res.status_code, 401)

    def test_authorized_bearer(self):
        res = self.client.post(
            "/mcp",
            headers={
                "Authorization": "Bearer test-secret-token",
                "Accept": "application/json, text/event-stream",
            },
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("result", res.text)

    def test_oauth_metadata(self):
        res = self.client.get("/.well-known/oauth-authorization-server")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("authorization_endpoint", data)
        self.assertIn("token_endpoint", data)
        self.assertEqual(data.get("code_challenge_methods_supported"), ["S256"])

        res_pr = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(res_pr.status_code, 200)
        data_pr = res_pr.json()
        self.assertIn("resource", data_pr)

    def _code(self, redirect_uri=CALLBACK):
        res = self.client.get("/oauth/authorize", params={
            "response_type": "code",
            "client_id": "mti-lms",
            "redirect_uri": redirect_uri,
            "state": "test-state-123",
            "code_challenge": CHALLENGE,
            "code_challenge_method": "S256",
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn("LMS MCP Server", res.text)
        match = re.search(r'code=([^&"\'>;]+)', res.text)
        self.assertTrue(match, "Code not found in authorize response HTML")
        return match.group(1)

    def _exchange(self, code, **overrides):
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": "mti-lms",
            "client_secret": "test-client-secret",
            "redirect_uri": CALLBACK,
            "code_verifier": VERIFIER,
        }
        data.update(overrides)
        return self.client.post("/oauth/token", data={k: v for k, v in data.items() if v is not None})

    def test_oauth_flow_and_token_exchange(self):
        res = self._exchange(self._code())
        self.assertEqual(res.status_code, 200)
        token_data = res.json()
        self.assertEqual(token_data["access_token"], "test-secret-token")
        self.assertEqual(token_data["token_type"], "Bearer")

    def test_token_refused_without_client_secret(self):
        self.assertEqual(self._exchange(self._code(), client_secret=None).status_code, 401)

    def test_token_refused_with_wrong_client_secret(self):
        self.assertEqual(self._exchange(self._code(), client_secret="nope").status_code, 401)

    def test_token_refused_without_pkce_verifier(self):
        self.assertEqual(self._exchange(self._code(), code_verifier=None).status_code, 400)

    def test_token_refused_for_other_redirect_uri(self):
        res = self._exchange(self._code(), redirect_uri="https://claude.ai/somewhere-else")
        self.assertEqual(res.status_code, 400)

    def test_authorize_refuses_foreign_redirect_uri(self):
        res = self.client.get("/oauth/authorize", params={"client_id": "mti-lms", "redirect_uri": "https://evil.example/cb"})
        self.assertEqual(res.status_code, 400)
        self.assertNotIn("code=", res.text)

    def test_authorize_escapes_client_id(self):
        res = self.client.get("/oauth/authorize", params={"client_id": "<script>x</script>", "redirect_uri": CALLBACK})
        self.assertNotIn("<script>x</script>", res.text)


class TestStartupRequiresSecrets(unittest.TestCase):
    def _refuses_without(self, name):
        saved_env = os.environ.pop(name, None)
        saved_cfg = server.CFG.pop(name, None)
        try:
            with self.assertRaises(RuntimeError):
                server.create_app(token=None if name == "MCP_TOKEN" else "t", transport="http")
        finally:
            if saved_env is not None:
                os.environ[name] = saved_env
            if saved_cfg is not None:
                server.CFG[name] = saved_cfg

    def test_http_app_refuses_to_start_without_token(self):
        self._refuses_without("MCP_TOKEN")

    def test_http_app_refuses_to_start_without_client_secret(self):
        self._refuses_without("MCP_CLIENT_SECRET")


class TestRelogin(unittest.TestCase):
    def test_relogin_over_stale_cookie_saves_fresh_one(self):
        import tempfile
        from pathlib import Path

        import httpx

        def lms(request):
            return httpx.Response(200, text="<html>ok</html>", headers=[
                ("set-cookie", "__ddg9_=fresh; Domain=.mti.moscow; Path=/"),
                ("set-cookie", "PHPSESSID=new; Path=/"),
            ])

        saved_env, saved_client, saved_cfg = server.ENV, server.client, dict(server.CFG)
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / ".env"
            env.write_text("LMS_COOKIE=__ddg9_=stale\nLMS_LOGIN=u\n", encoding="utf-8")
            server.ENV = env
            server.client = httpx.Client(base_url=server.BASE, transport=httpx.MockTransport(lms))
            server.client.cookies.set("__ddg9_", "stale", domain="lms.mti.moscow")
            server.CFG.update(LMS_LOGIN="u", LMS_PASSWORD="p")
            try:
                server._login()
            finally:
                server.ENV, server.client = saved_env, saved_client
                server.CFG.clear()
                server.CFG.update(saved_cfg)
            line = next(l for l in env.read_text(encoding="utf-8").splitlines() if l.startswith("LMS_COOKIE="))

        self.assertEqual(line.count("__ddg9_="), 1)
        self.assertIn("__ddg9_=fresh", line)
        self.assertIn("PHPSESSID=new", line)


if __name__ == "__main__":
    unittest.main()
