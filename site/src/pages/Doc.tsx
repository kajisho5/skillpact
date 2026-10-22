import { docs, parseDoc, latest, type Lang } from "@/content";
import { Layout } from "@/components/Layout";
import { Markdown } from "@/components/Markdown";
import { REPO, ui } from "@/i18n";

export function Toc({ headings, label }: { headings: { depth: number; id: string; text: string }[]; label: string }) {
  const items = headings.filter((h) => h.depth === 2);
  if (items.length < 3) return null;
  return (
    <>
      <details className="mb-8 rounded-md border px-4 py-3 text-sm lg:hidden">
        <summary className="cursor-pointer font-medium">{label}</summary>
        <ol className="mt-3 space-y-2 text-muted-foreground">{items.map((h) => <li key={h.id}><a href={`#${h.id}`}>{h.text}</a></li>)}</ol>
      </details>
      <nav aria-label={label} className="sticky top-20 hidden max-h-[calc(100vh-6rem)] overflow-y-auto text-[0.8125rem] lg:block">
        <p className="kbd mb-3 text-muted-foreground">{label}</p>
        <ol className="space-y-2 border-l">
          {items.map((h) => <li key={h.id}><a className="-ml-px block border-l border-transparent pl-3 leading-snug text-muted-foreground hover:border-foreground hover:text-foreground" href={`#${h.id}`}>{h.text}</a></li>)}
        </ol>
      </nav>
    </>
  );
}

export default function Doc({ lang, slug }: { lang: Lang; slug: string }) {
  const src = docs[lang][slug] ?? docs.en[slug];
  const { title, headings, body, desc } = parseDoc(src);
  const t = ui[lang];
  return (
    <Layout lang={lang} slug={slug} title={title} description={desc}>
      <div className="grid gap-x-16 pt-10 sm:pt-14 lg:grid-cols-[minmax(0,46rem)_13rem]">
        <article className="min-w-0">
          <p className="kbd mb-3 text-muted-foreground">SkillPact · {t.draft} {latest}</p>
          <div className="prose-sp">
            <h1>{title}</h1>
            <div className="lg:hidden"><Toc headings={headings} label={t.onThisPage} /></div>
            <Markdown>{body}</Markdown>
          </div>
          <p className="mt-16 border-t pt-4 text-[0.8125rem] text-muted-foreground">
            <a className="hover:text-foreground" href={`${REPO}/blob/main/content/${lang}/${slug}.md`}>{t.source}</a>
          </p>
        </article>
        <aside className="hidden lg:block"><Toc headings={headings} label={t.onThisPage} /></aside>
      </div>
    </Layout>
  );
}
