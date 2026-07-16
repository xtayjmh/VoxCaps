import unittest
from unittest.mock import patch

from core.client.manager.mic_runner import MicRunner


class _StartCounter:
    def __init__(self):
        self.start_calls = 0

    def start(self):
        self.start_calls += 1


class _StreamThatMustStayIdle:
    def __init__(self):
        self.start_calls = 0

    def start(self):
        self.start_calls += 1
        raise AssertionError('客户端空闲启动时不应打开麦克风')


class _App:
    def __init__(self):
        self.state = object()
        self.tray = _StartCounter()
        self.stream = _StreamThatMustStayIdle()
        self.shortcut = _StartCounter()
        self.udp = _StartCounter()
        self.hotword = _StartCounter()
        self.llm = _StartCounter()


class MicRunnerResourceTests(unittest.TestCase):
    @patch('core.client.manager.mic_runner.TipsDisplay.show_mic_tips')
    def test_starting_client_keeps_microphone_closed_until_shortcut_press(self, _tips):
        app = _App()

        MicRunner(app).start_resources()

        self.assertEqual(app.stream.start_calls, 0)
        self.assertEqual(app.tray.start_calls, 1)
        self.assertEqual(app.shortcut.start_calls, 1)


if __name__ == '__main__':
    unittest.main()
