import xml.etree.ElementTree as ET
import unittest
from pathlib import Path

from PIL import Image

from core.ui.window_icon import apply_window_icon


ROOT = Path(__file__).resolve().parents[1]
SVG_PATH = ROOT / 'assets' / 'voxcaps-icon.svg'
ICO_PATH = ROOT / 'assets' / 'icon.ico'
REQUIRED_SIZES = {
    (16, 16),
    (24, 24),
    (32, 32),
    (48, 48),
    (64, 64),
    (128, 128),
    (256, 256),
}


class BrandIconAssetTests(unittest.TestCase):
    def test_window_icon_helper_applies_shared_icon(self):
        class Window:
            applied = None

            def iconbitmap(self, *, default):
                self.applied = Path(default)

        window = Window()
        self.assertTrue(apply_window_icon(window, ICO_PATH))
        self.assertEqual(window.applied, ICO_PATH.resolve())

    def test_svg_is_editable_and_has_no_text_or_external_images(self):
        tree = ET.parse(SVG_PATH)
        root = tree.getroot()
        elements = list(root.iter())

        self.assertEqual(root.attrib.get('viewBox'), '0 0 256 256')
        self.assertFalse(any(node.tag.endswith('text') for node in elements))
        self.assertFalse(any(node.tag.endswith('image') for node in elements))
        self.assertTrue(any(node.tag.endswith('linearGradient') for node in elements))

    def test_ico_contains_all_required_windows_sizes(self):
        with Image.open(ICO_PATH) as image:
            self.assertEqual(set(image.info.get('sizes', set())), REQUIRED_SIZES)
            for size in REQUIRED_SIZES:
                layer = image.ico.getimage(size)
                self.assertEqual(layer.size, size)
                self.assertEqual(layer.mode, 'RGBA')

    def test_both_build_specs_embed_the_shared_icon(self):
        for spec_name in ('build.spec', 'build-client.spec'):
            content = (ROOT / spec_name).read_text(encoding='utf-8')
            self.assertIn("ICON_PATH = join('assets', 'icon.ico')", content)
            self.assertIn('icon=ICON_PATH', content)

    def test_build_pipeline_verifies_assets_and_all_three_executables(self):
        build_script = (
            ROOT / 'scripts' / 'build-windows-packages.ps1'
        ).read_text(encoding='utf-8')
        self.assertIn('verify-brand-assets.py', build_script)
        self.assertIn('dist\\VoxCaps\\start_client.exe', build_script)
        self.assertIn('dist\\VoxCaps\\start_server.exe', build_script)
        self.assertIn('dist\\VoxCaps-Client\\start_client.exe', build_script)


if __name__ == '__main__':
    unittest.main()
