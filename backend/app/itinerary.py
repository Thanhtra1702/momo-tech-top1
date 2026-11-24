"""Lập lịch trình xác định bằng thuật toán, LLM không tự tính tiền.

Tổng chi phí luôn bằng tổng các mục. Khoản ăn uống là ước tính cố định và được gắn nhãn.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from . import catalog
from .catalog import CatalogError, parse_date, vn_dt
from .db import Database
from .external import get_places
from .textutil import canon_city, city_display, norm

FOOD_EST_VND_PER_PERSON_DAY = 150_000
MAX_DAYS = 14


def _entry(time: str, title: str, cost: int, ref_id: str | None = None) -> dict:
    e = {"time": time, "title": title, "cost_vnd": int(cost)}
    if ref_id:
        e["ref_id"] = ref_id
    return e


def build_itinerary(db: Database, city: str, days: int, budget_vnd: int, guests: int, start_date: str,
                    origin: str | None = None, preferences: list[str] | None = None) -> dict:
    try:
        days, budget_vnd, guests = int(days), int(budget_vnd), int(guests)
    except (TypeError, ValueError) as exc:
        raise CatalogError("days, budget_vnd, guests phải là số nguyên") from exc
    if not 1 <= days <= MAX_DAYS:
        raise CatalogError(f"days phải từ 1 đến {MAX_DAYS}")
    if budget_vnd <= 0 or not 1 <= guests <= 10:
        raise CatalogError("budget_vnd phải dương và guests từ 1 đến 10")
    start = parse_date(start_date, "start_date")
    if start is None:
        raise CatalogError("Thiếu start_date (YYYY-MM-DD)")
    key = canon_city(city)
    end = start + timedelta(days=days - 1)
    nights = days - 1
    rooms = math.ceil(guests / 2)
    notes: list[str] = []
    prefs = [norm(p) for p in (preferences or []) if norm(p)]

    # 1. di chuyển
    transport: list[tuple[int, dict]] = []  # (ngày thứ, chuyến)
    if origin and canon_city(origin) != key:
        for day_idx, o, d, when in ((1, origin, city, start), (days, city, origin, end)):
            opts = [t for t in catalog.search_transport(db, origin=o, destination=d, date=when.isoformat(), limit=10)
                    if t["seats_left"] >= guests]
            if opts:
                transport.append((day_idx, opts[0]))
            else:
                notes.append(f"Không còn chuyến {city_display(canon_city(o))} - {city_display(canon_city(d))} ngày {when.isoformat()}")
    transport_cost = sum(t["price_vnd"] * guests for _, t in transport)
    food_cost = FOOD_EST_VND_PER_PERSON_DAY * guests * days

    # 2. lưu trú
    lodging = None
    lodging_cost = 0
    if nights > 0:
        room_budget = budget_vnd - transport_cost - food_cost
        options = [x for x in catalog.search_lodging(db, city=city, limit=10, sort_by="rating") if x["rooms_left"] >= rooms]

        def lodging_total(x: dict) -> int:
            return x["price_per_night_vnd"] * nights * rooms

        def pref_hits(x: dict) -> int:
            return sum(1 for p in prefs if any(p in norm(a) for a in x["amenities"]))

        affordable = [x for x in options if lodging_total(x) <= max(room_budget * 0.6, 0)]
        pool = affordable or sorted(options, key=lodging_total)[:1]
        if pool:
            lodging = max(pool, key=lambda x: (pref_hits(x), x["rating"], -lodging_total(x)))
            lodging_cost = lodging_total(lodging)
            if not affordable:
                notes.append("Không có lưu trú nào nằm trong phần ngân sách dự kiến, đã chọn phương án rẻ nhất")
        else:
            notes.append(f"Không còn chỗ lưu trú phù hợp ở {city_display(key)}")

    # 3. hoạt động tùy chọn, bỏ dần nếu vượt ngân sách
    base_total = transport_cost + food_cost + lodging_cost
    optional: list[tuple[str, dict, int]] = []  # (loại, item, chi phí)
    for tour in catalog.search_tours(db, city=city, max_days=days, limit=10):
        if tour["slots_left"] >= guests:
            optional.append(("tour", tour, tour["price_per_person_vnd"] * guests))
    for ev in catalog.search_events(db, city=city, date_from=start.isoformat(), date_to=end.isoformat(), limit=10, sort_by="rating"):
        if ev["seats_left"] >= guests:
            optional.append(("event", ev, ev["price_vnd"] * guests))
    optional.sort(key=lambda x: -x[1]["rating"])
    chosen: list[tuple[str, dict, int]] = []
    remaining = budget_vnd - base_total
    max_activities = max(1, days)
    event_days: set[int] = set()  # mỗi ngày tối đa một sự kiện
    event_titles: set[str] = set()  # không xếp cùng một phim hay sự kiện hai lần
    for kind, item, cost in optional:
        if len(chosen) >= max_activities:
            break
        if cost > remaining or (kind == "tour" and any(k == "tour" for k, _, _ in chosen)):
            continue
        if kind == "event":
            day_no = (vn_dt(item["starts_at"]).date() - start).days + 1
            if day_no in event_days or item["title"] in event_titles:
                continue
            event_days.add(day_no)
            event_titles.add(item["title"])
        chosen.append((kind, item, cost))
        remaining -= cost

    # 4. dựng từng ngày
    day_entries: dict[int, list[dict]] = {i: [] for i in range(1, days + 1)}
    for idx, t in transport:
        dep = vn_dt(t["departs_at"]).strftime("%H:%M")
        day_entries[idx].append(_entry(dep, f"{t['carrier']}: {t['origin']} - {t['destination']}", t["price_vnd"] * guests, t["id"]))
    if lodging:
        day_entries[1].append(_entry("14:00", f"Nhận phòng: {lodging['name']}", lodging_cost, lodging["id"]))
        day_entries[days].append(_entry("12:00", "Trả phòng", 0))
    try:
        places = get_places(city)
    except ValueError:
        places = []
    pi = 0
    for d in range(1, days + 1):
        day_entries[d].append(_entry("12:30", "Ăn trưa và tối (ước tính)", FOOD_EST_VND_PER_PERSON_DAY * guests))
        for hh in ("09:00", "16:00"):
            if places and not (d == 1 and hh == "09:00" and transport) and not (d == days and transport):
                p = places[pi % len(places)]; pi += 1
                day_entries[d].append(_entry(hh, f"Tham quan: {p['name']}", 0))
    slot_day = 2 if days > 1 else 1
    for kind, item, cost in chosen:
        if kind == "tour":
            day_entries[slot_day].append(_entry("08:30", f"Tour: {item['name']}", cost, item["id"]))
        else:
            when = vn_dt(item["starts_at"])
            d = (when.date() - start).days + 1
            if 1 <= d <= days:
                day_entries[d].append(_entry(when.strftime("%H:%M"), f"{item['title']} ({item['venue']})", cost, item["id"]))
    for d in day_entries:
        seen: set[str] = set()
        day_entries[d].sort(key=lambda e: e["time"])
        for e in day_entries[d]:  # tránh trùng giờ để dòng thời gian không chồng chéo
            while e["time"] in seen:
                h, m = map(int, e["time"].split(":"))
                m += 15
                e["time"] = f"{(h + m // 60) % 24:02d}:{m % 60:02d}"
            seen.add(e["time"])
        day_entries[d].sort(key=lambda e: e["time"])

    total = sum(e["cost_vnd"] for es in day_entries.values() for e in es)
    within = total <= budget_vnd
    if not within:
        notes.append(f"Tổng chi phí vượt ngân sách {total - budget_vnd:,} VND".replace(",", "."))
    block = {
        "kind": "itinerary",
        "days": [{"day": d, "entries": es} for d, es in day_entries.items()],
        "total_vnd": total,
    }
    return {"block": block, "within_budget": within, "total_vnd": total, "budget_vnd": budget_vnd,
            "guests": guests, "start_date": start.isoformat(), "end_date": end.isoformat(), "notes": notes}
