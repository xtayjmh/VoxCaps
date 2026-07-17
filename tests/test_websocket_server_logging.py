import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WebSocketServerLoggingTests(unittest.TestCase):
    def test_invalid_handshake_tracebacks_are_suppressed(self):
        source = (
            ROOT / 'core/server/connection/server_manager.py'
        ).read_text(encoding='utf-8')

        self.assertIn("logging.getLogger('voxcaps.websockets.server')", source)
        self.assertIn('_websocket_protocol_logger.setLevel(logging.CRITICAL)', source)
        self.assertIn('logger=_websocket_protocol_logger', source)


if __name__ == '__main__':
    unittest.main()
