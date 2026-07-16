"""动态状态岛尺寸和任务栏避让的回归测试。"""

import importlib.util
import sys
import types
import unittest
from pathlib import Path


ISLAND_DIR = Path(__file__).parents[1] / 'core' / 'client' / 'island'
PACKAGE_NAME = 'capswriter_test_island'
package = types.ModuleType(PACKAGE_NAME)
package.__path__ = [str(ISLAND_DIR)]
sys.modules.setdefault(PACKAGE_NAME, package)

for module_name in ('state_machine', 'view'):
    spec = importlib.util.spec_from_file_location(
        f'{PACKAGE_NAME}.{module_name}',
        ISLAND_DIR / f'{module_name}.py',
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

DynamicIslandView = sys.modules[f'{PACKAGE_NAME}.view'].DynamicIslandView


class DynamicIslandGeometryTests(unittest.TestCase):
    def test_default_size_stays_above_bottom_taskbar(self):
        work_area = (0, 0, 1920, 1040)

        x, y = DynamicIslandView._calculate_position(work_area, 276, 68, 18)

        self.assertEqual((x, y), (822, 954))
        self.assertEqual(y + 68 + 18, work_area[3])

    def test_position_respects_left_and_top_work_area(self):
        work_area = (100, 50, 1700, 950)

        x, y = DynamicIslandView._calculate_position(work_area, 276, 68, 18)

        self.assertGreaterEqual(x, work_area[0])
        self.assertGreaterEqual(y, work_area[1])
        self.assertLessEqual(y + 68, work_area[3] - 18)


if __name__ == '__main__':
    unittest.main()
