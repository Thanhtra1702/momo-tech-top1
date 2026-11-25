"""Đánh giá dấu hiệu giả mạo tài khoản từ dữ liệu người dùng cung cấp.

Không truy cập nền tảng bên ngoài và không xác thực danh tính chủ tài khoản.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from . import scamcheck

BRANDS = {
    "traveloka": "Traveloka",
    "agoda": "Agoda",
    "momo": "MoMo",
    "booking.com": "Booking.com",
}


def _claimed_brand(name: str) -> str | None:
    folded = scamcheck.fold(name)
    for key, label in BRANDS.items():
        if re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])", folded):
            return label
    return None


def check_account(account_name: str, profile_url: str = "", message: str = "") -> dict:
    """Return an unverified identity assessment plus a deterministic risk block."""
    name, profile_url, message = account_name.strip(), profile_url.strip(), message.strip()
    if not name:
        raise ValueError("Cần nhập tên tài khoản cần kiểm tra")
    if profile_url:
        parsed = urlparse(profile_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("Link hồ sơ phải là URL http hoặc https hợp lệ")

    report = scamcheck.check("\n".join(part for part in (profile_url, message) if part)) if message or profile_url else {
        "score": 0, "signals": [], "urls": [], "advice": [],
    }
    brand = _claimed_brand(name)
    if brand:
        report["signals"].insert(0, {
            "code": "unverified_brand_account",
            "label": f"Tài khoản tự nhận là {brand}; tên và ảnh đại diện không xác minh được danh tính",
            "severity": "medium", "evidence": name[:60],
        })
        report["score"] = min(100, report["score"] + 25)

    # A matching domain proves only the URL's hostname, never who controls this account.
    report["level"], report["headline"] = next(
        (level, headline) for threshold, level, headline in scamcheck.LEVELS if report["score"] >= threshold
    )
    report["headline"] = "Chưa xác minh danh tính tài khoản. " + report["headline"]
    report["advice"] = [
        "Tự mở ứng dụng hoặc trang chính thức và liên hệ hỗ trợ từ trong ứng dụng để đối chiếu tài khoản/đơn đặt chỗ.",
        *scamcheck.ADVICE[report["level"]],
    ]
    return {"account_name": name, "identity_status": "unverified", "report": scamcheck.risk_block(report)}
