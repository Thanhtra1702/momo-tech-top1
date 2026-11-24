import { FormEvent, useEffect, useState } from "react";
import { ApiError, clearMemory, deleteMemory, getMemory, putMemory } from "./api";
import { IconClose } from "./icons";

export default function MemoryPanel({ onClose, onAuthLost }: { onClose: () => void; onAuthLost: () => void }) {
  const [memory, setMemory] = useState<Record<string, string>>({});
  const [labels, setLabels] = useState<Record<string, string>>({});
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  function handle(e: unknown) {
    if (e instanceof ApiError && e.status === 401) onAuthLost();
    setError(e instanceof Error ? e.message : "Có lỗi xảy ra");
  }

  useEffect(() => {
    getMemory()
      .then((r) => {
        setMemory(r.memory);
        setLabels(r.labels);
        setKey(Object.keys(r.labels)[0] ?? "");
      })
      .catch(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      setMemory((await putMemory(key, value)).memory);
      setValue("");
    } catch (err) {
      handle(err);
    }
  }

  return (
    <>
    <div className="backdrop" onClick={onClose} aria-hidden="true" />
    <aside className="panel" aria-label="Bộ nhớ cá nhân">
      <div className="panel-head">
        <h2>Trợ lý đang nhớ về bạn</h2>
        <button className="icon-btn" onClick={onClose} aria-label="Đóng">
          <IconClose size={18} />
        </button>
      </div>
      {Object.keys(memory).length === 0 ? (
        <p className="muted">Chưa có gì. Bạn có thể nói "nhớ giúp mình là mình hay đi từ Hà Nội" hoặc thêm bên dưới.</p>
      ) : (
        <ul className="memory-list">
          {Object.entries(memory).map(([k, v]) => (
            <li key={k}>
              <span>
                <strong>{labels[k] ?? k}:</strong> {v}
              </span>
              <button className="btn-ghost" onClick={() => deleteMemory(k).then((r) => setMemory(r.memory)).catch(handle)}>
                Xóa
              </button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={add} className="memory-form">
        <select value={key} onChange={(e) => setKey(e.target.value)} aria-label="Loại thông tin">
          {Object.entries(labels).map(([k, label]) => (
            <option key={k} value={k}>
              {label}
            </option>
          ))}
        </select>
        <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Giá trị" maxLength={120} required />
        <button className="btn-primary">Lưu</button>
      </form>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <p className="muted small">Không lưu số thẻ, CCCD, số điện thoại, email hay mật khẩu.</p>
      {Object.keys(memory).length > 0 && (
        <button className="btn-ghost danger" onClick={() => clearMemory().then((r) => setMemory(r.memory)).catch(handle)}>
          Xóa tất cả
        </button>
      )}
    </aside>
    </>
  );
}
