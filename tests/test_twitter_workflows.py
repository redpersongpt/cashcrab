import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TwitterWorkflowTests(unittest.TestCase):
    def _reload_modules(self, home: str):
        with patch.dict(os.environ, {"CASHCRAB_HOME": home}, clear=False):
            from modules import analytics as analytics_module
            from modules import config as config_module
            from modules import twitter as twitter_module

            config = importlib.reload(config_module)
            analytics = importlib.reload(analytics_module)
            twitter = importlib.reload(twitter_module)
            return config, analytics, twitter

    def test_queue_tweet_persists_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, twitter = self._reload_modules(tmp)

            item = twitter.queue_tweet(
                "CashCrab runs X from one terminal.",
                tweet_type="organic",
                workflow="manual",
                topic="automation",
            )

            self.assertEqual(item["status"], "queued")
            self.assertEqual(item["workflow"], "manual")
            self.assertEqual(item["topic"], "automation")
            self.assertEqual(len(twitter.list_queue()), 1)

            queue_path = Path(tmp) / "twitter_queue.json"
            self.assertTrue(queue_path.exists())
            payload = json.loads(queue_path.read_text())
            self.assertEqual(payload["items"][0]["text"], "CashCrab runs X from one terminal.")

    def test_post_queued_marks_items_posted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, twitter = self._reload_modules(tmp)

            first = twitter.queue_tweet("First queued post")
            second = twitter.queue_tweet("Second queued post")
            posted = []

            def fake_post(text: str, tweet_type: str = "organic") -> str:
                posted.append((text, tweet_type))
                return f"id-{len(posted)}"

            with patch.object(twitter, "post_tweet", side_effect=fake_post):
                result = twitter.post_queued(limit=1)

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["queue_id"], first["id"])
            self.assertEqual(posted, [("First queued post", "organic")])

            remaining = twitter.list_queue()
            self.assertEqual(len(remaining), 1)
            self.assertEqual(remaining[0]["id"], second["id"])

            all_items = twitter.list_queue(status=None)
            first_item = next(item for item in all_items if item["id"] == first["id"])
            self.assertEqual(first_item["status"], "posted")
            self.assertEqual(first_item["tweet_id"], "id-1")

    def test_build_workflow_queue_generates_multiple_posts(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, twitter = self._reload_modules(tmp)

            drafted = []

            def fake_generate(prompt: str, system: str = "") -> str:
                drafted.append((prompt, system))
                return f"Draft {len(drafted)}"

            with patch.object(twitter.llm, "generate", side_effect=fake_generate):
                items = twitter.build_workflow_queue(
                    preset="launch",
                    topic="Qwen agent mode",
                    count=3,
                    spacing_minutes=30,
                )

            self.assertEqual(len(items), 3)
            self.assertTrue(all(item["workflow"] == "launch" for item in items))
            self.assertTrue(all(item["status"] == "queued" for item in items))
            self.assertEqual([item["text"] for item in items], ["Draft 1", "Draft 2", "Draft 3"])
            self.assertEqual(len(twitter.list_queue()), 3)
            self.assertEqual(len(drafted), 3)

    def test_export_queue_writes_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, twitter = self._reload_modules(tmp)

            twitter.queue_tweet("Queue item one", workflow="authority")
            output = twitter.export_queue(Path(tmp) / "x-queue.md")

            self.assertTrue(Path(output).exists())
            content = Path(output).read_text()
            self.assertIn("# CashCrab X Queue", content)
            self.assertIn("Queue item one", content)
            self.assertIn("authority", content)


if __name__ == "__main__":
    unittest.main()
