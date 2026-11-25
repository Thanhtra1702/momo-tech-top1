"""Kiểm thử giao diện thật bằng Chromium (Playwright) với LLM giả theo luật, không tốn chi phí API.

Cần:  pip install playwright && python -m playwright install chromium
Bỏ qua tự động nếu chưa cài. Đặt SCREENSHOT_DIR để lưu ảnh chụp màn hình.
"""

import os
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api")
import uvicorn  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DIST = ROOT / "frontend" / "dist"
pytestmark = pytest.mark.skipif(not (DIST / "index.html").is_file(), reason="chưa build frontend (npm run build)")

sys.path.insert(0, str(ROOT / "backend" / "scripts"))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def server(settings):
    from dev_server import RuleLLM

    from app.main import create_app

    app = create_app(settings.with_overrides(frontend_dir=str(DIST)), llm_factory=RuleLLM)
    port = free_port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(timeout=5)


@pytest.fixture()
def browser():
    with playwright_sync.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # chưa chạy `playwright install chromium`
            pytest.skip(f"không mở được Chromium: {type(exc).__name__}")
        yield b
        b.close()


def shot(page, name):
    d = os.environ.get("SCREENSHOT_DIR")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        page.wait_for_timeout(700)  # chờ hiệu ứng cuộn mượt và chuyển động kết thúc để ảnh không bị lệch
        page.screenshot(path=str(Path(d) / f"{name}.png"), full_page=os.environ.get("SCREENSHOT_FULL", "1") == "1")


def login(page, base):
    page.goto(base)
    page.get_by_label("Tên đăng nhập").fill("demo1")
    page.get_by_label("Mật khẩu").fill("momo2026")
    page.get_by_role("button", name="Đăng nhập").click()
    page.get_by_text("Bạn muốn đi đâu, xem gì?").wait_for()


def test_live_events_page_keeps_real_results_separate_from_demo(server, browser, monkeypatch):
    from app import live_events

    def fake_live_search(query, city_id):
        assert city_id is None
        return {"source": "Ticketbox MCP", "checked_at": "2026-11-25T09:00:00+00:00",
                "results": [{"id": "26853", "title": "Âm Nhạc & Quê Hương", "url": "https://ticketbox.vn/am-nhac-va-que-huong-26853",
                             "starts_at": "2026-12-12T12:30:00Z", "price_from_vnd": 700000}] if query == "Âm Nhạc" else [],
                "has_more": False, "notice": "Kiểm tra lần cuối trên Ticketbox."}

    monkeypatch.setattr(live_events, "search", fake_live_search)
    page = browser.new_page(viewport={"width": 390, "height": 844})
    login(page, server)
    page.locator('a[href="#/live-events"]').first.click()
    page.get_by_label("Tên sự kiện").fill("Lời Thề Biển Xanh")
    page.get_by_role("button", name="Tra cứu ngay").click()
    page.get_by_text("Không tìm thấy sự kiện khớp tên").wait_for()
    page.get_by_label("Tên sự kiện").fill("Âm Nhạc")
    page.get_by_role("button", name="Tra cứu ngay").click()
    link = page.get_by_role("link", name="Xem và mua trên Ticketbox")
    link.wait_for()
    assert link.get_attribute("href") == "https://ticketbox.vn/am-nhac-va-que-huong-26853"
    assert "Tra cứu lúc" in page.locator(".notice").inner_text()


@pytest.mark.parametrize("viewport", [{"width": 1280, "height": 800}, {"width": 390, "height": 844}])
def test_account_check_demo_requires_login_and_shows_evidence(server, browser, viewport):
    page = browser.new_page(viewport=viewport)
    page.goto(server + "/#/account-check")
    page.get_by_label("Tên đăng nhập").wait_for()
    login(page, server)
    page.get_by_role("link", name="Kiểm tra tài khoản").click()
    page.get_by_role("button", name="Giả nhân viên đặt phòng").click()
    page.get_by_role("button", name="Kiểm tra dấu hiệu").click()
    risk = page.get_by_label("Kết quả kiểm tra rủi ro")
    risk.wait_for()
    assert "Chưa xác minh danh tính" in page.locator(".notice").inner_text()
    assert "OTP" in risk.inner_text()
    assert "Rủi ro" in risk.inner_text()
    overflowing = page.evaluate("""() => [...document.querySelectorAll('*')]
      .filter(el => el.getBoundingClientRect().right > window.innerWidth + 1)
      .map(el => [el.tagName, el.className, Math.round(el.getBoundingClientRect().right)]).slice(0, 12)""")
    assert not overflowing, overflowing


@pytest.mark.parametrize("viewport,tag", [({"width": 1280, "height": 800}, "desktop"), ({"width": 390, "height": 844}, "mobile")])
def test_full_flow_search_choose_confirm(server, browser, viewport, tag):
    page = browser.new_page(viewport=viewport)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto(server)
    shot(page, f"{tag}-0-login")
    login(page, server)
    shot(page, f"{tag}-1-welcome")

    page.get_by_role("button", name="Tìm vé xem phim cuối tuần này ở Sài Gòn dưới 150 nghìn").click()
    page.get_by_role("button", name="Chọn").first.wait_for(timeout=15000)
    assert page.get_by_role("button", name="Chọn").count() >= 2
    # markdown được hiển thị thành định dạng, không lộ dấu **
    page.locator("strong", has_text="bạn xem").wait_for()
    assert page.locator(".md li").count() == 2
    assert "**" not in page.locator(".msg.assistant").first.inner_text()
    shot(page, f"{tag}-2-cards")

    page.get_by_role("button", name="Chọn").first.click()
    page.get_by_role("link", name="Xem và xác nhận đơn").wait_for(timeout=15000)
    shot(page, f"{tag}-3-draft")
    page.get_by_role("link", name="Xem và xác nhận đơn").click()

    page.get_by_text("Đơn nháp, chưa thanh toán").wait_for()
    assert "Đơn nháp còn hiệu lực" in page.get_by_role("timer").inner_text()
    confirm = page.get_by_role("button", name="Xác nhận thanh toán (mô phỏng)")
    assert confirm.is_disabled()  # phải đánh dấu đã xem lại trước
    page.get_by_label("Tôi đã xem lại sản phẩm").check()
    shot(page, f"{tag}-4-order")
    confirm.click()
    page.get_by_text("Đặt chỗ thành công (mô phỏng)").wait_for()
    shot(page, f"{tag}-5-confirmed")
    assert not errors, errors


def test_reload_restores_conversation_and_new_chat_clears_it(server, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    login(page, server)
    page.get_by_label("Tin nhắn").fill("tìm phim cho mình")
    page.get_by_role("button", name="Gửi").click()
    page.get_by_role("button", name="Chọn").first.wait_for(timeout=15000)
    page.reload()
    page.get_by_role("button", name="Chọn").first.wait_for(timeout=15000)  # thẻ vé vẫn còn sau khi tải lại
    assert "tìm phim cho mình" in page.locator(".msg.user").first.inner_text()
    page.get_by_role("button", name="Cuộc mới").click()
    page.get_by_text("Bạn muốn đi đâu, xem gì?").wait_for()
    assert page.get_by_role("button", name="Chọn").count() == 0


def send(page, text):
    page.get_by_label("Tin nhắn").fill(text)
    page.get_by_role("button", name="Gửi").click()


@pytest.mark.parametrize("viewport,tag", [({"width": 1280, "height": 800}, "desktop"), ({"width": 390, "height": 844}, "mobile")])
def test_scam_report_budget_and_split_blocks(server, browser, viewport, tag):
    page = browser.new_page(viewport=viewport)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)  # gồm cả vi phạm CSP
    login(page, server)

    send(page, "Kiểm tra giúp mình tin nhắn này: chuyển khoản trước ngay vào STK cá nhân, chỉ còn 2 vé cuối http://momo-sale.xyz/nhan-qua")
    risk = page.get_by_label("Kết quả kiểm tra rủi ro")
    risk.wait_for(timeout=15000)
    text = risk.inner_text()
    assert "momo-sale.xyz" in text and "Nên làm" in text and "không phải kết luận" in text
    assert "Rủi ro" in text
    shot(page, f"{tag}-8-risk")

    send(page, "Tạo chuyến đi Đà Lạt ngân sách 8 triệu")
    bar = page.get_by_role("progressbar")
    bar.wait_for(timeout=15000)
    assert bar.get_attribute("aria-valuenow") == "0"
    send(page, "Ghi khoản chi ăn tối")
    page.get_by_text("450.000").first.wait_for(timeout=15000)
    shot(page, f"{tag}-9-budget")

    send(page, "Chia tiền khách sạn cho cả nhóm")
    page.get_by_label("Chia tiền").wait_for(timeout=15000)
    assert page.get_by_text("Bình gửi An 1.000.000đ cho tiền khách sạn.").is_visible()
    page.get_by_role("button", name="Sao chép tin nhắn nhắc").wait_for()
    shot(page, f"{tag}-10-split")
    assert not errors, errors


def test_quick_replies_and_orders_page(server, browser):
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    login(page, server)
    send(page, "tìm chuyến bay đi Đà Nẵng")
    page.get_by_role("button", name="Chọn").first.wait_for(timeout=15000)
    chips = page.get_by_label("Gợi ý trả lời nhanh")
    chips.wait_for()
    assert "Tìm khách sạn ở Đà Nẵng" in chips.inner_text()
    page.get_by_role("button", name="Chọn").first.click()
    page.get_by_role("link", name="Xem và xác nhận đơn").wait_for(timeout=15000)
    page.get_by_role("link", name="Xem và xác nhận đơn").click()
    page.get_by_label("Tôi đã xem lại sản phẩm").check()
    page.get_by_role("button", name="Xác nhận thanh toán (mô phỏng)").click()
    page.get_by_text("Đặt chỗ thành công (mô phỏng)").wait_for()

    page.get_by_role("link", name="Đơn của tôi").click()
    page.get_by_role("heading", name="Đơn và chuyến đi của tôi").wait_for()
    page.get_by_label("Đã xác nhận").locator(".order-row").first.wait_for(timeout=10000)  # danh sách tải bất đồng bộ
    upcoming = page.get_by_label("Sắp tới")
    assert upcoming.locator("li").count() == 1 and "1 ×" in upcoming.inner_text()
    assert page.get_by_label("Đã xác nhận").locator(".order-row").count() == 1
    assert "Không có đơn nháp" in page.get_by_label("Đơn nháp").inner_text()
    shot(page, "desktop-11-orders")
    page.get_by_role("link", name="Quay lại trò chuyện").click()
    page.get_by_role("button", name="Chọn").first.wait_for(timeout=15000)  # cuộc trò chuyện được khôi phục khi quay lại


def test_itinerary_comparison_and_memory_panel(server, browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    login(page, server)
    page.get_by_label("Tin nhắn").fill("Lên kế hoạch lịch trình Đà Lạt")
    page.get_by_role("button", name="Gửi").click()
    page.get_by_text("Tổng chi phí:").wait_for(timeout=15000)
    shot(page, "mobile-6-itinerary")
    page.get_by_role("button", name="Bộ nhớ").click()
    page.get_by_text("Trợ lý đang nhớ về bạn").wait_for()
    shot(page, "mobile-7-memory")


def test_wrong_password_shows_error_and_logout_works(server, browser):
    page = browser.new_page()
    page.goto(server)
    page.get_by_label("Tên đăng nhập").fill("demo1")
    page.get_by_label("Mật khẩu").fill("sai")
    page.get_by_role("button", name="Đăng nhập").click()
    page.get_by_role("alert").wait_for()
    assert "Sai tên đăng nhập" in page.get_by_role("alert").inner_text()
    login(page, server)
    page.get_by_role("button", name="Đăng xuất").click()
    page.get_by_role("button", name="Đăng nhập").wait_for()
