import { useEffect, useState } from "react";
import { ApiError, confirmOrder, getOrder } from "./api";
import { safeHttpsUrl, vnd } from "./format";
import { IconArrowLeft, IconExternal } from "./icons";
import type { Order } from "./types";

const KIND_LABEL: Record<string, string> = { event: "Giải trí", transport: "Di chuyển", lodging: "Lưu trú", tour: "Tour" };
const STATUS_LABEL: Record<Order["status"], string> = {
  draft: "Đơn nháp, chưa thanh toán",
  confirmed: "Đã xác nhận (mô phỏng)",
  cancelled: "Đã hủy",
  expired: "Đã hết hạn",
};

/** Số giây còn lại đến hạn, cập nhật mỗi giây. Trả null nếu không có hạn. */
function useCountdown(expiresAt: string | null | undefined): number | null {
  const target = expiresAt ? Date.parse(expiresAt) : NaN;
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (Number.isNaN(target)) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [target]);
  return Number.isNaN(target) ? null : Math.max(0, Math.floor((target - now) / 1000));
}

export function formatCountdown(seconds: number): string {
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export default function OrderPage({ orderId, onAuthLost }: { orderId: string; onAuthLost: () => void }) {
  const [order, setOrder] = useState<Order | null>(null);
  const remaining = useCountdown(order?.status === "draft" ? order.expires_at : null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [agreed, setAgreed] = useState(false);

  useEffect(() => {
    let alive = true;
    getOrder(orderId)
      .then((o) => alive && setOrder(o))
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) onAuthLost();
        else if (alive) setError(e instanceof Error ? e.message : "Không tải được đơn");
      });
    return () => {
      alive = false;
    };
  }, [orderId, onAuthLost]);

  async function onConfirm() {
    setBusy(true);
    setError("");
    try {
      setOrder(await confirmOrder(orderId));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) onAuthLost();
      setError(e instanceof Error ? e.message : "Không xác nhận được đơn");
      getOrder(orderId).then(setOrder).catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  if (!order) {
    return (
      <main className="page">
        <a className="back" href="#/"><IconArrowLeft size={16} /> Quay lại trò chuyện</a>
        {error ? <p className="error" role="alert">{error}</p> : <p>Đang tải đơn...</p>}
      </main>
    );
  }

  return (
    <main className="page">
      <a className="back" href="#/"><IconArrowLeft size={16} /> Quay lại trò chuyện</a>
      <h1>Xác nhận đơn {order.id}</h1>
      <p className={`status status-${order.status}`}>{STATUS_LABEL[order.status]}</p>
      {order.status === "draft" && remaining !== null && (
        <p className={remaining < 300 ? "countdown low" : "countdown"} role="timer" aria-live="off">
          {remaining > 0 ? `Đơn nháp còn hiệu lực ${formatCountdown(remaining)}` : "Đơn nháp đã hết hạn, hãy quay lại trò chuyện để tạo lại."}
        </p>
      )}
      <div className="panel-card table-wrap">
        <table>
          <thead>
            <tr>
              <th>Mục</th>
              <th>Loại</th>
              <th>Số lượng</th>
              <th>Đơn giá</th>
              <th>Thành tiền</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((it) => {
              const link = safeHttpsUrl(it.deeplink);
              return (
                <tr key={it.ref_id}>
                  <td>
                    {it.title}
                    {link && (
                      <div>
                        <a href={link} target="_blank" rel="noopener noreferrer" className="ext">
                          Tìm kiếm tham khảo (mục này là mô phỏng) <IconExternal size={13} />
                        </a>
                      </div>
                    )}
                  </td>
                  <td>{KIND_LABEL[it.kind]}</td>
                  <td>{it.quantity}</td>
                  <td>{vnd(it.unit_price_vnd)}</td>
                  <td>{vnd(it.unit_price_vnd * it.quantity)}</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={4}>
                <strong>Tổng cộng</strong>
              </td>
              <td>
                <strong>{vnd(order.total_vnd)}</strong>
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="notice">
        Đây là bản trình diễn: dữ liệu vé là mô phỏng và việc xác nhận không trừ tiền thật. Trợ lý AI không thể thanh toán thay bạn. Chỉ nút bên dưới mới
        xác nhận đơn.
      </p>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {order.status === "draft" && (
        <>
          <label className="check">
            <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
            Tôi đã xem lại sản phẩm, số lượng và tổng tiền.
          </label>
          <button className="btn-primary" disabled={!agreed || busy || remaining === 0} onClick={onConfirm}>
            {busy ? "Đang xác nhận..." : "Xác nhận thanh toán (mô phỏng)"}
          </button>
        </>
      )}
      {order.status === "confirmed" && <p className="success">Đặt chỗ thành công (mô phỏng). Cảm ơn bạn đã dùng thử!</p>}
      {(order.status === "expired" || order.status === "cancelled") && <p className="muted">Hãy quay lại trò chuyện để tạo đơn mới.</p>}
    </main>
  );
}
