import asyncio
import tempfile
import unittest
from pathlib import Path

from state_store import GatewayState, default_audit_log_path


class GatewayStateAuditLogTests(unittest.TestCase):
    def test_default_audit_log_path_resolves_unity_project_root_after_package_move(self) -> None:
        expected = Path(__file__).resolve().parents[4] / "Library" / "UnityRoslynGateway" / "gateway_state.log"

        self.assertEqual(str(expected), default_audit_log_path())

    def test_register_agent_writes_state_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            log_path = temp_path / "gateway_state.log"
            state = GatewayState(offline_timeout_sec=10.0, max_queue_size=1, audit_log_path=str(log_path))

            asyncio.run(
                state.register_agent(
                    agent_name="unity-editor",
                    unity_id="unity-test",
                    project_root=str(temp_path),
                    data_path=str(temp_path / "Assets"),
                    unity_process_id=1234,
                    editor_version="6000.0",
                )
            )

            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("event=register_agent", log_text)
            self.assertIn("unity_id=unity-test", log_text)
            self.assertIn("new_state=Ready", log_text)

    def test_mark_timeout_clears_pending_request_and_restores_ready_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            state = GatewayState(offline_timeout_sec=10.0, max_queue_size=1, audit_log_path=str(temp_path / "gateway_state.log"))

            agent = asyncio.run(
                state.register_agent(
                    agent_name="unity-editor",
                    unity_id="unity-timeout",
                    project_root=str(temp_path),
                    data_path=str(temp_path / "Assets"),
                    unity_process_id=1234,
                    editor_version="6000.0",
                )
            )

            accepted, _, _, ticket, _, _ = asyncio.run(
                state.enqueue_do_code(
                    request_id="timeout-request",
                    code="return 1;",
                    timeout_sec=1,
                    refresh_assets=False,
                    request_script_compilation=False,
                    wait_for_script_compilation=False,
                    compile_timeout_sec=0,
                    include_compile_diagnostics=True,
                    unity_id=agent.unity_id,
                    project_root=None,
                )
            )
            self.assertTrue(accepted)

            pulled = asyncio.run(state.pull_task(agent.session_id, 50))
            self.assertTrue(pulled.accepted)
            self.assertTrue(pulled.hasTask)

            busy_status = asyncio.run(state.get_status(unity_id=agent.unity_id))
            self.assertEqual("Busy", busy_status.state)
            self.assertEqual("timeout-request", busy_status.unityTarget.pendingRequestId)

            asyncio.run(state.mark_timeout("timeout-request"))

            ready_status = asyncio.run(state.get_status(unity_id=agent.unity_id))
            self.assertEqual("Ready", ready_status.state)
            self.assertIsNone(ready_status.unityTarget.pendingRequestId)
            self.assertEqual("Idle", ready_status.unityTarget.detail)

    def test_ready_heartbeat_clears_lost_pending_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            state = GatewayState(offline_timeout_sec=10.0, max_queue_size=1, audit_log_path=str(temp_path / "gateway_state.log"))

            agent = asyncio.run(
                state.register_agent(
                    agent_name="unity-editor",
                    unity_id="unity-ready-heartbeat",
                    project_root=str(temp_path),
                    data_path=str(temp_path / "Assets"),
                    unity_process_id=1234,
                    editor_version="6000.0",
                )
            )

            accepted, _, _, ticket, _, _ = asyncio.run(
                state.enqueue_do_code(
                    request_id="lost-request",
                    code="return 1;",
                    timeout_sec=30,
                    refresh_assets=False,
                    request_script_compilation=False,
                    wait_for_script_compilation=False,
                    compile_timeout_sec=0,
                    include_compile_diagnostics=True,
                    unity_id=agent.unity_id,
                    project_root=None,
                )
            )
            self.assertTrue(accepted)
            self.assertIsNotNone(ticket)
            self.assertTrue(asyncio.run(state.pull_task(agent.session_id, 50)).hasTask)

            asyncio.run(state.heartbeat(agent.session_id, "Ready", "Registered"))
            self.assertIsInstance(ticket.future.exception(), RuntimeError)

            ready_status = asyncio.run(state.get_status(unity_id=agent.unity_id))
            self.assertEqual("Ready", ready_status.state)
            self.assertIsNone(ready_status.unityTarget.pendingRequestId)
            self.assertEqual("Registered", ready_status.unityTarget.detail)


if __name__ == "__main__":
    unittest.main()
