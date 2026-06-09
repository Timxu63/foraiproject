from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
import uuid

import uvicorn
from fastapi import FastAPI

from models import (
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    AgentPullTaskRequest,
    AgentPullTaskResponse,
    AgentPushResultRequest,
    AgentPushResultResponse,
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentUnregisterRequest,
    AgentUnregisterResponse,
    DoCodeRequest,
    DoCodeResponse,
    ErrorInfo,
    StatusResponse,
    TimingInfo,
    UnityListResponse,
)
from state_store import GatewayState


LOGGER = logging.getLogger("unity_roslyn_gateway")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

HEARTBEAT_INTERVAL_SEC = 1.0
OFFLINE_TIMEOUT_SEC = 10.0


APP = FastAPI(title="Unity Roslyn Gateway", version="1.0.0")
STATE = GatewayState(offline_timeout_sec=OFFLINE_TIMEOUT_SEC, max_queue_size=1)


@APP.get("/v1/status", response_model=StatusResponse)
async def get_status(unityId: str | None = None, projectRoot: str | None = None) -> StatusResponse:
    return await STATE.get_status(unity_id=unityId, project_root=projectRoot)


@APP.get("/v1/unities", response_model=UnityListResponse)
async def list_unities() -> UnityListResponse:
    return await STATE.list_unities()


@APP.post("/v1/do-code", response_model=DoCodeResponse)
async def do_code(request: DoCodeRequest) -> DoCodeResponse:
    request_id = request.requestId or str(uuid.uuid4())
    accepted, reject_state, reject_message, ticket, online_unities, target_info = await STATE.enqueue_do_code(
        request_id=request_id,
        code=request.code,
        timeout_sec=request.timeoutSec,
        refresh_assets=request.refreshAssets,
        request_script_compilation=request.requestScriptCompilation,
        wait_for_script_compilation=request.waitForScriptCompilation,
        compile_timeout_sec=request.compileTimeoutSec,
        include_compile_diagnostics=request.includeCompileDiagnostics,
        unity_id=request.unityId,
        project_root=request.projectRoot,
    )

    if not accepted or ticket is None:
        return DoCodeResponse(
            requestId=request_id,
            success=False,
            state=reject_state,
            error=ErrorInfo(type=reject_state, message=reject_message),
            unityTarget=target_info,
            onlineUnities=online_unities,
        )

    try:
        effective_timeout_sec = request.timeoutSec
        if request.waitForScriptCompilation:
            effective_timeout_sec = max(
                effective_timeout_sec,
                request.compileTimeoutSec if request.compileTimeoutSec > 0 else 600,
            )

        result = await asyncio.wait_for(ticket.future, timeout=effective_timeout_sec)
        roundtrip_ms = int((time.monotonic() - ticket.enqueued_monotonic) * 1000)
        if result.timingMs is None:
            result.timingMs = TimingInfo()

        result.timingMs.total = max(result.timingMs.total, roundtrip_ms)

        if result.timingMs.queue <= 0:
            result.timingMs.queue = max(
                0,
                result.timingMs.total - result.timingMs.compile - result.timingMs.execute,
            )
        result.unityTarget = await STATE.get_unity_info(ticket.unity_id)
        result.onlineUnities = await STATE.list_online_targets()
        return result
    except asyncio.TimeoutError:
        await STATE.mark_timeout(request_id)
        return DoCodeResponse(
            requestId=request_id,
            success=False,
            state="Timeout",
            error=ErrorInfo(type="Timeout", message=f"DoCode timed out after {effective_timeout_sec} seconds"),
            timingMs=TimingInfo(total=effective_timeout_sec * 1000),
            unityTarget=target_info,
            onlineUnities=await STATE.list_online_targets(),
        )
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("DoCode failed unexpectedly for request_id=%s", request_id)
        return DoCodeResponse(
            requestId=request_id,
            success=False,
            state="ClientError",
            error=ErrorInfo(type=type(exc).__name__, message=str(exc)),
            unityTarget=target_info,
            onlineUnities=await STATE.list_online_targets(),
        )


@APP.post("/internal/agent/register", response_model=AgentRegisterResponse)
async def register_agent(request: AgentRegisterRequest) -> AgentRegisterResponse:
    agent = await STATE.register_agent(
        agent_name=request.agentName,
        unity_id=request.unityId,
        project_root=request.projectRoot,
        data_path=request.dataPath,
        unity_process_id=request.unityProcessId,
        editor_version=request.editorVersion,
    )
    LOGGER.info(
        "Unity agent registered: agent_name=%s unity_id=%s project_root=%s session_id=%s",
        agent.agent_name,
        agent.unity_id,
        agent.project_root,
        agent.session_id,
    )
    return AgentRegisterResponse(
        accepted=True,
        sessionId=agent.session_id,
        unityId=agent.unity_id,
        projectRoot=agent.project_root,
        dataPath=agent.data_path,
        unityProcessId=agent.unity_process_id,
        editorVersion=agent.editor_version,
        heartbeatIntervalSec=HEARTBEAT_INTERVAL_SEC,
        pollIntervalSec=0.1,
        message="Registered",
    )


@APP.post("/internal/agent/heartbeat", response_model=AgentHeartbeatResponse)
async def heartbeat(request: AgentHeartbeatRequest) -> AgentHeartbeatResponse:
    ok = await STATE.heartbeat(request.sessionId, request.state, request.detail)
    if not ok:
        return AgentHeartbeatResponse(accepted=False, message="Invalid session")
    return AgentHeartbeatResponse(accepted=True, message="OK")


@APP.post("/internal/agent/unregister", response_model=AgentUnregisterResponse)
async def unregister_agent(request: AgentUnregisterRequest) -> AgentUnregisterResponse:
    ok, message = await STATE.unregister_agent(request.sessionId)
    return AgentUnregisterResponse(accepted=ok, message=message)


@APP.post("/internal/agent/pull-task", response_model=AgentPullTaskResponse)
async def pull_task(request: AgentPullTaskRequest) -> AgentPullTaskResponse:
    return await STATE.pull_task(request.sessionId, request.maxWaitMs)


@APP.post("/internal/agent/push-result", response_model=AgentPushResultResponse)
async def push_result(request: AgentPushResultRequest) -> AgentPushResultResponse:
    ok, message = await STATE.push_result(request.sessionId, request.result)
    if not ok:
        return AgentPushResultResponse(accepted=False, message=message)

    LOGGER.info(
        "Result received: request_id=%s success=%s state=%s",
        request.requestId,
        request.result.success,
        request.result.state,
    )
    return AgentPushResultResponse(accepted=True, message=message)


@APP.post("/internal/control/shutdown")
async def shutdown_gateway() -> dict[str, object]:
    loop = asyncio.get_running_loop()
    loop.call_later(0.15, _terminate_current_process)
    return {"accepted": True, "message": "Shutdown requested"}


def _terminate_current_process() -> None:
    try:
        os.kill(os.getpid(), signal.SIGTERM)
    except Exception:
        os._exit(0)


def main() -> None:
    host = os.environ.get("UNITY_ROSLYN_GATEWAY_HOST", "127.0.0.1")
    port = int(os.environ.get("UNITY_ROSLYN_GATEWAY_PORT", "19090"))
    log_level = os.environ.get("UNITY_ROSLYN_GATEWAY_LOG_LEVEL", "warning").lower()
    access_log = os.environ.get("UNITY_ROSLYN_GATEWAY_ACCESS_LOG", "0").strip().lower() in ("1", "true", "yes", "on")

    uvicorn.run(
        "gateway_server:APP",
        host=host,
        port=port,
        reload=False,
        log_level=log_level,
        access_log=access_log,
    )


if __name__ == "__main__":
    main()
