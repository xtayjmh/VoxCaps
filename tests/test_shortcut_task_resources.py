import unittest
from unittest.mock import patch

from core.client.shortcut.task import ShortcutTask


class _Counter:
    def __init__(self):
        self.calls = 0

    def stop(self):
        self.calls += 1


class _DeliveryOrder:
    def __init__(self):
        self.cancelled_ids = []
        self.registered = []

    def cancel(self, task_id):
        self.cancelled_ids.append(task_id)

    def register(self, task_id, start_time):
        self.registered.append((task_id, start_time))
        return len(self.registered)


class _State:
    def __init__(self):
        self.queue_in = type('Queue', (), {'put': lambda _self, _item: object()})()

    def stop_recording(self):
        pass

    def start_recording(self, _start_time):
        pass


class _Island:
    def __init__(self):
        self.cancelled_ids = []
        self.recognizing_ids = []
        self.recording_ids = []

    def cancelled(self, task_id):
        self.cancelled_ids.append(task_id)

    def recognizing(self, task_id):
        self.recognizing_ids.append(task_id)

    def recording(self, task_id):
        self.recording_ids.append(task_id)


class _Status:
    def start(self):
        pass

    def stop(self):
        pass


class _Stream(_Counter):
    def begin_direct_recording(self):
        return True


class _Recorder:
    task_id = None

    async def record_and_send(self):
        pass


class _Shortcut:
    key = 'caps_lock'

    @staticmethod
    def is_toggle_key():
        return False


class ShortcutTaskResourceTests(unittest.TestCase):
    def test_shutdown_cancel_can_leave_stream_release_to_daemon_executor(self):
        task = ShortcutTask.__new__(ShortcutTask)
        stream = _Counter()
        task.shortcut = _Shortcut()
        delivery_order = _DeliveryOrder()
        task.app = type(
            'App',
            (),
            {
                'stream': stream,
                'island': _Island(),
                'delivery_order': delivery_order,
            },
        )()
        task._status = _Status()
        task.pipeline_task_id = 'task-1'
        task.task = None
        task.is_recording = True
        task._owns_direct_stream = True

        # property state 读取 app.state，因此在构造的最小 app 上补齐。
        task.app.state = _State()
        task.cancel(release_stream=False)

        self.assertEqual(stream.calls, 0)
        self.assertFalse(task._owns_direct_stream)
        self.assertFalse(task.is_recording)
        self.assertIsNone(task.pipeline_task_id)
        self.assertEqual(delivery_order.cancelled_ids, ['task-1'])

    @patch('core.client.shortcut.task.asyncio.run_coroutine_threadsafe')
    def test_finish_releases_task_identity_for_next_direct_launch(self, run_async):
        task = ShortcutTask.__new__(ShortcutTask)
        island = _Island()
        task.shortcut = _Shortcut()
        task.app = type(
            'App',
            (),
            {
                'stream': _Counter(),
                'island': island,
                'state': _State(),
                'loop': object(),
                'delivery_order': _DeliveryOrder(),
            },
        )()
        task._status = _Status()
        task.pipeline_task_id = 'old-task'
        task.task = None
        task.is_recording = True
        task._owns_direct_stream = False

        task.finish()

        self.assertEqual(island.recognizing_ids, ['old-task'])
        self.assertIsNone(task.pipeline_task_id)
        run_async.assert_called_once()

    @patch('core.client.shortcut.task.asyncio.run_coroutine_threadsafe')
    def test_direct_launch_registers_order_before_recording(self, run_async):
        run_async.side_effect = lambda coroutine, _loop: coroutine.close()
        task = ShortcutTask.__new__(ShortcutTask)
        delivery_order = _DeliveryOrder()
        island = _Island()
        task.shortcut = _Shortcut()
        task.app = type(
            'App',
            (),
            {
                'stream': _Stream(),
                'island': island,
                'state': _State(),
                'loop': object(),
                'delivery_order': delivery_order,
            },
        )()
        task._status = _Status()
        task._recorder_class = lambda _app: _Recorder()
        task.pipeline_task_id = None
        task.delivery_sequence = None
        task.task = None
        task.is_recording = False
        task._owns_direct_stream = False

        task.launch(start_time=12.5)

        self.assertEqual(len(delivery_order.registered), 1)
        task_id, start_time = delivery_order.registered[0]
        self.assertEqual(start_time, 12.5)
        self.assertEqual(island.recording_ids, [task_id])
        self.assertEqual(task.delivery_sequence, 1)


if __name__ == '__main__':
    unittest.main()
