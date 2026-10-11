"""Offline unit tests for the agent's guardrails and grounded summary.

Run from the project root:
    python -m unittest discover -s tests -v

These tests do not call the Gemini API or mutate the company database.
"""
import os
import unittest

# Allow importing agent_loop without a real API key. These tests never call Gemini.
os.environ.setdefault("GEMINI_API_KEY", "unit-test-placeholder")

from agent.agent_loop import unsupported_claim, build_grounded_summary


class UnsupportedClaimTests(unittest.TestCase):
    def test_blocks_percentage_refund_claim(self):
        message = "I have processed a 10% refund of 450 to your original payment method."
        self.assertIsNotNone(unsupported_claim(message))

    def test_blocks_logistics_escalation_claim(self):
        message = "Your order has been escalated to our logistics team."
        self.assertIsNotNone(unsupported_claim(message))

    def test_blocks_future_update_promise(self):
        message = "You will receive a status update within 24 hours."
        self.assertIsNotNone(unsupported_claim(message))

    def test_allows_truthful_limitation(self):
        message = (
            "Your order is recorded as delayed. I cannot process a refund "
            "or contact the logistics team from this system."
        )
        self.assertIsNone(unsupported_claim(message))


class GroundedSummaryTests(unittest.TestCase):
    def test_rejected_refund_and_delayed_order_are_not_success(self):
        ledger = [
            {
                "tool": "get_order",
                "result": {
                    "found": True, "order_id": "O1002",
                    "status": "Delayed", "amount": 4500.0,
                },
            },
            {
                "tool": "get_ticket",
                "result": {
                    "found": True, "ticket_id": "T1002", "status": "Open",
                },
            },
            {
                "tool": "request_human_approval",
                "result": {
                    "approved": False,
                    "message": "Human rejected the proposed action.",
                    "amount_inr": 450,
                },
            },
            {
                "tool": "get_refund",
                "result": {"found": False, "ticket_id": "T1002"},
            },
            {
                "tool": "update_ticket",
                "result": {
                    "success": True, "verified": True, "ticket_id": "T1002",
                    "status": "Open",
                    "response": "The order is delayed; no refund has been processed.",
                },
            },
        ]

        result = build_grounded_summary("Check Priya's delayed order", ledger)
        self.assertFalse(result["success"])
        self.assertIn("rejected", result["final_response"].lower())
        self.assertIn("delayed", result["final_response"].lower())
        self.assertEqual(len(result["verified_actions"]["ticket_updates"]), 1)


    def test_pending_approval_request_counts_as_task_execution_success(self):
        ledger = [
            {"tool": "get_ticket", "result": {"found": True, "ticket_id": "T1004", "status": "Open"}},
            {"tool": "get_order", "result": {"found": True, "order_id": "O1004", "status": "Delivered", "amount": 3200}},
            {"tool": "get_refund", "result": {"found": True, "refund_id": "R001", "ticket_id": "T1004", "status": "Pending Approval"}},
            {"tool": "request_human_approval", "result": {"approved": False, "status": "pending", "approval_id": "approval-test-1", "amount_inr": 3200}},
            {"tool": "update_ticket", "result": {"success": True, "verified": True, "ticket_id": "T1004", "status": "Open", "response": "Refund status is Pending Approval."}},
        ]
        task = "Check the refund status and create a human approval request if required. Do not process the refund."
        result = build_grounded_summary(task, ledger)
        self.assertTrue(result["success"])
        self.assertIn("awaiting a decision", result["final_response"])
        self.assertIn("no financial action was executed", result["final_response"])

    def test_refund_processing_request_never_reports_success_without_integration(self):
        ledger = [
            {"tool": "get_refund", "result": {"found": True, "refund_id": "R001", "ticket_id": "T1004", "status": "Pending Approval"}},
            {"tool": "request_human_approval", "result": {"approved": False, "status": "pending", "approval_id": "approval-test-2", "amount_inr": 3200}},
        ]
        result = build_grounded_summary("Process the refund for ticket T1004", ledger)
        self.assertFalse(result["success"])
        self.assertIn("no financial action was executed", result["final_response"].lower())

    def test_unverified_update_is_not_reported_as_success(self):
        ledger = [{
            "tool": "update_ticket",
            "result": {
                "success": False, "verified": False, "ticket_id": "T1002",
                "error": "Could not verify update",
            },
        }]
        result = build_grounded_summary("Update a ticket", ledger)
        self.assertFalse(result["success"])
        self.assertEqual(result["verified_actions"]["ticket_updates"], [])
        self.assertIn("not verified", result["final_response"].lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
