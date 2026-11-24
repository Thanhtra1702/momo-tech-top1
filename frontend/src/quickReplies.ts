import { vnd } from "./format";
import type { UiBlock } from "./types";

/** Điểm đến lấy từ tiêu đề thẻ di chuyển dạng "Hãng: Hà Nội - Đà Nẵng". */
function destinationOf(title: string): string | null {
  const route = title.split(":").pop() ?? "";
  const parts = route.split(" - ");
  return parts.length >= 2 ? parts[parts.length - 1].trim() || null : null;
}

/** Thành phố lấy từ phụ đề thẻ lưu trú hoặc tour dạng "Đà Lạt, hồ bơi, wifi". */
function cityOf(subtitle?: string): string | null {
  const first = subtitle?.split(",")[0]?.trim();
  return first || null;
}

/**
 * Gợi ý trả lời nhanh dựa trên khối kết quả cuối của trợ lý. Hàm thuần, không gọi LLM, tối đa 3 gợi ý.
 * Chỉ dùng những gì đã hiển thị, không bịa thêm dữ kiện.
 */
export function quickReplies(blocks: UiBlock[]): string[] {
  const last = blocks[blocks.length - 1];
  if (!last) return [];
  const out: string[] = [];
  switch (last.kind) {
    case "ticket_cards": {
      const first = last.items[0];
      if (!first) break;
      const many = last.items.length >= 2;
      if (first.category === "transport") {
        const dest = destinationOf(first.title);
        if (many) out.push("So sánh các chuyến này");
        out.push("Chọn chuyến đầu tiên, đặt 1 vé");
        if (dest) out.push(`Tìm khách sạn ở ${dest}`);
      } else if (first.category === "lodging") {
        const city = cityOf(first.subtitle);
        if (many) out.push("So sánh các nơi ở này");
        if (city) out.push(`Tìm tour ở ${city}`);
        if (city) out.push(`Tìm chuyến bay đến ${city}`);
      } else if (first.category === "event") {
        if (many) out.push("So sánh các suất này");
        out.push("Đặt suất đầu tiên, 1 vé");
      } else {
        const city = cityOf(first.subtitle);
        if (city) out.push(`Lập lịch trình 3 ngày ở ${city} cho 2 người`);
        if (city) out.push(`Tìm khách sạn ở ${city}`);
      }
      break;
    }
    case "comparison_table":
      out.push("Đặt phương án nên chọn, 1 vé");
      break;
    case "itinerary":
      out.push(`Tạo chuyến đi với ngân sách ${vnd(last.total_vnd)}`, "Chia tiền cho cả nhóm");
      break;
    case "order_draft":
      out.push("Xem đơn của tôi", "Tạo ngân sách cho chuyến này");
      break;
    case "risk_report":
      out.push(last.level === "low" || last.level === "medium" ? "Kiểm tra giúp mình một tin nhắn khác" : "Làm sao để đặt vé an toàn?");
      break;
    case "budget_status":
      out.push("Ghi thêm một khoản chi", "Chia tiền cho cả nhóm");
      break;
    case "split_result":
      out.push("Xem ngân sách chuyến đi");
      break;
  }
  return out.slice(0, 3);
}
