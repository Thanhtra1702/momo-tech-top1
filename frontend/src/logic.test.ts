import { describe, expect, it } from "vitest";
import { applyEvent, finish, newAssistant } from "./chatState";
import { cell, safeHttpsUrl, vnd } from "./format";
import { parseSse } from "./sse";
import type { SseEvent } from "./types";

describe("parseSse", () => {
  it("tách nhiều sự kiện và giữ phần dang dở", () => {
    const a = parseSse('data: {"type":"text_delta","text":"Xin "}\n\ndata: {"type":"text_delta","text":"chào"}\n\ndata: {"type":"do');
    expect(a.events).toEqual([
      { type: "text_delta", text: "Xin " },
      { type: "text_delta", text: "chào" },
    ]);
    const b = parseSse(a.rest + 'ne"}\n\n');
    expect(b.events).toEqual([{ type: "done" }]);
    expect(b.rest).toBe("");
  });

  it("xử lý CRLF và bỏ qua dòng hỏng", () => {
    const r = parseSse('data: {"type":"thinking"}\r\n\r\ndata: {hỏng\n\n: comment\n\n');
    expect(r.events).toEqual([{ type: "thinking" }]);
  });

  it("giữ nguyên tiếng Việt có dấu", () => {
    const r = parseSse('data: {"type":"text_delta","text":"Đà Lạt"}\n\n');
    expect(r.events[0]).toEqual({ type: "text_delta", text: "Đà Lạt" });
  });
});

describe("applyEvent", () => {
  const run = (events: SseEvent[]) => events.reduce(applyEvent, newAssistant(1));

  it("ghép văn bản, khối giao diện và trạng thái công cụ", () => {
    const m = run([
      { type: "thinking" },
      { type: "tool_status", tool: "search_events", status: "running", label: "Đang tìm vé" },
      { type: "tool_status", tool: "search_events", status: "done" },
      { type: "ui_block", block: { kind: "order_draft", order_id: "ord_1", summary: "x" } },
      { type: "text_delta", text: "Xong" },
      { type: "done" },
    ]);
    expect(m.text).toBe("Xong");
    expect(m.blocks).toHaveLength(1);
    expect(m.tools).toEqual([{ tool: "search_events", label: "Đang tìm vé", status: "done" }]);
    expect(m.pending).toBe(false);
    expect(m.thinking).toBe(false);
  });

  it("ghi nhận lỗi và finish không ghi đè lỗi có sẵn", () => {
    const m = run([{ type: "error", message: "Lỗi A" }]);
    expect(finish(m, "Lỗi B").error).toBe("Lỗi A");
    expect(finish(newAssistant(2), "Lỗi B").error).toBe("Lỗi B");
  });
});

describe("format", () => {
  it("định dạng tiền VND", () => {
    expect(vnd(1290000)).toMatch(/^1[.\s]?290[.\s]?000đ$/);
  });
  it("chỉ định dạng tiền ở cột giá", () => {
    expect(cell(95000, "Giá")).toMatch(/đ$/);
    expect(cell(4.5, "Đánh giá")).toBe("4.5");
    expect(cell("1h25", "Thời gian")).toBe("1h25");
  });
  it("chỉ cho phép link https", () => {
    expect(safeHttpsUrl("https://example.com/a?b=1")).toBe("https://example.com/a?b=1");
    expect(safeHttpsUrl("javascript:alert(1)")).toBeNull();
    expect(safeHttpsUrl("http://example.com")).toBeNull();
    expect(safeHttpsUrl(undefined)).toBeNull();
    expect(safeHttpsUrl("không phải url")).toBeNull();
  });
});

import { parseInline, parseMarkdown } from "./mdParse";

describe("markdown", () => {
  it("tách đậm, nghiêng, mã và giữ nguyên chữ thường", () => {
    expect(parseInline("Giá **46.000đ** và *rẻ* với `abc`")).toEqual([
      { t: "text", s: "Giá " },
      { t: "b", s: "46.000đ" },
      { t: "text", s: " và " },
      { t: "i", s: "rẻ" },
      { t: "text", s: " với " },
      { t: "code", s: "abc" },
    ]);
  });

  it("để nguyên dấu sao chưa đóng (đang streaming) và dấu nhân", () => {
    expect(parseInline("**chưa đóng")).toEqual([{ t: "text", s: "**chưa đóng" }]);
    expect(parseInline("2 * 3 * 4")).toEqual([{ t: "text", s: "2 * 3 * 4" }]);
  });

  it("nhận danh sách gạch đầu dòng, đánh số và tiêu đề", () => {
    const blocks = parseMarkdown("### Gợi ý\nMở đầu\n\n- **A** rẻ\n- B\n\n1. Một\n2. Hai");
    expect(blocks.map((b) => b.type)).toEqual(["p", "p", "ul", "ol"]);
    const ul = blocks[2];
    expect(ul.type === "ul" && ul.items.length).toBe(2);
    const head = blocks[0];
    expect(head.type === "p" && head.inl).toEqual([{ t: "b", s: "Gợi ý" }]);
  });

  it("không bao giờ tạo HTML: thẻ script chỉ là chữ", () => {
    const blocks = parseMarkdown("<script>alert(1)</script> **x**");
    expect(JSON.stringify(blocks)).toContain("<script>alert(1)</script>");
    expect(blocks[0].type).toBe("p");
  });
});

import { fromSaved } from "./chatState";
import { formatCountdown } from "./OrderPage";

describe("khôi phục hội thoại và đồng hồ đếm ngược", () => {
  it("dựng lại tin nhắn từ bản lưu, giữ thẻ và đánh dấu ảnh", () => {
    const msgs = fromSaved(
      [
        { role: "user", text: "tìm phim", has_image: true },
        { role: "assistant", text: "Đây", blocks: [{ kind: "order_draft", order_id: "ord_1", summary: "x" }], error: "lỗi" },
      ],
      5,
    );
    expect(msgs.map((m) => m.id)).toEqual([5, 6]);
    expect(msgs[0].hadImage).toBe(true);
    expect(msgs[1].blocks).toHaveLength(1);
    expect(msgs[1].error).toBe("lỗi");
    expect(msgs.every((m) => !m.pending)).toBe(true);
  });

  it("định dạng mm:ss", () => {
    expect(formatCountdown(0)).toBe("00:00");
    expect(formatCountdown(65)).toBe("01:05");
    expect(formatCountdown(1800)).toBe("30:00");
  });
});

import { quickReplies } from "./quickReplies";
import { groupOrders } from "./OrdersPage";
import type { Order, UiBlock } from "./types";

const cards = (category: "transport" | "lodging" | "event" | "tour", title: string, subtitle: string, n = 3): UiBlock => ({
  kind: "ticket_cards",
  items: Array.from({ length: n }, (_, i) => ({ ref_id: `x_${i}`, category, title, subtitle, price_vnd: 1000 })),
});

describe("gợi ý trả lời nhanh", () => {
  it("không có khối thì không gợi ý", () => {
    expect(quickReplies([])).toEqual([]);
  });

  it("vé di chuyển: so sánh, chọn, tìm khách sạn ở điểm đến", () => {
    expect(quickReplies([cards("transport", "Hãng bay mẫu A: Hà Nội - Đà Nẵng", "06/12 07:10 - 08:35")])).toEqual([
      "So sánh các chuyến này",
      "Chọn chuyến đầu tiên, đặt 1 vé",
      "Tìm khách sạn ở Đà Nẵng",
    ]);
  });

  it("chỉ một kết quả thì không gợi ý so sánh", () => {
    expect(quickReplies([cards("transport", "Xe: Hà Nội - Huế", "x", 1)])).not.toContain("So sánh các chuyến này");
  });

  it("lưu trú và tour lấy thành phố từ phụ đề", () => {
    expect(quickReplies([cards("lodging", "KS A", "Đà Lạt, hồ bơi, wifi")])).toContain("Tìm tour ở Đà Lạt");
    expect(quickReplies([cards("tour", "Tour A", "Phú Quốc, 3 ngày")])).toContain("Lập lịch trình 3 ngày ở Phú Quốc cho 2 người");
  });

  it("dùng khối cuối cùng và tối đa 3 gợi ý", () => {
    const itinerary: UiBlock = { kind: "itinerary", days: [], total_vnd: 6490000 };
    const r = quickReplies([cards("event", "Phim", "Rạp"), itinerary]);
    expect(r[0]).toMatch(/^Tạo chuyến đi với ngân sách 6[.\s]?490[.\s]?000đ$/);
    expect(r).toContain("Chia tiền cho cả nhóm");
    expect(r.length).toBeLessThanOrEqual(3);
  });

  it("báo cáo rủi ro cao gợi ý đặt vé an toàn, mức thấp gợi ý kiểm tra tiếp", () => {
    const risk = (level: "low" | "high"): UiBlock => ({ kind: "risk_report", level, score: 10, headline: "", signals: [], urls: [], advice: [] });
    expect(quickReplies([risk("high")])).toEqual(["Làm sao để đặt vé an toàn?"]);
    expect(quickReplies([risk("low")])).toEqual(["Kiểm tra giúp mình một tin nhắn khác"]);
  });
});

describe("nhóm đơn", () => {
  it("tách đơn nháp, đã xác nhận, hết hạn", () => {
    const o = (id: string, status: Order["status"]): Order => ({ id, status, items: [], total_vnd: 0, created_at: "", confirmed_at: null });
    const g = groupOrders([o("a", "draft"), o("b", "confirmed"), o("c", "expired"), o("d", "cancelled"), o("e", "confirmed")]);
    expect(g.draft.map((x) => x.id)).toEqual(["a"]);
    expect(g.confirmed.map((x) => x.id)).toEqual(["b", "e"]);
    expect(g.other.map((x) => x.id)).toEqual(["c", "d"]);
  });
});

import { appendTranscript, finalTranscript, recognitionCtor, voiceErrorMessage } from "./voice";

describe("nhập bằng giọng nói", () => {
  it("nhận biết trình duyệt có hỗ trợ hay không", () => {
    expect(recognitionCtor({})).toBeNull();
    class Fake {}
    expect(recognitionCtor({ webkitSpeechRecognition: Fake })).toBe(Fake);
    expect(recognitionCtor({ SpeechRecognition: Fake })).toBe(Fake);
  });

  it("ghép lời nói vào văn bản đang gõ", () => {
    expect(appendTranscript("", " tìm vé phim ")).toBe("tìm vé phim");
    expect(appendTranscript("Tìm giúp mình", "vé đi Huế")).toBe("Tìm giúp mình vé đi Huế");
    expect(appendTranscript("giữ nguyên", "   ")).toBe("giữ nguyên");
  });

  it("chỉ lấy kết quả cuối cùng", () => {
    const e = { resultIndex: 0, results: [{ isFinal: false, 0: { transcript: "tìm" } }, { isFinal: true, 0: { transcript: "tìm vé" } }] };
    expect(finalTranscript(e)).toBe("tìm vé");
  });

  it("thông báo lỗi tiếng Việt, có mặc định", () => {
    expect(voiceErrorMessage("not-allowed")).toContain("micro");
    expect(voiceErrorMessage("xyz")).toContain("thử lại");
  });
});
