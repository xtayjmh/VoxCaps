import unittest

from core.client.audio.recorder import AudioRecorder
from core.client.connection import CommunicationError
from core.protocol import AudioMessage


class _DeliveryOrder:
    def __init__(self, trace):
        self.trace = trace

    def mark_submitted(self, task_id, connection_generation):
        self.trace.append(('submitted', task_id, connection_generation))
        return True

    def fail(self, task_id):
        self.trace.append(('failed', task_id))


class _WebSocketManager:
    is_connected = True
    connection_generation = 9

    def __init__(self, trace):
        self.trace = trace

    async def send(self, message):
        self.trace.append(('sent', message.task_id))
        return True


class _FailingWebSocketManager(_WebSocketManager):
    async def send(self, message):
        self.trace.append(('send-failed', message.task_id))
        raise CommunicationError('connection closed')


class _State:
    def __init__(self, trace):
        self.trace = trace

    def pop_audio_file(self, task_id):
        self.trace.append(('audio-released', task_id))


class _Island:
    def __init__(self, trace):
        self.trace = trace

    def error(self, task_id, message):
        self.trace.append(('island-error', task_id))


class AudioRecorderDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_is_bound_to_connection_generation_before_send(self):
        trace = []
        app = type(
            'App',
            (),
            {
                'state': object(),
                'ws': _WebSocketManager(trace),
                'delivery_order': _DeliveryOrder(trace),
            },
        )()
        recorder = AudioRecorder(app)
        message = AudioMessage(
            task_id='task-1',
            source='mic',
            data='',
            is_final=True,
            time_start=10.0,
        )

        await recorder._send_message(message)

        self.assertEqual(
            trace,
            [('submitted', 'task-1', 9), ('sent', 'task-1')],
        )

    async def test_final_send_failure_releases_ordered_delivery_head(self):
        trace = []
        app = type(
            'App',
            (),
            {
                'state': _State(trace),
                'ws': _FailingWebSocketManager(trace),
                'delivery_order': _DeliveryOrder(trace),
                'island': _Island(trace),
            },
        )()
        recorder = AudioRecorder(app)
        message = AudioMessage(
            task_id='task-1',
            source='mic',
            data='',
            is_final=True,
            time_start=10.0,
        )

        await recorder._send_message(message)

        self.assertIn(('failed', 'task-1'), trace)


if __name__ == '__main__':
    unittest.main()
