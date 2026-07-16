import threading
import time
import unittest

from core.client.audio.executor import DaemonSerialExecutor


class DaemonSerialExecutorTests(unittest.TestCase):
    def test_running_native_call_does_not_make_non_waiting_shutdown_block(self):
        executor = DaemonSerialExecutor()
        started = threading.Event()
        release = threading.Event()

        def blocked_native_call():
            started.set()
            release.wait(2)

        executor.submit(blocked_native_call)
        self.assertTrue(started.wait(1))
        self.assertTrue(executor.worker_is_daemon)

        shutdown_started = time.monotonic()
        executor.shutdown(wait=False, cancel_futures=False)
        self.assertLess(time.monotonic() - shutdown_started, 0.2)

        release.set()

    def test_cancelled_pending_call_is_skipped_in_submission_order(self):
        executor = DaemonSerialExecutor()
        first_started = threading.Event()
        release_first = threading.Event()
        calls = []

        def first():
            first_started.set()
            release_first.wait(2)
            calls.append('first')

        executor.submit(first)
        self.assertTrue(first_started.wait(1))
        cancelled = executor.submit(lambda: calls.append('cancelled'))
        final = executor.submit(lambda: calls.append('final'))
        self.assertTrue(cancelled.cancel())
        release_first.set()
        final.result(timeout=1)
        executor.shutdown(wait=True)

        self.assertEqual(calls, ['first', 'final'])


if __name__ == '__main__':
    unittest.main()
