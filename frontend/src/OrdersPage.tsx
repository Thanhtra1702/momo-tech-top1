import { useEffect, useState } from "react";
import { ApiError, listOrders } from "./api";
import { vnd } from "./format";
import { IconArrowLeft } from "./icons";
import type { Order, UpcomingItem } from "./types";

const KIND_LABEL: Record<string, string> = { event: "Giải trí", transport: "Di chuyển", lodging: "Lưu trú", tour: "Tour" };
const STATUS_LABEL: Record<Order["status"], string> = {
  draft: "Đơn nháp", confirmed: "Đã xác nhận (mô phỏng)", cancelled: "Đã hủy", expired: "Đã hết hạn",
};

export function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("vi-VN", { weekday: "short", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

/** Chia đơn thành nhóm hiển thị: nháp còn hạn, đã xác nhận, còn lại (hết hạn, hủy). */
export function groupOrders(orders: Order[]): { draft: Order[]; confirmed: Order[]; other: Order[] } {
  return {
    draft: orders.filter((o) => o.status === "draft"),
    confirmed: orders.filter((o) => o.status === "confirmed"),
    other: orders.filter((o) => o.status === "expired" || o.status === "cancelled"),
  };
}

function OrderRow({ o }: { o: Order }) {
  return (
    <li className="order-row">
      <div>
        <a href={`#/orders/${encodeURIComponent(o.id)}`}>
          <strong>{o.id}</strong>
        </a>{" "}
        <span className={`status status-${o.status}`}>{STATUS_LABEL[o.status]}</span>
        <ul className="order-items">
          {o.items.map((i) => (
            <li key={i.ref_id}>
              {i.quantity} × {i.title} <span className="muted">({KIND_LABEL[i.kind]})</span>
            </li>
          ))}
        </ul>
      </div>
      <strong>{vnd(o.total_vnd)}</strong>
    </li>
  );
}

export default function OrdersPage({ onAuthLost }: { onAuthLost: () => void }) {
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [upcoming, setUpcoming] = useState<UpcomingItem[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    listOrders()
      .then((r) => {
        if (!alive) return;
        setOrders(r.orders);
        setUpcoming(r.upcoming);
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) onAuthLost();
        else if (alive) setError(e instanceof Error ? e.message : "Không tải được danh sách đơn");
      });
    return () => {
      alive = false;
    };
  }, [onAuthLost]);

  const g = groupOrders(orders ?? []);
  return (
    <main className="page">
      <a className="back" href="#/"><IconArrowLeft size={16} /> Quay lại trò chuyện</a>
      <h1>Đơn và chuyến đi của tôi</h1>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {orders === null && !error && <p>Đang tải...</p>}
      {orders && (
        <>
          <section aria-label="Sắp tới">
            <h2>Sắp tới</h2>
            {upcoming.length === 0 ? (
              <p className="muted">Chưa có chuyến đi hay sự kiện nào sắp diễn ra. Đặt và xác nhận một đơn để thấy ở đây.</p>
            ) : (
              <ul className="upcoming">
                {upcoming.map((u) => (
                  <li key={`${u.order_id}-${u.ref_id}`}>
                    <time>{formatWhen(u.when_at)}</time>
                    <span>
                      {u.quantity} × {u.title}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section aria-label="Đơn nháp">
            <h2>Đơn nháp cần xác nhận</h2>
            {g.draft.length === 0 ? <p className="muted">Không có đơn nháp.</p> : <ul className="order-list">{g.draft.map((o) => <OrderRow key={o.id} o={o} />)}</ul>}
          </section>
          <section aria-label="Đã xác nhận">
            <h2>Đã xác nhận</h2>
            {g.confirmed.length === 0 ? <p className="muted">Chưa có đơn nào.</p> : <ul className="order-list">{g.confirmed.map((o) => <OrderRow key={o.id} o={o} />)}</ul>}
          </section>
          {g.other.length > 0 && (
            <section aria-label="Lịch sử khác">
              <h2>Hết hạn hoặc đã hủy</h2>
              <ul className="order-list">{g.other.map((o) => <OrderRow key={o.id} o={o} />)}</ul>
            </section>
          )}
        </>
      )}
    </main>
  );
}
