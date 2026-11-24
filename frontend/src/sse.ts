import type { SseEvent } from "./types";

/**
 * Tách các sự kiện SSE hoàn chỉnh khỏi bộ đệm. Phần dang dở được trả lại trong `rest`
 * để ghép với đoạn dữ liệu kế tiếp.
 */
export function parseSse(buffer: string): { events: SseEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const parts = normalized.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: SseEvent[] = [];
  for (const part of parts) {
    const data = part
      .split("\n")
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).replace(/^ /, ""))
      .join("\n");
    if (!data) continue;
    try {
      events.push(JSON.parse(data) as SseEvent);
    } catch {
      // bỏ qua sự kiện hỏng, không làm vỡ cả luồng
    }
  }
  return { events, rest };
}
