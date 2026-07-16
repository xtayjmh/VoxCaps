import unittest

from core.client.island.controller import DynamicIslandController
from core.client.island.state_machine import IslandStage


class DynamicIslandControllerTests(unittest.TestCase):
    def test_success_and_error_hide_instead_of_publishing_visible_stages(self):
        controller = DynamicIslandController(enabled=True)

        controller.preparing('task-1')
        self.assertEqual(controller._events.get_nowait().stage, IslandStage.PREPARING)

        controller.delivered('task-1')
        delivered = controller._events.get_nowait()
        self.assertEqual(delivered.stage, IslandStage.IDLE)
        self.assertEqual(delivered.task_id, 'task-1')

        controller.error('task-1', 'offline')
        error = controller._events.get_nowait()
        self.assertEqual(error.stage, IslandStage.IDLE)
        self.assertEqual(error.task_id, 'task-1')

    def test_unscoped_error_does_not_hide_an_unrelated_active_task(self):
        controller = DynamicIslandController(enabled=True)

        controller.error(None, 'offline')

        self.assertTrue(controller._events.empty())


if __name__ == '__main__':
    unittest.main()
