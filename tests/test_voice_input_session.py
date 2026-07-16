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
        self.begin_results = [True]
        self.capture_active = False

    @property
    def is_capture_active(self):
        return self.capture_active

    def begin_candidate(self):
        self.begin_calls += 1
        opened = self.begin_results.pop(0) if self.begin_results else True
        self.is_open = opened
        return opened

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


class _BlockingFirstOpenStream(_FakeStream):
    def __init__(self):
        super().__init__()
        self.first_open_started = threading.Event()
        self.allow_first_open = threading.Event()

    def begin_candidate(self):
        if self.begin_calls == 0:
            self.first_open_started.set()
            self.allow_first_open.wait(timeout=1)
        return super().begin_candidate()


class VoiceInputSessionCoordinatorTests(unittest.TestCase):
    def test_preheat_runs_after_delay_and_releases_microphone_on_success(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        notifications = []
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
            notify_microphone_error=lambda message: notifications.append(message),
        )

        scheduled = coordinator.schedule_preheat(delay=1.0, timeout=1.5)

        self.assertTrue(scheduled)
        self.assertEqual(stream.begin_calls, 0)
        self.assertEqual(scheduler.calls[0].delay, 1.0)

        scheduler.run_next()
        self.assertEqual(stream.begin_calls, 0)
        executor.run_next()

        self.assertEqual(stream.begin_calls, 1)
        self.assertEqual(stream.discard_calls, 1)
        self.assertFalse(stream.is_open)
        self.assertEqual(notifications, [])
        self.assertTrue(scheduler.calls[0].cancelled)

    def test_preheat_failure_notifies_generically_and_keeps_client_retryable(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        stream.begin_results = [False, True]
        notifications = []
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
            notify_microphone_error=lambda message: notifications.append(message),
        )

        coordinator.schedule_preheat(delay=1.0, timeout=1.5)
        scheduler.run_next()
        executor.run_next()

        self.assertEqual(len(notifications), 1)
        self.assertIn('麦克风权限', notifications[0])
        self.assertIn('安全软件设置', notifications[0])
        self.assertNotIn('火绒', notifications[0])
        self.assertNotIn('Defender', notifications[0])
        self.assertTrue(coordinator.press('caps_lock', _FakeTask()))
        executor.run_next()
        self.assertTrue(stream.is_open)

    def test_preheat_skips_notification_when_microphone_is_busy_recording(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        stream.capture_active = True
        stream.begin_results = [False]
        notifications = []
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
            notify_microphone_error=lambda message: notifications.append(message),
        )

        coordinator.schedule_preheat(delay=1.0, timeout=1.5)
        scheduler.run_next()
        executor.run_next()

        self.assertEqual(notifications, [])

    def test_real_press_waits_for_running_preheat_cleanup_before_opening(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _BlockingFirstOpenStream()
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
        )
        coordinator.schedule_preheat(delay=1.0, timeout=1.5)
        scheduler.run_next()

        preheat_thread = threading.Thread(target=executor.run_next)
        preheat_thread.start()
        self.assertTrue(stream.first_open_started.wait(timeout=1))

        self.assertTrue(coordinator.press('caps_lock', _FakeTask()))
        stream.allow_first_open.set()
        preheat_thread.join(timeout=1)

        self.assertFalse(stream.is_open)
        executor.run_next()
        self.assertTrue(stream.is_open)

    def test_preheat_timeout_notifies_once_and_closes_late_open(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        notifications = []
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
            notify_microphone_error=lambda message: notifications.append(message),
        )

        coordinator.schedule_preheat(delay=1.0, timeout=1.5)
        scheduler.run_next()
        self.assertEqual(scheduler.calls[0].delay, 1.5)

        scheduler.run_next()

        self.assertEqual(len(notifications), 1)
        self.assertFalse(stream.is_open)

        executor.run_next()

        self.assertFalse(stream.is_open)
        self.assertEqual(len(notifications), 1)
        self.assertTrue(coordinator.press('caps_lock', _FakeTask()))

    def test_shutdown_before_preheat_delay_prevents_microphone_open(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        notifications = []
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
            notify_microphone_error=lambda message: notifications.append(message),
        )

        coordinator.schedule_preheat(delay=1.0, timeout=1.5)
        coordinator.shutdown()
        scheduler.run_next()
        executor.run_next()

        self.assertEqual(stream.begin_calls, 0)
        self.assertEqual(executor.calls, [])
        self.assertEqual(notifications, [])

    def test_shutdown_cancels_preheat_already_queued_on_executor(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
        )

        coordinator.schedule_preheat(delay=1.0, timeout=1.5)
        scheduler.run_next()
        coordinator.shutdown()
        executor.run_next()

        self.assertEqual(stream.begin_calls, 0)

    def test_shutdown_cancels_candidate_open_already_queued_on_executor(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
        )

        coordinator.press('caps_lock', _FakeTask())
        coordinator.shutdown()
        executor.run_next()

        self.assertEqual(stream.begin_calls, 0)

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
        self.assertEqual(len(scheduler.calls), 2)
        self.assertEqual(scheduler.calls[0].delay, 0.25)
        self.assertEqual(scheduler.calls[1].delay, 1.5)

        executor.run_next()

        self.assertEqual(stream.begin_calls, 1)

    def test_confirmed_hold_open_failure_notifies_and_allows_retry(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        stream.begin_results = [False, True]
        task = _FakeTask()
        notifications = []
        restored = []
        now = [60.0]
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda key, _task: restored.append(key),
            notify_microphone_error=lambda message: notifications.append(message),
            clock=lambda: now[0],
        )

        coordinator.press('caps_lock', task)
        executor.run_next()
        now[0] = 60.251
        scheduler.run_next()

        self.assertEqual(len(notifications), 1)
        self.assertEqual(restored, [])
        self.assertEqual(task.launches, [])
        self.assertTrue(coordinator.press('caps_lock', _FakeTask()))
        executor.run_next()
        self.assertTrue(stream.is_open)

    def test_short_press_open_failure_restores_key_without_permission_notice(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        stream.begin_results = [False]
        notifications = []
        restored = []
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda key, _task: restored.append(key),
            notify_microphone_error=lambda message: notifications.append(message),
        )

        coordinator.press('caps_lock', _FakeTask())
        executor.run_next()
        coordinator.release('caps_lock')

        self.assertEqual(restored, ['caps_lock'])
        self.assertEqual(notifications, [])

    def test_confirmed_hold_timeout_closes_late_open_and_allows_retry(self):
        executor = _ManualExecutor()
        scheduler = _ManualScheduler()
        stream = _FakeStream()
        task = _FakeTask()
        notifications = []
        restored = []
        now = [70.0]
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda key, _task: restored.append(key),
            notify_microphone_error=lambda message: notifications.append(message),
            clock=lambda: now[0],
        )

        coordinator.press('caps_lock', task)
        now[0] = 70.251
        scheduler.run_next()
        scheduler.run_next()

        self.assertEqual(len(notifications), 1)
        self.assertEqual(restored, [])
        self.assertFalse(stream.is_open)

        executor.run_next()

        self.assertFalse(stream.is_open)
        self.assertEqual(len(notifications), 1)
        self.assertTrue(coordinator.press('caps_lock', _FakeTask()))

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
        executor.run_next()

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
        executor.run_next()

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
        self.assertEqual(stream.begin_calls, 0)

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
        executor.run_next()

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
        executor.run_next()

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
        stream = _FakeStream()
        coordinator = VoiceInputSessionCoordinator(
            stream=stream,
            executor=executor,
            scheduler=scheduler,
            restore_short_press=lambda _key, _task: None,
        )
        coordinator.press('caps_lock', _FakeTask())
        executor.run_next()

        coordinator.release('caps_lock')
        self.assertTrue(coordinator.press('caps_lock', _FakeTask()))

        executor.run_next()
        self.assertFalse(stream.is_open)
        executor.run_next()
        self.assertTrue(stream.is_open)


if __name__ == '__main__':
    unittest.main()
