import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseMetadataTests(unittest.TestCase):
    def test_project_lock_and_runtime_versions_are_3_0_2(self):
        pyproject = (ROOT / 'pyproject.toml').read_text(encoding='utf-8')
        lockfile = (ROOT / 'uv.lock').read_text(encoding='utf-8')

        self.assertRegex(pyproject, r'(?m)^version = "3\.0\.2"$')
        root_package = re.search(
            r'(?ms)^\[\[package\]\]\s+name = "voxcaps"\s+version = "([^"]+)"',
            lockfile,
        )
        self.assertIsNotNone(root_package)
        self.assertEqual(root_package.group(1), '3.0.2')
        for config_name in ('config_client.py', 'config_server.py'):
            config = (ROOT / config_name).read_text(encoding='utf-8')
            self.assertRegex(config, r'(?m)^__version__ = [\'\"]3\.0\.2[\'\"]$')

    def test_readme_documents_mixed_chinese_english_accuracy(self):
        readme = (ROOT / 'readme.md').read_text(encoding='utf-8')

        self.assertIn('中文夹英文', readme)
        for model in ('Paraformer', 'SenseVoice-Small', 'Fun-ASR-Nano', 'Qwen3-ASR'):
            self.assertIn(model, readme)
        self.assertIn('经验性分级', readme)


if __name__ == '__main__':
    unittest.main()
