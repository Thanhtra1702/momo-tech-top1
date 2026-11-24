import { parseSse } from "./sse";
import type { Mode, Order, SavedMessage, SseEvent, UpcomingItem } from "./types";

const TOKEN_KEY = "momo_token";
const USER_KEY = "momo_user";

export const auth = {
  token: () => sessionStorage.getItem(TOKEN_KEY),
  user: () => sessionStorage.getItem(USER_KEY),
  set(token: string, user: string) {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(USER_KEY, user);
  },
  clear() {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
  },
};

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function headers(json = true): HeadersInit {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  const t = auth.token();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

async function fail(res: Response): Promise<never> {
  let detail = "Có lỗi xảy ra, bạn thử lại nhé.";
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
  } catch {
    /* giữ thông báo mặc định */
  }
  if (res.status === 401) auth.clear();
  throw new ApiError(res.status, detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError(0, "Không kết nối được máy chủ, kiểm tra mạng rồi thử lại.");
  }
  if (!res.ok) return fail(res);
  return (await res.json()) as T;
}

export async function login(username: string, password: string): Promise<void> {
  const r = await request<{ token: string; username: string }>("/auth/login", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ username, password }),
  });
  auth.set(r.token, r.username);
}

export const getSamples = () => request<{ prompts: string[]; images: boolean }>("/samples");
export const getLatestConversation = () =>
  request<{ session_id: string | null; messages: SavedMessage[] }>("/conversations/latest", { headers: headers(false) });
export const listOrders = () => request<{ orders: Order[]; upcoming: UpcomingItem[] }>("/orders", { headers: headers(false) });
export const getOrder = (id: string) => request<Order>(`/orders/${encodeURIComponent(id)}`, { headers: headers(false) });
export const confirmOrder = (id: string) =>
  request<Order>(`/orders/${encodeURIComponent(id)}/confirm`, { method: "POST", headers: headers(false) });

export const getMemory = () =>
  request<{ memory: Record<string, string>; labels: Record<string, string> }>("/memory", { headers: headers(false) });
export const putMemory = (key: string, value: string) =>
  request<{ memory: Record<string, string> }>("/memory", { method: "PUT", headers: headers(), body: JSON.stringify({ key, value }) });
export const deleteMemory = (key: string) =>
  request<{ memory: Record<string, string> }>(`/memory/${encodeURIComponent(key)}`, { method: "DELETE", headers: headers(false) });
export const clearMemory = () => request<{ memory: Record<string, string> }>("/memory", { method: "DELETE", headers: headers(false) });

export interface ChatPayload {
  message: string;
  mode: Mode;
  session_id: string;
  image?: { mime: string; data: string };
}

/** Gửi tin nhắn và đọc luồng SSE. Gọi onEvent cho từng sự kiện theo thứ tự. */
export async function streamChat(payload: ChatPayload, onEvent: (e: SseEvent) => void, signal?: AbortSignal): Promise<void> {
  let res: Response;
  try {
    res = await fetch("/chat", { method: "POST", headers: headers(), body: JSON.stringify(payload), signal });
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    throw new ApiError(0, "Không kết nối được máy chủ, kiểm tra mạng rồi thử lại.");
  }
  if (!res.ok) return fail(res);
  if (!res.body) throw new ApiError(0, "Trình duyệt không hỗ trợ nhận dữ liệu theo luồng.");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parsed = parseSse(buffer);
      buffer = parsed.rest;
      parsed.events.forEach(onEvent);
    }
    buffer += decoder.decode();
    parseSse(buffer + "\n\n").events.forEach(onEvent);
  } catch (err) {
    if ((err as Error).name === "AbortError") return;
    throw new ApiError(0, "Kết nối bị gián đoạn, bạn thử lại nhé.");
  }
}

export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] ?? "");
    reader.onerror = () => reject(new Error("Không đọc được ảnh"));
    reader.readAsDataURL(file);
  });
}
