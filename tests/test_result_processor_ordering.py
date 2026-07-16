import unittest

from core.client.output.result_processor import ResultProcessor
from core.protocol import RecognitionMessage


class _DeliveryOrder:
    def __init__(self):
        self.completed = []

    def complete(self, task_id, message):
        self.completed.append((task_id, message))


class ResultProcessorOrderingTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_result_is_buffered_before_any_output_processing(self):
        processor = ResultProcessor.__new__(ResultProcessor)
        delivery_order = _DeliveryOrder()
        processor.app = type('App', (), {'delivery_order': delivery_order})()
        message = RecognitionMessage(
            task_id='task-2',
            is_final=True,
            duration=1.0,
            time_start=20.0,
            time_submit=21.0,
            time_complete=22.0,
            text='第二段',
        )

        await processor._handle_message(message)

        self.assertEqual(delivery_order.completed, [('task-2', message)])


if __name__ == '__main__':
    unittest.main()
