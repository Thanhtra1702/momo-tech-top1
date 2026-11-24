import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app import catalog
from app.seed import ensure_seeded, now_ict
from app.textutil import canon_city, norm

SCHEMAS = Path(__file__).resolve().parents[2] / "contracts" / "schemas"


def _validator(name):
    return Draft202012Validator(json.loads((SCHEMAS / f"{name}.json").read_text(encoding="utf-8")))


def test_norm_and_city_aliases():
    assert norm("Đà Lạt") == "da lat"
    assert canon_city("Sài Gòn") == "ho chi minh"
    assert canon_city("TP.HCM") == "ho chi minh"
    assert canon_city("thành phố Đà Nẵng") == "da nang"
    assert canon_city("Hà Nội") == "ha noi"


def test_seed_volume_and_schema(db):
    with db.conn() as c:
        counts = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("events", "transport", "lodging", "tours")}
    assert counts["events"] >= 300 and counts["transport"] >= 300
    assert counts["lodging"] >= 100 and counts["tours"] >= 30
    checks = {
        "event": (_validator("event"), lambda c: c.execute("SELECT * FROM events LIMIT 400").fetchall(), catalog.event_item),
        "transport": (_validator("transport"), lambda c: c.execute("SELECT * FROM transport LIMIT 400").fetchall(), catalog.transport_item),
        "lodging": (_validator("lodging"), lambda c: c.execute("SELECT * FROM lodging").fetchall(), catalog.lodging_item),
        "tour": (_validator("tour"), lambda c: c.execute("SELECT * FROM tours").fetchall(), catalog.tour_item),
    }
    with db.conn() as c:
        for name, (v, fetch, build) in checks.items():
            for row in fetch(c):
                errs = list(v.iter_errors(build(row)))
                assert not errs, (name, row["id"], errs[0].message)


def test_search_transport_by_route_date_price(db):
    rows = catalog.search_transport(db, origin="Hà Nội", destination="Đà Nẵng", mode="flight", max_price_vnd=1500000, limit=10)
    assert rows
    assert all(r["origin"] == "Hà Nội" and r["destination"] == "Đà Nẵng" and r["mode"] == "flight" for r in rows)
    assert all(r["price_vnd"] <= 1500000 for r in rows)
    assert [r["price_vnd"] for r in rows] == sorted(r["price_vnd"] for r in rows)
    target = rows[0]["departs_at"][:10]
    same_day = catalog.search_transport(db, origin="HN", destination="Da Nang", date=target)
    assert same_day and all(r["departs_at"].startswith(target) for r in same_day)


def test_search_events_filters(db):
    rows = catalog.search_events(db, kind="movie", city="Sài Gòn", max_price_vnd=100000, limit=10)
    assert rows and all(r["kind"] == "movie" and r["city"] == "TP. Hồ Chí Minh" and r["price_vnd"] <= 100000 for r in rows)
    assert all(r["seats_left"] > 0 for r in rows)
    by_tag = catalog.search_events(db, query="kinh dị", kind="movie", limit=5)
    assert by_tag and all("kinh dị" in r["tags"] for r in by_tag)


def test_search_lodging_amenities_and_price(db):
    rows = catalog.search_lodging(db, city="Đà Lạt", max_price_per_night_vnd=1000000, amenities=["hồ bơi"], limit=10)
    assert all("hồ bơi" in r["amenities"] and r["price_per_night_vnd"] <= 1000000 and r["city"] == "Đà Lạt" for r in rows)


def test_search_tours_filters(db):
    rows = catalog.search_tours(db, city="Đà Lạt", max_days=3, max_price_per_person_vnd=3000000)
    assert rows and all(r["duration_days"] <= 3 and r["price_per_person_vnd"] <= 3000000 for r in rows)


def test_invalid_args_raise_clear_errors(db):
    with pytest.raises(catalog.CatalogError, match="YYYY-MM-DD"):
        catalog.search_transport(db, origin="Hà Nội", date="mai")
    with pytest.raises(catalog.CatalogError):
        catalog.search_events(db, kind="opera")
    with pytest.raises(catalog.CatalogError):
        catalog.search_events(db, max_price_vnd="rẻ")


def test_limit_is_capped(db):
    assert len(catalog.search_events(db, limit=999)) <= catalog.MAX_LIMIT


def test_get_item_roundtrip(db):
    first = catalog.search_transport(db, origin="Hà Nội", destination="Huế", limit=1)[0]
    kind, item = catalog.get_item(db, first["id"])
    assert kind == "transport" and item == first
    assert catalog.get_item(db, "trp_missing") is None
    assert catalog.get_item(db, "zzz_1") is None


def test_ensure_seeded_is_idempotent_when_fresh(db):
    assert ensure_seeded(db) is False


def test_generic_words_in_query_do_not_empty_results(db):
    # Mô hình hay đặt kind vào cả query ("concert"); từ này không có trong tên nên từng làm kết quả rỗng.
    plain = catalog.search_events(db, kind="concert", city="Sài Gòn", limit=10)
    with_word = catalog.search_events(db, query="concert", kind="concert", city="Sài Gòn", limit=10)
    assert plain and [r["id"] for r in plain] == [r["id"] for r in with_word]
    assert catalog.search_events(db, query="vé phim cuối tuần", kind="movie", limit=3)
    assert not catalog.search_events(db, query="zzzzqqq")
    assert catalog.search_tours(db, city="Nha Trang", query="tour lặn biển")
