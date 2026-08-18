import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
IMPORT_SNIPPET = "import ticketbot.miniapp_server"


def _run_import(extra_env):
    """Import the miniapp server in a clean subprocess and return the result.

    Importing in a subprocess keeps the production hardening guard isolated so it
    cannot affect the module state that the rest of the test suite relies on.
    """
    env = {
        # Start from a minimal, deterministic environment.
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        # Neutral defaults so the guard only fires because of the values under test.
        "ENVIRONMENT": "",
        "REQUIRE_SECURE_CONFIG": "0",
        "MINIAPP_ALLOW_TG_ID_FALLBACK": "0",
        "BOT_TOKEN": "",
        "ADMIN_WEB_PASSWORD": "",
        "UPLOAD_LINK_SECRET": "",
        "TICKET_QR_SECRET": "",
        "EMAIL_LOGIN_SECRET": "",
    }
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", IMPORT_SNIPPET],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


class SecureConfigGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._base_env = {
            "DATABASE_PATH": os.path.join(self._tmp.name, "guard_test.db"),
            "UPLOAD_DIR": os.path.join(self._tmp.name, "uploads"),
        }

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_signing_secrets_fail_fast_in_production(self):
        env = dict(self._base_env)
        env["REQUIRE_SECURE_CONFIG"] = "1"
        # No dedicated secrets and no BOT_TOKEN to back them.
        result = _run_import(env)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RuntimeError", result.stderr)
        self.assertIn("signing secrets are missing", result.stderr)

    def test_environment_production_also_enables_guard(self):
        env = dict(self._base_env)
        env["ENVIRONMENT"] = "production"
        result = _run_import(env)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("signing secrets are missing", result.stderr)

    def test_tg_id_fallback_forbidden_in_production(self):
        env = dict(self._base_env)
        env["REQUIRE_SECURE_CONFIG"] = "1"
        # Provide a BOT_TOKEN so secrets are satisfied; the fallback must still be refused.
        env["BOT_TOKEN"] = "prod-bot-token"
        env["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "1"
        result = _run_import(env)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MINIAPP_ALLOW_TG_ID_FALLBACK", result.stderr)

    def test_bot_token_backs_secrets_and_allows_startup(self):
        env = dict(self._base_env)
        env["REQUIRE_SECURE_CONFIG"] = "1"
        env["BOT_TOKEN"] = "prod-bot-token"
        # Fallback disabled, BOT_TOKEN backs the signing secrets -> import must succeed.
        result = _run_import(env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dedicated_secrets_allow_startup(self):
        env = dict(self._base_env)
        env["REQUIRE_SECURE_CONFIG"] = "1"
        env["UPLOAD_LINK_SECRET"] = "u-secret"
        env["TICKET_QR_SECRET"] = "q-secret"
        env["EMAIL_LOGIN_SECRET"] = "e-secret"
        result = _run_import(env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_disabled_by_default_imports_cleanly(self):
        # Mirrors the dev/test configuration: flag off, no secrets, fallback on.
        env = dict(self._base_env)
        env["MINIAPP_ALLOW_TG_ID_FALLBACK"] = "1"
        result = _run_import(env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
