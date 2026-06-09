from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models import (
    AgentPullTaskResponse,
    DoCodeResponse,
    GatewayTaskPayload,
    StatusResponse,
    UnityListResponse,
    UnityTargetInfo,
)


LEGACY_UNITY_ID = "legacy-default"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_audit_log_path() -> str:
    project_root = find_unity_project_root(Path(__file__).resolve())
    return str(project_root / "Library" / "UnityRoslynGateway" / "gateway_state.log")


def find_unity_project_root(start_path: Path) -> Path:
    current = start_path if start_path.is_dir() else start_path.parent
    for candidate in [current, *current.parents]:
        if (candidate / "ProjectSettings" / "ProjectVersion.txt").is_file():
            return candidate

    return Path(__file__).resolve().parents[4]


def _clean_log_value(value: object) -> str:
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n")


class StateAuditLogger:
    def __init__(self, log_path: Optional[str]) -> None:
        self._log_path = log_path

    def write(self, event: str, **fields: object) -> None:
        if not self._log_path:
            return

        try:
            path = Path(self._log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            parts = [f"utc={utc_now_iso()}", f"event={_clean_log_value(event)}"]
            for key, value in fields.items():
                parts.append(f"{key}={_clean_log_value(value)}")

            # 审计日志不能影响网关状态机，写入失败时只静默跳过。
            with path.open("a", encoding="utf-8") as file:
                file.write(" ".join(parts))
                file.write("\n")
        except Exception:
            pass


def normalize_project_root(project_root: Optional[str]) -> Optional[str]:
    if project_root is None or not project_root.strip():
        return None

    expanded = os.path.expanduser(project_root.strip())
    return os.path.abspath(os.path.normpath(expanded))


def project_root_key(project_root: Optional[str]) -> Optional[str]:
    normalized = normalize_project_root(project_root)
    if normalized is None:
        return None
    return os.path.normcase(normalized).replace("\\", "/").casefold()


def resolve_unity_id(unity_id: Optional[str], project_root: Optional[str]) -> str:
    if unity_id is not None and unity_id.strip():
        return unity_id.strip()

    key = project_root_key(project_root)
    if key:
        return f"project:{key}"

    return LEGACY_UNITY_ID


@dataclass
class AgentSession:
    unity_id: str
    project_root: Optional[str]
    project_key: Optional[str]
    data_path: Optional[str]
    unity_process_id: int
    editor_version: str
    agent_name: str
    session_id: str
    state: str
    detail: str
    last_heartbeat_monotonic: float
    last_heartbeat_utc: str


@dataclass
class QueueTicket:
    unity_id: str
    payload: GatewayTaskPayload
    future: asyncio.Future
    enqueued_monotonic: float
    timed_out: bool = False


@dataclass
class TargetSelection:
    accepted: bool
    state: str
    message: str
    agent: Optional[AgentSession]
    online_unities: list[UnityTargetInfo]
    target_info: Optional[UnityTargetInfo]


class GatewayState:
    def __init__(
        self,
        offline_timeout_sec: float = 10.0,
        max_queue_size: int = 1,
        audit_log_path: Optional[str] = None,
    ) -> None:
        self._offline_timeout_sec = offline_timeout_sec
        self._max_queue_size = max_queue_size
        self._agents: dict[str, AgentSession] = {}
        self._session_to_unity: dict[str, str] = {}
        self._queues: dict[str, asyncio.Queue[QueueTicket]] = {}
        self._pending: dict[str, QueueTicket] = {}
        self._tickets: dict[str, QueueTicket] = {}
        self._audit_logger = StateAuditLogger(default_audit_log_path() if audit_log_path is None else audit_log_path)
        self._lock = asyncio.Lock()

    def _queue_for_unlocked(self, unity_id: str) -> asyncio.Queue[QueueTicket]:
        queue = self._queues.get(unity_id)
        if queue is None:
            queue = asyncio.Queue(maxsize=self._max_queue_size)
            self._queues[unity_id] = queue
        return queue

    def _is_agent_online_unlocked(self, agent: AgentSession) -> bool:
        elapsed = time.monotonic() - agent.last_heartbeat_monotonic
        return elapsed <= self._offline_timeout_sec

    def _agent_for_session_unlocked(self, session_id: str) -> Optional[AgentSession]:
        unity_id = self._session_to_unity.get(session_id)
        if unity_id is None:
            return None

        agent = self._agents.get(unity_id)
        if agent is None or agent.session_id != session_id:
            return None
        return agent

    def _pending_request_id_unlocked(self, unity_id: str) -> Optional[str]:
        for request_id, ticket in self._pending.items():
            if ticket.unity_id == unity_id:
                return request_id
        return None

    def _has_pending_for_unity_unlocked(self, unity_id: str) -> bool:
        return self._pending_request_id_unlocked(unity_id) is not None

    def _queued_count_unlocked(self, unity_id: str) -> int:
        queue = self._queues.get(unity_id)
        return 0 if queue is None else queue.qsize()

    def _remove_queued_ticket_unlocked(self, unity_id: str, request_id: str) -> bool:
        queue = self._queues.get(unity_id)
        if queue is None or queue.empty():
            return False

        removed = False
        kept: list[QueueTicket] = []
        while True:
            try:
                queued = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            if queued.payload.requestId == request_id:
                removed = True
                continue

            kept.append(queued)

        for queued in kept:
            queue.put_nowait(queued)

        return removed

    def _audit_event_unlocked(
        self,
        event: str,
        unity_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        **fields: object,
    ) -> None:
        pending_request_id = self._pending_request_id_unlocked(unity_id) if unity_id else None
        queued_count = self._queued_count_unlocked(unity_id) if unity_id else 0
        self._audit_logger.write(
            event,
            unity_id=unity_id,
            session_id=session_id,
            request_id=request_id,
            pending_request_id=pending_request_id,
            queued_count=queued_count,
            ticket_count=len(self._tickets),
            **fields,
        )

    def _set_agent_state_unlocked(
        self,
        agent: AgentSession,
        state: str,
        detail: str,
        event: str,
        request_id: Optional[str] = None,
        reason: str = "",
    ) -> None:
        old_state = agent.state
        old_detail = agent.detail
        agent.state = state
        agent.detail = detail
        self._audit_event_unlocked(
            event,
            unity_id=agent.unity_id,
            session_id=agent.session_id,
            request_id=request_id,
            old_state=old_state,
            new_state=state,
            old_detail=old_detail,
            new_detail=detail,
            reason=reason,
        )

    def _clear_pending_for_ready_heartbeat_unlocked(self, agent: AgentSession, detail: str) -> None:
        pending_ids = [
            request_id
            for request_id, ticket in self._pending.items()
            if ticket.unity_id == agent.unity_id
        ]
        if not pending_ids:
            return

        for request_id in pending_ids:
            ticket = self._pending.pop(request_id, None)
            self._tickets.pop(request_id, None)
            if ticket is not None:
                ticket.timed_out = True
                if not ticket.future.done():
                    ticket.future.set_exception(RuntimeError("Unity agent reported Ready while request was pending"))

            self._audit_event_unlocked(
                "heartbeat_cleared_pending",
                unity_id=agent.unity_id,
                session_id=agent.session_id,
                request_id=request_id,
                new_state="Ready",
                new_detail=detail,
                reason="Unity agent reported Ready without local pending work",
            )

    def _target_info_unlocked(self, agent: AgentSession) -> UnityTargetInfo:
        online = self._is_agent_online_unlocked(agent)
        queue = self._queues.get(agent.unity_id)
        queued_count = 0 if queue is None else queue.qsize()
        pending_request_id = self._pending_request_id_unlocked(agent.unity_id)

        if not online:
            state = "Offline"
            detail = "Unity agent is offline"
        else:
            raw_state = agent.state if agent.state in ("Ready", "Busy", "Reloading") else "Busy"
            state = raw_state
            detail = agent.detail or "Unity agent is ready"

            if pending_request_id:
                detail = f"Executing {pending_request_id}"
                if state == "Ready":
                    state = "Busy"
            elif queued_count > 0:
                detail = "Waiting queued task"
                if state == "Ready":
                    state = "Busy"

        return UnityTargetInfo(
            unityId=agent.unity_id,
            projectRoot=agent.project_root,
            dataPath=agent.data_path,
            unityProcessId=agent.unity_process_id,
            editorVersion=agent.editor_version,
            agentName=agent.agent_name,
            sessionId=agent.session_id,
            state=state,
            detail=detail,
            isOnline=online,
            lastHeartbeatUtc=agent.last_heartbeat_utc,
            pendingRequestId=pending_request_id,
            queuedCount=queued_count,
        )

    def _online_infos_unlocked(self) -> list[UnityTargetInfo]:
        infos = [
            self._target_info_unlocked(agent)
            for agent in self._agents.values()
            if self._is_agent_online_unlocked(agent)
        ]
        return sorted(infos, key=lambda item: item.unityId)

    def _status_state_from_target(self, target: UnityTargetInfo) -> str:
        if target.state == "Ready":
            return "Ready"
        if target.state == "Offline":
            return "Offline"
        return "Busy"

    def _status_response_for_target_unlocked(
        self,
        target: UnityTargetInfo,
        online_unities: list[UnityTargetInfo],
    ) -> StatusResponse:
        return StatusResponse(
            state=self._status_state_from_target(target),
            detail=target.detail,
            unitySessionId=target.sessionId,
            lastHeartbeatUtc=target.lastHeartbeatUtc,
            unityTarget=target,
            onlineUnities=online_unities,
        )

    def _select_online_target_unlocked(
        self,
        unity_id: Optional[str],
        project_root: Optional[str],
    ) -> TargetSelection:
        online_infos = self._online_infos_unlocked()

        if unity_id is not None and unity_id.strip():
            requested_unity_id = unity_id.strip()
            agent = self._agents.get(requested_unity_id)
            if agent is None:
                return TargetSelection(False, "Offline", "Requested Unity agent is not registered", None, online_infos, None)

            target_info = self._target_info_unlocked(agent)
            if not target_info.isOnline:
                return TargetSelection(False, "Offline", "Requested Unity agent is offline", None, online_infos, target_info)

            requested_project_key = project_root_key(project_root)
            if requested_project_key is not None and agent.project_key != requested_project_key:
                return TargetSelection(False, "ClientError", "unityId and projectRoot refer to different Unity agents", None, online_infos, target_info)

            return TargetSelection(True, "", "", agent, online_infos, target_info)

        requested_project_key = project_root_key(project_root)
        if requested_project_key is not None:
            known_matches = [
                agent for agent in self._agents.values()
                if agent.project_key == requested_project_key
            ]
            online_matches = [
                agent for agent in known_matches
                if self._is_agent_online_unlocked(agent)
            ]

            if len(online_matches) == 1:
                agent = online_matches[0]
                return TargetSelection(True, "", "", agent, online_infos, self._target_info_unlocked(agent))

            target_info = self._target_info_unlocked(known_matches[0]) if len(known_matches) == 1 else None
            if len(online_matches) <= 0:
                return TargetSelection(False, "Offline", "No online Unity agent matches projectRoot", None, online_infos, target_info)

            return TargetSelection(False, "ClientError", "Multiple online Unity agents match projectRoot", None, online_infos, None)

        online_agents = [
            agent for agent in self._agents.values()
            if self._is_agent_online_unlocked(agent)
        ]
        if len(online_agents) == 1:
            agent = online_agents[0]
            return TargetSelection(True, "", "", agent, online_infos, self._target_info_unlocked(agent))

        if len(online_agents) <= 0:
            return TargetSelection(False, "Offline", "No online Unity agents are connected", None, online_infos, None)

        return TargetSelection(False, "ClientError", "Multiple Unity agents are online; specify unityId or projectRoot", None, online_infos, None)

    async def list_unities(self) -> UnityListResponse:
        async with self._lock:
            unities = self._online_infos_unlocked()
            return UnityListResponse(count=len(unities), unities=unities)

    async def list_online_targets(self) -> list[UnityTargetInfo]:
        async with self._lock:
            return self._online_infos_unlocked()

    async def get_unity_info(self, unity_id: str) -> Optional[UnityTargetInfo]:
        async with self._lock:
            agent = self._agents.get(unity_id)
            if agent is None:
                return None
            return self._target_info_unlocked(agent)

    async def get_status(
        self,
        unity_id: Optional[str] = None,
        project_root: Optional[str] = None,
    ) -> StatusResponse:
        async with self._lock:
            online_unities = self._online_infos_unlocked()

            if unity_id is not None and unity_id.strip():
                agent = self._agents.get(unity_id.strip())
                if agent is not None:
                    return self._status_response_for_target_unlocked(
                        self._target_info_unlocked(agent),
                        online_unities,
                    )
                return StatusResponse(
                    state="Offline",
                    detail="Requested Unity agent is not registered",
                    onlineUnities=online_unities,
                )

            requested_project_key = project_root_key(project_root)
            if requested_project_key is not None:
                matches = [
                    agent for agent in self._agents.values()
                    if agent.project_key == requested_project_key
                ]
                online_matches = [
                    agent for agent in matches
                    if self._is_agent_online_unlocked(agent)
                ]

                if len(online_matches) == 1:
                    return self._status_response_for_target_unlocked(
                        self._target_info_unlocked(online_matches[0]),
                        online_unities,
                    )

                if len(matches) == 1:
                    return self._status_response_for_target_unlocked(
                        self._target_info_unlocked(matches[0]),
                        online_unities,
                    )

                detail = "No Unity agent matches projectRoot" if not matches else "Multiple Unity agents match projectRoot"
                return StatusResponse(
                    state="Offline" if not matches else "Busy",
                    detail=detail,
                    onlineUnities=online_unities,
                )

            if not online_unities:
                return StatusResponse(
                    state="Offline",
                    detail="No online Unity agents are connected",
                    onlineUnities=[],
                )

            if len(online_unities) == 1:
                return self._status_response_for_target_unlocked(online_unities[0], online_unities)

            busy_count = sum(1 for item in online_unities if item.state != "Ready")
            return StatusResponse(
                state="Busy" if busy_count > 0 else "Ready",
                detail=f"{len(online_unities)} Unity agents online"
                if busy_count <= 0
                else f"{len(online_unities)} Unity agents online, {busy_count} busy",
                onlineUnities=online_unities,
            )

    async def register_agent(
        self,
        agent_name: str,
        unity_id: Optional[str] = None,
        project_root: Optional[str] = None,
        data_path: Optional[str] = None,
        unity_process_id: int = 0,
        editor_version: str = "",
    ) -> AgentSession:
        async with self._lock:
            normalized_project_root = normalize_project_root(project_root)
            normalized_data_path = normalize_project_root(data_path)
            resolved_unity_id = resolve_unity_id(unity_id, normalized_project_root)
            existing = self._agents.get(resolved_unity_id)

            if normalized_project_root is None and existing is not None:
                normalized_project_root = existing.project_root
            if normalized_data_path is None and existing is not None:
                normalized_data_path = existing.data_path
            if unity_process_id <= 0 and existing is not None:
                unity_process_id = existing.unity_process_id
            if not editor_version and existing is not None:
                editor_version = existing.editor_version

            project_key = project_root_key(normalized_project_root)
            session_id = str(uuid.uuid4())
            if existing is not None:
                self._session_to_unity.pop(existing.session_id, None)

            queue = self._queue_for_unlocked(resolved_unity_id)
            pending_request_id = self._pending_request_id_unlocked(resolved_unity_id)
            has_queued_ticket = not queue.empty()
            state = "Busy" if pending_request_id or has_queued_ticket else "Ready"
            detail = (
                f"Recovering {pending_request_id}"
                if pending_request_id
                else ("Waiting queued task" if has_queued_ticket else "Registered")
            )

            agent = AgentSession(
                unity_id=resolved_unity_id,
                project_root=normalized_project_root,
                project_key=project_key,
                data_path=normalized_data_path,
                unity_process_id=unity_process_id,
                editor_version=editor_version or "",
                agent_name=agent_name or (existing.agent_name if existing is not None else "unity-editor"),
                session_id=session_id,
                state=state,
                detail=detail,
                last_heartbeat_monotonic=time.monotonic(),
                last_heartbeat_utc=utc_now_iso(),
            )
            self._agents[resolved_unity_id] = agent
            self._session_to_unity[session_id] = resolved_unity_id
            self._audit_event_unlocked(
                "register_agent",
                unity_id=resolved_unity_id,
                session_id=session_id,
                request_id=pending_request_id,
                old_state=existing.state if existing is not None else "",
                new_state=state,
                old_detail=existing.detail if existing is not None else "",
                new_detail=detail,
                project_root=normalized_project_root,
                data_path=normalized_data_path,
                unity_process_id=unity_process_id,
                editor_version=editor_version or "",
                recovered_existing=existing is not None,
            )
            return agent

    async def heartbeat(self, session_id: str, state: str, detail: str) -> bool:
        async with self._lock:
            agent = self._agent_for_session_unlocked(session_id)
            if agent is None:
                self._audit_event_unlocked("heartbeat_rejected", session_id=session_id, reason="Invalid session")
                return False

            if state == "Ready":
                self._clear_pending_for_ready_heartbeat_unlocked(agent, detail)

            if agent.state != state or agent.detail != detail:
                self._set_agent_state_unlocked(agent, state, detail, "heartbeat")
            else:
                self._audit_event_unlocked(
                    "heartbeat",
                    unity_id=agent.unity_id,
                    session_id=agent.session_id,
                    new_state=state,
                    new_detail=detail,
                    reason="unchanged",
                )

            agent.last_heartbeat_monotonic = time.monotonic()
            agent.last_heartbeat_utc = utc_now_iso()
            return True

    async def unregister_agent(self, session_id: str) -> tuple[bool, str]:
        async with self._lock:
            agent = self._agent_for_session_unlocked(session_id)
            if agent is None:
                return False, "Invalid session"

            unity_id = agent.unity_id
            self._audit_event_unlocked(
                "unregister_agent",
                unity_id=unity_id,
                session_id=session_id,
                old_state=agent.state,
                old_detail=agent.detail,
            )
            self._session_to_unity.pop(session_id, None)
            self._agents.pop(unity_id, None)

            queue = self._queues.pop(unity_id, None)
            if queue is not None:
                while True:
                    try:
                        queued = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    self._tickets.pop(queued.payload.requestId, None)
                    self._audit_event_unlocked(
                        "drop_queued_task",
                        unity_id=unity_id,
                        session_id=session_id,
                        request_id=queued.payload.requestId,
                        reason="Unity agent unregistered",
                    )
                    if not queued.future.done():
                        queued.future.set_exception(RuntimeError("Unity agent unregistered"))

            pending_ids = [
                request_id
                for request_id, ticket in self._pending.items()
                if ticket.unity_id == unity_id
            ]
            for request_id in pending_ids:
                ticket = self._pending.pop(request_id, None)
                self._tickets.pop(request_id, None)
                self._audit_event_unlocked(
                    "drop_pending_task",
                    unity_id=unity_id,
                    session_id=session_id,
                    request_id=request_id,
                    reason="Unity agent unregistered",
                )
                if ticket is not None and not ticket.future.done():
                    ticket.future.set_exception(RuntimeError("Unity agent unregistered"))

            return True, "Unregistered"

    async def enqueue_do_code(
        self,
        request_id: str,
        code: str,
        timeout_sec: int,
        refresh_assets: bool,
        request_script_compilation: bool,
        wait_for_script_compilation: bool,
        compile_timeout_sec: int,
        include_compile_diagnostics: bool,
        unity_id: Optional[str] = None,
        project_root: Optional[str] = None,
    ) -> tuple[bool, str, str, Optional[QueueTicket], list[UnityTargetInfo], Optional[UnityTargetInfo]]:
        loop = asyncio.get_running_loop()

        async with self._lock:
            selection = self._select_online_target_unlocked(unity_id, project_root)
            if not selection.accepted or selection.agent is None:
                self._audit_event_unlocked(
                    "enqueue_rejected",
                    unity_id=selection.target_info.unityId if selection.target_info is not None else unity_id,
                    request_id=request_id,
                    rejected_state=selection.state,
                    reason=selection.message,
                )
                return (
                    False,
                    selection.state,
                    selection.message,
                    None,
                    selection.online_unities,
                    selection.target_info,
                )

            if request_id in self._tickets:
                self._audit_event_unlocked(
                    "enqueue_rejected",
                    unity_id=selection.agent.unity_id,
                    session_id=selection.agent.session_id,
                    request_id=request_id,
                    rejected_state="ClientError",
                    reason="Duplicate requestId",
                )
                return (
                    False,
                    "ClientError",
                    "Duplicate requestId",
                    None,
                    selection.online_unities,
                    selection.target_info,
                )

            queue = self._queue_for_unlocked(selection.agent.unity_id)
            if queue.full():
                self._audit_event_unlocked(
                    "enqueue_rejected",
                    unity_id=selection.agent.unity_id,
                    session_id=selection.agent.session_id,
                    request_id=request_id,
                    rejected_state="BusyRejected",
                    reason="Gateway queue is full for target Unity agent",
                )
                return (
                    False,
                    "BusyRejected",
                    "Gateway queue is full for target Unity agent",
                    None,
                    selection.online_unities,
                    selection.target_info,
                )

            ticket = QueueTicket(
                unity_id=selection.agent.unity_id,
                payload=GatewayTaskPayload(
                    requestId=request_id,
                    code=code,
                    timeoutSec=timeout_sec,
                    refreshAssets=refresh_assets,
                    requestScriptCompilation=request_script_compilation,
                    waitForScriptCompilation=wait_for_script_compilation,
                    compileTimeoutSec=compile_timeout_sec,
                    includeCompileDiagnostics=include_compile_diagnostics,
                    createdAtUtc=utc_now_iso(),
                ),
                future=loop.create_future(),
                enqueued_monotonic=time.monotonic(),
            )

            self._tickets[request_id] = ticket
            queue.put_nowait(ticket)
            self._audit_event_unlocked(
                "enqueue_do_code",
                unity_id=selection.agent.unity_id,
                session_id=selection.agent.session_id,
                request_id=request_id,
                new_state=self._target_info_unlocked(selection.agent).state,
                new_detail=self._target_info_unlocked(selection.agent).detail,
                timeout_sec=timeout_sec,
                refresh_assets=refresh_assets,
                request_script_compilation=request_script_compilation,
                wait_for_script_compilation=wait_for_script_compilation,
            )
            return True, "", "", ticket, selection.online_unities, self._target_info_unlocked(selection.agent)

    async def pull_task(self, session_id: str, max_wait_ms: int) -> AgentPullTaskResponse:
        async with self._lock:
            agent = self._agent_for_session_unlocked(session_id)
            if agent is None:
                return AgentPullTaskResponse(accepted=False, message="Invalid session")
            unity_id = agent.unity_id
            queue = self._queue_for_unlocked(unity_id)

        timeout_sec = max_wait_ms / 1000.0
        end_time = time.monotonic() + timeout_sec

        while True:
            remaining = end_time - time.monotonic()
            if remaining <= 0:
                return AgentPullTaskResponse(accepted=True, hasTask=False)

            try:
                ticket = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                return AgentPullTaskResponse(accepted=True, hasTask=False)

            if ticket.timed_out:
                async with self._lock:
                    self._tickets.pop(ticket.payload.requestId, None)
                continue

            async with self._lock:
                agent = self._agent_for_session_unlocked(session_id)
                if agent is None or agent.unity_id != ticket.unity_id:
                    if not ticket.timed_out:
                        self._queue_for_unlocked(ticket.unity_id).put_nowait(ticket)
                    self._audit_event_unlocked(
                        "pull_task_rejected",
                        unity_id=ticket.unity_id,
                        session_id=session_id,
                        request_id=ticket.payload.requestId,
                        reason="Invalid session",
                    )
                    return AgentPullTaskResponse(accepted=False, message="Invalid session")

                self._pending[ticket.payload.requestId] = ticket
                self._set_agent_state_unlocked(
                    agent,
                    "Busy",
                    f"Executing {ticket.payload.requestId}",
                    "pull_task",
                    request_id=ticket.payload.requestId,
                    reason="Task assigned to Unity agent",
                )

            return AgentPullTaskResponse(accepted=True, hasTask=True, task=ticket.payload)

    async def push_result(self, session_id: str, result: DoCodeResponse) -> tuple[bool, str]:
        async with self._lock:
            agent = self._agent_for_session_unlocked(session_id)
            if agent is None:
                self._audit_event_unlocked("push_result_rejected", session_id=session_id, request_id=result.requestId, reason="Invalid session")
                return False, "Invalid session"

            ticket = self._pending.get(result.requestId)
            if ticket is None:
                self._audit_event_unlocked(
                    "push_result_rejected",
                    unity_id=agent.unity_id,
                    session_id=agent.session_id,
                    request_id=result.requestId,
                    reason="Unknown request",
                )
                return False, "Unknown request"

            if ticket.unity_id != agent.unity_id:
                self._audit_event_unlocked(
                    "push_result_rejected",
                    unity_id=agent.unity_id,
                    session_id=agent.session_id,
                    request_id=result.requestId,
                    reason="Request target mismatch",
                )
                return False, "Request target mismatch"

            self._pending.pop(result.requestId, None)
            self._tickets.pop(result.requestId, None)

            if ticket.timed_out:
                if not self._has_pending_for_unity_unlocked(agent.unity_id):
                    self._set_agent_state_unlocked(agent, "Ready", "Idle", "push_result_timed_out", request_id=result.requestId)
                else:
                    self._audit_event_unlocked(
                        "push_result_timed_out",
                        unity_id=agent.unity_id,
                        session_id=agent.session_id,
                        request_id=result.requestId,
                        old_state=agent.state,
                        new_state=agent.state,
                        old_detail=agent.detail,
                        new_detail=agent.detail,
                    )
                return False, "Timed out request"

            if self._has_pending_for_unity_unlocked(agent.unity_id):
                self._set_agent_state_unlocked(agent, "Busy", "Executing queued request", "push_result", request_id=result.requestId)
            elif not self._queue_for_unlocked(agent.unity_id).empty():
                self._set_agent_state_unlocked(agent, "Busy", "Waiting queued task", "push_result", request_id=result.requestId)
            else:
                self._set_agent_state_unlocked(agent, "Ready", "Idle", "push_result", request_id=result.requestId)

        if not ticket.future.done() and not ticket.timed_out:
            ticket.future.set_result(result)
        return True, "OK"

    async def mark_timeout(self, request_id: str) -> None:
        async with self._lock:
            ticket = self._tickets.get(request_id)
            if ticket is None:
                self._audit_event_unlocked("mark_timeout_ignored", request_id=request_id, reason="Unknown request")
                return

            ticket.timed_out = True
            was_pending = self._pending.pop(request_id, None) is not None
            was_queued = self._remove_queued_ticket_unlocked(ticket.unity_id, request_id)
            self._tickets.pop(request_id, None)

            self._audit_event_unlocked(
                "mark_timeout",
                unity_id=ticket.unity_id,
                request_id=request_id,
                reason="Client wait_for timeout elapsed",
                removed_pending=was_pending,
                removed_queued=was_queued,
            )

            agent = self._agents.get(ticket.unity_id)
            if agent is None:
                return

            if self._has_pending_for_unity_unlocked(agent.unity_id):
                self._set_agent_state_unlocked(
                    agent,
                    "Busy",
                    "Executing queued request",
                    "mark_timeout_state",
                    request_id=request_id,
                    reason="Other pending request remains after timeout",
                )
            elif not self._queue_for_unlocked(agent.unity_id).empty():
                self._set_agent_state_unlocked(
                    agent,
                    "Busy",
                    "Waiting queued task",
                    "mark_timeout_state",
                    request_id=request_id,
                    reason="Queued request remains after timeout",
                )
            else:
                self._set_agent_state_unlocked(
                    agent,
                    "Ready",
                    "Idle",
                    "mark_timeout_state",
                    request_id=request_id,
                    reason="Timed out request cleared",
                )
