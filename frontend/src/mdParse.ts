// Bộ phân tích markdown tối giản và an toàn: chỉ sinh cấu trúc dữ liệu, không bao giờ sinh HTML thô.
// Hỗ trợ: **đậm**, *nghiêng*, `mã`, tiêu đề (#), danh sách gạch đầu dòng và đánh số, đoạn văn.

export type Inline = { t: "text" | "b" | "i" | "code"; s: string };
export type MdBlock =
  | { type: "p"; inl: Inline[] }
  | { type: "ul" | "ol"; items: Inline[][] };

const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\*[^*\s][^*\n]*\*)/g;

export function parseInline(src: string): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const m of src.matchAll(INLINE)) {
    const idx = m.index ?? 0;
    if (idx > last) out.push({ t: "text", s: src.slice(last, idx) });
    const tok = m[0];
    if (tok.startsWith("**")) out.push({ t: "b", s: tok.slice(2, -2) });
    else if (tok.startsWith("`")) out.push({ t: "code", s: tok.slice(1, -1) });
    else out.push({ t: "i", s: tok.slice(1, -1) });
    last = idx + tok.length;
  }
  if (last < src.length) out.push({ t: "text", s: src.slice(last) });
  return out;
}

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/;
const HEADING = /^\s*#{1,6}\s+(.*)$/;

export function parseMarkdown(text: string): MdBlock[] {
  const blocks: MdBlock[] = [];
  let para: string[] = [];
  let list: { type: "ul" | "ol"; items: Inline[][] } | null = null;

  const flushPara = () => {
    if (para.length) blocks.push({ type: "p", inl: parseInline(para.join("\n")) });
    para = [];
  };
  const flushList = () => {
    if (list) blocks.push(list);
    list = null;
  };

  for (const line of text.replace(/\r\n/g, "\n").split("\n")) {
    const bullet = BULLET.exec(line);
    const numbered = bullet ? null : NUMBERED.exec(line);
    const heading = bullet || numbered ? null : HEADING.exec(line);
    if (bullet || numbered) {
      flushPara();
      const type = bullet ? "ul" : "ol";
      if (list && list.type !== type) flushList();
      list ??= { type, items: [] };
      list.items.push(parseInline((bullet ?? numbered)![1]));
    } else if (heading) {
      flushPara();
      flushList();
      blocks.push({ type: "p", inl: [{ t: "b", s: heading[1].replace(/\*\*/g, "") }] });
    } else if (line.trim() === "") {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  return blocks;
}
