import { FormEvent, useEffect, useRef, useState } from "react";
import { ApiError, fileToBase64, getLatestConversation, getSamples, streamChat } from "./api";
import { Block } from "./Blocks";
import { applyEvent, finish, fromSaved, newAssistant } from "./chatState";
import Markdown from "./Markdown";
import { IconAlert, IconBolt, IconCheck, IconImage, IconMemory, IconMic, IconPlane, IconPlus, IconSend, IconShield, IconSparkle, IconSplit, IconStop, IconWallet, iconForPrompt } from "./icons";
import { quickReplies } from "./quickReplies";
import { appendTranscript, finalTranscript, recognitionCtor, voiceErrorMessage, type Recognition } from "./voice";
import type { ChatMessage, Mode, TicketCard } from "./types";

const MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];
const FALLBACK_SAMPLES = ["Tìm vé xem phim cuối tuần này ở Sài Gòn dưới 150 nghìn", "Tìm chuyến bay Hà Nội đi Đà Nẵng cuối tuần này, rẻ nhất"];

function newSessionId(): string {
  return (crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`).replace(/[^A-Za-z0-9_-]/g, "");
}

export default function Chat({ onAuthLost, onOpenMemory }: { onAuthLost: () => void; onOpenMemory: () => void }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Mode>("fast");
  const [busy, setBusy] = useState(false);
  const [samples, setSamples] = useState<string[]>(FALLBACK_SAMPLES);
  const [image, setImage] = useState<{ file: File; preview: string } | null>(null);
  const [notice, setNotice] = useState("");
  const [imagesOn, setImagesOn] = useState(true);
  const sessionId = useRef(newSessionId());
  const nextId = useRef(1);
  const startedRef = useRef(false);
  const recRef = useRef<Recognition | null>(null);
  const [listening, setListening] = useState(false);
  const voiceSupported = recognitionCtor() !== null;
  const abort = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getSamples()
      .then((r) => {
        setSamples(r.prompts);
        setImagesOn(r.images);
      })
      .catch(() => undefined);
    // Khôi phục cuộc trò chuyện gần nhất (sau khi tải lại trang). Bỏ qua nếu người dùng đã gửi gì đó trong lúc chờ.
    getLatestConversation()
      .then((r) => {
        if (!r.session_id || r.messages.length === 0 || startedRef.current) return;
        sessionId.current = r.session_id;
        nextId.current = r.messages.length + 1000;
        setMessages(fromSaved(r.messages, 1));
      })
      .catch((e: unknown) => {
        if (e instanceof ApiError && e.status === 401) onAuthLost();
      });
    return () => {
      abort.current?.abort();
      recRef.current?.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (messages.length === 0) return; // màn hình chào giữ nguyên ở đầu trang, không tự cuộn xuống
    endRef.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function send(text: string, img = image) {
    const message = text.trim();
    if ((!message && !img) || busy) return;
    startedRef.current = true;
    setBusy(true);
    setNotice("");
    const userMsg: ChatMessage = {
      id: nextId.current++, role: "user", text: message, blocks: [], tools: [], thinking: false, imagePreview: img?.preview,
    };
    const aId = nextId.current++;
    setMessages((m) => [...m, userMsg, newAssistant(aId)]);
    setInput("");
    setImage(null);
    const update = (fn: (m: ChatMessage) => ChatMessage) => setMessages((all) => all.map((m) => (m.id === aId ? fn(m) : m)));
    const controller = new AbortController();
    abort.current = controller;
    try {
      const payload = {
        message, mode, session_id: sessionId.current,
        ...(img ? { image: { mime: img.file.type, data: await fileToBase64(img.file) } } : {}),
      };
      await streamChat(payload, (ev) => update((m) => applyEvent(m, ev)), controller.signal);
      if (controller.signal.aborted) update((m) => ({ ...finish(m), text: m.text ? m.text + "\n\n*(đã dừng)*" : "*(đã dừng)*" }));
      else update((m) => finish(m, m.pending && !m.text && !m.blocks.length ? "Không nhận được phản hồi, bạn thử lại nhé." : undefined));
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) onAuthLost();
      update((m) => finish(m, e instanceof Error ? e.message : "Có lỗi xảy ra"));
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void send(input);
  }

  function choose(card: TicketCard, quantity: number) {
    const unit = card.price_unit ?? "vé";
    void send(`Tạo đơn nháp cho ${card.ref_id} (${card.title}), số lượng ${quantity} ${unit}`);
  }

  function onPickImage(file: File | undefined) {
    if (!file) return;
    if (!IMAGE_TYPES.includes(file.type)) return setNotice("Chỉ nhận ảnh PNG, JPEG hoặc WEBP.");
    if (file.size > MAX_IMAGE_BYTES) return setNotice("Ảnh quá lớn, tối đa 4 MB.");
    setNotice("");
    setImage({ file, preview: URL.createObjectURL(file) });
  }

  /** Điền sẵn câu mở đầu để người dùng dán nội dung rồi gửi (không tự gửi). */
  function prefill(text: string) {
    setInput(text);
    inputRef.current?.focus();
  }

  function stop() {
    abort.current?.abort();
  }

  function toggleVoice() {
    if (listening) {
      recRef.current?.stop();
      return;
    }
    const Ctor = recognitionCtor();
    if (!Ctor) return;
    const rec = new Ctor();
    rec.lang = "vi-VN";
    rec.interimResults = false;
    rec.continuous = false;
    rec.onresult = (e) => setInput((cur) => appendTranscript(cur, finalTranscript(e)));
    rec.onerror = (e) => setNotice(voiceErrorMessage(e.error));
    rec.onend = () => setListening(false);
    recRef.current = rec;
    setNotice("");
    try {
      rec.start();
      setListening(true);
    } catch {
      setNotice(voiceErrorMessage(""));
    }
  }

  function reset() {
    abort.current?.abort();
    startedRef.current = true;
    sessionId.current = newSessionId();
    setMessages([]);
    setImage(null);
    setBusy(false);
  }

  const last = messages[messages.length - 1];
  const chips = !busy && last?.role === "assistant" ? quickReplies(last.blocks) : [];

  return (
    <div className="chat">
      <div className="toolbar">
        <div className="mode" role="radiogroup" aria-label="Chế độ trả lời">
          <button role="radio" aria-checked={mode === "fast"} className={mode === "fast" ? "on" : ""} onClick={() => setMode("fast")}>
            <IconBolt size={15} /> Nhanh
          </button>
          <button role="radio" aria-checked={mode === "deep"} className={mode === "deep" ? "on" : ""} onClick={() => setMode("deep")}>
            <IconSparkle size={15} /> Suy luận sâu
          </button>
        </div>
        <div className="toolbar-actions">
          <button className="btn-ghost" onClick={onOpenMemory} aria-label="Bộ nhớ">
            <IconMemory size={16} /> <span className="label">Bộ nhớ</span>
          </button>
          <button className="btn-ghost" onClick={reset} aria-label="Cuộc mới">
            <IconPlus size={16} /> <span className="label">Cuộc mới</span>
          </button>
        </div>
      </div>

      <div className="messages" aria-live="polite">
        {messages.length === 0 && (
          <div className="welcome">
            <div className="logo lg" aria-hidden="true">
              <IconPlane size={28} />
            </div>
            <h2>Bạn muốn đi đâu, xem gì?</h2>
            <p className="muted">Tìm và so sánh vé, khách sạn, tour, lập lịch trình, kiểm tra người bán, theo dõi ngân sách và chia tiền nhóm. Tất cả trong một cuộc trò chuyện.</p>
            <div className="section-label">Thử ngay</div>
            <div className="suggest-grid">
              {samples.map((s) => {
                const Icon = iconForPrompt(s);
                return (
                  <button key={s} className="suggest" onClick={() => void send(s)} disabled={busy}>
                    <span className="tile" aria-hidden="true">
                      <Icon size={18} />
                    </span>
                    <span>{s}</span>
                  </button>
                );
              })}
            </div>
            <div className="section-label">Công cụ cho cả chuyến đi</div>
            <div className="feature-grid">
              <a className="feature" href="#/live-events">
                <span className="tile" aria-hidden="true"><IconPlane size={18} /></span>
                <strong>Sự kiện thật</strong>
                <span className="desc">Tra Ticketbox trực tiếp, xem thời điểm kiểm tra và link mua vé.</span>
              </a>
              <button className="feature" onClick={() => prefill("Kiểm tra giúp mình tin nhắn này: ")}>
                <span className="tile t-shield" aria-hidden="true"><IconShield size={18} /></span>
                <strong>Kiểm tra người bán</strong>
                <span className="desc">Dán tin nhắn hoặc link để xem dấu hiệu lừa đảo.</span>
              </button>
              <button className="feature" onClick={() => prefill("Tạo chuyến đi ")}>
                <span className="tile t-wallet" aria-hidden="true"><IconWallet size={18} /></span>
                <strong>Ngân sách chuyến đi</strong>
                <span className="desc">Đặt ngân sách, ghi chi tiêu, theo dõi còn lại.</span>
              </button>
              <button className="feature" onClick={() => prefill("Chia tiền ")}>
                <span className="tile t-split" aria-hidden="true"><IconSplit size={18} /></span>
                <strong>Chia tiền nhóm</strong>
                <span className="desc">Chia đều hoặc theo tỷ trọng, soạn tin nhắc trả.</span>
              </button>
            </div>
          </div>
        )}
        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="msg user">
              {m.imagePreview && <img className="thumb" src={m.imagePreview} alt="Ảnh bạn đã gửi" />}
              {m.hadImage && !m.imagePreview && <p className="small">Ảnh đã gửi (không được lưu)</p>}
              {m.text && <p className="text">{m.text}</p>}
            </div>
          ) : (
            <div key={m.id} className="msg assistant">
              <span className="avatar" aria-hidden="true">
                <IconPlane size={16} />
              </span>
              <div className="content">
                {m.tools.length > 0 && (
                  <ul className="tools" aria-label="Tiến trình">
                    {m.tools.map((t, i) => (
                      <li key={i} className={t.status}>
                        {t.status === "running" ? <span className="spin" /> : t.status === "done" ? <IconCheck size={13} /> : <IconAlert size={13} />}
                        {t.label}
                      </li>
                    ))}
                  </ul>
                )}
                {m.thinking && m.pending && (
                  <p className="thinking">
                    <IconSparkle size={15} /> Đang suy luận...
                  </p>
                )}
                {m.text && <Markdown text={m.text} />}
                {m.pending && !m.text && m.tools.length === 0 && !m.thinking && (
                  <p className="thinking">
                    <span className="dots" aria-hidden="true"><i /><i /><i /></span> Đang xử lý...
                  </p>
                )}
                {m.blocks.map((b, i) => (
                  <Block key={i} block={b} onChoose={choose} disabled={busy} />
                ))}
                {m.error && (
                  <p className="error" role="alert">
                    {m.error}
                  </p>
                )}
              </div>
            </div>
          ),
        )}
        {chips.length > 0 && (
          <div className="chips quick" aria-label="Gợi ý trả lời nhanh">
            {chips.map((q) => (
              <button key={q} className="chip" onClick={() => void send(q)}>
                {q}
              </button>
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="composer-wrap">
        {notice && <p className="error" role="alert">{notice}</p>}
        {image && (
          <div className="attach">
            <img src={image.preview} alt="Ảnh sắp gửi" />
            <button className="btn-ghost" onClick={() => setImage(null)}>Bỏ ảnh</button>
          </div>
        )}
        <form onSubmit={onSubmit} className="composer">
          {imagesOn && (
            <label className="icon-btn attach-btn" title="Gửi ảnh">
              <IconImage size={20} />
              <span className="sr-only">Gửi ảnh</span>
              <input type="file" accept={IMAGE_TYPES.join(",")} hidden onChange={(e) => { onPickImage(e.target.files?.[0]); e.target.value = ""; }} />
            </label>
          )}
          {voiceSupported && (
            <button type="button" className={`icon-btn${listening ? " on" : ""}`} onClick={toggleVoice} aria-pressed={listening} aria-label="Nhập bằng giọng nói" title="Nhập bằng giọng nói">
              {listening ? <IconStop size={18} /> : <IconMic size={20} />}
            </button>
          )}
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={image ? "Hỏi gì về ảnh này?" : "Hỏi về vé, khách sạn, ngân sách..."}
            maxLength={2000}
            aria-label="Tin nhắn"
            autoComplete="off"
          />
          {busy ? (
            <button type="button" className="send stop" onClick={stop} aria-label="Dừng trả lời" title="Dừng">
              <IconStop size={16} />
            </button>
          ) : (
            <button className="send" disabled={!input.trim() && !image} aria-label="Gửi" title="Gửi">
              <IconSend size={17} />
            </button>
          )}
        </form>
        <p className="footnote">Dữ liệu trong chat là mô phỏng. <a href="#/live-events">Tra sự kiện thật</a> trên Ticketbox. Trợ lý chỉ tạo đơn nháp mô phỏng.</p>
      </div>
    </div>
  );
}
