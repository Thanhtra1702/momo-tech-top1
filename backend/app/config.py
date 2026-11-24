"""Cấu hình đọc từ biến môi trường. Khóa API không bao giờ nằm trong mã nguồn."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path


def load_dotenv(paths: list[Path] | None = None) -> list[Path]:
    """Nạp file .env (KEY=VALUE) vào os.environ. Biến đã có giá trị sẵn không bị ghi đè. Trả về các file đã đọc."""
    here = Path(__file__).resolve()
    candidates = paths if paths is not None else [here.parents[2] / ".env", here.parents[1] / ".env", Path.cwd() / ".env"]
    loaded: list[Path] = []
    for p in candidates:
        if not p.is_file() or p in loaded:
            continue
        for raw in p.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key and not os.environ.get(key):
                os.environ[key] = value
        loaded.append(p)
    return loaded


def resolve_frontend_dir(configured: str = "") -> Path | None:
    """Tìm thư mục giao diện đã build. Ưu tiên giá trị cấu hình, rồi các vị trí thông dụng.

    Cấu hình sai (đường dẫn tương đối lệch thư mục chạy) không còn làm mất giao diện: tự dò tiếp.
    """
    here = Path(__file__).resolve()
    candidates = [Path(configured)] if configured else []
    candidates += [here.parents[2] / "frontend" / "dist", Path("/srv/frontend_dist"), here.parents[2] / "frontend_dist",
                   Path.cwd() / "frontend_dist", Path.cwd().parent / "frontend" / "dist"]
    for c in candidates:
        if (c / "index.html").is_file():
            return c
    return None


def _f(name: str, default: str) -> float:
    return float(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    llm_api_key: str = ""
    llm_timeout_s: float = 60.0
    frontend_dir: str = ""  # rỗng: tự dò (xem resolve_frontend_dir)
    db_path: str = "data/app.db"
    # Tài khoản demo cho ban giám khảo, dạng "user:mật khẩu,user2:mật khẩu2".
    demo_users: str = "demo1:momo2026,demo2:momo2026,demo3:momo2026"
    max_agent_steps: int = 6
    rate_limit_per_min: int = 12
    daily_cost_cap_usd: float = 5.0
    user_daily_cost_cap_usd: float = 1.0
    session_ttl_s: int = 24 * 3600
    admin_token: str = ""  # rỗng nghĩa là tắt /admin/costs
    images_enabled: bool = True  # tắt nếu API không nhận ảnh (xem docs/deepseek-spike.md)
    # "production" bắt buộc đổi tài khoản demo mặc định và không cho chạy với mật khẩu yếu. Docker đặt mặc định này.
    app_env: str = "development"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        d = cls()
        return cls(
            llm_base_url=os.environ.get("LLM_BASE_URL", d.llm_base_url),
            llm_model=os.environ.get("LLM_MODEL", d.llm_model),
            llm_api_key=os.environ.get("LLM_API_KEY", ""),
            llm_timeout_s=_f("LLM_TIMEOUT_S", str(d.llm_timeout_s)),
            frontend_dir=os.environ.get("FRONTEND_DIR", d.frontend_dir),
            db_path=os.environ.get("DB_PATH", d.db_path),
            demo_users=os.environ.get("DEMO_USERS", d.demo_users),
            max_agent_steps=int(os.environ.get("MAX_AGENT_STEPS", d.max_agent_steps)),
            rate_limit_per_min=int(os.environ.get("RATE_LIMIT_PER_MIN", d.rate_limit_per_min)),
            daily_cost_cap_usd=_f("DAILY_COST_CAP_USD", str(d.daily_cost_cap_usd)),
            user_daily_cost_cap_usd=_f("USER_DAILY_COST_CAP_USD", str(d.user_daily_cost_cap_usd)),
            session_ttl_s=int(os.environ.get("SESSION_TTL_S", d.session_ttl_s)),
            admin_token=os.environ.get("ADMIN_TOKEN", ""),
            images_enabled=os.environ.get("IMAGES_ENABLED", "true").lower() not in ("0", "false", "no"),
            app_env=os.environ.get("APP_ENV", d.app_env).lower(),
        )

    def production_problems(self) -> list[str]:
        """Danh sách vấn đề cấu hình không chấp nhận được khi chạy thật. Rỗng nghĩa là ổn."""
        problems: list[str] = []
        if not self.llm_api_key:
            problems.append("thiếu LLM_API_KEY")
        users = dict(p.split(":", 1) for p in self.demo_users.split(",") if ":" in p)
        if not users:
            problems.append("DEMO_USERS rỗng, không ai đăng nhập được")
        if self.demo_users == Settings().demo_users or any(pw in ("momo2026", "password", "123456") for pw in users.values()):
            problems.append("DEMO_USERS đang dùng mật khẩu mặc định hoặc quá yếu, hãy đặt mật khẩu riêng")
        weak = [u for u, pw in users.items() if len(pw) < 8]
        if weak:
            problems.append("mật khẩu dưới 8 ký tự: " + ", ".join(weak))
        if self.admin_token and len(self.admin_token) < 16:
            problems.append("ADMIN_TOKEN nên dài ít nhất 16 ký tự")
        return problems

    def with_overrides(self, **kw) -> "Settings":
        return replace(self, **kw)
