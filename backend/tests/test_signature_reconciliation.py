import unittest
from unittest.mock import call, patch

from app.services import autentique_tasks


class SignatureReconciliationTests(unittest.TestCase):
    def test_existing_reconciler_publishes_autentique_and_clicksign_candidates(self):
        results = iter(
            [
                [("aut-event", "tenant-a")],
                [("click-event", "tenant-b"), ("sandbox-event", "tenant-c")],
            ]
        )

        def complete(coroutine):
            coroutine.close()
            return next(results)

        with patch.object(autentique_tasks.asyncio, "run", side_effect=complete), patch.object(
            autentique_tasks.process_autentique_signature_event, "delay"
        ) as publish_autentique, patch.object(
            autentique_tasks.process_clicksign_signature_event, "delay"
        ) as publish_clicksign:
            result = autentique_tasks.reconcile_autentique_signed_artifacts.run()

        publish_autentique.assert_called_once_with("aut-event", "tenant-a")
        self.assertEqual(
            publish_clicksign.call_args_list,
            [call("click-event", "tenant-b"), call("sandbox-event", "tenant-c")],
        )
        self.assertEqual(result["candidates"], 3)
        self.assertEqual(result["published"], 3)
        self.assertEqual(result["autentique_candidates"], 1)
        self.assertEqual(result["clicksign_candidates"], 2)


if __name__ == "__main__":
    unittest.main()
