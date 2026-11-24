import { Fragment } from "react";
import { Inline, parseMarkdown } from "./mdParse";

function Inlines({ items }: { items: Inline[] }) {
  return (
    <>
      {items.map((x, i) =>
        x.t === "b" ? (
          <strong key={i}>{x.s}</strong>
        ) : x.t === "i" ? (
          <em key={i}>{x.s}</em>
        ) : x.t === "code" ? (
          <code key={i}>{x.s}</code>
        ) : (
          <Fragment key={i}>{x.s}</Fragment>
        ),
      )}
    </>
  );
}

/** Hiển thị markdown bằng phần tử React, không dùng dangerouslySetInnerHTML. */
export default function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      {parseMarkdown(text).map((b, i) =>
        b.type === "p" ? (
          <p key={i}>
            <Inlines items={b.inl} />
          </p>
        ) : b.type === "ul" ? (
          <ul key={i}>
            {b.items.map((it, j) => (
              <li key={j}>
                <Inlines items={it} />
              </li>
            ))}
          </ul>
        ) : (
          <ol key={i}>
            {b.items.map((it, j) => (
              <li key={j}>
                <Inlines items={it} />
              </li>
            ))}
          </ol>
        ),
      )}
    </div>
  );
}
