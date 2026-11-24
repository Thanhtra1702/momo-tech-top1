// Nhập bằng giọng nói qua Web Speech API của trình duyệt. Âm thanh do trình duyệt xử lý, máy chủ của ta không nhận âm thanh.
// Chrome và Edge hỗ trợ; Firefox thì không. Cần HTTPS hoặc localhost để được cấp quyền micro.

interface RecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string };
}
interface RecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<RecognitionResultLike>;
}
export interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: RecognitionEventLike) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
type RecognitionCtor = new () => Recognition;

export function recognitionCtor(w: Record<string, unknown> = window as unknown as Record<string, unknown>): RecognitionCtor | null {
  return ((w.SpeechRecognition ?? w.webkitSpeechRecognition) as RecognitionCtor | undefined) ?? null;
}

export const VOICE_ERRORS: Record<string, string> = {
  "not-allowed": "Bạn chưa cho phép dùng micro. Hãy cấp quyền micro cho trang này rồi thử lại.",
  "service-not-allowed": "Trình duyệt không cho phép nhận giọng nói trên trang này.",
  "no-speech": "Mình chưa nghe thấy gì, bạn thử nói lại nhé.",
  "audio-capture": "Không tìm thấy micro.",
  network: "Không kết nối được dịch vụ nhận giọng nói của trình duyệt.",
};

export function voiceErrorMessage(code: string): string {
  return VOICE_ERRORS[code] ?? "Không nhận được giọng nói, bạn thử lại nhé.";
}

/** Ghép phần nhận dạng cuối cùng của một lần nghe vào văn bản đang gõ. */
export function appendTranscript(current: string, transcript: string): string {
  const t = transcript.trim();
  if (!t) return current;
  return current.trim() ? `${current.trim()} ${t}` : t;
}

export function finalTranscript(e: RecognitionEventLike): string {
  let out = "";
  for (let i = e.resultIndex; i < e.results.length; i++) {
    if (e.results[i].isFinal) out += e.results[i][0].transcript;
  }
  return out;
}
