import { FormEvent, useState } from "react";
import { ApiError, checkAccount } from "./api";
import { RiskReport } from "./Blocks";
import type { UiBlock } from "./types";

type Risk = Extract<UiBlock, { kind: "risk_report" }>;

const EXAMPLES = [
  {
    label: "Giả nhân viên đặt phòng",
    account_name: "Agoda Hỗ trợ 24/7",
    profile_url: "https://facebook.com/agoda.hotro24h",
    message: "Đơn đặt phòng của bạn sẽ bị hủy nếu không xác minh thanh toán trong 10 phút. Nhắn Zalo và gửi mã OTP cho tôi.",
  },
  {
    label: "Link nhái thương hiệu",
    account_name: "Traveloka CSKH",
    profile_url: "https://traveloka-help.example.com",
    message: "Chuyển khoản trước vào STK cá nhân để giữ vé, chỉ còn 2 chỗ cuối.",
  },
  {
    label: "Chưa đủ bằng chứng",
    account_name: "Khách sạn Hoa Sen",
    profile_url: "",
    message: "Phòng còn trống, giá 850.000đ/đêm, hủy miễn phí trước 24 giờ.",
  },
];

export default function AccountCheckPage({ onAuthLost }: { onAuthLost: () => void }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [message, setMessage] = useState("");
  const [report, setReport] = useState<Risk | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setReport(null);
    setBusy(true);
    try {
      const result = await checkAccount({ account_name: name, profile_url: url, message });
      setReport(result.report);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onAuthLost();
      else setError(err instanceof Error ? err.message : "Không kiểm tra được tài khoản.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="page account-check">
      <h1>Kiểm tra tài khoản liên hệ</h1>
      <p className="muted">Dán thông tin tài khoản vừa liên hệ về vé hoặc nơi lưu trú. Công cụ kiểm tra dấu hiệu trong nội dung; không xác minh chủ tài khoản với Agoda, Traveloka hay MoMo.</p>
      <div className="account-examples" aria-label="Tình huống demo">
        {EXAMPLES.map((x) => (
          <button type="button" key={x.label} onClick={() => { setName(x.account_name); setUrl(x.profile_url); setMessage(x.message); setReport(null); }}>
            {x.label}
          </button>
        ))}
      </div>
      <form className="account-form panel-card" onSubmit={(e) => void submit(e)}>
        <label>Tên tài khoản hoặc người liên hệ
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required placeholder="Ví dụ: Agoda Hỗ trợ 24/7" />
        </label>
        <label>Link hồ sơ (nếu có)
          <input value={url} onChange={(e) => setUrl(e.target.value)} maxLength={500} placeholder="https://..." />
        </label>
        <label>Nội dung họ gửi (nếu có)
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} maxLength={4000} rows={5} placeholder="Dán nguyên văn tin nhắn để xem bằng chứng cụ thể" />
        </label>
        <button className="btn-primary" type="submit" disabled={busy || !name.trim()}>{busy ? "Đang kiểm tra..." : "Kiểm tra dấu hiệu"}</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
      {report && <>
        <p className="notice"><strong>Chưa xác minh danh tính tài khoản.</strong> Một tên hoặc link trông giống thương hiệu không chứng minh người liên hệ thuộc thương hiệu đó.</p>
        <RiskReport block={report} />
      </>}
    </main>
  );
}
