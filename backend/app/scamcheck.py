"""Kiểm tra dấu hiệu lừa đảo trong tin nhắn người bán và đường link. Bộ luật xác định, không gọi LLM.

Nguyên tắc: chỉ nêu "dấu hiệu rủi ro" kèm bằng chứng trích từ chính nội dung, không kết luận ai đó là lừa đảo.
Không thấy dấu hiệu không có nghĩa là an toàn. Danh sách tên miền chính thức chỉ là mẫu, cần cập nhật khi dùng thật.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

MAX_TEXT = 4000


def fold(text: str) -> str:
    """Hạ chữ thường và bỏ dấu tiếng Việt nhưng GIỮ NGUYÊN ĐỘ DÀI, để vị trí khớp trỏ đúng về văn bản gốc."""
    out = []
    for ch in text:
        if ch in "đĐ":
            out.append("d")
            continue
        base = unicodedata.normalize("NFD", ch)[:1]
        out.append(base.lower() if base else ch.lower())
    return "".join(out)


# --- tín hiệu văn bản ---------------------------------------------------------------------------
@dataclass(frozen=True)
class TextRule:
    code: str
    label: str
    weight: int
    severity: str
    patterns: tuple[str, ...]


TEXT_RULES: tuple[TextRule, ...] = (
    TextRule("sensitive_info", "Đòi mã OTP, mật khẩu, số thẻ hoặc giấy tờ cá nhân", 50, "high", (
        # phải có động từ yêu cầu đi kèm: nhắc "mang CCCD" hay tin nhắn OTP thật của ngân hàng không bị báo
        r"\b(gui|doc|cung\s+cap|nhap|cho\s+(em|minh|toi|chung\s+toi|ben\s+em)|chup|xac\s+minh|bao\s+cho)\b.{0,30}"
        r"(\botp\b|ma\s+xac\s+(thuc|nhan|minh)|mat\s+khau|\bcvv\b|\bcvc\b|so\s+the\b|\bcccd\b|can\s+cuoc|\bma\s+pin\b|thong\s+tin\s+dang\s+nhap)",
        r"(\botp\b|ma\s+xac\s+(thuc|nhan|minh)|mat\s+khau|\bcvv\b|so\s+the\b|\bcccd\b)\b.{0,20}\b(de\s+(mo\s+khoa|xac\s+minh|nhan)|ngay\b)",
    )),
    TextRule("remote_access", "Yêu cầu cài ứng dụng điều khiển từ xa hoặc tệp lạ", 50, "high", (
        r"anydesk", r"ultraviewer", r"teamviewer", r"\bapk\b", r"cai\s+(dat\s+)?(app|ung\s+dung)", r"tai\s+(app|ung\s+dung)\s+(ve|de)",
    )),
    TextRule("fee_to_receive", "Đòi nộp phí trước để nhận tiền, quà hoặc giải ngân", 45, "high", (
        r"phi\s+(nhan|rut|giai\s+ngan|kich\s+hoat|xac\s+minh|bao\s+hiem)", r"dong\s+phi\s+(de|truoc)",
    )),
    TextRule("off_platform_payment", "Yêu cầu chuyển khoản ngoài kênh thanh toán có bảo vệ", 30, "high", (
        r"chuyen\s+khoan\s+(coc\s+)?(truoc|ngay|vao)", r"chuyen\s+(tien|khoan)\b.{0,40}(tai\s+khoan|stk)\s+ca\s+nhan",
        r"chuyen\s+ngoai", r"khong\s+(qua|dung)\s+(san|app|ung\s+dung)", r"\bchuyen\s+(em|minh|anh|chi)\s+truoc\b",
        r"\bgui\s+tien\s+(qua|vao)\b",
    )),
    TextRule("payment_details", "Nhắc đến đặt cọc hoặc số tài khoản, cần kiểm chứng người nhận", 12, "low", (
        r"dat\s+coc", r"coc\s+truoc", r"\bstk\b", r"so\s+tai\s+khoan",
    )),
    TextRule("impersonation", "Tự nhận là nhân viên, ngân hàng, cơ quan chức năng", 25, "medium", (
        r"nhan\s+vien\s+(momo|ngan\s+hang|ho\s+tro|bao\s+mat)", r"\bcong\s+an\b", r"\btoa\s+an\b", r"\bbuu\s+dien\b",
        r"bo\s+phan\s+(bao\s+mat|xac\s+minh|cham\s+soc)", r"\bcskh\b", r"tai\s+khoan\s+(cua\s+ban\s+)?(bi\s+)?(khoa|han\s+che)",
    )),
    TextRule("urgency", "Tạo áp lực phải làm ngay", 20, "medium", (
        r"\bgap\b", r"ngay\s+bay\s+gio", r"nhanh\s+(tay|keo)", r"\bcon\s+\d+\s+(ve|suat|phong|slot)\s+(cuoi|duy\s+nhat)",
        r"chi\s+con\s+\d+\s+(ve|cho|suat|phong|slot)", r"het\s+han", r"keo\s+het", r"trong\s+vong\s+\d+\s*(phut|gio|p\b)",
        r"\d+\s+(tieng|phut)\s+nua", r"cuoi\s+cung",
    )),
    TextRule("too_good_price", "Giá hoặc ưu đãi bất thường", 20, "medium", (
        r"giam\s+(den\s+)?[5-9]\d\s*%", r"gia\s+soc", r"re\s+vo\s+dich", r"\b0\s*d\b", r"tang\s+ve", r"(nhan|tang|trung)\s+.{0,20}mien\s+phi",
        r"trung\s+thuong", r"qua\s+tang", r"nhan\s+thuong",
    )),
    TextRule("move_off_app", "Kéo sang kênh chat riêng khó kiểm chứng", 15, "low", (
        r"\bzalo\b", r"telegram", r"whatsapp", r"\bviber\b", r"nhan\s+tin\s+rieng", r"lien\s+he\s+qua", r"\binbox\b",
    )),
)

# --- link ----------------------------------------------------------------------------------------
OFFICIAL_DOMAINS = {  # tên miền chính thức (danh sách mẫu) -> tên hiển thị
    "momo.vn": "MoMo", "vietjetair.com": "Vietjet Air", "vietnamairlines.com": "Vietnam Airlines",
    "bambooairways.com": "Bamboo Airways", "traveloka.com": "Traveloka", "agoda.com": "Agoda", "booking.com": "Booking.com",
    "ticketbox.vn": "Ticketbox", "cgv.vn": "CGV", "galaxycine.vn": "Galaxy Cinema", "vexere.com": "Vexere",
    "futabus.vn": "Futa Bus Lines", "dsvn.vn": "Đường sắt Việt Nam",
}
BRAND_KEYWORDS = {  # từ khóa thương hiệu -> tên miền chính thức
    "momo": "momo.vn", "vietjet": "vietjetair.com", "vietnamairlines": "vietnamairlines.com", "bambooairways": "bambooairways.com",
    "traveloka": "traveloka.com", "agoda": "agoda.com", "booking": "booking.com", "ticketbox": "ticketbox.vn",
    "cgv": "cgv.vn", "galaxycine": "galaxycine.vn", "vexere": "vexere.com", "futabus": "futabus.vn", "dsvn": "dsvn.vn",
}
SHORTENERS = {"bit.ly", "tinyurl.com", "cutt.ly", "t.ly", "rebrand.ly", "is.gd", "s.id", "shorturl.at", "ow.ly", "tiny.cc", "goo.gl"}
SUSPICIOUS_TLDS = {"xyz", "top", "click", "icu", "vip", "cc", "buzz", "cfd", "sbs", "rest", "fun", "live", "site", "online", "link"}
SECOND_LEVEL = {"com", "net", "org", "edu", "gov", "co"}  # dạng .com.vn, .net.vn, .co.uk
URL_RE = re.compile(
    r"(?i)(?:https?://|www\.)[^\s<>\"'()]+|\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:com|vn|net|org|xyz|top|click|icu|vip|cc|site|online|shop|info|link|me|ly|app|buzz|cfd|sbs|id)\b(?:/[^\s<>\"'()]*)?")


def registered_domain(host: str) -> str:
    labels = host.split(".")
    if len(labels) >= 3 and labels[-2] in SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _lookalike(host: str) -> str:
    """Quy các ký tự hay bị tráo (0→o, 1→l, rn→m) và bỏ gạch ngang để bắt tên miền nhái thương hiệu."""
    h = host.replace("0", "o").replace("1", "l").replace("rn", "m").replace("-", "").replace(".", "")
    return h


def analyze_url(raw: str) -> dict:
    url = raw.rstrip(".,;:!?)")
    parsed = urlparse(url if "://" in url else "http://" + url if not url.lower().startswith("www.") else "http://" + url)
    issues: list[dict] = []
    score = 0

    def add(code: str, label: str, weight: int) -> None:
        nonlocal score
        issues.append({"code": code, "label": label})
        score += weight

    netloc = parsed.netloc
    host = (parsed.hostname or "").lower()
    if "@" in netloc:
        add("userinfo_trick", "Địa chỉ chứa ký tự @ để đánh lừa phần tên miền thật", 45)
    if url.lower().startswith("http://"):
        add("no_https", "Không dùng HTTPS", 15)
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
        add("ip_host", "Dùng địa chỉ IP thay vì tên miền", 40)
    if "xn--" in host or any(ord(c) > 127 for c in host):
        add("punycode", "Tên miền chứa ký tự lạ có thể nhái chữ quen thuộc", 35)
    reg = registered_domain(host)
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if reg in SHORTENERS:
        add("shortener", "Link rút gọn che giấu địa chỉ đích", 25)
    if tld in SUSPICIOUS_TLDS:
        add("suspicious_tld", f"Đuôi tên miền .{tld} hay bị lạm dụng", 15)
    if host.count(".") >= 4:
        add("many_subdomains", "Quá nhiều tên miền con", 10)
    if host.count("-") >= 3:
        add("many_hyphens", "Tên miền chứa nhiều dấu gạch ngang", 10)

    official = OFFICIAL_DOMAINS.get(reg)
    if not official:
        flat = _lookalike(host)
        for keyword, real in BRAND_KEYWORDS.items():
            if keyword in flat and reg != real:
                add("brand_impersonation", f"Tên miền có chữ \"{keyword}\" nhưng không phải trang chính thức ({real})", 50)
                break
    return {"url": url[:200], "host": host, "registered_domain": reg, "official_for": official,
            "issues": issues, "score": min(score, 80)}


# --- tổng hợp --------------------------------------------------------------------------------
LEVELS = ((70, "critical", "Rất nhiều dấu hiệu rủi ro"), (45, "high", "Nhiều dấu hiệu rủi ro"),
          (20, "medium", "Có một số dấu hiệu rủi ro"), (0, "low", "Ít dấu hiệu rủi ro"))

ADVICE = {
    "critical": ["Không chuyển tiền, không cung cấp OTP, mật khẩu, số thẻ hay giấy tờ cho người này.",
                 "Tự mở trang hoặc ứng dụng chính thức (gõ địa chỉ thủ công, không bấm link trong tin nhắn) để kiểm tra lại.",
                 "Nếu đã chuyển tiền hoặc lộ thông tin: liên hệ ngân hàng ngay để khóa hoặc đổi thông tin, và trình báo cơ quan chức năng."],
    "high": ["Tạm dừng, không chuyển tiền hay gửi thông tin nhạy cảm.",
             "Đối chiếu với trang chính thức của đơn vị hoặc đặt vé qua kênh có bảo vệ người mua.",
             "Yêu cầu người bán chứng minh danh tính và giấy phép trước khi thanh toán."],
    "medium": ["Cẩn trọng, kiểm tra thêm trước khi thanh toán.",
               "Ưu tiên thanh toán qua kênh có bảo vệ thay vì chuyển khoản trực tiếp cho cá nhân."],
    "low": ["Không thấy dấu hiệu rõ ràng, nhưng điều này không có nghĩa là an toàn.",
            "Vẫn nên đặt vé qua kênh chính thức và giữ lại bằng chứng giao dịch."],
}


def check(text: str) -> dict:
    text = (text or "")[:MAX_TEXT]
    if not text.strip():
        raise ValueError("Cần dán nội dung tin nhắn hoặc link để kiểm tra")
    folded = fold(text)
    signals: list[dict] = []
    score = 0
    for rule in TEXT_RULES:
        for pat in rule.patterns:
            m = re.search(pat, folded)
            if m:
                evidence = text[m.start():m.end()].strip()[:60]
                signals.append({"code": rule.code, "label": rule.label, "severity": rule.severity, "evidence": evidence})
                score += rule.weight
                break
    urls = [analyze_url(m.group(0)) for m in URL_RE.finditer(text)][:5]
    for u in urls:
        score += u["score"]
        for issue in u["issues"]:
            if issue["code"] in ("brand_impersonation", "userinfo_trick", "ip_host", "punycode"):
                signals.append({"code": issue["code"], "label": issue["label"], "severity": "high", "evidence": u["host"][:60], "from_url": True})
    # Kết hợp nguy hiểm: ép chuyển khoản ngoài kênh cộng với áp lực thời gian hoặc giá quá rẻ
    codes = {s["code"] for s in signals}
    if "off_platform_payment" in codes and codes & {"urgency", "too_good_price"}:
        score += 10
    score = min(score, 100)
    level, headline = next((lv, hd) for threshold, lv, hd in LEVELS if score >= threshold)
    return {"score": score, "level": level, "headline": headline, "signals": signals, "urls": urls, "advice": ADVICE[level],
            "disclaimer": "Đây là phân tích dấu hiệu bằng luật tự động, không phải kết luận ai đó lừa đảo."}


def risk_block(report: dict) -> dict:
    return {
        "kind": "risk_report", "level": report["level"], "score": report["score"], "headline": report["headline"],
        "signals": [{"label": s["label"], "severity": s["severity"], **({"evidence": s["evidence"]} if s.get("evidence") else {})}
                    for s in report["signals"] if not s.get("from_url")],  # lỗi của link đã hiện ở mục link
        "urls": [{"host": u["host"], "verdict": "official" if u["official_for"] and not u["issues"] else "risky" if u["issues"] else "unknown",
                  "issues": [i["label"] for i in u["issues"]]} for u in report["urls"]],
        "advice": report["advice"],
    }
