import asyncio
import unittest

from core.client.output.ordered_delivery import OrderedDeliveryQueue


class OrderedDeliveryQueueTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.queue = OrderedDeliveryQueue(asyncio.get_running_loop())

    async def test_out_of_order_results_are_released_in_registration_order(self):
        first_sequence = self.queue.register('first', 10.0)
        second_sequence = self.queue.register('second', 20.0)

        self.assertLess(first_sequence, second_sequence)
        self.queue.complete('second', 'result-2')
        self.assertTrue(self.queue.ready_empty())

        self.queue.complete('first', 'result-1')

        self.assertEqual(await self.queue.get(), 'result-1')
        self.assertEqual(await self.queue.get(), 'result-2')
        self.assertEqual(self.queue.pending_count, 0)

    async def test_failed_early_session_unblocks_later_ready_result(self):
        self.queue.register('first', 10.0)
        self.queue.register('second', 20.0)
        self.queue.complete('second', 'result-2')

        self.queue.fail('first')

        self.assertEqual(await self.queue.get(), 'result-2')
        self.assertEqual(self.queue.pending_count, 0)

    async def test_cancel_and_clear_release_all_session_data(self):
        self.queue.register('first', 10.0)
        self.queue.register('second', 20.0)
        self.queue.complete('second', 'result-2')

        self.queue.cancel('first')
        self.queue.clear()

        self.assertEqual(self.queue.pending_count, 0)
        self.assertTrue(self.queue.ready_empty())

    async def test_disconnect_skips_submitted_head_and_releases_ready_tail(self):
        self.queue.register('first', 10.0)
        self.queue.register('second', 20.0)
        self.queue.mark_submitted('first', 7)
        self.queue.complete('second', 'result-2')

        self.queue.fail_submitted(7)

        self.assertEqual(await self.queue.get(), 'result-2')
        self.assertEqual(self.queue.pending_count, 0)

    async def test_disconnect_keeps_recording_that_has_not_submitted_final(self):
        self.queue.register('recording', 10.0)

        self.queue.fail_submitted(7)
        self.queue.mark_submitted('recording', 8)
        self.queue.complete('recording', 'result-after-reconnect')

        self.assertEqual(await self.queue.get(), 'result-after-reconnect')
        self.assertEqual(self.queue.pending_count, 0)

    async def test_disconnect_only_fails_matching_connection_generation(self):
        self.queue.register('old', 10.0)
        self.queue.register('new', 20.0)
        self.queue.mark_submitted('old', 7)
        self.queue.mark_submitted('new', 8)

        self.queue.fail_submitted(7)
        self.queue.complete('new', 'new-result')

        self.assertEqual(await self.queue.get(), 'new-result')
        self.assertEqual(self.queue.pending_count, 0)


if __name__ == '__main__':
    unittest.main()
