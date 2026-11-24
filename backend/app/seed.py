"""Sinh danh mục mô phỏng, xác định (cùng seed cho cùng kết quả), tính từ ngày hiện tại.

Toàn bộ tên hãng, rạp, khách sạn là hư cấu. Giá chỉ mang tính minh họa.
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone

from . import deeplinks
from .db import CATALOG_TABLES, Database
from .textutil import CITIES, norm

ICT = timezone(timedelta(hours=7))
HORIZON_DAYS = 45


def now_ict() -> datetime:
    return datetime.now(ICT)


def _iso(d: date, hh: int, mm: int) -> str:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ICT).isoformat()


def _round(v: float, step: int = 1000) -> int:
    return int(round(v / step) * step)


# --- giao thông ---------------------------------------------------------------------------
FLIGHT_ROUTES = [  # (a, b, phút, giá cơ sở)
    ("ha noi", "ho chi minh", 125, 1500000), ("ha noi", "da nang", 85, 1200000),
    ("ha noi", "da lat", 110, 1400000), ("ha noi", "nha trang", 115, 1500000),
    ("ha noi", "phu quoc", 125, 1700000), ("ha noi", "hue", 75, 1100000),
    ("ho chi minh", "da nang", 85, 1100000), ("ho chi minh", "da lat", 55, 700000),
    ("ho chi minh", "nha trang", 65, 800000), ("ho chi minh", "phu quoc", 60, 900000),
    ("ho chi minh", "hue", 95, 1200000), ("ho chi minh", "hai phong", 125, 1600000),
    ("da nang", "da lat", 70, 900000), ("da nang", "phu quoc", 100, 1300000),
]
TRAIN_ROUTES = [
    ("ha noi", "hue", 720, 750000), ("ha noi", "da nang", 900, 850000),
    ("da nang", "hue", 180, 150000), ("da nang", "nha trang", 560, 450000),
    ("ho chi minh", "nha trang", 500, 400000), ("ho chi minh", "da nang", 1000, 900000),
    ("ha noi", "ho chi minh", 1900, 1500000),
]
BUS_ROUTES = [
    ("ho chi minh", "da lat", 420, 300000), ("ho chi minh", "can tho", 210, 150000),
    ("ha noi", "hai phong", 120, 100000), ("da nang", "hoi an", 60, 60000),
    ("nha trang", "da lat", 240, 200000), ("ho chi minh", "nha trang", 600, 350000),
]
FLIGHT_CARRIERS = [("Hãng bay mẫu A", 1.0), ("Hãng bay mẫu B", 0.85), ("Hãng bay mẫu C", 1.2)]
TRAIN_CARRIERS = [("Đường sắt mẫu", 1.0)]
BUS_CARRIERS = [("Xe khách mẫu X", 1.0), ("Xe khách mẫu Y", 1.15)]

# --- giải trí -----------------------------------------------------------------------------
MOVIES = [
    ("Mưa Trên Phố Cổ", ["tình cảm"]), ("Hành Trình Về Phương Nam", ["phiêu lưu", "gia đình"]),
    ("Đêm Không Ngủ", ["hành động", "kinh dị"]), ("Con Đường Gió Lộng", ["tâm lý"]),
    ("Biệt Đội Sao Hôm", ["hoạt hình", "gia đình"]), ("Mật Mã Hà Nội", ["hành động", "trinh thám"]),
    ("Ngày Mai Nắng Lên", ["tình cảm", "hài"]), ("Rừng Sâu Thẳm", ["kinh dị"]),
    ("Chuyến Tàu Cuối Ngày", ["tâm lý", "tình cảm"]), ("Thiên Hà Xa Lạ", ["khoa học viễn tưởng"]),
    ("Quán Cà Phê Số 9", ["hài", "tình cảm"]), ("Lời Thề Biển Xanh", ["phiêu lưu"]),
]
CINEMA_CITIES = ["ha noi", "ho chi minh", "da nang", "da lat", "nha trang", "hue", "hai phong", "can tho"]
CONCERTS = [
    "Đêm Nhạc Mùa Đông", "Giai Điệu Thanh Xuân", "Rock Việt Live", "Acoustic Bên Hồ",
    "Nhạc Trịnh Một Thời", "Electronic Night Mẫu", "Hòa Tấu Giao Hưởng Cuối Năm", "Hip-hop Underground Mẫu",
    "Đêm Nhạc Bolero", "Indie Sài Gòn Live", "Jazz Bên Sông", "Lễ Hội Âm Nhạc Biển",
]
OTHER_EVENTS = [
    ("Đêm Hài Độc Thoại Mẫu", "event", ["hài", "stand-up"]), ("Triển Lãm Ánh Sáng Số", "event", ["triển lãm"]),
    ("Lễ Hội Ẩm Thực Đường Phố", "event", ["ẩm thực", "lễ hội"]), ("Chợ Phiên Cuối Tuần", "event", ["chợ", "gia đình"]),
    ("Kịch Nói: Người Ở Lại", "event", ["sân khấu"]), ("Giải Chạy Bộ Thành Phố", "event", ["thể thao"]),
    ("Triển Lãm Ảnh Đường Phố", "event", ["triển lãm", "nhiếp ảnh"]), ("Múa Rối Nước Đặc Sắc", "event", ["sân khấu", "gia đình"]),
]

# --- lưu trú, tour ------------------------------------------------------------------------
HOTEL_WORDS = ["Hoàng Hôn", "Sao Mai", "Hồ Xanh", "Phố Cổ", "Cánh Buồm", "Mây Trắng", "Ánh Dương", "Lá Xanh",
               "Bình Minh", "Hương Biển", "Đồi Thông", "Sông Hương Mẫu", "Trung Tâm", "Vườn Nhiệt Đới", "Gió Biển"]
KINDS = [("hotel", "Khách sạn", 1.0), ("resort", "Resort", 2.2), ("homestay", "Homestay", 0.55), ("hostel", "Hostel", 0.3)]
AMENITIES = ["hồ bơi", "bữa sáng", "wifi", "đưa đón sân bay", "gần biển", "bồn tắm", "phòng gia đình", "bãi đỗ xe", "gym", "spa"]
CITY_PRICE = {"ha noi": 1.0, "ho chi minh": 1.1, "da nang": 1.0, "da lat": 0.9, "nha trang": 1.0,
              "phu quoc": 1.4, "hue": 0.8, "hai phong": 0.8, "hoi an": 0.95, "can tho": 0.7}
TOUR_TEMPLATES = {
    "ha noi": [("Phố cổ và ẩm thực Hà Nội 1 ngày", 1, 450000, ["phố cổ", "ẩm thực"]),
               ("Hà Nội - Hạ Long 2N1Đ", 2, 2200000, ["vịnh Hạ Long", "chèo kayak"]),
               ("Ninh Bình 1 ngày", 1, 750000, ["Tràng An", "Hang Múa"]),
               ("Sapa 3N2Đ", 3, 3200000, ["ruộng bậc thang", "bản Cát Cát"])],
    "ho chi minh": [("Nửa ngày Sài Gòn xưa", 0.5, 350000, ["Dinh Độc Lập", "chợ Bến Thành"]),
                    ("Địa đạo Củ Chi 1 ngày", 1, 600000, ["địa đạo", "lịch sử"]),
                    ("Miền Tây 2N1Đ", 2, 1900000, ["chợ nổi", "vườn trái cây"]),
                    ("Sài Gòn về đêm", 0.5, 450000, ["ẩm thực đêm", "phố đi bộ"])],
    "da nang": [("Bà Nà - Cầu Vàng 1 ngày", 1, 900000, ["cáp treo", "cầu Vàng"]),
                ("Đà Nẵng - Hội An 3N2Đ", 3, 3400000, ["biển Mỹ Khê", "phố cổ Hội An"]),
                ("Sơn Trà - Ngũ Hành Sơn", 0.5, 400000, ["bán đảo Sơn Trà", "Ngũ Hành Sơn"]),
                ("Cù Lao Chàm 1 ngày", 1, 850000, ["lặn ngắm san hô", "biển"])],
    "da lat": [("Đà Lạt 3N2Đ săn mây và thác", 3, 2900000, ["săn mây", "thác Datanla", "chợ đêm"]),
               ("Đà Lạt 2N1Đ nghỉ dưỡng", 2, 1800000, ["hồ Xuân Hương", "đồi chè"]),
               ("Trekking Langbiang 1 ngày", 1, 700000, ["trekking", "núi Langbiang"]),
               ("Đà Lạt 4N3Đ khám phá", 4, 4100000, ["thung lũng", "vườn hoa", "thác"])],
    "nha trang": [("Tour 4 đảo Nha Trang", 1, 650000, ["lặn biển", "tắm biển"]),
                  ("Nha Trang 3N2Đ biển xanh", 3, 3100000, ["biển", "tháp Bà", "bùn khoáng"]),
                  ("Vịnh Vân Phong 1 ngày", 1, 800000, ["canoe", "đảo hoang"])],
    "phu quoc": [("Phú Quốc 3N2Đ nghỉ dưỡng", 3, 3800000, ["bãi Sao", "chợ đêm"]),
                 ("Lặn ngắm san hô Nam đảo", 1, 900000, ["lặn biển", "câu cá"]),
                 ("Phú Quốc 4N3Đ khám phá", 4, 5200000, ["Bãi Dài", "Dinh Cậu"])],
    "hue": [("Cố đô Huế 1 ngày", 1, 550000, ["Đại Nội", "chùa Thiên Mụ"]),
            ("Huế - Đà Nẵng 2N1Đ", 2, 1700000, ["lăng tẩm", "đèo Hải Vân"]),
            ("Sông Hương về đêm", 0.5, 300000, ["thuyền rồng", "ca Huế"])],
    "hai phong": [("Cát Bà 2N1Đ", 2, 1500000, ["vịnh Lan Hạ", "biển"]),
                  ("Đồ Sơn 1 ngày", 1, 450000, ["biển", "ẩm thực hải sản"])],
    "hoi an": [("Phố cổ Hội An về đêm", 0.5, 350000, ["thả đèn hoa đăng", "phố cổ"]),
               ("Làng nghề và rừng dừa", 1, 600000, ["thúng chai", "làng gốm"]),
               ("Học nấu ăn Hội An", 0.5, 500000, ["ẩm thực", "chợ địa phương"])],
    "can tho": [("Chợ nổi Cái Răng 1 ngày", 1, 450000, ["chợ nổi", "vườn trái cây"]),
                ("Cần Thơ - Cà Mau 3N2Đ", 3, 2600000, ["rừng U Minh", "mũi Cà Mau"])],
}
VENUES = {
    "ha noi": ["Nhà hát Lớn Mẫu", "Cung văn hóa Mẫu"], "ho chi minh": ["Nhà hát Hòa Bình Mẫu", "Sân khấu Thành Phố Mẫu"],
    "da nang": ["Trung tâm Văn hóa Đà Nẵng Mẫu"], "da lat": ["Quảng trường Lâm Viên Mẫu"],
    "nha trang": ["Quảng trường biển Mẫu"], "hue": ["Nhà hát Cung đình Mẫu"],
    "hai phong": ["Nhà hát thành phố Mẫu"], "can tho": ["Trung tâm hội nghị Mẫu"],
    "phu quoc": ["Sân khấu bãi biển Mẫu"], "hoi an": ["Sân khấu phố cổ Mẫu"],
}


def _seed_transport(rng: random.Random, today: date, rows: list[tuple]) -> None:
    counters = {"flight": 0, "train": 0, "bus": 0}
    prefix = {"flight": "fl", "train": "tr", "bus": "bs"}
    plans = [
        ("flight", FLIGHT_ROUTES, FLIGHT_CARRIERS, 3, [(6, 10), (9, 40), (13, 20), (16, 50), (20, 15)], [7, 20]),
        ("train", TRAIN_ROUTES, TRAIN_CARRIERS, 2, [(6, 30), (19, 0), (21, 30)], [20]),
        ("bus", BUS_ROUTES, BUS_CARRIERS, 4, [(6, 0), (9, 0), (13, 0), (21, 0), (22, 30)], [20]),
    ]
    for mode, routes, carriers, per_day, slots, bags in plans:
        for a, b, minutes, base in routes:
            for src, dst in ((a, b), (b, a)):
                for offset in range(1, HORIZON_DAYS + 1):
                    d = today + timedelta(days=offset)
                    weekend = 1.1 if d.weekday() >= 4 else 1.0
                    for hh, mm in rng.sample(slots, min(per_day, len(slots))):
                        carrier, tier = rng.choice(carriers)
                        price = _round(base * tier * weekend * rng.uniform(0.75, 1.3))
                        dep = datetime(d.year, d.month, d.day, hh, mm, tzinfo=ICT)
                        arr = dep + timedelta(minutes=minutes)
                        counters[mode] += 1
                        seats = 0 if rng.random() < 0.05 else rng.randint(2, 60)
                        rows.append((
                            f"trp_{prefix[mode]}_{counters[mode]:05d}", mode, carrier,
                            CITIES[src], src, CITIES[dst], dst, dep.isoformat(), arr.isoformat(), price, seats,
                            rng.choice(bags), int(rng.random() < 0.4),
                            deeplinks.transport_link(mode, src, dst, CITIES[src], CITIES[dst], d.isoformat()),
                        ))


def _seed_events(rng: random.Random, today: date, rows: list[tuple]) -> None:
    n = {"mv": 0, "cc": 0, "ev": 0}

    def add(prefix: str, kind: str, title: str, city: str, starts: str, price: int, seats: int, rating: float, tags: list[str]) -> None:
        n[prefix] += 1
        venue = rng.choice(VENUES[city]) if kind != "movie" else f"Rạp Cinema Mẫu {rng.randint(1, 3)} - {CITIES[city]}"
        rows.append((
            f"evt_{prefix}_{n[prefix]:04d}", kind, title, norm(title), venue, CITIES[city], city, starts,
            price, seats, rating, json.dumps(tags, ensure_ascii=False), norm(" ".join(tags)),
            deeplinks.event_link(title, CITIES[city]),
        ))

    for title, tags in MOVIES:
        rating = round(rng.uniform(3.4, 4.8), 1)
        for city in rng.sample(CINEMA_CITIES, 4):
            for offset in range(1, 22):
                d = today + timedelta(days=offset)
                for hh, mm in rng.sample([(10, 0), (13, 30), (16, 0), (19, 30), (21, 45)], 2):
                    price = 70000 + rng.choice([0, 10000, 20000, 30000]) + (20000 if d.weekday() >= 5 else 0)
                    seats = 0 if rng.random() < 0.04 else rng.randint(3, 120)
                    add("mv", "movie", title, city, _iso(d, hh, mm), price, seats, rating, tags + ["2D" if rng.random() < 0.7 else "3D"])
    major = ["ho chi minh", "ha noi", "da nang"]  # đảm bảo ba thành phố lớn luôn có concert
    for idx, title in enumerate(CONCERTS):
        for j in range(2):
            city = major[idx % 3] if j == 0 else rng.choice(list(VENUES))
            d = today + timedelta(days=rng.randint(3, HORIZON_DAYS))
            low, high = (200000, 500000) if rng.random() < 0.4 else (300000, 2500000)
            add("cc", "concert", title, city, _iso(d, 20, 0), _round(rng.uniform(low, high), 50000),
                0 if rng.random() < 0.1 else rng.randint(20, 400), round(rng.uniform(4.0, 4.9), 1), ["âm nhạc"])
    for title, kind, tags in OTHER_EVENTS:
        for _ in range(3):
            city = rng.choice(list(VENUES))
            d = today + timedelta(days=rng.randint(2, HORIZON_DAYS))
            add("ev", kind, title, city, _iso(d, rng.choice([9, 15, 19]), 0), _round(rng.uniform(0, 400000), 10000),
                rng.randint(10, 300), round(rng.uniform(3.6, 4.8), 1), tags)


def _seed_lodging(rng: random.Random, rows: list[tuple]) -> None:
    n = 0
    for city, factor in CITY_PRICE.items():
        words = rng.sample(HOTEL_WORDS, 12)
        for w in words:
            kind, label, kf = rng.choice(KINDS)
            n += 1
            name = f"{label} {w} {CITIES[city]}"
            amen = rng.sample(AMENITIES, rng.randint(2, 6))
            if "wifi" not in amen:
                amen.append("wifi")
            if city in ("da nang", "nha trang", "phu quoc", "hoi an") and rng.random() < 0.5 and "gần biển" not in amen:
                amen.append("gần biển")
            price = _round(600000 * factor * kf * rng.uniform(0.7, 1.4), 10000)
            rows.append((
                f"lod_{n:04d}", name, norm(name), kind, CITIES[city], city, price,
                0 if rng.random() < 0.05 else rng.randint(1, 12), round(rng.uniform(3.2, 4.9), 1),
                json.dumps(amen, ensure_ascii=False), norm(" ".join(amen)), int(rng.random() < 0.6),
                deeplinks.lodging_link(name, CITIES[city]),
            ))


def _seed_tours(rng: random.Random, today: date, rows: list[tuple]) -> None:
    n = 0
    for city, templates in TOUR_TEMPLATES.items():
        for name, days, price, highlights in templates:
            n += 1
            dep = today + timedelta(days=rng.randint(2, HORIZON_DAYS))
            rows.append((
                f"tur_{n:04d}", name, norm(name), CITIES[city], city, float(days),
                _round(price * rng.uniform(0.9, 1.15), 10000), 0 if rng.random() < 0.05 else rng.randint(2, 20),
                round(rng.uniform(3.7, 4.9), 1), json.dumps(highlights, ensure_ascii=False), norm(" ".join(highlights)),
                dep.isoformat(), deeplinks.tour_link(name, CITIES[city]),
            ))


def seed_catalog(db: Database, today: date | None = None, seed: int = 2026) -> None:
    today = today or now_ict().date()
    rng = random.Random(seed)
    ev: list[tuple] = []
    tr: list[tuple] = []
    lo: list[tuple] = []
    tu: list[tuple] = []
    _seed_events(rng, today, ev)
    _seed_transport(rng, today, tr)
    _seed_lodging(rng, lo)
    _seed_tours(rng, today, tu)
    with db.conn() as c:
        for t in CATALOG_TABLES:
            c.execute(f"DELETE FROM {t}")
        c.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ev)
        c.executemany("INSERT INTO transport VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", tr)
        c.executemany("INSERT INTO lodging VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", lo)
        c.executemany("INSERT INTO tours VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", tu)


def ensure_seeded(db: Database, today: date | None = None) -> bool:
    """Sinh lại danh mục nếu rỗng hoặc sắp hết dữ liệu tương lai. Trả về True nếu đã sinh."""
    today = today or now_ict().date()
    with db.conn() as c:
        row = c.execute("SELECT MAX(departs_at) AS m, COUNT(*) AS n FROM transport").fetchone()
    horizon = (today + timedelta(days=14)).isoformat()
    if not row["n"] or (row["m"] or "")[:10] < horizon:
        seed_catalog(db, today)
        return True
    return False
