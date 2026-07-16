import threading
import unittest

from core.client.audio.session import VoiceInputSessionCoordinator


class _PendingCall:
    def __init__(self, callback):
        self.callback = callback
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _ManualExecutor:
    def __init__(self):
        self.calls = []

    def submit(self, callback, *args):
        call = _PendingCall(lambda: callback(*args))
        self.calls.append(call)
        return call

    def run_next(self):
        call = self.calls.pop(0)
        if not call.cancelled:
            call.callback()


class _ManualScheduler:
    def __init__(self):
        self.calls = []

    def call_later(self, delay, callback):
        call = _PendingCall(callback)
        call.delay = delay
        self.calls.append(call)
        return call

    def run_next(self):
        call = self.calls.pop(0)
        if not call.cancelled:
            call.callback()


class _FakeStream:
    def __init__(self):
        self.begin_calls = 0
        self.discard_calls = 0
        self.stop_calls = 0
        self.candidate_frames = [('early', 100.05)]
        self.is_open = False
        self.commit_result = True

    def begin_candidate(self):
        self.begin_calls += 1
        self.is_open = True
        return True

    def discard_candidate(self):
        self.discard_calls += 1
        self.is_open = False

    def commit_candidate(self, start_recording):
        if not self.commit_result:
            return False
        start_recording(list(self.candidate_frames))
        return True

    def stop(self):
        self.stop_calls += 1
        self.is_open = False


class _FakeTask:
    threshold = 0.25

    def __init__(self):
        self.launches = []
        self.finish_calls = 0
        self.cancel_calls = 0

    def launch(self, *, start_time=None, initial_audio=None):
        self.launches.append((start_time, initial_audio))

    def finish(self):
        self.finish_calls += 1

    def cancel(self):
        self.cancel_calls += 1


class _BlockingDiscardStream(_FakeStream):
    def __init__(self):
        super().__init__()
        self.discard_started = threading.Event()
        self.allow_discard = threading.Event()

    def discard_candidate(self):
        self.discard_started.set()
        self.allow_discard.wait(timeout=1)
        super().discard_candidate()


class VoiceInputSessionCoordinatorTests(unittest.TestCase):
    def test_press_schedules_microphone_open_without_blocking_key_event(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
        )

        accepted = coordinator.press('caps_lock', _FakeTask())

        self.assertTrue(accepted)
        self.assertEqual(stream.begin_calls, 0)
        self.assertEqual(len(executor.calls), 1)
        self.assertEqual(len(scheduler.calls), 1)
        self.assertEqual(scheduler.calls[0].delay, 0.25)

        executor.run_next()

        self.assertEqual(stream.begin_calls, 1)

    def test_short_press_discards_candidate_and_restores_default_key(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        restored = []
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda key, _task: restored.append(key),
        )

        coordinator.press('caps_lock', _FakeTask())
        executor.run_next()
        released = coordinator.release('caps_lock')

        self.assertTrue(released)
        self.assertEqual(stream.discard_calls, 1)
        self.assertEqual(restored, ['caps_lock'])
        self.assertTrue(scheduler.calls[0].cancelled)
        self.assertTrue(coordinator.press('caps_lock', _FakeTask()))

    def test_long_press_commits_candidate_then_finishes_and_closes_stream(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        task = _FakeTask()
        restored = []
        now = [100.0]
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda key, _task: restored.append(key),
            clock=lambda: now[0],
        )

        coordinator.press('caps_lock', task)
        executor.run_next()
        now[0] = 100.251
        scheduler.run_next()

        self.assertEqual(task.launches, [(100.0, stream.candidate_frames)])

        coordinator.release('caps_lock')

        self.assertEqual(task.finish_calls, 1)
        self.assertEqual(stream.stop_calls, 1)
        self.assertEqual(stream.discard_calls, 0)
        self.assertEqual(restored, [])

    def test_microphone_that_opens_after_short_release_is_closed_immediately(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        restored = []
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda key, _task: restored.append(key),
        )

        coordinator.press('caps_lock', _FakeTask())
        coordinator.release('caps_lock')

        self.assertFalse(stream.is_open)
        self.assertEqual(restored, ['caps_lock'])

        executor.run_next()

        self.assertFalse(stream.is_open)
        self.assertGreaterEqual(stream.discard_calls, 1)

    def test_shutdown_cancels_active_recording_and_releases_microphone(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        task = _FakeTask()
        now = [30.0]
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
            clock=lambda: now[0],
        )

        coordinator.press('caps_lock', task)
        executor.run_next()
        now[0] = 30.251
        scheduler.run_next()
        coordinator.shutdown()

        self.assertEqual(task.cancel_calls, 1)
        self.assertEqual(stream.stop_calls, 1)
        self.assertFalse(stream.is_open)
        self.assertFalse(coordinator.press('caps_lock', _FakeTask()))

    def test_failed_candidate_commit_does_not_create_empty_recording(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        stream.commit_result = False
        task = _FakeTask()
        now = [40.0]
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
            clock=lambda: now[0],
        )

        coordinator.press('caps_lock', task)
        executor.run_next()
        now[0] = 40.251
        scheduler.run_next()
        coordinator.release('caps_lock')

        self.assertEqual(task.launches, [])
        self.assertEqual(task.finish_calls, 0)
        self.assertGreaterEqual(stream.discard_calls, 1)

    def test_exactly_250_milliseconds_is_still_a_short_press(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        task = _FakeTask()
        restored = []
        now = [50.0]
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda key, _task: restored.append(key),
            clock=lambda: now[0],
        )

        coordinator.press('caps_lock', task)
        executor.run_next()
        now[0] = 50.250
        coordinator.release('caps_lock')

        self.assertEqual(task.launches, [])
        self.assertEqual(task.finish_calls, 0)
        self.assertEqual(restored, ['caps_lock'])

    def test_release_uses_actual_hold_duration_when_timer_callback_is_late(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        task = _FakeTask()
        restored = []
        now = [20.0]
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda key, _task: restored.append(key),
            clock=lambda: now[0],
        )

        coordinator.press('caps_lock', task)
        executor.run_next()
        now[0] = 20.30
        coordinator.release('caps_lock')

        self.assertEqual(len(task.launches), 1)
        self.assertEqual(task.finish_calls, 1)
        self.assertEqual(restored, [])
        self.assertTrue(scheduler.calls[0].cancelled)

    def test_rapid_next_press_waits_until_previous_microphone_is_closed(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _BlockingDiscardStream()
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
        )
        coordinator.press('caps_lock', _FakeTask())
        executor.run_next()

        release_thread = threading.Thread(target=lambda: coordinator.release('caps_lock'))
        release_thread.start()
        self.assertTrue(stream.discard_started.wait(timeout=1))

        press_result = []
        press_finished = threading.Event()

        def press_again():
            press_result.append(coordinator.press('caps_lock', _FakeTask()))
            press_finished.set()

        press_thread = threading.Thread(target=press_again)
        press_thread.start()
        self.assertFalse(press_finished.wait(timeout=0.05))

        stream.allow_discard.set()
        release_thread.join(timeout=1)
        press_thread.join(timeout=1)

        self.assertEqual(press_result, [True])
        executor.run_next()
        self.assertTrue(stream.is_open)


if __name__ == '__main__':
    unittest.main()
