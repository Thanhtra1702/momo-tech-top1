export function vnd(value: number): string {
  return new Intl.NumberFormat("vi-VN").format(Math.round(value)) + "đ";
}

export function cell(value: string | number, column: string): string {
  // Chỉ cột có tên bắt đầu bằng "Giá" (Giá, Giá/đêm, Giá/người). Cột "Đánh giá" không phải tiền.
  if (typeof value === "number" && /^(giá|price)(\/|$)/i.test(column.trim())) return vnd(value);
  return String(value);
}

/** Chỉ cho phép mở link https, tránh javascript: hoặc data: từ dữ liệu không đáng tin. */
export function safeHttpsUrl(url: string | undefined): string | null {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.protocol === "https:" ? u.toString() : null;
  } catch {
    return null;
  }
}

export const UNIT_LABEL: Record<string, string> = { "vé": "vé", "đêm": "đêm", "người": "người" };
