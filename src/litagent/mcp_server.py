from __future__ import annotations

import json
import sys
import traceback
from typing import Any

from litagent.mcp_tools import call_tool_json, tool_definitions

PROTOCOL_VERSION = "2024-11-05"


def make_response(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def make_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    message_id = message.get("id")
    params = message.get("params") or {}

    if message_id is None:
        return None

    if method == "initialize":
        return make_response(
            message_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "litagent-mcp", "version": "0.1.0"},
            },
        )

    if method == "tools/list":
        return make_response(message_id, {"tools": tool_definitions()})

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            text = call_tool_json(str(tool_name), arguments)
            return make_response(
                message_id,
                {
                    "content": [{"type": "text", "text": text}],
                    "isError": False,
                },
            )
        except Exception as exc:  # noqa: BLE001 - MCP must return structured tool errors
            error_text = json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=6),
                },
                ensure_ascii=False,
                indent=2,
            )
            return make_response(
                message_id,
                {
                    "content": [{"type": "text", "text": error_text}],
                    "isError": True,
                },
            )

    return make_error(message_id, -32601, f"Method not found: {method}")


def serve(input_stream: Any = sys.stdin, output_stream: Any = sys.stdout) -> None:
    for line in input_stream:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle_request(message)
        except Exception as exc:  # noqa: BLE001 - keep MCP server alive on malformed messages
            response = make_error(None, -32700, str(exc))
        if response is not None:
            output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
            output_stream.flush()


def main() -> int:
    serve()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

