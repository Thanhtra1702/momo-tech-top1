import type { ReactNode } from "react";

// Bộ biểu tượng nét mảnh tự vẽ (SVG nội tuyến, không phụ thuộc thư viện, không vi phạm CSP).
function Svg({ children, size = 20 }: { children: ReactNode; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

type P = { size?: number };

export const IconPlane = ({ size }: P) => (
  <Svg size={size}>
    <path d="M17.8 19.2 16 11l3.5-3.5C21 6 21.5 4 21 3c-1-.5-3 0-4.5 1.5L13 8 4.8 6.2c-.5-.1-.9.1-1.1.5l-.3.5c-.2.5-.1 1 .3 1.3L9 12l-2 3H4l-1 1 3 2 2 3 1-1v-3l3-2 3.5 5.3c.3.4.8.5 1.3.3l.5-.2c.4-.3.6-.7.5-1.2z" />
  </Svg>
);
export const IconFilm = ({ size }: P) => (
  <Svg size={size}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4" />
  </Svg>
);
export const IconBed = ({ size }: P) => (
  <Svg size={size}>
    <path d="M3 19V6M3 14h18v5M21 14v-2.5A2.5 2.5 0 0 0 18.5 9H11v5" />
    <circle cx="7" cy="11" r="1.6" />
  </Svg>
);
export const IconCompass = ({ size }: P) => (
  <Svg size={size}>
    <circle cx="12" cy="12" r="9" />
    <path d="m15.5 8.5-2 5-5 2 2-5z" />
  </Svg>
);
export const IconShield = ({ size }: P) => (
  <Svg size={size}>
    <path d="M12 3 4.5 6v5.5c0 4.6 3.1 7.7 7.5 9.5 4.4-1.8 7.5-4.9 7.5-9.5V6z" />
    <path d="m9 12 2 2 4-4" />
  </Svg>
);
export const IconWallet = ({ size }: P) => (
  <Svg size={size}>
    <rect x="3" y="6" width="18" height="14" rx="2.5" />
    <path d="M3 10h18M16 15h2" />
  </Svg>
);
export const IconSplit = ({ size }: P) => (
  <Svg size={size}>
    <circle cx="8" cy="8" r="3" />
    <circle cx="17" cy="9" r="2.4" />
    <path d="M2.5 20c.4-3.2 2.6-5 5.5-5s5.1 1.8 5.5 5M15 15.3c2.6-.4 5 1 5.5 4.7" />
  </Svg>
);
export const IconList = ({ size }: P) => (
  <Svg size={size}>
    <path d="M9 6h12M9 12h12M9 18h12M4 6h.01M4 12h.01M4 18h.01" />
  </Svg>
);
export const IconSend = ({ size }: P) => (
  <Svg size={size}>
    <path d="m22 2-11 11M22 2l-7 20-4-9-9-4z" />
  </Svg>
);
export const IconStop = ({ size }: P) => (
  <Svg size={size}>
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </Svg>
);
export const IconMic = ({ size }: P) => (
  <Svg size={size}>
    <rect x="9" y="2.5" width="6" height="12" rx="3" />
    <path d="M5 11.5a7 7 0 0 0 14 0M12 18.5V22" />
  </Svg>
);
export const IconImage = ({ size }: P) => (
  <Svg size={size}>
    <rect x="3" y="4" width="18" height="16" rx="2.5" />
    <circle cx="9" cy="10" r="1.7" />
    <path d="m21 16-5-5-9 9" />
  </Svg>
);
export const IconBolt = ({ size }: P) => (
  <Svg size={size}>
    <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
  </Svg>
);
export const IconSparkle = ({ size }: P) => (
  <Svg size={size}>
    <path d="m12 3 1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.7 1.8L21.5 18.5l-1.8.7L19 21l-.7-1.8-1.8-.7 1.8-.7z" />
  </Svg>
);
export const IconMemory = ({ size }: P) => (
  <Svg size={size}>
    <ellipse cx="12" cy="6" rx="8" ry="3" />
    <path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
  </Svg>
);
export const IconPlus = ({ size }: P) => (
  <Svg size={size}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);
export const IconCheck = ({ size }: P) => (
  <Svg size={size}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </Svg>
);
export const IconAlert = ({ size }: P) => (
  <Svg size={size}>
    <path d="M12 3 2.5 20h19z" />
    <path d="M12 10v4.5M12 17.5h.01" />
  </Svg>
);
export const IconClose = ({ size }: P) => (
  <Svg size={size}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Svg>
);
export const IconLogout = ({ size }: P) => (
  <Svg size={size}>
    <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M19 12H9" />
  </Svg>
);
export const IconArrowLeft = ({ size }: P) => (
  <Svg size={size}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </Svg>
);
export const IconExternal = ({ size }: P) => (
  <Svg size={size}>
    <path d="M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4" />
  </Svg>
);

export const CATEGORY_ICON = { event: IconFilm, transport: IconPlane, lodging: IconBed, tour: IconCompass } as const;

/** Chọn biểu tượng cho một câu gợi ý theo nội dung. */
export function iconForPrompt(text: string): (p: P) => JSX.Element {
  const t = text.toLowerCase();
  if (/(lịch trình|kế hoạch)/.test(t)) return IconCompass;
  if (/(khách sạn|lưu trú|homestay|resort|phòng)/.test(t)) return IconBed;
  if (/(bay|tàu|xe khách|chuyến)/.test(t)) return IconPlane;
  if (/(phim|concert|nhạc|sự kiện|vé)/.test(t)) return IconFilm;
  return IconSparkle;
}
