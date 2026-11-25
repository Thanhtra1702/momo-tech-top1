import json
from datetime import timedelta

import pytest

from app import catalog, itinerary, memory, orders
from app.external import get_places, get_weather
from app.seed import now_ict
from app.tools import TOOL_SPECS, ToolContext, run_tool

from .helpers import validator


@pytest.fixture()
def ctx(db):
    return ToolContext(db=db, username="demo1")


def run(ctx, name, args):
    text, block, err = run_tool(ctx, name, json.dumps(args, ensure_ascii=False))
    return json.loads(text), block, err


def test_tool_specs_are_well_formed():
    names = [s["function"]["name"] for s in TOOL_SPECS]
    assert len(names) == len(set(names))
    assert "create_order_draft" in names
    # không có công cụ nào có thể xác nhận hay thanh toán
    assert not any("confirm" in n or "pay" in n for n in names)
    for s in TOOL_SPECS:
        assert s["function"]["parameters"]["type"] == "object"


@pytest.mark.parametrize("name,args", [
    ("search_events", {"kind": "concert", "city": "Sài Gòn"}),
    ("search_transport", {"origin": "Hà Nội", "destination": "Đà Nẵng", "mode": "flight"}),
    ("search_lodging", {"city": "Đà Lạt", "check_in": "2099-01-01", "check_out": "2099-01-03"}),
    ("search_tours", {"city": "Đà Lạt"}),
])
def test_search_tools_emit_valid_blocks_and_track_refs(ctx, name, args):
    data, block, err = run(ctx, name, args)
    assert not err and data["data"]["count"] > 0
    assert not list(validator("ui_block").iter_errors(block))
    assert {i["ref_id"] for i in block["items"]} <= ctx.seen_refs
    assert "_note" in data


def test_llm_payload_is_compact_but_ui_block_and_db_keep_full_data(ctx):
    text, block, err = run_tool(ctx, "search_transport", json.dumps({"origin": "Hà Nội", "destination": "Huế", "limit": 3}))
    assert not err and "deeplink" not in text
    assert text == json.dumps(json.loads(text), ensure_ascii=False, separators=(",", ":"))  # JSON không có khoảng trắng thừa
    items = json.loads(text)["data"]["items"]
    assert items and all({"id", "price_vnd", "seats_left", "departs_at"} <= set(i) for i in items)
    assert block["items"][0]["ref_id"] == items[0]["id"]
    # mã vẫn tạo được đơn và đơn vẫn giữ deeplink lấy từ DB
    ctx.seen_refs.add(items[0]["id"])
    d, _, e = run(ctx, "create_order_draft", {"items": [{"ref_id": items[0]["id"], "quantity": 1}]})
    assert not e and orders.get_order(ctx.db, "demo1", d["data"]["order_id"])["items"][0]["deeplink"].startswith("https://")


def test_lodging_nights_total_estimate(ctx):
    data, _, _ = run(ctx, "search_lodging", {"city": "Đà Lạt", "check_in": "2099-01-01", "check_out": "2099-01-04"})
    assert data["data"]["nights"] == 3
    for item in data["data"]["items"]:
        assert data["data"]["total_estimate_vnd"][item["id"]] == item["price_per_night_vnd"] * 3


def test_empty_result_gives_hint_and_no_block(ctx):
    data, block, err = run(ctx, "search_events", {"query": "zzzzqqq"})
    assert not err and data["data"]["count"] == 0 and block is None and "hint" in data["data"]


def test_movie_tool_never_returns_fictional_titles_or_cards(ctx):
    for args in ({"kind": "movie", "query": "Con Đường Gió Lộng"}, {}):
        data, block, err = run(ctx, "search_events", args)
        assert not err
        assert "Con Đường Gió Lộng" not in json.dumps(data, ensure_ascii=False)
        assert block is None or all(item["ref_id"][:6] != "evt_mv" for item in block["items"])
    assert data["data"]["count"] >= 0
    movie, _, _ = run(ctx, "search_events", {"kind": "movie"})
    assert movie["data"]["sources"] and movie["data"]["items"] == []
    old_movie = catalog.search_events(ctx.db, kind="movie", limit=1)[0]
    ctx.seen_refs.add(old_movie["id"])
    draft, block, err = run(ctx, "create_order_draft", {"items": [{"ref_id": old_movie["id"], "quantity": 1}]})
    assert err and block is None and "phim giả lập" in draft["error"]


def test_bad_args_return_error_to_llm_without_raising(ctx):
    for name, raw in [("search_transport", '{"origin": "Hà Nội", "date": "mai"}'),
                      ("search_events", "not json"), ("nope", "{}"), ("search_events", "[1,2]")]:
        text, block, err = run_tool(ctx, name, raw)
        assert err and block is None and "error" in json.loads(text)


def test_round_trip_search_returns_both_legs(ctx):
    out = catalog.search_transport(ctx.db, origin="Hà Nội", destination="Đà Nẵng", mode="flight", limit=1)[0]
    d_out = out["departs_at"][:10]
    from datetime import date as _d
    d_back = (_d.fromisoformat(d_out) + timedelta(days=2)).isoformat()
    data, block, err = run(ctx, "search_transport", {"origin": "Hà Nội", "destination": "Đà Nẵng", "date": d_out,
                                                      "return_date": d_back, "mode": "flight"})
    assert not err and not list(validator("ui_block").iter_errors(block))
    d = data["data"]
    assert d["outbound"] and d["inbound"]
    assert all(i["origin"] == "Hà Nội" and i["departs_at"].startswith(d_out) for i in d["outbound"])
    assert all(i["origin"] == "Đà Nẵng" and i["departs_at"].startswith(d_back) for i in d["inbound"])
    assert d["cheapest_round_trip_per_person_vnd"] == min(i["price_vnd"] for i in d["outbound"]) + min(i["price_vnd"] for i in d["inbound"])
    badges = [b for c in block["items"] for b in c["badges"]]
    assert "Chiều đi" in badges and "Chiều về" in badges
    assert {i["id"] for i in d["outbound"] + d["inbound"]} <= ctx.seen_refs
    # một chiều vẫn hoạt động như cũ, không có khóa khứ hồi
    one, _, _ = run(ctx, "search_transport", {"origin": "Hà Nội", "destination": "Đà Nẵng", "date": d_out})
    assert "outbound" not in one["data"]


def test_round_trip_with_missing_leg_gives_hint(ctx):
    data, block, err = run(ctx, "search_transport", {"origin": "Hà Nội", "destination": "Đà Nẵng", "return_date": "2001-01-01"})
    assert not err and data["data"]["inbound"] == [] and "chiều về" in data["data"]["hint"]


def test_compare_options_picks_cheapest_transport(ctx):
    items = catalog.search_transport(ctx.db, origin="Hà Nội", destination="Đà Nẵng", mode="flight", limit=3)
    data, block, err = run(ctx, "compare_options", {"ref_ids": [i["id"] for i in items]})
    assert not err and not list(validator("ui_block").iter_errors(block))
    cheapest = min(items, key=lambda i: i["price_vnd"])
    assert data["data"]["recommended_ref_id"] == cheapest["id"]


def test_compare_rejects_mixed_kinds(ctx):
    t = catalog.search_transport(ctx.db, origin="Hà Nội", destination="Huế", limit=1)[0]["id"]
    e = catalog.search_events(ctx.db, limit=1)[0]["id"]
    _, _, err = run(ctx, "compare_options", {"ref_ids": [t, e]})
    assert err


def test_weather_falls_back_to_estimate_when_api_fails(monkeypatch):
    def boom(lat, lon):
        raise RuntimeError("network down")

    w = get_weather("Đà Lạt", now_ict().date() + timedelta(days=1), fetcher=boom)
    assert w["source"] == "estimate" and 10 < w["temp_c"] < 35
    far = get_weather("Hà Nội", now_ict().date() + timedelta(days=200), fetcher=boom)
    assert far["source"] == "estimate"


def test_weather_uses_forecast_and_caches():
    tomorrow = now_ict().date() + timedelta(days=2)
    calls = []

    def fake(lat, lon):
        calls.append(1)
        return {"daily": {"time": [tomorrow.isoformat()], "temperature_2m_min": [17.0], "temperature_2m_max": [25.0],
                          "weathercode": [3], "precipitation_probability_max": [40]}}

    a = get_weather("Nha Trang", tomorrow, fetcher=fake)
    b = get_weather("Nha Trang", tomorrow, fetcher=fake)
    assert a["source"] == "open-meteo" and a["temp_c"] == 21.0 and a == b and len(calls) == 1


def test_places_and_unknown_city():
    assert get_places("Đà Lạt")
    with pytest.raises(ValueError):
        get_places("Paris")


# --- bộ nhớ ---------------------------------------------------------------------------------------
def test_memory_save_recall_delete_and_isolation(db):
    memory.save(db, "demo1", "home_city", "Hà Nội")
    memory.save(db, "demo1", "home_city", "Hải Phòng")
    memory.save(db, "demo2", "home_city", "Huế")
    assert memory.recall(db, "demo1") == {"home_city": "Hải Phòng"}
    assert memory.recall(db, "demo2") == {"home_city": "Huế"}
    assert memory.delete(db, "demo1", "home_city") and memory.recall(db, "demo1") == {}
    assert memory.recall(db, "demo2") == {"home_city": "Huế"}


@pytest.mark.parametrize("value", ["4111 1111 1111 1111", "0912345678", "a@b.com", "mật khẩu của tôi là 1", "OTP 123"])
def test_memory_rejects_sensitive(db, value):
    with pytest.raises(memory.MemoryValidationError):
        memory.save(db, "demo1", "interests", value)


def test_memory_rejects_unknown_key_and_long_value(db):
    with pytest.raises(memory.MemoryValidationError):
        memory.save(db, "demo1", "credit_card", "x")
    with pytest.raises(memory.MemoryValidationError):
        memory.save(db, "demo1", "interests", "x" * 500)


def test_memory_tools(ctx):
    _, _, err = run(ctx, "save_preference", {"key": "lodging_amenities", "value": "hồ bơi"})
    assert not err
    data, _, _ = run(ctx, "recall_memory", {})
    assert data["data"]["memory"] == {"lodging_amenities": "hồ bơi"}
    _, _, err = run(ctx, "save_preference", {"key": "interests", "value": "thẻ 4111111111111111"})
    assert err


# --- lịch trình -----------------------------------------------------------------------------------
def _start():
    return (now_ict().date() + timedelta(days=10)).isoformat()


def test_itinerary_total_equals_sum_and_valid(db):
    res = itinerary.build_itinerary(db, "Đà Lạt", 3, 8_000_000, 2, _start(), origin="Hà Nội")
    assert not list(validator("ui_block").iter_errors(res["block"]))
    entries = [e for d in res["block"]["days"] for e in d["entries"]]
    assert res["total_vnd"] == sum(e["cost_vnd"] for e in entries) == res["block"]["total_vnd"]
    assert len(res["block"]["days"]) == 3
    for d in res["block"]["days"]:
        times = [e["time"] for e in d["entries"]]
        assert times == sorted(times) and len(times) == len(set(times))
    for e in entries:
        if e.get("ref_id"):
            assert catalog.get_item(db, e["ref_id"])
    assert res["within_budget"] == (res["total_vnd"] <= 8_000_000)


def test_itinerary_has_no_duplicate_events_or_two_events_in_a_day(db):
    for city in ("Đà Lạt", "Hà Nội", "Đà Nẵng", "Huế"):
        res = itinerary.build_itinerary(db, city, 4, 30_000_000, 2, _start())
        events = [e for d in res["block"]["days"] for e in d["entries"] if e.get("ref_id", "").startswith("evt_")]
        titles = [e["title"] for e in events]
        assert len(titles) == len(set(titles)), (city, titles)
        for d in res["block"]["days"]:
            assert sum(1 for e in d["entries"] if e.get("ref_id", "").startswith("evt_")) <= 1


def test_itinerary_reports_when_over_budget(db):
    res = itinerary.build_itinerary(db, "Phú Quốc", 4, 500_000, 2, _start(), origin="Hà Nội")
    assert not res["within_budget"] and any("vượt ngân sách" in n for n in res["notes"])


def test_itinerary_validates_input(db):
    with pytest.raises(catalog.CatalogError):
        itinerary.build_itinerary(db, "Đà Lạt", 0, 1_000_000, 2, _start())
    with pytest.raises(catalog.CatalogError):
        itinerary.build_itinerary(db, "Đà Lạt", 2, 1_000_000, 2, "mai")


def test_itinerary_tool(ctx):
    data, block, err = run(ctx, "build_itinerary", {"city": "Đà Nẵng", "days": 2, "budget_vnd": 6_000_000, "guests": 2,
                                                     "start_date": _start()})
    assert not err and block["kind"] == "itinerary" and data["data"]["total_vnd"] == block["total_vnd"]


# --- đơn hàng -------------------------------------------------------------------------------------
def _flight(db):
    return catalog.search_transport(db, origin="Hà Nội", destination="Đà Nẵng", mode="flight", limit=1)[0]


def test_draft_tool_requires_seen_refs(ctx):
    f = _flight(ctx.db)
    data, block, err = run(ctx, "create_order_draft", {"items": [{"ref_id": f["id"], "quantity": 1}]})
    assert err and "chưa được hiển thị" in data["error"]
    ctx.seen_refs.add(f["id"])
    data, block, err = run(ctx, "create_order_draft", {"items": [{"ref_id": f["id"], "quantity": 2}]})
    assert not err and block["kind"] == "order_draft" and block["total_vnd"] == f["price_vnd"] * 2
    assert not list(validator("ui_block").iter_errors(block))
    order = orders.get_order(ctx.db, "demo1", data["data"]["order_id"])
    assert order["status"] == "draft"
    assert not list(validator("order_draft").iter_errors(order))


def test_confirm_flow_decrements_stock_once(db):
    f = _flight(db)
    draft = orders.create_draft(db, "demo1", [{"ref_id": f["id"], "quantity": 2}])
    done = orders.confirm(db, "demo1", draft["id"])
    assert done["status"] == "confirmed" and done["confirmed_at"]
    assert not list(validator("order_draft").iter_errors(done))
    assert catalog.get_item(db, f["id"])[1]["seats_left"] == f["seats_left"] - 2
    again = orders.confirm(db, "demo1", draft["id"])  # lặp lại không trừ thêm
    assert again["status"] == "confirmed"
    assert catalog.get_item(db, f["id"])[1]["seats_left"] == f["seats_left"] - 2


def test_confirm_detects_price_change_and_sold_out(db):
    f = _flight(db)
    d1 = orders.create_draft(db, "demo1", [{"ref_id": f["id"], "quantity": 1}])
    with db.conn() as c:
        c.execute("UPDATE transport SET price_vnd = price_vnd + 1000 WHERE id = ?", (f["id"],))
    with pytest.raises(orders.OrderError) as e:
        orders.confirm(db, "demo1", d1["id"])
    assert e.value.code == "conflict" and "thay đổi" in e.value.message
    assert orders.get_order(db, "demo1", d1["id"])["status"] == "draft"

    g = catalog.search_transport(db, origin="Hà Nội", destination="Huế", limit=1)[0]
    d2 = orders.create_draft(db, "demo1", [{"ref_id": g["id"], "quantity": 1}])
    with db.conn() as c:
        c.execute("UPDATE transport SET seats_left = 0 WHERE id = ?", (g["id"],))
    with pytest.raises(orders.OrderError) as e:
        orders.confirm(db, "demo1", d2["id"])
    assert "hết chỗ" in e.value.message


def test_confirm_rejects_reused_catalog_id_with_changed_schedule(db):
    flight = _flight(db)
    draft = orders.create_draft(db, "demo1", [{"ref_id": flight["id"], "quantity": 1}])
    with db.conn() as c:
        c.execute("UPDATE transport SET departs_at = '2027-01-01T12:00:00+07:00' WHERE id = ?", (flight["id"],))
    with pytest.raises(orders.OrderError) as error:
        orders.confirm(db, "demo1", draft["id"])
    assert error.value.code == "conflict" and "thay đổi" in error.value.message
    assert orders.get_order(db, "demo1", draft["id"])["status"] == "draft"
    assert catalog.get_item(db, flight["id"])[1]["seats_left"] == flight["seats_left"]


def test_orders_are_private_and_validated(db):
    f = _flight(db)
    d = orders.create_draft(db, "demo1", [{"ref_id": f["id"], "quantity": 1}])
    with pytest.raises(orders.OrderError):
        orders.get_order(db, "demo2", d["id"])
    with pytest.raises(orders.OrderError):
        orders.confirm(db, "demo2", d["id"])
    for bad in ([], [{"ref_id": f["id"], "quantity": 0}], [{"ref_id": f["id"], "quantity": 99}],
                [{"ref_id": "trp_nope", "quantity": 1}]):
        with pytest.raises(orders.OrderError):
            orders.create_draft(db, "demo1", bad)


def test_draft_expires(db, monkeypatch):
    f = _flight(db)
    d = orders.create_draft(db, "demo1", [{"ref_id": f["id"], "quantity": 1}])
    future = now_ict() + timedelta(minutes=45)
    monkeypatch.setattr(orders, "now_ict", lambda: future)
    assert orders.get_order(db, "demo1", d["id"])["status"] == "expired"
    with pytest.raises(orders.OrderError):
        orders.confirm(db, "demo1", d["id"])


def test_lodging_draft_counts_nights_but_needs_one_room(db):
    lod = catalog.search_lodging(db, city="Đà Lạt", limit=1)[0]
    d = orders.create_draft(db, "demo1", [{"ref_id": lod["id"], "quantity": 3}])
    assert d["total_vnd"] == lod["price_per_night_vnd"] * 3
    orders.confirm(db, "demo1", d["id"])
    assert catalog.get_item(db, lod["id"])[1]["rooms_left"] == lod["rooms_left"] - 1
