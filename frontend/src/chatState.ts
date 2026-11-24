import type { ChatMessage, SavedMessage, SseEvent } from "./types";

export function newAssistant(id: number): ChatMessage {
  return { id, role: "assistant", text: "", blocks: [], tools: [], thinking: false, pending: true };
}

/** Áp một sự kiện SSE vào tin nhắn của trợ lý. Hàm thuần để dễ kiểm thử. */
export function applyEvent(msg: ChatMessage, ev: SseEvent): ChatMessage {
  switch (ev.type) {
    case "text_delta":
      return { ...msg, text: msg.text + ev.text };
    case "thinking":
      return { ...msg, thinking: true };
    case "tool_status": {
      const label = ev.label ?? ev.tool;
      const idx = msg.tools.findIndex((t) => t.tool === ev.tool && t.status === "running");
      if (ev.status === "running" || idx < 0) {
        return { ...msg, tools: [...msg.tools, { tool: ev.tool, label, status: ev.status }] };
      }
      const tools = msg.tools.slice();
      tools[idx] = { ...tools[idx], status: ev.status };
      return { ...msg, tools };
    }
    case "ui_block":
      return { ...msg, blocks: [...msg.blocks, ev.block] };
    case "error":
      return { ...msg, error: ev.message };
    case "done":
      return { ...msg, pending: false, thinking: false };
    default:
      return msg;
  }
}

/** Dựng lại tin nhắn từ bản lưu trên máy chủ. `startId` là id đầu tiên chưa dùng. */
export function fromSaved(saved: SavedMessage[], startId: number): ChatMessage[] {
  return saved.map((m, i) => ({
    id: startId + i,
    role: m.role,
    text: m.text,
    blocks: m.blocks ?? [],
    tools: [],
    thinking: false,
    error: m.error,
    hadImage: m.has_image,
  }));
}

export function finish(msg: ChatMessage, error?: string): ChatMessage {
  return { ...msg, pending: false, thinking: false, error: msg.error ?? error };
}
