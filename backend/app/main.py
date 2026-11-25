from __future__ import annotations

import hmac
import json
import logging
import threading
import time
from pathlib import Path
from typing import Callable, Iterator, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import accountcheck, auth, convstore, live_events, memory, orders
from agents.orchestrator import SESSION_ID_PATTERN, AgentDeps, SessionStore, run_turn
from .config import Settings, resolve_frontend_dir
from .db import Database
from .images import MAX_B64_CHARS, ImageError, to_data_url
from .limits import CostGuard, LimitError, RateLimiter
from .llm import ChatClient, ConfigError, LLMClient, estimate_cost
from .samples import SAMPLE_PROMPTS
from .seed import ensure_seeded
from .textutil import norm

log = logging.getLogger("momo.app")
CACHE_TTL_S = 3600
_SAMPLE_KEYS = {norm(s) for s in SAMPLE_PROMPTS}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ImagePayload(BaseModel):
    mime: str = Field(max_length=32)
    data: str = Field(max_length=MAX_B64_CHARS)


class ChatRequest(BaseModel):
    message: str = Field(default="", max_length=2000)
    mode: Literal["fast", "deep"] = "fast"
    session_id: str = Field(min_length=8, max_length=64)
    image: ImagePayload | None = None


class MemoryItem(BaseModel):
    key: str = Field(max_length=40)
    value: str = Field(max_length=300)


class AccountCheckRequest(BaseModel):
    account_name: str = Field(min_length=1, max_length=120)
    profile_url: str = Field(default="", max_length=500)
    message: str = Field(default="", max_length=4000)


def sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


class State:
    def __init__(self, settings: Settings, llm_factory: Callable[[], ChatClient] | None):
        self.settings = settings
        self.db = Database(settings.db_path)
        ensure_seeded(self.db)
        auth.ensure_demo_users(self.db, settings)
        self.sessions = SessionStore(loader=lambda u, s: convstore.load(self.db, u, s))
        self.rate = RateLimiter(settings.rate_limit_per_min)
        self.login_rate = RateLimiter(10, 300)
        self.cost = CostGuard(self.db, settings)
        self.cache: dict[tuple[str, str], tuple[float, list[dict], list[dict], set[str]]] = {}
        self._factory = llm_factory
        self._llm: ChatClient | None = None
        self._lock = threading.Lock()
        self._last_seed_check = time.time()

    def refresh_catalog_if_due(self, every_s: int = 3600) -> None:
        """Máy chủ chạy nhiều ngày: danh mục mô phỏng chỉ có 45 ngày phía trước, nên sinh lại khi sắp hết."""
        with self._lock:
            if time.time() - self._last_seed_check < every_s:
                return
            self._last_seed_check = time.time()
        try:
            if ensure_seeded(self.db):
                log.info("đã sinh lại danh mục mô phỏng")
        except Exception:
            log.exception("không làm mới được danh mục")

    def llm(self) -> ChatClient:
        with self._lock:
            if self._llm is None:
                self._llm = self._factory() if self._factory else LLMClient(self.settings)
            return self._llm


def create_app(settings: Settings | None = None, llm_factory: Callable[[], ChatClient] | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if settings.app_env == "production":
        problems = settings.production_problems()
        if problems:
            raise RuntimeError("Cấu hình chưa an toàn để chạy thật (APP_ENV=production): " + "; ".join(problems))
    state = State(settings, llm_factory)
    app = FastAPI(title="Momo Travel Assistant", docs_url=None, redoc_url=None)
    app.state.s = state

    csp = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; connect-src 'self'; "
           "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Content-Security-Policy", csp)
        if request.url.path.startswith(("/auth", "/orders", "/memory", "/conversations", "/usage", "/admin", "/risk", "/live")):
            resp.headers.setdefault("Cache-Control", "no-store")  # dữ liệu cá nhân không được cache
        return resp

    @app.exception_handler(LimitError)
    async def limit_handler(_: Request, exc: LimitError):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    def current_user(authorization: str | None = Header(default=None)) -> str:
        token = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else ""
        user = auth.user_for_token(state.db, token) if token else None
        if not user:
            raise HTTPException(status_code=401, detail="Bạn cần đăng nhập.")
        return user

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/samples")
    def samples() -> dict:
        return {"prompts": SAMPLE_PROMPTS, "images": settings.images_enabled}

    @app.get("/live/events")
    def live_event_search(q: str = Query(default="", max_length=120), city_id: int | None = Query(default=None),
                          user: str = Depends(current_user)) -> dict:
        if city_id not in (None, 1, 68, 79):
            raise HTTPException(status_code=422, detail="Thành phố chưa được hỗ trợ trong tra cứu live.")
        state.rate.check(user)
        try:
            return live_events.search(q, city_id)
        except live_events.LiveEventError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    # --- tài khoản ---
    @app.post("/auth/login")
    def login(req: LoginRequest, request: Request) -> dict:
        ip = request.client.host if request.client else "?"
        state.login_rate.check(f"ip:{ip}")
        state.login_rate.check(f"user:{req.username.lower()}")
        token = auth.login(state.db, settings, req.username, req.password)
        if not token:
            raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu.")
        return {"token": token, "username": req.username}

    @app.get("/auth/me")
    def me(user: str = Depends(current_user)) -> dict:
        return {"username": user}

    @app.get("/usage")
    def usage(user: str = Depends(current_user)) -> dict:
        return {"spent_usd": round(state.cost.spent(user), 6), "cap_usd": settings.user_daily_cost_cap_usd}

    @app.post("/risk/account-check")
    def check_account(req: AccountCheckRequest, user: str = Depends(current_user)) -> dict:
        state.rate.check(user)
        try:
            return accountcheck.check_account(req.account_name, req.profile_url, req.message)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/admin/costs")
    def admin_costs(x_admin_token: str | None = Header(default=None)) -> dict:
        if not settings.admin_token or not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
            raise HTTPException(status_code=404, detail="Không tìm thấy.")
        return state.cost.report()

    # --- chat (SSE) ---
    @app.post("/chat")
    def chat(req: ChatRequest, user: str = Depends(current_user)) -> StreamingResponse:
        if not SESSION_ID_PATTERN.match(req.session_id):
            raise HTTPException(status_code=422, detail="session_id không hợp lệ.")
        text = req.message.strip()
        if not text and not req.image:
            raise HTTPException(status_code=422, detail="Tin nhắn không được để trống.")
        image_url = None
        if req.image:
            if not settings.images_enabled:
                raise HTTPException(status_code=422, detail="Tính năng gửi ảnh đang tắt.")
            try:
                image_url = to_data_url(req.image.mime, req.image.data)
            except ImageError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        state.rate.check(user)
        state.cost.check(user)
        state.refresh_catalog_if_due()
        try:
            llm = state.llm()
        except ConfigError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        session = state.sessions.get(user, req.session_id)
        if not session.lock.acquire(blocking=False):
            raise HTTPException(status_code=409, detail="Phiên đang xử lý tin nhắn trước, vui lòng đợi.")

        def stream() -> Iterator[str]:
            try:
                yield from _run(state, llm, session, user, req.session_id, text, req.mode, image_url)
            finally:
                session.lock.release()

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.get("/conversations/latest")
    def latest_conversation(user: str = Depends(current_user)) -> dict:
        found = convstore.latest(state.db, user)
        return {"session_id": found[0], "messages": found[1]} if found else {"session_id": None, "messages": []}

    # --- đơn hàng ---
    def _order_call(fn, *args):
        try:
            return fn(state.db, *args)
        except orders.OrderError as exc:
            status = {"not_found": 404, "invalid": 422, "conflict": 409}[exc.code]
            raise HTTPException(status_code=status, detail=exc.message) from exc

    @app.get("/orders")
    def list_my_orders(user: str = Depends(current_user)) -> dict:
        return {"orders": orders.list_orders(state.db, user), "upcoming": orders.upcoming(state.db, user)}

    @app.get("/orders/{order_id}")
    def get_order(order_id: str, user: str = Depends(current_user)) -> dict:
        return _order_call(orders.get_order, user, order_id)

    @app.post("/orders/{order_id}/confirm")
    def confirm_order(order_id: str, user: str = Depends(current_user)) -> dict:
        return _order_call(orders.confirm, user, order_id)

    # --- bộ nhớ ---
    @app.get("/memory")
    def get_memory(user: str = Depends(current_user)) -> dict:
        return {"memory": memory.recall(state.db, user), "labels": memory.ALLOWED_KEYS}

    @app.put("/memory")
    def put_memory(item: MemoryItem, user: str = Depends(current_user)) -> dict:
        try:
            memory.save(state.db, user, item.key, item.value)
        except memory.MemoryValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"memory": memory.recall(state.db, user)}

    @app.delete("/memory/{key}")
    def delete_memory(key: str, user: str = Depends(current_user)) -> dict:
        if not memory.delete(state.db, user, key):
            raise HTTPException(status_code=404, detail="Không tìm thấy mục này.")
        return {"memory": memory.recall(state.db, user)}

    @app.delete("/memory")
    def clear_memory(user: str = Depends(current_user)) -> dict:
        memory.clear(state.db, user)
        return {"memory": {}}

    _mount_frontend(app, settings.frontend_dir)
    return app


def _persist(state: State, session, user: str, sid: str, text: str, events: list[dict], has_image: bool) -> None:
    """Lưu hội thoại sau mỗi lượt. Lỗi lưu không được làm hỏng phản hồi đã gửi cho người dùng."""
    try:
        session.display.extend(convstore.display_from_events(text, events, has_image))
        del session.display[:-convstore.MAX_DISPLAY]
        convstore.save(state.db, user, sid, session.history, session.seen_refs, session.display)
    except Exception:
        log.exception("không lưu được hội thoại")


def _run(state: State, llm: ChatClient, session, user: str, sid: str, text: str, mode: str,
         image_url: str | None) -> Iterator[str]:
    cache_key = (mode, norm(text))
    cacheable = (image_url is None and norm(text) in _SAMPLE_KEYS and not session.history
                 and not memory.recall(state.db, user))
    if cacheable:
        hit = state.cache.get(cache_key)
        if hit and time.time() - hit[0] < CACHE_TTL_S:
            _, events, history, refs = hit
            session.history.extend(dict(m) for m in history)
            session.seen_refs.update(refs)
            for ev in events:
                yield sse(ev)
            _persist(state, session, user, sid, text, events, False)
            return

    deps = AgentDeps(db=state.db, llm=llm, max_steps=state.settings.max_agent_steps,
                     on_usage=lambda p, c: state.cost.record(user, p, c, estimate_cost(p, c)))
    events: list[dict] = []
    had_error = False
    try:
        for ev in run_turn(deps, session, user, text, mode, image_url):
            if ev["type"] == "error":
                had_error = True
            events.append(ev)
            yield sse(ev)
    except Exception:
        log.exception("agent crashed")
        yield sse({"type": "error", "message": "Có lỗi xảy ra, bạn thử lại nhé."})
        yield sse({"type": "done"})
        return
    _persist(state, session, user, sid, text, events, image_url is not None)
    if cacheable and not had_error and len(session.history) >= 2:
        replay = [e for e in events if e["type"] != "done"] + [{"type": "done", "usage": {
            "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}}]
        state.cache[cache_key] = (time.time(), replay, [dict(m) for m in session.history[-2:]], set(session.seen_refs))


def _mount_frontend(app: FastAPI, frontend_dir: str) -> None:
    root = resolve_frontend_dir(frontend_dir)
    if root is None:
        log.warning("không tìm thấy giao diện đã build (chạy `npm run build` trong frontend/); chỉ có API")
        return
    if frontend_dir and Path(frontend_dir) != root:
        log.warning("FRONTEND_DIR=%s không hợp lệ, dùng %s", frontend_dir, root)
    index = root / "index.html"
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_index() -> FileResponse:
        return FileResponse(index)
