import { useState } from "react";
import { cell, vnd } from "./format";
import { CATEGORY_ICON, IconAlert, IconCheck, IconShield } from "./icons";
import type { TicketCard, UiBlock } from "./types";

interface Props {
  block: UiBlock;
  onChoose: (card: TicketCard, quantity: number) => void;
  disabled: boolean;
}

const QTY_LABEL: Record<string, string> = { "đêm": "Số đêm", "người": "Số người", "vé": "Số vé" };

function badgeClass(b: string): string {
  return b === "Chiều đi" ? "badge go" : b === "Chiều về" ? "badge back" : "badge";
}

function Card({ card, onChoose, disabled }: { card: TicketCard; onChoose: Props["onChoose"]; disabled: boolean }) {
  const [qty, setQty] = useState(1);
  const Icon = CATEGORY_ICON[card.category];
  const unit = card.price_unit ?? "vé";
  return (
    <li className={`card cat-${card.category}`}>
      <span className="card-icon" aria-hidden="true">
        <Icon size={22} />
      </span>
      <div className="card-body">
        <strong>{card.title}</strong>
        {card.subtitle && <span className="sub">{card.subtitle}</span>}
        {card.badges && card.badges.length > 0 && (
          <div className="badges">
            {card.badges.map((b) => (
              <span key={b} className={badgeClass(b)}>
                {b}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="card-side">
        <span className="price">
          {vnd(card.price_vnd)}
          <small>/{unit}</small>
        </span>
        <div className="card-actions">
          <select value={qty} onChange={(e) => setQty(Number(e.target.value))} aria-label={QTY_LABEL[unit] ?? "Số lượng"}>
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
              <option key={n} value={n}>
                {n} {unit}
              </option>
            ))}
          </select>
          <button className="btn-primary" disabled={disabled} onClick={() => onChoose(card, qty)}>
            Chọn
          </button>
        </div>
      </div>
    </li>
  );
}
export function Block({ block, onChoose, disabled }: Props) {
  if (block.kind === "ticket_cards") {
    return (
      <section className="block" aria-label={block.title ?? "Kết quả"}>
        {block.title && <h3>{block.title}</h3>}
        <ul className="cards">
          {block.items.map((c) => (
            <Card key={c.ref_id} card={c} onChoose={onChoose} disabled={disabled} />
          ))}
        </ul>
      </section>
    );
  }
  if (block.kind === "comparison_table") {
    return (
      <section className="block" aria-label="Bảng so sánh">
        <h3>So sánh</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {block.columns.map((c) => (
                  <th key={c}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, i) => (
                <tr key={i} className={i === block.recommended_row ? "recommended" : undefined}>
                  {row.map((v, j) => (
                    <td key={j}>
                      {cell(v, block.columns[j] ?? "")}
                      {j === 0 && i === block.recommended_row && <span className="badge ok">Nên chọn</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    );
  }
  if (block.kind === "itinerary") {
    return (
      <section className="block" aria-label="Lịch trình">
        <h3>Lịch trình</h3>
        {block.days.map((d) => (
          <div key={d.day} className="day">
            <h4>Ngày {d.day}</h4>
            <ol className="timeline">
              {d.entries.map((e, i) => (
                <li key={i}>
                  <time>{e.time}</time>
                  <span>{e.title}</span>
                  <span className="muted">{e.cost_vnd > 0 ? vnd(e.cost_vnd) : "Miễn phí"}</span>
                </li>
              ))}
            </ol>
          </div>
        ))}
        <p className="total">
          Tổng chi phí: <strong>{vnd(block.total_vnd)}</strong>
        </p>
      </section>
    );
  }
  if (block.kind === "risk_report") return <RiskReport block={block} />;
  if (block.kind === "budget_status") return <BudgetStatus block={block} />;
  if (block.kind === "split_result") return <SplitResult block={block} />;
  return (
    <section className="block order-card" aria-label="Đơn nháp">
      <h3>Đơn nháp đã tạo</h3>
      <p>{block.summary}</p>
      {block.total_vnd !== undefined && (
        <p>
          Tổng: <strong>{vnd(block.total_vnd)}</strong>
        </p>
      )}
      <a className="btn-primary link" href={`#/orders/${encodeURIComponent(block.order_id)}`}>
        Xem và xác nhận đơn
      </a>
    </section>
  );
}

type Risk = Extract<UiBlock, { kind: "risk_report" }>;
type Budget = Extract<UiBlock, { kind: "budget_status" }>;
type Split = Extract<UiBlock, { kind: "split_result" }>;

const LEVEL_LABEL: Record<Risk["level"], string> = { low: "Ít dấu hiệu", medium: "Cần cẩn trọng", high: "Rủi ro cao", critical: "Rủi ro rất cao" };
const VERDICT_LABEL: Record<string, string> = { official: "Trang chính thức", risky: "Có dấu hiệu rủi ro", unknown: "Chưa xác định" };

export function RiskReport({ block }: { block: Risk }) {
  return (
    <section className={`block risk risk-${block.level}`} aria-label="Kết quả kiểm tra rủi ro">
      <div className="risk-head">
        <span className="risk-icon" aria-hidden="true">
          {block.level === "low" ? <IconCheck size={22} /> : block.level === "medium" ? <IconAlert size={22} /> : <IconShield size={22} />}
        </span>
        <div>
          <strong>
            {LEVEL_LABEL[block.level]} ({block.score}/100)
          </strong>
          <span className="muted small">{block.headline}</span>
        </div>
      </div>
      {block.signals.length > 0 && (
        <ul className="risk-list">
          {block.signals.map((s, i) => (
            <li key={i} className={`sev-${s.severity}`}>
              {s.label}
              {s.evidence && <q>{s.evidence}</q>}
            </li>
          ))}
        </ul>
      )}
      {block.urls.map((u) => (
        <div key={u.host} className={`risk-url verdict-${u.verdict}`}>
          <code>{u.host}</code> <span className="badge">{VERDICT_LABEL[u.verdict]}</span>
          {u.issues.length > 0 && (
            <ul>
              {u.issues.map((x) => (
                <li key={x}>{x}</li>
              ))}
            </ul>
          )}
        </div>
      ))}
      <p className="risk-advice-title">Nên làm</p>
      <ul>
        {block.advice.map((a) => (
          <li key={a}>{a}</li>
        ))}
      </ul>
      <p className="muted small">Phân tích dấu hiệu tự động, không phải kết luận ai đó lừa đảo.</p>
    </section>
  );
}

export function BudgetStatus({ block }: { block: Budget }) {
  const pct = Math.min(100, Math.max(0, block.percent));
  return (
    <section className={`block budget budget-${block.level}`} aria-label={`Ngân sách ${block.trip}`}>
      <h3>{block.trip}</h3>
      <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}>
        <span className="bar-fill" data-pct={pct} ref={(el) => el && (el.style.width = `${pct}%`)} />
      </div>
      <p className="budget-line">
        Đã chi <strong>{vnd(block.spent_vnd)}</strong> / {vnd(block.budget_vnd)} ({block.percent}%)
      </p>
      <p className={block.remaining_vnd < 0 ? "error" : ""}>
        {block.remaining_vnd >= 0 ? `Còn lại ${vnd(block.remaining_vnd)}` : `Vượt ngân sách ${vnd(-block.remaining_vnd)}`}
        {block.level === "warning" && " — sắp chạm ngân sách"}
      </p>
      {block.breakdown.length > 0 && (
        <ul className="breakdown">
          {block.breakdown.map((b) => (
            <li key={b.label}>
              <span>{b.label}</span>
              <span>{vnd(b.amount_vnd)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function SplitResult({ block }: { block: Split }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(block.messages.join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* trình duyệt chặn clipboard: người dùng vẫn bôi đen chữ để sao chép được */
    }
  }
  return (
    <section className="block" aria-label="Chia tiền">
      <h3>
        Chia {vnd(block.total_vnd)} {block.label && `(${block.label})`}
      </h3>
      <table>
        <thead>
          <tr>
            <th>Người</th>
            <th>Phần của mình</th>
            <th>Cần gửi</th>
          </tr>
        </thead>
        <tbody>
          {block.per_person.map((p) => (
            <tr key={p.name}>
              <td>
                {p.name}
                {block.payer === p.name && <span className="badge ok">Ứng tiền</span>}
              </td>
              <td>{vnd(p.share_vnd)}</td>
              <td>{p.owes_vnd > 0 ? `${vnd(p.owes_vnd)} → ${p.owes_to}` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {block.messages.length > 0 && (
        <>
          <ul className="messages-list">
            {block.messages.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
          <button className="btn-ghost" onClick={copy}>
            {copied ? "Đã sao chép" : "Sao chép tin nhắn nhắc"}
          </button>
        </>
      )}
      <p className="muted small">Chỉ là bản tính và tin nhắn mẫu, chưa gửi yêu cầu thanh toán thật.</p>
    </section>
  );
}
