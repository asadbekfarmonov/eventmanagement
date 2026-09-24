import hashlib
import hmac
import importlib
import os
import tempfile
import time
import unittest

from fastapi.testclient import TestClient


def _telegram_login_hash(bot_token: str, fields: dict) -> str:
    """Compute a Telegram Login Widget hash: secret = sha256(bot_token)."""
    data_check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    return hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()


class TelegramWidgetLoginTests(unittest.TestCase):
    """Batch B2: POST /api/web/login/telegram (Telegram Login Widget)."""

    bot_token = "123456:test-bot-token-for-widget"

    def _reload_server(self, bot_token: str, bot_username: str = ""):
        os.environ["DATABASE_PATH"] = self.db_path
        os.environ["ADMIN_IDS"] = "7164876915"
        os.environ["BOT_TOKEN"] = bot_token
        os.environ["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "1"
        os.environ["WEB_APP_URL"] = "https://example.invalid"
        os.environ["UPLOAD_DIR"] = os.path.join(self.temp_dir.name, "uploads")
        os.environ["EMAIL_LOGIN_DEV_MODE"] = "1"
        os.environ["TELEGRAM_LOGIN_BOT_USERNAME"] = bot_username
        os.environ["TELEGRAM_AUTH_MAX_AGE_SECONDS"] = "86400"
        import ticketbot.miniapp_server as miniapp_server

        server = importlib.reload(miniapp_server)
        return server

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "batch_b2_test.db")
        self._env_keys = (
            "DATABASE_PATH",
            "ADMIN_IDS",
            "BOT_TOKEN",
            "MINIAPP_ALLOW_TG_ID_FALLBACK",
            "WEB_APP_URL",
            "UPLOAD_DIR",
            "EMAIL_LOGIN_DEV_MODE",
            "TELEGRAM_LOGIN_BOT_USERNAME",
            "TELEGRAM_AUTH_MAX_AGE_SECONDS",
        )
        self._env_backup = {key: os.environ.get(key) for key in self._env_keys}
        self.server = self._reload_server(self.bot_token, bot_username="budapest_tunderi_bot")
        self.client = TestClient(self.server.app)

    def tearDown(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.temp_dir.cleanup()

    def _valid_payload(self, tg_id: int = 511308234, auth_date=None) -> dict:
        if auth_date is None:
            auth_date = int(time.time())
        fields = {
            "id": str(int(tg_id)),
            "first_name": "Tele",
            "auth_date": str(int(auth_date)),
        }
        payload = {
            "id": int(tg_id),
            "first_name": "Tele",
            "auth_date": int(auth_date),
            "hash": _telegram_login_hash(self.bot_token, fields),
        }
        return payload

    def test_valid_hash_logs_in_and_sets_cookie(self) -> None:
        payload = self._valid_payload()
        resp = self.client.post("/api/web/login/telegram", json=payload)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["profile"]["tg_id"], 511308234)
        self.assertEqual(body["profile"]["name"], "Tele")
        self.assertEqual(body["profile"]["source"], "telegram")
        # A website session cookie must be set so the user is logged in on the website.
        self.assertIn("bt_web_session", resp.cookies)
        # And the session is usable: /api/me returns the same profile via the cookie.
        me = self.client.get("/api/me")
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["profile"]["tg_id"], 511308234)

    def test_tampered_hash_is_rejected(self) -> None:
        payload = self._valid_payload()
        payload["hash"] = "0" * 64
        resp = self.client.post("/api/web/login/telegram", json=payload)
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_tampered_field_is_rejected(self) -> None:
        payload = self._valid_payload()
        # Change first_name after signing -> hash no longer matches.
        payload["first_name"] = "Attacker"
        resp = self.client.post("/api/web/login/telegram", json=payload)
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_stale_auth_date_is_rejected(self) -> None:
        stale = int(time.time()) - (86400 + 3600)
        payload = self._valid_payload(auth_date=stale)
        resp = self.client.post("/api/web/login/telegram", json=payload)
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_missing_bot_token_returns_503(self) -> None:
        self.client.close()
        server = self._reload_server(bot_token="", bot_username="")
        client = TestClient(server.app)
        try:
            payload = {
                "id": 511308234,
                "first_name": "Tele",
                "auth_date": int(time.time()),
                "hash": "deadbeef",
            }
            resp = client.post("/api/web/login/telegram", json=payload)
            self.assertEqual(resp.status_code, 503, resp.text)
        finally:
            client.close()

    def test_auth_config_exposes_telegram_bot_username(self) -> None:
        resp = self.client.get("/api/web/auth_config")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["telegram_bot_username"], "budapest_tunderi_bot")

    def test_auth_config_defaults_bot_username_empty(self) -> None:
        self.client.close()
        server = self._reload_server(self.bot_token, bot_username="")
        client = TestClient(server.app)
        try:
            resp = client.get("/api/web/auth_config")
            self.assertEqual(resp.json()["telegram_bot_username"], "")
        finally:
            client.close()


    def test_endpoint_is_rate_limited(self) -> None:
        """Task requirement: the Telegram login endpoint must be rate limited.

        The default EMAIL_LOGIN_RATE_LIMIT is 8 requests/window. The limiter runs
        BEFORE hash verification, so repeated bad attempts still count and the
        endpoint eventually returns 429 (brute-force protection)."""
        limit = self.server.EMAIL_LOGIN_RATE_LIMIT
        payload = self._valid_payload()
        payload["hash"] = "0" * 64  # bad hash -> 401, but still counts toward the limit
        statuses = []
        for _ in range(limit + 2):
            resp = self.client.post("/api/web/login/telegram", json=payload)
            statuses.append(resp.status_code)
        self.assertIn(429, statuses, statuses)
        # The very first request must not be a 429 (limiter is not open-by-default).
        self.assertNotEqual(statuses[0], 429, statuses)

    def test_initdata_hmac_variant_is_rejected(self) -> None:
        """Signature-bypass guard: the Login Widget uses secret=sha256(BOT_TOKEN).
        A hash computed with the Mini App initData scheme
        (secret=HMAC_SHA256(key='WebAppData', msg=BOT_TOKEN)) must NOT be accepted."""
        auth_date = int(time.time())
        fields = {"id": "511308234", "first_name": "Tele", "auth_date": str(auth_date)}
        data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
        webapp_secret = hmac.new(b"WebAppData", self.bot_token.encode("utf-8"), hashlib.sha256).digest()
        wrong_hash = hmac.new(webapp_secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        payload = {"id": 511308234, "first_name": "Tele", "auth_date": auth_date, "hash": wrong_hash}
        resp = self.client.post("/api/web/login/telegram", json=payload)
        self.assertEqual(resp.status_code, 401, resp.text)

    def test_nonpositive_id_is_rejected(self) -> None:
        """Even with a correctly-signed payload, a non-positive Telegram id must be
        rejected (401) and must not create a session."""
        auth_date = int(time.time())
        fields = {"id": "0", "first_name": "Tele", "auth_date": str(auth_date)}
        payload = {
            "id": 0,
            "first_name": "Tele",
            "auth_date": auth_date,
            "hash": _telegram_login_hash(self.bot_token, fields),
        }
        resp = self.client.post("/api/web/login/telegram", json=payload)
        self.assertEqual(resp.status_code, 401, resp.text)
        self.assertNotIn("bt_web_session", resp.cookies)

    def test_empty_hash_is_rejected_by_validation(self) -> None:
        """An empty hash must never authenticate (model validation -> 422, not a login)."""
        payload = self._valid_payload()
        payload["hash"] = ""
        resp = self.client.post("/api/web/login/telegram", json=payload)
        self.assertIn(resp.status_code, (401, 422), resp.text)
        self.assertNotIn("bt_web_session", resp.cookies)



if __name__ == "__main__":
    unittest.main()
