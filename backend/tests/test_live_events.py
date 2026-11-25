import json

import httpx
from fastapi.testclient import TestClient

from app import live_events
from app.main import create_app

from .helpers import validator


def test_live_search_filters_unrelated_titles_and_unsafe_links():
    calls = []

    def handler(request):
        payload = json.loads(request.content)
        calls.append(payload["method"])
        if payload["method"] == "initialize":
            result = {"protocolVersion": "2025-06-18"}
        else:
            assert payload["params"]["arguments"]["query"] == "Lời Thề Biển Xanh"
            result = {"structuredContent": {"events": [
                {"id": 1, "name": "VinWonders", "url": "https://ticketbox.vn/vinwonders-1", "price": 100000},
                {"id": 2, "name": "Lời Thề Biển Xanh", "url": "https://evil.example/2", "price": 100000},
                {"id": 3, "name": "Lời Thề Biển Xanh", "url": "https://ticketbox.vn/loi-the-bien-xanh-3",
                 "startTime": "2026-12-12T12:30:00Z", "price": 200000},
            ], "has_more": False}}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": result})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = live_events.search("Lời Thề Biển Xanh", client=client)
    assert calls == ["initialize", "tools/call"]
    assert [x["id"] for x in result["results"]] == ["3"]
    assert not list(validator("live_events").iter_errors(result))


def test_live_search_does_not_use_synthetic_fallback_on_provider_error():
    def handler(_):
        return httpx.Response(503, text="provider down")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        try:
            live_events.search("concert", client=client)
        except live_events.LiveEventError:
            pass
        else:
            raise AssertionError("provider failure returned a fake event")


def test_live_api_requires_auth_and_preserves_source(monkeypatch, settings):
    client = TestClient(create_app(settings.with_overrides(llm_api_key="")))
    assert client.get("/live/events?q=concert").status_code == 401
    token = client.post("/auth/login", json={"username": "demo1", "password": "momo2026"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    monkeypatch.setattr(live_events, "search", lambda q, city_id: {
        "source": "Ticketbox MCP", "checked_at": "2026-11-25T09:00:00+00:00", "results": [],
        "has_more": False, "notice": "Nguồn Ticketbox",
    })
    result = client.get("/live/events?q=L%E1%BB%9Di+Th%E1%BB%81+Bi%E1%BB%83n+Xanh", headers=headers)
    assert result.status_code == 200 and result.json()["results"] == []
    assert result.headers["cache-control"] == "no-store"
    assert client.get("/live/events?city_id=999", headers=headers).status_code == 422
