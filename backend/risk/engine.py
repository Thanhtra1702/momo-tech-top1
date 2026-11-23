"""Rule-based risk score. Numbers and levels are never supplied by an LLM."""

from __future__ import annotations

import json
import re
from pathlib import Path
from statistics import median
from typing import Any

CONFIG_PATH = Path(__file__).with_name("weights.json")
URGENCY_RE = re.compile(r"gấp|chốt ngay|chỉ hôm nay|đặt cọc ngay|sắp hết|nhanh tay", re.I)


def score_listing(listing: dict[str, Any], catalog: list[dict[str, Any]], config_path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    weights = config["weights"]
    peer_prices = [int(x["price_vnd"]) for x in catalog if x["product_id"] == listing["product_id"]]
    peer_median = median(peer_prices) if peer_prices else int(listing["price_vnd"])
    score = 0
    reasons: list[dict[str, str]] = []

    def add(code: str, message: str) -> None:
        nonlocal score
        score += int(weights[code])
        reasons.append({"code": code, "message": message})

    ratio = int(listing["price_vnd"]) / max(1, peer_median)
    if ratio <= 0.65:
        add("price_below_median_35pct", "Giá thấp hơn đáng kể so với trung vị các tin cùng sản phẩm.")
    elif ratio <= 0.8:
        add("price_below_median_20pct", "Giá thấp hơn mặt bằng các tin cùng sản phẩm.")
    if int(listing["seller_age_days"]) < 30:
        add("seller_younger_30_days", "Tài khoản người bán còn mới.")
    elif int(listing["seller_age_days"]) < 90:
        add("seller_younger_90_days", "Tài khoản người bán có lịch sử hoạt động ngắn.")
    if int(listing["completed_orders"]) < 10:
        add("seller_low_order_count", "Người bán có ít đơn hoàn tất được ghi nhận.")
    if float(listing["rating"]) < 3.8:
        add("seller_low_rating", "Điểm đánh giá trung bình thấp.")
    if listing.get("repetitive_reviews"):
        add("repetitive_reviews", "Đánh giá có dấu hiệu lặp mẫu.")
    if listing.get("payment_channel") == "off_platform_transfer":
        add("off_platform_payment", "Tin đăng đề nghị chuyển khoản ngoài nền tảng.")
    if str(listing.get("payee_name", "")).casefold() not in str(listing.get("seller_name", "")).casefold():
        add("payee_name_mismatch", "Tên người nhận không khớp tên cửa hàng đã hiển thị.")
    if URGENCY_RE.search(str(listing.get("description", ""))):
        add("urgency_language", "Nội dung có từ ngữ thúc giục quyết định nhanh.")

    score = min(100, score)
    thresholds = config["thresholds"]
    if score >= thresholds["very_high"]:
        level = "very_high"
    elif score >= thresholds["high"]:
        level = "high"
    elif score >= thresholds["medium"]:
        level = "medium"
    else:
        level = "low"
    return {"score": score, "level": level, "reasons": reasons, "price_reference_vnd": int(peer_median), "engine_version": config["version"]}
