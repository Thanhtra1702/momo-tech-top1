"""Truy vấn danh mục. Mọi con số (giá, chỗ trống, thời gian) đến từ SQL, không từ LLM."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from .db import Database
from .seed import ICT, now_ict
from .textutil import canon_city, norm

MAX_LIMIT = 10

# kind -> (bảng, tiền tố id, cột giá, cột tồn kho)
KINDS: dict[str, tuple[str, str, str, str]] = {
    "event": ("events", "evt_", "price_vnd", "seats_left"),
    "transport": ("transport", "trp_", "price_vnd", "seats_left"),
    "lodging": ("lodging", "lod_", "price_per_night_vnd", "rooms_left"),
    "tour": ("tours", "tur_", "price_per_person_vnd", "slots_left"),
}


class CatalogError(ValueError):
    """Tham số không hợp lệ. Thông điệp được trả cho LLM để tự sửa."""


def parse_date(value: str | None, name: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise CatalogError(f"{name} phải có dạng YYYY-MM-DD") from exc


def _limit(limit: Any, default: int = 5) -> int:
    try:
        n = int(limit) if limit is not None else default
    except (TypeError, ValueError) as exc:
        raise CatalogError("limit phải là số nguyên") from exc
    return max(1, min(n, MAX_LIMIT))


def _price(value: Any, name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        v = int(value)
    except (TypeError, ValueError) as exc:
        raise CatalogError(f"{name} phải là số nguyên (VND)") from exc
    if v < 0:
        raise CatalogError(f"{name} không được âm")
    return v


# Từ chung chung mô hình hay nhét vào `query` ("concert", "phim"...). Loại bỏ để không làm rỗng kết quả:
# loại vé đã có tham số riêng (kind) và các từ này không nằm trong tên hay thẻ của danh mục.
_STOPWORDS = {"concert", "phim", "movie", "ve", "event", "su", "kien", "show", "xem", "tim", "tour", "cho", "va", "hoac",
              "nao", "cuoi", "tuan", "gia", "re", "nhat"}


def _tokens(query: str | None) -> list[str]:
    return [t for t in norm(query).split() if len(t) > 1 and t not in _STOPWORDS]


def _score(tokens: list[str], haystack: str) -> int:
    return sum(1 for t in tokens if t in haystack)


def _now_iso() -> str:
    return now_ict().isoformat()


# --- chuyển hàng DB sang đúng schema trong contracts/ ---------------------------------------
def event_item(r) -> dict:
    return {"id": r["id"], "kind": r["kind"], "title": r["title"], "venue": r["venue"], "city": r["city"],
            "starts_at": r["starts_at"], "price_vnd": r["price_vnd"], "seats_left": r["seats_left"],
            "rating": r["rating"], "tags": json.loads(r["tags"]), "deeplink": r["deeplink"]}


def transport_item(r) -> dict:
    return {"id": r["id"], "mode": r["mode"], "carrier": r["carrier"], "origin": r["origin"],
            "destination": r["destination"], "departs_at": r["departs_at"], "arrives_at": r["arrives_at"],
            "price_vnd": r["price_vnd"], "seats_left": r["seats_left"], "baggage_kg": r["baggage_kg"],
            "refundable": bool(r["refundable"]), "deeplink": r["deeplink"]}


def lodging_item(r) -> dict:
    return {"id": r["id"], "name": r["name"], "kind": r["kind"], "city": r["city"],
            "price_per_night_vnd": r["price_per_night_vnd"], "rooms_left": r["rooms_left"], "rating": r["rating"],
            "amenities": json.loads(r["amenities"]), "free_cancellation": bool(r["free_cancellation"]),
            "deeplink": r["deeplink"]}


def tour_item(r) -> dict:
    d = {"id": r["id"], "name": r["name"], "city": r["city"], "duration_days": r["duration_days"],
         "price_per_person_vnd": r["price_per_person_vnd"], "slots_left": r["slots_left"], "rating": r["rating"],
         "highlights": json.loads(r["highlights"]), "deeplink": r["deeplink"]}
    if r["departs_on"]:
        d["departs_on"] = r["departs_on"]
    return d


_BUILDERS = {"event": event_item, "transport": transport_item, "lodging": lodging_item, "tour": tour_item}


def kind_of(ref_id: str) -> str | None:
    for kind, (_, prefix, _, _) in KINDS.items():
        if isinstance(ref_id, str) and ref_id.startswith(prefix):
            return kind
    return None


def get_item(db: Database, ref_id: str) -> tuple[str, dict] | None:
    kind = kind_of(ref_id)
    if kind is None:
        return None
    table = KINDS[kind][0]
    with db.conn() as c:
        row = c.execute(f"SELECT * FROM {table} WHERE id = ?", (ref_id,)).fetchone()
    return (kind, _BUILDERS[kind](row)) if row else None


def unit_price_and_stock(item: dict, kind: str) -> tuple[int, int, str]:
    """Trả về (đơn giá, tồn kho, tiêu đề) từ một item đã dựng theo schema."""
    if kind == "event":
        return item["price_vnd"], item["seats_left"], item["title"]
    if kind == "transport":
        return item["price_vnd"], item["seats_left"], f"{item['carrier']}: {item['origin']} - {item['destination']}"
    if kind == "lodging":
        return item["price_per_night_vnd"], item["rooms_left"], item["name"]
    return item["price_per_person_vnd"], item["slots_left"], item["name"]


# --- tìm kiếm ---------------------------------------------------------------------------------
def search_events(db: Database, query=None, kind=None, city=None, date_from=None, date_to=None,
                  max_price_vnd=None, limit=5, sort_by="time", exclude_movies=False) -> list[dict]:
    if kind not in (None, "", "movie", "concert", "event"):
        raise CatalogError("kind phải là movie, concert hoặc event")
    d_from, d_to = parse_date(date_from, "date_from"), parse_date(date_to, "date_to")
    maxp = _price(max_price_vnd, "max_price_vnd")
    sql, params = "SELECT * FROM events WHERE seats_left > 0 AND starts_at >= ?", [_now_iso()]
    if exclude_movies:
        sql += " AND kind != 'movie'"
    if kind:
        sql += " AND kind = ?"; params.append(kind)
    if city:
        sql += " AND city_norm = ?"; params.append(canon_city(city))
    if d_from:
        sql += " AND substr(starts_at,1,10) >= ?"; params.append(d_from.isoformat())
    if d_to:
        sql += " AND substr(starts_at,1,10) <= ?"; params.append(d_to.isoformat())
    if maxp is not None:
        sql += " AND price_vnd <= ?"; params.append(maxp)
    with db.conn() as c:
        rows = c.execute(sql, params).fetchall()
    tokens = _tokens(query)
    scored = [(r, _score(tokens, r["title_norm"] + " " + r["tags_norm"] + " " + norm(r["venue"]))) for r in rows]
    if tokens:
        scored = [(r, s) for r, s in scored if s > 0]
    if sort_by == "price":
        scored.sort(key=lambda x: (-x[1], x[0]["price_vnd"], x[0]["starts_at"]))
    elif sort_by == "rating":
        scored.sort(key=lambda x: (-x[1], -x[0]["rating"], x[0]["starts_at"]))
    else:
        scored.sort(key=lambda x: (-x[1], x[0]["starts_at"], x[0]["price_vnd"]))
    return [event_item(r) for r, _ in scored[: _limit(limit)]]


def search_transport(db: Database, origin=None, destination=None, date=None, mode=None, max_price_vnd=None,
                     limit=5, sort_by="price") -> list[dict]:
    if mode not in (None, "", "flight", "train", "bus"):
        raise CatalogError("mode phải là flight, train hoặc bus")
    day = parse_date(date, "date")
    maxp = _price(max_price_vnd, "max_price_vnd")
    sql, params = "SELECT * FROM transport WHERE seats_left > 0 AND departs_at >= ?", [_now_iso()]
    if origin:
        sql += " AND origin_norm = ?"; params.append(canon_city(origin))
    if destination:
        sql += " AND destination_norm = ?"; params.append(canon_city(destination))
    if day:
        sql += " AND substr(departs_at,1,10) = ?"; params.append(day.isoformat())
    if mode:
        sql += " AND mode = ?"; params.append(mode)
    if maxp is not None:
        sql += " AND price_vnd <= ?"; params.append(maxp)
    order = {"time": "departs_at, price_vnd", "price": "price_vnd, departs_at"}.get(sort_by, "price_vnd, departs_at")
    sql += f" ORDER BY {order} LIMIT ?"; params.append(_limit(limit))
    with db.conn() as c:
        return [transport_item(r) for r in c.execute(sql, params).fetchall()]


def nights_between(check_in: str | None, check_out: str | None) -> int | None:
    a, b = parse_date(check_in, "check_in"), parse_date(check_out, "check_out")
    if a and b:
        if b <= a:
            raise CatalogError("check_out phải sau check_in")
        return (b - a).days
    return None


def search_lodging(db: Database, city=None, max_price_per_night_vnd=None, amenities=None, kind=None,
                   limit=5, sort_by="rating") -> list[dict]:
    if kind not in (None, "", "hotel", "resort", "homestay", "hostel"):
        raise CatalogError("kind phải là hotel, resort, homestay hoặc hostel")
    maxp = _price(max_price_per_night_vnd, "max_price_per_night_vnd")
    sql, params = "SELECT * FROM lodging WHERE rooms_left > 0", []
    if city:
        sql += " AND city_norm = ?"; params.append(canon_city(city))
    if kind:
        sql += " AND kind = ?"; params.append(kind)
    if maxp is not None:
        sql += " AND price_per_night_vnd <= ?"; params.append(maxp)
    for a in (amenities or []):
        na = norm(a)
        if na:
            sql += " AND amenities_norm LIKE ?"; params.append(f"%{na}%")
    order = {"price": "price_per_night_vnd, rating DESC"}.get(sort_by, "rating DESC, price_per_night_vnd")
    sql += f" ORDER BY {order} LIMIT ?"; params.append(_limit(limit))
    with db.conn() as c:
        return [lodging_item(r) for r in c.execute(sql, params).fetchall()]


def search_tours(db: Database, city=None, max_price_per_person_vnd=None, max_days=None, query=None,
                 limit=5, sort_by="rating") -> list[dict]:
    maxp = _price(max_price_per_person_vnd, "max_price_per_person_vnd")
    sql, params = "SELECT * FROM tours WHERE slots_left > 0", []
    if city:
        sql += " AND city_norm = ?"; params.append(canon_city(city))
    if maxp is not None:
        sql += " AND price_per_person_vnd <= ?"; params.append(maxp)
    if max_days not in (None, ""):
        try:
            sql += " AND duration_days <= ?"; params.append(float(max_days))
        except (TypeError, ValueError) as exc:
            raise CatalogError("max_days phải là số") from exc
    order = {"price": "price_per_person_vnd, rating DESC"}.get(sort_by, "rating DESC, price_per_person_vnd")
    with db.conn() as c:
        rows = c.execute(sql + f" ORDER BY {order}", params).fetchall()
    tokens = _tokens(query)
    if tokens:
        rows = [r for r in rows if _score(tokens, r["name_norm"] + " " + r["highlights_norm"]) > 0]
    return [tour_item(r) for r in rows[: _limit(limit)]]


def vn_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso).astimezone(ICT)
