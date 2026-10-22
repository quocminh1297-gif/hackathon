"""HTTP-level regression tests for AgentGuard's simulated governance demo."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class DemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "AGENTGUARD_PORT": str(cls.port)}
        cls.proc = subprocess.Popen([sys.executable, "server.py"], cwd=ROOT,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        for _ in range(50):
            try:
                cls.call("GET", "/api/state")
                break
            except Exception:
                if cls.proc.poll() is not None:
                    raise RuntimeError("AgentGuard test server exited during startup")
                time.sleep(.1)
        else:
            cls.proc.terminate()
            raise RuntimeError("AgentGuard test server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=3)

    @classmethod
    def call(cls, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(cls.base + path, data=body, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def setUp(self):
        self.call("POST", "/api/reset", {})

    def request(self):
        status, req = self.call("POST", "/api/request-access", {"actor": "nova"})
        self.assertEqual(status, 201)
        return req["id"]

    def test_requester_cannot_self_approve(self):
        rid = self.request()
        status, _ = self.call("POST", "/api/approve", {"requestId": rid, "admin": "nova"})
        self.assertEqual(status, 403)
        _, state = self.call("GET", "/api/state")
        self.assertEqual(state["requests"][0]["approvals"], [])
        self.assertNotIn("sensitive-reader", state["roles"])

    def test_duplicate_approval_is_denied_and_does_not_count_twice(self):
        rid = self.request()
        self.assertEqual(self.call("POST", "/api/approve", {"requestId": rid, "admin": "admin-alex"})[0], 200)
        self.assertEqual(self.call("POST", "/api/approve", {"requestId": rid, "admin": "admin-alex"})[0], 409)
        _, state = self.call("GET", "/api/state")
        self.assertEqual(state["requests"][0]["approvals"], ["admin-alex"])
        self.assertEqual(state["requests"][0]["status"], "PENDING")

    def test_direct_api_cannot_self_grant_role(self):
        rid = self.request()
        self.assertEqual(self.call("POST", "/api/approve", {"requestId": rid, "admin": "nova"})[0], 403)
        # There is no grant endpoint; guessing a direct mutation route cannot grant access.
        self.assertEqual(self.call("POST", "/api/grant", {"actor": "nova", "role": "sensitive-reader"})[0], 404)
        _, state = self.call("GET", "/api/state")
        self.assertNotIn("sensitive-reader", state["roles"])

    def test_server_checks_authorization_even_when_api_is_called_directly(self):
        status, result = self.call("POST", "/api/read", {"actor": "nova", "docId": "hr-confidential"})
        self.assertEqual(status, 403)
        self.assertFalse(result["ok"])

    def test_quorum_state_transitions_only_after_two_distinct_approvers(self):
        rid = self.request()
        _, first = self.call("POST", "/api/approve", {"requestId": rid, "admin": "admin-alex"})
        self.assertEqual(first["status"], "PENDING")
        self.assertEqual(len(first["approvals"]), 1)
        self.assertEqual(self.call("POST", "/api/read", {"actor": "nova", "docId": "hr-confidential"})[0], 403)
        _, second = self.call("POST", "/api/approve", {"requestId": rid, "admin": "admin-blair"})
        self.assertEqual(second["status"], "APPROVED_AND_APPLIED")
        self.assertEqual(len(second["approvals"]), 2)
        self.assertEqual(self.call("POST", "/api/read", {"actor": "nova", "docId": "hr-confidential"})[0], 200)

    def test_audit_trail_records_denials_approvals_and_quorum_application(self):
        rid = self.request()
        self.call("POST", "/api/approve", {"requestId": rid, "admin": "nova"})
        self.call("POST", "/api/approve", {"requestId": rid, "admin": "admin-alex"})
        self.call("POST", "/api/approve", {"requestId": rid, "admin": "admin-alex"})
        self.call("POST", "/api/approve", {"requestId": rid, "admin": "admin-blair"})
        _, state = self.call("GET", "/api/state")
        events = [(entry["action"], entry["outcome"]) for entry in state["audit"]]
        self.assertTrue(any(action == "APPROVE ROLE" and "self approval" in outcome for action, outcome in events))
        self.assertTrue(any(action == "APPROVE ROLE" and "duplicate approval" in outcome for action, outcome in events))
        self.assertTrue(any(action == "APPROVE ROLE" and outcome == "APPROVED 1/2" for action, outcome in events))
        self.assertIn(("APPLY ROLE", "APPLIED AFTER QUORUM"), events)


if __name__ == "__main__":
    unittest.main(verbosity=2)
