#!/usr/bin/env python3
"""Render content/{en,ja}/<slug>.md to docs/<slug>/index.html and docs/ja/<slug>/index.html (stdlib only, small Markdown subset:
headings, paragraphs, lists, tables, fenced code, blockquotes, **bold**, `code`, [links](url)). Called by sitechrome.py."""
import html, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent; SRC = ROOT / "content"; DOCS = ROOT / "docs"
SITE = "https://kajisho5.github.io/skillpact/"

def slugify(t): return re.sub(r"[^\w\-]+", "-", t.lower()).strip("-")

def inline(t):
    t = html.escape(t, quote=False); codes = []
    t = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or f"\x00{len(codes)-1}\x00", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: f'<img src="{m.group(2)}" alt="{m.group(1)}">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', t)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", t)

def md(text):
    out, lines, i, toc = [], text.splitlines(), 0, []
    while i < len(lines):
        l = lines[i]
        if l.startswith("```"):
            j = i + 1; buf = []
            while j < len(lines) and not lines[j].startswith("```"): buf.append(lines[j]); j += 1
            out.append("<pre><code>" + html.escape("\n".join(buf), quote=False) + "</code></pre>"); i = j + 1; continue
        m = re.match(r"^(#{1,4}) (.*)$", l)
        if m:
            n = len(m.group(1)); hid = slugify(re.sub(r"[`*]", "", m.group(2))) or f"s{i}"
            if n == 2: toc.append((hid, m.group(2)))
            out.append(f'<h{n} id="{hid}">{inline(m.group(2))}</h{n}>'); i += 1; continue
        if l.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1]):
            cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]
            h = cells(l); rows = []; i += 2
            while i < len(lines) and lines[i].startswith("|"): rows.append(cells(lines[i])); i += 1
            out.append('<div class="tw"><table class="ft"><thead><tr>' + "".join(f'<th scope="col">{inline(c)}</th>' for c in h) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows) + "</tbody></table></div>"); continue
        if re.match(r"^(\s*)([-*]|\d+\.) ", l):
            tag = "ol" if re.match(r"^\s*\d+\. ", l) else "ul"; items = []
            while i < len(lines) and (re.match(r"^\s*([-*]|\d+\.) ", lines[i]) or (lines[i].startswith("  ") and lines[i].strip())):
                if re.match(r"^\s*([-*]|\d+\.) ", lines[i]): items.append(re.sub(r"^\s*([-*]|\d+\.) ", "", lines[i]))
                else: items[-1] += " " + lines[i].strip()
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>"); continue
        if l.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].startswith("> "): buf.append(lines[i][2:]); i += 1
            out.append("<blockquote><p>" + inline(" ".join(buf)) + "</p></blockquote>"); continue
        if not l.strip(): i += 1; continue
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|```|\||>|\s*([-*]|\d+\.) )", lines[i]): buf.append(lines[i]); i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n".join(out), toc

def page(slug, lang):
    src = (SRC / lang / f"{slug}.md").read_text(); title = re.match(r"^# (.*)$", src, re.M).group(1)
    desc = next((l for l in src.splitlines()[1:] if l.strip() and not l.startswith(("#", ">", "-", "|"))), title)[:200]
    body, toc = md(src)
    rel = "../" if lang == "en" else "../../"; canon = (f"{slug}/" if lang == "en" else f"ja/{slug}/")
    alt_en, alt_ja = SITE + f"{slug}/", SITE + f"ja/{slug}/"
    nav = ('<nav class="toc" aria-label="' + ("On this page" if lang == "en" else "このページの目次") + '"><b>' + ("Contents" if lang == "en" else "目次") + "</b><ol>"
           + "".join(f'<li><a href="#{h}">{inline(t)}</a></li>' for h, t in toc) + "</ol></nav>") if len(toc) > 3 else ""
    foot = ("Spec text CC BY 4.0 · Code Apache-2.0 · © 2026 SEVENTHWELL · " if lang == "en" else "仕様 CC BY 4.0 · コード Apache-2.0 · © 2026 SEVENTHWELL · ") + \
           f'<a href="https://github.com/kajisho5/skillpact/blob/main/content/{lang}/{slug}.md">' + ("source" if lang == "en" else "原稿") + "</a>"
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{html.escape(title)} — SkillPact</title><meta name="description" content="{html.escape(re.sub(r"[`*]", "", desc))}">\n'
            f'<link rel="canonical" href="{SITE}{canon}"><link rel="alternate" hreflang="en" href="{alt_en}"><link rel="alternate" hreflang="ja" href="{alt_ja}">\n'
            f'<link rel="stylesheet" href="{rel}assets/site.css"></head><body>\n<header class="top"></header>\n'
            f'<main id="main" class="wrap doc">\n{nav}\n<article>\n{body}\n</article></main>\n<footer class="wrap foot">{foot}</footer></body></html>\n')

def build():
    slugs = sorted({p.stem for p in (SRC / "en").glob("*.md")} | {p.stem for p in (SRC / "ja").glob("*.md")})
    for slug in slugs:
        for lang in ("en", "ja"):
            if not (SRC / lang / f"{slug}.md").exists(): continue
            d = DOCS / slug if lang == "en" else DOCS / "ja" / slug; d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(page(slug, lang))
    return slugs

if __name__ == "__main__": print(build())
