import { FormEvent, useState } from "react";
import { ApiError, searchLiveEvents } from "./api";
import { vnd } from "./format";
import type { LiveEventResult } from "./types";

function timeLabel(value: string | null): string {
  if (!value) return "Xem thời gian trên Ticketbox";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "Xem thời gian trên Ticketbox" : new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh", dateStyle: "medium", timeStyle: "short",
  }).format(d);
}

export default function LiveEventsPage({ onAuthLost }: { onAuthLost: () => void }) {
  const [query, setQuery] = useState("");
  const [cityId, setCityId] = useState("");
  const [data, setData] = useState<LiveEventResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setData(null);
    setBusy(true);
    try {
      setData(await searchLiveEvents(query.trim(), cityId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) onAuthLost();
      else setError(err instanceof Error ? err.message : "Không tra cứu được sự kiện.");
    } finally {
      setBusy(false);
    }
  }

  return <main className="page live-events">
    <h1>Tra cứu sự kiện Ticketbox</h1>
    <p className="muted">Tra cứu trực tiếp từ Ticketbox. Kết quả này tách khỏi danh mục mô phỏng và không tạo đơn trong ứng dụng.</p>
    <form className="live-form panel-card" onSubmit={(e) => void submit(e)}>
      <label>Tên sự kiện
        <input value={query} onChange={(e) => setQuery(e.target.value)} maxLength={120} placeholder="Nhập tên sự kiện hoặc để trống để khám phá" />
      </label>
      <label>Thành phố
        <select value={cityId} onChange={(e) => setCityId(e.target.value)}>
          <option value="">Toàn quốc</option><option value="79">TP. Hồ Chí Minh</option>
          <option value="1">Hà Nội</option><option value="68">Đà Lạt</option>
        </select>
      </label>
      <button className="btn-primary" type="submit" disabled={busy}>{busy ? "Đang tra cứu..." : "Tra cứu ngay"}</button>
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    {data && <section aria-label="Kết quả sự kiện thật">
      <p className="notice">Nguồn: {data.source}. Tra cứu lúc {timeLabel(data.checked_at)}. {data.notice}</p>
      {data.results.length === 0 ? <p role="status">Không tìm thấy sự kiện khớp tên trong kết quả hiện tại của Ticketbox. Không suy ra sự kiện không tồn tại ở mọi kênh.</p> :
        <ul className="live-list">{data.results.map((event) => <li key={event.id} className="panel-card">
          <h2>{event.title}</h2>
          <p>{timeLabel(event.starts_at)}</p>
          <p>{event.price_from_vnd === null ? "Xem giá trên Ticketbox" : `Giá từ ${vnd(event.price_from_vnd)}`}</p>
          <a className="btn-primary link" href={event.url} target="_blank" rel="noopener noreferrer">Xem và mua trên Ticketbox</a>
        </li>)}</ul>}
      {data.has_more && <p className="muted">Có thêm kết quả trên Ticketbox; hãy thu hẹp tên sự kiện để tìm chính xác hơn.</p>}
    </section>}
  </main>;
}
