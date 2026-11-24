"""Deterministic, synthetic demo catalog. No records describe real sellers."""

from __future__ import annotations

from typing import Any

PRODUCTS = [
    ("phone-a", "Điện thoại Nova A", "phone", 5_490_000),
    ("phone-b", "Điện thoại Nova B", "phone", 7_990_000),
    ("phone-c", "Điện thoại Pixel Việt", "phone", 11_990_000),
    ("headphones-a", "Tai nghe chống ồn Mây Pro", "audio", 1_890_000),
    ("headphones-b", "Tai nghe không dây Gió 2", "audio", 990_000),
    ("charger-a", "Sạc nhanh 45W Cánh Diều", "accessory", 490_000),
    ("case-a", "Ốp lưng chống sốc Trong Suốt", "accessory", 190_000),
    ("watch-a", "Đồng hồ thông minh Nhịp", "wearable", 2_490_000),
    ("tablet-a", "Máy tính bảng Mầm 10", "tablet", 4_990_000),
    ("keyboard-a", "Bàn phím cơ Gõ Êm", "accessory", 1_290_000),
]

SCAM_TYPES = ("too_cheap", "new_seller", "off_platform_payment", "payee_mismatch", "review_pattern")


def build_catalog(count: int = 300) -> list[dict[str, Any]]:
    """Build a repeatable 22% positive-labeled synthetic dataset."""
    records: list[dict[str, Any]] = []
    for i in range(count):
        product_id, product_name, category, base_price = PRODUCTS[i % len(PRODUCTS)]
        risky = i % 9 in (0, 1)  # 2/9 = 22.2%
        scam_type = SCAM_TYPES[i % len(SCAM_TYPES)] if risky else None
        seller_age = 3 + (i * 17) % 1100
        completed_orders = (i * 13) % 1200
        rating = round(3.4 + ((i * 7) % 16) / 10, 1)
        discount = 0.28 if risky and scam_type == "too_cheap" else 0.04 + (i % 13) / 100
        price = max(50_000, int(base_price * (1 - discount)))
        off_platform = bool(risky and scam_type == "off_platform_payment")
        payee_match = not (risky and scam_type == "payee_mismatch")
        description = f"{product_name}, bảo hành 12 tháng, giao hàng toàn quốc."
        if off_platform:
            description += " Chuyển khoản riêng ngoài nền tảng để được giá tốt."
        if risky and scam_type == "new_seller":
            seller_age = 5 + i % 20
            completed_orders = i % 4
        if risky and scam_type == "review_pattern":
            rating = 5.0
        records.append({
            "id": f"listing-{i + 1:04d}",
            "product_id": product_id,
            "product_name": product_name,
            "category": category,
            "price_vnd": price,
            "seller_id": f"seller-{i % 45 + 1:03d}",
            "seller_name": f"Cửa hàng Demo {i % 45 + 1:03d}",
            "seller_age_days": seller_age,
            "completed_orders": completed_orders,
            "rating": rating,
            "review_count": 3 + (i * 11) % 240,
            "repetitive_reviews": bool(risky and scam_type == "review_pattern"),
            "payment_channel": "off_platform_transfer" if off_platform else "platform_escrow",
            "payee_name": f"Cửa hàng Demo {i % 45 + 1:03d}" if payee_match else "Nguyen Van Example",
            "description": description,
            "scam_label": risky,
            "scam_type": scam_type,
            "synthetic": True,
        })
    return records
