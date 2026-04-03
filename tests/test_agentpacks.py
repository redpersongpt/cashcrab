from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from modules import agentpacks


class AgentPackTests(unittest.TestCase):
    def test_skill_count(self):
        self.assertEqual(len(agentpacks.SKILLS), 120)

    def test_agent_count(self):
        self.assertGreaterEqual(len(agentpacks.AGENTS), 8)

    def test_sync_workspace_writes_expected_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = agentpacks.sync_workspace(root)

            self.assertEqual(result["skills"], 120)
            self.assertTrue((root / ".codex" / "config.toml").exists())
            self.assertTrue((root / ".codex" / "agents" / "explorer.toml").exists())
            self.assertTrue((root / ".agents" / "skills" / "cashcrab-youtube-title-lab" / "SKILL.md").exists())
            self.assertTrue(
                (root / ".agents" / "skills" / "cashcrab-youtube-title-lab" / "agents" / "openai.yaml").exists()
            )


if __name__ == "__main__":
    unittest.main()
