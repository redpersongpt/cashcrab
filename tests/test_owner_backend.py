import json
import os
import tempfile
import unittest
import importlib
from pathlib import Path
from unittest.mock import patch


class OwnerBackendTests(unittest.TestCase):
    def test_owner_status_payload_reflects_env(self):
        with patch.dict(
            os.environ,
            {
                "CASHCRAB_TWITTER_CLIENT_ID": "abc",
                "CASHCRAB_PEXELS_API_KEY": "pexels-key",
            },
            clear=False,
        ):
            from modules import owner_api

            payload = owner_api.status_payload()
            self.assertTrue(payload["capabilities"]["twitter"]["ready"])
            self.assertTrue(payload["capabilities"]["pexels"]["ready"])

    def test_sync_owner_config_writes_youtube_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.dict(os.environ, {"CASHCRAB_HOME": str(home)}, clear=False):
                from modules import config as config_module
                from modules import backend as backend_module

                config = importlib.reload(config_module)
                backend = importlib.reload(backend_module)

                payload = {
                    "backend": {"enabled": True, "base_url": "http://localhost:8787", "client_token": "x"},
                    "youtube": {"client_secrets_json": {"installed": {"client_id": "abc"}}},
                    "twitter": {"client_id": "tw"},
                    "tiktok": {"client_key": "tt"},
                    "instagram": {"app_id": "ig"},
                    "capabilities": {},
                }

                with patch("modules.backend.bootstrap", return_value=payload):
                    backend.sync_owner_config()

                cfg = json.loads((home / "config.json").read_text())
                self.assertEqual(cfg["twitter"]["client_id"], "tw")
                self.assertTrue((home / "client_secrets.json").exists())


if __name__ == "__main__":
    unittest.main()
