from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .paths import gateway_python_dir


DEFAULT_GATEWAY_URL = os.environ.get("UNITY_ROSLYN_GATEWAY_URL", "http://127.0.0.1:19090")


def append_query(url: str, params: dict[str, str | None]) -> str:
    query = {
        key: value
        for key, value in params.items()
        if value is not None and str(value).strip()
    }
    if not query:
        return url
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(query)


def gateway_status(
    project_root: Path,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    timeout: int = 10,
) -> tuple[int, dict[str, Any]]:
    url = append_query(f"{gateway_url}/v1/status", {"projectRoot": str(project_root)})
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset)
            return 0, json.loads(text) if text else {}
    except Exception as exc:
        return 2, {
            "state": "ClientError",
            "detail": f"Status request failed: {type(exc).__name__}: {exc}",
        }


def run_compile_check(
    project_root: Path,
    timeout: int = 180,
    gateway_url: str = DEFAULT_GATEWAY_URL,
) -> subprocess.CompletedProcess[str]:
    script = gateway_python_dir(project_root) / "check_unity_compile.py"
    return subprocess.run(
        [
            sys.executable,
            str(script),
            "--project-root",
            str(project_root),
            "--gateway-url",
            gateway_url,
            "--compile-timeout",
            str(timeout),
            "--json",
        ],
        cwd=str(project_root),
        text=True,
        capture_output=True,
        check=False,
    )


def validation_report_from_compile(
    run_id: str,
    completed: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    parsed = _parse_stdout_json(completed.stdout)
    request_state = str(parsed.get("requestState") or parsed.get("gatewayState") or parsed.get("state") or "")
    raw_evidence = parsed if parsed else {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }

    if request_state == "SecurityCheck":
        status = "blocked"
        check_status = "blocked"
    elif completed.returncode == 0:
        status = "passed"
        check_status = "passed"
    else:
        status = "failed"
        check_status = "failed"

    return {
        "version": "validation-report/v1",
        "runId": run_id,
        "status": status,
        "checks": [
            {
                "name": "unity-compile",
                "status": check_status,
                "evidence": json.dumps(raw_evidence, ensure_ascii=False, separators=(",", ":")),
            }
        ],
    }


def _parse_stdout_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}

