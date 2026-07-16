import unittest

from config_client import ClientConfig
from core.client.shortcut.shortcut_config import Shortcut
from core.client.shortcut.shortcut_manager import ShortcutManager


class KeyboardShortcutConfigTests(unittest.TestCase):
    def test_default_keyboard_voice_trigger_is_caps_lock_only(self):
        enabled_keyboard_keys = [
            shortcut['key']
            for shortcut in ClientConfig.shortcuts
            if shortcut.get('enabled', True)
            and shortcut['type'] == 'keyboard'
            and shortcut['hold_mode']
        ]

        self.assertEqual(enabled_keyboard_keys, ['caps_lock'])

    def test_non_caps_keyboard_voice_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '仅支持 CapsLock'):
            ShortcutManager._validate_keyboard_shortcuts([
                Shortcut(key='alt_gr', type='keyboard', enabled=True),
            ])

        ShortcutManager._validate_keyboard_shortcuts([
            Shortcut(key='caps_lock', type='keyboard', enabled=True),
            Shortcut(key='x2', type='mouse', enabled=True),
        ])


if __name__ == '__main__':
    unittest.main()
