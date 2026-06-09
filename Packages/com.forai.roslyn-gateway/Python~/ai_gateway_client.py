#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_GATEWAY_URL = os.environ.get("UNITY_ROSLYN_GATEWAY_URL", "http://127.0.0.1:19090")


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def http_json(method: str, url: str, payload: dict[str, Any] | None, timeout: int) -> dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json; charset=utf-8"}

    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(url=url, data=data, method=method.upper(), headers=headers)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        text = response.read().decode(charset)
        if not text:
            return {}
        return json.loads(text)


def append_query(url: str, params: dict[str, str | None]) -> str:
    query = {
        key: value
        for key, value in params.items()
        if value is not None and str(value).strip()
    }
    if not query:
        return url
    separator = "&" if "?" in url else "?"
    return url + separator + urllib.parse.urlencode(query)


def add_target_payload(payload: dict[str, Any], args: argparse.Namespace) -> None:
    project_root = getattr(args, "project_root", None)
    unity_id = getattr(args, "unity_id", None)
    if project_root:
        payload["projectRoot"] = project_root
    if unity_id:
        payload["unityId"] = unity_id


def target_params(args: argparse.Namespace) -> dict[str, str | None]:
    return {
        "projectRoot": getattr(args, "project_root", None),
        "unityId": getattr(args, "unity_id", None),
    }


def handle_status(args: argparse.Namespace) -> int:
    try:
        url = append_query(f"{args.gateway_url}/v1/status", target_params(args))
        response = http_json("GET", url, None, timeout=args.http_timeout)
        print_json(response)
        return 0
    except Exception as exc:
        print_json(
            {
                "state": "ClientError",
                "detail": f"Status request failed: {type(exc).__name__}: {exc}",
            }
        )
        return 2


def handle_list_unities(args: argparse.Namespace) -> int:
    try:
        response = http_json("GET", f"{args.gateway_url}/v1/unities", None, timeout=args.http_timeout)
        print_json(response)
        return 0
    except Exception as exc:
        print_json(
            {
                "state": "ClientError",
                "detail": f"List unities request failed: {type(exc).__name__}: {exc}",
            }
        )
        return 2


def load_code(args: argparse.Namespace) -> str:
    if args.code is not None:
        return args.code

    if args.code_file is not None:
        path = Path(args.code_file)
        return path.read_text(encoding="utf-8")

    if args.code_stdin:
        text = sys.stdin.read()
        if not text:
            raise ValueError("STDIN为空，无法读取代码")
        return text

    raise ValueError("必须提供 --code 或 --code-file 或 --code-stdin")


def handle_do_code(args: argparse.Namespace) -> int:
    try:
        code = load_code(args)
    except Exception as exc:
        print_json(
            {
                "requestId": "",
                "success": False,
                "state": "ClientError",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "stackTrace": None,
                },
            }
        )
        return 2

    payload = {
        "code": code,
        "timeoutSec": args.timeout,
        "refreshAssets": args.refresh_assets,
        "requestScriptCompilation": args.request_script_compilation,
        "waitForScriptCompilation": args.wait_for_script_compilation,
        "compileTimeoutSec": args.compile_timeout,
        "includeCompileDiagnostics": not args.no_compile_diagnostics,
    }

    if args.request_id:
        payload["requestId"] = args.request_id
    add_target_payload(payload, args)

    try:
        effective_wait_timeout = args.timeout
        if args.wait_for_script_compilation:
            effective_wait_timeout = max(
                effective_wait_timeout,
                args.compile_timeout if args.compile_timeout > 0 else 600,
            )

        response = http_json(
            "POST",
            f"{args.gateway_url}/v1/do-code",
            payload,
            timeout=max(effective_wait_timeout + 5, args.http_timeout),
        )
        print_json(response)
        return 0
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        print_json(
            {
                "requestId": payload.get("requestId", ""),
                "success": False,
                "state": "ClientError",
                "error": {
                    "type": "HTTPError",
                    "message": f"HTTP {exc.code}: {text}",
                    "stackTrace": None,
                },
            }
        )
        return 2
    except Exception as exc:
        print_json(
            {
                "requestId": payload.get("requestId", ""),
                "success": False,
                "state": "ClientError",
                "error": {
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "stackTrace": None,
                },
            }
        )
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unity Roslyn Gateway CLI")
    parser.add_argument("--gateway-url", default=DEFAULT_GATEWAY_URL, help="网关地址")
    parser.add_argument("--http-timeout", type=int, default=10, help="HTTP请求超时秒数")

    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="查询Unity可执行状态")
    status_parser.add_argument("--project-root", help="按 Unity 工程根目录查询目标")
    status_parser.add_argument("--unity-id", help="按 Unity 稳定 ID 查询目标")
    status_parser.set_defaults(handler=handle_status)

    list_parser = subparsers.add_parser("list-unities", help="列出当前在线的 Unity 实例")
    list_parser.set_defaults(handler=handle_list_unities)

    do_code_parser = subparsers.add_parser("do-code", help="发送代码字符串执行")
    do_code_parser.add_argument("--code", help="直接传入代码字符串")
    do_code_parser.add_argument("--code-file", help="从UTF-8文件读取代码字符串")
    do_code_parser.add_argument("--code-stdin", action="store_true", help="从STDIN读取代码字符串")
    do_code_parser.add_argument("--timeout", type=int, default=30, help="DoCode执行超时秒数")
    do_code_parser.add_argument("--request-id", help="自定义请求ID")
    do_code_parser.add_argument("--refresh-assets", action="store_true", help="执行代码后主动刷新 Unity 资源数据库")
    do_code_parser.add_argument("--request-script-compilation", action="store_true", help="执行代码后主动请求 Unity 脚本编译")
    do_code_parser.add_argument("--wait-for-script-compilation", action="store_true", help="等待 Unity 脚本编译完成并返回最终结果")
    do_code_parser.add_argument("--compile-timeout", type=int, default=0, help="等待 Unity 编译的超时秒数，0 表示使用 Editor 默认值")
    do_code_parser.add_argument("--no-compile-diagnostics", action="store_true", help="等待编译时不返回详细诊断列表")
    do_code_parser.add_argument("--project-root", help="指定 Unity 工程根目录作为执行目标")
    do_code_parser.add_argument("--unity-id", help="指定 Unity 稳定 ID 作为执行目标")
    do_code_parser.set_defaults(handler=handle_do_code)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
