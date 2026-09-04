"""Run in Linux: python deploy/tests/test-notification-health.py (no real Docker calls)."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ReminderHealthTest(unittest.TestCase):
    def test_missing_stale_and_backlogged_reminders_fail_closed(self):
        script = Path(__file__).resolve().parents[1] / "notification-recovery-health.sh"
        with tempfile.TemporaryDirectory(prefix="legaltech-health-") as directory:
            docker = Path(directory) / "docker"
            docker.write_text('''#!/bin/sh
case "$*" in
  *NOTIFICATION_PROCESSING_TIMEOUT_SECONDS*) echo "120 180";;
  *legaltech:routines:recovery-heartbeat*)
    case "$HEALTH_TEST_CASE" in missing) echo "";; stale) echo 1;; *) date +%s;; esac;;
  *routine_reminder_candidates*)
    case "$HEALTH_TEST_CASE" in backlog) echo 1;; *) echo 0;; esac;;
  *recovery-heartbeat*) date +%s;;
  *recovery_candidates*) echo 0;;
  *WEB_PUSH_ENABLED*) echo 1;;
  *) exit 5;;
esac
''', encoding="utf-8")
            docker.chmod(0o700)
            for scenario in ("healthy", "missing", "stale", "backlog"):
                env = dict(os.environ, PATH=directory + os.pathsep + os.environ["PATH"],
                           POSTGRES_USER="unused", POSTGRES_DB="unused", HEALTH_TEST_CASE=scenario)
                result = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, scenario == "healthy", result.stderr)


if __name__ == "__main__":
    unittest.main()
