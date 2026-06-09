#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from ai_gateway_client import DEFAULT_GATEWAY_URL, append_query, http_json


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="通过 Unity Roslyn Gateway 检查 Unity 工程脚本编译状态")
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL, help="网关地址")
    parser.add_argument("--http-timeout", type=int, default=15, help="HTTP 请求超时秒数")
    parser.add_argument(
        "--mode",
        choices=("compile", "current"),
        default="compile",
        help="compile=主动请求 Unity 脚本编译并等待结果；current=只读取当前编译状态",
    )
    parser.add_argument("--timeout", type=int, default=30, help="DoCode 执行超时秒数")
    parser.add_argument("--compile-timeout", type=int, default=180, help="等待 Unity 编译完成的超时秒数")
    parser.add_argument("--no-refresh-assets", action="store_true", help="执行检查前不调用 AssetDatabase.Refresh")
    parser.add_argument("--project-root", help="指定 Unity 工程根目录作为检查目标")
    parser.add_argument("--unity-id", help="指定 Unity 稳定 ID 作为检查目标")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON 结果")
    return parser


def query_status(args: argparse.Namespace) -> dict[str, Any]:
    url = append_query(
        f"{args.gateway_url}/v1/status",
        {
            "projectRoot": args.project_root,
            "unityId": args.unity_id,
        },
    )
    return http_json("GET", url, None, timeout=args.http_timeout)


def do_code(args: argparse.Namespace, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    return http_json("POST", f"{args.gateway_url}/v1/do-code", payload, timeout=timeout)


def handle_current_mode(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    # 直接读取 Unity 编辑器当前编译标记，适合快速判断当前会话是否存在脚本编译失败。
    code = """
bool isCompiling = UnityEditor.EditorApplication.isCompiling;
bool scriptCompilationFailed = UnityEditor.EditorUtility.scriptCompilationFailed;
return new
{
    IsCompiling = isCompiling,
    ScriptCompilationFailed = scriptCompilationFailed,
};
""".strip()

    payload = {
        "code": code,
        "timeoutSec": args.timeout,
        "refreshAssets": False,
        "requestScriptCompilation": False,
        "waitForScriptCompilation": False,
        "compileTimeoutSec": 0,
        "includeCompileDiagnostics": True,
    }
    add_target_payload(args, payload)

    response = do_code(args, payload, timeout=max(args.timeout + 5, args.http_timeout))
    state = response.get("state", "")
    result = (((response.get("result") or {}).get("resultJson")) or "")

    exit_code = 0 if state == "Success" else 2
    normalized = {
        "mode": "current",
        "gatewayState": "Ready",
        "requestState": state,
        "raw": response,
        "resultJson": result,
    }
    return exit_code, normalized


def handle_compile_mode(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    # 触发 Unity 自己的脚本编译，并等待编译诊断返回；这是判断工程真实编译状态的主路径。
    code = 'return "unity-compile-check";'
    payload = {
        "code": code,
        "timeoutSec": args.timeout,
        "refreshAssets": not args.no_refresh_assets,
        "requestScriptCompilation": True,
        "waitForScriptCompilation": True,
        "compileTimeoutSec": args.compile_timeout,
        "includeCompileDiagnostics": True,
    }
    add_target_payload(args, payload)

    response = do_code(
        args,
        payload,
        timeout=max(args.timeout, args.compile_timeout) + 10,
    )

    compile_info = response.get("compile") or {}
    diagnostics = compile_info.get("diagnostics") or []
    has_compile_error = bool(compile_info.get("compilationHadErrors")) or any(
        str(diagnostic.get("severity", "")).lower() == "error"
        for diagnostic in diagnostics
    )

    state = response.get("state", "")
    if state in ("Timeout", "BusyRejected", "Offline", "ClientError", "RuntimeError", "SecurityCheck"):
        exit_code = 2
    elif state == "CompileError" or has_compile_error:
        exit_code = 1
    else:
        exit_code = 0

    normalized = {
        "mode": "compile",
        "gatewayState": "Ready",
        "requestState": state,
        "compilationCompleted": bool(compile_info.get("compilationCompleted")),
        "compilationHadErrors": bool(compile_info.get("compilationHadErrors")),
        "diagnostics": diagnostics,
        "raw": response,
    }
    return exit_code, normalized


def add_target_payload(args: argparse.Namespace, payload: dict[str, Any]) -> None:
    if args.project_root:
        payload["projectRoot"] = args.project_root
    if args.unity_id:
        payload["unityId"] = args.unity_id


def print_human_summary(payload: dict[str, Any]) -> None:
    mode = payload["mode"]
    if mode == "current":
        raw = payload["raw"]
        result_text = ((raw.get("result") or {}).get("resultText")) or ""
        print(f"模式: {mode}")
        print(f"请求状态: {payload['requestState']}")
        print(f"结果: {result_text or '<empty>'}")
        return

    diagnostics = payload["diagnostics"]
    print(f"模式: {mode}")
    print(f"请求状态: {payload['requestState']}")
    print(f"编译完成: {payload['compilationCompleted']}")
    print(f"存在编译错误: {payload['compilationHadErrors']}")
    print(f"诊断数量: {len(diagnostics)}")

    if diagnostics:
        print("诊断明细:")
        for index, diagnostic in enumerate(diagnostics, start=1):
            severity = diagnostic.get("severity", "")
            code = diagnostic.get("code", "")
            message = diagnostic.get("message", "")
            line = diagnostic.get("line", "")
            column = diagnostic.get("column", "")
            print(f"{index}. [{severity}] {code} L{line}:C{column} {message}")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        status = query_status(args)
        if status.get("state") != "Ready":
            payload = {
                "mode": args.mode,
                "gatewayState": status.get("state", "Unknown"),
                "detail": status.get("detail", ""),
            }
            if args.json:
                print_json(payload)
            else:
                print(f"网关不可用: {payload['gatewayState']} {payload['detail']}".strip())
            return 2

        if args.mode == "current":
            exit_code, payload = handle_current_mode(args)
        else:
            exit_code, payload = handle_compile_mode(args)

        if args.json:
            print_json(payload)
        else:
            print_human_summary(payload)
        return exit_code
    except Exception as exc:
        payload = {
            "mode": args.mode,
            "gatewayState": "ClientError",
            "detail": f"{type(exc).__name__}: {exc}",
        }
        if args.json:
            print_json(payload)
        else:
            print(f"检查失败: {payload['detail']}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
