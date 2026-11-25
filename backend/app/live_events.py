"""Read-only Ticketbox MCP discovery. Never mix these offers with simulated orders."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from .textutil import norm

MCP_URL = "https://mcp.ticketbox.vn/mcp"


class LiveEventError(Exception):
    pass


def _rpc(client: httpx.Client, method: str, params: dict, request_id: int, headers: dict) -> dict:
    response = client.post(MCP_URL, headers=headers, json={
        "jsonrpc": "2.0", "id": request_id, "method": method, "params": params,
    })
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or "error" in payload or not isinstance(payload.get("result"), dict):
        raise LiveEventError("Nguồn Ticketbox chưa trả được kết quả hợp lệ. Vui lòng thử lại sau.")
    if session_id := response.headers.get("Mcp-Session-Id"):
        headers["Mcp-Session-Id"] = session_id
    return payload["result"]


def search(query: str = "", city_id: int | None = None, limit: int = 10,
           client: httpx.Client | None = None) -> dict:
    """Query Ticketbox now; filter provider matches by title and validate purchase URLs."""
    owned_client = client is None
    client = client or httpx.Client(timeout=12.0, follow_redirects=False)
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    try:
        init = _rpc(client, "initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "momo-trip-assistant", "version": "0.1"},
        }, 1, headers)
        headers["MCP-Protocol-Version"] = init.get("protocolVersion", "2025-06-18")
        args = {"language": "vi", "limit": limit, "include_ineligible": True}
        if query.strip():
            args["query"] = query.strip()
        if city_id:
            args["cityId"] = city_id
        result = _rpc(client, "tools/call", {"name": "search_events", "arguments": args}, 2, headers)
        data = result.get("structuredContent")
        if result.get("isError") or not isinstance(data, dict) or not isinstance(data.get("events"), list):
            raise LiveEventError("Nguồn Ticketbox chưa trả được kết quả hợp lệ. Vui lòng thử lại sau.")
        matches = []
        wanted = norm(query)
        for raw in data["events"]:
            if not isinstance(raw, dict):
                continue
            title, url = raw.get("name"), raw.get("url") or raw.get("eventUrl") or raw.get("fallback_url")
            if not isinstance(title, str) or not isinstance(url, str):
                continue
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.netloc.lower() != "ticketbox.vn" or not parsed.path.strip("/"):
                continue
            if wanted and wanted not in norm(title):
                continue  # Provider may return unrelated fallback results for a missing title.
            event_id = raw.get("id")
            if not isinstance(event_id, (int, str)) or not str(event_id):
                continue
            starts_at = raw.get("startTime")
            if isinstance(starts_at, str):
                try:
                    if datetime.fromisoformat(starts_at.replace("Z", "+00:00")).tzinfo is None:
                        starts_at = None
                except ValueError:
                    starts_at = None
            else:
                starts_at = None
            price = raw.get("price")
            matches.append({
                "id": str(event_id), "title": title[:200], "url": url,
                "starts_at": starts_at,
                "price_from_vnd": price if isinstance(price, int) and price >= 0 else None,
            })
        return {
            "source": "Ticketbox MCP", "checked_at": datetime.now(timezone.utc).isoformat(),
            "results": matches, "has_more": bool(data.get("has_more")),
            "notice": "Kết quả từ Ticketbox tại thời điểm truy vấn; giá và tình trạng vé có thể đổi. Kiểm tra lần cuối trên Ticketbox trước khi mua.",
        }
    except (httpx.HTTPError, ValueError) as exc:
        raise LiveEventError("Không kết nối được nguồn sự kiện Ticketbox. Vui lòng thử lại sau.") from exc
    finally:
        if owned_client:
            client.close()
