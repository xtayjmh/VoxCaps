import unittest
from unittest.mock import patch

from core.client.shortcut.task import ShortcutTask


class _Counter:
    def __init__(self):
        self.calls = 0

    def stop(self):
        self.calls += 1


class _State:
    def __init__(self):
        self.queue_in = type('Queue', (), {'put': lambda _self, _item: object()})()

    def stop_recording(self):
        pass


class _Island:
    def __init__(self):
        self.cancelled_ids = []
        self.recognizing_ids = []

    def cancelled(self, task_id):
        self.cancelled_ids.append(task_id)

    def recognizing(self, task_id):
        self.recognizing_ids.append(task_id)


class _Status:
    def start(self):
        pass

    def stop(self):
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
        task.app = type('App', (), {'stream': stream, 'island': _Island()})()
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


if __name__ == '__main__':
    unittest.main()
