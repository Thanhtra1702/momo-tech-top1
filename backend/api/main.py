"""FastAPI endpoints for search, explainable risk, and simulated checkout."""

from __future__ import annotations

import os
import re
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.data.repository import CatalogRepository
from backend.risk.engine import score_listing

app = FastAPI(
    title="MoMo Safe Shopping Demo API",
    version="0.1.0",
    description="Demo API backed by synthetic catalog data. No real merchants or payments are involved.",
)
repo = CatalogRepository()
_lock = threading.Lock()
_requests: dict[str, list[float]] = defaultdict(list)
_daily_spend: dict[str, float] = defaultdict(float)
_day_key = datetime.now(timezone.utc).date().isoformat()
RATE_LIMIT = max(1, int(os.getenv("MOMO_RATE_LIMIT_PER_MINUTE", "30")))
DAILY_BUDGET_VND = max(0, int(os.getenv("MOMO_DAILY_BUDGET_VND", "100000")))
BYTE_LIMIT = 1_000_000


class DraftRequest(BaseModel):
    listing_id: str = Field(min_length=1, max_length=64)


class ConfirmRequest(BaseModel):
    second_confirmation: bool = False


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    url: str | None = Field(default=None, max_length=2048)


def _enforce_daily_budget() -> None:
    """Reserve a small synthetic per-request cost for future LLM integration."""
    global _day_key
    today = datetime.now(timezone.utc).date().isoformat()
    with _lock:
        if today != _day_key:
            _daily_spend.clear()
            _day_key = today
        if _daily_spend["demo"] + 100 > DAILY_BUDGET_VND:
            raise HTTPException(status_code=429, detail="Hệ thống đã chạm hạn mức xử lý hôm nay. Vui lòng thử lại sau.")
        _daily_spend["demo"] += 100


@app.middleware("http")
async def abuse_guards(request: Request, call_next):
    if int(request.headers.get("content-length", "0") or 0) > BYTE_LIMIT:
        return JSONResponse(status_code=413, content={"detail": "Request body is too large."})
    if request.url.path != "/health":
        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        with _lock:
            recent = [t for t in _requests[client] if now - t < 60]
            if len(recent) >= RATE_LIMIT:
                return JSONResponse(status_code=429, content={"detail": "Bạn gửi yêu cầu quá nhanh. Vui lòng đợi một chút."})
            recent.append(now)
            _requests[client] = recent
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok", "mode": "synthetic_demo"}


@app.get("/listings/search")
def search_products(query: str = "", max_price: int | None = None, category: str | None = None, limit: int = 20):
    _enforce_daily_budget()
    limit = min(max(limit, 1), 50)
    q = query.strip().casefold()
    results = []
    catalog = repo.all_listings()
    for item in catalog:
        if category and item["category"] != category:
            continue
        if max_price is not None and item["price_vnd"] > max_price:
            continue
        searchable = f"{item['product_name']} {item['category']} {item['description']}".casefold()
        if q and not all(token in searchable for token in q.split()):
            continue
        risk = score_listing(item, catalog)
        results.append({**item, "risk": risk})
    results.sort(key=lambda x: (x["risk"]["score"] >= 80, x["risk"]["score"], x["price_vnd"]))
    return {"synthetic_data": True, "count": min(len(results), limit), "items": results[:limit]}


@app.get("/listings/{listing_id}/risk")
def get_risk(listing_id: str):
    _enforce_daily_budget()
    listing = repo.listing(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin đăng.")
    return {"listing_id": listing_id, **score_listing(listing, repo.all_listings()), "synthetic_data": True}


@app.post("/orders/draft", status_code=201)
def create_order_draft(body: DraftRequest):
    _enforce_daily_budget()
    listing = repo.listing(body.listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin đăng.")
    risk = score_listing(listing, repo.all_listings())
    if risk["level"] == "very_high":
        raise HTTPException(status_code=409, detail={"message": "Tin đăng có nhiều dấu hiệu rủi ro nên không thể tạo đơn nháp.", "risk": risk})
    order = {
        "id": f"ord_{uuid.uuid4().hex[:12]}",
        "listing_id": listing["id"],
        "status": "draft",
        "second_confirmation": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "synthetic_data": True,
        "simulated_payment": True,
        "listing": listing,
        "risk": risk,
        "payee_matches_seller": listing["payee_name"].casefold() in listing["seller_name"].casefold(),
    }
    repo.create_order(order)
    return order


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    _enforce_daily_budget()
    order = repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")
    return order


@app.post("/orders/{order_id}/confirm")
def confirm_order(order_id: str, body: ConfirmRequest):
    _enforce_daily_budget()
    order = repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Không tìm thấy đơn hàng.")
    if order["status"] != "draft":
        raise HTTPException(status_code=409, detail="Đơn hàng không còn ở trạng thái nháp.")
    if order["risk"]["level"] == "very_high":
        raise HTTPException(status_code=409, detail="Đơn có mức rủi ro rất cao và đã bị chặn.")
    if order["risk"]["level"] == "high" and not body.second_confirmation:
        raise HTTPException(status_code=409, detail={"message": "Cần xác nhận lần hai sau khi xem cảnh báo rủi ro.", "requires_second_confirmation": True})
    order["second_confirmation"] = bool(body.second_confirmation)
    order["status"] = "simulated_paid"
    order["confirmed_at"] = datetime.now(timezone.utc).isoformat()
    repo.update_order(order)
    return {**order, "message": "Thanh toán mô phỏng hoàn tất do người dùng xác nhận."}


@app.post("/risk/analyze-message")
def analyze_message(body: AnalyzeRequest):
    _enforce_daily_budget()
    text = body.text
    lowered = text.casefold()
    signals: list[dict[str, str]] = []
    patterns = [
        (r"chuyển khoản.{0,30}(ngoài|riêng)|ngoài nền tảng", "off_platform_payment", "Đề nghị thanh toán ngoài nền tảng."),
        (r"đặt cọc|cọc trước|chuyển cọc", "deposit_request", "Yêu cầu đặt cọc trước."),
        (r"gấp|chốt ngay|chỉ hôm nay|nhanh tay", "urgency", "Ngôn ngữ thúc giục quyết định nhanh."),
        (r"mật khẩu|mã otp|mã xác thực", "credential_request", "Yêu cầu thông tin xác thực nhạy cảm."),
    ]
    for pattern, code, message in patterns:
        if re.search(pattern, lowered, re.I):
            signals.append({"code": code, "message": message})
    suspicious_domains = []
    urls = re.findall(r"https?://[^\s<>()]+", " ".join([text, body.url or ""]))
    for raw in urls[:10]:
        host = (urlparse(raw).hostname or "").casefold().rstrip(".")
        if host and (host.startswith("xn--") or any(c.isdigit() for c in host.split(".")[0]) or host.count("-") >= 3):
            suspicious_domains.append(host)
            signals.append({"code": "unusual_domain", "message": f"Tên miền có đặc điểm bất thường: {host}. Hãy tự kiểm tra trước khi mở."})
    score = min(100, sum({"off_platform_payment": 30, "deposit_request": 20, "urgency": 10, "credential_request": 35, "unusual_domain": 25}.get(x["code"], 0) for x in signals))
    level = "very_high" if score >= 80 else "high" if score >= 55 else "medium" if score >= 25 else "low"
    return {"score": score, "level": level, "signals": signals, "domains_to_review": sorted(set(suspicious_domains)), "fetched_url": False, "notice": "Phân tích heuristic trên văn bản; hệ thống không mở URL và không kết luận người bán lừa đảo."}\n