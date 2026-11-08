import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('run_demo', Path(__file__).resolve().parents[1] / 'docker/run_demo.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class ReportTests(unittest.TestCase):
    def test_success_summary_and_latest_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'example-run'
            run.mkdir()
            (run / 'console.log').write_text('Progress...\n{"transactions": 123, "failed_transactions": 0, "response_time": 0.0}\nLOG FILE: example\n')
            runner.write_report(run, 'COMPLETED')
            report = (run / 'output.txt').read_text()
            self.assertIn('NO FAILED TRANSACTIONS REPORTED', report)
            self.assertIn('Transactions: 123', report)
            self.assertIn('does not mean zero latency', report)
            self.assertEqual(report, (Path(directory) / 'output.txt').read_text())

    def test_failed_run_replaces_previous_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'output.txt').write_text('Previous successful run')
            run = root / 'failed-run'
            run.mkdir()
            runner.write_report(run, 'FAILED', 'CONCURRENCY must be positive')
            report = (root / 'output.txt').read_text()
            self.assertIn('Status: FAILED', report)
            self.assertIn('No Siege summary available', report)
            self.assertIn('CONCURRENCY must be positive', report)
            self.assertNotIn('Previous successful run', report)

    def test_missing_summary_and_failed_transactions(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / 'run'
            run.mkdir()
            runner.write_report(run, 'COMPLETED')
            self.assertIn('RESULTS UNAVAILABLE', (run / 'output.txt').read_text())
            (run / 'console.log').write_text('{"transactions": 12, "failed_transactions": 3}')
            runner.write_report(run, 'COMPLETED')
            self.assertIn('COMPLETED WITH FAILED TRANSACTIONS', (run / 'output.txt').read_text())
