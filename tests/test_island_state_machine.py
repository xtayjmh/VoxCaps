import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / 'core' / 'client' / 'island' / 'state_machine.py'
SPEC = importlib.util.spec_from_file_location('capswriter_island_state_machine', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

IslandEvent = MODULE.IslandEvent
IslandStage = MODULE.IslandStage
IslandStateMachine = MODULE.IslandStateMachine


class IslandStateMachineTests(unittest.TestCase):
    def test_happy_path(self):
        machine = IslandStateMachine()

        self.assertTrue(machine.apply(IslandEvent(IslandStage.RECORDING, 'task-1')))
        self.assertTrue(machine.apply(IslandEvent(IslandStage.RECOGNIZING, 'task-1')))
        self.assertTrue(machine.apply(IslandEvent(IslandStage.DELIVERED, 'task-1')))
        self.assertEqual(machine.state.stage, IslandStage.DELIVERED)

    def test_stale_result_does_not_override_new_recording(self):
        machine = IslandStateMachine()
        machine.apply(IslandEvent(IslandStage.RECORDING, 'old'))
        machine.apply(IslandEvent(IslandStage.RECORDING, 'new'))

        self.assertFalse(machine.apply(IslandEvent(IslandStage.DELIVERED, 'old')))
        self.assertEqual(machine.state.stage, IslandStage.RECORDING)
        self.assertEqual(machine.state.task_id, 'new')

    def test_cancel_returns_to_idle(self):
        machine = IslandStateMachine()
        machine.apply(IslandEvent(IslandStage.RECORDING, 'task-1'))

        self.assertTrue(machine.apply(IslandEvent(IslandStage.IDLE, 'task-1')))
        self.assertEqual(machine.state.stage, IslandStage.IDLE)
        self.assertIsNone(machine.state.task_id)

    def test_error_without_id_targets_active_task(self):
        machine = IslandStateMachine()
        machine.apply(IslandEvent(IslandStage.RECORDING, 'task-1'))

        self.assertTrue(machine.apply(IslandEvent(IslandStage.ERROR, message='offline')))
        self.assertEqual(machine.state.task_id, 'task-1')
        self.assertEqual(machine.state.message, 'offline')


if __name__ == '__main__':
    unittest.main()
