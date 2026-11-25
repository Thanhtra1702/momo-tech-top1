import base64
import json

import pytest
from fastapi.testclient import TestClient

from app import catalog
from app.llm import AssistantTurn, ConfigError, FakeLLMClient, LLMError
from app.main import create_app
from app.samples import SAMPLE_PROMPTS

from .helpers import call, parse_sse, text_turn, tool_turn, validator

SID = "session-0001"
PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 32).decode()


def make(settings, llm=None, **over):
    s = settings.with_overrides(**over) if over else settings
    app = create_app(s, llm_factory=(lambda: llm) if llm is not None else None)
    return TestClient(app), app


def login(client, user="demo1", password="momo2026") -> dict:
    r = client.post("/auth/login", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def chat(client, headers, message="xin chào", **extra):
    body = {"message": message, "session_id": SID, **extra}
    return client.post("/chat", json=body, headers=headers)


def test_health_and_samples(settings):
    c, _ = make(settings)
    assert c.get("/health").json() == {"status": "ok"}
    assert c.get("/samples").json() == {"prompts": SAMPLE_PROMPTS, "images": True}
    assert c.get("/health").headers["x-content-type-options"] == "nosniff"


def test_login_success_failure_and_protected_routes(settings):
    c, _ = make(settings)
    assert c.post("/chat", json={"message": "hi", "session_id": SID}).status_code == 401
    assert c.get("/orders/ord_x").status_code == 401
    assert c.get("/memory").status_code == 401
    bad = c.post("/auth/login", json={"username": "demo1", "password": "sai"})
    assert bad.status_code == 401 and "Sai tên" in bad.json()["detail"]
    assert c.post("/auth/login", json={"username": "ghost", "password": "x"}).status_code == 401
    h = login(c)
    assert c.get("/auth/me", headers=h).json() == {"username": "demo1"}
    assert c.get("/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_login_is_throttled(settings):
    c, _ = make(settings)
    codes = [c.post("/auth/login", json={"username": "demo1", "password": "x"}).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10 and 429 in codes[10:]


def test_chat_streams_sse_in_contract_format(settings):
    llm = FakeLLMClient([tool_turn(call("search_events", {"kind": "concert", "city": "Hà Nội"})), text_turn("Gợi ý cho bạn")])
    c, _ = make(settings, llm)
    r = chat(c, login(c), "tìm concert ở Hà Nội")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    v = validator("sse_event")
    assert all(not list(v.iter_errors(e)) for e in events)
    assert [e["type"] for e in events][-1] == "done" and any(e["type"] == "ui_block" for e in events)


def test_chat_validation(settings):
    llm = FakeLLMClient(reply="ok")
    c, _ = make(settings, llm)
    h = login(c)
    assert chat(c, h, "").status_code == 422
    assert c.post("/chat", json={"message": "hi", "session_id": "bad id!!"}, headers=h).status_code == 422
    assert chat(c, h, "x" * 2001).status_code == 422
    assert c.post("/chat", json={"message": "hi", "session_id": SID, "mode": "turbo"}, headers=h).status_code == 422


def test_missing_api_key_gives_clear_503(settings):
    app = create_app(settings.with_overrides(llm_api_key=""), llm_factory=lambda: (_ for _ in ()).throw(ConfigError("Thiếu LLM_API_KEY. x")))
    c = TestClient(app)
    r = chat(c, login(c))
    assert r.status_code == 503 and "LLM_API_KEY" in r.json()["detail"]


def test_llm_failure_is_friendly_in_stream(settings):
    class Broken:
        def stream(self, *a, **k):
            raise LLMError("secret-detail")
            yield

    c, _ = make(settings, Broken())
    r = chat(c, login(c))
    events = parse_sse(r.text)
    assert events[0]["type"] == "error" and "secret" not in r.text and events[-1]["type"] == "done"


def test_image_validation_and_passthrough(settings):
    llm = FakeLLMClient(reply="Đây là một địa điểm")
    c, _ = make(settings, llm)
    h = login(c)
    assert chat(c, h, "đây là đâu", image={"mime": "image/png", "data": PNG}).status_code == 200
    sent = llm.calls[0]["messages"][-1]["content"]
    assert sent[1]["image_url"]["url"].startswith("data:image/png;base64,")
    for bad in ({"mime": "image/gif", "data": PNG}, {"mime": "image/jpeg", "data": PNG},
                {"mime": "image/png", "data": "!!!"}, {"mime": "image/png", "data": base64.b64encode(b"x" * 10).decode()},
                {"mime": "image/png", "data": base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)).decode()}):
        assert chat(c, h, "x", image=bad).status_code == 422
    assert chat(c, h, "", image={"mime": "image/png", "data": PNG}).status_code == 200  # chỉ gửi ảnh


def test_conversation_is_saved_restored_and_survives_restart(settings):
    llm = FakeLLMClient([tool_turn(call("search_events", {"kind": "concert", "city": "Hà Nội"})), text_turn("Gợi ý concert"),
                         text_turn("Ok lượt hai")])
    c, _ = make(settings, llm)
    h = login(c)
    assert c.get("/conversations/latest", headers=h).json() == {"session_id": None, "messages": []}
    chat(c, h, "tìm concert ở Hà Nội")
    saved = c.get("/conversations/latest", headers=h).json()
    assert saved["session_id"] == SID
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant"]
    assert saved["messages"][1]["text"] == "Gợi ý concert" and saved["messages"][1]["blocks"][0]["kind"] == "ticket_cards"
    assert c.get("/conversations/latest", headers=login(c, "demo2")).json()["session_id"] is None  # không lộ sang người khác

    # "khởi động lại": ứng dụng mới trên cùng DB, bộ nhớ trong trống
    llm2 = FakeLLMClient(reply="Ok lượt hai")
    c2, app2 = make(settings, llm2)
    h2 = login(c2)
    chat(c2, h2, "cảm ơn")
    sent = json.dumps(llm2.calls[0]["messages"], ensure_ascii=False)
    assert "tìm concert ở Hà Nội" in sent and "Gợi ý concert" in sent  # lịch sử được nạp lại
    assert len(c2.get("/conversations/latest", headers=h2).json()["messages"]) == 4


def test_saved_conversation_never_contains_image_data(settings):
    c, _ = make(settings, FakeLLMClient(reply="Đây là hồ"))
    h = login(c)
    chat(c, h, "đây là đâu", image={"mime": "image/png", "data": PNG})
    msgs = c.get("/conversations/latest", headers=h).json()["messages"]
    assert msgs[0].get("has_image") is True and PNG not in json.dumps(msgs)
    with c.app.state.s.db.conn() as conn:
        assert all(PNG not in r[0] for r in conn.execute("SELECT history || display FROM conversations"))


def test_images_can_be_disabled(settings):
    c, _ = make(settings, FakeLLMClient(reply="ok"), images_enabled=False)
    assert c.get("/samples").json()["images"] is False
    r = chat(c, login(c), "đây là đâu", image={"mime": "image/png", "data": PNG})
    assert r.status_code == 422 and "tắt" in r.json()["detail"]
    assert chat(c, login(c), "xin chào").status_code == 200


def test_rate_limit(settings):
    c, _ = make(settings, FakeLLMClient(reply="ok"), rate_limit_per_min=3)
    h = login(c)
    codes = [chat(c, h).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    assert "quá nhanh" in chat(c, h).json()["detail"]


def test_cost_cap_blocks_and_usage_is_reported(settings):
    llm = FakeLLMClient([AssistantTurn(text="a", prompt_tokens=1_000_000, completion_tokens=1_000_000)])
    c, app = make(settings, llm, user_daily_cost_cap_usd=1.0, admin_token="adm")
    h = login(c)
    assert chat(c, h).status_code == 200  # 1.5 USD ước tính, vượt trần người dùng
    blocked = chat(c, h)
    assert blocked.status_code == 429 and "hạn mức" in blocked.json()["detail"]
    other = chat(c, login(c, "demo2"))  # người dùng khác chưa chạm trần
    assert other.status_code == 200
    assert c.get("/usage", headers=h).json()["spent_usd"] > 1.0
    assert c.get("/admin/costs").status_code == 404
    report = c.get("/admin/costs", headers={"X-Admin-Token": "adm"}).json()
    assert {u["username"] for u in report["by_user"]} == {"demo1", "demo2"}


def test_global_cost_cap(settings):
    llm = FakeLLMClient([AssistantTurn(text="a", prompt_tokens=1_000_000, completion_tokens=0)])
    c, _ = make(settings, llm, daily_cost_cap_usd=0.2, user_daily_cost_cap_usd=9)
    assert chat(c, login(c)).status_code == 200
    r = chat(c, login(c, "demo2"))
    assert r.status_code == 429 and "ngày mai" in r.json()["detail"]


def test_sample_prompts_are_cached_without_calling_llm_again(settings):
    sample = SAMPLE_PROMPTS[0]
    llm = FakeLLMClient([tool_turn(call("search_events", {"kind": "movie", "city": "Sài Gòn"})), text_turn("Gợi ý")])
    c, _ = make(settings, llm)
    first = chat(c, login(c, "demo1"), sample)
    second_client_headers = login(c, "demo2")
    second = c.post("/chat", json={"message": sample, "session_id": "session-0002"}, headers=second_client_headers)
    assert len(llm.calls) == 2  # lần 2 không gọi thêm LLM
    ev1, ev2 = parse_sse(first.text), parse_sse(second.text)
    assert [e for e in ev1 if e["type"] != "done"] == [e for e in ev2 if e["type"] != "done"]
    assert ev2[-1]["usage"]["cost_usd"] == 0.0
    # hội thoại tiếp tục được sau khi phát lại từ cache
    follow = c.post("/chat", json={"message": "cảm ơn", "session_id": "session-0002"}, headers=second_client_headers)
    assert follow.status_code == 200
    assert "Gợi ý" in json.dumps(llm.calls[-1]["messages"], ensure_ascii=False)


def test_non_sample_and_personalized_requests_are_not_cached(settings):
    llm = FakeLLMClient(reply="ok")
    c, _ = make(settings, llm)
    h = login(c)
    chat(c, h, "một câu bất kỳ")
    chat(c, h, "một câu bất kỳ", )
    assert len(llm.calls) == 2


def test_orders_end_to_end_with_user_confirmation_only(settings):
    f = None
    llm = FakeLLMClient()
    c, app = make(settings, llm)
    h = login(c)
    f = catalog.search_transport(app.state.s.db, origin="Hà Nội", destination="Đà Nẵng", mode="flight", limit=1)[0]
    llm._script = [tool_turn(call("create_order_draft", {"items": [{"ref_id": f["id"], "quantity": 2}]})), text_turn("Đã tạo đơn nháp")]
    events = parse_sse(chat(c, h, f"Đặt giúp mình {f['id']} 2 vé").text)
    oid = next(e["block"]["order_id"] for e in events if e["type"] == "ui_block")
    order = c.get("/orders/" + oid, headers=h).json()
    assert order["status"] == "draft" and order["total_vnd"] == f["price_vnd"] * 2
    assert not list(validator("order_draft").iter_errors(order))
    assert c.get("/orders/" + oid, headers=login(c, "demo2")).status_code == 404
    assert c.post(f"/orders/{oid}/confirm", headers=login(c, "demo2")).status_code == 404
    done = c.post(f"/orders/{oid}/confirm", headers=h)
    assert done.status_code == 200 and done.json()["status"] == "confirmed"
    assert c.get("/orders/ord_missing", headers=h).status_code == 404


def test_orders_list_endpoint_is_private_and_includes_upcoming(settings):
    c, app = make(settings, FakeLLMClient())
    h1, h2 = login(c, "demo1"), login(c, "demo2")
    from app import orders as orders_mod
    db = app.state.s.db
    f = catalog.search_transport(db, origin="Hà Nội", destination="Huế", limit=1)[0]
    d = orders_mod.create_draft(db, "demo1", [{"ref_id": f["id"], "quantity": 1}])
    orders_mod.create_draft(db, "demo1", [{"ref_id": f["id"], "quantity": 1}])
    assert c.get("/orders").status_code == 401
    before = c.get("/orders", headers=h1).json()
    assert len(before["orders"]) == 2 and before["upcoming"] == []  # đơn nháp chưa tính là sắp tới
    assert c.post(f"/orders/{d['id']}/confirm", headers=h1).status_code == 200
    after = c.get("/orders", headers=h1).json()
    assert len(after["upcoming"]) == 1 and after["upcoming"][0]["order_id"] == d["id"]
    assert c.get("/orders", headers=h2).json() == {"orders": [], "upcoming": []}
    assert c.get("/orders", headers=h1).headers["cache-control"] == "no-store"


def test_confirm_conflict_returns_409(settings):
    c, app = make(settings, FakeLLMClient())
    h = login(c)
    from app import orders
    f = catalog.search_transport(app.state.s.db, origin="Hà Nội", destination="Huế", limit=1)[0]
    d = orders.create_draft(app.state.s.db, "demo1", [{"ref_id": f["id"], "quantity": 1}])
    with app.state.s.db.conn() as conn:
        conn.execute("UPDATE transport SET seats_left = 0 WHERE id = ?", (f["id"],))
    r = c.post(f"/orders/{d['id']}/confirm", headers=h)
    assert r.status_code == 409 and "hết chỗ" in r.json()["detail"]


def test_memory_endpoints(settings):
    c, _ = make(settings, FakeLLMClient())
    h1, h2 = login(c, "demo1"), login(c, "demo2")
    assert c.put("/memory", json={"key": "home_city", "value": "Hà Nội"}, headers=h1).status_code == 200
    assert c.put("/memory", json={"key": "interests", "value": "0912345678"}, headers=h1).status_code == 422
    assert c.put("/memory", json={"key": "bad", "value": "x"}, headers=h1).status_code == 422
    assert c.get("/memory", headers=h1).json()["memory"] == {"home_city": "Hà Nội"}
    assert c.get("/memory", headers=h2).json()["memory"] == {}
    assert c.delete("/memory/home_city", headers=h1).json()["memory"] == {}
    assert c.delete("/memory/home_city", headers=h1).status_code == 404
    c.put("/memory", json={"key": "interests", "value": "phim"}, headers=h1)
    assert c.delete("/memory", headers=h1).json() == {"memory": {}}


def test_memory_saved_via_chat_applies_next_session(settings):
    llm = FakeLLMClient([tool_turn(call("save_preference", {"key": "home_city", "value": "Hà Nội"})), text_turn("Đã nhớ"),
                         text_turn("ok")])
    c, _ = make(settings, llm)
    h = login(c)
    chat(c, h, "tôi hay đi từ Hà Nội, nhớ giúp nhé")
    c.post("/chat", json={"message": "tìm vé đi Huế", "session_id": "session-0002"}, headers=h)
    assert "Hà Nội" in llm.calls[-1]["messages"][0]["content"]


def test_concurrent_turn_on_same_session_is_rejected(settings):
    c, app = make(settings, FakeLLMClient(reply="ok"))
    h = login(c)
    sess = app.state.s.sessions.get("demo1", SID)
    assert sess.lock.acquire(blocking=False)
    try:
        assert chat(c, h).status_code == 409
    finally:
        sess.lock.release()
    assert chat(c, h).status_code == 200


def test_wrong_frontend_dir_falls_back_to_autodetect(settings, tmp_path):
    from app.config import resolve_frontend_dir

    (tmp_path / "ok").mkdir()
    (tmp_path / "ok" / "index.html").write_text("<html>x</html>", encoding="utf-8")
    assert resolve_frontend_dir(str(tmp_path / "ok")) == tmp_path / "ok"
    found = resolve_frontend_dir("duong-dan-khong-ton-tai")
    assert found is None or (found / "index.html").is_file()  # sai đường dẫn thì dò tiếp, không làm mất giao diện
    built = resolve_frontend_dir("")
    if built:  # đã build frontend trên máy này: cấu hình sai vẫn phục vụ được giao diện
        c, _ = make(settings, None, frontend_dir="duong-dan-khong-ton-tai")
        assert 'id="root"' in c.get("/").text


def test_serves_frontend_when_built(settings, tmp_path):
    (tmp_path / "web" / "assets").mkdir(parents=True)
    (tmp_path / "web" / "index.html").write_text("<html>app</html>", encoding="utf-8")
    (tmp_path / "web" / "assets" / "a.js").write_text("1", encoding="utf-8")
    c, _ = make(settings, None, frontend_dir=str(tmp_path / "web"))
    assert c.get("/").text == "<html>app</html>" and c.get("/assets/a.js").status_code == 200
