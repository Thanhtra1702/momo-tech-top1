// Khớp với contracts/schemas/*.json

export type Category = "event" | "transport" | "lodging" | "tour";

export interface TicketCard {
  ref_id: string;
  category: Category;
  title: string;
  subtitle?: string;
  price_vnd: number;
  price_unit?: string;
  badges?: string[];
}

export interface LiveEventResult {
  source: string;
  checked_at: string;
  results: { id: string; title: string; url: string; starts_at: string | null; price_from_vnd: number | null }[];
  has_more: boolean;
  notice: string;
}

export interface ItineraryEntry {
  time: string;
  title: string;
  cost_vnd: number;
  ref_id?: string;
}

export type UiBlock =
  | { kind: "ticket_cards"; title?: string; items: TicketCard[] }
  | { kind: "comparison_table"; columns: string[]; rows: (string | number)[][]; recommended_row?: number }
  | { kind: "itinerary"; days: { day: number; entries: ItineraryEntry[] }[]; total_vnd: number }
  | { kind: "order_draft"; order_id: string; summary: string; total_vnd?: number }
  | {
      kind: "risk_report";
      level: "low" | "medium" | "high" | "critical";
      score: number;
      headline: string;
      signals: { label: string; severity: "low" | "medium" | "high"; evidence?: string }[];
      urls: { host: string; verdict: "official" | "risky" | "unknown"; issues: string[] }[];
      advice: string[];
    }
  | {
      kind: "budget_status";
      trip: string;
      budget_vnd: number;
      spent_vnd: number;
      remaining_vnd: number;
      percent: number;
      level: "ok" | "warning" | "over";
      breakdown: { label: string; amount_vnd: number }[];
    }
  | {
      kind: "split_result";
      total_vnd: number;
      label: string;
      payer?: string;
      per_person: { name: string; share_vnd: number; owes_vnd: number; owes_to?: string }[];
      messages: string[];
    };

export interface Usage {
  prompt_tokens?: number;
  completion_tokens?: number;
  cost_usd?: number;
}

export type SseEvent =
  | { type: "text_delta"; text: string }
  | { type: "thinking" }
  | { type: "tool_status"; tool: string; status: "running" | "done" | "error"; label?: string }
  | { type: "ui_block"; block: UiBlock }
  | { type: "done"; usage?: Usage }
  | { type: "error"; message: string };

export interface OrderItem {
  ref_id: string;
  kind: Category;
  title: string;
  quantity: number;
  unit_price_vnd: number;
  deeplink?: string;
  when_at?: string | null;
}

export interface SavedMessage {
  role: "user" | "assistant";
  text: string;
  blocks?: UiBlock[];
  error?: string;
  has_image?: boolean;
}

export interface Order {
  id: string;
  status: "draft" | "confirmed" | "cancelled" | "expired";
  trip_id?: string | null;
  expires_at?: string | null;
  items: OrderItem[];
  total_vnd: number;
  created_at: string;
  confirmed_at: string | null;
}

export type Mode = "fast" | "deep";

export interface ToolStep {
  tool: string;
  label: string;
  status: "running" | "done" | "error";
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  text: string;
  blocks: UiBlock[];
  tools: ToolStep[];
  thinking: boolean;
  error?: string;
  imagePreview?: string;
  hadImage?: boolean; // tin đã khôi phục từ máy chủ: có gửi ảnh nhưng ảnh không được lưu
  pending?: boolean;
}

export interface UpcomingItem {
  order_id: string;
  ref_id: string;
  kind: Category;
  title: string;
  quantity: number;
  when_at: string;
}
