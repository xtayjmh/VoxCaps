import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OLD_BRAND = re.compile(r'caps[ _-]?writer', re.IGNORECASE)
TEXT_SUFFIXES = {
    '.ipynb', '.json', '.md', '.py', '.spec', '.toml', '.txt', '.yaml', '.yml'
}


def tracked_text_files():
    output = subprocess.check_output(
        ['git', 'ls-files', '-z'],
        cwd=ROOT,
    ).decode('utf-8')
    return [
        ROOT / path
        for path in output.split('\0')
        if (
            path
            and Path(path).suffix.lower() in TEXT_SUFFIXES
            and (ROOT / path).is_file()
        )
    ]


def is_allowed_upstream_reference(relative_path, line):
    normalized = relative_path.as_posix()
    if normalized == 'docs/CHANGELOG.md':
        return True
    if normalized.startswith('docs/specs/'):
        return True
    if 'HaujetZhao/CapsWriter' in line:
        return True
    upstream_credit = '来自 Caps' + 'Writer-Offline 原作者'
    return normalized == 'readme.md' and upstream_credit in line


class BrandResidueTests(unittest.TestCase):
    def test_tracked_product_text_uses_voxcaps_brand(self):
        residues = []
        for path in tracked_text_files():
            relative_path = path.relative_to(ROOT)
            for line_number, line in enumerate(
                path.read_text(encoding='utf-8').splitlines(),
                start=1,
            ):
                if OLD_BRAND.search(line) and not is_allowed_upstream_reference(
                    relative_path,
                    line,
                ):
                    residues.append(f'{relative_path}:{line_number}')

        self.assertEqual(residues, [], f'发现旧品牌残留：{residues}')


if __name__ == '__main__':
    unittest.main()
