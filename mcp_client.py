"""Minimal client for the OParl-Lite Bonn MCP server (Streamable HTTP, stateless).

Each tool call is one JSON-RPC POST; results are cached on disk by
(tool, arguments) so reruns don't hit the server again.
"""
import hashlib
import json
import time
import urllib.request
from pathlib import Path

ENDPOINT = "https://oparl.bonn.machdenstaat.de/mcp"
CACHE = Path(__file__).parent / "cache"
MIN_INTERVAL = 0.3  # seconds between live requests

_last_call = 0.0
_next_id = 0


def call(tool, use_cache=True, **arguments):
    """Call one MCP tool and return its parsed JSON result."""
    global _last_call, _next_id
    key = hashlib.sha1(json.dumps([tool, arguments], sort_keys=True).encode()).hexdigest()
    path = CACHE / tool / f"{key}.json"
    if use_cache and path.exists():
        return json.loads(path.read_text())

    wait = MIN_INTERVAL - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _next_id += 1
    body = json.dumps({
        "jsonrpc": "2.0", "id": _next_id, "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "bonn-entscheidet/0.1 (personal research)",
    })
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read())
            break
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    _last_call = time.monotonic()

    if "error" in payload:
        raise RuntimeError(f"{tool}: {payload['error']}")
    result = payload["result"]
    if result.get("isError"):
        raise RuntimeError(f"{tool}: {result['content'][0]['text']}")
    data = json.loads(result["content"][0]["text"])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return data


def paginate(tool, items_key, limit=100, **arguments):
    """Yield all items of a paginated list tool."""
    offset = 0
    while offset is not None:
        page = call(tool, limit=limit, offset=offset, **arguments)
        yield from page.get(items_key, [])
        offset = page.get("next_offset")
