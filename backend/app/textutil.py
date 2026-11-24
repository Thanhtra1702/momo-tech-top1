"""Chuẩn hóa tiếng Việt không dấu và tên thành phố."""

from __future__ import annotations

import re
import unicodedata

CITIES: dict[str, str] = {
    "ha noi": "Hà Nội",
    "ho chi minh": "TP. Hồ Chí Minh",
    "da nang": "Đà Nẵng",
    "da lat": "Đà Lạt",
    "nha trang": "Nha Trang",
    "phu quoc": "Phú Quốc",
    "hue": "Huế",
    "hai phong": "Hải Phòng",
    "hoi an": "Hội An",
    "can tho": "Cần Thơ",
}

_ALIASES: dict[str, str] = {
    "sai gon": "ho chi minh",
    "saigon": "ho chi minh",
    "sg": "ho chi minh",
    "hcm": "ho chi minh",
    "tp hcm": "ho chi minh",
    "tphcm": "ho chi minh",
    "tp ho chi minh": "ho chi minh",
    "thanh pho ho chi minh": "ho chi minh",
    "ho chi minh city": "ho chi minh",
    "hn": "ha noi",
    "hanoi": "ha noi",
    "thu do": "ha noi",
    "dalat": "da lat",
    "danang": "da nang",
    "nhatrang": "nha trang",
    "phuquoc": "phu quoc",
    "hoian": "hoi an",
}


def norm(text: str | None) -> str:
    """Bỏ dấu, hạ chữ thường, chỉ giữ chữ và số."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return text.strip()


def canon_city(text: str | None) -> str:
    """Trả về khóa thành phố chuẩn (không dấu). Không nhận ra thì trả chuỗi đã chuẩn hóa."""
    n = norm(text)
    if n in CITIES:
        return n
    if n in _ALIASES:
        return _ALIASES[n]
    for alias, key in _ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", n):
            return key
    for key in CITIES:
        if re.search(rf"\b{re.escape(key)}\b", n):
            return key
    return n


def city_display(key: str) -> str:
    return CITIES.get(key, key)
