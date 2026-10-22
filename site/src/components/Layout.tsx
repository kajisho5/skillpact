import { Head } from "vite-react-ssg";
import { Link } from "react-router-dom";
import { Moon, Sun, Menu } from "lucide-react";
import type { ReactNode } from "react";
import { latest, type Lang } from "@/content";
import { href, nav, ui, SITE, prefix, REPO } from "@/i18n";
import { Button } from "@/components/ui/button";

function ThemeToggle({ label }: { label: string }) {
  const toggle = () => {
    const d = !document.documentElement.classList.contains("dark");
    document.documentElement.classList.toggle("dark", d);
    try { localStorage.setItem("sp-theme", d ? "dark" : "light"); } catch { /* private mode */ }
  };
  return (
    <Button variant="ghost" size="icon" onClick={toggle} aria-label={label} title={label}>
      <Sun className="hidden dark:block" /><Moon className="dark:hidden" />
    </Button>
  );
}

export function Layout({ lang, slug, title, description, children, csp, wide }: {
  lang: Lang; slug: string; title: string; description: string; children: ReactNode; csp?: string; wide?: boolean;
}) {
  const t = ui[lang]; const other: Lang = lang === "en" ? "ja" : "en";
  const full = slug ? `${title} — SkillPact` : `SkillPact — ${title}`;
  const url = (l: Lang) => `${SITE}${prefix(l)}${slug ? slug + "/" : ""}`;
  return (
    <>
      <Head htmlAttributes={{ lang }}>
        {csp && <meta httpEquiv="Content-Security-Policy" content={csp} />}
        <title>{full}</title>
        <meta name="description" content={description} />
        <link rel="canonical" href={url(lang)} />
        <link rel="alternate" hrefLang="en" href={url("en")} />
        <link rel="alternate" hrefLang="ja" href={url("ja")} />
        <meta property="og:title" content={full} />
        <meta property="og:description" content={description} />
        <meta property="og:url" content={url(lang)} />
        <meta property="og:site_name" content="SkillPact" />
      </Head>
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-background focus:px-3 focus:py-2 focus:shadow">{t.skip}</a>
      <header className="sticky top-0 z-40 border-b bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/75">
        <div className="container flex h-14 max-w-[76rem] items-center gap-6">
          <Link to={`/${prefix(lang)}`} className="flex items-baseline gap-2 font-semibold tracking-tight">
            <span className="text-[1.05rem]">SkillPact</span>
            <span className="kbd hidden font-normal text-muted-foreground sm:inline">{t.draft} {latest}</span>
          </Link>
          <nav aria-label="Main" className="hidden flex-1 items-center gap-1 text-[0.875rem] lg:flex">
            {nav.slice(0, 6).map((n) => (
              <Link key={n.slug} to={`/${prefix(lang)}${n.slug}/`} aria-current={slug === n.slug ? "page" : undefined}
                className="rounded px-2.5 py-1.5 text-muted-foreground transition-colors hover:text-foreground aria-[current=page]:text-foreground aria-[current=page]:font-medium">
                {n[lang]}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1 lg:ml-0">
            <a href={href(other, slug)} hrefLang={other} lang={other} aria-label={t.langLabel}
              className="rounded px-2.5 py-1.5 text-[0.8125rem] text-muted-foreground hover:text-foreground">{t.lang}</a>
            <a href={REPO} className="hidden rounded px-2.5 py-1.5 text-[0.8125rem] text-muted-foreground hover:text-foreground sm:inline">GitHub</a>
            <ThemeToggle label={t.theme} />
            <details className="group relative lg:hidden">
              <summary className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-md hover:bg-accent [&::-webkit-details-marker]:hidden" aria-label={t.menu}>
                <Menu className="size-4" />
              </summary>
              <nav aria-label="Main" className="fixed inset-x-0 top-14 border-b bg-background px-5 pb-5 pt-2 shadow-sm">
                <ul className="grid grid-cols-2 gap-x-6">
                  {nav.map((n) => (
                    <li key={n.slug}>
                      <a href={href(lang, n.slug)} aria-current={slug === n.slug ? "page" : undefined}
                        className="block border-b py-3 text-[0.95rem] aria-[current=page]:font-semibold">{n[lang]}</a>
                    </li>
                  ))}
                </ul>
              </nav>
            </details>
          </div>
        </div>
      </header>
      <div role="note" className="border-b bg-muted/60 text-[0.8125rem]">
        <div className="container max-w-[76rem] py-2">
          {lang === "ja" ? "公開レビュー中（2026-10-22〜2026-11-21 JST）。" : "Public review open: 2026-10-22 – 2026-11-21 (JST). "}
          <a className="underline underline-offset-2" href={`${REPO}/blob/main/REVIEW.md`}>{lang === "ja" ? "参加方法（REVIEW.md）" : "How to comment (REVIEW.md)"}</a>
          {" · "}
          <a className="underline underline-offset-2" href={`${REPO}/issues/1`}>{lang === "ja" ? "進捗の issue" : "Tracking issue"}</a>
        </div>
      </div>
      <main id="main" className={wide ? "" : "container max-w-[76rem]"}>{children}</main>
      <footer className="mt-24 border-t">
        <div className="container grid max-w-[76rem] gap-8 py-10 text-[0.8125rem] text-muted-foreground sm:grid-cols-[1fr_auto]">
          <div className="space-y-1.5">
            <p className="font-medium text-foreground">SkillPact</p>
            <p>{t.footer} · © 2026 SEVENTHWELL</p>
          </div>
          <ul className="grid grid-cols-2 gap-x-8 gap-y-1.5 sm:grid-cols-4">
            {nav.map((n) => <li key={n.slug}><a className="hover:text-foreground" href={href(lang, n.slug)}>{n[lang]}</a></li>)}
            <li><a className="hover:text-foreground" href={REPO}>GitHub</a></li>
            <li><a className="hover:text-foreground" href={`${REPO}/blob/main/SECURITY.md`}>Security</a></li>
          </ul>
        </div>
      </footer>
    </>
  );
}

export function PageHeader({ eyebrow, title, lead, children }: { eyebrow?: ReactNode; title: ReactNode; lead?: ReactNode; children?: ReactNode }) {
  return (
    <div className="max-w-[46rem] pb-8 pt-12 sm:pt-16">
      {eyebrow && <p className="kbd mb-3 text-muted-foreground">{eyebrow}</p>}
      <h1 className="text-[1.75rem] font-semibold leading-[1.2] tracking-tight sm:text-[2.125rem]">{title}</h1>
      {lead && <p className="mt-4 text-[1.0625rem] leading-relaxed text-foreground/75">{lead}</p>}
      {children}
    </div>
  );
}
