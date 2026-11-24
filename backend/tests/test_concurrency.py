"""Kiểm tra hành vi khi nhiều người dùng cùng lúc: không bán lố chỗ, không khóa DB, không lẫn dữ liệu giữa người dùng."""

import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app import catalog, orders
from app.llm import FakeLLMClient
from app.main import create_app

from .helpers import call, parse_sse, text_turn, tool_turn


def _app(settings, llm_factory):
    return create_app(settings.with_overrides(rate_limit_per_min=1000), llm_factory=llm_factory)


def test_concurrent_confirms_never_oversell(db):
    f = catalog.search_transport(db, origin="Hà Nội", destination="Huế", limit=1)[0]
    with db.conn() as c:
        c.execute("UPDATE transport SET seats_left = 5 WHERE id = ?", (f["id"],))
    drafts = [orders.create_draft(db, f"u{i}", [{"ref_id": f["id"], "quantity": 1}])["id"] for i in range(12)]

    results: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(len(drafts))

    def confirm(i: int):
        barrier.wait()
        try:
            orders.confirm(db, f"u{i}", drafts[i])
            outcome = "ok"
        except orders.OrderError as exc:
            outcome = exc.code
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=confirm, args=(i,)) for i in range(len(drafts))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count("ok") == 5 and results.count("conflict") == 7
    assert catalog.get_item(db, f["id"])[1]["seats_left"] == 0


def test_many_users_chat_at_once_without_errors_or_cross_talk(settings):
    def factory():
        # mỗi yêu cầu gọi công cụ rồi trả lời, đủ để tranh chấp DB (đọc danh mục, ghi hội thoại và chi phí)
        class PerCall(FakeLLMClient):
            def stream(self, messages, tools=None, mode="fast"):
                last = messages[-1]
                if last["role"] == "tool":
                    self._script = [text_turn("Xong")]
                else:
                    self._script = [tool_turn(call("search_events", {"kind": "movie", "city": "Hà Nội"}))]
                yield from super().stream(messages, tools, mode)

        return PerCall()

    app = _app(settings, factory)
    client = TestClient(app)
    users = ["demo1", "demo2", "demo3"]
    tokens = {u: client.post("/auth/login", json={"username": u, "password": "momo2026"}).json()["token"] for u in users}

    def one(i: int):
        u = users[i % 3]
        r = client.post("/chat", json={"message": f"tìm phim số {i}", "session_id": f"load-test-{i:04d}"},
                        headers={"Authorization": f"Bearer {tokens[u]}"})
        return u, i, r.status_code, parse_sse(r.text)

    with ThreadPoolExecutor(max_workers=16) as pool:
        out = list(pool.map(one, range(60)))
    assert all(status == 200 for _, _, status, _ in out)
    assert all(ev[-1]["type"] == "done" and not any(e["type"] == "error" for e in ev) for _, _, _, ev in out)
    # hội thoại lưu đúng người, đúng nội dung, không lẫn
    db = app.state.s.db
    with db.conn() as c:
        rows = c.execute("SELECT username, session_id, display FROM conversations").fetchall()
    assert len(rows) == 60
    for r in rows:
        i = int(r["session_id"].split("-")[-1])
        assert r["username"] == users[i % 3] and f"tìm phim số {i}" in r["display"]
    with db.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM cost_log").fetchone()[0] >= 60


# --- cấu hình chạy thật, header bảo mật, làm mới danh mục, giữ kết nối khi mô hình nghĩ lâu ---
import pytest  # noqa: E402

from app.agent import AgentDeps, Session, run_turn  # noqa: E402
from app.config import Settings  # noqa: E402
from app.llm import AssistantTurn  # noqa: E402


def test_production_refuses_default_or_weak_credentials(settings):
    prod = settings.with_overrides(app_env="production")
    with pytest.raises(RuntimeError, match="mật khẩu mặc định"):
        create_app(prod, llm_factory=lambda: FakeLLMClient())
    weak = prod.with_overrides(demo_users="giamkhao:abc")
    with pytest.raises(RuntimeError, match="dưới 8 ký tự"):
        create_app(weak, llm_factory=lambda: FakeLLMClient())
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        create_app(prod.with_overrides(llm_api_key="", demo_users="giamkhao:MatKhau-Manh-123"), llm_factory=lambda: FakeLLMClient())
    ok = prod.with_overrides(demo_users="giamkhao:MatKhau-Manh-123", admin_token="a-long-random-admin-token")
    assert Settings.production_problems(ok) == []
    assert TestClient(create_app(ok, llm_factory=lambda: FakeLLMClient())).get("/health").status_code == 200


def test_development_allows_defaults(settings):
    assert settings.app_env == "development"
    assert TestClient(create_app(settings, llm_factory=lambda: FakeLLMClient())).get("/health").status_code == 200


def test_security_headers_and_no_store_for_private_routes(settings):
    c = TestClient(create_app(settings, llm_factory=lambda: FakeLLMClient()))
    h = c.get("/health").headers
    csp = h["content-security-policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and "'unsafe-inline'" not in csp and "'unsafe-eval'" not in csp
    assert h["x-frame-options"] == "DENY"
    tok = c.post("/auth/login", json={"username": "demo1", "password": "momo2026"})
    assert tok.headers["cache-control"] == "no-store"
    assert "cache-control" not in c.get("/health").headers


def test_catalog_refresh_runs_at_most_hourly_and_only_when_needed(settings, monkeypatch):
    app = create_app(settings, llm_factory=lambda: FakeLLMClient())
    st = app.state.s
    calls = []
    monkeypatch.setattr("app.main.ensure_seeded", lambda db: calls.append(1) or False)
    st.refresh_catalog_if_due()
    assert calls == []  # vừa khởi động, chưa đến hạn
    st._last_seed_check -= 3601
    st.refresh_catalog_if_due()
    st.refresh_catalog_if_due()
    assert calls == [1]


def test_long_thinking_emits_periodic_keepalive_not_a_flood(db, monkeypatch):
    import app.agent as agent

    clock = {"t": 1000.0}
    monkeypatch.setattr(agent.time, "monotonic", lambda: clock["t"])

    class Slow(FakeLLMClient):
        def stream(self, messages, tools=None, mode="fast"):
            from app.llm import ReasoningDelta, TextDelta, TurnEnd
            for _ in range(5):  # 5 đoạn suy luận liên tiếp trong cùng một giây
                yield ReasoningDelta("...")
            clock["t"] += 11  # rồi 11 giây sau, mô hình vẫn đang nghĩ
            yield ReasoningDelta("...")
            yield TextDelta("xong")
            yield TurnEnd(AssistantTurn(text="xong"))

    events = list(run_turn(AgentDeps(db, Slow()), Session(), "demo1", "hi", "deep"))
    assert [e["type"] for e in events if e["type"] == "thinking"] == ["thinking", "thinking"]
