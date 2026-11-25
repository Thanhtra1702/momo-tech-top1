"""Tình huống tài khoản giả định, dựa trên mẫu cảnh báo từ nền tảng đặt phòng."""

from fastapi.testclient import TestClient

from app import accountcheck
from app.main import create_app

from .helpers import validator


def test_fake_support_account_with_cancel_threat_and_otp_is_high_risk():
    result = accountcheck.check_account(
        "Agoda Hỗ trợ 24/7", "https://facebook.com/agoda.hotro24h",
        "Đơn đặt phòng sẽ bị hủy nếu không xác minh thanh toán trong 10 phút. Nhắn Zalo và gửi mã OTP cho tôi.",
    )
    block = result["report"]
    assert result["identity_status"] == "unverified"
    assert block["level"] in ("high", "critical")
    assert any("OTP" in s["evidence"] for s in block["signals"] if "evidence" in s)
    assert not list(validator("ui_block").iter_errors(block))


def test_brand_lookalike_and_personal_transfer_are_flagged():
    result = accountcheck.check_account(
        "Traveloka CSKH", "https://traveloka-help.example.com",
        "Chuyển khoản trước vào STK cá nhân để giữ vé, chỉ còn 2 chỗ cuối.",
    )
    block = result["report"]
    assert block["level"] in ("high", "critical")
    assert any("traveloka.com" in issue for url in block["urls"] for issue in url["issues"])


def test_benign_contact_stays_unverified_without_fraud_claim():
    result = accountcheck.check_account("Khách sạn Hoa Sen", message="Phòng còn trống, hủy miễn phí trước 24 giờ.")
    assert result["identity_status"] == "unverified"
    assert result["report"]["level"] == "low"
    assert "Chưa xác minh" in result["report"]["headline"]


def test_brand_name_alone_is_not_proof_and_invalid_url_is_rejected():
    assert accountcheck.check_account("Traveloka CSKH")["report"]["level"] == "medium"
    try:
        accountcheck.check_account("Traveloka CSKH", "javascript:alert(1)")
    except ValueError:
        pass
    else:
        raise AssertionError("invalid URL accepted")


def test_account_check_api_requires_login_and_does_not_need_llm(settings):
    client = TestClient(create_app(settings.with_overrides(llm_api_key="")))
    data = {"account_name": "Agoda hỗ trợ", "message": "Gửi mã OTP cho tôi để xác minh đặt phòng"}
    assert client.post("/risk/account-check", json=data).status_code == 401
    token = client.post("/auth/login", json={"username": "demo1", "password": "momo2026"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/risk/account-check", json=data, headers=headers)
    assert response.status_code == 200
    assert response.json()["report"]["level"] in ("high", "critical")
    assert client.post("/risk/account-check", json={**data, "profile_url": "file:///secret"}, headers=headers).status_code == 422
