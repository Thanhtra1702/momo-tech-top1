"""Kiểm tra ảnh người dùng gửi. Ảnh chỉ nằm trong bộ nhớ trong lúc xử lý, không lưu đĩa và không giữ trong lịch sử."""

from __future__ import annotations

import base64
import binascii

MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_B64_CHARS = MAX_IMAGE_BYTES * 4 // 3 + 8
ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}


class ImageError(ValueError):
    pass


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def to_data_url(mime: str, b64: str) -> str:
    """Xác thực và trả về data URL. Tin vào nội dung byte, không tin khai báo mime."""
    if mime not in ALLOWED_MIME:
        raise ImageError("Chỉ nhận ảnh PNG, JPEG hoặc WEBP")
    if len(b64) > MAX_B64_CHARS:
        raise ImageError("Ảnh quá lớn, tối đa 4 MB")
    try:
        data = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageError("Dữ liệu ảnh không hợp lệ") from exc
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ImageError("Ảnh quá lớn, tối đa 4 MB")
    sniffed = _sniff(data)
    if sniffed is None or sniffed != mime:
        raise ImageError("Nội dung tệp không khớp định dạng ảnh đã khai báo")
    return f"data:{mime};base64,{b64}"
