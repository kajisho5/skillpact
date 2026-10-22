import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";
import type { ReactNode } from "react";

function H({ level, id, children }: { level: number; id?: string; children?: ReactNode }) {
  const Tag = `h${level}` as "h2";
  return <Tag id={id}>{children}{id && level > 1 && <a className="anchor" href={`#${id}`} aria-label="Permalink">#</a>}</Tag>;
}
// GFM's autolink-literal swallows full-width punctuation after a bare URL (common in Japanese text).
// Turn bare ASCII URLs outside code into explicit <autolinks> so the URL ends where the ASCII ends.
function fixBareUrls(md: string) {
  let fence = false;
  return md.split("\n").map((l) => {
    if (l.startsWith("```")) fence = !fence;
    if (fence) return l;
    return l.split(/(`[^`]*`)/).map((seg, i) => i % 2 ? seg : seg.replace(/(^|[^(<\w])(https?:\/\/[A-Za-z0-9\-._~:/?#@!$&'*+,;=%]+?)(?=[.,;:]?(?:[^A-Za-z0-9\-._~:/?#@!$&'*+,;=%]|$))/g, "$1<$2>")).join("");
  }).join("\n");
}
export function Markdown({ children }: { children: string }) {
  children = fixBareUrls(children);
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSlug]}
      components={{
        h2: (p) => <H level={2} id={p.id}>{p.children}</H>,
        h3: (p) => <H level={3} id={p.id}>{p.children}</H>,
        h4: (p) => <H level={4} id={p.id}>{p.children}</H>,
        pre: (p) => <pre tabIndex={0}>{p.children}</pre>,
        table: (p) => <div className="tbl-wrap"><table>{p.children}</table></div>,
        a: ({ href, children }) => {
          const ext = href?.startsWith("http");
          return <a href={href} {...(ext ? { rel: "noopener" } : {})}>{children}</a>;
        },
      }}>
      {children}
    </ReactMarkdown>
  );
}
