import { FormEvent, useState } from "react";
import { login } from "./api";
import { IconPlane } from "./icons";

export default function Login({ onDone }: { onDone: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username.trim(), password);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth">
      <div className="auth-card">
        <div className="logo" aria-hidden="true">
          <IconPlane size={18} />
        </div>
        <h1>Trợ lý Chuyến đi</h1>
        <p className="muted">Tìm vé, khách sạn và tour, kiểm tra người bán, theo dõi ngân sách và chia tiền nhóm trong một cuộc trò chuyện.</p>
        <form onSubmit={submit} className="login-form">
          <label>
            Tên đăng nhập
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
          </label>
          <label>
            Mật khẩu
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </label>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button className="btn-primary" disabled={busy}>
            {busy ? "Đang đăng nhập..." : "Đăng nhập"}
          </button>
        </form>
        <p className="muted small">Dùng tài khoản dùng thử ghi trong tài liệu hướng dẫn. Dữ liệu vé và thanh toán là mô phỏng.</p>
      </div>
    </main>
  );
}