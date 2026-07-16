import unittest

from core.client.shortcut.event_handler import ShortcutEventHandler


class _Shortcut:
    hold_mode = True


class _Task:
    shortcut = _Shortcut()

    def launch(self):
        raise AssertionError('长按事件不应直接启动录音任务')


class _Coordinator:
    def __init__(self):
        self.events = []

    def press(self, key_name, task):
        self.events.append(('press', key_name, task))

    def release(self, key_name):
        self.events.append(('release', key_name))


class ShortcutEventHandlerTests(unittest.TestCase):
    def test_hold_key_events_are_delegated_to_voice_session_coordinator(self):
        coordinator = _Coordinator()
        handler = ShortcutEventHandler(
            tasks={},
            pool=None,
            emulator=None,
            voice_sessions=coordinator,
        )
        task = _Task()

        handler.handle_keydown('caps_lock', task)
        handler.handle_keyup('caps_lock', task)

        self.assertEqual(
            coordinator.events,
            [('press', 'caps_lock', task), ('release', 'caps_lock')],
        )


if __name__ == '__main__':
    unittest.main()
