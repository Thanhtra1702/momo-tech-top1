"""Dữ liệu bên ngoài: thời tiết (Open-Meteo, không cần khóa) và địa điểm (danh sách tuyển chọn).

Thời tiết có cache và dự phòng ước tính theo khí hậu trung bình khi API ngoài lỗi hoặc ngày quá xa.
"""

from __future__ import annotations

import math
import threading
import time
from datetime import date
from typing import Callable

import httpx

from .seed import now_ict
from .textutil import CITIES, canon_city

COORDS = {
    "ha noi": (21.0285, 105.8542), "ho chi minh": (10.8231, 106.6297), "da nang": (16.0544, 108.2022),
    "da lat": (11.9404, 108.4583), "nha trang": (12.2388, 109.1967), "phu quoc": (10.2899, 103.9840),
    "hue": (16.4637, 107.5909), "hai phong": (20.8449, 106.6881), "hoi an": (15.8801, 108.3380),
    "can tho": (10.0452, 105.7469),
}
# (nhiệt độ trung bình năm, biên độ theo mùa). Chỉ là ước tính thô, luôn gắn nhãn "estimate".
CLIMATE = {
    "ha noi": (24, 7), "ho chi minh": (28, 1.5), "da nang": (26, 4), "da lat": (18, 2), "nha trang": (27, 2),
    "phu quoc": (28, 1.5), "hue": (25, 5), "hai phong": (24, 7), "hoi an": (26, 4), "can tho": (28, 1.5),
}
_WMO = [
    (0, "trời quang"), (3, "ít mây đến nhiều mây"), (48, "sương mù"), (57, "mưa phùn"), (67, "mưa"),
    (77, "tuyết"), (82, "mưa rào"), (99, "dông"),
]
_CACHE: dict[tuple[str, str], tuple[float, dict]] = {}
_LOCK = threading.Lock()
TTL_S = 3600
FORECAST_DAYS = 16

Fetcher = Callable[[float, float], dict]


def _sky(code: int) -> str:
    for limit, label in _WMO:
        if code <= limit:
            return label
    return "không rõ"


def _fetch_open_meteo(lat: float, lon: float) -> dict:
    resp = httpx.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon, "timezone": "Asia/Bangkok", "forecast_days": FORECAST_DAYS,
            "daily": "temperature_2m_max,temperature_2m_min,weathercode,precipitation_probability_max",
        },
        timeout=5.0,
    )
    resp.raise_for_status()
    return resp.json()


def _estimate(city_key: str, day: date) -> dict:
    mean, amp = CLIMATE.get(city_key, (26, 3))
    temp = mean + amp * math.cos(2 * math.pi * (day.timetuple().tm_yday - 196) / 365)
    return {"temp_c": round(temp, 1), "sky": "không có dự báo, đây là ước tính theo khí hậu trung bình",
            "rain_chance_pct": None, "source": "estimate"}


def get_weather(city: str, day: date | None = None, fetcher: Fetcher | None = None) -> dict:
    key = canon_city(city)
    if key not in COORDS:
        raise ValueError("Chưa hỗ trợ thành phố này. Các thành phố có dữ liệu: " + ", ".join(CITIES.values()))
    day = day or now_ict().date()
    base = {"city": CITIES[key], "date": day.isoformat()}
    if not 0 <= (day - now_ict().date()).days < FORECAST_DAYS:
        return {**base, **_estimate(key, day)}
    cache_key = (key, day.isoformat())
    with _LOCK:
        hit = _CACHE.get(cache_key)
        if hit and time.time() - hit[0] < TTL_S:
            return {**base, **hit[1]}
    try:
        data = (fetcher or _fetch_open_meteo)(*COORDS[key])["daily"]
        idx = data["time"].index(day.isoformat())
        lo, hi = data["temperature_2m_min"][idx], data["temperature_2m_max"][idx]
        result = {
            "temp_c": round((lo + hi) / 2, 1), "temp_min_c": lo, "temp_max_c": hi,
            "sky": _sky(int(data["weathercode"][idx])),
            "rain_chance_pct": data["precipitation_probability_max"][idx], "source": "open-meteo",
        }
        with _LOCK:
            _CACHE[cache_key] = (time.time(), result)
    except Exception:
        result = _estimate(key, day)
    return {**base, **result}


# Danh sách địa điểm tuyển chọn (tọa độ gần đúng), tránh phụ thuộc dịch vụ ngoài và giới hạn sử dụng của chúng.
PLACES: dict[str, list[tuple[str, str, float, float]]] = {
    "ha noi": [("Hồ Hoàn Kiếm", "sight", 21.0285, 105.8522), ("Văn Miếu - Quốc Tử Giám", "culture", 21.0293, 105.8355),
               ("Phố cổ Hà Nội", "food", 21.0340, 105.8500), ("Hồ Tây", "nature", 21.0583, 105.8230)],
    "ho chi minh": [("Nhà thờ Đức Bà", "sight", 10.7798, 106.6990), ("Chợ Bến Thành", "food", 10.7725, 106.6980),
                    ("Phố đi bộ Nguyễn Huệ", "nightlife", 10.7745, 106.7040),
                    ("Bảo tàng Chứng tích Chiến tranh", "culture", 10.7794, 106.6920)],
    "da nang": [("Cầu Rồng", "sight", 16.0614, 108.2272), ("Bãi biển Mỹ Khê", "nature", 16.0544, 108.2478),
                ("Bán đảo Sơn Trà", "nature", 16.1167, 108.2833), ("Ngũ Hành Sơn", "culture", 16.0039, 108.2631)],
    "da lat": [("Hồ Xuân Hương", "nature", 11.9437, 108.4416), ("Thung lũng Tình Yêu", "sight", 11.9760, 108.4500),
               ("Chợ Đà Lạt", "food", 11.9437, 108.4380), ("Thác Datanla", "nature", 11.9024, 108.4503)],
    "nha trang": [("Tháp Bà Ponagar", "culture", 12.2653, 109.1953), ("Bãi biển Trần Phú", "nature", 12.2388, 109.1967),
                  ("Hòn Chồng", "sight", 12.2700, 109.2050), ("Viện Hải dương học", "culture", 12.2064, 109.2111)],
    "phu quoc": [("Bãi Sao", "nature", 10.0560, 104.0380), ("Chợ đêm Phú Quốc", "food", 10.2220, 103.9620),
                 ("Dinh Cậu", "culture", 10.2166, 103.9669), ("Bãi Dài", "nature", 10.3300, 103.8500)],
    "hue": [("Đại Nội Huế", "culture", 16.4698, 107.5786), ("Chùa Thiên Mụ", "culture", 16.4538, 107.5448),
            ("Lăng Khải Định", "culture", 16.3993, 107.5898), ("Sông Hương", "nature", 16.4637, 107.5909)],
    "hai phong": [("Bãi biển Đồ Sơn", "nature", 20.7060, 106.7900), ("Nhà hát Lớn Hải Phòng", "culture", 20.8590, 106.6830),
                  ("Đảo Cát Bà", "nature", 20.7270, 107.0480)],
    "hoi an": [("Phố cổ Hội An", "sight", 15.8801, 108.3380), ("Chùa Cầu", "culture", 15.8770, 108.3263),
               ("Bãi biển An Bàng", "nature", 15.9020, 108.3570), ("Rừng dừa Bảy Mẫu", "nature", 15.8650, 108.3700)],
    "can tho": [("Chợ nổi Cái Răng", "food", 10.0050, 105.7490), ("Bến Ninh Kiều", "sight", 10.0330, 105.7880),
                ("Nhà cổ Bình Thủy", "culture", 10.0640, 105.7360)],
}


def get_places(city: str, category: str | None = None) -> list[dict]:
    key = canon_city(city)
    if key not in PLACES:
        raise ValueError("Chưa hỗ trợ thành phố này. Các thành phố có dữ liệu: " + ", ".join(CITIES.values()))
    out = [{"name": n, "category": c, "lat": la, "lon": lo} for n, c, la, lo in PLACES[key]]
    if category:
        out = [p for p in out if p["category"] == category]
    return out
