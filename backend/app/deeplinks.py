"""Deep link tới trang tìm kiếm công khai, điền sẵn truy vấn. Không tự động hóa thao tác trên trang đối tác."""

from __future__ import annotations

from urllib.parse import quote

AIRPORT_CODES = {
    "ha noi": "HAN",
    "ho chi minh": "SGN",
    "da nang": "DAD",
    "da lat": "DLI",
    "nha trang": "CXR",
    "phu quoc": "PQC",
    "hue": "HUI",
    "hai phong": "HPH",
}


def _search(q: str) -> str:
    return f"https://www.google.com/search?q={quote(q)}"


def transport_link(mode: str, origin_key: str, dest_key: str, origin: str, dest: str, date: str) -> str:
    if mode == "flight" and origin_key in AIRPORT_CODES and dest_key in AIRPORT_CODES:
        q = f"Flights from {AIRPORT_CODES[origin_key]} to {AIRPORT_CODES[dest_key]} on {date}"
        return f"https://www.google.com/travel/flights?q={quote(q)}"
    label = {"train": "vé tàu hỏa", "bus": "vé xe khách"}.get(mode, "vé")
    return _search(f"{label} {origin} {dest} {date}")


def event_link(title: str, city: str) -> str:
    return _search(f"đặt vé {title} {city}")


def lodging_link(name: str, city: str) -> str:
    return _search(f"đặt phòng {name} {city}")


def tour_link(name: str, city: str) -> str:
    return _search(f"đặt tour {name} {city}")
