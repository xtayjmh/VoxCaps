import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.server.worker import diagnostics


class WorkerCrashDiagnosticsTests(unittest.TestCase):
    def test_report_preserves_exception_traceback_and_runtime_sections(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / 'worker_crash_latest.log'
            with (
                patch.object(diagnostics, 'REPORT_PATH', report_path),
                patch.object(
                    diagnostics,
                    '_runtime_diagnostics',
                    return_value=['ggml.dll: exists=True, load=OK'],
                ),
                patch.object(
                    diagnostics,
                    '_onnx_diagnostics',
                    return_value=['version=test', "available_providers=['CPUExecutionProvider']"],
                ),
                patch.object(
                    diagnostics,
                    '_gpu_diagnostics',
                    return_value='Name : Test GPU',
                ),
            ):
                result = diagnostics.write_worker_crash_report(
                    RuntimeError('model startup failed'),
                    'Traceback: expected failure',
                )

            self.assertEqual(Path(result), report_path)
            report = report_path.read_text(encoding='utf-8')
            self.assertIn('RuntimeError: model startup failed', report)
            self.assertIn('Traceback: expected failure', report)
            self.assertIn('ggml.dll: exists=True, load=OK', report)
            self.assertIn("available_providers=['CPUExecutionProvider']", report)
            self.assertIn('Name : Test GPU', report)


if __name__ == '__main__':
    unittest.main()
