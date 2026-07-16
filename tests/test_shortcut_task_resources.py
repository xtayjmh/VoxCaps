import unittest

from core.client.shortcut.task import ShortcutTask


class _Counter:
    def __init__(self):
        self.calls = 0

    def stop(self):
        self.calls += 1


class _State:
    def stop_recording(self):
        pass


class _Island:
    def cancelled(self, _task_id):
        pass


class _Status:
    def stop(self):
        pass


class ShortcutTaskResourceTests(unittest.TestCase):
    def test_shutdown_cancel_can_leave_stream_release_to_daemon_executor(self):
        task = ShortcutTask.__new__(ShortcutTask)
        stream = _Counter()
        task.shortcut = type('Shortcut', (), {'key': 'caps_lock'})()
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


if __name__ == '__main__':
    unittest.main()
