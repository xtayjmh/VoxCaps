import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / 'core' / 'client' / 'island' / 'state_machine.py'
SPEC = importlib.util.spec_from_file_location('voxcaps_island_state_machine', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

IslandEvent = MODULE.IslandEvent
IslandStage = MODULE.IslandStage
IslandStateMachine = MODULE.IslandStateMachine


class IslandStateMachineTests(unittest.TestCase):
    def test_happy_path(self):
        machine = IslandStateMachine()

        self.assertTrue(machine.apply(IslandEvent(IslandStage.PREPARING, 'task-1')))
        self.assertTrue(machine.apply(IslandEvent(IslandStage.RECORDING, 'task-1')))
        self.assertTrue(machine.apply(IslandEvent(IslandStage.RECOGNIZING, 'task-1')))
        self.assertTrue(machine.apply(IslandEvent(IslandStage.IDLE, 'task-1')))
        self.assertEqual(machine.state.stage, IslandStage.IDLE)

    def test_stale_result_does_not_override_new_recording(self):
        machine = IslandStateMachine()
        machine.apply(IslandEvent(IslandStage.RECORDING, 'old'))
        machine.apply(IslandEvent(IslandStage.RECORDING, 'new'))

        self.assertFalse(machine.apply(IslandEvent(IslandStage.RECOGNIZING, 'old')))
        self.assertEqual(machine.state.stage, IslandStage.RECORDING)
        self.assertEqual(machine.state.task_id, 'new')

    def test_old_success_hide_cannot_override_new_preparing(self):
        machine = IslandStateMachine()
        machine.apply(IslandEvent(IslandStage.RECOGNIZING, 'old'))
        machine.apply(IslandEvent(IslandStage.PREPARING, 'new'))

        self.assertFalse(machine.apply(IslandEvent(IslandStage.IDLE, 'old')))
        self.assertEqual(machine.state.stage, IslandStage.PREPARING)
        self.assertEqual(machine.state.task_id, 'new')

    def test_stale_preparing_event_cannot_override_newer_recording(self):
        machine = IslandStateMachine()
        machine.apply(IslandEvent(IslandStage.RECORDING, 'new', created_at=20.0))

        self.assertFalse(
            machine.apply(IslandEvent(IslandStage.PREPARING, 'old', created_at=10.0))
        )
        self.assertEqual(machine.state.stage, IslandStage.RECORDING)
        self.assertEqual(machine.state.task_id, 'new')

    def test_cancel_returns_to_idle(self):
        machine = IslandStateMachine()
        machine.apply(IslandEvent(IslandStage.RECORDING, 'task-1'))

        self.assertTrue(machine.apply(IslandEvent(IslandStage.IDLE, 'task-1')))
        self.assertEqual(machine.state.stage, IslandStage.IDLE)
        self.assertIsNone(machine.state.task_id)

        self.assertFalse(
            machine.apply(IslandEvent(IslandStage.RECOGNIZING, 'task-1'))
        )
        self.assertEqual(machine.state.stage, IslandStage.IDLE)

    def test_superseded_task_cannot_reappear_after_new_task_hides(self):
        machine = IslandStateMachine()
        machine.apply(IslandEvent(IslandStage.RECOGNIZING, 'old'))
        machine.apply(IslandEvent(IslandStage.PREPARING, 'new'))
        machine.apply(IslandEvent(IslandStage.IDLE, 'new'))

        self.assertFalse(machine.apply(IslandEvent(IslandStage.RECOGNIZING, 'old')))
        self.assertEqual(machine.state.stage, IslandStage.IDLE)

if __name__ == '__main__':
    unittest.main()
